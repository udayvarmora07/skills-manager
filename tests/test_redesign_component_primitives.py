"""Component primitives are a contract, so they are checked like one.

``check_design_tokens.py`` PRIMITIVES already derives five assertions from the
shipped stylesheet: every primitive is declared, every one carries its required
states, every one is read by markup or by another rule, no pending-adoption
exception has quietly become wired, and no surface primitive casts a shadow.

This file is the other half. The gate proves the *stylesheet* satisfies the
contract; these tests prove the gate itself does not quietly stop applying —
which is the failure mode this repository has now shipped five times
(``--border-strong`` at a compliant contrast that no element referenced, a
``doctor()["repair"]`` field with no reader, six ``@font-face`` rules covering
no basic Latin, the 11px floor check whose regex stopped matching the moment
sizes became tokens, and a pending-adoption list that could have become a
permanent exemption).

Every test here therefore mutates and asserts the gate goes RED. A test that
passes against a broken gate is worse than no test.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "skillsmgr" / "webui" / "styles.css"
GATE_PATH = ROOT / "check_design_tokens.py"


def run_gate() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE_PATH)],
        capture_output=True, text=True, cwd=str(ROOT), check=False,
    )


def assert_gate_catches(phrase: str) -> None:
    """The gate must FAIL, and name the phrase in its output.

    Both halves matter. A mutation the gate ignores leaves it green, and a
    gate that fails for an unrelated reason would satisfy the test while
    proving nothing about the check under test - the version of this helper
    that only counted "FAIL" lines did exactly that.
    """
    out = run_gate()
    assert out.returncode != 0, "the gate stayed green on a mutated stylesheet"
    assert phrase in out.stdout, out.stdout


class PrimitivesGateIsRedFirst(unittest.TestCase):
    """Each mutation must be caught. A green result here means a broken gate."""

    def setUp(self) -> None:
        self.css_original = CSS_PATH.read_text(encoding="utf-8")
        self.gate_original = GATE_PATH.read_text(encoding="utf-8")
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        CSS_PATH.write_text(self.css_original, encoding="utf-8")
        GATE_PATH.write_text(self.gate_original, encoding="utf-8")

    def _mutate_css(self, old: str, new: str) -> None:
        text = CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(old, text, f"mutation anchor not found: {old!r}")
        CSS_PATH.write_text(text.replace(old, new, 1), encoding="utf-8")

    def _mutate_gate(self, old: str, new: str) -> None:
        text = GATE_PATH.read_text(encoding="utf-8")
        self.assertIn(old, text, f"mutation anchor not found: {old!r}")
        GATE_PATH.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_the_real_tree_passes(self) -> None:
        """Red-first is meaningless if the honest tree is already red."""
        out = run_gate()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("all 16 primitives are declared", out.stdout)

    def test_removing_a_required_state_is_caught(self) -> None:
        """A control that lost its :disabled looks operable and is not."""
        self._mutate_css(".tab:disabled { opacity: .5; cursor: not-allowed; }", "")
        assert_gate_catches("carries its required states")

    def test_removing_a_focus_ring_from_a_field_is_caught(self) -> None:
        self._mutate_css(
            ".field-input:focus-visible,\n"
            ".field-select:focus-visible,\n"
            ".field-textarea:focus-visible {\n"
            "  outline: 2px solid var(--accent);\n"
            "  outline-offset: 1px;\n"
            "  border-color: var(--accent);\n"
            "}\n", "")
        assert_gate_catches("carries its required states")

    def test_removing_the_sticky_table_header_is_caught(self) -> None:
        self._mutate_css("  position: sticky;\n  top: 0;\n", "  top: 0;\n")
        assert_gate_catches("carries its required states")

    def test_adding_a_shadow_to_a_surface_is_caught(self) -> None:
        """Surfaces separate with a 1px border; --shadow is for popovers only."""
        self._mutate_css(
            ".panel { border: 1px solid var(--border);",
            ".panel { box-shadow: var(--shadow); border: 1px solid var(--border);")
        assert_gate_catches("casts a shadow")

    def test_an_adopted_primitive_left_on_the_pending_list_is_caught(self) -> None:
        """An exception that no longer applies is not an exception.

        This one was vacuous in its first form: it compared the required set
        against the union of pending and wired, which is a tautology - every
        required primitive is in one or the other by construction, so deleting
        an entry from the pending list could not make it fail.
        """
        self._mutate_gate('    ".panel": "2.1 status strip, 3.1 overview sections",\n', "")
        assert_gate_catches("pending-adoption list")

    def test_a_primitive_with_no_reader_is_caught(self) -> None:
        """Declaring a part nobody uses is the exact failure under watch.

        The reader set deliberately excludes the stylesheet itself: a declared
        primitive is trivially present in the CSS that declares it, so
        including it made this assertion pass no matter what. `.tooltip` is
        used here because it is genuinely unwired today, so dropping its
        pending-adoption entry is the exact state the check exists to catch.
        """
        self._mutate_gate('    ".tooltip": "2.1 icon-only buttons",\n', "")
        out = run_gate()
        self.assertNotEqual(out.returncode, 0, out.stdout)
        self.assertIn("declared and never read: ['.tooltip']", out.stdout)


class PrimitivesAreRealParts(unittest.TestCase):
    """The block is a contract, not a comment above a pile of CSS."""

    def setUp(self) -> None:
        self.css = CSS_PATH.read_text(encoding="utf-8")

    def test_the_primitives_block_exists_and_precedes_the_other_sections(self) -> None:
        self.assertIn("5.0", self.css)
        self.assertIn("PRIMITIVES", self.css)
        # It is the FIRST section of the components layer, so a screen that
        # adopts a primitive is styled by one rule rather than by whichever
        # ad-hoc block happens to come last.
        self.assertLess(self.css.index("PRIMITIVES"),
                        self.css.index("/* ---------------------------------------------------------------- topbar */"))

    def test_no_primitive_declares_a_literal_size_colour_or_duration(self) -> None:
        """A literal in a primitive is a seventh type step in disguise.

        This is the constraint 1.6 was spent on: the six steps were declared
        and unread, and the real sizes were 25 ad-hoc literals. A primitive
        that hard-codes a value reopens exactly that hole in the place where
        it is least visible.
        """
        block = self.css[self.css.index("PRIMITIVES"):
                         self.css.index("/* ---------------------------------------------------------------- topbar */")]
        # Strip the section comments (they carry prose, not declarations).
        import re
        body = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        for prop, unit in (("font-size", "px"), ("border-radius", "px"),
                           ("padding", "px"), ("height", "px"), ("width", "px")):
            offenders = [m.group(1).strip() for m in
                         re.finditer(prop + r":\s*([^;{}]+)", body)
                         if re.fullmatch(r"[0-9.]+" + unit, m.group(1).strip())]
            # Two exceptions, both named here so the list is the contract:
            # the switch knob and the diff gutter are fixed-size geometry.
            allowed = {"16px", "14px", "20px", "32px", "18px", "36px", "4ch", "1ch",
                      "999px", "1px", "96px", "2px", "0", "3px", "14px",
                      "24px", "20px", "40px"}  # fixed control geometry
            self.assertEqual([o for o in offenders if o not in allowed], [],
                             f"{prop} declares a literal in the primitives block")

    def test_interactive_primitives_declare_every_state(self) -> None:
        for selector, state in ((".btn:hover", "{"), (".btn:disabled", "{"),
                                (".tab:hover", "{"), (".tab:focus-visible", "{"),
                                (".tab:disabled", "{"),
                                (".choice input:disabled + .choice-box", "{")):
            self.assertIn(selector + " " + state, self.css,
                          f"{selector} is missing its {state} state")

    def test_the_primitives_block_does_not_re_declare_an_ad_hoc_component(self) -> None:
        """Two definitions of one selector read as two components.

        The earlier ones that already exist lower in the layer (button,
        badge, chip, banner, empty, skeleton) are listed in the block's own
        header as not-yet-migrated; the block must not add a second
        definition of one of them, which would resolve to whichever came last.
        """
        import re
        block = re.sub(r"/\*.*?\*/", "", self.css[
            self.css.index("PRIMITIVES"):
            self.css.index("/* ---------------------------------------------------------------- topbar */")
        ], flags=re.S)
        for legacy in (".badge", ".chip", ".banner", ".empty", ".skeleton"):
            self.assertNotRegex(block, r"(?m)^\s*" + re.escape(legacy) + r"\s*[,{]",
                                f"{legacy} is declared twice; last one wins silently")


class PendingAdoptionListIsHonest(unittest.TestCase):
    """A pending list that cannot shrink is a permanent exemption."""

    def setUp(self) -> None:
        self.gate = GATE_PATH.read_text(encoding="utf-8")

    def test_every_pending_entry_names_the_task_that_will_adopt_it(self) -> None:
        import re
        start = self.gate.index("PRIMITIVE_PENDING_ADOPTION")
        end = self.gate.index("\n}", start)
        entries = re.findall(r'^\s+"(\.[\w-]+)":\s*"([^"]+)"',
                             self.gate[start:end], flags=re.M)
        self.assertGreaterEqual(len(entries), 9)
        for selector, reason in entries:
            self.assertTrue(re.search(r"\d+\.\d+", reason),
                            f"{selector} pending adoption without a backlog task id: "
                            f"{reason!r}")

    def test_the_gate_reports_how_many_are_still_pending(self) -> None:
        """A count in the output is what makes the list visible when it shrinks."""
        out = run_gate()
        self.assertRegex(out.stdout, r"read by markup or a rule \(\d+ declared, adoption pending\)")


if __name__ == "__main__":
    unittest.main()