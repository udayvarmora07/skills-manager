"""DESIGN.md's Shell/Motion/Component numbers are the product's numbers.

`DESIGN.md` is the design contract and `check_design_tokens.py` compares its
palette against `skillsmgr/webui/styles.css`. Everything else it said about the
shell was prose, and the prose was wrong for the whole of this redesign:

- it drew a 240px rail while `--rail-w` said 240px and three layout tracks
  hard-coded 56px;
- it listed a "last scan" fact in the status bar, which the markup does not
  render and the API has no field for (no per-instance `updated_at`);
- it put the list pane at a fixed 392px when the track is a 320-380px range;
- it called the compact button 28px while `.btn-sm` is 26px;
- it said the budget meter axis "runs to 125%" when it is
  `max(125, ceil(peak / 25) * 25)`.

None of that was visible to a gate. A design contract is a claim about the
product, and a claim no check reads decays silently -- the same finding as the
dead `--rail-w`, one layer out. `check_doc_numbers()` therefore reads each
figure out of the file that owns it and requires it to appear in the contract.

Every test here is a mutation, because the property is only worth something if
it can fail: a green run from a probe that compares nothing is the failure mode
this repository has now recorded ten times.
"""

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "cdt_doc_numbers", ROOT / "check_design_tokens.py")
cdt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cdt)

CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")


def _root_map(css: str) -> dict:
    """Merge every ``:root`` block the way the gate does, for a given CSS text."""
    out: dict = {}
    for block in re.findall(r"(?m)^\s*:root\s*\{([^}]*)\}", css):
        for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;{}]+);", block):
            out.setdefault(m.group(1), m.group(2).strip())
    return out


def _mutate(old: str, new: str) -> str:
    """Replace exactly one occurrence and fail loudly if the text moved.

    A mutation that does not apply returns the original string and the test it
    guards passes vacuously. `sed '0,/min-height: 24px/'` matched the first of
    three occurrences once already; this asserts the anchor was unique.
    """
    assert CSS.count(old) == 1, f"mutation anchor is not unique: {old!r}"
    return CSS.replace(old, new)


class DocNumbersGate(unittest.TestCase):
    """The gate, on the shipped tree and on four mutations of it."""

    def _failures(self, css: str = CSS) -> list:
        return cdt.check_doc_numbers(css, _root_map(css))

    def test_the_shipped_tree_is_green(self):
        self.assertEqual([], self._failures())

    def test_the_derivation_actually_derives_something(self):
        """A control: the probe must find figures, not an empty set.

        Without this, every assertion below could pass because the gate found
        nothing to compare -- which is what happened to this repository's
        palette check when it looked tokens up without their `--` prefix and
        compared `None` with `None` nine times.
        """
        failures = self._failures()
        counted = int(re.search(r"(\d+) figure\(s\)", self._last_line()).group(1))
        self.assertGreaterEqual(counted, 10)
        self.assertEqual([], failures)

    def _last_line(self) -> str:
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._failures()
        return buf.getvalue()

    def test_a_widened_rail_fails(self):
        """The product moves; the contract must follow or the gate says so."""
        css = _mutate("  --rail-w: 56px;", "  --rail-w: 64px;")
        failures = self._failures(css)
        self.assertTrue(any("--rail-w" in f for f in failures), failures)

    def test_a_resized_compact_button_fails(self):
        css = _mutate(
            "padding: 2px 8px; font-size: var(--t-meta); height: 26px;",
            "padding: 2px 8px; font-size: var(--t-meta); height: 28px;")
        failures = self._failures(css)
        self.assertTrue(any(".btn-sm" in f for f in failures), failures)

    def test_a_new_duration_token_fails_until_the_contract_names_it(self):
        """Derived, not hand-listed: a fourth token must be named to pass."""
        css = _mutate("  --dur: 120ms;", "  --dur: 120ms;\n  --dur-skeleton: 140ms;")
        failures = self._failures(css)
        self.assertTrue(any("--dur-skeleton" in f for f in failures), failures)

    def test_a_contract_that_stops_naming_the_rail_fails(self):
        """The other direction: the document drifts and the gate catches it."""
        doc = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
        stale = doc.replace("`--rail-w` is 56px.", "a narrow icon rail.")
        self.assertNotEqual(doc, stale)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "DESIGN.md"
            path.write_text(stale, encoding="utf-8")
            original = cdt.DESIGN_MD
            cdt.DESIGN_MD = path
            try:
                failures = self._failures()
            finally:
                cdt.DESIGN_MD = original
        self.assertTrue(any("--rail-w" in f for f in failures), failures)

    def test_the_markup_half_finds_real_facts(self):
        """The status-bar facts are read from index.html, not remembered.

        Two of the three `.statusbar-fact` elements are interpolations, which
        are data rather than design claims, so they are stripped before the
        check. If the stripping ever swallowed a literal too, this fails.
        """
        markup = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")
        statics = [
            re.sub(r"\{\{[^}]*\}\}", "", m).strip()
            for m in re.findall(r'class="statusbar-fact"[^>]*>([^<>]*)<', markup)
        ]
        statics = [s for s in statics if s]
        self.assertIn("served", statics)
        self.assertIn("data stays on this machine", markup)
        doc = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
        for fact in statics:
            self.assertIn(fact, doc, f"DESIGN.md omits the status-bar fact {fact!r}")


if __name__ == "__main__":
    unittest.main()