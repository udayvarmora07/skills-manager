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

import contextlib
import copy
import datetime
import os
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skillsmgr.paths as paths_module
from skillsmgr import loader, observations, scopes
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

# ------------------------------------------------- content-addressed reuse
#
# The second half of docs/24 §D1.  Within ONE ``list_all()`` call every
# document is derived exactly once (measured: 1.00 derivations per row, per
# request), so the audit's "scoped to one request" cache would have bought a
# cold request nothing at all.  The reuse therefore has to live in the process,
# keyed on the bytes rather than on ``(mtime_ns, size)``:
#
# * a repeat request re-derives nothing (red-first below);
# * a cold request re-derives everything, exactly as before;
# * the filesystem stays authoritative, because the key is the *content
#   hash* -- not the size, not the mtime.  ``test_a_same_size_edit_with_a
#   restored_mtime_is_still_observed`` forces the strongest form of that:
#   identical byte count AND identical mtime_ns, so only a content-derived key
#   can possibly see the change.


class DocumentReuseWarmTests(ScopeReadCase):
    """A repeat request must not re-derive documents it already derived."""

    def _derived_calls(self, run):
        """Count ``loader.parse_frontmatter`` calls made by *run*."""
        real = loader.parse_frontmatter
        seen: list[str] = []

        def counting(text):
            seen.append(text[:40])
            return real(text)

        with mock.patch.object(loader, "parse_frontmatter", counting):
            rows = run()
        return rows, seen

    def test_a_warm_repeated_merged_read_re_derives_no_document(self):
        """RED-FIRST: pre-fix the second request re-parsed every document."""
        self._seed_flat(4)
        self._seed_recursive()
        rows1, first = self._derived_calls(scopes.list_all)
        rows2, second = self._derived_calls(scopes.list_all)
        self.assertTrue(rows1)
        self.assertEqual(len(rows1), len(rows2))
        self.assertEqual(len(rows1), len(first), "one derivation per row, per request")
        self.assertEqual([], second, "a warm request re-parsed every document")

    def test_a_warm_repeated_single_scope_read_re_derives_no_document(self):
        """RED-FIRST: the same reuse must reach ``GET /api/skills?scope=…``."""
        self._seed_flat(5)
        self._derived_calls(lambda: scopes.scan_scope("gemini"))
        _, second = self._derived_calls(lambda: scopes.scan_scope("gemini"))
        self.assertEqual([], second)

    def test_the_first_request_still_derives_every_document(self):
        """A cold request gains nothing and loses nothing: no cold fast path."""
        self._seed_flat(4)
        self._seed_recursive()
        _, first = self._derived_calls(scopes.list_all)
        self.assertTrue(first)

    def test_the_cache_is_bounded(self):
        """An unbounded cache in a long-lived web UI process is a leak.

        Driven through ``load_skill`` rather than ``scan_dir``: a scan larger
        than the bound now turns reuse *off* (see
        :class:`ReuseAboveTheBoundTests`), which would make an assertion about
        the eviction loop pass without ever exercising it.
        """
        loader.clear_document_cache()
        self.addCleanup(loader.clear_document_cache)
        root = self._seed_flat(12)
        documents = sorted(p for p in root.iterdir() if p.is_dir())
        self.assertEqual(12, len(documents))
        with mock.patch.object(loader, "MAX_DOCUMENT_CACHE", 5):
            for skill_dir in documents:
                loader.load_skill(skill_dir)
            self.assertEqual(5, loader.document_cache_size())
            for skill_dir in documents:
                loader.load_skill(skill_dir)
            self.assertEqual(5, loader.document_cache_size())
        # With the bound restored the same twelve all fit again.
        loader.clear_document_cache()
        for skill_dir in documents:
            loader.load_skill(skill_dir)
        self.assertEqual(12, loader.document_cache_size())


