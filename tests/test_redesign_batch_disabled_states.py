"""6.3b — a `busy` flag that only SETS is not a disabled state.

4.7b settled the shape for a double-click: **both** halves, a guard before the
request and `:disabled="busy"` on the control. It gave both to
`toggleSelected`, and the commit note recorded that an attribute cannot stop
two dispatches inside one frame while a guard alone leaves the button looking
clickable — so neither half substitutes for the other.

Measured on 6.3b's arrival, one batch verb had NEITHER:

    `updateBatchTags` set `this.busy = true` inside its own `try`, and no
    `:disabled="busy"` appeared on Add, Remove, or any of the four
    `.batchbar-verb` review buttons.

It is the one batch verb that writes with **no dialog between the press and
the POST** — `openBatch` opens a review the reader must confirm, this goes
straight to `/api/catalog/tags`. Two presses inside one frame therefore
produced two requests, and because the handler ends in `clearSelection()` the
second one re-read a selection that no longer exists, so the failure is not
"a duplicate request" but "a request against targets the reader can no longer
see".

What these tests pin:

* every batch-bar verb that WRITES carries `:disabled="busy"` — the attribute,
  because it is the half a reader can see;
* `updateBatchTags` guards on `busy` BEFORE the request, not after it — the
  half that actually stops the second dispatch;
* the two halves are asserted separately because the repo has now recorded
  twice that one does not imply the other;
* a control: the guard is checked at a position BEFORE `this.busy = true`, so
  moving it after the assignment — where it can only ever be true — fails.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "skillsmgr", "webui", "app.js")
HTML = os.path.join(ROOT, "skillsmgr", "webui", "index.html")

with open(APP, encoding="utf-8") as fh:
    APP_SRC = fh.read()
with open(HTML, encoding="utf-8") as fh:
    HTML_SRC = fh.read()


def _strip_comments(text):
    """Comments removed, because this file's assertions quote the code they
    describe — and 6.3's lesson was that a locator reading prose reports PASS
    about a path it cannot see."""
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("<!--", i):
            end = text.find("-->", i + 4)
            i = n if end < 0 else end + 3
            out.append(" ")
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            out.append(" ")
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


APP_CODE = _strip_comments(APP_SRC)
HTML_CODE = _strip_comments(HTML_SRC)


def _method(name):
    """The body of one method, brace- and string-matched."""
    # parameters are allowed: `updateBatchTags(operation)` is the subject here and
    # a `\(\)\s*\{` pattern could not find it — a locator that cannot name its
    # own subject fails as "not found", which reads like a missing method.
    m = re.search(r"\n    (?:async )?" + re.escape(name) + r"\([^)]*\)\s*\{", APP_CODE)
    assert m, "method not found: " + name
    start, depth, i = m.end(), 1, m.end()
    while i < len(APP_CODE) and depth:
        ch = APP_CODE[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch in "\"'`":
            j = i + 1
            while j < len(APP_CODE) and APP_CODE[j] != ch:
                j += 2 if APP_CODE[j] == "\\" else 1
            i = j
        i += 1
    return APP_CODE[start:i - 1]


# Every batch-bar control that either WRITES or opens a review. A control that
# only reads (Select visible) is deliberately absent: `:disabled` on it would
# be decoration.
BATCH_VERBS = [
    ("updateBatchTags('add')", "Add"),
    ("updateBatchTags('remove')", "Remove"),
    ("openBatch('enable')", "Enable"),
    ("openBatch('disable')", "Disable"),
    ("openBatch('sync')", "Sync"),
    ("openBatch('remove')", "Remove"),
]


class BatchVerbIsDisabledInFlightTests(unittest.TestCase):
    """The half a reader can see."""

    def test_every_writing_batch_verb_is_disabled_while_busy(self):
        for handler, label in BATCH_VERBS:
            with self.subTest(handler=handler):
                # the exact button, found by its handler, so a relabelled verb
                # cannot pass by having its disabled state checked on another
                m = re.search(
                    r"<button[^>]*@click=\"" + re.escape(handler) + r"\"[^>]*>",
                    HTML_CODE)
                self.assertIsNotNone(m, "no button calls " + handler)
                tag = m.group(0)
                self.assertIn(
                    ':disabled="busy"', tag,
                    'the %r button (%s) carries no :disabled="busy", so it looks '
                    "clickable while a write is in flight. 4.7b's rule is both "
                    "halves or neither." % (label, handler))

    def test_the_danger_verb_is_the_one_that_is_disabled(self):
        """The control: the destructive verb is the one a reader is most
        likely to press twice. It must be in the list above, not merely
        somewhere in the bar."""
        m = re.search(r"<button[^>]*@click=\"openBatch\('remove'\)\"[^>]*>",
                      HTML_CODE)
        self.assertIsNotNone(m)
        self.assertIn("batchbar-danger", m.group(0))
        self.assertIn(':disabled="busy"', m.group(0))


class GuardStopsTheSecondDispatchTests(unittest.TestCase):
    """The half that actually stops the request."""

    def test_update_batch_tags_guards_before_it_posts(self):
        body = _method("updateBatchTags")
        guard = body.find("if (this.busy) return")
        self.assertGreater(guard, -1,
                           "updateBatchTags has no busy guard, so a second "
                           "press inside one frame sends a second POST")
        sets_busy = body.find("this.busy = true")
        request = body.find('api("/api/catalog/tags"')
        self.assertGreater(sets_busy, -1, "the handler must still set busy")
        self.assertGreater(request, -1)
        self.assertLess(
            guard, request,
            "the guard is AFTER the request, which is where it can never be true")

    def test_the_control_a_guard_after_the_assignment_cannot_fire(self):
        """If the guard ever moves below `this.busy = true` it is dead code
        that reads as protection. This asserts the ORDER rather than the
        presence, because presence passed on the broken tree."""
        body = _method("updateBatchTags")
        guard = body.find("if (this.busy) return")
        sets_busy = body.find("this.busy = true")
        self.assertNotEqual(guard, -1)
        self.assertNotEqual(sets_busy, -1)
        self.assertLess(guard, sets_busy,
                        "the guard must precede `this.busy = true`; after it, "
                        "busy is always true and the handler never runs")

    def test_the_other_half_was_already_there(self):
        """`busy` is still set and still cleared, so the control cannot be
        satisfied by deleting the work."""
        body = _method("updateBatchTags")
        self.assertIn("this.busy = true", body)
        self.assertIn("this.busy = false", body)


class NoOtherUnguardedWriterTests(unittest.TestCase):
    """The property that found the defect, so the next one is not a list edit.

    Stated over the batch bar rather than over `updateBatchTags` by name: a
    control that passes only while nobody adds a fifth verb. The set is derived
    from what the bar ACTUALLY renders, not from a list written here.
    """

    def _bar_buttons(self):
        """Every `<button>` whose class carries a `batchbar` class, anywhere.

        Two earlier locators were wrong and both are the repo's recorded
        failure: cut the bar by raw offset and it swallowed the whole list pane
        (6.3's lesson, ninth time, in a new file), then try to close it by
        brace depth and a `>` inside an attribute value breaks the walk. The
        locator that cannot be wrong is the one with nothing to parse: **the
        batch bar's controls are exactly the buttons carrying a `batchbar*`
        class**, so find those and stop. Adding a fifth verb cannot escape it,
        and a button outside the bar cannot be mistaken for one.
        """
        return re.findall(r"<button[^>]*class=\"[^\"]*batchbar[^\"]*\"[^>]*>",
                          HTML_CODE)

    def test_no_button_in_the_bar_that_writes_lacks_the_disabled_state(self):
        buttons = self._bar_buttons()
        # The 4 `.batchbar-verb` review buttons plus the Clear control. The
        # tag panel's Add/Remove are `class="btn btn-secondary"` — the same
        # class as every secondary button in the app — so no class-based
        # locator can find them, and guessing by section would be the raw
        # offset this file already got wrong twice. Those two are asserted by
        # HANDLER in the class above, which is exact. Stated rather than
        # pretended around: this property covers the verbs, the per-handler
        # test covers the tags, and together they cover the bar.
        self.assertGreaterEqual(
            len(buttons), 5,
            "found %d batch-bar buttons, expected at least 5 (4 verbs + Clear) "
            "— the locator or the bar changed" % len(buttons))
        # reads only: selection state and tag text, which write nothing
        # `Clear` (4.3b: "it ends the selection rather than acting on it") and
        # `Select visible` write nothing, so a disabled state on them would be
        # decoration. Named here rather than left implicit, because the honest
        # reason a control is exempt is always worth one line.
        READS_ONLY = ("toggleSelectAll", "clearSelection")
        unguarded = []
        for tag in buttons:
            m = re.search(r'@click="([^"]+)"', tag)
            if not m or m.group(1) in READS_ONLY:
                continue
            if ':disabled="busy"' not in tag:
                unguarded.append(m.group(1))
        self.assertEqual([], unguarded,
                         'these bar buttons write or open a review with no '
                         ':disabled="busy": ' + ", ".join(unguarded))


if __name__ == "__main__":
    unittest.main()