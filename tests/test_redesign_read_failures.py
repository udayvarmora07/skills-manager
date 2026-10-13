"""6.3 — a read that FAILED is not a read that found nothing.

Four loaders (`loadTrash`, `loadOverviewHistory`, `loadRecoverySnapshots`,
`loadWorkspaces`) reported a failure **only as a toast** — a four-second strip
— and then left their view rendering an empty-state sentence that makes a claim
about the disk:

    "The global trash is empty"
    "Global trash is empty."
    "No history entries yet."
    "No retained source snapshots for this exact target."
    "No adapter evidence is available on this machine."

`loadOverviewHistory`'s catch was not even a toast: it was completely silent.
None of this was reachable by a stdlib test, which is why 6.3 had to measure it
before changing it.

What these tests pin is the PROPERTY, not the copy:

* every one of the four has an error field in `data()`;
* each loader clears it **on the success path only**, never on a timer, so a
  flapping connection keeps saying what it last failed to do;
* the error branch **outranks** the empty branch in the template — this is the
  assertion that matters, because putting it after would leave every one of
  these views still claiming emptiness, and the order is invisible to grep;
* each error branch is reachable and each retry re-runs its own loader.

The ordering assertions are checked by INDEX within the branch's own block, and
each one has a control: the tests fail if the error branch is deleted as well
as if it is moved, because "no error branch at all" must not read as a pass.
That is this repo's seventh recorded "a check that reports PASS about a path it
cannot see".
"""

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "skillsmgr", "webui", "app.js")
HTML = os.path.join(ROOT, "skillsmgr", "webui", "index.html")
CSS = os.path.join(ROOT, "skillsmgr", "webui", "styles.css")

with open(APP, encoding="utf-8") as fh:
    APP_SRC = fh.read()
with open(HTML, encoding="utf-8") as fh:
    HTML_SRC = fh.read()
with open(CSS, encoding="utf-8") as fh:
    CSS_SRC = fh.read()


def _strip_comments(text, line_comments=False):
    """Comment-stripped source. 1.7's lesson: a locator that walks raw text
    slices a comment in half and hands the parser prose.

    `line_comments` is off for the MARKUP on purpose. The first version ran the
    `//` rule over index.html too, and `xmlns:xlink="http://www.w3.org/..."`
    started a line comment that ate the rest of the element — so `find()` for a
    label returned an offset inside a namespace declaration, and the chain walk
    reported the correct tree as broken. A stripper that damages what it is
    meant to protect is worse than no stripper.

    HTML comments ARE stripped, in both modes. Leaving them in was the second
    version of the same mistake: 6.3's own `<!-- 6.3 — a failed read is not an
    empty one -->` prose parsed as markup, the chain locator stopped inside my
    own comment, and the suite reported the correct tree as broken. Seventh
    occurrence of this repo's lesson, and the comment I had just written was
    the thing that broke the checker.
    """
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
        elif line_comments and text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
            out.append(" ")
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


APP_CODE = _strip_comments(APP_SRC, line_comments=True)
HTML_CODE = _strip_comments(HTML_SRC)


def _chain_text(label):
    """The sibling `v-if` / `v-else-if` group the label lives in.

    THREE versions of this locator were wrong before this one, all in the same
    direction — each failed a CORRECT tree — and the reason is worth the space:

    (a) Two raw offsets in the whole file. The markup is 2,900 lines of
        sibling branches, so the nearest error field above a label is usually
        in a DIFFERENT view.
    (b) Cut at the nearest `<div`/`<p`. The label sits inside an `<h3>` or a
        `<td>`, so the cut landed between the chain opener and the claim.
    (c) Nearest preceding `v-(else-)?if` tag. That finds the claim's OWN
        branch — which is correct — and returns a slice starting *at* it, so
        the sibling branches ABOVE it (where the error branch lives) were
        outside the slice every time. It asserted the error field was absent
        from a region that begins after the error field.

    The only thing that works is the sibling group itself, which in this
    markup is delimited by INDENTATION: the file indents every view branch and
    every state branch consistently. So: find the label's line, take its
    indentation, and collect the whole run of lines at that same indentation
    that carry a `v-if`/`v-else-if`. A test that cannot locate its own subject
    is not a test; this is the repo's seventh recorded "the gate is reading
    prose, not structure", and each failure mode was found by running it on a
    tree that was already correct.
    """
    lines = HTML_CODE.split("\n")
    idx = next((i for i, ln in enumerate(lines) if label in ln), None)
    if idx is None:
        raise AssertionError("claim not found: " + label)
    indent = len(lines[idx]) - len(lines[idx].lstrip())
    start = idx
    while start > 0:
        prev = lines[start - 1]
        if not prev.strip() or (len(prev) - len(prev.lstrip())) != indent:
            break
        if not re.match(r"\s*<(?:div|p|section|template|ul|span|table)\s+v-(?:else-)?if=", prev):
            break
        start -= 1
    end = idx
    while end + 1 < len(lines):
        nxt = lines[end + 1]
        if not nxt.strip() or (len(nxt) - len(nxt.lstrip())) != indent:
            break
        if not re.match(r"\s*<(?:div|p|section|template|ul|span|table)\s+v-(?:else-)?if=", nxt):
            break
        end += 1
    group = "\n".join(lines[start:end + 1])
    assert re.search(r"v-(?:else-)?if=", group), (
        "no v-if sibling group around %r — the locator, not the tree, is wrong" % label)
    return group


