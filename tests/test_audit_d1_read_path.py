"""Red-first regressions for the primary read path (docs/24 §D1).

``Store.list()`` is not an index read: it re-reads, re-parses and re-hashes
every document to attach derived observations, and the profile put 81% of a
1,200-skill ``list()`` inside ``_observe_index_row``.  Three of the four costs
audited there are pure overhead with no behavioural contract behind them:

* the shared-read fan-in deep-copied its result twice for the caller that
  actually produced it;
* the per-row containment guard re-resolved the *same* skills root once per
  row (``path_safety.contained_path`` resolves the root and the candidate);
* the provenance sidecar probe walked the whole directory ancestry -- one
  ``lstat`` per component, to the filesystem root -- before checking whether
  the sidecar it protects exists at all.

Each test below asserts the property that makes the optimisation safe, or the
user-visible behaviour the optimisation must not change.  They fail against the
pre-fix code for the right reason; see each test's docstring.
"""

from __future__ import annotations

import copy
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import path_safety, registry
from skillsmgr.path_safety import contained_path
from skillsmgr.registry import RegistryError, read_provenance
from skillsmgr.store import Store


def _valid_snapshot() -> dict:
    files = [
        {
            "path": "SKILL.md",
            "contents": "---\nname: alpha\ndescription: Demo.\n---\n# Alpha\n",
        },
    ]
    return {
        "id": "acme/repo/alpha",
        "files": files,
        "hash": registry.registry_snapshot_hash(files),
    }


def _write_skill(skills_dir: Path, name: str, body: str = "body") -> Path:
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use this when you need {name} things.\n"
        "license: MIT\ncategory: bench\n---\n"
        f"# {name}\n\n{body}\n",
        encoding="utf-8",
    )
    return skill_dir


