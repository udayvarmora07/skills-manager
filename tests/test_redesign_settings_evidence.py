"""5.7c — the Settings view's accessibility evidence, and the deleted reader.

**How this row found what it found.** 5.7c was written as density work ("the
view is 1335–1756px tall, would a two-column grid be better"). Its item (2)
asked for the evidence `<dl>` to be checked against RULES #12's observed-state
vocabulary. It is:

    System preference = light dark-mode preference
    Reduced motion   = OS has not requested reduced motion

The first is a label glued to a noun. **The second is a false claim about the
reader's own machine, and it was false on every machine.** 6.4c deleted
`prefersReducedMotion` and `readReducedMotion` from `app.js` as "declared and
never read" — the repository's recurring class, ninth recorded instance — and
its test proved it by grepping `app.js` for the two NAMES. It never looked at
the markup, and the markup was still bound to the field, so the binding
resolved to `undefined`, `undefined` is falsy, and the row printed "the OS has
not requested reduced motion" on a desktop that had asked for exactly that.

This is the repository's **tenth** recorded "a gate reporting PASS about a path
it cannot see", and the first whose path was *outside the file the gate read*.
No stdlib test renders the template — 4.4 recorded that when `detailObservation`
threw during render and unmounted the app with every gate green — so nothing
else on this branch could have seen it either.

**What these tests hold now.**

  1. The field exists AND has a reader in the markup. The old test asserted the
     NAME was absent from `app.js`, which is what let the reader be deleted
     silently. The invariant is the other shape of the same claim: a motion
     state may exist only while something reads it.
  2. The reader is a BINDING, not a literal, so the two strings cannot be
     swapped for hardcoded copy and still pass.
  3. The signal is SUBSCRIBED, not sampled once at mount: a reader who turns
     reduced motion on while the app is open is told so.
  4. Every evidence row names its subject in the `<dt>` and carries the observed
     value alone in the `<dd>` — no label fragments glued to a value.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(ROOT, "skillsmgr", "webui", "app.js")
INDEX_HTML = os.path.join(ROOT, "skillsmgr", "webui", "index.html")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def strip_js_comments(source):
    """Comment-free source.

    A block-comment scanner rather than a regex, because a regex that fails to
    pair a comment returns its own prose as code — 1.7's four failed attempts
    in one sentence. The `/*` pairing here is a simple depth counter, which is
    enough for a source file with no `*/` inside a string.
    """
    out = []
    i, n = 0, len(source)
    while i < n:
        two = source[i:i + 2]
        if two == "/*":
            end = source.find("*/", i + 2)
            if end == -1:
                break
            i = end + 2
            continue
        if two == "//":
            end = source.find("\n", i)
            i = n if end == -1 else end
            continue
        out.append(source[i])
        i += 1
    return "".join(out)


def evidence_block(html):
    """The `<dl>` inside `#settings-accessibility`, with its attribute values.

    Sliced by the SECTION id and then by the `<dl>` that follows it, so this
    cannot pick up the About section's own `<dl>` — 1.7's lesson is that a
    locator which silently finds the wrong block makes every assertion over it
    vacuous. If the slice is empty the tests below fail rather than pass.
    """
    start = html.index('<section id="settings-accessibility"')
    end = html.index("</section>", start)
    section = html[start:end]
    match = re.search(r"<dl[^>]*class=\"[^\"]*settings-evidence[^\"]*\"[^>]*>(.*?)</dl>", section, re.S)
    if match is None:
        raise AssertionError("the accessibility-evidence section has no .settings-evidence <dl>")
    return section, match.group(1)


def evidence_rows(body):
    rows = []
    for row in re.findall(r"<div>(.*?)</div>", body, re.S):
        dt = re.search(r"<dt>(.*?)</dt>", row, re.S)
        dd = re.search(r"<dd>(.*?)</dd>", row, re.S)
        if dt and dd:
            rows.append((dt.group(1).strip(), dd.group(1).strip()))
    return rows


class ReducedMotionIsObserved(unittest.TestCase):
    """The row states what the OS is doing, so it has to ask the OS."""

    def test_the_motion_state_exists_and_is_read_by_the_markup(self):
        """The invariant 6.4c wanted, in the shape that cannot pass on a lie.

        6.4c asserted the NAME was absent from `app.js`; that assertion is what
        let the only reader be deleted with no failure. Asserting the field is
        PRESENT *and* bound in the markup holds the same intent — no motion
        state without a reader — and fails the moment one is orphaned again.
        """
        app = read(APP_JS)
        self.assertIn(
            "prefersReducedMotion", app,
            "the reduced-motion field is gone again. If it has no reader, that "
            "is the state 6.4c recorded; if it has one, this test is the wrong "
            "shape and the reader must be named in it.")
        section, _ = evidence_block(read(INDEX_HTML))
        # The row binds the COMPUTED, not the raw field: the value is stated
        # once (4.7's literal-`N` lesson) and the template must not re-derive
        # it. So the reader chain is field -> computed -> markup, and an orphan
        # is any break in it.
        self.assertIn(
            "reducedMotionLabel", section,
            "the Accessibility-evidence row no longer reads the motion signal "
            "— that is exactly the orphan 6.4c deleted the reader for.")
        body = re.search(r"reducedMotionLabel\(\)\s*\{(.*?)\n    \}", app, re.S)
        self.assertIsNotNone(body, "reducedMotionLabel is gone; the <dd> binds nothing")
        self.assertIn(
            "prefersReducedMotion", body.group(1),
            "the row reads a computed that does not read the field: the chain "
            "is broken and the value is now invented.")
        self.assertNotIn(
            "readReducedMotion", app,
            "the one-shot reader is back. The signal must be SUBSCRIBED (see "
            "the next test), not sampled once.")

    def test_the_reader_is_a_binding_not_a_literal(self):
        """Two hardcoded sentences would pass a test that only greps the name.

        Each `dd` that reports an OS signal has to be an interpolation, and
        must interpolate the computed rather than the raw field: the value is
        stated once, in `reducedMotionLabel`, and the template may not re-derive
        it. A `{{ prefersReducedMotion ? 'a' : 'b' }}` in the template is the
        4.7 literal-`N` defect one layer down — two sources that can disagree.
        """
        _, body = evidence_block(read(INDEX_HTML))
        # the raw field never appears in a dd; the computed owns both states
        self.assertNotIn("prefersReducedMotion", body,
                         "the template re-derives the reduced-motion value. It "
                         "has one source: reducedMotionLabel.")
        self.assertIn("{{ reducedMotionLabel }}", body)

    def test_both_states_are_named_in_one_place(self):
        """The two halves of the claim must both exist, or the row cannot fail.

        A computed with one branch is a constant, and a constant rendered as an
        observation is the defect this row is about.
        """
        app = read(APP_JS)
        match = re.search(r"reducedMotionLabel\(\)\s*\{(.*?)\n    \}", app, re.S)
        self.assertIsNotNone(match, "reducedMotionLabel is gone; the <dd> now binds nothing")
        body = match.group(1)
        self.assertIn("prefersReducedMotion", body)
        self.assertEqual(
            body.count("?"), 1,
            "reducedMotionLabel must be a single two-branch decision, got: %r" % body)
        for side in body.split("?"):
            self.assertTrue(
                side.strip().strip(':').strip().strip('"').strip("'"),
                "one branch of reducedMotionLabel is empty: %r" % body)

    def test_the_signal_is_subscribed_and_unsubscribed(self):
        """A reader who changes the OS setting while the app is open.

        Sampling once in `mounted()` makes the row a claim about the machine
        at load, which is the same lie in a smaller window. Both halves are
        asserted together on purpose: a listener that is added and never
        removed leaks a handler per mount, which is invisible until someone
        reloads forty times.
        """
        app = read(APP_JS)
        for hook in ("this.setupMotionListener()", "this.removeMotionListener()"):
            self.assertIn(hook, app, "%s is never called" % hook)
        self.assertRegex(
            app, r"matchMedia\(\"\(prefers-reduced-motion: reduce\)\"\)",
            "the reduced-motion query is not the media query it claims to read")
        # The query itself is an instance field, not reactive data: a
        # MediaQueryList inside `data()` makes Vue walk it. Comments are
        # stripped first — the field's own declaration comment NAMES both
        # fields, so a raw scan of `data()` reads prose (1.7, 2.2).
        code = strip_js_comments(app)
        data_block = code[code.index("  data() {"):code.index("  computed: {")]
        self.assertNotIn("motionMediaQuery", data_block)
        self.assertIn("motionMediaHandler", app)


class EvidenceCopyIsHonest(unittest.TestCase):
    """`<dt>` names the subject, `<dd>` carries the value alone."""

    def test_no_row_glues_a_label_to_a_value(self):
        """`{{ systemThemeLabel }} dark-mode preference` — a measured defect.

        The five subjects' evidence rows are the only place on this view where
        a template concatenated a label onto an interpolated value, and it
        rendered "light dark-mode preference". Asserting that no `<dd>` mixes a
        binding with trailing words covers the class; the row below names the
        two subjects so the fix is readable.
        """
        _, body = evidence_block(read(INDEX_HTML))
        for label, value in evidence_rows(body):
            self.assertNotRegex(
                value, r"\{\{[^}]*\}\}\s+[A-Za-z][A-Za-z .'-]*$",
                "the <dd> for %r glues prose onto an interpolated value: %r"
                % (label, value))

    def test_every_row_has_a_subject_and_a_value(self):
        section, body = evidence_block(read(INDEX_HTML))
        rows = evidence_rows(body)
        self.assertGreaterEqual(len(rows), 4, "the evidence ledger lost rows: %r" % rows)
        labels = [label for label, _ in rows]
        self.assertEqual(len(labels), len(set(labels)), "duplicate subjects: %r" % labels)
        for label, value in rows:
            self.assertTrue(label, "an evidence row has no subject")
            self.assertTrue(value.strip(), "the %r row has no value" % label)
        self.assertIn("OS reduced-motion setting", labels)
        self.assertIn("OS dark-mode setting", labels)
        # the lead sentence must not promise more than the rows deliver
        hint = re.search(r'<p class="hint">(.*?)</p>', section, re.S).group(1)
        self.assertIn("cannot change them", hint)

    def test_the_hint_names_the_signal_it_describes(self):
        """A hint that says the app "honors the OS" while App theme reads
        `Dark` is an overstatement; the reader chose the app's theme and the
        OS row then contradicts it without saying which one is in force."""
        section, _ = evidence_block(read(INDEX_HTML))
        self.assertNotIn("honors the current OS signals", section,
                         "the old hint claims the app always honors the OS even "
                         "when the reader has chosen an explicit theme")


class NodeBehaviour(unittest.TestCase):
    """Run the real listener pair in a Node VM.

    A source assertion cannot tell a subscription from a call that reads
    `.matches` and throws the result away, and this repo's rule is that a
    check which cannot fail is worse than none.
    """

    def _app_options(self):
        script = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {SkillManagerDomain: {
    api: async () => ({}),
    formatBytes(){}, formatTokens(){}, tokenPctClass(){}, tokenBarWidth(){},
    renderMarkdown(){}, parseFrontmatter(){}, formatCompat(){}, formatTools(){},
    groupLogicalSkills(){}, deriveLogicalSkillIdentity(){}, observedIdentity(){}
  }},
  Vue: {createApp(app){ sandbox.app = app; return {mount(){}}; }, nextTick(){}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, documentElement:{dataset:{}}, querySelectorAll(){return [];}},
  setTimeout, clearTimeout
};
// A media query whose `matches` and listener list the test controls. It hangs
// off the sandbox's GLOBAL `window` because the guard in the product reads
// `typeof window` — stubbing `ctx.window` instead would be tested in a
// context the guard rejects, which is the 5.3c harness shape.
function fakeMql(matches) {
  const listeners = [];
  return {
    matches: matches, listeners: listeners,
    addEventListener: (type, fn) => listeners.push(fn),
    removeEventListener: (type, fn) => {
      const i = listeners.indexOf(fn);
      if (i >= 0) listeners.splice(i, 1);
    },
    fire(value) { this.matches = value; listeners.forEach(fn => fn({ matches: value })); },
  };
}
const mql = fakeMql(true);
let queried = null;
sandbox.window.matchMedia = (q) => { queried = q; return mql; };
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/app.js', 'utf8'), sandbox);
const meth = sandbox.app.methods, comp = sandbox.app.computed;
const ctx = {prefersReducedMotion: false, motionMediaQuery: null, motionMediaHandler: null};
// The real instance has every method; the listener pair calls each other.
ctx.removeMotionListener = meth.removeMotionListener;
meth.setupMotionListener.call(ctx);
const afterMount = ctx.prefersReducedMotion;
const subscribed = mql.listeners.length;
mql.fire(false);
const afterFire = ctx.prefersReducedMotion;
const labelOff = comp.reducedMotionLabel.call(ctx);
mql.fire(true);
const labelOn = comp.reducedMotionLabel.call(ctx);
meth.removeMotionListener.call(ctx);
console.log(JSON.stringify({
  query: queried, afterMount, subscribed, afterFire, labelOn, labelOff,
  afterRemove: mql.listeners.length,
  cleared: ctx.motionMediaQuery === null && ctx.motionMediaHandler === null,
}));
"""
        out = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=60,
            cwd=ROOT)
        self.assertEqual(out.returncode, 0, out.stderr.strip())
        return json.loads(out.stdout.strip().splitlines()[-1])

    @unittest.skipUnless(subprocess.run(["which", "node"], capture_output=True).returncode == 0,
                         "node unavailable: the listener pair is not exercised")
    def test_mounting_reads_the_query_and_changing_it_updates_the_row(self):
        data = self._app_options()
        self.assertEqual(data["query"], "(prefers-reduced-motion: reduce)")
        self.assertIs(data["afterMount"], True,
                      "mounted() ignored the query's own value")
        self.assertEqual(data["subscribed"], 1, "no change listener was attached")
        self.assertIs(data["afterFire"], False,
                      "an OS change did not reach the field the row reads")
        self.assertEqual(data["afterRemove"], 0, "the listener outlived the component")
        self.assertTrue(data["cleared"], "the query/handler were not released")
        # The label is the row's whole payload, so both of its states have to be
        # distinct words about the OS — not one branch empty, not a constant.
        self.assertNotEqual(data["labelOn"], data["labelOff"],
                            "reducedMotionLabel returns one string for both OS "
                            "states: the row cannot be wrong, which means it "
                            "cannot be right either")
        self.assertIn("honored", data["labelOn"])
        self.assertIn("not requested", data["labelOff"])


if __name__ == "__main__":
    unittest.main()