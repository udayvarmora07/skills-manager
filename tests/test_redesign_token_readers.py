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
    "line", "line-2", "line-3", "line-strong",
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


class RequiredPaletteStepsAreReadOrNamed(unittest.TestCase):
    """`REQUIRED` says these steps exist. Existence is a claim a reader backs.

    9.1a left `--accent-line` and `--line-2` on an exemption table with the
    reason "9.1b", which is a promise, not a measurement. `--accent-line` now
    has a reader; `--line-2` is still exempt, and its exemption says why.
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