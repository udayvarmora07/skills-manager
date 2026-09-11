#!/usr/bin/env python3
"""Machine-check current documentation against repository source facts.

This is intentionally a repository check, not a new product CLI command.  It
uses only the Python standard library and local source files.  Historical docs
remain readable records; checks that describe the current product are limited
to the authoritative/current-doc set below.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"

# These docs describe the current contract.  In particular, do not apply
# current UI/command checks to the superseded GTK plan or append-only history.
CURRENT_DOCS = (
    "AGENTS.md",
    "README.md",
    "CONTRIBUTING.md",
    "docs/README.md",
    "docs/01-architecture.md",
    "docs/02-modules.md",
    "docs/03-cli-surface.md",
    "docs/04-store-api.md",
    "docs/07-context-strategy.md",
    "docs/08-web-ui.md",
    "docs/12-agent-root-discovery-2026-09-08.md",
    "docs/ADR-002-root-consumer-effective-state.md",
    "docs/ADR-003-registry-bridge-and-eval-harness.md",
    "docs/ADR-004-team-sharing-signed-bundles.md",
    "docs/SESSION-CONTEXT.md",
)
REQUIRED_DOCS = (
    "01-architecture.md",
    "02-modules.md",
    "03-cli-surface.md",
    "04-store-api.md",
    "06-progress-log.md",
    "07-context-strategy.md",
    "08-web-ui.md",
    "12-agent-root-discovery-2026-09-08.md",
    "ADR-002-root-consumer-effective-state.md",
    "README.md",
)


def _relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _current_paths(root: Path) -> list[Path]:
    return [root / name for name in CURRENT_DOCS]


def _all_markdown(root: Path) -> list[Path]:
    """Return markdown files, excluding generated VCS/artifact directories."""
    return sorted(
        path
        for path in root.rglob("*.md")
        if ".git" not in path.parts and ".autogit" not in path.parts and "dist" not in path.parts
    )


def check_required_docs(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_DOCS:
        path = root / "docs" / name if name != "README.md" else root / "docs" / name
        if not path.is_file():
            errors.append(f"missing required document: docs/{name}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].startswith("# "):
            errors.append(f"{_relative(path, root)}: missing H1 title")
        if not any(line.startswith("**Version") for line in lines[:20]):
            errors.append(f"{_relative(path, root)}: missing version line")
        if not any("AI manifest" in line for line in lines[:20]):
            errors.append(f"{_relative(path, root)}: missing AI manifest")
    return errors


def check_doc_links(root: Path = ROOT) -> list[str]:
    """Check every local ``@docs/name.md`` pointer, including historical docs."""
    errors: list[str] = []
    # Stop at whitespace or markdown delimiters, then remove an optional anchor.
    pointer_pattern = re.compile(r"@docs/([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.md)")
    for path in _all_markdown(root):
        text = path.read_text(encoding="utf-8")
        for raw_target in pointer_pattern.findall(text):
            target = raw_target.rstrip(".,;:`")
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target or not (root / "docs" / target).is_file():
                errors.append(f"{_relative(path, root)}: broken @docs/{raw_target}")
    return errors


def _parse_module_symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    symbols: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            symbols.update(target.id for target in targets if isinstance(target, ast.Name))
    return symbols


def check_documented_source_symbols(root: Path = ROOT) -> list[str]:
    """Check qualified symbols and explicit source paths in current docs.

    Unqualified prose is deliberately not guessed.  Only ``Store.method`` and
    ``module.symbol`` references have an unambiguous source owner, while
    ``skillsmgr/foo.py`` references are checked as paths.
    """
    errors: list[str] = []
    docs = [(root / name) for name in CURRENT_DOCS]
    store_path = root / "skillsmgr" / "store.py"
    if store_path.is_file():
        store_symbols = _parse_module_symbols(store_path)
        tree = ast.parse(store_path.read_text(encoding="utf-8"))
        store_class = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Store"), None)
        store_methods = {
            n.name for n in (store_class.body if store_class else [])
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        store_symbols |= store_methods
    else:
        store_symbols = set()
        store_methods = set()

    module_symbols: dict[str, set[str]] = {}
    package = root / "skillsmgr"
    for path in package.glob("*.py"):
        module_symbols[path.stem] = _parse_module_symbols(path)

    source_path_pattern = re.compile(r"`(skillsmgr/[A-Za-z0-9_]+\.py)`")
    store_ref_pattern = re.compile(r"\bStore\.([A-Za-z_]\w*)")
    # Only dotted references with a symbol after the module are checked; plain
    # ``foo.py`` source-path prose is handled by source_path_pattern above.
    module_ref_pattern = re.compile(
        r"(?<![A-Za-z0-9_/])(?:skillsmgr/)?(" + "|".join(sorted(module_symbols)) + r")\.(?!py\b)([A-Za-z_]\w*)"
    )
    for path in docs:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rel = _relative(path, root)
        for source_path in source_path_pattern.findall(text):
            if not (root / source_path).is_file():
                errors.append(f"{rel}: documented source path does not exist: {source_path}")
        for symbol in store_ref_pattern.findall(text):
            if symbol not in store_methods:
                errors.append(f"{rel}: documented source symbol does not exist: Store.{symbol}")
        for module, symbol in module_ref_pattern.findall(text):
            if symbol not in module_symbols[module]:
                errors.append(f"{rel}: documented source symbol does not exist: {module}.{symbol}")
    return errors


def _command_inventory(root: Path = ROOT) -> tuple[int, int, int, int]:
    """Return canonical top-level, nested, alias, and total parser names."""
    # Parser construction may live behind the stable cli.py compatibility
    # adapter. Inspect the dedicated parser module when present, while keeping
    # this check compatible with older checkouts that still colocate it.
    cli_path = root / "skillsmgr" / "cli_parser.py"
    if not cli_path.is_file():
        cli_path = root / "skillsmgr" / "cli.py"
    tree = ast.parse(cli_path.read_text(encoding="utf-8"), filename=str(cli_path))
    top_level = 0
    nested = 0
    aliases = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_parser" or not node.args:
            continue
        # ``sub.add_parser`` is the top-level command collection.  The three
        # ``*_sub.add_parser`` calls are nested actions; no runtime import is
        # needed, keeping this check deterministic and offline.
        receiver = node.func.value
        receiver_name = receiver.id if isinstance(receiver, ast.Name) else ""
        if receiver_name == "sub":
            top_level += 1
            for keyword in node.keywords:
                if keyword.arg == "aliases" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                    aliases += len(keyword.value.elts)
        elif receiver_name.endswith("_sub"):
            nested += 1
    return top_level, nested, aliases, top_level + nested + aliases


def check_current_claims(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    canonical, nested, aliases, total = _command_inventory(root)
    for path in _current_paths(root):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if "invocable names" in line]
        if not lines:
            continue
        line = lines[0]
        total_match = re.search(r"(\d+)\s+invocable\s+names?", line, re.IGNORECASE)
        top_match = re.search(r"(\d+)\s+top-level\s+commands?", line, re.IGNORECASE)
        nested_match = re.search(r"(\d+)\s+(?:subcommands?|`?trash`?/`?templates`?/`?db`?)", line, re.IGNORECASE)
        alias_match = re.search(r"(\d+)\s+(?:`[^`]+`(?:/|\s+))*aliases?", line, re.IGNORECASE)
        valid = (
            total_match is not None
            and top_match is not None
            and nested_match is not None
            and alias_match is not None
            and int(total_match.group(1)) == total
            and int(top_match.group(1)) == canonical
            and int(nested_match.group(1)) == nested
            and int(alias_match.group(1)) == aliases
        )
        if not valid:
            errors.append(f"{_relative(path, root)}: command inventory disagrees with cli.py ({canonical}+{nested}+{aliases}={total})")

    architecture = root / "docs/01-architecture.md"
    if architecture.is_file():
        text = architecture.read_text(encoding="utf-8")
        if "skills-manager.db" not in text or "skills.db`" in text:
            errors.append("docs/01-architecture.md: database path disagrees with store.py")
        if "local web UI" not in text or "skillsmgr/webapp.py" not in text:
            errors.append("docs/01-architecture.md: current web architecture is missing")
        if "GTK4, in progress" in text or "GUI toolkit: GTK4" in text:
            errors.append("docs/01-architecture.md: stale GTK architecture claim")

    gui_plan = root / "docs/05-gui-plan.md"
    if gui_plan.is_file():
        text = gui_plan.read_text(encoding="utf-8")
        if "SUPERSEDED" not in text or "historical" not in text.lower():
            errors.append("docs/05-gui-plan.md: superseded GTK plan is not marked historical")

    cli_doc = root / "docs/03-cli-surface.md"
    if cli_doc.is_file():
        text = cli_doc.read_text(encoding="utf-8")
        if "webui" not in text or "alias" not in text or "gui" not in text:
            errors.append("docs/03-cli-surface.md: current webui/gui alias contract is missing")
        if "127.0.0.1:8765" not in text and "127.0.0.1" not in text:
            errors.append("docs/03-cli-surface.md: current web UI bind/default-port claim is missing")

    web_doc = root / "docs/08-web-ui.md"
    if web_doc.is_file():
        text = web_doc.read_text(encoding="utf-8")
        if "skillsmgr/webapp.py" not in text or "skillsmgr/webui/" not in text:
            errors.append("docs/08-web-ui.md: current web UI source paths are missing")
        if "127.0.0.1" not in text or "8765" not in text:
            errors.append("docs/08-web-ui.md: current loopback/default-port claim is missing")
    return errors


def _package_version(root: Path) -> str | None:
    init = root / "skillsmgr" / "__init__.py"
    if not init.is_file():
        return None
    tree = ast.parse(init.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__" and isinstance(node.value, ast.Constant):
                    return node.value.value if isinstance(node.value.value, str) else None
    return None


def check_version_alignment(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    source_version = _package_version(root)
    pyproject = root / "pyproject.toml"
    project_version = None
    if pyproject.is_file():
        match = re.search(r"(?m)^version\s*=\s*[\"']([^\"']+)[\"']", pyproject.read_text(encoding="utf-8"))
        project_version = match.group(1) if match else None
    if source_version is None:
        errors.append("skillsmgr/__init__.py: missing string __version__")
    if project_version is None:
        errors.append("pyproject.toml: missing project version")
    if source_version and project_version and source_version != project_version:
        errors.append(f"version mismatch: skillsmgr.__version__={source_version!r}, pyproject project.version={project_version!r}")

    for name in ("docs/01-architecture.md", "docs/02-modules.md"):
        path = root / name
        if not path.is_file() or not source_version:
            continue
        text = path.read_text(encoding="utf-8")
        versions = re.findall(r"__version__\s*=\s*[\"']([^\"']+)[\"']", text)
        if any(version != source_version for version in versions):
            errors.append(f"{name}: documented __version__ disagrees with source ({source_version})")
    return errors


def _errors(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    errors.extend(check_required_docs(root))
    errors.extend(check_doc_links(root))
    errors.extend(check_documented_source_symbols(root))
    errors.extend(check_current_claims(root))
    errors.extend(check_version_alignment(root))

    settings = root / ".commandcode/settings.json"
    if settings.is_file() and "skillsmgr/gui.py" in settings.read_text(encoding="utf-8"):
        errors.append(".commandcode/settings.json: references deleted skillsmgr/gui.py")
    return errors


def run_checks(root: Path = ROOT) -> list[str]:
    """Return consistency errors; an empty list means the check passed."""
    return _errors(Path(root))


def main() -> int:
    errors = run_checks()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("DOCUMENTATION/SOURCE CONSISTENCY PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
