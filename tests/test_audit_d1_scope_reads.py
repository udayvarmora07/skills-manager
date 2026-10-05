"""Red-first contracts for the agent-scope half of the primary read path.

``scopes.list_all()`` -- what ``GET /api/skills?scope=all`` and the web UI's
default Library view call -- re-read, re-parsed and re-hashed every document in
every agent scope on every request.  At the measured size of one developer's
machine (~2,000 rows across seven roots) that was the same O(n) full-document
cost the global half had just paid, and the agent half had four pieces of work
with no behavioural contract behind them:

* ``scan_scope`` re-derived a path per row that ``scan_dir`` had already
  validated -- re-resolving the scope base and re-running the name and
  containment checks, once per skill, per request.
* ``scan_dir`` asked pathlib to recompute the relative parts of every candidate
  whose relative parts are, for a direct child, just its own name.
* ``load_skill`` re-stat'ed both document names after the read had already
  established which one exists, because ``conflicting_documents`` answered the
  same question from scratch.
* a recursive root was traversed twice per scan, once per document name.

The first four tests in each class are **red-first**: they fail against the
pre-fix source, which is what makes them evidence rather than decoration.  The
rest pin the equivalence this change depends on -- that every record still
carries the same keys and values, that the physical-root dedupe and the
instance-state vocabulary are untouched, and that the drift rows (undecodable,
unreadable, link-escaping, unaddressable) are still reported.

Stdlib only.  Real scope roots with real symlinks; no mocks of the product,
only of the syscall/``pathlib`` seams whose call counts *are* the contract.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skillsmgr.paths as paths_module
from skillsmgr import loader, scopes
from skillsmgr.store import Store

_DOCUMENT_NAMES = {"SKILL.md", "SKILL.md.disabled"}


class ScopeReadCase(unittest.TestCase):
    """Base: fresh HOME + data root per test, no environment leakage."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self._old = {key: os.environ.get(key) for key in ("HOME", "SKILLS_MANAGER_DATA")}
        os.environ["HOME"] = str(self.home)
        os.environ["SKILLS_MANAGER_DATA"] = str(self.base / "data")
        scopes.set_global_store(None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        scopes.set_global_store(None)
        for key, old in self._old.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    @staticmethod
    def _document(name: str, description: str = "A skill for tests.") -> str:
        return f"---\nname: {name}\ndescription: {description}\n---\nbody of {name}\n"

    def _skill(self, directory: Path, name: str, *, disabled: bool = False) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        filename = "SKILL.md.disabled" if disabled else "SKILL.md"
        (directory / filename).write_text(self._document(name), encoding="utf-8")
        return directory

    def _flat_root(self, scope_id: str = "gemini") -> Path:
        return scopes._scope_by_id(scope_id).base

    def _recursive_root(self, scope_id: str = "agents") -> Path:
        return scopes._scope_by_id(scope_id).base

    def _seed_flat(self, count: int = 4, scope_id: str = "gemini") -> Path:
        root = self._flat_root(scope_id)
        for index in range(count):
            self._skill(root / f"flat-{index}", f"flat-{index}")
        return root

    def _seed_recursive(self, scope_id: str = "agents") -> Path:
        root = self._recursive_root(scope_id)
        for index in range(3):
            self._skill(root / f"top-{index}", f"top-{index}")
        for index in range(2):
            self._skill(root / "apps" / "web" / f"nested-{index}", f"nested-{index}")
        self._skill(root / "apps" / "web" / "parked", "parked", disabled=True)
        return root

    def _counting(self, target, attribute: str, match, *, only_project_frames: bool = False):
        """Patch ``target.<attribute>`` and record the calls ``match`` accepts.

        The wrapper always delegates to the real method, so patching cannot
        change behaviour -- only what gets counted.

        ``only_project_frames`` counts a call only when the *immediate caller*
        is our own code.  That is required when patching a stdlib method: on
        Python < 3.12 ``Path.is_relative_to()`` is implemented as
        ``self.relative_to(*other)``, so a bare patch counts pathlib's own
        internal and a test asserting "we do not call relative_to" fails on
        3.10/3.11 while passing on 3.12+ -- the code it claims to police is
        identical on every version.  A cost assertion that depends on which
        interpreter is running is not a contract; this makes it one.
        """
        real = getattr(target, attribute)
        seen: list[str] = []

        def wrapper(self, *args, **kwargs):
            if only_project_frames and not _called_from_project_code():
                return real(self, *args, **kwargs)
            if match(self, *args, **kwargs):
                seen.append(str(self))
            return real(self, *args, **kwargs)

        return mock.patch.object(target, attribute, wrapper), seen


_PROJECT_DIR_MARKERS = ("skillsmgr/", "skillsmgr\\")


def _called_from_project_code() -> bool:
    """Whether the immediate caller is this project's code rather than the stdlib."""
    filename = sys._getframe(2).f_code.co_filename
    return any(marker in filename for marker in _PROJECT_DIR_MARKERS)


# --------------------------------------------------------------- scan_scope


class MergedScanDoesNotRederivePathsTests(ScopeReadCase):
    """``scan_scope`` must not rebuild a path the scan already validated."""

    def test_a_flat_scope_scan_never_re_derives_a_validated_path(self):
        """RED-FIRST: pre-fix this called ``contained_entry`` once per row."""
        self._seed_flat(4)
        patcher, seen = self._counting(
            paths_module, "contained_entry", lambda self, *a, **k: True
        )
        with patcher:
            rows = scopes.scan_scope("gemini")
        self.assertEqual(4, len(rows))
        self.assertEqual(
            [], seen, "scan_scope re-derived a path scan_dir had already validated"
        )

    def test_a_recursive_scope_scan_never_re_derives_a_validated_path(self):
        self._seed_recursive()
        patcher, seen = self._counting(
            paths_module, "contained_entry", lambda self, *a, **k: True
        )
        with patcher:
            rows = scopes.scan_scope("agents")
        self.assertTrue(rows)
        self.assertEqual([], seen)

    def test_the_merged_list_never_re_derives_a_validated_path(self):
        self._seed_flat(3)
        self._seed_recursive()
        patcher, seen = self._counting(
            paths_module, "contained_entry", lambda self, *a, **k: True
        )
        with patcher:
            rows = scopes.list_all()
        self.assertTrue(rows)
        self.assertEqual([], seen)


class ScanScopePathValueTests(ScopeReadCase):
    """The value the scan hands over must be the value the old code derived."""

    def test_a_flat_row_reports_the_contained_entry_under_the_resolved_root(self):
        self._seed_flat(3)
        scope = scopes._scope_by_id("gemini")
        resolved = scopes._resolved_scope_root(scope)
        for row in scopes.scan_scope("gemini"):
            self.assertEqual(str(resolved / row["name"]), row["path"])
            self.assertEqual(str(Path(row["path"]).resolve()), row["physical_path"])
            # And the pre-fix expression the annotation loop used to evaluate.
            self.assertEqual(
                str(paths_module.contained_entry(scope.base, row["name"])), row["path"]
            )

    def test_a_symlinked_scope_base_still_reports_the_resolved_base(self):
        """The scan's own entry is used, not the raw enumerating path.

        ``scan_dir`` enumerates under the unresolved base, so ``str(child)``
        would carry the symlinked spelling while every pre-fix record carried the
        resolved one.  This is the assertion that makes handing the validated
        entry over safe.
        """
        real = self.home / "real-gemini"
        (real / "skills").mkdir(parents=True)
        (real / "skills" / "linked").mkdir()
        (real / "skills" / "linked" / "SKILL.md").write_text(
            self._document("linked"), encoding="utf-8"
        )
        (self.home / ".gemini").symlink_to(real, target_is_directory=True)
        scope = scopes._scope_by_id("gemini")
        rows = scopes.scan_scope("gemini")
        self.assertEqual(1, len(rows))
        resolved = scopes._resolved_scope_root(scope)
        self.assertNotEqual(str(scope.base / "linked"), rows[0]["path"])
        self.assertEqual(str(resolved / "linked"), rows[0]["path"])
        self.assertEqual(str(resolved / "linked"), rows[0]["physical_path"])


# ------------------------------------------------------------------ scan_dir


class ScanDirWalkCostTests(ScopeReadCase):
    """The per-candidate work a scan does before it loads a document."""

    def test_a_flat_scan_does_not_recompute_relative_parts_per_candidate(self):
        """RED-FIRST: pre-fix this called ``Path.relative_to`` once per row."""
        root = self._seed_flat(5)
        patcher, seen = self._counting(
            pathlib.Path, "relative_to", lambda self, *a, **k: True, only_project_frames=True
        )
        with patcher:
            rows = loader.scan_dir(root)
        self.assertEqual(5, len(rows))
        self.assertEqual([], seen, "a direct child's relative parts are its own name")

    def test_a_recursive_scan_traverses_the_root_once(self):
        """RED-FIRST: pre-fix this walked the tree once per document name."""
        root = self._seed_recursive()
        patcher, seen = self._counting(
            pathlib.Path, "rglob", lambda self, *a, **k: True, only_project_frames=True
        )
        with patcher:
            rows = loader.scan_dir(root, recursive=True)
        self.assertEqual(6, len(rows))
        self.assertEqual(
            1, len(seen), f"one walk must find both document names; walked {seen}"
        )

    def test_a_recursive_scan_still_finds_every_document(self):
        """The single walk must select the same candidates as two name walks."""
        root = self._seed_recursive()
        expected = sorted(
            {p.parent for p in root.rglob("SKILL.md")}
            | {p.parent for p in root.rglob("SKILL.md.disabled")}
        )
        rows = loader.scan_dir(root, recursive=True)
        self.assertEqual([str(p) for p in expected], sorted(r["path"] for r in rows))
        self.assertEqual(
            {"nested-0", "nested-1", "parked", "top-0", "top-1", "top-2"},
            {r["name"] for r in rows},
        )
        self.assertEqual([1], [r["disabled"] for r in rows if r["name"] == "parked"])


class ScanDirRecordShapeTests(ScopeReadCase):
    """``annotate_paths`` is opt-in; every other caller is unaffected."""

    def test_the_default_flat_scan_still_carries_no_path(self):
        """``effective``, ``cli_handlers`` and the web route read these records."""
        root = self._seed_flat(3)
        rows = loader.scan_dir(root)
        self.assertTrue(rows)
        for row in rows:
            self.assertNotIn("path", row)

    def test_the_default_recursive_scan_still_reports_the_enumerating_path(self):
        """A recursive record keeps ``str(child)``, which is *not* the resolved base.

        Only a symlinked scope base makes the two spellings differ, which is the
        case the annotated flat record must keep matching.
        """
        real = self.home / "real-agents"
        (real / "skills").mkdir(parents=True)
        self._skill(real / "skills" / "one", "one")
        self._skill(real / "skills" / "apps" / "web" / "two", "two")
        (self.home / ".agents").symlink_to(real, target_is_directory=True)
        root = scopes._scope_by_id("agents").base
        resolved = root.resolve()
        self.assertNotEqual(str(root), str(resolved))
        rows = loader.scan_dir(root, recursive=True)
        self.assertEqual(2, len(rows))
        for row in rows:
            self.assertTrue(str(row["path"]).startswith(str(root)))
            self.assertFalse(str(row["path"]).startswith(str(resolved)))

    def test_annotate_paths_records_the_validated_entry_on_flat_rows(self):
        root = self._seed_flat(3)
        resolved = root.resolve()
        rows = loader.scan_dir(root, annotate_paths=True)
        self.assertEqual(3, len(rows))
        for row in rows:
            self.assertEqual(str(resolved / row["name"]), row["path"])

    def test_annotate_paths_is_off_by_default(self):
        import inspect

        default = inspect.signature(loader.scan_dir).parameters["annotate_paths"].default
        self.assertIs(False, default)


# -------------------------------------------------------------------- loader


class DocumentProbeTests(ScopeReadCase):
    """The read establishes which document exists; the conflict check reuses it."""

    def test_an_active_document_is_not_stat_ed_twice(self):
        """RED-FIRST: pre-fix ``conflicting_documents`` re-stat'ed both names."""
        skill = self._skill(self.base / "skills" / "one", "one")
        patcher, seen = self._counting(
            pathlib.Path, "is_file", lambda self, *a, **k: self.name in _DOCUMENT_NAMES, only_project_frames=True
        )
        with patcher:
            record = loader.load_skill(skill)
        self.assertFalse(record["malformed"])
        self.assertLessEqual(
            len(seen),
            2,
            f"one read plus one conflict probe is enough; stat'ed {seen}",
        )

    def test_read_skill_or_report_keeps_its_three_value_contract(self):
        skill = self._skill(self.base / "skills" / "one", "one")
        result = loader.read_skill_or_report(skill)
        self.assertEqual(3, len(result))
        text, disabled, read_error = result
        self.assertIn("name: one", text)
        self.assertEqual(0, disabled)
        self.assertIsNone(read_error)

    def test_the_conflicting_document_state_is_still_reported(self):
        """All four presence combinations, through both the helper and the record."""
        cases = {
            "active-only": (("SKILL.md",), False, 0),
            "disabled-only": (("SKILL.md.disabled",), False, 1),
            "both": (("SKILL.md", "SKILL.md.disabled"), True, 0),
            "neither": ((), False, 0),
        }
        for label, (names, expected_conflict, expected_disabled) in cases.items():
            with self.subTest(case=label):
                skill = self.base / "skills" / label
                skill.mkdir(parents=True)
                for name in names:
                    (skill / name).write_text(self._document("one"), encoding="utf-8")
                self.assertEqual(
                    expected_conflict, loader.conflicting_documents(skill)
                )
                self.assertEqual(
                    expected_disabled, loader.read_skill_or_report(skill)[1]
                )
                if not names:
                    from skillsmgr.store import SkillNotFound

                    with self.assertRaises(SkillNotFound):
                        loader.load_skill(skill)
                    continue
                record = loader.load_skill(skill)
                self.assertEqual(expected_conflict, record["document_conflict"])
                self.assertEqual(expected_conflict, record["malformed"])
                self.assertEqual(expected_disabled, record["disabled"])

    def test_a_disabled_only_document_is_read_and_not_a_conflict(self):
        skill = self._skill(self.base / "skills" / "parked", "parked", disabled=True)
        self.assertFalse(loader.conflicting_documents(skill))
        record = loader.load_skill(skill)
        self.assertEqual(1, record["disabled"])
        self.assertFalse(record["document_conflict"])
        self.assertFalse(record["malformed"])

    def test_a_directory_with_no_document_still_raises_skill_not_found(self):
        from skillsmgr.store import SkillNotFound

        empty = self.base / "skills" / "empty"
        empty.mkdir(parents=True)
        self.assertIsNone(loader.read_skill_or_report(empty)[0])
        with self.assertRaises(SkillNotFound):
            loader.load_skill(empty)
        self.assertTrue(loader.load_skill(empty, include_husks=True)["document_missing"])

    def test_an_undecodable_document_is_still_reported_rather_than_raised(self):
        skill = self.base / "skills" / "latin"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_bytes(b"---\nname: latin\ndescription: caf\xe9\n---\n")
        record = loader.load_skill(skill)
        self.assertTrue(record["malformed"])
        self.assertIn("not valid UTF-8", record["decode_error"])
        self.assertEqual("", record["description"])

    @unittest.skipIf(os.getuid() == 0, "root ignores the permission bits under test")
    def test_an_unreadable_document_is_still_reported_as_drift(self):
        skill = self._skill(self.base / "skills" / "locked", "locked")
        os.chmod(skill, 0o000)
        self.addCleanup(os.chmod, skill, 0o700)
        record = loader.load_skill(skill)
        self.assertTrue(record["malformed"])
        self.assertTrue(record["decode_error"])
        self.assertEqual("", record["body"])


class ScopeReadDriftTests(ScopeReadCase):
    """Drift rows the aggregate views depend on stay visible."""

    def test_an_unaddressable_name_is_still_listed_and_marked(self):
        root = self._flat_root()
        (root / "Upper-Case").mkdir(parents=True)
        (root / "Upper-Case" / "SKILL.md").write_text(
            self._document("Upper-Case"), encoding="utf-8"
        )
        rows = {r["name"]: r for r in scopes.scan_scope("gemini")}
        self.assertIn("Upper-Case", rows)
        row = rows["Upper-Case"]
        self.assertFalse(row["addressable"])
        self.assertIn("unaddressable", row["instance_states"])
        self.assertEqual(str(root.resolve() / "Upper-Case"), row["path"])

    def test_a_skill_linking_out_of_its_scope_is_still_reported_as_drift(self):
        """SCOPE-2: the entry stays visible instead of vanishing from the view."""
        root = self._flat_root("gemini")
        root.mkdir(parents=True, exist_ok=True)
        outside = self.base / "outside" / "escaped"
        outside.mkdir(parents=True)
        (outside / "SKILL.md").write_text(self._document("escaped"), encoding="utf-8")
        (root / "escaped").symlink_to(outside, target_is_directory=True)
        rows = {r["name"]: r for r in scopes.scan_scope("gemini")}
        self.assertIn("escaped", rows)
        row = rows["escaped"]
        self.assertTrue(row.get("link_escape"))
        self.assertTrue(row["malformed"])
        self.assertIn("invalid", row["instance_states"])
        self.assertEqual(str(root / "escaped"), row["path"])

    def test_same_name_instances_in_one_recursive_scope_are_both_listed(self):
        """SCOPE-11: the merge dedupes on the path, not on (scope, name)."""
        root = self._recursive_root("agents")
        self._skill(root / "apps" / "web" / "twin", "one")
        self._skill(root / "apps" / "other" / "twin", "a different description")
        rows = [r for r in scopes.list_all() if r["name"] == "twin"]
        self.assertEqual(2, len(rows))
        self.assertEqual(2, len({r["path"] for r in rows}))
        for row in rows:
            self.assertIn("duplicated", row["instance_states"])
            self.assertEqual("unresolved", row["effective_state"])


class StoreScopeReadUnchangedTests(ScopeReadCase):
    """The aggregate shape other routes assert on is untouched."""

    def test_a_scope_row_keeps_its_documented_fields(self):
        self._seed_flat(2)
        row = scopes.scan_scope("gemini")[0]
        for field in (
            "name", "scope", "scope_label", "path", "physical_root", "physical_path",
            "status", "description", "body", "category", "tokens", "tokens_method",
            "tokens_pct", "chars", "root_availability", "discovery_recursive",
            "consumer", "content_hash", "metadata_hash", "provenance",
            "portable_frontmatter", "frontmatter_extensions", "malformed",
            "addressable", "disabled", "document_missing", "decode_error",
            "document_conflict", "missing_required", "instance_states",
            "instance_state", "effective_state",
        ):
            self.assertIn(field, row)

    def test_the_global_scope_half_is_unaffected(self):
        store = Store()
        store.init_db()
        store.create("global-one", "A global skill for the read path tests.")
        scopes.set_global_store(store)
        row = scopes.scan_scope("global")[0]
        self.assertEqual("global", row["scope"])
        self.assertEqual("skills-manager", row["consumer"])
        self.assertTrue(row["tokens"] > 0)
        self.assertEqual(
            ["global-one"], [r["name"] for r in scopes.list_all()]
        )


if __name__ == "__main__":
    unittest.main()