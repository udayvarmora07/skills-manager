"""5.9a — the About section in Settings.

DESIGN-V2 §8 asks Settings for "About/data location"; 5.7a filed the absence
here. What the section may SAY is the whole test: every line on it is observed
(RULES #12), which rules out the three things an About section usually reaches
for — a version number no route carries, a changelog link, and a description of
capabilities nobody measured.

The load-bearing claims, in the order they can break:

1. `observedRoots` is the switcher's OWN list with the synthetic `All scopes`
   row dropped. A second derivation of "which directories is this pointed at"
   is free to disagree with the control that changes which root is loaded.
2. The tail of a path is what is kept. CSS truncation keeps the head, and on
   one machine every root shares a head, so the column that exists to tell
   them apart rendered eight identical prefixes.
3. The section is reachable from the rail and TAKES FOCUS (5.7b's contract).

The Node VM loads the real `app.js`, which is the shape 5.5 and 7.1 settled on:
slicing the options literal out of the source passes on a broken tree.
"""

import json
import os
import re
import subprocess
import unittest

APP_JS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skillsmgr", "webui", "app.js")
INDEX_HTML = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skillsmgr", "webui", "index.html")
STYLES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skillsmgr", "webui", "styles.css")

with open(APP_JS, encoding="utf-8") as handle:
    APP = handle.read()
with open(INDEX_HTML, encoding="utf-8") as handle:
    HTML = handle.read()
with open(STYLES, encoding="utf-8") as handle:
    CSS = handle.read()


