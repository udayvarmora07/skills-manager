"""A colour the token layer names, and the colour the cascade paints, are one thing.

Backlog 9.1b. Nine different files agreed that `--accent-line` existed: the
`REQUIRED` contract, `check_doc_matches`' alias, `DESIGN.md`, both themes of
`styles.css`, both themes of `site/site.css`, the landing page's `PALETTE` list
and its parity test. **Nothing read it.** The one place in the product that
paints that colour — the command palette's selected row — spelled it out as
`color-mix(in srgb, var(--accent) 38%, var(--border))`, which is:

  * invisible to `check_unread_tokens`, because that check counts `var(--x)`
    readers and this expression contains two of them;
  * invisible to `check_doc_matches`, because no token is named;
  * **and not even the same colour** — the mix computed to `#92b7b6` (light) and
    `#346464` (dark); the token said `#a8d0cb` and `#1d4744`.

So the product was carrying a hard-coded tint two colour tables disagreed with,
and nine gates were green about it. These are the three assertions that would
have caught it, and each is red-first against the tree 9.1b started from.

The same row also found `--sans`, a token whose value was **byte-identical** to
`--font` and which had **zero** readers in the product. A second name for one
family stack is not a token, it is a divergence waiting to happen.
"""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")
SITE_CSS = (ROOT / "site" / "site.css").read_text(encoding="utf-8")

# The colour steps `check_design_tokens.REQUIRED` contracts. Duplicated as a
# literal on purpose: importing the gate under test and then asserting against
# the gate's own table would make every mutation below a no-op.
PALETTE = (
    "bg", "surface", "surface-2", "surface-3",
    "ink", "ink-2", "ink-3", "ink-4",
    "line", "line-3", "line-strong",
    "accent", "accent-2", "accent-3", "accent-ink", "accent-bg", "accent-line",
    "ok", "ok-bg", "warn", "warn-bg", "err", "err-bg", "mute", "mute-bg",
)


def strip_css_comments(text):
    """The same reason `check_design_tokens` strips them: banner prose that
    *names* a token is not a reader, and this file has comments that do."""
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def blocks_of(css):
    """(selector-list, body) for every flat rule. Token blocks have no nested
    braces, so `[^\\{\\}]*` is exact here — and a selector LIST is several
    comma-separated parts, which is how the product writes its two light themes
    in one rule (`[data-theme="light"], [data-theme="system"]`)."""
    for sel, body in re.findall(r"([^{}]*)\{([^{}]*)\}", css):
        parts = [p.strip() for p in sel.split(",")]
        yield parts, body


def declared_value(css, selector, token):
    """The literal value of `token` in any rule whose selector list contains
    `selector`, or None. Accumulates rather than returning on first miss: a
    first-match scan is how this branch's gates have silently compared nothing."""
    for parts, body in blocks_of(strip_css_comments(css)):
        if selector not in parts:
            continue
        m = re.search(rf"(?<![\w-]){re.escape(token)}\s*:\s*([^;]+);", body)
        if m:
            return m.group(1).strip()
    return None


