"""Red-first: one enforcement point for the one-document invariant (docs/24 §C4 #4).

A skill directory must hold exactly one of ``SKILL.md`` and
``SKILL.md.disabled``.  With both present a toggle resolves one as its source
and renames it *over* the other, destroying a document with no snapshot.

The invariant was enforced in four places with four different wordings:

* ``store._reject_both_documents`` -> ``StoreError`` (add, disable, enable),
* ``scopes.toggle_skill`` -> an inline ``dst.is_file()`` check and a *different*
  ``StoreError`` message that also names the scope,
* ``archive.has_skill_document`` -> ``ArchiveError`` (tar and ZIP import),
* ``loader.conflicting_documents`` -> the predicate the first two disagreed
  about calling.

Measured before the change: the two toggle guards are **behaviourally
equivalent** for every reachable state (active-only, disabled-only, both,
neither, both-directions).  ``scopes`` reaches ``dst.is_file()`` only after
``src.is_file()`` is already true, so ``src and dst`` collapses to ``dst``.
They differed in *message* (scope named vs not) and in *mechanism*
(``loader`` predicate vs raw ``Path.is_file()``) -- a duplicated guard that
could drift, not one that had drifted into a different verdict.  Two real
defects did fall out, and both are pinned here:

* the scope-naming diagnostic existed in only one of the two toggles, so the
  store toggle could not report *which* physical copy was ambiguous;
* ``scopes.sync_skill`` copied an already-mixed source tree verbatim into the
  destination, so ``sync`` *created* the very state every other path refuses
  to install, and the next toggle of the destination then refused forever.

Run:  python3 -m unittest tests.test_one_document_invariant -v
"""

from __future__ import annotations

import io
import json
import os
import re
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from skillsmgr import loader, scopes
from skillsmgr.store import SkillNotFound, Store, StoreError

ACTIVE = "SKILL.md"
DISABLED = "SKILL.md.disabled"

#: The one wording both toggles now emit.  Pinned as a literal so a future edit
#: cannot silently re-split the two messages; ``test_the_two_toggle_messages_
#: share_one_template`` asserts both call sites derive from this template.
EXPECTED_MESSAGE = (
    "skill '{name}' has both SKILL.md and SKILL.md.disabled{scope_clause}; "
    "remove one of the two documents first"
)


def _doc(name: str) -> str:
    return f"---\nname: {name}\ndescription: probe document\n---\n\nbody\n"


