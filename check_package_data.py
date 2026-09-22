#!/usr/bin/env python3
"""Verify that built distributions contain the complete web UI.

This repository check intentionally has no third-party Python imports.  It uses
``python -m build`` when that optional build tool is available, inspects the
fresh wheel and sdist in a temporary directory, and can optionally install each
artifact into a fresh temporary virtual environment.  Missing build tooling is
reported as ``UNAVAILABLE`` rather than being mistaken for a passing packaging
check.  ``--require-build`` turns that report into a non-zero exit status for
release jobs that require packaging coverage.

Independently of the build tool, the check always verifies that the checked-in
vendored Vue bundle is the recorded upstream artifact (SEC-9): that file runs
same-origin with access to every local REST endpoint, so its integrity must not
depend on optional tooling being installed.
"""

from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from dataclasses import dataclass
from typing import Mapping


ROOT = Path(__file__).resolve().parent
WEBUI_ROOT = Path("skillsmgr") / "webui"
VUE_MEMBER = "skillsmgr/webui/static/vendor/vue.global.prod.js"

#: SEC-9: the vendored bundle executes same-origin with access to every local
#: REST endpoint, including all mutations, and a 158 KB minified blob cannot be
#: reviewed by reading its diff.  Recording the exact upstream artifact here
#: turns any change to that file into a deliberate, reviewable one-line edit
#: instead of an invisible one.  Verified against the upstream file on
#: 2026-09-12: the payload is byte-identical to what the URL below serves.
#: Bumping Vue means updating all four values together, in one commit.
VUE_VERSION = "3.5.13"
VUE_UPSTREAM_URL = "https://unpkg.com/vue@3.5.13/dist/vue.global.prod.js"
VUE_SHA256 = "c459ba7cc8db65c982589fa5d64c7ff478877e8e5b0fd75683207cec6a4e89e8"
VUE_SIZE = 157924


class BuildUnavailable(RuntimeError):
    """The optional package build tool cannot be run in this environment."""


class BuildFailed(RuntimeError):
    """The build tool ran but failed to produce distributions."""


@dataclass(frozen=True)
class ArchiveReport:
    """Deterministic package-data facts collected from one archive."""

    path: Path
    kind: str
    webui_members: tuple[str, ...]
    vue_size: int
    license_expression: str = ""
    license_files: tuple[str, ...] = ()


def verify_vendored_vue(payload: bytes, *, source: str) -> int:
    """Assert a vendored Vue payload is the recorded upstream artifact (SEC-9).

    Returns the payload size so callers can report it.  Raises ``AssertionError``
    with an actionable message when the bytes differ, so the gate fails loudly
    instead of accepting an unreviewable replacement of a file that runs with
    full access to the local REST API.
    """

    digest = hashlib.sha256(payload).hexdigest()
    if digest != VUE_SHA256:
        raise AssertionError(
            f"{source}: vendored Vue payload does not match the recorded upstream artifact "
            f"{VUE_UPSTREAM_URL} (expected sha256 {VUE_SHA256}, got {digest}); a deliberate "
            "vendor bump must update VUE_VERSION/VUE_UPSTREAM_URL/VUE_SHA256/VUE_SIZE in "
            "check_package_data.py in the same commit"
        )
    if VUE_VERSION.encode("ascii") not in payload:
        raise AssertionError(
            f"{source}: vendored Vue payload does not embed the recorded version {VUE_VERSION}"
        )
    if len(payload) != VUE_SIZE:
        raise AssertionError(
            f"{source}: vendored Vue payload is {len(payload)} bytes, recorded size is {VUE_SIZE}"
        )
    return len(payload)


def verify_vendored_bundle(project_root: Path = ROOT) -> int:
    """Verify the checked-in vendored bundle in the source tree (SEC-9).

    This runs even when the optional build tooling is missing — the default
    local outcome of this check is otherwise ``UNAVAILABLE``, which would leave
    the bundle unverified on every ordinary run.
    """

    path = project_root / VUE_MEMBER
    if not path.is_file():
        raise AssertionError(f"missing vendored Vue source file: {VUE_MEMBER}")
    return verify_vendored_vue(path.read_bytes(), source=VUE_MEMBER)


def expected_webui_members(project_root: Path = ROOT) -> tuple[str, ...]:
    """Return the sorted web UI files that package-data must include."""

    webui = project_root / WEBUI_ROOT
    if not webui.is_dir():
        raise AssertionError(f"missing web UI source directory: {webui}")
    files = sorted(
        "skillsmgr/webui/" + path.relative_to(webui).as_posix()
        for path in webui.rglob("*")
        if path.is_file()
    )
    if VUE_MEMBER not in files:
        raise AssertionError(f"missing vendored Vue source file: {VUE_MEMBER}")
    return tuple(files)