def _options():
    """Evaluate the real app.js and hand back its options object.

    Deliberately not a slice: 7.1 recorded a harness that read the options
    LITERAL and so could not see a module-scope const (`SETTINGS_SECTIONS`)
    that 5.7b had started using, reporting a TypeError about a Settings list
    inside a suite about profiles.
    """
    driver = r"""
const fs = require("fs");
const vm = require("vm");
const src = fs.readFileSync(process.argv[1], "utf8");
const captured = {};
// app.js ends in a BARE `createApp(appOptions).mount("#app")` — it does not
// read `Vue.createApp`, so a sandbox that only stubs `Vue` captures nothing
// and every assertion below fails on an empty payload rather than on the
// product. Stubs the global the file actually calls.
const createApp = (o) => { captured.o = o; return { mount() {}, component() {} }; };
const Vue = { createApp, nextTick() {}, ref: (v) => ({ value: v }), reactive: (v) => v };
const ctx = {
  Vue, createApp, console, setTimeout, clearTimeout, fetch: () => new Promise(() => {}),
  location: { host: "127.0.0.1:8791", href: "http://127.0.0.1:8791/" },
  document: {
    addEventListener() {}, querySelector: () => null, querySelectorAll: () => [],
    createElement: () => ({ style: {}, setAttribute() {}, appendChild() {},
                            classList: { add() {}, remove() {} }, textContent: "" }),
    documentElement: { setAttribute() {}, getAttribute: () => null, style: {} },
    body: { appendChild() {}, removeChild() {}, classList: { add() {}, remove() {} } },
  },
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  navigator: { language: "en-US" },
  matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
};
ctx.globalThis = ctx; ctx.window = ctx;
vm.createContext(ctx);
// domain.js is a separate file the page loads first, and app.js THROWS at
// module scope without it ("SkillManagerDomain missing"). Loading app.js
// alone would fail for a reason that has nothing to do with this section.
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx, { filename: "domain.js" });
vm.runInContext(src, ctx, { filename: "app.js" });
process.stdout.write(JSON.stringify({
  hasObservedRoots: "observedRoots" in (captured.o.computed || {}),
  hasInMethods: "observedRoots" in (captured.o.methods || {}),
  roots: (() => {
    const app = Object.create(captured.o.methods);
    app.scopes = [
      { id: "global", label: "Global", path: "/tmp/sandbox/data/skills-manager/skills", exists: true, count: 45 },
      { id: "claude-code", label: "Claude Code", path: "/tmp/sandbox/.claude/skills", exists: true, count: 19 },
      { id: "opencode", label: "Opencode", path: "/tmp/sandbox/.config/opencode/skills", exists: false, count: 0 },
      // No `exists` and no `count` keys at all. `scopeOptions` normalises both
      // (`exists: s.exists !== false`, `count: s.count || 0`); a second
      // derivation reading `this.scopes` directly would carry `undefined` for
      // each. That is the control for "reads the switcher's list" — a grep for
      // the word `scopeOptions` would pass on a broken tree, which is the
      // repo's eighth-recorded failure mode and 7.1's harness lesson.
      { id: "agents", label: "Agents", path: "/tmp/sandbox/.agents/skills" },
    ];
    app.scopeBudgetFor = () => null;
    Object.assign(app, captured.o.computed);
    for (const [k, v] of Object.entries(captured.o.computed)) {
      if (typeof v === "function") { try { Object.defineProperty(app, k, { get: v.bind(app), configurable: true }); } catch (e) {} }
    }
    return app.observedRoots;
  })(),
  allScopesCountSource: String(captured.o.computed.allScopesCount),
}));
"""
    domain = os.path.join(os.path.dirname(APP_JS), "domain.js")
    out = subprocess.run(["node", "-e", driver, APP_JS, domain], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise AssertionError("node VM failed: " + out.stderr[-1500:])
    return json.loads(out.stdout)


class AboutSection(unittest.TestCase):
    def test_observed_roots_is_a_computed_and_not_a_method(self):
        options = _options()
        self.assertTrue(options["hasObservedRoots"], "observedRoots must live in computed:")
        # 5.5's trap: a function CALLED from a template must be a method,
        # because Vue unwraps a computed to its value before the template
        # sees it. `v-for="root in observedRoots"` never calls it, so computed
        # is right — and the wrong block is how 5.5's silent blank section
        # happened.
        self.assertFalse(options["hasInMethods"], "observedRoots belongs in one block only")

    def test_observed_roots_drops_the_synthetic_all_scopes_row(self):
        roots = _options()["roots"]
        ids = [r["id"] for r in roots]
        self.assertEqual(["global", "claude-code", "opencode", "agents"], ids)
        for root in roots:
            self.assertNotEqual("every detected root", root.get("path", ""))

    def test_observed_roots_reads_the_switchers_list_and_not_the_scopes_array(self):
        # The control for the comment's claim. The 4th scope has neither an
        # `exists` nor a `count` key; `scopeOptions` fills both in. Reading
        # `this.scopes` directly leaves them `undefined`, which is falsy, so
        # an undetected root would render as "not detected" on the About pane
        # while the switcher beside it draws an available dot. Two derivations
        # of one list, free to disagree — the defect 2.1e and 5.5b both name.
        roots = {r["id"]: r for r in _options()["roots"]}
        self.assertIs(roots["agents"]["exists"], True)
        self.assertEqual(roots["agents"]["count"], 0)

    def test_observed_roots_keeps_the_tail_of_a_long_path(self):
        roots = _options()["roots"]
        by_id = {r["id"]: r for r in roots}
        # 34-char budget, kept from the END. The opencode path is the long one.
        self.assertTrue(by_id["opencode"]["short"].startswith("…/"), by_id["opencode"]["short"])
        self.assertTrue(
            by_id["opencode"]["short"].endswith("opencode/skills"),
            by_id["opencode"]["short"],
        )
        # The control: two roots whose HEADS are identical must not produce
        # identical shortened strings, which is the defect itself.
        self.assertNotEqual(by_id["claude-code"]["short"], by_id["opencode"]["short"])
        # And the leading `…/` is the assertion that the head was dropped.
        self.assertNotIn("/tmp/sandbox/.config", by_id["opencode"]["short"])

    def test_a_path_that_fits_is_returned_unchanged(self):
        # No ellipsis is added to a string that never needed one. Without this
        # the helper is "always shorten", and the test above cannot tell an
        # ellipsis that marks a truncation from one that marks nothing.
        roots = _options()["roots"]
        short = [r for r in roots if r["id"] == "claude-code"][0]
        self.assertEqual("/tmp/sandbox/.claude/skills", short["short"])
        self.assertNotIn("\u2026", short["short"])

    def test_the_section_states_no_version(self):
        about = HTML[HTML.index('<section id="settings-about"'):]
        about = about[: about.index("</section>")]
        # The honest gap: no route carries a version and RULES #1 freezes the
        # REST contract. A "v1.0.2" on this pane would be a constant read out
        # of a file the reader cannot see.
        # Scoped to THIS section. The whole document legitimately carries
        # version-shaped strings (Lucide 1.54.0, the Geist families), and a
        # page-wide grep would have failed for reasons that are not about this
        # pane - a check scoped wider than its own subject, the 4.7d mistake.
        self.assertNotRegex(about.lower(), r"\bv?\d+\.\d+\.\d+\b")

    def test_the_one_remote_host_is_a_real_literal_in_the_product(self):
        # Not a promise written into copy: the host named on the pane is the
        # one the product actually dials.
        registry = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skillsmgr", "registry.py")
        with open(registry, encoding="utf-8") as handle:
            self.assertIn("https://skills.sh", handle.read())
        self.assertIn("skills.sh", HTML)

    def test_every_selector_the_section_uses_has_a_rule(self):
        # 5.1c's finding: "a selector that does not exist is quieter than one
        # declared and never read" — an unstyled `<ul>` wears disc markers and
        # a 40px indent, which is what the Install results list did.
        block = HTML[HTML.index('<section id="settings-about"'):]
        block = block[: block.index("</section>")]
        for cls in re.findall(r'class="([a-z-]+(?: [a-z-]+)*)"', block):
            for name in cls.split():
                self.assertRegex(CSS, r"(^|[\s,>+~])\." + re.escape(name) + r"[\s,{:.]", name)

    def test_the_rail_owns_the_fifth_subject_and_focuses_it(self):
        sections = re.findall(r'\{ id: "(settings-[a-z-]+)"', APP)
        self.assertIn("settings-about", sections)
        self.assertEqual(len(sections), len(set(sections)), "a duplicated id makes one rail row unreachable")
        self.assertIn('id="settings-about"', HTML)
        self.assertIn('tabindex="-1"', HTML[HTML.index('<section id="settings-about"'):][:400])
        # `jumpToSetting` validates against SETTINGS_SECTIONS, so a rail entry
        # with no section silently does nothing — the reader presses and the
        # marker does not move.
        self.assertIn("if (!SETTINGS_SECTIONS.some((entry) => entry.id === id)) return;", APP)


if __name__ == "__main__":
    unittest.main()