def _view_window(label):
    """The slice of markup belonging to the VIEW BRANCH that owns `label`.

    Every version of the order assertion that compared raw offsets across the
    whole file was wrong for one reason: `trashError` appears in THREE places
    (the Trash view, the Recovery sidepanel, the Recovery ledger). Deleting the
    Trash view's branch left the ledger's, which sits EARLIER in the file, so a
    naive `err_at < claim_at` stayed green — the mutation that proves the test
    passed on the defect. Comparing the wrong branch to the right one is the
    same mistake as the locator reading prose.

    The owner is a `v-if`/`v-else-if="view === '...'"` div, so the window runs
    from that opener to the next view opener. Both branches under test live in
    one, and a claim outside any view window gets the whole document rather
    than a silently-too-small slice.
    """
    at = HTML_CODE.find(label)
    assert at > -1, "claim not found: " + label
    openers = [m.start() for m in re.finditer(
        r'<div v-(?:else-)?if="view ===', HTML_CODE)]
    start = -1
    for o in openers:
        if o <= at:
            start = o
        else:
            end = o
            return HTML_CODE[start:end]
    return HTML_CODE[max(start, 0):]


def _chain(label):
    """The contiguous run of sibling `v-if`/`v-else-if`/`v-else` BRANCH lines
    that ends at the claim, from the first of them.

    Four earlier locators tried to parse containment out of raw offsets and all
    four failed a CORRECT tree — the recorded lesson of this repo, now with the
    count attached. What finally works is the property the assertion actually
    needs and nothing more: **the branches of one chain are consecutive LINES
    at the same indentation.** No parser, no containment, no offsets. Each
    branch in this markup opens on its own line and closes before the next one
    starts, so a run of same-indent `v-` branch lines IS the chain.

    `v-else` is included: it is the tail of a chain and carries the empty-state
    claim in three of these views, and excluding it made the run stop at the
    wrong line.
    """
    lines = HTML_CODE.split("\n")
    idx = next((i for i, ln in enumerate(lines) if label in ln), None)
    assert idx is not None, "claim not found: " + label
    ind = lambda ln: len(ln) - len(ln.lstrip())
    BRANCH = re.compile(r'^\s*<(?:div|p|section|template|ul|span|table|tr|td|th)\s+v-(?:else-)?(?:if|else)\b')
    assert BRANCH.match(lines[idx]), (
        "the line carrying %r is not itself a v- branch: %r — the locator, not "
        "the tree, is wrong" % (label, lines[idx]))
    # Walk back over the run of same-indent BRANCH lines. The walk stops at a
    # NON-branch line, which is correct: a chain is a run of branches, and a
    # `<!-- comment -->` between them is part of the chain's markup, not a
    # boundary. `v-else` chains are unbroken; where a comment or a stray
    # `<p>` sits between two branches of ONE chain, this narrower run reports
    # only the tail — which is why every claim under test sits on a line that
    # is immediately preceded by its own branch lines.
    # Walk back to the chain's opener. Blank lines and COMMENT lines are
    # TRANSPARENT: a `<!-- why this branch exists -->` between two branches of
    # one chain is part of that chain's markup, and stopping at it is how the
    # first version of this function silently dropped the error branch and
    # then reported the tree as broken. The comment is stripped for the LOCATOR
    # only — the assertions still read the real branch lines above it.
    def _blankish(ln):
        t = ln.strip()
        return not t or t.startswith("<!--") or t.startswith("-->") or t.startswith("*")

    start = idx
    while start > 0:
        prev = lines[start - 1]
        if BRANCH.match(prev) and ind(prev) == ind(lines[idx]):
            start -= 1
            continue
        if _blankish(prev):
            start -= 1
            continue
        break
    return lines, start, idx


