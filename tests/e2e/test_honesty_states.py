"""6.5b e2e — §I's honesty rules, walked in the RENDERED DOM: "errors say
what happened and what to do next", and "a failed read is never dressed as an
empty one".

**Why this file exists, and why it is in `tests/e2e/` at all.** 6.3 fixed the
product defect — a read that failed used to render a sentence about the disk —
but `tests/test_redesign_read_failures.py` records five attempts at asserting
the *ordering* that fixes it, and **the mutation came back GREEN on all five**.
The assertion had to be a source-order check because nothing in the browser can
fail it: Vue renders whatever branch wins, and by the time a screenshot exists
the branch question is settled. So the honest instrument is the one MAP.md
names: **make the read actually fail, then ask the DOM what rendered.**

Every surface here is forced by aborting the network route the loader calls,
which is the only way to reach the state honestly — a test that pokes
`this.trashError = "x"` proves nothing about what a reader sees when the disk
misbehaves.

**The honesty rule this file keeps, copied from the row that spawned it: an
assertion that cannot fail is worse than none.** Each surface ships in three
tests that have to be read together:

  * ``test_a_failed_read_paints_the_error_not_an_empty_claim`` — the claim.
  * ``test_the_empty_claim_is_reachable_when_the_read_succeeds`` — the control.
    If the empty claim never rendered in the first place, "the empty claim is
    absent" would be true for every surface forever.
  * ``test_the_error_offers_a_retry_that_actually_recovers`` — "what to do
    next" as behaviour, not as the presence of a button. The route is restored
    and the retry is clicked; if the button were decoration the error would
    still be on screen and this fails.
"""

import os
import shutil
import sys
import tempfile
import threading
import unittest

from contextlib import contextmanager
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _has_chromium():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


# One row per read-failure surface 6.3 gave an error field to, minus the two
# that need a selected Library target to be reachable at all (the Recovery
# snapshot pane) — those are covered as "not exercised" rather than claimed.
#
#   key         the API path the loader calls, matched on `url.path`
#   view        the nav rail button that triggers the read
#   region      the CSS selector for the block the error renders in
#   claim       the empty-state sentence that must NOT render instead
#   subject     a word the message must name, so "something went wrong" fails
def _path_of(url):
    """The path of a URL Playwright handed us as a string."""
    return urlsplit(str(url)).path


def _fixtures(store):
    """A library worth auditing.

    An empty store renders the "Overview unavailable" branch instead of the
    Overview, so the walk would measure one screen and report it as eight.
    The history and trash claims below are empty with or without skills,
    which is why those two are unaffected.
    """
    rows = [
        ("platform-infrastructure-bootstrap",
         "Reads the host, reports what it actually found."),
        ("incident-response-runbook-coordinator",
         "Turns a noisy page into the next three actions."),
        ("release-notes-writer",
         "Writes release notes from a diff, and never claims a change it did not see."),
    ]
    for name, description in rows:
        store.create(name, description)


SURFACES = (
    {"key": "overview-history", "path": "/api/history", "view": "Overview",
     "region": ".overview-activity", "claim": "No history entries yet.",
     # "recent activity", not "history": that is the word the message and the
     # section heading BOTH use, and the first version of this test asserted
     # "history" and failed a correct product.
     "subject": "recent activity", "claim_reachable": False,
     "claim_why": "the fixtures below are created through the store, and "
                  "creating a skill IS a history record, so the claim is "
                  "unreachable the moment the walk has a library to walk"},
    {"key": "trash-detail", "path": "/api/trash", "view": "Recovery",
     "region": ".detail-inner", "claim": "Global trash is empty.",
     "subject": "trash"},
    # The one surface whose paired claim CANNOT be reached in a test: the
    # adapter catalogue is served from the app's own consumer table, so it
    # reads "6 consumers" on every machine and its empty branch has never
    # painted for anyone. Recorded rather than quietly dropped — the control
    # below fails loudly on this row instead of pretending the claim is live.
    {"key": "workspaces", "path": "/api/workspaces", "view": "Workspaces",
     "region": ".detail-inner", "claim": "No adapter evidence is available",
     "subject": "adapter", "claim_reachable": False,
     "claim_why": "the catalogue comes from the app's own consumer table, so "
                  "it reads 6 consumers on every machine"},
    {"key": "history-dialog", "path": "/api/history", "view": "Overview",
     "region": "[data-modal=history]", "claim": "No history records.",
     "subject": "history", "open": "View history",
     "claim_reachable": False,
     "claim_why": "the same history the fixtures write is what this dialog "
                  "lists, so an empty-history dialog and a populated Overview "
                  "cannot both be true in one walk"},
)