class InvariantHomeTestCase(unittest.TestCase):
    """Isolated HOME *and* data root per test.

    Both matter: without the isolated HOME the scope layer walks the
    developer's real ``~/.claude`` / ``~/.codex`` / ``~/.gemini`` trees, which
    is both a leak and the source of the multi-second flake that
    docs/24 §D3-4 recorded.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._saved = {
            key: os.environ.get(key)
            for key in ("SKILLS_MANAGER_DATA", "XDG_DATA_HOME", "HOME")
        }
        self.addCleanup(self._restore_env)
        os.environ["HOME"] = str(self.root / "home")
        os.environ["SKILLS_MANAGER_DATA"] = str(self.root / "data")
        (self.root / "home").mkdir(parents=True, exist_ok=True)
        self.store = Store()
        scopes.set_global_store(self.store)
        self.addCleanup(scopes.set_global_store, None)
        self.store.init_db()

    def _restore_env(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # -- fixtures -------------------------------------------------------
    def _global_dir(self, name: str) -> Path:
        d = self.store.skills_dir / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _mixed_global(self, name: str) -> Path:
        d = self._global_dir(name)
        (d / ACTIVE).write_text(_doc(name), encoding="utf-8")
        (d / DISABLED).write_text(_doc(name), encoding="utf-8")
        self.store.resync()
        return d

    def _mixed_scope(self, scope_id: str, name: str) -> Path:
        scopes.create_skill(scope_id, name, "probe document")
        d = Path(scopes._scope_by_id(scope_id).base) / name
        (d / DISABLED).write_text(_doc(name), encoding="utf-8")
        return d


class TestSharedEnforcementPoint(InvariantHomeTestCase):
    """The predicate and the raise have exactly one home."""

    def test_the_predicate_lives_in_loader_only(self):
        """``loader.conflicting_documents`` is the single predicate.

        The audit's suggestion to move the guard into ``path_safety`` is not
        possible: that module raises only ``ValueError``, knows nothing of
        ``StoreError``, and ``store.py`` imports it at module level -- a raise
        there would need ``path_safety -> store`` while ``store -> path_safety``
        already exists, i.e. a real cycle.
        """
        self.assertTrue(callable(loader.conflicting_documents))
        self.assertTrue(loader.conflicting_documents(self._mixed_global("d1")))
        self.assertFalse(loader.conflicting_documents(self._global_dir("d2")))

    def test_both_toggles_route_through_the_one_predicate(self):
        """Neither toggle re-implements the condition.

        RED-FIRST: before the change ``scopes.toggle_skill`` called
        ``Path.is_file()`` inline, so patching the shared predicate to answer
        ``False`` left the scope toggle still refusing.
        """
        self._mixed_scope("agents", "probed")

        calls: list[Path] = []
        original = loader.conflicting_documents

        def counting(skill_dir: Path) -> bool:
            calls.append(Path(skill_dir))
            return original(skill_dir)

        loader.conflicting_documents = counting
        self.addCleanup(setattr, loader, "conflicting_documents", original)

        with self.assertRaises(StoreError):
            scopes.toggle_skill("agents", "probed", enable=False)
        self.assertTrue(calls, "scope toggle did not consult the shared predicate")

        calls.clear()
        self._mixed_global("probedg")
        with self.assertRaises(StoreError):
            self.store.disable("probedg")
        self.assertTrue(calls, "store toggle did not consult the shared predicate")

    def test_no_second_copy_of_the_condition_in_source(self):
        """A structural pin: the refusal message is written once.

        The repository has shipped this defect class twice (five hand-copied
        observed-state predicates in the frontend; two upload paths disagreeing
        about the same unsafe-part rule).  A test that only pins behaviour
        cannot catch the *next* copy, so this one reads the source.
        """
        root = Path(__file__).resolve().parent.parent / "skillsmgr"
        fragment = "remove one of the two documents first"
        hits = [
            p.name
            for p in sorted(root.glob("*.py"))
            if fragment in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(
            hits,
            ["loader.py"],
            f"the one-document refusal message must be written in one place, found in {hits}",
        )

    def test_loader_raises_the_public_store_error(self):
        """The shared guard raises ``StoreError`` -- not a new class.

        A new exception class is a contract change: REST maps ``StoreError`` to
        400 and the CLI to exit 1, and neither knows a subclass.
        """
        d = self._mixed_global("cls")
        with self.assertRaises(StoreError):
            loader.reject_conflicting_documents(d, "cls")

    def test_the_shared_guard_is_a_noop_for_every_other_state(self):
        for files, expected in (
            ([ACTIVE], False),
            ([DISABLED], False),
            ([ACTIVE, DISABLED], True),
            ([], False),
        ):
            with self.subTest(files=files):
                d = self._global_dir("s" + "".join(str(len(f)) for f in files))
                for f in files:
                    (d / f).write_text(_doc("s"), encoding="utf-8")
                if expected:
                    with self.assertRaises(StoreError):
                        loader.reject_conflicting_documents(d, "s")
                else:
                    self.assertIsNone(
                        loader.reject_conflicting_documents(d, "s")
                    )


class TestBothMessageShapesArePreserved(InvariantHomeTestCase):
    """One template, two shapes -- neither may be silently merged away.

    The scope clause is real diagnostic value: a user with the same skill in
    seven agent roots needs to know *which* copy is ambiguous.  Dropping it
    would make the two wordings identical and lose that.
    """

    def _template(self, name: str, scope_id: str | None) -> str:
        clause = f" in scope '{scope_id}'" if scope_id else ""
        return EXPECTED_MESSAGE.format(name=name, scope_clause=clause)

    def test_the_two_toggle_messages_share_one_template(self):
        """Both messages are the one template with/without the scope clause."""
        self.assertEqual(
            self._template("x", None),
            "skill 'x' has both SKILL.md and SKILL.md.disabled; "
            "remove one of the two documents first",
        )
        self.assertEqual(
            self._template("x", "agents"),
            "skill 'x' has both SKILL.md and SKILL.md.disabled in scope "
            "'agents'; remove one of the two documents first",
        )

    def test_the_store_toggle_message_does_not_name_a_scope(self):
        d = self._mixed_global("storem")
        for enable in (False, True):
            with self.subTest(enable=enable):
                call = (
                    self.store.enable if enable else self.store.disable
                )
                with self.assertRaises(StoreError) as ctx:
                    call("storem")
                self.assertEqual(str(ctx.exception), self._template("storem", None))

    def test_the_scope_toggle_message_names_the_scope(self):
        for scope_id in ("agents", "claude-code", "gemini"):
            with self.subTest(scope=scope_id):
                d = self._mixed_scope(scope_id, "scopem")
                for enable in (False, True):
                    with self.subTest(enable=enable):
                        with self.assertRaises(StoreError) as ctx:
                            scopes.toggle_skill(scope_id, "scopem", enable=enable)
                        self.assertEqual(
                            str(ctx.exception),
                            self._template("scopem", scope_id),
                        )
                        # pinned behaviour: the refusal is total, and the
                        # documents are still both there afterwards.
                        self.assertTrue((d / ACTIVE).is_file())
                        self.assertTrue((d / DISABLED).is_file())

    def test_add_still_refuses_a_mixed_source_with_the_store_wording(self):
        src = Path(tempfile.mkdtemp()) / "mixed"
        src.mkdir()
        (src / ACTIVE).write_text(_doc("mixed"), encoding="utf-8")
        (src / DISABLED).write_text(_doc("mixed"), encoding="utf-8")
        with self.assertRaises(StoreError) as ctx:
            self.store.add(src)
        self.assertEqual(str(ctx.exception), self._template("mixed", None))
        self.assertFalse((self.store.skills_dir / "mixed").exists())


class TestBothTogglesAgreeOnEveryReachableState(InvariantHomeTestCase):
    """The equivalence that was *measured*, now pinned.

    Before the change the two guards were equivalent in verdict for every
    reachable state; this test says so out loud so a future edit to either
    one that makes them diverge fails here rather than in a user's data
    directory.
    """

    def _verdict(self, files, enable, in_scope, name):
        """Build *files* exactly in one root and return the toggle's verdict.

        The same skill ``name`` is used on both sides of a comparison because
        the two roots are disjoint, so the messages are directly comparable.
        """
        if in_scope:
            scopes.create_skill("agents", name, "probe document")
            d = Path(scopes._scope_by_id("agents").base) / name
        else:
            d = self._global_dir(name)
        # create_skill always writes SKILL.md, so start from a known-empty
        # directory and place exactly the documents under test.
        for f in (ACTIVE, DISABLED):
            if (d / f).exists():
                (d / f).unlink()
        for f in files:
            (d / f).write_text(_doc(name), encoding="utf-8")
        self.store.resync()
        call = (
            (lambda: scopes.toggle_skill("agents", name, enable=enable))
            if in_scope
            else (
                lambda: self.store.enable(name)
                if enable
                else self.store.disable(name)
            )
        )
        try:
            call()
        except StoreError as exc:
            return ("StoreError", str(exc))
        except SkillNotFound as exc:
            return ("SkillNotFound", str(exc))
        return ("ok", "")

    def test_store_and_scope_toggles_agree_for_every_state(self):
        for files in ([ACTIVE], [DISABLED], [ACTIVE, DISABLED], []):
            for enable in (False, True):
                tag = "".join("a" if f == ACTIVE else "d" for f in files) or "none"
                flag = "on" if enable else "off"
                name = f"probe-{tag}-{flag}"
                with self.subTest(files=files, enable=enable):
                    gs = self._verdict(files, enable, False, name)
                    ss = self._verdict(files, enable, True, name)
                    self.assertEqual(
                        gs[0], ss[0], f"verdict class differs for {files}/{enable}"
                    )
                    if set(files) == {ACTIVE, DISABLED}:
                        # The invariant's own refusal: same verdict, and the
                        # only difference is the scope clause.  Pinned exactly.
                        self.assertEqual(gs[0], "StoreError")
                        self.assertEqual(
                            ss[1].replace(" in scope 'agents'", ""), gs[1]
                        )
                    elif gs[0] in ("StoreError", "SkillNotFound"):
                        # The *other* refusals (``not installed`` / ``already
                        # enabled``) carry a scope clause on both sides and
                        # always did -- that is a separate pre-existing
                        # message, not this invariant, so only the verdict
                        # class is compared here.
                        self.assertEqual(
                            ss[1].replace(" in scope 'agents'", ""), gs[1]
                        )


class TestSyncCannotCreateTheStateEveryOtherPathRefuses(InvariantHomeTestCase):
    """RED-FIRST: ``sync_skill`` copied a mixed source verbatim.

    ``Store.add`` refuses a mixed source (STORE-3) and both archives refuse a
    mixed member, on the reasoning that the next toggle would destroy a
    document.  ``sync_skill`` copied the tree with ``copytree(symlinks=True)``
    and no check, so ``sync`` *produced* the mixed state -- and the
    destination's toggle then refused forever, with no route back through
    sync because the mixed source was still there.
    """

    def _mixed_source_in_agents(self, name: str) -> Path:
        src = Path(scopes._scope_by_id("agents").base) / name
        src.mkdir(parents=True, exist_ok=True)
        (src / ACTIVE).write_text(_doc(name), encoding="utf-8")
        (src / DISABLED).write_text(_doc(name), encoding="utf-8")
        return src

    def test_sync_refuses_a_mixed_source(self):
        self._mixed_source_in_agents("mixedsrc")
        with self.assertRaises(StoreError) as ctx:
            scopes.sync_skill("mixedsrc", "agents", ["claude-code"], force=True)
        self.assertIn("both SKILL.md and SKILL.md.disabled", str(ctx.exception))

    def test_sync_does_not_land_a_mixed_directory_in_the_target(self):
        self._mixed_source_in_agents("mixedsrc2")
        try:
            scopes.sync_skill("mixedsrc2", "agents", ["claude-code"], force=True)
        except StoreError:
            pass
        dest = Path(scopes._scope_by_id("claude-code").base) / "mixedsrc2"
        self.assertFalse(
            dest.is_dir() and (dest / ACTIVE).is_file() and (dest / DISABLED).is_file(),
            "sync landed a mixed-document directory in the target scope",
        )

    def test_sync_still_copies_a_clean_skill(self):
        """The guard must not break the ordinary path."""
        scopes.create_skill("agents", "clean", "probe document")
        out = scopes.sync_skill("clean", "agents", ["claude-code"], force=True)
        self.assertIn("claude-code", out["synced"])
        dest = Path(scopes._scope_by_id("claude-code").base) / "clean"
        self.assertTrue((dest / ACTIVE).is_file())
        self.assertFalse((dest / DISABLED).exists())


class TestImportStillRefusesAMixedMember(InvariantHomeTestCase):
    """``archive`` keeps its own ``ArchiveError``; the store still says StoreError.

    This is a pin, not a change: the archive wording is deliberately left
    alone because ``archive`` raises ``ArchiveError`` and has no knowledge of
    ``StoreError`` -- unifying it would mean an import-cycle-inducing import
    or a contract change.  What must not happen is the store surfacing a raw
    ``ArchiveError``.
    """

    def _tar(self, names, name="imp"):
        path = Path(tempfile.mkdtemp()) / "a.tar.gz"
        manifest = {
            "app": "skills-mgr",
            "version": "1.0.2",
            "created": "2026-10-06T00:00:00Z",
            "full": False,
            "skills": [
                {
                    "name": name,
                    "description": "probe",
                    "license": None,
                    "version": None,
                    "category": "uncategorized",
                    "content_hash": None,
                }
            ],
        }
        with tarfile.open(path, "w:gz") as tf:
            for fn in names:
                payload = _doc(name).encode("utf-8")
                info = tarfile.TarInfo(f"skills/{name}/{fn}")
                info.size = len(payload)
                tf.addfile(info, io.BytesIO(payload))
            blob = json.dumps(manifest).encode("utf-8")
            info = tarfile.TarInfo("manifest.json")
            info.size = len(blob)
            tf.addfile(info, io.BytesIO(blob))
        return path

    def test_tar_import_refuses_a_mixed_skill_as_store_error(self):
        with self.assertRaises(StoreError) as ctx:
            self.store.import_(self._tar([ACTIVE, DISABLED]))
        self.assertIn("both enabled and disabled documents", str(ctx.exception))
        self.assertFalse((self.store.skills_dir / "imp").exists())

    def test_zip_import_refuses_a_mixed_skill_as_store_error(self):
        path = Path(tempfile.mkdtemp()) / "a.zip"
        manifest = json.dumps(
            {
                "app": "skills-mgr",
                "version": "1.0.2",
                "created": "2026-10-06T00:00:00Z",
                "full": False,
                "skills": [
                    {
                        "name": "imp",
                        "description": "probe",
                        "license": None,
                        "version": None,
                        "category": "uncategorized",
                        "content_hash": None,
                    }
                ],
            }
        )
        with zipfile.ZipFile(path, "w") as zf:
            for fn in (ACTIVE, DISABLED):
                zf.writestr(f"skills/imp/{fn}", _doc("imp"))
            zf.writestr("manifest.json", manifest)
        with self.assertRaises(StoreError) as ctx:
            self.store.import_(path)
        self.assertIn("both enabled and disabled documents", str(ctx.exception))
        self.assertFalse((self.store.skills_dir / "imp").exists())


class TestDoctorStillReportsTheDrift(InvariantHomeTestCase):
    """Refusing at the write paths must not stop ``doctor`` reporting it.

    A mixed directory can still be produced outside the tool (a hand edit, a
    restore from another machine), so the drift report is the recovery route.
    """

    def test_doctor_still_lists_a_conflicting_directory(self):
        self._mixed_global("drift")
        report = self.store.doctor()
        self.assertIn("drift", report["conflicting_documents"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()