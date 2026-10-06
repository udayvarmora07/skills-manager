"""D1 item 1: make the observations lazy without losing a signal.

Measured on this tree at 1,200 synthetic skills (isolated ``HOME`` **and**
``SKILLS_MANAGER_DATA``, wall-clock interleaved A/B):

======================================  ==========  ========
variant                                 warm median  vs base
======================================  ==========  ========
A ``Store.list()`` baseline                 155.3 ms     --
B skip the document read                     72.8 ms  -53.1%
F drop the 3 observation keys nobody reads  148.1 ms   -4.6%
C skip *all* observation                     17.2 ms  -88.9%
======================================  ==========  ========

Two things follow, and both are pinned below.

**1. The document read is ~53% of the cost, not the 82%/54% the 2026-10-04
profile recorded.**  cProfile inflates per-row Python call overhead
(``realpath``, ``deepcopy``, pathlib) relative to syscalls, so it mis-ranks the
read against the call loop.  Half the remaining cost is *not* the read, which is
why "lazy observations" alone caps at 53%: a lazy list that stops reading
documents cannot report ``malformed``/``decode_error``, and those are what the
Overview attention queue, Quality, Doctor and ``effective.explain`` all read.
That is the exact trade the maintainer refused in 2026-10-05, so this change
keeps the signals and removes the *duplicate* work instead.

**2. ``GET /api/skills?scope=global`` reads every document TWICE.**
``Store.list()`` already derives the token estimate from the bytes it just read;
``webapp._enrich_rows_with_tokens`` then re-reads the same document and
**unconditionally overwrites** the identical value.  Measured at 2.0x reads per
skill and 17-19% of the route.  It is worse than waste: ``_skill_text`` reads
through a bare ``read_text(encoding="utf-8")``, so an undecodable document
yields ``""`` and **clobbers a correct 277-token estimate with 0** --
``GET /api/skills?scope=global`` reports a malformed document as occupying no
context at all.  ``scopes._enrich_global_row`` already guards this with
``if "tokens" not in r``; this module's sibling copy never got the guard.

Every test below is red-first: each asserts the property that must hold, and
fails against the pre-fix source for its own reason.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import urllib.request
from pathlib import Path

from skillsmgr import loader, webapp
from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


class LazyObservationTestCase(unittest.TestCase):
    """A private data root *and* a private HOME, per test.

    Both are required.  ``WebAppServer`` binds a Store, but every scope route
    still reads the *real* agent scope roots through ``scopes.known_scopes()``;
    without the HOME isolation this suite walks the developer's actual
    ``~/.claude/skills`` and friends.  That has made this repository's tests
    flaky for exactly this reason before (tests/test_audit_d3_read_purity.py).
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.data_dir = self.root / "data"
        home = self.root / "home"
        home.mkdir(mode=0o700)
        self._saved_env = {
            key: os.environ.get(key)
            for key in ("SKILLS_MANAGER_DATA", "XDG_DATA_HOME", "HOME")
        }
        self.addCleanup(self._restore_env)
        os.environ["SKILLS_MANAGER_DATA"] = str(self.data_dir)
        os.environ["XDG_DATA_HOME"] = str(home / ".local" / "share")
        os.environ["HOME"] = str(home)

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def store(self) -> Store:
        store = Store(data_dir=self.data_dir)
        store.init_db()
        self.addCleanup(shutil.rmtree, self.data_dir, True)
        return store

    def write_skill(self, store: Store, name: str, body: str = "Body text.") -> Path:
        directory = store.skills_dir / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Use when doing {name}.\n"
            f"metadata:\n  category: testing\n---\n\n{body}\n",
            encoding="utf-8",
        )
        return directory

    def write_undecodable(self, store: Store, name: str) -> Path:
        """A SKILL.md that is not valid UTF-8 (issue #13's drift case)."""
        directory = store.skills_dir / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_bytes(
            f"---\nname: {name}\ndescription: Broken.\n---\n\n".encode("utf-8")
            + b"caf\xe9 not utf-8 " * 40
        )
        return directory

    def serve(self, store: Store) -> WebAppServer:
        server = WebAppServer(store, host="127.0.0.1", port=0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return server

    def get_rows(self, server: WebAppServer, path: str) -> list[dict]:
        with urllib.request.urlopen(f"{server.url}{path}", timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, list) else payload.get("skills", [])


class TheListRouteReadsEachDocumentOnce(LazyObservationTestCase):
    """RED-FIRST: the measured 2.0x read is a defect, not a design."""

    def test_the_global_list_route_reads_each_document_exactly_once(self):
        """One request, one read per skill.

        Fails against the pre-fix source at 2.0x: ``Store.list()`` observes
        every document, then ``_enrich_rows_with_tokens`` re-reads the same
        bytes.  Counting reads -- not timing -- is the assertion, so this does
        not flake on a loaded machine.
        """
        store = self.store()
        for i in range(6):
            self.write_skill(store, f"skill-{i}", "prose " * 40)
        store.db_rebuild()
        server = self.serve(store)

        counts = {"probe": 0, "direct": 0}
        real_probe = loader._probe_document
        real_text = webapp._skill_text

        def counting_probe(path):
            counts["probe"] += 1
            return real_probe(path)

        def counting_text(path):
            counts["direct"] += 1
            return real_text(path)

        loader._probe_document = counting_probe
        webapp._skill_text = counting_text
        self.addCleanup(setattr, loader, "_probe_document", real_probe)
        self.addCleanup(setattr, webapp, "_skill_text", real_text)
        self.get_rows(server, "/api/skills?scope=global")
        loader._probe_document = real_probe
        webapp._skill_text = real_text

        total = counts["probe"] + counts["direct"]
        self.assertEqual(
            6, total,
            f"one request read {total} documents for 6 skills "
            f"(loader={counts['probe']}, enrichment={counts['direct']}); "
            "the second read recomputes a value already derived from the same bytes",
        )

    def test_the_enrichment_does_not_reread_a_document_the_loader_already_read(self):
        """The function-level property behind the route test.

        ``_enrich_rows_with_tokens`` receives rows that ``Store.list()`` has
        already observed.  For such a row it must not open the document again.
        """
        store = self.store()
        self.write_skill(store, "alpha", "prose " * 40)
        self.write_skill(store, "beta", "prose " * 40)
        store.db_rebuild()

        rows = store.list()
        self.assertTrue(all(r.get("tokens") for r in rows))

        calls = {"n": 0}
        real_text = webapp._skill_text

        def counting_text(path):
            calls["n"] += 1
            return real_text(path)

        webapp._skill_text = counting_text
        try:
            webapp._enrich_rows_with_tokens(store, rows, "test")
        finally:
            webapp._skill_text = real_text

        self.assertEqual(
            0, calls["n"],
            f"enrichment re-read {calls['n']} documents the loader had already read",
        )


class EnrichmentNeverClobbersACorrectEstimate(LazyObservationTestCase):
    """RED-FIRST: the correctness half of the same defect."""

    def test_an_undecodable_document_keeps_its_observed_token_estimate(self):
        """A malformed document must not be reported as occupying no context.

        ``_skill_text`` decodes with a bare ``read_text(encoding="utf-8")``,
        which raises on a non-UTF-8 document and yields ``""``.  The loader
        reads the same document tolerantly (issue #13) and produces a real
        estimate over the U+FFFD text.  The enrichment overwrote that correct
        answer with 0 -- so ``GET /api/skills?scope=global`` reported a document
        that occupies 277 tokens as ``tokens: 0``.
        """
        store = self.store()
        self.write_undecodable(store, "bad-utf8")
        store.db_rebuild()

        rows = store.list()
        self.assertEqual(1, len(rows))
        observed = rows[0]["tokens"]
        self.assertGreater(
            observed, 0,
            "precondition: the loader must produce a non-zero estimate for a "
            "document it read tolerantly",
        )

        webapp._enrich_rows_with_tokens(store, rows, "test")

        self.assertEqual(
            observed, rows[0]["tokens"],
            "the enrichment replaced the loader's estimate with its own; for an "
            "undecodable document that answer is 0, because a bare "
            "read_text(encoding='utf-8') cannot decode it",
        )
        self.assertGreater(rows[0]["chars"], 0)

    def test_the_route_reports_a_malformed_document_as_occupying_context(self):
        """The user-visible shape of the same bug, over HTTP."""
        store = self.store()
        self.write_undecodable(store, "bad-utf8")
        store.db_rebuild()
        server = self.serve(store)

        rows = self.get_rows(server, "/api/skills?scope=global")
        self.assertEqual(1, len(rows))
        self.assertTrue(rows[0]["malformed"], "the document is malformed and must say so")
        self.assertGreater(
            rows[0]["tokens"], 0,
            "GET /api/skills reported a malformed document as occupying no "
            "context, so the context-budget figures silently under-count it",
        )


class ObservationSignalsSurviveTheFastPath(LazyObservationTestCase):
    """Every field a consumer reads must still be present and correct."""

    def test_a_healthy_row_reports_every_documented_field(self):
        store = self.store()
        self.write_skill(store, "alpha", "prose " * 40)
        store.db_rebuild()

        rows = store.list()
        self.assertEqual(1, len(rows))
        row = rows[0]
        for key in Store._OBSERVED_KEYS + Store._TOKEN_KEYS:
            if key in ("registry_provenance", "registry_provenance_error"):
                # A sidecar answer is only present when there is a sidecar:
                # ``_registry_provenance_fields`` returns {} for a library that
                # did not come from the registry.  Pinned separately below.
                continue
            self.assertIn(key, row, f"list() dropped the observed field {key!r}")
        self.assertTrue(row["addressable"])
        self.assertFalse(row["malformed"])
        self.assertIsNone(row["decode_error"])
        self.assertTrue(row["content_hash"])
        self.assertTrue(row["metadata_hash"])
        self.assertTrue(row["observed_at"])
        self.assertEqual("alpha", row["portable_frontmatter"]["name"])
        self.assertEqual("testing", row["category"])
        self.assertGreater(row["tokens"], 0)
        self.assertEqual(row["provenance"]["path"], str(store.skills_dir / "alpha"))

    def test_registry_provenance_is_kept_when_a_sidecar_exists(self):
        """The one observed key whose presence is conditional.

        ``registry_provenance`` is absent for a library that did not come from
        the registry and present when a sidecar exists.  The fast path must not
        disturb either direction.
        """
        from skillsmgr import registry

        store = self.store()
        directory = self.write_skill(store, "alpha", "prose " * 40)
        store.db_rebuild()

        self.assertNotIn("registry_provenance", store.list()[0])

        # Build the sidecar through the module's own validated writer rather
        # than hand-writing JSON: a hand-written payload that fails validation
        # is reported as ``registry_provenance_error`` + ``malformed``, which is
        # a different (also correct) behaviour and would not test this path.
        snapshot = registry.validate_snapshot(
            {
                "id": "acme/repo/alpha",
                "files": [
                    {
                        "path": "SKILL.md",
                        "contents": (directory / "SKILL.md").read_text(encoding="utf-8"),
                    }
                ],
            }
        )
        snapshot.update(
            {
                "source": "acme/repo",
                "slug": "alpha",
                "api_url": "https://skills.sh/api/download/acme/repo/alpha",
                "_registry": {"cache_state": "miss"},
            }
        )
        registry.write_provenance(
            directory, registry.provenance_for_snapshot(snapshot)
        )

        row = store.list()[0]
        self.assertIn("registry_provenance", row)
        self.assertEqual("acme/repo/alpha", row["registry_provenance"]["id"])
        self.assertNotIn("registry_provenance_error", row)

    def test_a_malformed_document_is_still_reported_as_malformed(self):
        """Frontmatter the parser rejects is drift the user must still see."""
        store = self.store()
        directory = store.skills_dir / "broken-frontmatter"
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            "---\nname: broken\nthis line is not a mapping\n---\n\nBody\n",
            encoding="utf-8",
        )
        store.db_rebuild()

        rows = store.list()
        self.assertEqual(1, len(rows))
        self.assertTrue(rows[0]["malformed"], "a malformed document was reported healthy")

    def test_a_document_missing_its_required_description_is_reported(self):
        store = self.store()
        directory = store.skills_dir / "no-description"
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            "---\nname: no-description\n---\n\nBody\n", encoding="utf-8"
        )
        store.db_rebuild()

        rows = store.list()
        self.assertTrue(
            rows[0]["malformed"],
            "a document missing its required description was reported healthy",
        )
        # The gap list is a loader field, not one of ``_OBSERVED_KEYS``, so it
        # reaches the loader's own consumers (hygiene, scan_scope) rather than
        # the list row.  Asserted here so the fast path cannot lose it.
        observed = loader.load_skill(directory)
        self.assertIn("description", observed["missing_required"])

    def test_a_conflicting_document_directory_is_still_reported(self):
        """Both ``SKILL.md`` and ``SKILL.md.disabled`` present (STORE-3)."""
        store = self.store()
        directory = store.skills_dir / "conflicted"
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            "---\nname: conflicted\ndescription: One.\n---\n\nBody\n", encoding="utf-8"
        )
        (directory / "SKILL.md.disabled").write_text(
            "---\nname: conflicted\ndescription: Two.\n---\n\nBody\n", encoding="utf-8"
        )
        store.db_rebuild()

        rows = store.list()
        self.assertEqual(1, len(rows))
        self.assertTrue(
            rows[0]["malformed"],
            "a conflicting directory is never a healthy skill, so the invisible "
            "second document -- which the next toggle would destroy -- was not "
            "surfaced as drift",
        )
        # ``document_conflict`` is a loader field rather than an observed key,
        # so it reaches the consumers that read the loader record directly.
        self.assertTrue(loader.load_skill(directory)["document_conflict"])

    def test_an_unaddressable_name_is_still_reported_and_marked(self):
        """A directory name failing the canonical rule (SCOPE-14)."""
        store = self.store()
        directory = store.skills_dir / "Not_A_Valid_Name"
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            "---\nname: whatever\ndescription: Unaddressable.\n---\n\nBody\n",
            encoding="utf-8",
        )
        store.db_rebuild()

        rows = store.list()
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertFalse(row["addressable"], "an unaddressable row was presented as addressable")
        self.assertTrue(row["malformed"])
        self.assertIn("canonical name rule", row["decode_error"])

    def test_the_scope_layer_still_reports_every_instance_state(self):
        """``instance_state`` is derived from ``malformed``/``addressable``."""
        from skillsmgr import scopes

        store = self.store()
        self.write_skill(store, "healthy", "prose " * 40)
        broken = store.skills_dir / "Broken_Name"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text(
            "---\nname: broken\ndescription: Unaddressable.\n---\n\nBody\n",
            encoding="utf-8",
        )
        store.db_rebuild()

        previous = scopes._global_store()
        scopes.set_global_store(store)
        self.addCleanup(scopes.set_global_store, previous)

        rows = scopes.scan_scope("global")
        states = {row["name"]: row["instance_states"] for row in rows}
        self.assertIn("healthy", states)
        self.assertEqual(["active"], states["healthy"])
        self.assertIn("Broken_Name", states)
        self.assertIn("unaddressable", states["Broken_Name"])
        self.assertIn("invalid", states["Broken_Name"])


