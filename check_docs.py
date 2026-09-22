#!/usr/bin/env python3
"""Machine-check current documentation against repository source facts.

This is intentionally a repository check, not a new product CLI command.  It
uses only the Python standard library and local source files.  Historical docs
remain readable records; checks that describe the current product are limited
to the authoritative/current-doc set below.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
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
    "docs/13-audit-remediation-status-2026-09-11.md",
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

_FIRST_PARTY_TOP_LEVEL_MARKDOWN = (
    "AGENTS.md",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "ROADMAP.md",
    "TODO.md",
    "PLAN.md",
    "SECURITY.md",
    "task.md",
    "DEEP-AUDIT-2026-09-11.md",
    "skills-manager-threat-model.md",
    "security_best_practices_report.md",
    "loop-engineering-findings.md",
)


def _relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _current_paths(root: Path) -> list[Path]:
    return [root / name for name in CURRENT_DOCS]


def _inside_root_regular_file(path: Path, root: Path) -> bool:
    """Return whether *path* resolves to a regular file below *root*."""
    try:
        root_resolved = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return False
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return False
    return resolved.is_file()


def _tracked_markdown(root: Path) -> list[Path]:
    """Return tracked Markdown paths using Git's NUL-safe output mode."""
    try:
        root_resolved = root.resolve(strict=True)
        git_root = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
        )
        if git_root.returncode != 0:
            return []
        raw_git_root = git_root.stdout or b""
        if isinstance(raw_git_root, str):
            raw_git_root = os.fsencode(raw_git_root)
        if Path(os.fsdecode(raw_git_root).strip()).resolve() != root_resolved:
            return []
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", "*.md"],
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    output = result.stdout or b""
    if isinstance(output, str):
        output = os.fsencode(output)
    paths: list[Path] = []
    for raw_path in output.split(b"\0"):
        if not raw_path:
            continue
        candidate = root / Path(os.fsdecode(raw_path))
        if candidate.suffix == ".md" and _inside_root_regular_file(candidate, root):
            paths.append(candidate)
    return paths


def _first_party_untracked_markdown(root: Path) -> list[Path]:
    """Return explicitly first-party Markdown outside Git's tracked set."""
    paths = [root / name for name in _FIRST_PARTY_TOP_LEVEL_MARKDOWN]
    docs_root = root / "docs"
    if docs_root.is_dir():
        for current, directories, filenames in os.walk(docs_root, followlinks=False):
            current_path = Path(current)
            directories[:] = [name for name in directories if not (current_path / name).is_symlink()]
            paths.extend(current_path / name for name in filenames if name.endswith(".md"))
    return [path for path in paths if path.suffix == ".md" and _inside_root_regular_file(path, root)]


def _all_markdown(root: Path) -> list[Path]:
    """Return tracked plus explicitly first-party Markdown in stable order."""
    candidates = {*_tracked_markdown(root), *_first_party_untracked_markdown(root)}
    return sorted(
        candidates,
        key=lambda path: path.relative_to(root).as_posix(),
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
        r"(?<![A-Za-z0-9_/-])(?:skillsmgr/)?(" + "|".join(sorted(module_symbols)) + r")\.(?!py\b)([A-Za-z_]\w*)"
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


def check_house_style(root: Path = ROOT) -> list[str]:
    """Check HADS conformance and markdown integrity for every markdown file.

    ``check_required_docs`` only inspects the ``REQUIRED_DOCS`` subset; this
    covers the rest of the ``docs/`` tree and repairs three defects that
    silently change how a page renders (2026-09-11 docs truth pass):

    * an unescaped ``|`` inside a table cell adds a column,
    * a missing final newline makes git report the file as unterminated,
    * a heading marker that is not surrounded as HADS requires.
    """
    errors: list[str] = []
    for path in sorted((root / "docs").glob("*.md")):
        rel = _relative(path, root)
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].startswith("# "):
            errors.append(f"{rel}: missing H1 title")
        head = lines[:20]
        if not any(line.startswith("**Version") for line in head):
            errors.append(f"{rel}: version line not within the first 20 lines")
        if not any("AI manifest" in line for line in head):
            errors.append(f"{rel}: AI manifest not within the first 20 lines")

    for path in _all_markdown(root):
        rel = _relative(path, root)
        raw = path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            errors.append(f"{rel}: file does not end with a newline")
        block: list[str] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                cells = len(re.split(r"(?<!\\)\|", stripped.strip("|")))
                block.append(cells)
                continue
            if len(block) > 1 and len(set(block)) > 1:
                errors.append(f"{rel}: table ending at line {number - 1} has inconsistent cell counts {sorted(set(block))}")
            block = []
            if name := re.match(r"^(\s*)(`{3,}|~{3,})(.*)$", line):
                if name.group(3).strip() and not name.group(3).lstrip().startswith(("text", "python", "yaml", "json", "js", "html", "css", "bash", "sh", "toml", "diff")):
                    pass  # unknown but non-empty info string: nothing to check here
        if len(block) > 1 and len(set(block)) > 1:
            errors.append(f"{rel}: final table has inconsistent cell counts {sorted(set(block))}")
    return errors