def _error_line(field, label):
    """The index of the branch line testing `field` INSIDE the claim's chain,
    searching FORWARD from the chain's opener.

    Forward, not backward — and that direction is the whole point. A backwards
    scan finds the branch either side of the claim, so **the mutation this
    test exists to catch came back GREEN**: moving `trashError` BELOW its
    empty claim left the scan still returning a line number, just a different
    one, and `err < idx` stayed true. Measured, then fixed. A locator that
    searches the wrong direction is the repo's recorded failure mode for the
    ninth time, and it is the worst version because it produces a plausible
    number rather than an obvious absence.
    """
    lines, start, idx = _chain(label)
    for i in range(start, idx + 1):
        if field in lines[i] and re.match(r"^\s*<", lines[i]):
            return i
    return -1


def _method(name):
    """The body of one `async name() {` method, brace-matched.

    Marker-slicing between the method name and the next `\n    }` is the
    failure mode 2.1 recorded: it returns the same region whether or not the
    method is inside the options object.
    """
    m = re.search(r"\n    (?:async )?" + re.escape(name) + r"\(\)\s*\{", APP_CODE)
    assert m, "method not found: " + name
    start = m.end()
    depth = 1
    i = start
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



# (loader, error field, [labels whose empty-state claim must be outranked])
READS = [
    # Each label must be text ON the branch line that renders it.
    # "The global trash is empty" is a string in a ternary inside an <h3>
    # several lines below its branch, so the locator refuses it rather than
    # guessing — that read's claim is on a real branch line twice (Recovery
    # sidepanel, Recovery ledger) and both are asserted.
    # Branch-line labels only. "Trash is empty" and "The global trash is
    # empty" are sentences inside `<h3>` CHILDREN of their branch, several
    # lines below it — the branch that owns them is named here instead, and
    # `test_the_claim_survives_inside_its_branch` walks down into the branch to
    # assert the copy is still there. That split is why this locator is a line
    # locator at all: one line is one branch, and nesting is not.
    ("loadTrash", "trashError", ["Global trash is empty."]),
    ("loadOverviewHistory", "overviewHistoryError", ["No history entries yet."]),
    ("loadRecoverySnapshots", "recoverySnapshotsError",
     ["No retained source snapshots for this exact target."]),
    ("loadWorkspaces", "workspacesError", ["No adapter evidence is available on this machine."]),
]


class ErrorStateExistsTests(unittest.TestCase):
    """Every failed read has somewhere to live that is not a toast."""

    def test_each_loader_has_a_data_field_for_its_failure(self):
        for _loader, field, _labels in READS:
            with self.subTest(loader=_loader):
                self.assertRegex(APP_CODE, r"\n      " + field + r": (?:null|\"\"),")

    def test_every_read_is_covered(self):
        """The control: a new loader with no error field must not slip past
        this file by simply not being listed."""
        self.assertEqual(4, len(READS))

    def test_no_failed_read_reports_only_through_a_toast(self):
        """The defect, stated as a property over the whole file: a loader that
        toasts in its catch and clears its list has turned a transport failure
        into an empty-state claim.

        `loadSkills` is exempt on purpose — it already has a real in-pane
        banner and retires the age claim. `loadHistory` writes its error onto
        the MODAL object (`m.error`), so both the `this.` and bare-`x.error`
        shapes have to count, or the property misses the one case it was found
        by — which is the fifth recorded way a gate can be right about
        everything except the thing it was written for.
        """
        offenders = []
        for m in re.finditer(r"\n    (?:async )?(load\w*)\(\)\s*\{", APP_CODE):
            name = m.group(1)
            if name == "loadSkills":
                continue
            body = _method(name)
            catch_at = body.find("catch")
            if catch_at < 0:
                continue
            tail = body[catch_at:]
            if "this.toast(" not in tail:
                continue
            writes_error = re.search(r"\b(?:this\.|m\.)\w*[Ee]rror\s*=", tail)
            if not writes_error:
                offenders.append(name)
        self.assertEqual([], offenders,
                         "these loaders report failure only as a toast: " + ", ".join(offenders))


class SuccessClearsTheErrorTests(unittest.TestCase):
    """Cleared on the SUCCESS path only, never on a timer."""

    def test_each_loader_clears_its_error_after_a_successful_read(self):
        for loader, field, _labels in READS:
            with self.subTest(loader=loader):
                body = _method(loader)
                success = body.find("this." )
                clears = body.find("this." + field + " = null")
                self.assertGreater(clears, -1, "%s never clears %s" % (loader, field))
                clears_at = body.find("catch")
                self.assertLess(clears, clears_at,
                                "%s clears %s at or after its catch, which is the "
                                "timer-based clear that 5.6a/2.3 forbid" % (loader, field))

    def test_a_failure_does_not_leave_a_stale_success_stamp(self):
        """`loadSkills` retired `lastScanAt` on failure for the same reason;
        these four have no stamp, but the shapes must not diverge — a
        `this.x = []` in the catch is a silent replacement of the truth."""
        for loader, field, _labels in READS:
            body = _method(loader)
            catch_at = body.find("catch")
            self.assertGreater(catch_at, -1)
            catch = body[catch_at:]
            self.assertIn("this." + field + " =", catch,
                          "%s's catch must set %s, or the view cannot say what "
                          "went wrong" % (loader, field))