class ReadPathTestCase(unittest.TestCase):
    """Fresh data root per test; nothing touches the developer's real store."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = Store(data_dir=Path(self._tmp.name) / "data")
        self.store.init_db()

    def seed(self, count: int) -> None:
        for i in range(count):
            _write_skill(self.store.skills_dir, f"bench-{i:04d}")
        self.store.db_rebuild()


class CoalescedReadCopyTests(ReadPathTestCase):
    """D1: the caller that ran the read must not pay for two deep copies.

    ``_coalesced_read`` published ``copy.deepcopy(func())`` into the flight and
    then returned ``copy.deepcopy(result)``.  The first copy exists so a
    *waiting* caller never shares objects with the producer; the producer's own
    return copy is a second full traversal of the same structure that nobody
    else can reach, so the library's most-experienced request paid it twice.
    """

    def test_a_single_list_copies_the_result_exactly_once(self):
        self.seed(3)
        real_deepcopy = copy.deepcopy
        calls = []

        def counting_deepcopy(value, *args, **kwargs):
            # Only count the whole-result copies, not the recursion copy.deepcopy
            # performs internally on nested containers.
            if isinstance(value, list) and value and isinstance(value[0], dict):
                calls.append(len(value))
            return real_deepcopy(value, *args, **kwargs)

        with mock.patch.object(copy, "deepcopy", counting_deepcopy):
            rows = self.store.list()

        self.assertEqual(3, len(rows))
        self.assertEqual([3], calls, "list() deep-copied its whole result more than once")

    def test_every_caller_still_receives_an_independent_copy(self):
        """The optimisation must not hand two callers the same dicts."""
        self.seed(2)
        first = self.store.list()
        second = self.store.list()
        self.assertEqual(first, second)
        self.assertIsNot(first[0], second[0])
        self.assertIsNot(first[0]["provenance"], second[0]["provenance"])
        first[0]["description"] = "mutated by one caller"
        first[0]["provenance"]["scope"] = "mutated"
        self.assertNotEqual("mutated by one caller", second[0]["description"])
        self.assertNotEqual("mutated", second[0]["provenance"]["scope"])


class ContainedPathUnderTests(ReadPathTestCase):
    """D1: hoisting the skills-root resolve must not weaken containment.

    ``contained_path`` resolves ``root`` on every call, so a scan paid one full
    ancestry resolution per row for a root it had already resolved.  The
    pre-resolved form must return exactly what the general form returns --
    including the escape rejection -- or the hoist is a security regression
    dressed as a speedup.
    """

    def setUp(self):
        super().setUp()
        self.root = self.store.skills_dir
        self.resolved_root = self.root.expanduser().resolve()
        _write_skill(self.root, "alpha")

    def test_it_matches_the_general_form_for_a_plain_skill(self):
        self.assertEqual(
            contained_path(self.root, "alpha"),
            path_safety.contained_path_under(self.resolved_root, "alpha"),
        )

    def test_it_matches_the_general_form_for_a_deeper_path(self):
        nested = self.root / "alpha" / "references"
        nested.mkdir(parents=True, exist_ok=True)
        self.assertEqual(
            contained_path(self.root, "alpha", "references"),
            path_safety.contained_path_under(self.resolved_root, "alpha", "references"),
        )

    def test_an_escaping_symlink_target_is_still_rejected(self):
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        alias = self.root / "escapee"
        os.symlink(outside, alias)
        with self.assertRaises(ValueError):
            path_safety.contained_path_under(self.resolved_root, "escapee")

    def test_a_parent_traversing_name_is_still_rejected(self):
        with self.assertRaises(ValueError):
            path_safety.contained_path_under(self.resolved_root, "..")
        with self.assertRaises(ValueError):
            path_safety.contained_path_under(self.resolved_root, "alpha", "..", "..")

    def test_an_absolute_part_is_still_rejected(self):
        with self.assertRaises(ValueError):
            path_safety.contained_path_under(self.resolved_root, "/etc")

    def test_a_windows_separator_or_drive_prefix_is_still_rejected(self):
        for part in ("alpha\\beta", "C:/beta"):
            with self.subTest(part=part):
                with self.assertRaises(ValueError):
                    path_safety.contained_path_under(self.resolved_root, part)

    def test_the_safe_wrapper_still_enforces_the_canonical_name_rule(self):
        """The hoist must not trade the name rule away for the speedup."""
        self.assertEqual(
            path_safety.safe_skill_path(self.root, "alpha"),
            path_safety.safe_skill_path_under(self.resolved_root, "alpha"),
        )
        for name in ("Not_A_Canonical_Name", "--lead", "trail-", "a" * 65):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    path_safety.safe_skill_path_under(self.resolved_root, name)

    def test_listing_resolves_the_skills_root_once_not_once_per_row(self):
        """The audited cost: one root resolution per row, not one per scan."""
        self.seed(40)
        calls = []

        real_realpath = os.path.realpath

        def counting_realpath(path, *args, **kwargs):
            calls.append(str(path))
            return real_realpath(path, *args, **kwargs)

        with mock.patch.object(os.path, "realpath", counting_realpath):
            self.store.list()

        root_resolutions = [
            path for path in calls
            if path.rstrip(os.sep) == str(self.store.skills_dir)
        ]
        self.assertLessEqual(
            len(root_resolutions), 1,
            f"list() re-resolved the skills root {len(root_resolutions)} times for 40 rows",
        )


class ProvenanceSidecarProbeTests(ReadPathTestCase):
    """D1: probe for the sidecar before walking its ancestry.

    ``read_provenance`` ran ``_reject_symlink_ancestors`` first -- one ``lstat``
    per component from the skill directory to ``/`` -- and only then checked
    ``lexists`` on the sidecar it exists to protect.  A library where no skill
    came from the registry therefore paid a full ancestry walk per row, per
    read, to guard a file that was not there.
    """

    def test_a_missing_sidecar_does_not_walk_a_symlinked_ancestry(self):
        base = Path(self._tmp.name) / "real"
        base.mkdir()
        skill_dir = base / "alpha"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: alpha\ndescription: d\n---\nb\n", encoding="utf-8")
        link = Path(self._tmp.name) / "link"
        link.symlink_to(base)

        # Reachable through a symlinked ancestor, with no sidecar at all.
        self.assertIsNone(read_provenance(link / "alpha"))

    def test_a_present_sidecar_under_a_symlinked_ancestry_is_still_refused(self):
        """The guard is not weakened: it only stops guarding nothing."""
        base = Path(self._tmp.name) / "real"
        base.mkdir()
        skill_dir = base / "alpha"
        snapshot = registry.validate_snapshot(_valid_snapshot())
        snapshot.update({
            "source": "acme/repo",
            "slug": "alpha",
            "api_url": "https://skills.sh/api/download/acme/repo/alpha",
            "_registry": {"cache_state": "miss"},
        })
        registry.materialize_snapshot(snapshot, skill_dir)
        registry.write_provenance(
            skill_dir, registry.provenance_for_snapshot(snapshot)
        )
        link = Path(self._tmp.name) / "link"
        link.symlink_to(base)

        with self.assertRaises(RegistryError):
            read_provenance(link / "alpha")
        # The same sidecar reached directly is read normally.
        self.assertIsNotNone(read_provenance(skill_dir))

    def test_reading_a_missing_sidecar_walks_no_ancestry(self):
        skill_dir = _write_skill(self.store.skills_dir, "alpha")
        walked = []
        real_reject = registry._reject_symlink_ancestors

        def counting_reject(path):
            walked.append(str(path))
            return real_reject(path)

        with mock.patch.object(registry, "_reject_symlink_ancestors", counting_reject):
            self.assertIsNone(read_provenance(skill_dir))

        self.assertEqual([], walked, "the ancestry walk ran for a sidecar that does not exist")


class ScanScopeGlobalReadTests(ReadPathTestCase):
    """D1: a merged read must not read the same document twice.

    ``scan_scope("global")`` enriches index rows with a token estimate by
    opening ``SKILL.md`` and re-running ``tokens.estimate`` -- work the row's
    own loader pass had already done for the same bytes, and then threw away.
    So the default Library view read every global skill document twice.
    """

    def test_a_global_scan_opens_each_document_once(self):
        self.seed(6)
        opened = []
        real_read_bytes = Path.read_bytes
        real_read_text = Path.read_text

        def _count(name, real):
            def reader(self_path, *args, **kwargs):
                if self_path.name in ("SKILL.md", "SKILL.md.disabled"):
                    opened.append(name)
                return real(self_path, *args, **kwargs)
            return reader

        with mock.patch.object(Path, "read_bytes", _count("read_bytes", real_read_bytes)), \
                mock.patch.object(Path, "read_text", _count("read_text", real_read_text)):
            from skillsmgr import scopes

            scopes.set_global_store(self.store)
            self.addCleanup(scopes.set_global_store, None)
            rows = scopes.scan_scope("global")

        self.assertEqual(6, len(rows))
        self.assertEqual(
            6, len(opened),
            f"scan_scope('global') opened {len(opened)} documents for 6 skills; "
            "each must be read exactly once",
        )

    def test_token_fields_survive_the_single_read(self):
        self.seed(3)
        from skillsmgr import scopes

        scopes.set_global_store(self.store)
        self.addCleanup(scopes.set_global_store, None)
        rows = scopes.scan_scope("global")
        self.assertEqual(3, len(rows))
        for row in rows:
            with self.subTest(name=row["name"]):
                self.assertGreater(row["tokens"], 0)
                self.assertIn(row["tokens_method"], ("tiktoken", "heuristic"))
                self.assertGreaterEqual(row["tokens_pct"], 0)
                self.assertGreater(row["chars"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class StoreListReuseGuardTests(ReadPathTestCase):
    """``Store.list()`` must consult the reuse guard before loading a batch.

    ``loader.scan_dir`` and ``hygiene._prepare_records`` both decide once per
    batch; the global half of the Library view did not, so a store above the
    bound measured 0% reuse on a warm pass and +10.8% against running with reuse
    switched off -- the failure the guard exists to prevent, on the default
    global read.

    Red-first: before ``reuse`` was threaded through, the cache filled to the
    bound instead of staying empty.
    """

    def setUp(self):
        super().setUp()
        from skillsmgr import loader

        self.loader = loader
        loader.clear_document_cache()
        self.addCleanup(loader.clear_document_cache)

    def test_a_store_above_the_bound_lists_everything_and_reuses_nothing(self):
        self.seed(6)
        # seed() indexes the store, which populates the reuse cache at the real
        # bound. Clear it so this measures `list()` and nothing before it.
        self.loader.clear_document_cache()
        with mock.patch.object(self.loader, "MAX_DOCUMENT_CACHE", 4):
            rows = self.store.list()
            self.assertEqual(6, len(rows), "turning reuse off must not change a single row")
            self.assertEqual(
                0, self.loader.document_cache_size(),
                "a batch above the bound must not populate the cache it cannot hold",
            )

    def test_a_store_within_the_bound_still_reuses(self):
        self.seed(4)
        with mock.patch.object(self.loader, "MAX_DOCUMENT_CACHE", 64):
            self.store.list()
            self.assertEqual(4, self.loader.document_cache_size())
            self.loader.clear_document_cache()
            self.store.list()
            self.assertEqual(4, self.loader.document_cache_size())