def _canonical_member(name: str, kind: str) -> str | None:
    """Map wheel/sdist member names to repository-relative package names.

    Every regular member of an sdist is kept, with the single
    ``<name>-<version>/`` root component removed.  Keeping non-``skillsmgr/``
    members visible is the point: the forbidden-member policy exists to catch a
    build that ships ``tests/``, ``docs/`` or an ``.env``, and an sdist carrying
    them used to be dropped here before that policy ever saw it (SEC-13).
    """

    name = PurePosixPath(name).as_posix()
    if kind == "wheel":
        return name
    _root, sep, rest = name.partition("/")
    return rest if sep else name


def read_archive_files(path: Path) -> tuple[str, Mapping[str, bytes]]:
    """Read regular archive files as canonical names and bytes."""

    if path.name.endswith(".whl"):
        kind = "wheel"
        with zipfile.ZipFile(path) as archive:
            files = {
                canonical: archive.read(name)
                for name in archive.namelist()
                if not name.endswith("/")
                for canonical in [_canonical_member(name, kind)]
                if canonical is not None
            }
    elif path.name.endswith(".tar.gz") or path.name.endswith(".tar.bz2") or path.name.endswith(".tar.xz"):
        kind = "sdist"
        with tarfile.open(path, mode="r:*") as archive:
            files = {}
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                canonical = _canonical_member(member.name, kind)
                if canonical is None:
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise AssertionError(f"cannot read archive member: {member.name}")
                files[canonical] = extracted.read()
    else:
        raise AssertionError(f"unsupported distribution archive: {path.name}")
    return kind, files