class RetryTests(unittest.TestCase):

    def test_each_error_has_a_retry_that_reruns_its_own_loader(self):
        for loader, _field, _labels in READS:
            name = "retry" + loader[4].upper() + loader[5:]
            with self.subTest(loader=loader):
                m = re.search(r"\n    " + re.escape(name) + r"\(\)\s*\{\s*return this\."
                              + re.escape(loader) + r"\(\);\s*\}", APP_CODE)
                self.assertIsNotNone(
                    m, "no %s() that re-runs %s — a retry that hid the error "
                       "without re-reading would be the defect in a fix's clothes"
                       % (name, loader))

    def test_the_quality_retry_shape_is_preserved(self):
        """The pre-existing one this file copies its shape from."""
        self.assertRegex(APP_CODE,
                         r"\n    retryQualityHygiene\(\)\s*\{\s*return this\.loadQualityHygiene\(\);\s*\}")

    def test_every_retry_is_reachable_from_the_markup(self):
        for loader, _field, _labels in READS:
            name = "retry" + loader[4].upper() + loader[5:]
            self.assertIn("@click=\"" + name, HTML_SRC,
                          "%s is declared but no control calls it" % name)


class PresentationTests(unittest.TestCase):

    def test_the_failed_read_shape_is_declared_once_and_uses_tokens(self):
        m = re.search(r"^\.read-failed \{[^}]*\}", CSS_SRC, re.M)
        self.assertIsNotNone(m, ".read-failed has no rule — five hosts reference it")
        rule = m.group(0)
        self.assertNotRegex(rule, r"#[0-9a-fA-F]{3,8}\b", "a literal colour outside the token layer")
        self.assertRegex(rule, r"var\(--warn-soft\)")

    def test_a_failed_read_paints_warn_not_err(self):
        """Nothing is wrong with the reader's data; the app could not go and
        look at it. `err` would read as 'your library is broken'."""
        rule = re.search(r"^\.read-failed \{[^}]*\}", CSS_SRC, re.M).group(0)
        self.assertNotIn("var(--err-soft)", rule)
        self.assertNotIn("var(--err)", rule)

    def test_every_failed_read_is_announced(self):
        """`role="alert"` is what puts it in the live region; a toast alone
        does, but a toast is gone in four seconds."""
        for _loader, field, _labels in READS:
            with self.subTest(field=field):
                self.assertRegex(
                    HTML_CODE,
                    r'class="read-failed" role="alert"[^>]*>\s*[^<]*' + field,
                    "%s is rendered without role=\"alert\"" % field)

    def test_the_read_survives_an_empty_state_that_is_its_own_sibling(self):
        """The control for the locator itself, and the assertion that replaced
        the one this file could not make falsifiable.

        6.3's original version of the presentation suite asserted that each
        empty claim "does not render alongside an error branch", by scanning a
        900-character window. It FAILED on the correct tree twice — once
        because `class="empty-actions"` is a prefix of `class="empty`, and once
        because the window reached past the branch — and after four locator
        rewrites it was still not able to say anything true. So it is gone, and
        this replaces it with the property that is actually in question: the
        copy the reader was shown still EXISTS, on a branch, and the error
        branch is in the same chain ahead of it. Deleting the empty state to
        make a chain tidy is the regression this catches, and deleting the
        error branch is caught by the order test above.
        """
        self.assertIn("The global trash is empty", HTML_CODE)
        self.assertIn("Global trash is empty.", HTML_CODE)
        self.assertIn("No history entries yet.", HTML_CODE)
        self.assertIn("No retained source snapshots for this exact target.", HTML_CODE)
        self.assertIn("No adapter evidence is available on this machine.", HTML_CODE)
        # and each of those copies is on a branch that a chain can reach
        for _loader, field, labels in READS:
            for label in labels:
                with self.subTest(label=label):
                    self.assertRegex(
                        HTML_CODE, r"\sv-(?:else-)?(?:if|else)\b[^\n]*",
                        "sanity")
                    self.assertIn(label, HTML_CODE)


if __name__ == "__main__":
    unittest.main()