class SynthesisedPaletteColours(unittest.TestCase):
    """No `color-mix()` may build a colour the token layer already declares.

    The permitted form is a mix against `transparent`, which derives an
    **alpha** from a step (a 18%-err wash is not a palette colour, it is the
    error hue at low opacity) and cannot be expressed by a hex step. A mix
    between two declared steps is the opposite: it invents a fifth colour the
    contract has never heard of, and nothing will ever check it against AA.
    """

    def mixes_between_two_declared_steps(self, css):
        found = []
        code = strip_css_comments(css)
        # A naive `color-mix\(\s*in srgb\s*,([^)]*)\)` truncates at the FIRST
        # `)` — which is the one closing `var(--accent)` — and so reports an
        # empty mix for every expression in the file. That check would pass
        # forever, so the parentheses are balanced instead of guessed: the walk
        # starts at the `(` that OPENS `color-mix(` (`start.start()`), not at
        # the character after its comma, which closes nothing.
        for start in re.finditer(r"color-mix\(\s*in srgb\s*,", code):
            i, depth = start.start(), 0
            while i < len(code):
                if code[i] == "(":
                    depth += 1
                elif code[i] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            if depth != 0:
                continue
            partners = [p.strip() for p in code[start.end():i].split(",")]
            # A partner carries its percentage (`var(--accent) 38%`), so this
            # matches the LEADING token rather than requiring the whole part to
            # be one — the version that required it saw zero mixes ever.
            named = [m.group(1) for m in (re.match(r"var\((--[\w-]+)\)", p) for p in partners) if m]
            if len(named) >= 2:
                found.append(", ".join(partners))
        return found

    def test_the_cascade_never_mixes_two_named_steps_into_a_new_colour(self):
        offenders = self.mixes_between_two_declared_steps(CSS)
        self.assertEqual(
            offenders, [],
            "these synthesise a palette colour inline; name it as a token or "
            "delete the mix: " + "; ".join(offenders[:4]),
        )

    def test_the_landing_page_never_mixes_two_named_steps_into_a_new_colour(self):
        offenders = self.mixes_between_two_declared_steps(SITE_CSS)
        self.assertEqual(offenders, [], "; ".join(offenders[:4]))

    def test_the_check_can_see_a_reintroduced_mix(self):
        """A count of zero passes on a file with no mixes in it at all, which is
        also what an empty scan returns. Prove the scan finds one before trusting
        it to report one."""
        probe = ".x { border-color: color-mix(in srgb, var(--accent) 38%, var(--line)); }"
        self.assertEqual(
            self.mixes_between_two_declared_steps(CSS + "\n" + probe),
            ["var(--accent) 38%, var(--line)"],
        )
        # ...and that an alpha derivation, which is legitimate, is not one.
        alpha = ".y { background: color-mix(in srgb, var(--err) 18%, transparent); }"
        self.assertEqual(self.mixes_between_two_declared_steps(CSS + "\n" + alpha), [])


class OneFamilyOneName(unittest.TestCase):
    """`--sans` and `--font` had byte-identical values and 14 + 0 readers."""

    def test_neither_stylesheet_declares_a_second_name_for_the_family_stack(self):
        for label, css in (("product", CSS), ("site", SITE_CSS)):
            code = strip_css_comments(css)
            self.assertIsNone(
                declared_value(css, ":root", "--sans"),
                label + " declares --sans as well as --font; one stack, one name",
            )
            self.assertNotRegex(code, r"var\(--sans\)")

    def test_both_stylesheets_declare_the_same_family_stack_under_one_name(self):
        for label, css in (("product", CSS), ("site", SITE_CSS)):
            self.assertIsNotNone(declared_value(css, ":root", "--font"), label)

    def test_the_family_stack_is_read_somewhere(self):
        """A token nothing reads is the class this whole branch keeps meeting;
        the deleted duplicate had zero readers, and so would a typo'd rename."""
        self.assertIn("var(--font)", strip_css_comments(CSS))
        self.assertIn("var(--font)", strip_css_comments(SITE_CSS))


