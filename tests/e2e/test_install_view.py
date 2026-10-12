"""The Install view, driven for real — the first run that has ever SEEN it.

5.1c. 5.1 built the view, 5.1b moved the runner form onto it, and both closed
with the same honest gap written in the same words: **24 source-text contracts,
no e2e, no screenshots**. Every assertion either matched a string in
``index.html`` or matched a string in ``app.js``. A string in a template can
prove the control is *written*; it cannot prove it is *reachable*, cannot see a
clip, and cannot see whether the command line a reader copies is the command
line that would run. That last one is the whole reason this file exists.

Four things are measured here that no source assertion could measure:

1. **The workflow toggle actually moves between two forms.** The
   ``install.mode`` default is ``registry``; if the buttons were inert the
   Installer half would be unreachable at every width and every contract would
   still pass, because the runner form's markup is in the template either way.
2. **Both halves' controls are hit-testable at 390/768/1280.** Layout boxes do
   not report clipping (this repo has now been bitten three times: the nav
   drawer, the ``<details>`` explainer, the `.selection-hint`); the question a
   reader has is "can I reach the thing", so ``document.elementFromPoint``
   answers it.
3. **The dry-run label flips.** ``-l`` was ticked while the primary button said
   "Run" — the one label in this view that could overstate the press.
4. **The printed command IS the command that runs.** ``installPreview()`` is
   read from the live app and compared to the painted ``.install-cmd-text``,
   after driving every control that feeds it. A template that assembled its own
   string would pass every existing contract and fail here.

SKIPS LOUDLY when Playwright or the fixture is absent (never a silent pass).
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright

WIDTHS = (390, 768, 1280)


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
    "Playwright/Chromium unavailable: reachability, the workflow toggle and "
    "the printed command are only observable through a real engine, and are "
    "NOT verified by this skip",
)
class InstallViewTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-install-")
        # RULES #8. The Store takes a data dir, but the AGENT SCOPES come from
        # HOME — 4.2 slice A walked the maintainer's real ~/.codex because this
        # redirect was missing, and read-only is still not permitted.
        cls._saved_env = {
            k: os.environ.get(k)
            for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                      "PLAYWRIGHT_BROWSERS_PATH")
        }
        browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if not browsers:
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            browsers = os.path.join(real_home, ".cache", "ms-playwright")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers

        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        # The Install view reads a REGISTRY, not the library, so an empty store
        # is a correct fixture here — but the rail renders and the page still
        # has to mount, so one skill keeps the shell honest.
        cls.store.create(
            "install-fixture",
            "A fixture skill so the shell has something to render.",
            body="# install-fixture\n\nFixture body.\n",
        )
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()
            cls.thread.join(timeout=5)
        for key, value in cls._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH") is None:
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._page.goto(self.server.url, wait_until="domcontentloaded")
        self._page.wait_for_selector("#nav-drawer", state="attached", timeout=20000)
        self._open_install()

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    # -- navigation -----------------------------------------------------------

    def _open_install(self):
        """Click the rail's Install destination, drawer and all.

        Below 761px the rail IS the drawer, so a `click()` on a button that is
        in the DOM and off screen waits out Playwright's full timeout and then
        reports a timeout rather than a navigation problem. `shots.sh` has had
        this blind spot since 2.1e2; this file does it by construction.
        """
        self._page.wait_for_selector(".nav-drawer-trigger", state="attached", timeout=20000)
        if self._page.evaluate(
            "() => { const t = document.querySelector('.nav-drawer-trigger');"
            " if (!t) return false; const r = t.getBoundingClientRect();"
            " return r.width > 0 && r.height > 0; }"
        ):
            self._page.click(".nav-drawer-trigger")
            self._page.wait_for_selector("#nav-drawer.open", timeout=10000)
        # `#nav-drawer button[data-tip='Install']` — the destinations live in the
        # navigation rail, which is the SAME element as the phone drawer (2.1e2).
        # There is no `.sidebar` button for them; `.sidebar` is the list pane.
        self._page.click("#nav-drawer button[data-tip='Install']")
        self._page.wait_for_selector(".install-shell", timeout=15000)

    def _set_width(self, width):
        self._page.set_viewport_size({"width": width, "height": 900})
        self._page.wait_for_timeout(120)

    def _mode(self):
        return self._page.evaluate("() => window.__skillsManagerApp.install.mode")

    def _select(self, mode):
        self._page.click(f".install-workflow-btn[data-install-workflow='{mode}']")
        self._page.wait_for_timeout(60)

    # -- 1. the toggle actually moves -----------------------------------------

    def test_the_workflow_toggle_replaces_one_form_with_the_other(self):
        """Not "both forms exist in the markup" — they do, and that is the trap.

        `install.mode` ships as `registry`, so an inert toggle leaves the
        Installer form permanently unreachable and every source contract green.
        """
        self.assertEqual("registry", self._mode())
        self._select("runner")
        self.assertEqual("runner", self._mode())
        self._select("registry")
        self.assertEqual("registry", self._mode())

    def test_the_pressed_state_says_which_half_is_shown(self):
        """`aria-pressed` is the only thing telling a screen reader the mode
        changed; the `btn-primary` class alone is a colour."""
        self.assertEqual(
            "true",
            self._page.get_attribute(".install-workflow-btn[data-install-workflow='registry']", "aria-pressed"),
        )
        self._select("runner")
        self.assertEqual(
            "true",
            self._page.get_attribute(".install-workflow-btn[data-install-workflow='runner']", "aria-pressed"),
        )
        self.assertEqual(
            "false",
            self._page.get_attribute(".install-workflow-btn[data-install-workflow='registry']", "aria-pressed"),
        )

    def test_the_scope_note_changes_with_the_mode(self):
        """"Nothing on this page writes to disk" is true until Installer runs."""
        registry_note = self._page.eval_on_selector(".install-scope-note", "el => el.textContent")
        self._select("runner")
        runner_note = self._page.eval_on_selector(".install-scope-note", "el => el.textContent")
        self.assertNotEqual(registry_note, runner_note)
        self.assertIn("writes to disk", registry_note)
        self.assertNotIn("writes to disk", runner_note)

    # -- 2. both halves' controls are reachable at every width ----------------

    def _reachable(self, selector):
        """Can a reader actually press this, HERE.

        `elementFromPoint` returns null for any point outside the viewport, so a
        control below the fold on a 900px-tall window reads as unreachable when
        it is merely not scrolled to. Scrolling first is what makes the question
        honest; without it this helper fails every long form at 390px and the
        suite becomes a second, worse copy of `shots.sh`'s blind spot.
        """
        return self._page.evaluate(
            """(sel) => {
              const b = document.querySelector(sel);
              if (!b) return {missing: true};
              const cs = getComputedStyle(b);
              if (cs.display === 'none' || cs.visibility === 'hidden') return {hidden: true};
              b.scrollIntoView({block: 'center', behavior: 'instant'});
              const r = b.getBoundingClientRect();
              if (r.width < 1 || r.height < 1) return {zero: true, w: r.width, h: r.height};
              const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
              const hit = (cy >= 0 && cy <= window.innerHeight)
                ? document.elementFromPoint(cx, cy) : null;
              return {w: Math.round(r.width), h: Math.round(r.height),
                      hit: !!hit && (hit === b || b.contains(hit)),
                      overflowsHorizontally: r.right > window.innerWidth + 1,
                      docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth};
            }""",
            selector,
        )

    def test_the_registry_halfs_controls_are_reachable_at_every_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                self._open_install()
                self._select("registry")
                self._set_width(width)
                for sel in (".install-workflow-btn[data-install-workflow='registry']",
                            "[data-install-tab='curated']",
                            "[data-install-tab='browse']",
                            "[data-install-tab='search']",
                            ".install-precondition",
                            ".install-panel"):
                    state = self._reachable(sel)
                    self.assertFalse(state.get("missing"), f"{width}px {sel} is absent")
                    self.assertFalse(state.get("hidden"), f"{width}px {sel} is display:none")
                    self.assertFalse(state.get("zero"), f"{width}px {sel} has no box: {state}")
                    self.assertTrue(state.get("hit"), f"{width}px {sel} is not hit-testable: {state}")

    def test_the_installer_halfs_controls_are_reachable_at_every_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                self._open_install()
                self._select("runner")
                self._set_width(width)
                for sel in ("#install-source", "#install-runner", "#install-scope",
                            "#install-agents", "#install-filter",
                            ".install-cmd-text", ".install-cmd .btn"):
                    state = self._reachable(sel)
                    self.assertFalse(state.get("missing"), f"{width}px {sel} is absent")
                    self.assertFalse(state.get("hidden"), f"{width}px {sel} is display:none")
                    self.assertFalse(state.get("zero"), f"{width}px {sel} has no box: {state}")
                    self.assertTrue(state.get("hit"), f"{width}px {sel} is not hit-testable: {state}")

    def test_no_horizontal_overflow_at_any_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                self._open_install()
                self._set_width(width)
                self.assertEqual(0, self._reachable(".install-shell")["docOverflow"])
                self._select("runner")
                self.assertEqual(0, self._reachable(".install-shell")["docOverflow"])

    # -- 3. the dry-run label flips -------------------------------------------

    def test_the_primary_button_says_what_the_press_will_do(self):
        self._select("runner")
        self.assertEqual("Run", self._page.eval_on_selector(
            ".install-runner-actions .btn-primary", "el => el.textContent.trim()"))
        self._page.check('.check-row:has-text("List only") input')
        self.assertEqual("List only", self._page.eval_on_selector(
            ".install-runner-actions .btn-primary", "el => el.textContent.trim()"))
        self.assertIn(" -l", self._page.eval_on_selector(
            ".install-cmd-text", "el => el.textContent"))
        self._page.uncheck('.check-row:has-text("List only") input')
        self.assertEqual("Run", self._page.eval_on_selector(
            ".install-runner-actions .btn-primary", "el => el.textContent.trim()"))

    def test_an_empty_source_cannot_run_anything(self):
        """The guard has to be on the control, not only inside the handler.

        `installRunnerReady` is `false` for an empty source; if `:disabled` were
        dropped from the template the button would still refuse (and still toast
        a sentence), so the source assertion could not tell the difference. A
        reader pressing a dead button learns nothing; a reader pressing a
        refusing button learns that a field above it is required.
        """
        self._select("runner")
        btn = ".install-runner-actions .btn-primary"
        self.assertTrue(self._page.is_disabled(btn), "an empty source is already runnable")
        self._page.fill("#install-source", "vercel-labs/agent-skills")
        self.assertFalse(self._page.is_disabled(btn))

    # -- 4. the printed command IS the command that runs ----------------------

    def test_the_printed_command_is_the_one_installpreview_builds(self):
        """The whole point. 5.1b made `installPreview()` the single assembler and
        Copy/`runInstall` both read it — but "they both read it" is a claim about
        source text, and the third reader is the painted string."""
        self._select("runner")
        self._page.fill("#install-source", "vercel-labs/agent-skills")
        self._page.select_option("#install-runner", "pnpm")
        self._page.select_option("#install-scope", "project")
        self._page.fill("#install-agents", "claude-code, codex")
        self._page.dispatch_event("#install-agents", "change")
        self._page.fill("#install-filter", "commit-signoff-policy")
        self._page.check('.check-row:has-text("Copy into each scope") input')
        self._page.check('.check-row:has-text("List only") input')

        painted = self._page.eval_on_selector(".install-cmd-text", "el => el.textContent.trim()")
        built = self._page.evaluate("() => window.__skillsManagerApp.installPreview()")
        self.assertEqual(built, painted)
        # And the shape a reader would check by eye.
        self.assertTrue(painted.startswith("pnpm dlx skills add vercel-labs/agent-skills"), painted)
        for token in ("-a claude-code", "-a codex", "-s commit-signoff-policy",
                      "--copy", "-l"):
            self.assertIn(token, painted, painted)
        self.assertNotIn(" -g ", painted, "project scope must not emit the global flag")

    def test_copy_sends_the_same_string_it_paints(self):
        """Copy is a second reader of the same sentence. A clipboard shim is the
        only way to see what the button actually hands over."""
        self._select("runner")
        self._page.fill("#install-source", "acme/skills")
        self._page.evaluate(
            """() => { window.__copied = null;
                Object.defineProperty(navigator, 'clipboard', {configurable: true,
                  value: {writeText: (t) => { window.__copied = t; return Promise.resolve(); }}}); }"""
        )
        self._page.click(".install-cmd .btn")
        self._page.wait_for_timeout(150)
        copied = self._page.evaluate("() => window.__copied")
        painted = self._page.eval_on_selector(".install-cmd-text", "el => el.textContent.trim()")
        self.assertEqual(painted, copied)

    # -- 5. the states 5.1 could never reach ----------------------------------

    def test_a_seeded_listing_renders_rows_and_its_cache_state(self):
        """`browse`/`curated` need a project token the sandbox has not got, so
        this list had never been rendered by anything. `install` is a plain
        reactive object, so a nested assignment from the page is a faithful
        stand-in for a response — and the payload below is deliberately ragged,
        because `_validate_listing` only checks that `data` is a list."""
        self._select("registry")
        self._page.click("[data-install-tab='browse']")
        self._page.evaluate(
            """() => { window.__skillsManagerApp.install.lastResult = {
                data: [
                  {name: 'commit-signoff-policy', source: 'acme/agent-skills', installs: 1284},
                  {name: 'kubectl-runbook', source: 'opsco/tools', installs: 93},
                  {name: 'repo-without-a-source'},      /* source & installs absent */
                  null,                                 /* dropped by the normaliser */
                ],
                _registry: {cache_state: 'refreshed', stale: false},
            }; }"""
        )
        self._page.wait_for_selector(".registry-list", timeout=5000)
        rows = self._page.locator(".registry-row").all_text_contents()
        self.assertEqual(3, len(rows), rows)
        self.assertIn("commit-signoff-policy", rows[0])
        self.assertIn("1,284 installs", rows[0])
        # The row the registry sent with nothing in it must say so, not render blank.
        self.assertIn("without a source or an install count", rows[2])
        # `stale: false` must NOT raise the cache banner — it is gated on the boolean.
        self.assertEqual(0, self._page.locator(".install-cache-banner").count())
        self.assertIn("Refreshed", self._page.eval_on_selector(".install-precondition", "el => el.textContent"))

    def test_only_a_stale_response_raises_the_cache_banner(self):
        """The banner is about `stale`, not about a cache existing: `fresh`,
        `refreshed` and `miss` all mean the answer came from the registry."""
        for state, banner in (("fresh", False), ("refreshed", False), ("miss", False), ("stale", True)):
            with self.subTest(cache_state=state):
                self._select("registry")
                self._page.evaluate(
                    """(state) => { window.__skillsManagerApp.install.lastResult = {
                        data: [{name: 'entry', source: 'acme/one', installs: 1}],
                        _registry: {cache_state: state, stale: state === 'stale'},
                    }; }""",
                    state,
                )
                self._page.wait_for_timeout(60)
                self.assertEqual(
                    banner,
                    self._page.locator(".install-cache-banner").count() == 1,
                    f"cache_state={state}",
                )

    def test_the_listing_reads_as_a_list_and_not_as_browser_defaults(self):
        """The defects 5.1c's screenshots found, stated as properties.

        `.registry-list` and `.registry-row` had **no CSS rule at all**, so the
        results list wore what a `<ul>` wears when nobody styles it: `disc`
        markers, a 40px indent, and — because an unstyled `<li>` is
        `display: list-item` — `.registry-row-state` falling to its OWN LINE
        under the name, even though it was written as a flex row's trailing
        cell with `flex: none`. Every assertion 5.1 and 5.1b made was about
        whether the markup was present; none of them could see that.

        Asserted as properties rather than as exact numbers so a padding change
        does not have to be fought: no marker, no inherited indent, and the
        trailing state on the SAME line as the name it belongs to.
        """
        self._select("registry")
        self._page.click("[data-install-tab='browse']")
        self._page.evaluate(
            """() => { window.__skillsManagerApp.install.lastResult = {
                data: [{name: 'commit-signoff-policy', source: 'anthropics/skills', installs: 12841}],
                _registry: {cache_state: 'refreshed', stale: false},
            }; }"""
        )
        self._page.wait_for_selector(".registry-list", timeout=5000)
        measured = self._page.evaluate(
            """() => {
              const ul = document.querySelector('.registry-list');
              const li = document.querySelector('.registry-row');
              const name = li.querySelector('.row-name').getBoundingClientRect();
              const state = li.querySelector('.registry-row-state').getBoundingClientRect();
              return {listStyle: getComputedStyle(ul).listStyleType,
                      display: getComputedStyle(li).display,
                      ulPad: parseFloat(getComputedStyle(ul).paddingLeft),
                      sameLine: Math.abs(name.top - state.top) < 4,
                      stateLeftOfName: state.left < name.left,
                      hitsName: state.left >= name.right - 1};
            }"""
        )
        self.assertEqual("none", measured["listStyle"], "the browser's bullet is back")
        self.assertEqual("flex", measured["display"], "the row stopped being a row")
        self.assertEqual(0, measured["ulPad"], "the browser's 40px list indent is back")
        self.assertTrue(measured["sameLine"],
                        f'"Listed" is on its own line again: {measured}')
        self.assertFalse(measured["stateLeftOfName"], measured)
        self.assertTrue(measured["hitsName"],
                        f'"Listed" no longer trails the name: {measured}')

    def test_the_stale_toggle_keeps_its_last_words_at_every_width(self):
        """A label that says what happens when the registry is unreachable,
        amputated at "could be reach—" by its own flex parent.

        `flex: 0 0 auto` let the label size to content and overflow by **75px at
        768** (a 379px box inside a 304px parent, text painting to x=819 on a
        768px viewport). The words that disappeared were the condition under
        which this page is allowed to show an unconfirmed cache.
        """
        for width in WIDTHS:
            with self.subTest(width=width):
                self._open_install()
                self._select("registry")
                self._set_width(width)
                measured = self._page.evaluate(
                    """() => {
                      const l = document.querySelector('.install-stale-toggle');
                      const r = l.getBoundingClientRect();
                      const rng = document.createRange();
                      rng.selectNodeContents(l);
                      const rects = Array.from(rng.getClientRects()).filter(x => x.width > 0);
                      return {boxRight: Math.round(r.right),
                              textRight: Math.round(Math.max(...rects.map(x => x.right))),
                              viewport: window.innerWidth};
                    }"""
                )
                self.assertLessEqual(measured["textRight"], measured["viewport"],
                                     f"the label paints past the viewport: {measured}")
                self.assertIn("reached", self._page.eval_on_selector(
                    ".install-stale-toggle", "el => el.textContent"))

    def test_a_stale_response_names_what_was_not_confirmed(self):
        self._select("registry")
        self._page.evaluate(
            """() => { window.__skillsManagerApp.install.lastResult = {
                data: [{name: 'entry', source: 'acme/one', installs: 1}],
                _registry: {cache_state: 'stale', stale: true},
            }; }"""
        )
        self._page.wait_for_selector(".install-cache-banner", timeout=5000)
        text = self._page.eval_on_selector(".install-cache-banner", "el => el.textContent")
        self.assertIn("could not be reached", text)
        self.assertIn("nothing here was confirmed", text)
        self.assertIn("Cached copy", self._page.eval_on_selector(".install-precondition", "el => el.textContent"))


if __name__ == "__main__":
    unittest.main()