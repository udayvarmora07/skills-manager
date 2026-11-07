"""Contracts for the leaf exception module ``skillsmgr.errors`` (R15, part).

``skillsmgr.store`` used to define the exception hierarchy itself, so every
module that only needed to catch or raise one imported the entire Store.
Moving the classes into a leaf module breaks that coupling and the import
cycle, provided both spellings stay the same object.  These tests pin:

* re-export identity (``store.X is errors.X``),
* the subclass relationships,
* the routing attributes the web layer reads (``status``),
* a fresh interpreter importing only ``skillsmgr.errors`` never imports
  ``skillsmgr.store``.
"""

from __future__ import annotations

import pickle
import subprocess
import sys
import unittest
from pathlib import Path

import skillsmgr.errors as errors
import skillsmgr.store as store

ROOT = Path(__file__).resolve().parent.parent

EXCEPTION_NAMES = (
    "StoreError",
    "SkillNotFound",
    "LockTimeoutError",
    "StoreLayoutError",
)


class ReExportIdentityTests(unittest.TestCase):
    """Both import paths must name exactly the same classes."""

    def test_store_reexports_the_errors_module_classes(self) -> None:
        for name in EXCEPTION_NAMES:
            with self.subTest(name=name):
                self.assertIs(getattr(store, name), getattr(errors, name))

    def test_every_class_is_defined_in_the_leaf_module(self) -> None:
        for name in EXCEPTION_NAMES:
            with self.subTest(name=name):
                cls = getattr(errors, name)
                self.assertEqual(cls.__module__, "skillsmgr.errors")
                self.assertTrue(cls.__qualname__)

    def test_pickling_round_trips_after_the_move(self) -> None:
        for name in EXCEPTION_NAMES:
            with self.subTest(name=name):
                original = getattr(errors, name)("boom")
                restored = pickle.loads(pickle.dumps(original))
                self.assertIs(type(restored), type(original))
                self.assertEqual(str(restored), "boom")


class HierarchyTests(unittest.TestCase):
    """The inheritance and routing attributes must not have changed."""

    def test_subclass_relationships(self) -> None:
        self.assertTrue(issubclass(errors.StoreError, Exception))
        for name in ("SkillNotFound", "LockTimeoutError", "StoreLayoutError"):
            with self.subTest(name=name):
                self.assertTrue(issubclass(getattr(errors, name), errors.StoreError))

    def test_status_attributes(self) -> None:
        self.assertFalse(hasattr(errors.StoreError, "status"))
        self.assertFalse(hasattr(errors.SkillNotFound, "status"))
        self.assertEqual(errors.LockTimeoutError.status, 409)
        self.assertEqual(errors.StoreLayoutError.status, 404)

    def test_no_exception_carries_a_code_attribute(self) -> None:
        for name in EXCEPTION_NAMES:
            with self.subTest(name=name):
                self.assertFalse(hasattr(getattr(errors, name), "code"))


class LeafImportTests(unittest.TestCase):
    """Importing the exceptions must not drag in the Store module."""

    def test_importing_errors_does_not_import_store(self) -> None:
        code = (
            "import sys\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            "import skillsmgr.errors\n"
            "loaded = [m for m in sys.modules if m == 'skillsmgr.store']\n"
            "print('store' if loaded else 'clean')\n"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "clean", result.stderr)

    def test_errors_module_imports_nothing_from_the_package(self) -> None:
        source = (ROOT / "skillsmgr" / "errors.py").read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import skillsmgr", "from skillsmgr", "from .")):
                self.fail(f"leaf errors module imports the package: {stripped}")


if __name__ == "__main__":
    unittest.main()
