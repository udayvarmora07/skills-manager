#!/usr/bin/env python3
"""Verify that built distributions contain the complete web UI.

This repository check intentionally has no third-party Python imports.  It uses
``python -m build`` when that optional build tool is available, inspects the
fresh wheel and sdist in a temporary directory, and can optionally install each
artifact into a fresh temporary virtual environment.  Missing build tooling is
reported as ``UNAVAILABLE`` rather than being mistaken for a passing packaging
check.  ``--require-build`` turns that report into a non-zero exit status for
release jobs that require packaging coverage.
"""

from __future__ import annotations

import argparse
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
    """Map wheel/sdist member names to repository-relative package names."""

    name = PurePosixPath(name).as_posix()
    if kind == "wheel":
        return name
    marker = "skillsmgr/"
    index = name.find(marker)
    return name[index:] if index >= 0 else None


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


def inspect_archive(path: Path, project_root: Path = ROOT) -> ArchiveReport:
    """Assert exact web UI package-data coverage for one archive."""

    kind, files = read_archive_files(path)
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
    return ArchiveReport(path, kind, actual, len(vue))


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


def run_check(project_root: Path = ROOT, *, install: bool = False, require_build: bool = False) -> int:
    """Run the packaging check, returning a shell-friendly status code."""

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
            print(f"PASS: {report.kind} {report.path.name} ({len(report.webui_members)} web UI files; Vue {report.vue_size} bytes)")
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
    args = parser.parse_args(argv)
    return run_check(args.project_root.resolve(), install=args.install, require_build=args.require_build)


if __name__ == "__main__":
    raise SystemExit(main())
