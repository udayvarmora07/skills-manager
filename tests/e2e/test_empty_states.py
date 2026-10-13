"""6.5c e2e — §I's "empty states: one sentence + one action", walked in the
RENDERED DOM against BOTH a populated store and a fresh empty one.

**6.5 counted "31 `.empty` blocks" from a regex over nested Vue markup. The
count is 4, and the regex was the reason.** `grep -c 'class="empty"'` answers
four and the `.compact-empty` variants add more, but neither number is the
question. The question is what a reader sees, so this walks the browser, in two
stores, and asks each block two things:

  1. **Is the text one claim?** A title plus at most one supporting sentence.
     An empty state that explains itself in four paragraphs is a paragraph
     wearing an empty state's border.
  2. **Is an action reachable?** Here is the decision this task exists to
     make, and the measurement overturned the obvious one: **the action does
     NOT have to live inside the block.** Eight blocks ship with no button of
     their own and six of them are in a sidepanel where the control belongs to
     the view — the Library's "No skills installed" sits 40px from the "New
     skill" button that resolves it. Adding a button to each of those would
     have been the wrong fix: eight duplicate controls, and a block that claims
     to be a dead end when the reader is one click from somewhere. **So the
     rule asserted here is view-level**, and a block fails only when its whole
     surrounding surface offers no verb-led control at all.

**Two stores, because "empty" means different things in each.** A fresh install
is the case empty states are written for; a populated store is the case where a
*filtered* result is empty. Asserting only one measures half the product and
calls it all of it.

**Every locator here was run against a tree before it was trusted** — this
branch's most repeated lesson. The first probe of this task reported three
Quality blocks with `paras=0`, which reads as "three blocks have no text at
all": all three were a descendant query missing a block that IS the `<p>`, and
the product was correct in every case.
"""

import os
import shutil
import sys
import tempfile
import threading
import unittest

from contextlib import contextmanager

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VIEWS = ("Overview", "Library", "Profiles", "Workspaces",
         "Install", "Recovery", "Quality", "Settings")

# §I asks for an ACTION. A verb-led label is the shape §B already settled and
# 6.5 measured across all 112 control labels; this list is deliberately the
# verbs the product actually uses, not a generic dictionary, because a word
# that appears in no control could never satisfy it.
VERBS = ("add", "browse", "check", "choose", "clear", "close", "copy", "create",
         "disable", "edit", "enable", "export", "import", "inspect", "open",
         "read", "reset", "restore", "review", "run", "search", "select",
         "show", "start", "try", "undo", "use", "view")

# The walk, in the page. `host` is the surface the block lives on — the
# sidepanel, the detail pane or the open dialog — and the action may be
# anywhere on it, which is the decision this file records.
MEASURE = """
(verbs) => {
  const isVerb = (t) => verbs.some(v => t.trim().toLowerCase().startsWith(v));
  const blocks = [];
  for (const el of document.querySelectorAll('.empty, .compact-empty')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    // A block is SOMETIMES the <p> itself. A descendant-only query reads it as
    // having no text, which is a defect in the check, not in the product.
    const paras = [...(el.matches('p') ? [el] : []),
                   ...el.querySelectorAll('p, .empty-title, .empty-note')]
      .map(p => p.innerText.trim()).filter(Boolean);
    // The surface is the view's own working area, and the chrome is NOT part
    // of it. Three widths were measured and all three were wrong:
    //   - the block alone: five views look stranded;
    //   - the block's pane (`aside.sidebar`): still stranded, because the
    //     control that resolves a sidepanel empty state lives in the SIBLING
    //     `section.detail`;
    //   - the whole `main`: every view "passes" on the topbar's "Show scope
    //     controls", which resolves nothing and makes the rule vacuous.
    // So: the view, minus the persistent rail/topbar/statusbar. Navigation is
    // not an action on an empty state; the control that creates the missing
    // thing is.
    const host = el.closest('.modal') || document.querySelector('main.layout')
      || document.body;
    const isChrome = (node) => node.closest(
      '.navigation-rail, .topbar, .statusbar, .brand, .scope-controls');
    const labels = (scope) => [...scope.querySelectorAll('button, a')]
      .filter(b => !isChrome(b))
      .map(b => (b.innerText || '').trim()).filter(Boolean);
    blocks.push({
      title: (el.querySelector('.empty-title, .empty-note') || el)
        .innerText.trim().slice(0, 60),
      paras: paras,
      inside: labels(el).filter(isVerb),
      host: labels(host).filter(isVerb),
    });
  }
  return blocks;
}
"""


def _fixtures(store):
    store.create("platform-infrastructure-bootstrap",
                 "Reads the host, reports what it actually found.")
    store.create("incident-response-runbook-coordinator",
                 "Turns a noisy page into the next three actions.")
    store.create("release-notes-writer",
                 "Writes release notes from a diff.")


def _chromium_available():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


