"""4.8b — `pending` was reachable only in theory, and the one state nobody read was the failure.

4.8 slice A asserted this dialog's EXIT by EXECUTION over six modal states and
recorded the honest gap: *reaching `pending` needs a real multipart folder
upload, which no test in this suite performs.* This file performs one.

Three measurements shaped everything here, and each is asserted rather than
assumed:

1. **`set_input_files` DOES survive `webkitdirectory`.** Playwright hands
   Chromium a directory path and the input reports `webkitRelativePath` of
   `candidate/SKILL.md`, so the whole upload -> review -> confirm -> apply path
   is driven the way a reader drives it. The row said to check this first and
   to move the slice to an API-level fixture if it did not work; it works, so
   the fixture stayed at the level a reader can reach.

2. **The candidate's frontmatter decides the state.** A first candidate with a
   different `name:` returned `review_state: "blocked"` with one validation
   error ("frontmatter name does not match the target skill name"), not
   `pending`. So the fixture writes the target's OWN name — and asserts it got
   `pending`, so a fixture that quietly degrades to `blocked` cannot report a
   pass for a flow it never entered.

3. **The band is asked about with `elementFromPoint`, not
   `getBoundingClientRect`.** Clipping is a paint operation and layout boxes do
   not report it; a band scrolled out of the `.modal-body` still has a perfect
   rect. My first probe read `hitIsBand: false` and I nearly believed it —
   then found I had set `scrollTop = 0` in the measuring expression itself,
   undoing the very scroll the assertion was about. The helper here NEVER
   touches scrollTop; it reads what `requestCloseUpdate` produced.

`committed_with_warning` is the defect this file found. `_reconcile_after_commit`
answers that when the bytes were replaced but index reconciliation or snapshot
pruning failed, and the banner read "Update applied successfully." for it.

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
import shutil
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


# The one record shape `updateTargetAvailable` accepts (app.js:713): an exact,
# addressable, writable instance with a physical root and a concrete path.
_WRITABLE_SELECTOR = """
(n) => {
  const a = window.__skillsManagerApp;
  const rec = (a.skills || []).find(s => !s.disabled
      && s.name && s.name === n
      && s.scope && s.scope !== 'all'
      && s.addressable !== false
      && s.root_availability === 'writable'
      && (s.physical_path || s.path) && s.physical_root);
  if (!rec) return null;
  a.selectSkill(rec);
  return rec.scope;
}
"""


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: this drives a real multipart folder "
    "upload through the update review, and is NOT verified by this skip",
)
class UpdateReviewLiveTests(unittest.TestCase):
    _seq = 0

    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-updatereview-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                real_home, ".cache", "ms-playwright")
        # RULES #8: agent SCOPES come from HOME, not the data dir. Without this
        # the fixture server walks the real ~/.codex.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        cls.store.create(
            "rollback-fixture",
            "A fixture that exists to be updated and then rolled back.",
            body=("# rollback-fixture\n\nThe original body.\n"),
        )
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

        cls.candidate = os.path.join(cls._tmp, "candidate")
        os.makedirs(cls.candidate, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        for key, value in cls._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_function("() => document.getElementById('app').children.length > 0",
                                     timeout=15000)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    # ------------------------------------------------------------- helpers

    def _reload(self):
        """One browser, a fresh page per case — a nested `sync_playwright()`
        inside a test raises (STATE records this for the scope-switcher)."""
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_function(
            "() => document.getElementById('app').children.length > 0", timeout=15000)

    def _write_candidate(self, name="rollback-fixture", body=None):
        """A candidate whose frontmatter names the TARGET.

        This is the whole difference between `pending` and `blocked`: a
        mismatched `name:` is a validation error and the backend refuses to
        stage. See the module docstring.

        The body carries a fresh nonce per call because the apply tests COMMIT
        their candidate: a second test uploading identical bytes would come back
        `no-change`, which is a third review_state neither path is testing.
        """
        UpdateReviewLiveTests._seq += 1
        path = os.path.join(self.candidate, "SKILL.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body or ("---\nname: %s\ndescription: A revised body "
                              "staged for review by the live-app test.\n---\n\n"
                              "# %s\n\nA revised body, revision %d.\n"
                              % (name, name, UpdateReviewLiveTests._seq)))
        return path

    def _open_update(self, name="rollback-fixture"):
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        picked = self._page.evaluate(_WRITABLE_SELECTOR, name)
        self.assertTrue(picked, f"no writable instance named {name} in the fixture")
        self._page.wait_for_timeout(300)
        self._page.evaluate("() => window.__skillsManagerApp.openUpdate()")
        self._page.wait_for_selector('[data-modal="update"] #update-folder-input', timeout=10000)

    def _upload(self):
        """The reader's path, end to end: a directory, a real POST, a real
        staged review. Returns once the dialog has settled.

        `onUpdateFiles` only prepares a review when the input reports at least
        one file, so an empty candidate directory leaves `review` null forever
        and every wait here would time out rather than fail.
        """
        self._write_candidate()
        self._page.set_input_files('#update-folder-input', self.candidate)
        self._page.wait_for_function(
            "() => { const m = window.__skillsManagerApp.modals.update;"
            " return !!(m && m.review && !m.loading); }", timeout=20000)
        self._page.wait_for_timeout(200)

    def _upload_the_installed_bytes(self, name="rollback-fixture"):
        """9.1d: reach `no-change` by copying what is already installed.

        The bytes are read off disk rather than reconstructed from what
        `store.create` was called with, because an earlier test in this class
        COMMITS its candidate and the installed document is no longer the
        original. Reconstructing it would compare a stale fixture against a
        changed one and report `pending`, which is a pass for a state nobody
        reached.
        """
        installed = None
        for root, _dirs, files in os.walk(self._tmp):
            if os.path.basename(root) == name and "SKILL.md" in files:
                installed = os.path.join(root, "SKILL.md")
                break
        self.assertIsNotNone(
            installed, f"the fixture's own {name}/SKILL.md was not found on disk")
        shutil.copyfile(installed, os.path.join(self.candidate, "SKILL.md"))
        self._page.set_input_files('#update-folder-input', self.candidate)
        self._page.wait_for_function(
            "() => { const m = window.__skillsManagerApp.modals.update;"
            " return !!(m && m.review && !m.loading); }", timeout=20000)
        self._page.wait_for_timeout(200)

    def _review_state(self):
        return self._page.evaluate(
            "() => (window.__skillsManagerApp.modals.update.review || {}).review_state")

    def _modal_open(self):
        return bool(self._page.query_selector('[data-modal="update"]'))

    def _select_target(self, name="rollback-fixture"):
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        picked = self._page.evaluate(_WRITABLE_SELECTOR, name)
        self.assertTrue(picked, f"no writable instance named {name} in the fixture")
        self._page.wait_for_timeout(300)
        return picked

    def _first_snapshot(self):
        """Ask the app for the snapshots rather than reading a property that
        may not have been loaded yet — `recoverySnapshots` starts `[]` and is
        only filled by `loadRecoverySnapshots()`, which the detail tab triggers.
        A rollback review is by definition a review of a snapshot, so a missing
        one is a fixture that has not applied anything yet."""
        self._page.evaluate("() => window.__skillsManagerApp.loadRecoverySnapshots()")
        try:
            self._page.wait_for_function(
                "() => { const a = window.__skillsManagerApp;"
                " return !!(a.recoverySnapshots && a.recoverySnapshots.length)"
                " && !a.loadingRecoverySnapshots; }", timeout=15000)
        except Exception:
            return None
        return self._page.evaluate(
            "() => (window.__skillsManagerApp.recoverySnapshots || [])[0] || null")

    def _band_reachable(self):
        """Can the reader actually SEE the question? `elementFromPoint` over the
        band's own centre, and the scroll position is NOT touched here — this
        measures what `requestCloseUpdate` did. (Reading `getBoundingClientRect`
        alone is 4.5a's mistake: a band scrolled out of the body still has one.)"""
        return self._page.evaluate("""() => {
          const band = document.querySelector('[data-modal="update"] .update-close-confirm');
          if (!band) return {present: false};
          const r = band.getBoundingClientRect();
          if (!r.width || !r.height) return {present: true, reachable: false, why: 'zero box'};
          const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
          const body = document.querySelector('[data-modal="update"] .modal-body');
          return {
            present: true,
            reachable: !!(hit && band.contains(hit)),
            top: r.top | 0,
            scrollTop: body ? body.scrollTop : null,
            scrollHeight: body ? body.scrollHeight : null,
            viewport: window.innerHeight,
            hit: hit ? (hit.className || hit.tagName) : null,
          };
        }""")

    # --------------------------------------------------------------- tests

    def test_a_folder_upload_reaches_pending_and_offers_the_apply(self):
        """The state 4.8 slice A could not reach, reached by the reader's own
        path. It asserts `pending` EXPLICITLY: a fixture that degraded to
        `blocked` would still render the dialog, and without this the rest of
        the file would be testing a flow it never entered."""
        self._open_update()
        self._upload()
        self.assertEqual(
            self._review_state(), "pending",
            "a candidate naming the target did not reach `pending`; every other "
            "assertion in this file runs against that state, so a `blocked` "
            "review here would make the rest vacuous",
        )
        self.assertTrue(
            bool(self._page.query_selector('[data-modal="update"] #update-confirmation')),
            "a pending review must still demand the explicit confirmation")
        apply_btn = self._page.query_selector(
            '[data-modal="update"] .modal-foot .btn-primary')
        self.assertIsNotNone(apply_btn, "no Apply button on a pending review")
        self.assertTrue(
            apply_btn.is_disabled(),
            "Apply was enabled before the reader ticked the confirmation")

    def test_a_no_change_review_is_stated_in_a_neutral_level_not_a_success(self):
        """9.1d. `no-change` was painted `banner-ok` — a green success for a
        no-op, in the one dialog where a reader is deciding whether to abandon
        a review. Nothing succeeded and nothing failed.

        The colours are read from a probe element rather than from a hex table:
        a resolved token value survives a palette retune, and this assertion is
        about WHICH level paints, not about a number that would need rewriting.
        The `ok` values are read in the same evaluate as the control — asserting
        only that info is present would pass if the rule were the base class.
        """
        self._open_update()
        self._upload_the_installed_bytes()
        self.assertEqual(
            self._review_state(), "no-change",
            "a byte-identical candidate did not produce `no-change`; the banner "
            "under test would not be the one this test names")

        painted = self._page.evaluate("""() => {
          const modal = document.querySelector('[data-modal="update"]');
          const banner = modal && modal.querySelector('.banner-info');
          const probe = (declaration) => {
            const el = document.createElement('span');
            el.style.color = declaration;
            document.body.appendChild(el);
            const out = getComputedStyle(el).color;
            el.remove();
            return out;
          };
          const glyph = banner && banner.querySelector('.banner-icon-info');
          const cs = banner ? getComputedStyle(banner) : null;
          return {
            info: !!banner,
            ok: !!(modal && modal.querySelector('.banner-ok')),
            level: banner ? (banner.className || '') : '',
            border: cs ? cs.borderTopColor : null,
            background: cs ? cs.backgroundColor : null,
            accentText: probe('var(--accent-text)'),
            accentBg: probe('var(--accent-bg)'),
            okText: probe('var(--ok)'),
            okBg: probe('var(--ok-bg)'),
            glyph: !!glyph,
            glyphHidden: glyph ? glyph.getAttribute('aria-hidden') : null,
            text: banner ? banner.textContent.trim() : '',
          };
        }""")
        self.assertTrue(painted["info"], "no .banner-info rendered for `no-change`")
        self.assertFalse(
            painted["ok"],
            "the no-change review still paints `banner-ok` — a success for a "
            "state in which nothing succeeded")
        self.assertEqual(painted["border"], painted["accentText"])
        self.assertEqual(painted["background"], painted["accentBg"])
        self.assertNotEqual(
            painted["background"], painted["okBg"],
            "the info tint is the ok tint — the level was renamed, not changed")
        self.assertNotEqual(painted["border"], painted["okText"])
        self.assertTrue(painted["glyph"], "an informational banner is colour-only")
        self.assertEqual(painted["glyphHidden"], "true")
        self.assertIn("No changes detected", painted["text"])

    def test_the_apply_button_answers_only_the_explicit_confirmation(self):
        self._open_update()
        self._upload()
        self.assertEqual(self._review_state(), "pending")
        self._page.check('[data-modal="update"] #update-confirmation')
        self._page.wait_for_timeout(200)
        apply_btn = self._page.query_selector(
            '[data-modal="update"] .modal-foot .btn-primary')
        self.assertFalse(apply_btn.is_disabled(),
                         "ticking the confirmation did not enable Apply")

    def test_the_abandon_band_is_a_question_the_reader_can_actually_see(self):
        """4.8 slice A added `scrollIntoView` to fix this and asserted only
        that the ORDER was right. The order being right is not the band being
        reachable, and a rect exists for a band clipped out of the viewport."""
        self._open_update()
        self._upload()
        self.assertEqual(self._review_state(), "pending")
        # A reader at the TOP of the evidence, which is where Escape, the
        # scrim and the always-visible foot button find them.
        self._page.evaluate("""() => { const b =
            document.querySelector('[data-modal="update"] .modal-body');
          if (b) b.scrollTop = 0; }""")
        self._page.wait_for_timeout(150)
        self._page.keyboard.press("Escape")
        self._page.wait_for_timeout(400)
        band = self._band_reachable()
        self.assertTrue(band["present"], "Escape did not ask anything")
        self.assertTrue(
            band["reachable"],
            f"the question rendered where the reader cannot reach it: {band}",
        )
        self.assertTrue(self._modal_open(),
                        "the dialog closed instead of asking")

    def test_a_second_escape_clears_the_question_rather_than_re_asking(self):
        """The DECISION 4.8b makes, and the editor's rule rather than this
        dialog's.

        The update dialog re-raised on every Escape while `skillEscape` cleared
        it. Clearing loses nothing here: the reader stays in the dialog with the
        review exactly as pending as it was, so "step back one level" is the
        same meaning in both dialogs. A second Escape that DESTROYED the review
        would be the defect; one that re-asks is merely tedious.
        """
        self._open_update()
        self._upload()
        self._page.keyboard.press("Escape")
        self._page.wait_for_timeout(250)
        self.assertTrue(self._band_reachable()["present"], "first Escape did not ask")
        self._page.keyboard.press("Escape")
        self._page.wait_for_timeout(250)
        after = self._page.evaluate(
            "() => { const m = window.__skillsManagerApp.modals.update;"
            " return {open: !!m, confirming: !!(m && m.confirmingClose),"
            " state: m && m.review && m.review.review_state}; }")
        self.assertTrue(after["open"], "a second Escape closed the dialog outright")
        self.assertFalse(after["confirming"],
                         "a second Escape re-asked instead of stepping back")
        self.assertEqual(after["state"], "pending",
                         "stepping back destroyed the pending review")

    def test_a_clean_commit_reports_success_and_a_real_snapshot(self):
        """The happy path, end to end, through the reader's own clicks."""
        self._open_update()
        self._upload()
        self.assertEqual(self._review_state(), "pending")
        self._page.check('[data-modal="update"] #update-confirmation')
        self._page.wait_for_timeout(200)
        self._page.click('[data-modal="update"] .modal-foot .btn-primary')
        self._page.wait_for_selector('[data-modal="update"] .update-success', timeout=25000)
        self._page.wait_for_timeout(300)
        banner = self._page.text_content('[data-modal="update"] .update-success')
        self.assertIn("Update applied successfully.", banner)
        self.assertNotIn("Outstanding:", banner,
                         "a clean commit reported an outstanding step")
        state = self._page.evaluate(
            "() => { const a = window.__skillsManagerApp;"
            " return a.updateApplyOutcome; }")
        self.assertTrue(state["ok"], f"a clean commit was read as {state}")

    def test_a_commit_that_reports_an_outstanding_step_does_not_say_successfully(self):
        """THE DEFECT. `_reconcile_after_commit` answers
        `committed_with_warning` when the bytes were replaced but index
        reconciliation or snapshot pruning failed; the banner read "Update
        applied successfully." for that payload and the toast said the same, so
        a reader was told a clean success while the counts above the dialog
        were stale (RULES #12).

        The response is routed rather than provoked because provoking it means
        making `resync()` or `_prune_snapshots()` fail inside a real commit —
        a far more fragile thing to arrange than the payload the endpoint
        documents. The SHAPE is the endpoint's own; the rendering is what is
        under test.
        """
        body = ('{"committed": true, "review_id": "r-1", "snapshot_id": "snap-1",'
                ' "content_hash": "abc", "source_lock": {"state": "recorded"},'
                ' "rollback_available": true,'
                ' "result": "committed_with_warning", "code": "committed-with-warning",'
                ' "warning": "filesystem update committed; global index '
                'reconciliation is pending",'
                ' "target": {"physical_path": "/tmp/whatever"}}')
        self._page.route("**/api/source-updates/reviews/*/commit",
                         lambda route: route.fulfill(
                             status=200, content_type="application/json", body=body))
        self._open_update()
        self._upload()
        self.assertEqual(self._review_state(), "pending")
        self._page.check('[data-modal="update"] #update-confirmation')
        self._page.wait_for_timeout(200)
        self._page.click('[data-modal="update"] .modal-foot .btn-primary')
        self._page.wait_for_selector('[data-modal="update"] .update-success', timeout=25000)
        self._page.wait_for_timeout(300)
        banner = self._page.text_content('[data-modal="update"] .update-success')
        self.assertIn("global index reconciliation is pending", banner,
                      "the warning the backend sent was dropped by the banner")
        self.assertNotIn("Update applied successfully.", banner,
                         "a commit with an outstanding step was reported as a "
                         "clean success")
        classes = self._page.get_attribute(
            '[data-modal="update"] .update-success', "class") or ""
        self.assertIn("banner-warn", classes,
                      "an incomplete commit still paints as the all-clear")

    def test_the_toast_agrees_with_the_banner(self):
        """The same failure in the place a reader sees for eight seconds. Two
        sources stating two verdicts is 4.7's lesson: the literal `N` in the
        sync dialog cost a whole task."""
        body = ('{"committed": true, "review_id": "r-1", "snapshot_id": "snap-1",'
                ' "content_hash": "abc", "source_lock": {"state": "recorded"},'
                ' "rollback_available": true, "result": "committed_with_warning",'
                ' "warning": "filesystem update committed; snapshot retention '
                'could not be completed"}')
        self._page.route("**/api/source-updates/reviews/*/commit",
                         lambda route: route.fulfill(
                             status=200, content_type="application/json", body=body))
        self._open_update()
        self._upload()
        self._page.check('[data-modal="update"] #update-confirmation')
        self._page.wait_for_timeout(200)
        self._page.click('[data-modal="update"] .modal-foot .btn-primary')
        self._page.wait_for_selector(".toast", timeout=25000)
        self._page.wait_for_timeout(250)
        toasts = self._page.evaluate(
            "() => (window.__skillsManagerApp.toasts || []).map(t => t.text)")
        joined = " ".join(toasts)
        self.assertIn("outstanding step", joined,
                      f"the toast did not carry the verdict: {toasts}")
        # The CLEAN toast ends "; recovery snapshot <id>." Asserting on the
        # shared "Update applied to" prefix instead would have been an
        # assertion that could not fail — both forms begin with it.
        self.assertNotIn("; recovery snapshot", joined,
                         f"the toast still reads as a clean success: {toasts}")

    def test_an_outstanding_step_with_no_named_cause_says_so_rather_than_guessing(self):
        """The payload can say `committed_with_warning` with no `warning`
        string. Inventing a cause would break RULES #12 harder than the
        original defect, so the copy states the absence."""
        body = ('{"committed": true, "review_id": "r-1", "snapshot_id": "snap-1",'
                ' "result": "committed_with_warning"}')
        self._page.route("**/api/source-updates/reviews/*/commit",
                         lambda route: route.fulfill(
                             status=200, content_type="application/json", body=body))
        self._open_update()
        self._upload()
        self._page.check('[data-modal="update"] #update-confirmation')
        self._page.wait_for_timeout(200)
        self._page.click('[data-modal="update"] .modal-foot .btn-primary')
        self._page.wait_for_selector('[data-modal="update"] .update-success', timeout=25000)
        self._page.wait_for_timeout(300)
        banner = self._page.text_content('[data-modal="update"] .update-success')
        self.assertNotIn("Update applied successfully.", banner)
        self.assertIn("named no outstanding step", banner,
                      "with no warning string the UI must say so, not invent one")

    def test_the_rollback_branch_opens_in_snapshot_mode(self):
        """`mode: snapshot` has no coverage of its own. Three things make it
        different from the local path — the mode, the source section, and the
        absence of the folder input — and each is asserted, because a test that
        only opened the dialog would pass against the local path too."""
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        self._page.evaluate(_WRITABLE_SELECTOR, "rollback-fixture")
        self._page.wait_for_timeout(400)
        snapshot = self._first_snapshot()
        if not snapshot:
            self.skipTest(
                "the fixture has no recovery snapshot yet; run the apply test "
                "first — a rollback review is by definition a review of a "
                "snapshot, and this test does not claim it passed")
        self._page.evaluate("(s) => window.__skillsManagerApp.openRollbackReview(s)",
                            snapshot)
        self._page.wait_for_selector('[data-modal="update"]', timeout=10000)
        self._page.wait_for_function(
            "() => { const m = window.__skillsManagerApp.modals.update;"
            " return !!(m && m.review && !m.loading); }", timeout=25000)
        self._page.wait_for_timeout(200)
        state = self._page.evaluate(
            "() => { const m = window.__skillsManagerApp.modals.update;"
            " return {mode: m.mode, state: m.review && m.review.review_state,"
            " kind: (m.review.source || {}).kind,"
            " sourceValue: (m.review.source || {}).value,"
            " rollbackFrom: m.review.rollback_from_snapshot,"
            " hasFolderInput: !!document.querySelector"
            "('[data-modal=\"update\"] #update-folder-input'),"
            " title: document.querySelector('[data-modal=\"update\"] .modal-head h2')"
            " ?.textContent || ''}; }")
        self.assertEqual(state["mode"], "snapshot")
        # Measured, and my first assertion here was wrong: the backend records
        # `source_identity("local", f"snapshot:{id}")` for EVERY snapshot-derived
        # review (source_update.py:649), so `kind` is "local" here and cannot
        # distinguish the two paths. `rollback_from_snapshot` is the fact the
        # backend actually promises, and it is what the assertion states.
        self.assertEqual(state["rollbackFrom"], snapshot.get("snapshot_id"),
                         "the rollback review did not carry the snapshot back")
        self.assertEqual(state["sourceValue"], f"snapshot:{snapshot.get('snapshot_id')}")
        self.assertFalse(state["hasFolderInput"],
                         "a rollback review still offers the local folder picker")
        self.assertIn("Review rollback", state["title"])

    def test_preparing_a_snapshot_review_drops_a_stale_confirmation(self):
        """`prepareSnapshotReview` cleared neither `review` nor `confirmed`,
        while the local path cleared both.

        Measured, not assumed: `openRollbackReview` builds a FRESH modal with
        `confirmed: false` and prepares once, so the carried-over `true` is
        unreachable through the UI today — which is why the row asks for the
        reset to be CONFIRMED unreachable rather than assumed either way. The
        test drives the method twice, because that is the invariant the method
        owes every future caller, and an assertion that only holds on the path
        a reader cannot take describes the first call rather than the rule.
        """
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        self._page.evaluate(_WRITABLE_SELECTOR, "rollback-fixture")
        self._page.wait_for_timeout(400)
        snapshot = self._first_snapshot()
        if not snapshot:
            self.skipTest(
                "the fixture has no recovery snapshot yet; run the apply test "
                "first — this test drives a snapshot review, not an assertion "
                "about a missing one")
        self._page.evaluate("(s) => window.__skillsManagerApp.openRollbackReview(s)",
                            snapshot)
        self._page.wait_for_function(
            "() => { const m = window.__skillsManagerApp.modals.update;"
            " return !!(m && m.review && !m.loading); }", timeout=25000)
        # The reader ticks the box, then the SAME modal is prepared again.
        self._page.evaluate(
            "() => { window.__skillsManagerApp.modals.update.confirmed = true; }")
        self._page.evaluate(
            "(s) => window.__skillsManagerApp.prepareSnapshotReview(s)", snapshot)
        self._page.wait_for_function(
            "() => { const m = window.__skillsManagerApp.modals.update;"
            " return !!(m && m.review && !m.loading); }", timeout=25000)
        after = self._page.evaluate(
            "() => { const m = window.__skillsManagerApp.modals.update;"
            " return {confirmed: m.confirmed, state: m.review && m.review.review_state,"
            " canApply: window.__skillsManagerApp.updateReviewCanApply(m)}; }")
        self.assertFalse(after["confirmed"],
                         "a stale confirmation survived a re-prepared review, so "
                         "the next candidate would be one click from applying")
        self.assertFalse(after["canApply"])


if __name__ == "__main__":
    unittest.main()