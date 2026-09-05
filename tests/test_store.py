"""Unit tests for skills-manager. Stdlib unittest only (no third-party deps).

Hermetic: every test uses an isolated $SKILLS_MANAGER_DATA tmp dir.
Filesystem is the source of truth; the DB is only an index.

Run:  python3 -m unittest discover -s tests -v
"""

import os
import tempfile
import unittest

from skillsmgr.frontmatter import dump_frontmatter, parse_frontmatter
from skillsmgr.loader import load_skill
from skillsmgr.scopes import known_scopes
from skillsmgr.search import rank_results
from skillsmgr.store import SkillNotFound, Store, StoreError
from skillsmgr.validator import description_score, validate_skill, validate_text


def _skill_body(name="demo", description="Demo skill"):
    return dump_frontmatter(
        {
            "name": name,
            "description": description,
            "license": "",
            "compatibility": "",
            "version": "",
            "allowed_tools": "",
        },
    ) + "# Demo\n\nBody text.\n"


class IsolatedStoreTestCase(unittest.TestCase):
    """Base: fresh $SKILLS_MANAGER_DATA per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        os.environ["SKILLS_MANAGER_DATA"] = self._tmp.name
        self.store = Store()
        self.store.init_db()

    def make_skill_dir(self, name, text=None, disabled=False):
        from pathlib import Path

        d = Path(self._tmp.name) / name
        d.mkdir(exist_ok=True)
        fname = "SKILL.md.disabled" if disabled else "SKILL.md"
        (d / fname).write_text(
            text if text is not None else _skill_body(name), encoding="utf-8"
        )
        return d


class TestCreateGetList(IsolatedStoreTestCase):
    def test_create_and_get(self):
        rec = self.store.create("demo", "Demo skill", body="Hello.")
        self.assertEqual(rec["name"], "demo")
        self.assertEqual(self.store.get("demo")["description"], "Demo skill")
        self.assertEqual(len(self.store.list()), 1)

    def test_create_rejects_bad_name(self):
        with self.assertRaises(StoreError):
            self.store.create("Bad Name!", "x")

    def test_create_rejects_duplicate(self):
        self.store.create("demo", "Demo skill")
        with self.assertRaises(StoreError):
            self.store.create("demo", "Other description")

    def test_get_missing_raises(self):
        with self.assertRaises(SkillNotFound):
            self.store.get("nope")


class TestEditToggle(IsolatedStoreTestCase):
    def test_edit_partial(self):
        self.store.create("demo", "Demo skill")
        out = self.store.edit("demo", description="New desc")
        self.assertTrue(out["changed"])
        self.assertEqual(self.store.get("demo")["description"], "New desc")

    def test_disable_enable_cycle(self):
        self.store.create("demo", "Demo skill")
        self.store.disable("demo")
        rows = self.store.list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["disabled"], 1)
        self.store.enable("demo")
        rows = self.store.list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["disabled"], 0)


class TestTrash(IsolatedStoreTestCase):
    def test_remove_trash_restore_purge(self):
        self.store.create("demo", "Demo skill")
        self.store.remove("demo")
        self.assertEqual(len(self.store.list()), 0)
        self.assertEqual(len(self.store.trash_list()), 1)
        self.store.restore("demo")
        self.assertEqual(len(self.store.list()), 1)
        self.store.remove("demo", purge=True)
        self.assertEqual(len(self.store.trash_list()), 0)

    def test_restore_prefix_collision(self):
        """Restoring 'demo' must not match trashed 'demo-x'."""
        self.store.create("demo", "Demo skill")
        self.store.create("demo-x", "Demo x skill")
        self.store.remove("demo-x")
        self.store.remove("demo")
        self.store.restore("demo")
        self.assertEqual(self.store.get("demo")["description"], "Demo skill")
        self.assertEqual(len(self.store.trash_list()), 1)


class TestSearchStatsHistoryDoctor(IsolatedStoreTestCase):
    def test_search_ranked(self):
        self.store.create("deploy-app", "Deploys the app")
        self.store.create("other", "Unrelated")
        hits = self.store.search("deploy")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["name"], "deploy-app")

    def test_stats_counts(self):
        self.store.create("a", "Skill a")
        self.store.create("b", "Skill b")
        stats = self.store.stats()
        self.assertEqual(stats["total"], 2)

    def test_history_records(self):
        self.store.create("demo", "Demo skill")
        names = [h["name"] for h in self.store.history(limit=10)]
        self.assertIn("demo", names)

    def test_doctor_ok(self):
        self.store.create("demo", "Demo skill")
        self.assertTrue(self.store.doctor()["ok"])

    def test_db_rebuild_roundtrip(self):
        self.store.create("demo", "Demo skill")
        out = self.store.db_rebuild()
        self.assertIn("added", out)
        self.assertEqual(len(self.store.list()), 1)


class TestExportImport(IsolatedStoreTestCase):
    def test_export_import_roundtrip(self):
        from pathlib import Path

        self.store.create("demo", "Demo skill", body="Hello.")
        dest = Path(self._tmp.name) / "exp.tar.gz"
        out = self.store.export(dest=str(dest))
        self.assertTrue(Path(str(out)).is_file())
        self.store.remove("demo", purge=True)
        result = self.store.import_(str(dest))
        self.assertIn("demo", result["imported"])
        self.assertEqual(len(self.store.list()), 1)


class TestValidatorLoaderScopes(unittest.TestCase):
    def test_validator_accepts_good_skill(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "demo"
            p.mkdir()
            (p / "SKILL.md").write_text(_skill_body(), encoding="utf-8")
            result = validate_skill("demo", p)
            self.assertTrue(result.valid, [i.message for i in result.issues])

    def test_validator_rejects_bad_name(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "Bad Name!"
            p.mkdir()
            (p / "SKILL.md").write_text(_skill_body(), encoding="utf-8")
            self.assertFalse(validate_skill("Bad Name!", p).valid)

    def test_validator_warns_on_link_escape(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "demo"
            p.mkdir()
            (p / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Demo skill.\n---\n"
                "See [x](../../evil.md).\n",
                encoding="utf-8",
            )
            result = validate_skill("demo", p)
            self.assertTrue(
                any(
                    "outside" in i.message.lower() or "escape" in i.message.lower()
                    for i in result.issues
                )
            )

    def test_validator_reads_disabled_file(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "demo"
            p.mkdir()
            (p / "SKILL.md.disabled").write_text(
                "---\nname: demo\ndescription: Demo skill.\n---\nBody.\n",
                encoding="utf-8",
            )
            self.assertTrue(validate_skill("demo", p).valid)

    def test_validator_warns_on_missing_use_context(self):
        result = validate_text(_skill_body(description="Does stuff"))
        self.assertTrue(
            any("use-context" in i.message for i in result.warnings),
            [i.message for i in result.issues],
        )
        ok = validate_text(
            _skill_body(description="Use when deploying to staging.")
        )
        self.assertFalse(
            any("use-context" in i.message for i in ok.issues),
            [i.message for i in ok.issues],
        )

    def test_validator_warns_on_vague_filler(self):
        result = validate_text(_skill_body(description="Handles various stuff"))
        self.assertTrue(
            any("filler" in i.message for i in result.warnings),
            [i.message for i in result.issues],
        )

    def test_validator_warns_on_missing_layout_file(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "demo"
            p.mkdir()
            (p / "SKILL.md").write_text(
                _skill_body(description="Use when testing refs.")
                + "\nRead references/api.md when the API errors.\n",
                encoding="utf-8",
            )
            result = validate_skill("demo", p)
            self.assertTrue(
                any("references/api.md" in i.message for i in result.warnings),
                [i.message for i in result.issues],
            )
            (p / "references").mkdir()
            (p / "references" / "api.md").write_text("# API\n", encoding="utf-8")
            result = validate_skill("demo", p)
            self.assertFalse(
                any("references/api.md" in i.message for i in result.issues),
                [i.message for i in result.issues],
            )

    def test_validator_warns_on_oversize_body_tokens(self):
        big = "word " * 6000  # heuristic ~9000 tokens, over the 5000 cap
        result = validate_text(_skill_body() + "\n" + big)
        self.assertTrue(
            any("tokens" in i.message for i in result.warnings),
            [i.message for i in result.issues],
        )

    def test_description_score(self):
        good = description_score("Use this skill when reviewing pull requests.")
        self.assertTrue(good["has_use_context"])
        self.assertEqual(good["filler_hits"], [])
        bad = description_score("Handles various things appropriately.")
        self.assertFalse(bad["has_use_context"])
        self.assertIn("various", bad["filler_hits"])

    def test_loader_flags_malformed_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "broken"
            p.mkdir()
            (p / "SKILL.md").write_text(
                "---\nname: [unclosed\n---\nbody\n", encoding="utf-8"
            )
            self.assertTrue(load_skill(p).get("malformed"))

    def test_known_scopes_include_all_agents(self):
        ids = {s.id for s in known_scopes()}
        self.assertTrue(
            {
                "global",
                "claude-code",
                "codex",
                "cursor",
                "opencode",
                "gemini",
                "commandcode",
                "agents",
            }
            <= ids
        )


class TestFrontmatterSearchUnits(unittest.TestCase):
    def test_frontmatter_roundtrip(self):
        fm, body = parse_frontmatter(_skill_body(name="x", description="Y"))
        self.assertEqual(fm["name"], "x")
        self.assertIn("Body", body)

    def test_search_scoring_prefers_exact(self):
        recs = [
            {"name": "other", "description": "mentions deploy here", "category": ""},
            {"name": "deploy", "description": "", "category": ""},
        ]
        ranked = rank_results(recs, "deploy")
        self.assertEqual(ranked[0][0]["name"], "deploy")


if __name__ == "__main__":
    unittest.main()