class _Store:
    """An isolated server over a store that is either populated or fresh."""

    def __init__(self, populated):
        self._tmp = tempfile.mkdtemp(
            prefix="skillsmgr-e2e-empty-%s-" % ("full" if populated else "bare"))
        home = os.path.join(self._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(self._tmp, "data")
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        store = Store(self._tmp)
        store.init_db()
        if populated:
            _fixtures(store)
        self.store = store
        self.server = WebAppServer(store, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        shutil.rmtree(self._tmp, ignore_errors=True)


@unittest.skipUnless(_chromium_available(),
                     "Playwright/Chromium unavailable: an empty state is only "
                     "reachable in a browser, and no source contract can "
                     "stand in for what a reader would see")
class EmptyStateWalk(unittest.TestCase):
    """§I's two rules, over every empty state the product can actually show."""

    @classmethod
    def setUpClass(cls):
        cls._saved_env = {k: os.environ.get(k) for k in
                          ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                           "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            rh = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                rh, ".cache", "ms-playwright")
        cls.stores = {"populated": _Store(True), "fresh": _Store(False)}

    @classmethod
    def tearDownClass(cls):
        for store in cls.stores.values():
            store.close()
        for k, v in cls._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    @contextmanager
    def _page_on(self, which):
        pw = sync_playwright().start()
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(self.stores[which].server.url, wait_until="networkidle")
            page.wait_for_selector("#app", timeout=15000)
            page.wait_for_timeout(200)
            yield page
        finally:
            browser.close()
            pw.stop()

    def _measure(self, page):
        return page.evaluate(MEASURE, list(VERBS))

    def _walk(self, page, found):
        for view in VIEWS:
            page.click('.navigation-rail button[data-tip="%s"]' % view)
            page.wait_for_timeout(300)
            for block in self._measure(page):
                found.append((view, block))

    # -- 1. one sentence ------------------------------------------------------

    def test_an_empty_state_states_one_claim_and_nothing_more(self):
        """A title, plus at most one supporting sentence.

        Measured over both stores, so a block that is well-behaved only in a
        populated store is caught in the fresh one and vice versa.
        """
        for which in ("populated", "fresh"):
            with self.subTest(which):
                with self._page_on(which) as page:
                    found = []
                    self._walk(page, found)
                    self.assertTrue(found, "%s: no empty state rendered, so "
                                    "this measures nothing" % which)
                    for view, block in found:
                        self.assertLessEqual(
                            len(block["paras"]), 2,
                            "%s / %s: %r states %d paragraphs. An empty state "
                            "is one claim; a fourth paragraph is a section "
                            "wearing its border." % (
                                which, view, block["title"], len(block["paras"])))

    # -- 2. one action -------------------------------------------------------

    def test_every_empty_state_leaves_an_action_within_reach(self):
        """The rule this task decided, and it is view-level on purpose.

        Eight blocks ship with no button of their own and are not defects: the
        Library's "No skills installed" sits beside the "New skill" that
        resolves it, and a second button inside the block would be a duplicate
        control pretending to be a dead end. What must never happen is an empty
        state on a surface with NOTHING verb-led anywhere on it.
        """
        for which in ("populated", "fresh"):
            with self.subTest(which):
                with self._page_on(which) as page:
                    found = []
                    self._walk(page, found)
                    stranded = [(v, b) for v, b in found
                                if not b["inside"] and not b["host"]]
                    self.assertEqual(
                        stranded, [],
                        "empty states with no action anywhere on their surface: "
                        + "; ".join("%s: %r" % (v, b["title"])
                                    for v, b in stranded))

    # -- 3. the control ------------------------------------------------------

    def test_the_walk_reaches_empty_states_in_both_stores(self):
        """Without this, 1 and 2 pass on a page that renders nothing.

        Also the honest record of what the two stores are FOR: the fresh one
        is where the onboarding-shaped empty states live, the populated one
        where filtered results run dry. A change that empties one of them is
        visible here rather than in a screenshot nobody opens.
        """
        counts = {}
        for which in ("populated", "fresh"):
            with self.subTest(which):
                with self._page_on(which) as page:
                    found = []
                    self._walk(page, found)
                    counts[which] = len(found)
                    self.assertGreater(
                        len(found), 0,
                        "%s: the walk rendered no empty state at all" % which)
        self.assertGreater(
            counts["fresh"], counts["populated"] - 1,
            "a store with no skills must show at least as many empty states "
            "as one with three: measured %r" % counts)

    # -- 4. the dialogs, which no view walk reaches --------------------------

    def test_the_history_dialog_is_walked_too(self):
        """The history dialog is where 6.5 named a candidate, and a view-only
        walk never opens it.

        `"No history records."` IS reachable — in a fresh store there is no
        history — which is the whole point: a candidate that only exists in the
        source is not a finding, and one that only exists in a browser is.
        """
        with self._page_on("fresh") as page:
            page.click('.navigation-rail button[data-tip="Recovery"]')
            page.wait_for_timeout(400)
            page.click('button:has-text("Review history")')
            page.wait_for_selector('[data-modal=history]', timeout=8000)
            page.wait_for_timeout(400)
            blocks = self._measure(page)
            modal_blocks = [b for b in blocks if "history records" in b["title"].lower()]
            self.assertEqual(
                len(modal_blocks), 1,
                "the empty history dialog did not render exactly one claim "
                "block; measured %r" % [b["title"] for b in blocks])
            block = modal_blocks[0]
            self.assertLessEqual(len(block["paras"]), 2)
            self.assertTrue(
                block["inside"] or block["host"],
                "the history dialog's empty state leaves no verb-led control "
                "on the dialog itself")


if __name__ == "__main__":
    unittest.main()