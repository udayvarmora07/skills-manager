#!/usr/bin/env python3
"""Machine-check current documentation against repository source facts.

This is intentionally a repository check, not a new product CLI command. It
fails closed on broken ``@docs/`` links, stale architecture claims, missing
HADS headers, and mismatches in the documented CLI/API contract.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"


def _errors() -> list[str]:
    errors: list[str] = []
    required_docs = [
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
    ]
    for name in required_docs:
        path = DOCS / name
        if not path.is_file():
            errors.append(f"missing required document: docs/{name}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].startswith("# "):
            errors.append(f"{path.relative_to(ROOT)}: missing H1 title")
        if not any(line.startswith("**Version") for line in lines[:20]):
            errors.append(f"{path.relative_to(ROOT)}: missing version line")
        if not any("AI manifest" in line for line in lines[:20]):
            errors.append(f"{path.relative_to(ROOT)}: missing AI manifest")

    pointer_pattern = re.compile(r"@docs/([A-Za-z0-9_.-]+\.md)")
    for path in [ROOT / "AGENTS.md", *DOCS.glob("*.md")]:
        text = path.read_text(encoding="utf-8")
        for target in pointer_pattern.findall(text):
            if not (DOCS / target).is_file():
                errors.append(f"{path.relative_to(ROOT)}: broken @docs/{target}")

    architecture = (DOCS / "01-architecture.md").read_text(encoding="utf-8")
    if "skills-manager.db" not in architecture or "skills.db`" in architecture:
        errors.append("docs/01-architecture.md: database path disagrees with store.py")
    if "local web UI" not in architecture or "skillsmgr/webapp.py" not in architecture:
        errors.append("docs/01-architecture.md: current web architecture is missing")
    if "GTK4, in progress" in architecture or "GUI toolkit: GTK4" in architecture:
        errors.append("docs/01-architecture.md: stale GTK architecture claim")

    gui_plan = (DOCS / "05-gui-plan.md").read_text(encoding="utf-8")
    if "SUPERSEDED" not in gui_plan or "historical" not in gui_plan.lower():
        errors.append("docs/05-gui-plan.md: superseded GTK plan is not marked historical")

    cli_source = ast.parse((ROOT / "skillsmgr/cli.py").read_text(encoding="utf-8"))
    parser_names = {
        node.args[0].value
        for node in ast.walk(cli_source)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_parser"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    cli_doc = (DOCS / "03-cli-surface.md").read_text(encoding="utf-8")
    if "40 invocable names" not in cli_doc:
        errors.append("docs/03-cli-surface.md: expected current 40-name CLI inventory")
    for name in ("webui", "install", "sync", "scopes", "tokens"):
        if name in parser_names and name not in cli_doc:
            errors.append(f"docs/03-cli-surface.md: missing parser command {name}")

    store_source = (ROOT / "skillsmgr/store.py").read_text(encoding="utf-8")
    store_doc = (DOCS / "04-store-api.md").read_text(encoding="utf-8")
    for required in ("export(self, dest=None, full=False)", "backup(self, dest=None, full=False)", "content hash"):
        if required not in store_doc:
            errors.append(f"docs/04-store-api.md: missing current Store contract detail {required!r}")
    if 'SCHEMA_VERSION = "1"' not in store_source or 'SCHEMA_VERSION = "1"' not in store_doc:
        errors.append("docs/04-store-api.md: schema version contract is missing")

    settings = (ROOT / ".commandcode/settings.json").read_text(encoding="utf-8")
    if "skillsmgr/gui.py" in settings:
        errors.append(".commandcode/settings.json: references deleted skillsmgr/gui.py")

    return errors


def run_checks() -> list[str]:
    """Return consistency errors; an empty list means the check passed."""
    return _errors()


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