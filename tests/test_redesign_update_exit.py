"""4.8 — the update review's exit told the reader it would do something else.

The dialog's foot button read **"Review later"**. No path in the product can
review later: a private review lives server-side with an expiry, nothing lists
pending reviews (API gap, RULES #1), and the only answers to the question the
press raises are "keep reviewing here" and a ``DELETE``. The label promised a
return the dialog cannot deliver — RULES #12's failure, wearing a button.

The second defect is the editor's, one dialog over. 4.5 slice A had to scroll
the *skill* editor's abandon-band into view, because the reader who pressed
Escape is the one already scrolled down to the body textarea; this band is the
**last** child of the scrolling ``.modal-body`` and the evidence above it (target,
two tree hashes, a per-file diff, validity, risk, recovery policy) is taller
than the body at every width. The foot button is always on screen, so raising a
question off-screen is the *likely* path, not the edge case.

Two rules, both directions of each:

1. **The exit says what the press opens.** ``updateExitLabel`` is the only thing
   that decides it, and it lives in ``computed`` — the template reads the
   property, and a function's ``.length`` is its ARITY, so as a method this
   would print ``0`` on every review (2.1, then 4.3b's ``batchStaleTargets``,
   then 4.7's ``syncPickedTargets``: the same defect, three times, each time
   fixed and each time reachable again).
2. **A confirmation that raises a question must raise it where the reader is.**
   Asserted against the mechanism AND its subject, because a bare
   ``assertIn("scrollIntoView", ...)`` would pass on a scroll aimed at the
   editor's band or at nothing.

``updateReviewIsBlocked`` is deleted here: declared in ``methods`` at 4.8's
arrival, read by nothing in ``skillsmgr/`` or ``tests/``. It is the sixth
recorded instance of this branch's own "declared and never read" class.
"""

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")