class DocumentReuseAuthoritativenessTests(ScopeReadCase):
    """The filesystem must stay the source of truth through the reuse."""

    def setUp(self):
        super().setUp()
        loader.clear_document_cache()
        self.addCleanup(loader.clear_document_cache)

    def test_a_same_size_edit_with_a_restored_mtime_is_still_observed(self):
        """The hard requirement, in its strongest form.

        Same byte count, and the mtime restored to the nanosecond, so a cache
        keyed on ``(mtime_ns, size)`` -- the shape the audit recommended -- is
        blind to this by construction.  Only a content-derived key passes.
        """
        skill = self._skill(self.base / "skills" / "mutate", "mutate")
        document = skill / "SKILL.md"
        scopes.list_all()  # warm whatever there is to warm
        loader.load_skill(skill)
        before = document.stat()
        original = document.read_text(encoding="utf-8")
        # "A skill for tests." -> "B skill for testz." : same length, new bytes.
        edited = original.replace("A skill for tests.", "B skill for testz.")
        self.assertEqual(len(original), len(edited))
        document.write_text(edited, encoding="utf-8")
        os.utime(document, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = document.stat()
        self.assertEqual(before.st_size, after.st_size)
        self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)
        record = loader.load_skill(skill)
        self.assertEqual("B skill for testz.", record["description"])

    def test_a_same_size_edit_is_observed_through_the_merged_view(self):
        root = self._flat_root()
        skill = self._skill(root / "mutate", "mutate")
        scopes.list_all()
        document = skill / "SKILL.md"
        before = document.stat()
        edited = document.read_text(encoding="utf-8").replace(
            "A skill for tests.", "B skill for testz."
        )
        document.write_text(edited, encoding="utf-8")
        os.utime(document, ns=(before.st_atime_ns, before.st_mtime_ns))
        rows = {r["name"]: r for r in scopes.list_all()}
        self.assertEqual("B skill for testz.", rows["mutate"]["description"])
        # And the derived content hash moved with it.
        self.assertNotEqual(
            loader.load_skill(skill)["description"], "A skill for tests."
        )

    def test_a_deleted_document_is_not_served_from_the_cache(self):
        from skillsmgr.store import SkillNotFound

        skill = self._skill(self.base / "skills" / "gone", "gone")
        self.assertFalse(loader.load_skill(skill)["malformed"])
        (skill / "SKILL.md").unlink()
        with self.assertRaises(SkillNotFound):
            loader.load_skill(skill)

    def test_a_second_document_appearing_after_the_cache_is_warm_is_reported(self):
        """The conflict flag is a filesystem fact, not a content fact.

        Both documents may hold *identical bytes*, so a cache keyed only on the
        document content would keep reporting ``document_conflict: False`` for a
        directory that would have its second document destroyed by the next
        toggle (STORE-3/SCOPE-13).
        """
        skill = self._skill(self.base / "skills" / "twin", "twin")
        self.assertFalse(loader.load_skill(skill)["document_conflict"])
        (skill / "SKILL.md.disabled").write_bytes((skill / "SKILL.md").read_bytes())
        record = loader.load_skill(skill)
        self.assertTrue(record["document_conflict"])
        self.assertTrue(record["malformed"])

    def test_toggling_the_document_name_after_the_cache_is_warm_is_observed(self):
        """``SKILL.md`` and ``SKILL.md.disabled`` may hold identical bytes."""
        skill = self._skill(self.base / "skills" / "parked", "parked")
        self.assertEqual(0, loader.load_skill(skill)["disabled"])
        (skill / "SKILL.md").rename(skill / "SKILL.md.disabled")
        record = loader.load_skill(skill)
        self.assertEqual(1, record["disabled"])
        self.assertFalse(record["document_conflict"])

    def test_two_reads_never_share_a_record_or_its_nested_dictionaries(self):
        """``scopes.scan_scope`` writes ``record["provenance"]["scope"]``."""
        skill = self._skill(self.base / "skills" / "one", "one")
        first = loader.load_skill(skill)
        second = loader.load_skill(skill)
        self.assertIsNot(first, second)
        self.assertIsNot(first["provenance"], second["provenance"])
        first["provenance"]["scope"] = "tampered"
        first["portable_frontmatter"]["description"] = "tampered"
        first["frontmatter_extensions"]["injected"] = "tampered"
        self.assertNotEqual("tampered", second["provenance"]["scope"])
        self.assertNotEqual("tampered", second["portable_frontmatter"]["description"])
        self.assertNotIn("injected", second["frontmatter_extensions"])
        third = loader.load_skill(skill)
        self.assertIsNone(third["provenance"]["scope"])
        self.assertNotEqual("tampered", third["portable_frontmatter"]["description"])

    def test_a_hit_hands_out_a_record_the_cache_never_sees_again(self):
        """The hazard the copy on *lookup* exists for.

        A caller annotating a reused record -- ``scopes.scan_scope`` writes
        ``provenance["scope"]``, ``Store`` writes ``"global"`` -- must not be
        able to turn its own annotation into the next request's fact.  Only a
        record that came *out* of the cache exercises this; the miss path
        already returns a fresh object.
        """
        skill = self._skill(self.base / "skills" / "one", "one")
        warm = loader.load_skill(skill)  # miss
        self.assertEqual("one", warm["portable_frontmatter"]["name"])
        warm["provenance"]["scope"] = "gemini"
        warm["portable_frontmatter"]["name"] = "hijacked"
        warm["name"] = "hijacked"
        warm["malformed"] = True
        again = loader.load_skill(skill)  # hit
        self.assertIsNot(again, warm)
        self.assertEqual("one", again["name"])
        self.assertIsNone(again["provenance"]["scope"])
        self.assertEqual("one", again["portable_frontmatter"]["name"])
        self.assertFalse(again["malformed"])
        # And the object a *hit* hands out is itself a copy: annotating it must
        # not become the next hit's starting state either.
        again["provenance"]["scope"] = "gemini"
        again["portable_frontmatter"]["name"] = "hijacked"
        third = loader.load_skill(skill)
        self.assertIsNone(third["provenance"]["scope"])
        self.assertEqual("one", third["portable_frontmatter"]["name"])

    def test_two_undecodable_documents_sharing_replacement_text_stay_distinct(self):
        """The decode reason is a fact about the bytes, not about the lossy text.

        ``read_skill_text`` keeps an undecodable document readable by replacing
        the bad byte with U+FFFD, so two *different* invalid sequences render as
        the same string -- and therefore hash to the same key.  Only the decode
        reason separates them, and it names the offending byte value, so reuse
        without it would report the first document's ``0xe9`` for the second's
        ``0xe8``.
        """
        skill = self.base / "skills" / "latin"
        skill.mkdir(parents=True)
        document = skill / "SKILL.md"
        lossy: dict[str, str] = {}
        for bad in (b"\xe9", b"\xe8"):
            document.write_bytes(
                b"---\nname: latin\ndescription: caf" + bad + b"\n---\n"
            )
            lossy[bad.hex()] = loader.read_skill_text(document)[0]
            record = loader.load_skill(skill)
            self.assertTrue(record["malformed"], bad)
            self.assertIn(f"0x{bad.hex()}", record["decode_error"])
            # The second read of the same bytes must agree.
            self.assertIn(f"0x{bad.hex()}", loader.load_skill(skill)["decode_error"])
        # The premise: two different invalid sequences render identically, so the
        # content hash cannot tell them apart and the decode reason must.
        self.assertEqual(lossy["e9"], lossy["e8"])

    def test_the_record_reports_the_spelling_the_caller_addressed(self):
        """``provenance.path`` is the caller's spelling, not the first one's.

        Two callers reach the same physical document through two spellings:
        ``scan_dir`` addresses it below the *resolved* scope root, while
        ``hygiene`` reaches it through a recursive scope record's ``path``,
        which ``scan_dir`` fills from the enumerating (unresolved) path.  Each
        has always reported the path it was handed.
        """
        real = self.home / "real-gemini"
        (real / "skills").mkdir(parents=True)
        self._skill(real / "skills" / "one", "one")
        (self.home / ".gemini").symlink_to(real, target_is_directory=True)
        scope = scopes._scope_by_id("gemini")
        self.assertNotEqual(str(scope.base), str(scope.base.resolve()))
        through_scan = loader.load_skill(scope.base.resolve() / "one")
        through_record = loader.load_skill(scope.base / "one")
        self.assertEqual(
            str(scope.base.resolve() / "one"), through_scan["provenance"]["path"]
        )
        self.assertEqual(str(scope.base / "one"), through_record["provenance"]["path"])

    def test_a_scope_annotation_never_leaks_into_another_scope(self):
        """Two scopes holding byte-identical documents stay distinct rows."""
        self._seed_flat(1, "gemini")
        self._skill(self._flat_root("gemini") / "shared", "shared")
        other = self._flat_root("commandcode")
        other.mkdir(parents=True, exist_ok=True)
        self._skill(other / "shared", "shared")
        scopes.scan_scope("gemini")
        scopes.scan_scope("commandcode")
        rows = {f"{r['scope']}:{r['name']}": r for r in scopes.list_all()}
        self.assertEqual("gemini", rows["gemini:shared"]["provenance"]["scope"])
        self.assertEqual(
            "commandcode", rows["commandcode:shared"]["provenance"]["scope"]
        )
        self.assertEqual("gemini", rows["gemini:shared"]["provenance"]["consumer"])

    def test_a_registry_provenance_sidecar_appearing_later_is_reported(self):
        """The sidecar probe is part of what a warm read must not skip.

        Writing a ``.skillsmgr-provenance.json`` changes nothing about
        ``SKILL.md``'s bytes, so a reuse keyed on the document's content would
        keep reporting a skill as never fetched from the registry.
        """
        import hashlib
        import json

        from skillsmgr import registry

        skill = self._skill(self.base / "skills" / "fetched", "fetched")
        self.assertNotIn("registry_provenance", loader.load_skill(skill))
        raw = (skill / "SKILL.md").read_bytes()
        files = [
            {
                "path": "SKILL.md",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "contents": raw.decode("utf-8"),
            }
        ]
        provenance = {
            "version": 1,
            "kind": "skills.sh",
            "id": "owner/repo/fetched",
            "source": "owner/repo",
            "slug": "fetched",
            "page_url": "https://skills.sh/owner/repo/fetched",
            "api_url": "https://skills.sh/api/download/owner/repo/fetched",
            "remote_hash": None,
            "remote_hash_verified": False,
            "registry_hash": "0" * 64,
            "local_snapshot_hash": registry.snapshot_hash(files),
            "hash_verified": False,
            "fetched_at": "2026-01-01T00:00:00Z",
            "cache_state": "miss",
            "normalization": None,
            "files": [{key: entry[key] for key in ("path", "sha256", "bytes")} for entry in files],
        }
        (skill / registry.PROVENANCE_FILENAME).write_text(
            json.dumps(provenance), encoding="utf-8"
        )
        record = loader.load_skill(skill)
        self.assertIn("registry_provenance", record)
        self.assertEqual("owner/repo", record["registry_provenance"]["source"])
        self.assertFalse(record["malformed"])
        # ...and removing it again is observed too, rather than lingering.
        (skill / registry.PROVENANCE_FILENAME).unlink()
        self.assertNotIn("registry_provenance", loader.load_skill(skill))

    def test_a_malformed_sidecar_after_a_warm_read_is_reported_as_drift(self):
        from skillsmgr import registry

        skill = self._skill(self.base / "skills" / "drifted", "drifted")
        self.assertFalse(loader.load_skill(skill)["malformed"])
        (skill / registry.PROVENANCE_FILENAME).write_text("{not json", encoding="utf-8")
        record = loader.load_skill(skill)
        self.assertTrue(record["malformed"])
        self.assertIn("registry_provenance_error", record)
        self.assertNotIn("registry_provenance", record)

    def test_nothing_is_persisted(self):
        """No SQLite, no data-dir write: the reuse is process-local only."""
        from skillsmgr.atomic_io import tree_content_hash
        from skillsmgr.store import SCHEMA_VERSION

        self._seed_flat(4)
        store = Store()
        store.init_db()
        scopes.set_global_store(store)
        data_dir = store.data_dir
        before = tree_content_hash(data_dir)
        for _ in range(3):
            scopes.list_all()
        self.assertGreater(loader.document_cache_size(), 0)
        self.assertEqual(before, tree_content_hash(data_dir))
        self.assertEqual("1", SCHEMA_VERSION)