class TheRetiredLineStepIsGoneFromEveryFileThatNamedIt(unittest.TestCase):
    """Eight coordinated edits, asserted together or not at all.

    9.1c's row warned that option (b) is "eight coordinated edits across four
    gates; do not do it half", so this class is the half-check: each file that
    quoted `--line-2` is named here, and a new one would have to be added to the
    list by hand. That is a real cost and it is the right trade — the failure
    this guards is a name surviving in one gate's table while the stylesheet has
    moved on, which is the branch's recorded claim-about-a-file class.
    """

    STYLESHEETS = (
        ("skillsmgr/webui/styles.css", CSS),
        ("site/site.css", SITE_CSS),
    )

    def test_no_stylesheet_declares_or_reads_the_deleted_step(self):
        for label, text in self.STYLESHEETS:
            # Comments are allowed to name it — styles.css carries a comment
            # recording WHY it was deleted, and a check that could not tell a
            # comment from a declaration would forbid the explanation. The
            # comment strip is the same one `strip_css_comments` exists for.
            self.assertNotIn("--line-2", strip_css_comments(text), label)

    def test_the_gate_carries_no_live_reference_to_the_deleted_step(self):
        """`check_design_tokens.py` keeps the reasoning where the table was, so
        the name IS in the file — in a comment and in two docstrings. What must
        not survive is a live reference: a `REQUIRED` entry, a
        `check_doc_matches` alias, or a key in `UNREAD_ALLOWED`, any of which
        would require the deleted token again.

        Read through `ast` rather than by line, because a line-based filter has
        to know what a docstring is, and the first version treated two docstring
        lines as live code. That is this file's own rule applied to itself: a
        reader that cannot tell prose from structure reports the explanation as
        the defect. Comments are not in the AST at all, and a module/function/
        class docstring is skipped by identity below.
        """
        tree = ast.parse((ROOT / "check_design_tokens.py").read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                body = getattr(node, "body", None)
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    docstrings.add(id(body[0].value))
        live = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and "--line-2" in n.value and id(n) not in docstrings]
        self.assertEqual(live, [], "a live gate reference to a deleted token")

    def test_the_contract_no_longer_prices_a_step_it_does_not_ship(self):
        """DESIGN.md is the document `check_doc_matches` reads the palette out
        of. A row left behind would be a price for a colour nothing declares,
        and the gate's own comparison cannot see it: it iterates the CSS's
        tokens, not the document's."""
        doc = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
        self.assertNotRegex(doc, r'(?m)^\s*line-2:\s*"?#[0-9a-fA-F]{6}',
                             "the contract still prices a deleted step")

    def test_the_step_the_sites_four_readers_moved_to_is_read_by_each_of_them(self):
        """.btn-secondary, .snippet, .note and .shot read `--line-2`. Each now
        reads a step the PRODUCT already uses for that job, and a reader can
        name which one: the button's edge is the product's `.btn-secondary`
        edge, `.note`'s 2px rule is the document blockquote's rule."""
        code = strip_css_comments(SITE_CSS)
        for selector, token, why in (
            (".btn-secondary", "--line-3", "the product's control boundary"),
            (".snippet", "--line-3", "a box the reader has to find"),
            (".note", "--line-3", "the document blockquote's 2px rule"),
            (".shot", "--line", "its shadow already carries that frame"),
        ):
            rules = re.findall(
                re.escape(selector) + r"(?:[^\n]*)\{([^}]*)\}", code
            )
            self.assertTrue(rules, selector + " has no rule to read")
            self.assertIn(
                f"var({token})", rules[0],
                f"{selector} does not read {token} ({why})",
            )

    def test_the_retargeted_boundary_is_the_one_the_product_measures(self):
        """`--line-2` on `--surface` was 1.50:1 light / 1.45:1 dark — half the
        3:1 a control boundary needs. The step that replaced it clears it in
        both themes, and the product's own gate already asserts the number; this
        is the site's copy of that claim."""
        for expected, site_sel, product_sel in (
            ("#868d95", ":root", '[data-theme="light"]'),
            ("#6a7178", '[data-theme="dark"]', '[data-theme="dark"]'),
        ):
            value = declared_value(SITE_CSS, site_sel, "--line-3")
            self.assertEqual(value, expected, "the site's step is not the product's")
            self.assertEqual(
                value, declared_value(CSS, product_sel, "--line-3"),
                "the site's control boundary drifted from the product's")