class TheFastPathIsNotASilentDefault(LazyObservationTestCase):
    """A fast path that changes a payload shape must say so, not hide it."""

    def test_enrichment_still_fills_in_a_row_that_has_no_estimate(self):
        """The fallback stays: a row the loader could not read is still enriched.

        Without this the optimisation would trade a duplicate read for a
        *missing* field on exactly the malformed rows a user most needs to see.
        """
        store = self.store()
        self.write_skill(store, "alpha", "prose " * 40)
        store.db_rebuild()

        rows = [{"name": "alpha"}]
        webapp._enrich_rows_with_tokens(store, rows, "test")

        self.assertIn("tokens", rows[0])
        self.assertGreater(rows[0]["tokens"], 0, "a row with no estimate was left unenriched")
        self.assertIn("tokens_method", rows[0])

    def test_enrichment_reports_a_failure_rather_than_hiding_it(self):
        """BUG-8's contract: a failure is marked, not swallowed."""
        store = self.store()
        rows = [{"name": "alpha"}]

        original = webapp._skill_text
        webapp._skill_text = lambda path: (_ for _ in ()).throw(OSError("boom"))
        try:
            webapp._enrich_rows_with_tokens(store, rows, "test")
        finally:
            webapp._skill_text = original

        self.assertEqual(0, rows[0]["tokens"])
        self.assertEqual("unavailable", rows[0]["tokens_method"])
        self.assertEqual(0, rows[0]["tokens_pct"])
        self.assertEqual(0, rows[0]["chars"])


if __name__ == "__main__":
    unittest.main()