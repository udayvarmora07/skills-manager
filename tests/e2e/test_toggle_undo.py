"""4.7b — one click is one request, and a disable can be put back.

The stdlib suite (`tests/test_redesign_toggle_guard.py`) pins the SHAPE: the
guard precedes the request, both buttons carry `:disabled="busy"`, the undo
shares one helper with the button, and the sentence names the verb it
performed. Every one of those is a statement about source text.

This file is the half that can only be observed by driving the page, because
**no stdlib test renders the template** — the lesson 4.4 recorded after
`detailObservation` threw inside render and unmounted the whole app while
`node --check` and the entire stdlib suite stayed green.

What only a browser can settle:

* a second press inside one tick really is one POST, counted on the wire
  rather than read out of a `:disabled` attribute;
* the button is visibly disabled while the request is in flight;
* the Undo button exists, and pressing it re-enables the skill and puts the
  row back to `Active`;
* the toast names the scope by its observed label, not the wire slug.

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
import sys
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright


def _has_chromium():
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: this counts real POSTs against a live "
    "server, which is NOT verified by this skip",
)
class ToggleUndoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-toggle-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                real_home, ".cache", "ms-playwright")
        # RULES #8: the agent SCOPES come from HOME, not the data dir, so a
        # fixture server started without this walks the real ~/.codex.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        for name, body in (("toggle-target", "# toggle target\n\nAn ordinary skill."),
                           ("toggle-neighbour", "# neighbour\n\nAnother skill.")):
            cls.store.create(name, f"Fixture {name}.", body=body)
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        import shutil

        cls.server.shutdown()
        cls.thread.join(timeout=5)
        for key, value in cls._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def _reset_fixture(cls):
        """Put BOTH skills back to Active.

        The server is one per class and `Store` is the source of truth on disk,
        so a skill disabled by one test is still disabled for the next — which
        silently inverted two tests: the "disable" test ran against an already
        -disabled skill (so its button said Enable and no Undo appeared), and
        the label test read the enable sentence. **A shared fixture whose state
        one test writes is two tests sharing a variable**, and unittest runs
        them in alphabetical order, so the failure lands on whichever ran
        second.
        """
        # Through the REST API the product itself uses, not the filesystem:
        # `Store` exposes no data-dir accessor and RULES #1 keeps this test out
        # of store.py's internals. One request per skill that is currently
        # disabled, so the fixture is restored whether or not the previous test
        # touched it.
        import urllib.error
        import urllib.request

        for name in ("toggle-target", "toggle-neighbour"):
            req = urllib.request.Request(
                cls.server.url + "/api/skills/" + name + "/enable?scope=global",
                method="POST", data=b"")
            try:
                with urllib.request.urlopen(req, timeout=10):
                    pass
            except urllib.error.HTTPError as exc:
                # 400 "already enabled" is the state we are restoring to, not
                # a failure. Asserting the call succeeds would make the reset
                # fail on exactly the runs where the previous test did nothing.
                if exc.code != 400:
                    raise

    def setUp(self):
        self._reset_fixture()
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        self._page.wait_for_timeout(300)
        self.posts = []
        self._page.on("request", self._on_request)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _on_request(self, request):
        # Counted on the WIRE. The `:disabled` attribute is what this file is
        # trying to check, so reading it to decide the request would be the
        # assertion agreeing with itself.
        if request.method == "POST" and "/disable" in request.url:
            self.posts.append(request.url)
        if request.method == "POST" and "/enable" in request.url:
            self.posts.append(request.url)

    def _open(self, name="toggle-target"):
        """Select a row by CLICKING it.

        4.2 recorded that the FIRST row of `.skilllist` does not open the
        detail pane on a dispatched click (a group with no `primary`), so this
        clicks the row whose key matches and falls back to the app's own
        selector — it never writes `selectedName` directly, which would
        fabricate the very selection under test.
        """
        self._page.wait_for_selector(
            '.skilllist > li[data-skill-key]:has-text("%s")' % name, timeout=10000)
        self._page.click('.skilllist > li[data-skill-key]:has-text("%s")' % name)
        self._page.wait_for_selector(".detail-actions", timeout=10000)
        self._page.wait_for_timeout(200)

    def _toggle_button(self):
        return self._page.locator('.detail-actions button:has-text("Disable"), '
                                  '.detail-actions button:has-text("Enable")').first

    def _latest_toast(self):
        """The NEWEST toast, by stack order.

        Not `locator(...).first`. The disable toast lives 8 seconds — which is
        the whole point of this task — so a test that enables straight after a
        disable finds the disable toast still on screen and reads ITS Undo as
        the enable path's. My first draft of the enable test did exactly that
        and reported 1 != 0 against a correct product. A stack is ordered and
        the newest entry is the last child; counting over the stack instead
        would be true for either toast and assert nothing.
        """
        return self._page.locator(".toast").last

    def _wait_for_latest_toast(self):
        """Wait for a toast, then resolve `.last` FRESH.

        `wait_for_selector(".toast")` is satisfied by any toast already on
        screen, and a Playwright locator is LAZY: `locator(".toast").last`
        returned before this action captured the old stack, so the count came
        back 0 against a toast that had the Undo. My first draft had exactly
        this bug and its failure message blamed the product's design decision
        rather than its own timing. `.last` is re-resolved after the wait AND
        the stack is asserted to have grown, so a stale toast cannot be read as
        this action's.
        """
        before = self._page.locator(".toast").count()
        self._page.wait_for_function(
            "n => document.querySelectorAll('.toast').length > n", arg=before,
            timeout=10000)
        return self._latest_toast()

    def test_a_second_press_in_one_tick_is_one_request(self):
        """The defect 4.7b measured: two dispatches, two POSTs, and the
        second one's rejection — the backend's own sentence, lower case and
        single-quoted — reaching the screen beside the product's voice."""
        self._open()
        # Two clicks in ONE tick, not two clicks with a wait between them: the
        # attribute `:disabled="busy"` cannot stop the second one on its own,
        # which is why the handler guards too and why both halves are tested.
        self._page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('.detail-actions button')]
                .find(x => /Disable|Enable/.test(x.textContent));
              b.click(); b.click(); b.click();
            }""")
        self._page.wait_for_timeout(1200)
        self.assertEqual(
            len(self.posts), 1,
            "three presses of one button are one decision, not three; "
            f"measured: {self.posts}")

    def test_the_button_is_visibly_disabled_while_a_request_is_in_flight(self):
        """The other half, asserted separately: a guard alone leaves the
        button looking clickable, and an attribute alone cannot stop two
        dispatches inside a single frame. Neither substitutes for the other."""
        self._open()
        busy_seen = self._page.evaluate(
            """async () => {
              const b = [...document.querySelectorAll('.detail-actions button')]
                .find(x => /Disable|Enable/.test(x.textContent));
              b.click();
              // Sampled synchronously after the click dispatch, before the
              // response can settle.
              await new Promise(r => setTimeout(r, 0));
              return { disabled: b.disabled, now: b.textContent.trim() };
            }""")
        self.assertTrue(
            busy_seen["disabled"],
            "the Disable/Enable button looked clickable while its own request "
            "was in flight; measured: %r" % (busy_seen,))

    def test_disabling_offers_an_undo_that_re_enables_the_skill(self):
        """2.3 built this — the third `toast()` argument, the button in the
        markup, an 8s window and `undoToast` — and measured, nothing in the
        product had ever passed it. It was unreachable until this task."""
        self._open()
        self._toggle_button().click()
        # Wait for THIS toast rather than counting immediately: the previous
        # version asserted on a count taken before the toast had rendered, so
        # it failed for a timing reason while its message named a design
        # decision. The assertion is about the Undo, so the wait is about the
        # Undo's own surface existing.
        toast = self._wait_for_latest_toast()
        self.assertEqual(
            toast.locator(".toast-undo").count(), 1,
            "a disable the reader cannot put back is an action with no "
            "consequence stated and no way home")

        toast.locator(".toast-undo").click()
        self._page.wait_for_selector(
            '.skilllist > li[data-skill-key]:has-text("toggle-target") '
            '.identity-state:text-is("Active")', timeout=10000)
        self.assertTrue(
            any("/enable" in url for url in self.posts),
            "the Undo must send the inverse action; measured: %r" % (self.posts,))

    def test_enabling_offers_no_undo(self):
        """Re-enabling IS the restore. An Undo on it would offer the action the
        reader just took and burn the 8s window getting them back to the start.
        """
        # Leave the skill DISABLED (no Undo press), so the next press really is the
        # ENABLE path. My first draft pressed Undo first and then called the
        # second press "the enable path" — it was a second DISABLE, and the
        # assertion failed for that reason alone.
        self._open()
        self._toggle_button().click()
        self._page.wait_for_selector(
            '.skilllist > li[data-skill-key]:has-text("toggle-target") '
            '.identity-state:text-is("Disabled")', timeout=10000)

        self._open()
        self.assertEqual(
            self._toggle_button().inner_text().strip(), "Enable",
            "the fixture must reach the enable path for this test to mean "
            "anything; a disable here would assert the opposite of its claim")
        self._toggle_button().click()
        # Scoped to the NEWEST toast. The disable toast above is still within
        # its 8s window, so a whole-stack count would find its Undo and call
        # it this one.
        enable_toast = self._wait_for_latest_toast()
        self.assertEqual(
            enable_toast.locator(".toast-undo").count(), 0,
            "the enable path must not offer an Undo")

    def test_the_toast_names_the_scope_by_its_observed_label(self):
        """Not the wire slug. `disabled in claude-code.` beside a Library row
        whose chip said `Claude Code` is two names for one location, and RULES
        #12 says the UI states only observed facts — the label IS what the
        backend observed."""
        self._open()
        self._toggle_button().click()
        text = self._wait_for_latest_toast().inner_text()
        self.assertIn("Disabled in", text, f"measured toast: {text!r}")
        self.assertNotIn("-code", text,
                         f"a wire slug reached the sentence: {text!r}")


if __name__ == "__main__":
    unittest.main()