def _options_literal():
    """The object literal ``createApp`` is handed, brace-matched.

    Slicing ``computed: {`` ... ``watch: {`` contains the getters whether or
    not they are inside the object, so it passes on a broken tree. This asks
    the object what it has, which is the only question worth asking after 2.1,
    4.3b and 4.7 each shipped the same class of bug through a passing test.
    """
    decl = APP.index("const appOptions = {")
    open_brace = APP.index("{", decl)
    depth = 0
    i = open_brace
    while True:
        if APP[i] == "{":
            depth += 1
        elif APP[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return APP[open_brace:i + 1]


def _node(script):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "probe.js"
        path.write_text(script, encoding="utf-8")
        proc = subprocess.run(
            [node, str(path)], capture_output=True, text=True, timeout=60,
        )
    if proc.returncode != 0:
        raise AssertionError("node probe failed: " + proc.stderr.strip()[:800])
    return proc.stdout.strip()


def _probe(body):
    """Run ``body`` with ``__opts`` bound to the real options object."""
    prelude = (
        "const __own = { Object: Object, JSON: JSON, console: console };\n"
        "let __captured = null;\n"
        "const __scope = new Proxy(__own, {\n"
        "  has: (t, k) => !(k in t),\n"
        "  get: (t, k) => (k in t ? t[k] : function () {}),\n"
        "  set: (t, k, v) => { __captured = v; return true; },\n"
        "});\n"
        "with (__scope) { __opts = " + _options_literal() + "; }\n"
        "const __opts = __captured;\n"
    )
    return _node(prelude + body)


class UpdateExitPlacementTests(unittest.TestCase):
    """Where the label is decided — the arity trap, from three directions."""

    def test_the_exit_label_is_a_computed_and_not_a_method(self):
        out = _probe(
            "const out = {};\n"
            "for (const n of ['computed', 'methods', 'data', 'watch']) {\n"
            "  out[n] = Object.keys(__opts[n] || {});\n"
            "}\n"
            "console.log(JSON.stringify(out));\n"
        )
        blocks = json.loads(out)
        self.assertIn(
            "updateExitLabel", blocks["computed"],
            "the exit label must be a computed: the template reads the property, "
            "and a function's .length is its arity",
        )
        self.assertNotIn(
            "updateExitLabel", blocks["methods"],
            "as a method, `{{ updateExitLabel }}` prints the arity, not the label "
            "(2.1, 4.3b batchStaleTargets, 4.7 syncPickedTargets)",
        )

    def test_the_exit_label_names_the_exit_the_press_actually_opens(self):
        """Executed, not read: four real modal states through the real getter."""
        out = _probe(
            "const label = __opts.computed.updateExitLabel;\n"
            "const run = (modal) => label.call({ modals: { update: modal } });\n"
            "const out = [\n"
            "  run(null),\n"
            "  run({ review: null, success: null }),\n"
            "  run({ review: { review_state: 'pending' }, success: null }),\n"
            "  run({ review: { review_state: 'blocked' }, success: null }),\n"
            "  run({ review: { review_state: 'no-change' }, success: null }),\n"
            "  run({ review: { review_state: 'pending' }, success: { id: 1 } }),\n"
            "];\n"
            "console.log(JSON.stringify(out));\n"
        )
        got = json.loads(out)
        # Only a PENDING, un-applied review raises the abandon question, so it
        # is the only state whose label may promise anything else.
        self.assertEqual(
            got, ["Close", "Close", "Cancel review…", "Close", "Close", "Close"],
        )

    def test_the_button_carries_no_label_of_its_own(self):
        """The ternary the button used to hold, deleted rather than moved."""
        button = re.search(
            r'<button class="btn btn-secondary" type="button" @click="requestCloseUpdate">(.*?)</button>',
            HTML, re.S,
        )
        self.assertIsNotNone(button, "the update dialog's exit button is gone")
        body = button.group(1)
        self.assertEqual(body.strip(), "{{ updateExitLabel }}")
        self.assertNotIn("Review later", body)

    def test_no_dead_predicate_survives_in_the_update_flow(self):
        self.assertNotIn(
            "updateReviewIsBlocked", APP,
            "declared and never read (the sixth recorded instance on this branch)",
        )


class AbandonBandVisibilityTests(unittest.TestCase):
    """The question must be raised where the reader is looking."""

    def _request_close_body(self):
        start = APP.index("requestCloseUpdate() {")
        # Brace-matched to the end of the method, so a comment quoting a brace
        # cannot end it early (4.6b's `_document_block` trap).
        i = APP.index("{", start)
        depth = 0
        while True:
            if APP[i] == "{":
                depth += 1
            elif APP[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        return APP[start:i + 1]

    def test_raising_the_question_scrolls_this_dialogs_own_band_into_view(self):
        body = self._request_close_body()
        self.assertIn("scrollIntoView", body)
        self.assertIn('[data-modal="update"] .update-close-confirm', body,
                      "the scroll must target the update band, not any banner — "
                      "and not the skill editor's, which 4.5a already scrolls")

    def test_the_scroll_happens_after_the_question_is_raised(self):
        """Ordering, because `block: nearest` against a not-yet-painted band
        scrolls the body to a stale position — the same reason 4.7b pins
        `busy = true` BEFORE the first await."""
        body = self._request_close_body()
        self.assertLess(
            body.index("confirmingClose = true"), body.index("scrollIntoView"),
            "the band must be in the DOM before anything measures it",
        )

    def test_the_band_is_the_last_child_of_the_scrolling_body(self):
        """The defect's precondition, pinned so a future reorder cannot hide it.

        Asserting the fix alone would let a reordering put the band back at the
        top while the test still passed — and the scroll would then be the
        thing making it work, which is fine, so this states the premise
        honestly rather than pretending the scroll is load-bearing forever.
        """
        modal = HTML[HTML.index('data-modal="update"'):HTML.index('data-modal="history"')]
        band = modal.index('class="banner banner-warn update-close-confirm"')
        body_close = modal.rindex("</div>\n        </div>\n      </div>") if "</div>\n        </div>\n      </div>" in modal else None
        self.assertIsNotNone(body_close)
        self.assertLess(band, body_close, "the band must sit inside the modal body")


if __name__ == "__main__":
    unittest.main()