#: BUG-13: member shapes that must never appear in a published artifact.  The
#: web UI comparison only looked at ``skillsmgr/webui/``, so a build that
#: accidentally shipped the test suite, the docs, an environment file or a
#: database was never flagged.
_FORBIDDEN_MEMBER_PARTS = (
    "tests/",
    "docs/",
    ".git/",
    ".github/",
    "build/",
    "dist/",
    "__pycache__/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".pytest_cache/",
)
_FORBIDDEN_MEMBER_SUFFIXES = (".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".env", ".pem", ".key")
_FORBIDDEN_MEMBER_NAMES = (".env", ".netrc", ".secrets")


def unexpected_members(files: Mapping[str, bytes]) -> list[str]:
    """Return archive members that must never be published (BUG-13).

    The comparison is by member *shape*, so it holds for both the wheel and the
    sdist and does not need to enumerate every legitimate metadata file.
    """
    offenders: list[str] = []
    for name in files:
        lowered = name.lower()
        parts = lowered.split("/")
        if any(part in lowered for part in _FORBIDDEN_MEMBER_PARTS):
            offenders.append(name)
            continue
        if lowered.endswith(_FORBIDDEN_MEMBER_SUFFIXES):
            offenders.append(name)
            continue
        if parts[-1] in _FORBIDDEN_MEMBER_NAMES:
            offenders.append(name)
    return sorted(offenders)


def _metadata_member(files: Mapping[str, bytes], kind: str, source: str) -> str:
    """Return the sole core-metadata member for an archive."""
    if kind == "wheel":
        candidates = sorted(name for name in files if name.endswith(".dist-info/METADATA"))
    else:
        candidates = sorted(name for name in files if name == "PKG-INFO")
    if len(candidates) != 1:
        raise AssertionError(
            f"{source} must contain exactly one core metadata file; found {candidates}"
        )
    return candidates[0]


def _license_members(files: Mapping[str, bytes], kind: str, declared: str) -> list[str]:
    """Find an artifact's license payload at its PEP 639 location."""
    if kind == "sdist":
        return [declared] if declared in files else []
    suffix = f".dist-info/licenses/{declared}"
    return sorted(name for name in files if name.endswith(suffix))


def verify_license_metadata(
    files: Mapping[str, bytes], kind: str, project_root: Path, source: str
) -> tuple[str, tuple[str, ...]]:
    """Verify PEP 639 metadata and exact LICENSE bytes without extraction."""
    license_path = project_root / "LICENSE"
    if not license_path.is_file():
        raise AssertionError("repository LICENSE file is missing")
    try:
        license_bytes = license_path.read_bytes()
        license_bytes.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise AssertionError(f"repository LICENSE must be readable UTF-8: {exc}") from exc

    metadata_name = _metadata_member(files, kind, source)
    metadata = BytesParser().parsebytes(files[metadata_name])
    expression = metadata.get("License-Expression")
    if expression != "MIT":
        raise AssertionError(f"{source} must declare License-Expression: MIT, got {expression!r}")
    declared = tuple(metadata.get_all("License-File") or ())
    if declared != ("LICENSE",):
        raise AssertionError(f"{source} must declare License-File: LICENSE, got {declared!r}")
    legacy = [value for value in metadata.get_all("Classifier") or () if value.startswith("License ::")]
    if legacy:
        raise AssertionError(f"{source} contains deprecated license classifier(s): {legacy}")
    members = _license_members(files, kind, declared[0])
    if len(members) != 1:
        raise AssertionError(f"{source} is missing its declared LICENSE artifact member")
    member = members[0]
    if files[member] != license_bytes:
        raise AssertionError(f"{source} LICENSE bytes differ from the repository LICENSE")
    return expression, (member,)


def inspect_archive(path: Path, project_root: Path = ROOT) -> ArchiveReport:
    """Assert exact web UI package-data coverage for one archive."""

    kind, files = read_archive_files(path)
    offenders = unexpected_members(files)
    if offenders:
        raise AssertionError(
            f"{path.name} ships members that must never be published: "
            + ", ".join(offenders[:5])
            + (f" (+{len(offenders) - 5} more)" if len(offenders) > 5 else "")
        )
    expected = expected_webui_members(project_root)
    actual = tuple(sorted(name for name in files if name.startswith("skillsmgr/webui/")))
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        details = []
        if missing:
            details.append(f"missing={missing}")
        if unexpected:
            details.append(f"unexpected={unexpected}")
        raise AssertionError(f"{path.name} web UI package-data mismatch: " + "; ".join(details))
    vue = files.get(VUE_MEMBER, b"")
    if not vue:
        raise AssertionError(f"{path.name} contains no vendored Vue payload: {VUE_MEMBER}")
    vue_size = verify_vendored_vue(vue, source=path.name)
    license_expression, license_files = verify_license_metadata(files, kind, project_root, path.name)
    return ArchiveReport(path, kind, actual, vue_size, license_expression, license_files)


def _build_error(result: subprocess.CompletedProcess[str]) -> RuntimeError:
    output = (result.stderr + "\n" + result.stdout).strip()
    if "No module named build" in output or "No module named 'build'" in output:
        return BuildUnavailable("python -m build is unavailable (install the optional 'build' tool)")
    return BuildFailed(f"python -m build failed with exit {result.returncode}:\n{output}")


def build_distributions(project_root: Path, output_dir: Path, python: str = sys.executable) -> tuple[Path, Path]:
    """Build exactly one wheel and one sdist into an empty output directory."""

    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError(f"build output directory must be empty: {output_dir}")
    result = subprocess.run(
        [python, "-m", "build", "--wheel", "--sdist", "--outdir", str(output_dir)],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise _build_error(result)
    wheels = sorted(output_dir.glob("*.whl"))
    sdists = sorted(output_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise BuildFailed(
            f"expected exactly one wheel and one sdist, found {len(wheels)} wheel(s) and {len(sdists)} sdist(s)"
        )
    return wheels[0], sdists[0]


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def clean_install(artifact: Path, temporary_root: Path) -> None:
    """Install one artifact offline into a fresh temporary virtualenv."""

    venv_dir = temporary_root / (artifact.stem.replace(".", "-") + "-venv")
    try:
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        raise BuildUnavailable(f"cannot create isolated virtualenv: {exc}") from exc
    python = _venv_python(venv_dir)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    if artifact.name.endswith(".tar.gz"):
        backend_probe = subprocess.run(
            [str(python), "-c", "import setuptools"],
            cwd=temporary_root,
            env=env,
            capture_output=True,
            text=True,
        )
        if backend_probe.returncode:
            raise BuildUnavailable(
                f"isolated sdist install backend unavailable for {artifact.name}: "
                f"{backend_probe.stderr.strip() or backend_probe.stdout.strip()}"
            )
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "--no-index", "--no-deps", "--no-build-isolation", str(artifact)],
        cwd=temporary_root,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        output = (result.stderr + "\n" + result.stdout).strip()
        if "No module named" in output or "No matching distribution" in output:
            raise BuildUnavailable(f"isolated install tooling unavailable for {artifact.name}: {output}")
        raise BuildFailed(f"isolated install failed for {artifact.name}:\n{output}")
    probe = (
        "from pathlib import Path; import skillsmgr; "
        "p=Path(skillsmgr.__file__).parent/'webui/static/vendor/vue.global.prod.js'; "
        "assert p.is_file() and p.stat().st_size > 0, p"
    )
    probe_result = subprocess.run([str(python), "-c", probe], cwd=temporary_root, env=env, capture_output=True, text=True)
    if probe_result.returncode:
        raise AssertionError(f"clean install probe failed for {artifact.name}: {probe_result.stderr.strip()}")


def run_check(project_root: Path = ROOT, *, install: bool = False, require_build: bool = False, dist_dir: Path | None = None) -> int:
    """Run the packaging check, returning a shell-friendly status code.

    When *dist_dir* is given, exactly one wheel and one sdist already present
    in that directory are inspected instead of invoking ``python -m build``.
    CI uses this to test the exact artifacts it will publish (build-once,
    test-exact-artifacts); local developers keep the default fresh-build
    behavior. Only ``--require-build`` makes unavailable tooling non-zero.
    """

    try:
        size = verify_vendored_bundle(project_root)
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        f"PASS: vendored Vue {VUE_VERSION} matches {VUE_UPSTREAM_URL} "
        f"(sha256 {VUE_SHA256}; {size} bytes)"
    )

    if dist_dir is not None:
        dist_dir = Path(dist_dir)
        wheels = sorted(dist_dir.glob("*.whl"))
        sdists = sorted(
            [path for pattern in ("*.tar.gz", "*.tar.bz2", "*.tar.xz") for path in dist_dir.glob(pattern)]
        )
        if len(wheels) != 1 or len(sdists) != 1:
            print(
                f"FAIL: --dist-dir must hold exactly one wheel and one sdist, "
                f"found {len(wheels)} wheel(s) and {len(sdists)} sdist(s) in {dist_dir}",
                file=sys.stderr,
            )
            return 1
        try:
            reports = [inspect_archive(wheels[0], project_root), inspect_archive(sdists[0], project_root)]
        except AssertionError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        for report in reports:
            print(
                f"PASS: {report.kind} {report.path.name} ({len(report.webui_members)} web UI files; "
                f"Vue {report.vue_size} bytes; {report.license_expression} license)"
            )
        if install:
            # Release jobs inspect exact artifacts and then install those exact
            # artifacts; a silently ignored --install would look like verified
            # installation without running one.
            with tempfile.TemporaryDirectory(prefix="skillsmgr-package-install-") as temp:
                temp_root = Path(temp)
                try:
                    for artifact in (wheels[0], sdists[0]):
                        clean_install(artifact, temp_root)
                        print(f"PASS: clean install {artifact.name}")
                except (BuildUnavailable, BuildFailed, AssertionError) as exc:
                    print(f"UNAVAILABLE: {exc}" if isinstance(exc, BuildUnavailable) else f"FAIL: {exc}", file=sys.stderr)
                    return 2 if isinstance(exc, BuildUnavailable) and not require_build else 1
        return 0
    with tempfile.TemporaryDirectory(prefix="skillsmgr-package-check-") as temp:
        temp_root = Path(temp)
        output_dir = temp_root / "dist"
        try:
            wheel, sdist = build_distributions(project_root, output_dir)
        except BuildUnavailable as exc:
            print(f"UNAVAILABLE: {exc}")
            print("Package-data coverage was not verified; no existing dist/ artifact was used.")
            return 2 if require_build else 0
        except (BuildFailed, AssertionError, ValueError) as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        try:
            reports = [inspect_archive(wheel, project_root), inspect_archive(sdist, project_root)]
        except AssertionError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        for report in reports:
            print(
                f"PASS: {report.kind} {report.path.name} ({len(report.webui_members)} web UI files; "
                f"Vue {report.vue_size} bytes; {report.license_expression} license)"
            )
        if install:
            try:
                for artifact in (wheel, sdist):
                    clean_install(artifact, temp_root)
                    print(f"PASS: clean install {artifact.name}")
            except (BuildUnavailable, BuildFailed, AssertionError) as exc:
                print(f"UNAVAILABLE: {exc}" if isinstance(exc, BuildUnavailable) else f"FAIL: {exc}", file=sys.stderr)
                return 2 if isinstance(exc, BuildUnavailable) and not require_build else 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--install", action="store_true", help="also install wheel and sdist into fresh temporary venvs")
    parser.add_argument("--require-build", action="store_true", help="return 2 when optional build tooling is unavailable")
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=None,
        help="inspect exactly one wheel + one sdist already in DIR instead of building (CI build-once artifact check)",
    )
    args = parser.parse_args(argv)
    return run_check(args.project_root.resolve(), install=args.install, require_build=args.require_build, dist_dir=args.dist_dir)


if __name__ == "__main__":
    raise SystemExit(main())