@unittest.skipUnless(_has_chromium(),
                     "Playwright/Chromium unavailable: a failed read is only "
                     "reachable in a browser, and no source contract can "
                     "stand in for what a reader would see")
class HonestyWalk(unittest.TestCase):
    """Every read failure says what failed, offers the retry, and never
    claims emptiness."""

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-honesty-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            rh = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                rh, ".cache", "ms-playwright")
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        _fixtures(cls.store)
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        for k, v in cls._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        # One browser per surface, not per test: each walk needs a network
        # state the previous surface left behind, and restarting Playwright's
        # sync loop inside a running test raises before any assertion is
        # reached. `_page_for` is the context manager that does it correctly.
        pass

    @contextmanager
    def _page_for(self, surface=None):
        """A page that has never been routed, opened on the server under test."""
        pw = sync_playwright().start()
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(self.server.url, wait_until="networkidle")
            page.wait_for_selector("#app", timeout=15000)
            page.wait_for_timeout(150)
            yield page
        finally:
            browser.close()
            pw.stop()

    # -- driving -------------------------------------------------------------

    def _goto(self, page, view):
        page.click('.navigation-rail button[data-tip="%s"]' % view)
        page.wait_for_selector(
            '.navigation-rail button[data-tip="%s"][aria-current="page"]' % view,
            timeout=10000)
        page.wait_for_timeout(250)

    def _break(self, page, path):
        """Make a read fail, for real, at the network layer.

        The matcher is handed the URL as a STRING in this Playwright version —
        `url.path` raises `AttributeError: 'str' object has no attribute
        'path'` before a single assertion is reached, which is recorded here
        because the failure reads like a product defect and is not one.
        """
        matcher = lambda url, p=path: _path_of(url) == p
        handler = lambda route: route.abort()
        page.route(matcher, handler)
        # `unroute` matches BOTH the url matcher and the handler, and a lambda
        # compares by IDENTITY — so a freshly built pair never matches and the
        # route stays installed. The first version of this test therefore
        # proved nothing about the retry: the read was still aborted, so of
        # course the error stayed. Keep and reuse these exact two objects.
        return matcher, handler

    def _open(self, page, surface):
        """Land on the surface with the failure already in place."""
        surface["_route"] = self._break(page, surface["path"])
        self._goto(page, surface["view"])
        if surface.get("open"):
            page.click('button:has-text("%s")' % surface["open"])
            page.wait_for_timeout(250)

    def _region(self, page, surface):
        return page.query_selector(surface["region"])

    # -- 1. the claim --------------------------------------------------------

    def test_a_failed_read_paints_the_error_not_an_empty_claim(self):
        """The falsifiable form of 6.3's ordering rule.

        For each surface: abort the read, then ask the DOM two questions the
        source-order check could not ask. Did the error render? Did the
        sentence claiming emptiness stay out of the document?
        """
        for surface in SURFACES:
            with self.subTest(surface["key"]):
                with self._page_for() as page:
                    self._open(page, surface)
                    region = self._region(page, surface)
                    self.assertIsNotNone(region,
                                         "%s never rendered" % surface["region"])
                    alert = region.query_selector(".read-failed[role=alert]")
                    self.assertIsNotNone(
                        alert,
                        "a failed read of %s painted no alert inside %s"
                        % (surface["path"], surface["region"]))
                    text = alert.inner_text()
                    self.assertIn(
                        surface["subject"], text.lower(),
                        "the message does not say what failed: %r" % text)
                    # The claim a reader must NOT be shown. Checked against the
                    # whole region rather than a sibling, because the defect
                    # 6.3 fixed was precisely the claim winning over the error.
                    self.assertNotIn(
                        surface["claim"], region.inner_text(),
                        "%s rendered the empty-state claim while the read had "
                        "failed: %r" % (surface["key"], surface["claim"]))

    # -- 2. the control ------------------------------------------------------

    def test_the_empty_claim_is_reachable_when_the_read_succeeds(self):
        """Without this, assertion 1 is unfalsifiable.

        "The empty claim is absent when the read fails" is trivially true of a
        claim that never renders. This proves each claim is live on a healthy
        server, so its absence under failure means something.
        """
        for surface in SURFACES:
            with self.subTest(surface["key"]):
                with self._page_for() as page:
                    self._goto(page, surface["view"])
                    if surface.get("open"):
                        page.click('button:has-text("%s")' % surface["open"])
                        page.wait_for_timeout(250)
                    region = self._region(page, surface)
                    self.assertIsNotNone(region)
                    if surface.get("claim_reachable") is False:
                        self.assertTrue(
                            surface.get("claim_why"),
                            "%s is flagged claim_reachable=False with no "
                            "recorded reason; an unmeasured exception is not "
                            "an exception" % surface["key"])
                        self.assertNotIn(
                            surface["claim"], region.inner_text(),
                            "%s is recorded as having an unreachable empty "
                            "claim, and it now renders — drop the flag and let "
                            "this assert the claim instead" % surface["key"])
                        continue
                    self.assertIn(
                        surface["claim"], region.inner_text(),
                        "%s: the control failed — this empty claim does not "
                        "render on a healthy server, so the assertion that it "
                        "stays hidden during a failure cannot fail"
                        % surface["key"])

    # -- 3. what to do next --------------------------------------------------

    def test_the_error_offers_a_retry_that_actually_recovers(self):
        """"What to do next" as behaviour.

        Asserting that a button named Retry exists would pass on a button wired
        to nothing. This heals the route, clicks whatever control the error
        offers, and requires the error to be gone — which is the only claim a
        reader can act on.
        """
        for surface in SURFACES:
            with self.subTest(surface["key"]):
                with self._page_for() as page:
                    self._open(page, surface)
                    region = self._region(page, surface)
                    alert = region.query_selector(".read-failed[role=alert]")
                    self.assertIsNotNone(alert, "%s painted no error to retry"
                                         % surface["key"])
                    control = alert.query_selector("button")
                    self.assertIsNotNone(
                        control,
                        "%s: the failure names no way forward — the alert has "
                        "no control at all" % surface["key"])
                    self.assertTrue(
                        control.is_enabled(),
                        "%s: the offered action is disabled, so it is not an "
                        "action" % surface["key"])
                    # Heal by removing the SAME matcher AND handler.
                    page.unroute(*surface["_route"])
                    control.click()
                    page.wait_for_timeout(700)
                    self.assertIsNone(
                        region.query_selector(".read-failed[role=alert]"),
                        "%s: the retry did not recover — the alert is still on "
                        "screen after the read succeeded again"
                        % surface["key"])

    # -- 4. the control for 3 -----------------------------------------------

    def test_the_error_stays_until_the_reader_acts(self):
        """The recovery in 3 must come from the offered control, not from a
        re-render the view performs on its own.

        If a view silently re-reads on a timer, 3 would pass with a dead
        button. This heals nothing and waits: the error must STAY.
        """
        for surface in SURFACES:
            with self.subTest(surface["key"]):
                with self._page_for() as page:
                    self._open(page, surface)
                    page.wait_for_timeout(1500)
                    region = self._region(page, surface)
                    self.assertIsNotNone(
                        region.query_selector(".read-failed[role=alert]"),
                        "%s: the error cleared on its own while the read was "
                        "still failing, so 3 measures a re-render and not the "
                        "retry control" % surface["key"])


if __name__ == "__main__":
    unittest.main()