class IsolatedCopyEquivalenceTests(ScopeReadCase):
    """``isolated_record`` must be exactly ``copy.deepcopy``, only cheaper.

    It runs on every load, so it is hand-written; the hand-written part is only
    acceptable if it is pinned to the thing it replaces.
    """

    def _shapes(self):
        return [
            {},
            {"provenance": {"path": "/a/b", "scope": None, "consumer": None}},
            {"portable_frontmatter": {"name": "n", "metadata": {"category": "c"}}},
            {"frontmatter_extensions": {"x": ["a", "b"], "y": {"z": 1}}},
            {"registry_provenance": {"files": [{"path": "SKILL.md", "sha256": "0" * 64}]}},
            {"portable_frontmatter": {"metadata": {"deep": {"deeper": [{"k": "v"}]}}}},
            {"name": "n", "tokens": 12, "malformed": False, "body": "b", "extra": None},
        ]

    def test_the_isolated_copy_equals_a_whole_record_deepcopy(self):
        for index, record in enumerate(self._shapes()):
            with self.subTest(shape=index):
                self.assertEqual(copy.deepcopy(record), loader.isolated_record(record))

    def test_the_isolated_copy_shares_nothing_mutable_with_its_source(self):
        def shared(source, other):
            if isinstance(source, dict):
                if source is other:
                    return True
                return any(shared(v, other.get(k)) for k, v in source.items())
            if isinstance(source, list):
                return source is other or any(
                    shared(v, other[i]) for i, v in enumerate(source)
                )
            return False

        for index, record in enumerate(self._shapes()):
            with self.subTest(shape=index):
                copy_ = loader.isolated_record(record)
                self.assertIsNot(copy_, record)
                for key in loader._MUTABLE_RECORD_KEYS:
                    value = record.get(key)
                    if isinstance(value, (dict, list, tuple)):
                        self.assertFalse(
                            shared(value, copy_[key]),
                            f"shape {index}: {key} is still shared",
                        )

    def test_an_unrecognised_value_type_is_still_copied_exactly(self):
        """Anything the copier does not model falls through to deepcopy.

        ``complex`` is a real stdlib type the copier does not enumerate, is not
        a ``dict``/``list``/``tuple``, and compares equal to its own copy, so it
        exercises the fallback without making the assertion unreadable.
        """
        record = {"provenance": {"path": "/a", "odd": complex(1, 2)}}
        self.assertEqual(copy.deepcopy(record), loader.isolated_record(record))

    def test_a_self_referential_value_is_copied_not_recursed_forever(self):
        """The depth bound is a *safety* net, not a fidelity claim.

        A cycle cannot occur in a loader record -- frontmatter is parsed text
        and provenance is ``json.loads`` -- so what matters is only that the
        copier terminates and produces a distinct object rather than blowing the
        stack.  Its result is deliberately not asserted equal to
        ``copy.deepcopy``: past the bound the remainder is handed to
        ``deepcopy``, which keeps its own aliasing rather than the copy's.
        """
        loop: dict = {}
        loop["self"] = loop
        copied = loader._copy_value(loop)
        self.assertIsInstance(copied, dict)
        self.assertIsNot(copied, loop)
        self.assertIsNot(copied["self"], loop)


