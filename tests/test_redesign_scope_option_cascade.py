"""A shared ancestor's rule must not outrank the component's own rule.

Why this file exists
--------------------
Task 2.1 shipped a scope switcher whose options declared a two-row CSS grid.
``.scope-option`` (0,1,0) never rendered as that grid, because ``.menu button``
(0,1,1) sets ``display: flex`` and wins the cascade. Every option therefore
shipped as a single-line flex row in which the label and a 379px filesystem
path competed for about 150px of width; flex shrink is proportional to base
size, so the path won and each scope's name was cut to its initial --
"All… _ed root 103", "G… ~/.ger/skills/ 43".

Nothing in the repository failed. The class was declared, the template bound it,
the markup carried all four children, the option rendered, the count rendered,
the dot rendered, and the screenshot showed a control that looked finished.

What this asserts
-----------------
The one thing that would have caught it without a browser: for the elements a
component styles *inside* a shared container, the component's own rule has to
outrank the container's shared rule. Read over the real stylesheet through the
same tokenizer ``check_design_tokens.py`` uses, this is a cascade calculation,
not a string search -- the failure mode here was a *lower-specificity* rule, and
grepping for ``display: grid`` finds it happily in a file where it never applies.

The companion e2e assertions live in ``tests/e2e/test_scope_switcher.py``; that
directory is not collected by ``unittest discover``, so without this file the
suite CI runs would have no coverage of the defect at all.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from check_design_tokens import _skip_string

ROOT = Path(__file__).resolve().parents[1]
# Comments are removed before anything is parsed. A brace or a whole rule sitting
# inside a comment otherwise rides along in the next prelude and is scored as if
# it were a selector: an early version of this file read
# ``.scope-menu.is-up { ... }\n\n.scope-menu .scope-option`` as one selector,
# counted two classes in it, and so rated the broken tree ABOVE the container
# rule -- the mutation that reverts this very fix passed. The guard below fails
# that class of scan bug outright rather than letting it read as coverage.
_RAW_CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")
CSS = re.sub(r"/\*.*?\*/", "", _RAW_CSS, flags=re.S)

# The shared container the options live inside, and the component class they own.
CONTAINER = ".menu"
COMPONENT = ".scope-option"

_ID = re.compile(r"#[\w-]+")
_ATTR_OR_PSEUDO_CLASS = re.compile(r"\[[^\]]*\]|:[-\w]+")
_CLASS_OR_PSEUDO_ELEMENT = re.compile(r"\.[\w-]+|::[-\w]+")


def _subject_compound(selector: str) -> str:
    """The rightmost compound of a complex selector, ignoring combinators.

    ``.menu button:hover`` -> ``button:hover``. Only the subject can name the
    element itself; ``.menu`` is an ancestor and matches thousands of things
    that are not scope options.
    """
    for combinator in (" ", ">", "+", "~"):
        if combinator == " ":
            parts = selector.split()
        else:
            parts = [p for p in selector.split(combinator) if p.strip()]
        if len(parts) > 1:
            selector = parts[-1]
    return selector.strip()


def _specificity(selector: str) -> tuple[int, int, int]:
    """(ids, classes+attrs+pseudo-classes, types+pseudo-elements).

    Over the **whole** selector, not the subject compound. That distinction is
    the entire point of this file: ``.menu button`` scores (0,1,1) and a bare
    ``.scope-option`` scores (0,1,0), and reading only the subject would score
    the latter (0,1,0) against a (0,0,1) "container" -- so the comparison passes
    on the exact tree that carries the defect. ``_subject_compound`` decides
    *which* element a rule targets; this decides how that rule ranks.

    Anything it cannot classify sorts into the class bucket rather than being
    silently dropped, which can only make a comparison stricter than the real
    cascade, never looser.
    """
    pseudo_elements = len(re.findall(r"::[-\w]+", selector))
    classes = (
        len(re.findall(r"\.[\w-]+", selector))
        + len(_ATTR_OR_PSEUDO_CLASS.findall(selector))
        - pseudo_elements
    )
    types = len(re.findall(r"(?:^|[\s>+~])([a-zA-Z][\w-]*)", selector))
    return (len(_ID.findall(selector)), classes, types + pseudo_elements)


def _declarations(body: str) -> dict[str, str]:
    """Declarations of one rule body, comments and at-rule preludes removed."""
    stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    out: dict[str, str] = {}
    for chunk in stripped.split(";"):
        if ":" in chunk:
            prop, _, value = chunk.partition(":")
            name = prop.strip().lower()
            if re.fullmatch(r"-?[a-z][a-z0-9-]*", name):
                out.setdefault(name, value.strip())
    return out


def _rules() -> list[tuple[str, int, dict[str, str]]]:
    """Every top-level style rule as (raw selector list, line, declarations).

    Its own scan rather than ``css_rules``: that helper yields *normalised*
    selectors, which is what the duplicate check wants, but here the prelude text
    is re-parsed by ``_subject_compound``, so the raw form is what must be kept.
    Comments are already gone from ``CSS``; a naive ``css.split("{")`` still
    reads a brace inside a quoted content string as a rule boundary, which is
    how task 1.7's first four attempts "passed" vacuously.
    """
    rules: list[tuple[str, int, dict[str, str]]] = []
    i, n, line, start = 0, len(CSS), 1, 0
    while i < n:
        ch = CSS[i]
        if ch == "\n":
            line += 1
        elif ch in "\"'":
            i = _skip_string(CSS, i)
            continue
        elif ch == "{":
            prelude = CSS[start:i].strip()
            depth, end = 1, i + 1
            while depth and end < n:
                if CSS[end] == "{":
                    depth += 1
                elif CSS[end] == "}":
                    depth -= 1
                end += 1
            if not prelude.startswith("@") and prelude:
                rules.append((prelude, line, _declarations(CSS[i + 1 : end - 1])))
            line += CSS[i:end].count("\n")
            i = end
            start = end + 1
        i += 1
    return rules


class ScopeOptionCascadeTests(unittest.TestCase):
    """The scope option's own rule must outrank the shared menu rule."""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = _rules()

    def _owning_rules(self, component: str) -> list[tuple[str, int, str]]:
        """Rules whose *subject* is ``component`` and which declare a property."""
        out = []
        for selector, line, decls in self.rules:
            if _subject_compound(selector) == component and "display" in decls:
                out.append((selector, line, decls["display"]))
        return out

    def _shared_container_rule(self, container: str, element: str) -> tuple[str, int] | None:
        """The ``.menu button``-shaped rule: a container plus a bare element."""
        for selector, line, decls in self.rules:
            parts = selector.split()
            if len(parts) == 2 and parts[0] == container and parts[1] == element and "display" in decls:
                return (selector, line)
        return None

    def test_the_scan_never_returns_a_brace_inside_a_selector(self) -> None:
        """A prelude that still carries a brace means the scan lost its place.

        This is the meta-failure: a selector the scan fudged still gets scored,
        still gets compared, and can rate a broken tree above the rule it lost
        to. It produced a green mutation in the first version of this file, so
        it is asserted rather than trusted.
        """
        for selector, line, _decls in self.rules:
            self.assertNotIn("{", selector, f"line {line}: {selector!r}")
            self.assertNotIn("}", selector, f"line {line}: {selector!r}")
            self.assertNotIn("/*", selector, f"line {line}: {selector!r}")
        self.assertGreater(
            len(self.rules), 300,
            f"only {len(self.rules)} rules parsed from a {len(_RAW_CSS)}-byte "
            f"stylesheet; the scan is not reading the file",
        )

    def test_the_option_rule_exists_and_is_the_grid_it_claims_to_be(self) -> None:
        owning = self._owning_rules(COMPONENT)
        self.assertTrue(owning, f"no rule gives {COMPONENT} a display; the grid was deleted")
        self.assertEqual(
            [d for _s, _l, d in owning],
            ["grid"],
            f"{COMPONENT} must lay out as the grid it declares, not something else: {owning}",
        )

    def test_the_component_outranks_the_container_rule_it_renders_inside(self) -> None:
        shared = self._shared_container_rule(CONTAINER, "button")
        self.assertIsNotNone(shared, f"expected the shared {CONTAINER} <element> rule to exist")
        shared_selector, _shared_line = shared  # type: ignore[misc]
        own = min(_specificity(s) for s, _l, _d in self._owning_rules(COMPONENT))
        theirs = _specificity(shared_selector)
        self.assertGreater(
            own,
            theirs,
            f"{COMPONENT} scores {own} but {shared_selector} scores {theirs}, so the "
            f"shared container's display wins and {COMPONENT}'s own never applies",
        )

    def test_every_property_the_option_styles_is_not_shadowed_by_the_container(self) -> None:
        """The same fight applies to padding and radius, so assert the whole set.

        ``.menu button`` also sets ``padding`` and ``border-radius``; the
        screenshot that exposed the defect also showed the container's 8px/10px
        padding and its radius, not the component's. One property would have
        let the other two regress silently.
        """
        shared_decls = {}
        for selector, _line, decls in self.rules:
            if selector == f"{CONTAINER} button":
                shared_decls = decls
        self.assertTrue(shared_decls, f"expected the shared {CONTAINER} button rule")
        contested = {"display", "padding", "border-radius", "align-items", "gap"}
        for prop in sorted(contested & set(shared_decls)):
            mine = [
                _specificity(s)
                for s, _l, d in self._owning_rules(COMPONENT)
                if prop != "display" or d
            ]
            own_selectors = [s for s, _l, _d in self._owning_rules(COMPONENT)]
            if prop == "display":
                self.assertTrue(mine, "no display rule")
                self.assertGreater(min(mine), _specificity(f"{CONTAINER} button"), prop)
            else:
                # Anything the component declares for `prop` must outrank the
                # container; nothing else is asserted about properties the
                # component never claimed.
                if own_selectors:
                    self.assertGreater(min(mine), _specificity(f"{CONTAINER} button"), prop)

    def test_the_path_cannot_span_into_the_count_column(self) -> None:
        """A spanning grid item feeds its max-content to every track it spans.

        ``grid-template-areas: "dot label count" ". path path"`` put the path in
        the ``auto`` count column as well, so the count column grew to a share of
        a 379px string and the ``1fr`` label track got what was left -- zero. The
        label must not be able to lose its width to the path, and the only
        structural expression of that is the path staying in one track.
        """
        areas = [
            decls["grid-template-areas"]
            for selector, _line, decls in self.rules
            if _subject_compound(selector) == COMPONENT
            and "grid-template-areas" in decls
        ]
        self.assertTrue(areas, "the option no longer declares grid-template-areas")
        for value in areas:
            rows = [row.split() for row in value.split('"') if row.strip()]
            self.assertEqual(len(rows), 2, f"expected a two-row option, got {value!r}")
            for index, cell in enumerate(rows[1]):
                if cell == "path":
                    # Column 0 is the dot, column 1 the label, column 2 the
                    # count. The path may sit only under the label.
                    self.assertEqual(
                        index, 1,
                        f"the path spans into column {index} of {value!r}; a spanning "
                        f"grid item contributes its max-content to every track it spans, "
                        f"which is what starved the label",
                    )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()