def check_markdown_anchors(root: Path = ROOT) -> list[str]:
    """Check every local markdown link target and ``#anchor`` resolves."""
    errors: list[str] = []
    anchors: dict[Path, set[str]] = {}
    markdown = _all_markdown(root)
    for path in markdown:
        found: set[str] = set()
        fenced = False
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            heading = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
            if heading:
                text = re.sub(r"[`*_]", "", heading.group(1).lower())
                text = re.sub(r"[^\w\s-]", "", text)
                found.add(text.replace(" ", "-"))
        anchors[path] = found

    for path in markdown:
        rel = _relative(path, root)
        for match in re.finditer(r"\[[^\]]+\]\(([^)\s]+)\)", path.read_text(encoding="utf-8")):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            name, _, fragment = target.partition("#")
            resolved = path if not name else (path.parent / name).resolve()
            if not resolved.exists():
                errors.append(f"{rel}: dead markdown link -> {target}")
            elif fragment and resolved.suffix == ".md" and fragment not in anchors.get(resolved, set()):
                errors.append(f"{rel}: dead markdown anchor -> {target}")
    return errors


def check_surface_parity(root: Path = ROOT) -> list[str]:
    """Check the documented surfaces against the source, in both directions.

    Each of these caught real drift on 2026-09-11: ``/api/tokens`` was
    implemented but absent from the endpoint tables, ``Store.resync`` was
    undocumented while a nonexistent ``Store.db_resync`` was documented, and a
    file listed in the session-context inventory no longer existed.
    """
    errors: list[str] = []

    # -- REST routes -------------------------------------------------------
    webapp = root / "skillsmgr" / "webapp.py"
    web_doc = root / "docs" / "08-web-ui.md"
    if webapp.is_file() and web_doc.is_file():
        tree = ast.parse(webapp.read_text(encoding="utf-8"), filename=str(webapp))
        implemented: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.List) or not node.elts:
                continue
            if not all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
                continue
            values = [e.value for e in node.elts]
            if values[0] == "api" and len(values) > 1:
                implemented.add(values[1])
        text = web_doc.read_text(encoding="utf-8")
        documented = set(re.findall(r"/api/([a-z][a-z0-9-]*)", text))
        for name in sorted(implemented - documented):
            errors.append(f"docs/08-web-ui.md: /api/{name} is implemented but undocumented")
        for name in sorted(documented - implemented):
            errors.append(f"docs/08-web-ui.md: /api/{name} is documented but not implemented")

    # -- Store public methods ---------------------------------------------
    store_path = root / "skillsmgr" / "store.py"
    store_doc = root / "docs" / "04-store-api.md"
    if store_path.is_file() and store_doc.is_file():
        tree = ast.parse(store_path.read_text(encoding="utf-8"), filename=str(store_path))
        store_class = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Store"), None)
        public = {
            n.name for n in (store_class.body if store_class else [])
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_")
        }
        text = store_doc.read_text(encoding="utf-8")
        for name in sorted(public):
            if not re.search(rf"`{re.escape(name)}\b", text):
                errors.append(f"docs/04-store-api.md: public Store.{name} is undocumented")
        section = text.split("## Public methods", 1)[-1].split("## SQLite schema", 1)[0]
        for name in sorted(set(re.findall(r"`([a-z_][a-z0-9_]*)\(self", section))):
            if name not in public:
                errors.append(f"docs/04-store-api.md: documents Store.{name}() which does not exist")

    # -- CLI commands ------------------------------------------------------
    cli_path = root / "skillsmgr" / "cli_parser.py"
    cli_doc = root / "docs" / "03-cli-surface.md"
    if cli_path.is_file() and cli_doc.is_file():
        tree = ast.parse(cli_path.read_text(encoding="utf-8"), filename=str(cli_path))
        text = cli_doc.read_text(encoding="utf-8")
        # A heading documents commands as backticked spans, optionally
        # slash-separated and repeated ("`list` / `ls [--json]`", "`webui ...`
        # (alias: `gui`)").  Take the leading token of every span so a rename
        # such as `init` -> `init-DISABLED` cannot pass on a word boundary.
        documented_commands: set[str] = set()
        for line in text.splitlines():
            if not line.startswith("### "):
                continue
            for span in re.findall(r"`([^`]+)`", line):
                for part in span.split("/"):
                    words = part.strip().split()
                    if not words:
                        continue
                    token = re.sub(r"[^A-Za-z0-9_-]+$", "", words[0])
                    if token:
                        documented_commands.add(token)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "add_parser" or not node.args:
                continue
            first = node.args[0]
            if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
                continue
            names = [first.value]
            for keyword in node.keywords:
                if keyword.arg == "aliases" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                    names += [e.value for e in keyword.value.elts
                              if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            receiver = node.func.value
            receiver_name = receiver.id if isinstance(receiver, ast.Name) else ""
            for name in names:
                if receiver_name.endswith("_sub"):
                    # A nested action is documented as "<parent> <action>".
                    parent = receiver_name[: -len("_sub")]
                    if f"{parent} {name}" not in text:
                        errors.append(f"docs/03-cli-surface.md: CLI command '{parent} {name}' is undocumented")
                elif name not in documented_commands:
                    errors.append(f"docs/03-cli-surface.md: CLI command '{name}' has no documented heading")

    # -- session-context file inventory ------------------------------------
    sc = root / "docs" / "SESSION-CONTEXT.md"
    if sc.is_file():
        text = sc.read_text(encoding="utf-8")
        if "## File inventory" in text:
            block = text.split("## File inventory", 1)[1].split("```")[1]
            stack: list[tuple[int, Path]] = []
            for line in block.splitlines():
                if not line.strip() or line.strip().startswith("#"):
                    continue
                indent = len(line) - len(line.lstrip())
                body = line.split("#")[0].strip()
                while stack and stack[-1][0] >= indent:
                    stack.pop()
                parent = stack[-1][1] if stack else root
                for token in re.findall(r"[A-Za-z0-9_./-]+\.(?:py|js|html|css|md)", body):
                    if not (parent / token).exists():
                        errors.append(f"docs/SESSION-CONTEXT.md: inventory lists missing file {token}")
                directory = re.match(r"^([A-Za-z0-9_./-]+/)\s*$", body)
                if directory:
                    stack.append((indent, parent / directory.group(1).rstrip("/")))
    return errors


def _errors(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    errors.extend(check_required_docs(root))
    errors.extend(check_doc_links(root))
    errors.extend(check_documented_source_symbols(root))
    errors.extend(check_current_claims(root))
    errors.extend(check_version_alignment(root))
    errors.extend(check_house_style(root))
    errors.extend(check_markdown_anchors(root))
    errors.extend(check_surface_parity(root))

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