class AnExemptionMustBeADistinctStep(unittest.TestCase):
    """`UNREAD_ALLOWED` claims a token is a pending STEP.

    `--line-2` sat on that table for three iterations with a well-reasoned
    exemption and was never a step: it was byte-identical to `--mute-line` in
    both themes, so it was a second NAME for a colour the product already
    painted. No reader could have made it a step — only a different colour
    could. `check_design_tokens.check_exemptions_are_distinct_steps` is the
    check that says so, and it is empty on the shipped tree, so both tests here
    supply the exemption rather than reading one from the file.
    """

    def _gate(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "check_design_tokens_under_test", ROOT / "check_design_tokens.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _with_exemption(self, gate, css, token):
        original = gate.UNREAD_ALLOWED
        gate.UNREAD_ALLOWED = dict(original)
        gate.UNREAD_ALLOWED[token] = "injected by the test"
        try:
            failures = []
            gate.check_exemptions_are_distinct_steps(css, failures)
            return failures
        finally:
            gate.UNREAD_ALLOWED = original

    def _reinject_line2(self, colour="#ccd0d6", colour_dark="#31373e"):
        """Rebuild 9.1c's starting state: the token, in both themes, exempt."""
        css = CSS.replace("  --line-3: #868d95;",
                          f"  --line-2: {colour};\n  --line-3: #868d95;", 1)
        css = css.replace("  --line-3: #6a7178;",
                          f"  --line-2: {colour_dark};\n  --line-3: #6a7178;", 1)
        return css

    def test_an_exemption_that_repeats_a_read_colour_in_both_themes_fails(self):
        gate = self._gate()
        css = self._reinject_line2()
        self.assertIn("--line-2: #ccd0d6", css, "the injection did not land")
        failures = self._with_exemption(gate, css, "--line-2")
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("--mute-line", failures[0],
                      "the check must name the token whose value it repeats")

    def test_the_gate_actually_calls_it(self):
        """Deleting the call site leaves `check_design_tokens.py` exiting 0.

        Measured, not assumed: with `check_exemptions_are_distinct_steps(css,
        failures)` removed from `check_scale`, the gate still printed
        "DESIGN TOKENS OK" and exited 0 — because the shipped tree has **zero**
        exemptions, so a check with nothing to examine cannot fail on it. Every
        test in this class injects its own exemption and calls the function
        directly, which is what makes the check provable; it is exactly what
        makes the *call site* invisible to them. So the call site is asserted
        as structure, by parsing the module and looking for the call.

        The general shape: a gate wired to a corpus that does not yet contain
        the defect is not a gate until someone puts the defect in the corpus.
        """
        tree = ast.parse((ROOT / "check_design_tokens.py").read_text(encoding="utf-8"))
        called = {n.func.id for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertIn("check_exemptions_are_distinct_steps", called,
                      "the exemption check is defined but never called")

    def test_an_exemption_with_a_colour_of_its_own_passes(self):
        """The control. Without it, "the check fails" could mean the check
        fails on any exemption at all, and the gate would then be banning the
        table rather than reading it."""
        gate = self._gate()
        failures = self._with_exemption(gate, self._reinject_line2("#b0b6bd", "#3c434b"), "--line-2")
        self.assertEqual(failures, [], "a genuinely distinct pending step was rejected")

    def test_a_coincidence_in_one_theme_is_not_a_second_name(self):
        """`--mute-bg` IS `--surface-2` in both themes and that is deliberate —
        a muted block is a recessed surface. The check's claim is narrower: a
        duplicate in only ONE theme is a coincidence, and rejecting it would
        make the gate unadoptable."""
        gate = self._gate()
        # --mute-line matches --surface-2 in NEITHER theme, so reuse a colour
        # that does: match --mute-bg, which is #eceef0 / #1e2227.
        css = self._reinject_line2("#eceef0")
        failures = self._with_exemption(gate, css, "--line-2")
        self.assertEqual(failures, [], failures)

    def test_the_alias_of_a_duplicated_token_is_not_a_false_positive(self):
        """`--border-strong: var(--line-3)` is how the product says "the control
        step" without repeating a hex. An exempt token that ALIASES a read one
        is a deliberate restatement, not a second value — and the check has to
        be able to tell, or every future alias becomes a failure."""
        gate = self._gate()
        css = CSS.replace("  --border: var(--line);", "  --border: var(--line-2);")
        failures = self._with_exemption(gate, css, "--line-2")
        self.assertEqual(failures, [], failures)


class RequiredPaletteStepsAreReadOrNamed(unittest.TestCase):
    """`REQUIRED` says these steps exist. Existence is a claim a reader backs.

    9.1a left `--accent-line` and `--line-2` on an exemption table with the
    reason "9.1b", which is a promise, not a measurement. `--accent-line` was
    given its reader by 9.1b; `--line-2` was deleted by 9.1c, which measured
    it byte-identical to `--mute-line` in both themes and found every reader of
    it in `site/site.css`. The table is empty now, so the check below has
    nothing to examine — `AnExemptionMustBeADistinctStep` supplies it.
    """

    def _exemptions(self):
        src = (ROOT / "check_design_tokens.py").read_text(encoding="utf-8")
        table = src.split("UNREAD_ALLOWED = {", 1)[1].split("\n}", 1)[0]
        # entries are `"--token": "..."` — the key only, and the key is what the
        # table's own `stale` check compares against.
        return set(re.findall(r'^\s*"(--[\w-]+)":', table, re.M))

    def test_every_required_step_has_a_reader_or_a_named_exemption(self):
        code = strip_css_comments(CSS)
        exemptions = self._exemptions()
        for name in PALETTE:
            token = "--" + name
            self.assertIsNotNone(
                declared_value(CSS, ":root", token) or declared_value(CSS, '[data-theme="dark"]', token),
                token + " is in REQUIRED and declared in neither theme",
            )
            if f"var({token})" not in code:
                self.assertIn(token, exemptions, token + " is declared and never read")

    def test_an_exemption_naming_a_token_that_is_now_read_is_a_claim_about_a_file(self):
        """`check_unread_tokens` fails an exemption for a token that is no longer
        DECLARED. It does not fail one for a token that is declared and now read —
        which is exactly the state 9.1b created for `--accent-line` and left
        sitting in the table describing the opposite."""
        code = strip_css_comments(CSS)
        for token in sorted(self._exemptions()):
            self.assertNotIn(
                f"var({token})", code,
                token + " is exempt as unread and is now read; the exemption "
                        "describes a file that has stopped being true",
            )

    def test_the_product_and_the_landing_page_agree_on_the_accent_line_step(self):
        """One colour, stated once per theme in each stylesheet and once in
        DESIGN.md. 9.1b changed the value; these are what stop it drifting again."""
        for label, css, selector in (
            ("product light", CSS, '[data-theme="light"]'),
            ("site light", SITE_CSS, ":root"),
        ):
            self.assertEqual(declared_value(css, selector, "--accent-line"), "#92b7b6", label)
        for label, css in (("product dark", CSS), ("site dark", SITE_CSS)):
            self.assertEqual(
                declared_value(css, '[data-theme="dark"]', "--accent-line"), "#346464", label
            )
        doc = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn('accent-line: "#92b7b6"', doc)

    def test_the_palette_selects_with_the_named_token_not_a_mix(self):
        """The rule 9.1b rewrote. If it ever goes back to a `color-mix()` the
        token loses its only reader, which is the other assertion firing."""
        rules = re.findall(
            r"\.command-palette-option\[aria-selected=\"true\"\][^{]*\{([^}]*)\}", CSS
        )
        self.assertEqual(len(rules), 1, "the selected-option rule is not singular")
        self.assertIn("var(--accent-line)", rules[0])
        self.assertNotIn("color-mix", rules[0])


if __name__ == "__main__":
    unittest.main()