class ReuseAboveTheBoundTests(ScopeReadCase):
    """A scan larger than the bound must not thrash: it must not reuse at all.

    A bounded LRU cannot beat a sequential scan bigger than itself -- measured,
    5,000 documents through a 1,000-entry bound re-derived 5,001 on the second
    pass.  The caller keeps the pre-reuse cost instead, which is the only
    honest outcome when the working set cannot fit.
    """

    def setUp(self):
        super().setUp()
        loader.clear_document_cache()
        self.addCleanup(loader.clear_document_cache)

    def _derived_calls(self, run):
        real = loader.parse_frontmatter
        seen: list[str] = []

        def counting(text):
            seen.append(text[:40])
            return real(text)

        with mock.patch.object(loader, "parse_frontmatter", counting):
            rows = run()
        return rows, len(seen)

    def test_a_scan_beyond_the_bound_publishes_nothing_and_reuses_nothing(self):
        root = self._seed_flat(40)
        with mock.patch.object(loader, "MAX_DOCUMENT_CACHE", 8):
            rows, first = self._derived_calls(lambda: loader.scan_dir(root))
            self.assertEqual(40, len(rows))
            self.assertEqual(40, first)
            self.assertEqual(0, loader.document_cache_size())
            rows2, second = self._derived_calls(lambda: loader.scan_dir(root))
            self.assertEqual(40, len(rows2))
            self.assertEqual(40, second, "reuse must not thrash; it must be off")
            self.assertEqual(0, loader.document_cache_size())

    def test_a_scan_within_the_bound_still_reuses(self):
        root = self._seed_flat(6)
        with mock.patch.object(loader, "MAX_DOCUMENT_CACHE", 64):
            self._derived_calls(lambda: loader.scan_dir(root))
            self.assertEqual(6, loader.document_cache_size())
            _, second = self._derived_calls(lambda: loader.scan_dir(root))
            self.assertEqual(0, second)

    def test_the_bound_decision_is_exactly_the_bound(self):
        self.assertTrue(loader.document_reuse_worthwhile(loader.MAX_DOCUMENT_CACHE))
        self.assertTrue(loader.document_reuse_worthwhile(0))
        self.assertFalse(
            loader.document_reuse_worthwhile(loader.MAX_DOCUMENT_CACHE + 1)
        )

    def test_a_scan_beyond_the_bound_still_reports_everything_it_found(self):
        """Turning reuse off must not change a single reported row."""
        root = self._seed_flat(6)
        self._seed_recursive()
        with mock.patch.object(loader, "MAX_DOCUMENT_CACHE", 3):
            bounded = loader.scan_dir(root, recursive=True)
        loader.clear_document_cache()
        unbounded = loader.scan_dir(root, recursive=True)
        strip = lambda rows: [  # noqa: E731 - one-line local in a test
            {k: v for k, v in r.items() if k != "observed_at"} for r in rows
        ]
        self.assertEqual(strip(unbounded), strip(bounded))


