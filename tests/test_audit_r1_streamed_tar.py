"""R1 / S1 (docs/28): tar caps apply while reading, not after ``getmembers()``.

A 13 KB bz2 of repeated headers once reached 373 MB RSS and 49 s, because
``archive.validate_members`` listed every header before the 200-member and
expanded-size caps applied.  These tests pin a *bounded* cost — peak traced
memory and wall-clock — rather than a mechanism, so they hold whichever way the
walk is implemented.
"""

from __future__ import annotations

import bz2
import gzip
import io
import lzma
import os
import shutil
import tarfile
import tempfile
import time
import tracemalloc
import unittest
from pathlib import Path

from skillsmgr.store import Store, StoreError

PEAK_BUDGET = 12 * 1024 * 1024  # bytes of traced allocation during the import
TIME_BUDGET = 10.0  # seconds; generous for slow CI runners


def _dir_header(name: str) -> bytes:
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    return info.tobuf(tarfile.USTAR_FORMAT)


class StreamedTarCaps(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="r1-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.store = Store(self.tmp / "data")
        self.store.init_db()

    def _measure(self, archive: Path) -> tuple[Exception | None, int, float]:
        tracemalloc.start()
        started = time.monotonic()
        error: Exception | None = None
        try:
            self.store.import_(archive)
        except Exception as exc:  # noqa: BLE001 - the type is asserted by callers
            error = exc
        elapsed = time.monotonic() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return error, peak, elapsed

    def test_many_headers_stop_at_the_member_cap(self) -> None:
        archive = self.tmp / "many.tar.bz2"
        with bz2.open(archive, "wb", compresslevel=9) as out:
            out.write(_dir_header("skills/"))
            for index in range(40_000):
                out.write(_dir_header(f"skills/s{index}/"))
            out.write(b"\0" * 1024)
        self.assertLess(archive.stat().st_size, 512 * 1024)
        error, peak, elapsed = self._measure(archive)
        self.assertIsInstance(error, StoreError)
        self.assertIn("too many members", str(error))
        self.assertLess(peak, PEAK_BUDGET, f"peak traced memory {peak} bytes")
        self.assertLess(elapsed, TIME_BUDGET)

    def test_oversized_pax_header_is_refused_before_it_is_read(self) -> None:
        archive = self.tmp / "pax.tar.gz"
        payload = 64 * 1024 * 1024
        info = tarfile.TarInfo("pax")
        info.type = tarfile.XHDTYPE
        info.size = payload
        chunk = b"\0" * (1024 * 1024)
        with gzip.open(archive, "wb", compresslevel=1) as out:
            out.write(info.tobuf(tarfile.USTAR_FORMAT))
            for _ in range(payload // len(chunk)):
                out.write(chunk)
            out.write(b"\0" * 1024)
        error, peak, elapsed = self._measure(archive)
        self.assertIsInstance(error, StoreError)
        self.assertLess(peak, PEAK_BUDGET, f"peak traced memory {peak} bytes")
        self.assertLess(elapsed, TIME_BUDGET)

    def test_corrupt_bzip2_is_a_clean_store_error(self) -> None:
        archive = self.tmp / "bad.tar.bz2"
        good = bz2.compress(_dir_header("skills/") + b"\0" * 1024)
        archive.write_bytes(good[:20] + b"\xff" * 64)
        with self.assertRaises(StoreError):
            self.store.import_(archive)

    def test_corrupt_xz_is_a_clean_store_error(self) -> None:
        archive = self.tmp / "bad.tar.xz"
        good = lzma.compress(_dir_header("skills/") + b"\0" * 1024)
        archive.write_bytes(good[:16] + b"\x00" * 64)
        with self.assertRaises(StoreError):
            self.store.import_(archive)

    def test_valid_exports_still_import_in_every_compression(self) -> None:
        self.store.create("alpha", "Use when testing streamed tar imports.")
        exported = self.store.export(self.tmp / "out.tar.gz")
        plain = gzip.decompress(Path(exported).read_bytes())
        variants = {
            "plain.tar": plain,
            "copy.tar.gz": gzip.compress(plain),
            "copy.tar.bz2": bz2.compress(plain),
            "copy.tar.xz": lzma.compress(plain),
        }
        for filename, data in variants.items():
            with self.subTest(filename=filename):
                target = Store(self.tmp / f"data-{filename}")
                target.init_db()
                path = self.tmp / filename
                path.write_bytes(data)
                result = target.import_(path)
                self.assertEqual(result["imported"], ["alpha"])
                self.assertEqual(target.get("alpha")["name"], "alpha")

    def test_member_payload_past_the_expanded_cap_is_refused(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            for index in range(3):
                info = tarfile.TarInfo(f"skills/s{index}/blob")
                info.size = 7 * 1024 * 1024
                tar.addfile(info, io.BytesIO(os.urandom(16) * (info.size // 16)))
        archive = self.tmp / "big.tar.gz"
        archive.write_bytes(gzip.compress(buffer.getvalue(), compresslevel=1))
        with self.assertRaises(StoreError) as ctx:
            self.store.import_(archive)
        self.assertRegex(str(ctx.exception), "expanded size|layout|directory")


if __name__ == "__main__":
    unittest.main()