class ObservedAtRefreshTests(ScopeReadCase):
    """``observed_at`` is a *read-time* observation, not a derivation stamp.

    ``document_observations`` stamps it with ``datetime.now()``, so the field
    means "when this read happened".  Reuse froze it at "when this process
    first derived these bytes", which is a different claim: a refresh button
    reporting an observation from before the session started is exactly the
    wrong answer for a tool whose pitch is trustworthy provenance.  It reaches
    the global Store too -- ``observed_at`` is in ``Store._OBSERVED_KEYS`` --
    and ``insights.provenance_summary`` surfaces it as evidence.
    """

    def setUp(self):
        super().setUp()
        loader.clear_document_cache()
        self.addCleanup(loader.clear_document_cache)

    @staticmethod
    def _stamp(moment: str) -> str:
        return datetime.datetime.fromisoformat(moment).strftime("%Y-%m-%dT%H:%M:%SZ")

    @contextlib.contextmanager
    def _frozen_clock(self, moment: str = "2026-10-05T18:00:00"):
        """Yield a callable that moves ``datetime.now`` to a named instant.

        Pinned in ``observations`` (where the miss path stamps) and in
        ``loader`` (where a hit re-stamps) *only where those names exist*, so
        this asserts behaviour rather than the presence of an import: against a
        tree that reuses but never refreshes, the second read still returns the
        first read's stamp and the assertion fails.

        The clock only moves when a test moves it.  It cannot be driven by
        call count, because one request stamps once *per document*.
        """
        holder = [moment]

        class Frozen(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.datetime.fromisoformat(holder[0]).replace(tzinfo=tz)

        targets = [mock.patch.object(observations, "datetime", Frozen)]
        if hasattr(loader, "datetime"):
            targets.append(mock.patch.object(loader, "datetime", Frozen))
        with contextlib.ExitStack() as stack:
            for target in targets:
                stack.enter_context(target)
            yield lambda value: holder.__setitem__(0, value)

    def test_a_reused_record_is_re_stamped_with_the_time_of_the_read(self):
        """RED-FIRST: pre-fix the second read returned the first read's stamp."""
        skill = self._skill(self.base / "skills" / "one", "one")
        with self._frozen_clock("2026-10-05T18:08:28") as at:
            first = loader.load_skill(skill)
            at("2026-10-05T18:08:31")
            second = loader.load_skill(skill)
        self.assertEqual("2026-10-05T18:08:28Z", first["observed_at"])
        self.assertEqual("2026-10-05T18:08:31Z", second["observed_at"])
        self.assertEqual(1, loader.document_cache_size(), "the second read was a hit")

    def test_every_reuse_advances_the_stamp_rather_than_repeating_it(self):
        skill = self._skill(self.base / "skills" / "one", "one")
        moments = (
            "2026-10-05T18:00:00",
            "2026-10-05T18:00:05",
            "2026-10-05T18:00:09",
            "2026-10-05T18:00:14",
        )
        with self._frozen_clock(moments[0]) as at:
            stamps = []
            for moment in moments[1:]:
                at(moment)
                stamps.append(loader.load_skill(skill)["observed_at"])
        first = loader.load_skill(skill)["observed_at"]
        self.assertEqual(len(set(stamps)), len(stamps), "a stamp repeated")
        self.assertNotEqual(first, stamps[-1])
        for moment, stamp in zip(moments[1:], stamps):
            self.assertEqual(self._stamp(moment), stamp)

    def test_the_refresh_moves_the_copy_not_the_stored_entry(self):
        """A stored entry that drifted forward would be a different bug.

        The refresh must land on the object the caller receives.  If it landed
        on the cached record, the entry's stamp would creep forward on every hit
        and stop describing anything at all.
        """
        skill = self._skill(self.base / "skills" / "one", "one")
        with self._frozen_clock("2026-10-05T18:00:00") as at:
            first = loader.load_skill(skill)
            stored = next(iter(loader._document_cache.values()))
            self.assertEqual("2026-10-05T18:00:00Z", stored["observed_at"])
            at("2026-10-05T18:00:05")
            second = loader.load_skill(skill)
            self.assertEqual("2026-10-05T18:00:05Z", second["observed_at"])
            self.assertEqual("2026-10-05T18:00:00Z", first["observed_at"])
            self.assertEqual(
                "2026-10-05T18:00:00Z",
                next(iter(loader._document_cache.values()))["observed_at"],
            )
            at("2026-10-05T18:00:09")
            third = loader.load_skill(skill)
            self.assertEqual("2026-10-05T18:00:09Z", third["observed_at"])
            self.assertEqual(
                "2026-10-05T18:00:00Z",
                next(iter(loader._document_cache.values()))["observed_at"],
            )
        self.assertEqual(1, loader.document_cache_size())

    def test_the_refreshed_copy_is_still_private_to_its_caller(self):
        skill = self._skill(self.base / "skills" / "one", "one")
        with self._frozen_clock("2026-10-05T18:00:00") as at:
            first = loader.load_skill(skill)
            at("2026-10-05T18:00:05")
            second = loader.load_skill(skill)
        self.assertIsNot(first, second)
        self.assertIsNot(first["provenance"], second["provenance"])
        second["provenance"]["scope"] = "tampered"
        second["portable_frontmatter"]["name"] = "hijacked"
        at("2026-10-05T18:00:09")
        third = loader.load_skill(skill)
        self.assertIsNone(third["provenance"]["scope"])
        self.assertEqual("one", third["portable_frontmatter"]["name"])

    def test_the_content_derived_fields_are_not_re_stamped(self):
        """Only the clock moves; every hash still describes the same bytes."""
        skill = self._skill(self.base / "skills" / "one", "one")
        with self._frozen_clock("2026-10-05T18:00:00") as at:
            first = loader.load_skill(skill)
            at("2026-10-05T18:00:05")
            second = loader.load_skill(skill)
        for field in (
            "content_hash", "metadata_hash", "description", "body", "tokens",
            "category", "portable_frontmatter", "frontmatter_extensions",
        ):
            self.assertEqual(first[field], second[field], field)
        self.assertNotEqual(first["observed_at"], second["observed_at"])

    def test_the_loader_stamp_format_is_the_observation_format(self):
        """Two producers of one field must not drift apart.

        ``observations.document_observations`` stamps the field on the miss
        path and the loader re-stamps it on the hit path.  Both carry the same
        format literal, so this pins them to each other: a change to either
        alone fails here rather than producing two shapes of timestamp.
        """
        skill = self._skill(self.base / "skills" / "one", "one")
        with self._frozen_clock("2026-10-05T18:08:28"):
            derived = observations.document_observations(skill, "text", {})
        with self._frozen_clock("2026-10-05T18:08:28"):
            re_stamped = loader._observed_at()
        self.assertEqual(derived["observed_at"], re_stamped)
        self.assertEqual("2026-10-05T18:08:28Z", re_stamped)

    def test_the_global_store_path_reports_a_current_observation(self):
        """``observed_at`` is in ``Store._OBSERVED_KEYS``, so the defect was global."""
        from skillsmgr.insights import provenance_summary

        store = Store()
        store.init_db()
        store.create("global-one", "A global skill for the observation tests.")
        scopes.set_global_store(store)
        with self._frozen_clock("2026-10-05T18:00:00") as at:
            first = store.list()[0]
            at("2026-10-05T18:00:07")
            second = store.list()[0]
        self.assertEqual("2026-10-05T18:00:00Z", first["observed_at"])
        self.assertEqual("2026-10-05T18:00:07Z", second["observed_at"])
        self.assertEqual(
            second["observed_at"], provenance_summary(second)["observed_at"]
        )

    def test_the_merged_scope_view_reports_a_current_observation(self):
        """The Library view is the surface the defect was reproduced on."""
        self._seed_flat(3)
        with self._frozen_clock("2026-10-05T18:00:00") as at:
            first = {r["name"]: r for r in scopes.list_all()}
            at("2026-10-05T18:00:06")
            second = {r["name"]: r for r in scopes.list_all()}
        self.assertEqual(3, len(first))
        for name in first:
            self.assertEqual("2026-10-05T18:00:00Z", first[name]["observed_at"], name)
            self.assertEqual("2026-10-05T18:00:06Z", second[name]["observed_at"], name)
            # Everything that describes the bytes is unchanged by the refresh.
            self.assertEqual(first[name]["content_hash"], second[name]["content_hash"])


class ScanScopeAnnotationLoopTests(ScopeReadCase):
    """Work the per-row annotation loop repeats for a per-scope answer."""

    def test_a_row_reports_the_same_physical_path_either_way(self):
        self._seed_flat(4)
        self._seed_recursive()
        for row in scopes.scan_scope("gemini") + scopes.scan_scope("agents"):
            self.assertEqual(str(Path(row["path"]).resolve()), row["physical_path"])

    def test_scope_availability_is_classified_once_not_once_per_row(self):
        """``_availability`` is a function of the scope, not of the row."""
        self._seed_flat(4)
        scope = scopes._scope_by_id("gemini")
        patcher, seen = self._counting(
            scopes, "_availability", lambda self, *a, **k: True
        )
        with patcher:
            rows = scopes.scan_scope("gemini")
        self.assertEqual(4, len(rows))
        self.assertEqual(1, len(seen), f"asked per row {len(seen)} times")
