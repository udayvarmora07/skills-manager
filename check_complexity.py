#!/usr/bin/env python3
"""Check complexity budgets for the four Python hotspot modules.

This is a repository check, not a product CLI command.  It parses source with
only the standard-library :mod:`ast` module, reports the largest functions in
the web, CLI, store, and frontmatter modules, and applies a checked-in ratchet
from ``complexity-baseline.json``.  Existing functions may be above the global
threshold while they are being decomposed; their current metric is recorded in
the baseline and any later increase fails CI.  New functions must be at or
below the threshold.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


ROOT = Path(__file__).resolve().parent
BASELINE_PATH = ROOT / "complexity-baseline.json"
TARGET_FILES = (
    "skillsmgr/webapp.py",
    "skillsmgr/cli.py",
    "skillsmgr/store.py",
    "skillsmgr/frontmatter.py",
)
DEFAULT_THRESHOLD = 15
DEFAULT_TOP_N = 10
BASELINE_VERSION = 1


@dataclass(frozen=True)
class FunctionMetric:
    """Measurable complexity facts for one function or method."""

    path: str
    name: str
    lineno: int
    end_lineno: int
    complexity: int

    @property
    def key(self) -> str:
        return f"{self.path}::{self.name}"

    @property
    def loc(self) -> int:
        """Return the inclusive source span, for reporting and tie-breaking."""
        return max(1, self.end_lineno - self.lineno + 1)

    def as_baseline_record(self) -> dict[str, int]:
        # Keep source spans as useful diagnostics, but never use them for the
        # ratchet: inserting lines should not look like a complexity increase.
        return {
            "complexity": self.complexity,
            "lineno": self.lineno,
            "end_lineno": self.end_lineno,
        }


@dataclass(frozen=True)
class ComplexityViolation:
    """A baseline or threshold violation reported by the checker."""

    kind: str
    metric: FunctionMetric
    baseline_complexity: int | None = None

    def message(self) -> str:
        if self.kind == "new violation":
            return (
                f"new violation: {self.metric.key} lines "
                f"{self.metric.lineno}-{self.metric.end_lineno} complexity "
                f"{self.metric.complexity} exceeds budget"
            )
        return (
            f"metric increase: {self.metric.key} lines "
            f"{self.metric.lineno}-{self.metric.end_lineno} complexity "
            f"{self.baseline_complexity} -> {self.metric.complexity}"
        )


class _ComplexityVisitor(ast.NodeVisitor):
    """Count control-flow decisions inside one function body.

    The score starts at one.  ``if``/loops/``with``/``try`` handlers, ternary
    expressions, match cases, comprehension generators, and each additional
    operand in a boolean expression add one.  Nested functions, lambdas, and
    classes are separate scopes and are intentionally not included.
    """

    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self.complexity += len(node.handlers)
        self.generic_visit(node)

    # ``TryStar`` was added after the oldest supported Python version.  The
    # method is harmless on versions where the AST node is unavailable and
    # keeps the checker correct on newer interpreters.
    visit_TryStar = visit_Try

    def visit_With(self, node: ast.With) -> None:
        self.complexity += 1
        self.generic_visit(node)

    visit_AsyncWith = visit_With

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.complexity += len(node.cases)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # A nested function has its own metric.
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # A nested class and its methods have their own scopes.
        return


def function_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the McCabe-like score for ``node`` without nested scopes."""

    visitor = _ComplexityVisitor()
    for statement in node.body:
        visitor.visit(statement)
    return visitor.complexity


class _FunctionCollector(ast.NodeVisitor):
    """Collect qualified function names while preserving lexical scopes."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.scope: list[str] = []
        self.metrics: list[FunctionMetric] = []

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        name = ".".join([*self.scope, node.name])
        end_lineno = getattr(node, "end_lineno", node.lineno)
        self.metrics.append(
            FunctionMetric(
                path=self.path,
                name=name,
                lineno=node.lineno,
                end_lineno=end_lineno,
                complexity=function_complexity(node),
            )
        )
        self.scope.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.scope.pop()


def collect_metrics(source: str, path: str = "<source>") -> list[FunctionMetric]:
    """Parse *source* and return sorted function metrics."""

    tree = ast.parse(source, filename=path)
    collector = _FunctionCollector(Path(path).as_posix())
    collector.visit(tree)
    return sorted(
        collector.metrics,
        key=lambda metric: (metric.path, metric.lineno, metric.name),
    )


def discover_python_files(root: Path = ROOT) -> list[Path]:
    """Return exactly the configured hotspot files that exist under *root*."""

    return [root / relative for relative in TARGET_FILES if (root / relative).is_file()]


def scan_repository(root: Path = ROOT) -> tuple[list[FunctionMetric], list[str]]:
    """Collect target metrics and parse/missing-file errors for *root*."""

    metrics: list[FunctionMetric] = []
    errors: list[str] = []
    for relative in TARGET_FILES:
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative}: file not found")
            continue
        try:
            metrics.extend(collect_metrics(path.read_text(encoding="utf-8"), relative))
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(f"{relative}: could not parse ({exc})")
    return sorted(
        metrics,
        key=lambda metric: (metric.path, metric.lineno, metric.name),
    ), errors


def largest_metrics(
    metrics: Iterable[FunctionMetric], limit: int = DEFAULT_TOP_N
) -> dict[str, list[FunctionMetric]]:
    """Return the largest functions per target file for human-readable output.

    The guard evaluates every function.  This view is intentionally limited so
    CI logs focus on the hotspots that motivate the budget check.
    """

    if limit < 1:
        raise ValueError("limit must be positive")
    grouped: dict[str, list[FunctionMetric]] = {path: [] for path in TARGET_FILES}
    for metric in metrics:
        if metric.path in grouped:
            grouped[metric.path].append(metric)
    for path in grouped:
        grouped[path] = sorted(
            grouped[path],
            key=lambda metric: (
                -metric.complexity,
                -metric.loc,
                metric.lineno,
                metric.name,
            ),
        )[:limit]
    return grouped


def build_baseline(
    metrics: Iterable[FunctionMetric], threshold: int = DEFAULT_THRESHOLD
) -> dict[str, object]:
    """Build the checked-in JSON representation for *metrics*."""

    if threshold < 1:
        raise ValueError("threshold must be positive")
    functions = {
        metric.key: metric.as_baseline_record()
        for metric in sorted(metrics, key=lambda item: item.key)
    }
    return {
        "version": BASELINE_VERSION,
        "threshold": threshold,
        "targets": list(TARGET_FILES),
        "functions": functions,
    }


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, object]:
    """Load and validate a target-aware baseline file."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != BASELINE_VERSION:
        raise ValueError(f"{path}: unsupported baseline version")
    threshold = data.get("threshold")
    targets = data.get("targets")
    functions = data.get("functions")
    if not isinstance(threshold, int) or threshold < 1:
        raise ValueError(f"{path}: threshold must be a positive integer")
    if targets != list(TARGET_FILES):
        raise ValueError(f"{path}: targets do not match configured hotspot files")
    if not isinstance(functions, dict):
        raise ValueError(f"{path}: functions must be an object")
    for key, record in functions.items():
        if not isinstance(key, str) or not isinstance(record, dict):
            raise ValueError(f"{path}: invalid function record")
        complexity = record.get("complexity")
        if not isinstance(complexity, int) or complexity < 1:
            raise ValueError(f"{path}: invalid complexity for {key}")
    return data


def evaluate_metrics(
    metrics: Iterable[FunctionMetric], baseline: Mapping[str, object]
) -> list[ComplexityViolation]:
    """Return new budget violations and metric increases against *baseline*."""

    threshold = baseline.get("threshold")
    functions = baseline.get("functions")
    if not isinstance(threshold, int) or not isinstance(functions, Mapping):
        raise ValueError("baseline must contain an integer threshold and functions")

    violations: list[ComplexityViolation] = []
    for metric in sorted(metrics, key=lambda item: (item.path, item.lineno, item.name)):
        record = functions.get(metric.key)
        if record is None:
            if metric.complexity > threshold:
                violations.append(ComplexityViolation("new violation", metric))
            continue
        if not isinstance(record, Mapping) or not isinstance(record.get("complexity"), int):
            raise ValueError(f"invalid baseline record for {metric.key}")
        previous = int(record["complexity"])
        if metric.complexity > previous:
            violations.append(ComplexityViolation("metric increase", metric, previous))
    return violations


def write_baseline(path: Path, metrics: Iterable[FunctionMetric], threshold: int) -> None:
    """Write a deterministic baseline for a deliberate maintainer update."""

    payload = json.dumps(build_baseline(metrics, threshold), indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")


def _existing_threshold() -> int:
    """Read a previous threshold without requiring an otherwise valid baseline."""

    try:
        raw = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        threshold = raw.get("threshold") if isinstance(raw, dict) else None
        if isinstance(threshold, int) and threshold >= 1:
            return threshold
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return DEFAULT_THRESHOLD


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="replace the checked-in baseline with the current target metrics",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"number of largest functions to print per file (default: {DEFAULT_TOP_N})",
    )
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be positive")

    metrics, parse_errors = scan_repository()
    if args.write_baseline:
        for error in parse_errors:
            print(f"ERROR: {error}")
        if parse_errors:
            return 1
        write_baseline(BASELINE_PATH, metrics, _existing_threshold())
        print(f"Wrote {BASELINE_PATH.relative_to(ROOT)} for {len(metrics)} functions")
        return 0

    try:
        baseline = load_baseline()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    for path, rows in largest_metrics(metrics, args.top).items():
        print(f"{path} (largest {len(rows)}):")
        for metric in rows:
            print(
                f"  {metric.name}: lines {metric.lineno}-{metric.end_lineno}, "
                f"LOC {metric.loc}, complexity {metric.complexity}"
            )
    for error in parse_errors:
        print(f"ERROR: {error}")
    violations = evaluate_metrics(metrics, baseline) if not parse_errors else []
    for violation in violations:
        print(f"ERROR: {violation.message()}")
    if parse_errors or violations:
        return 1
    print(
        f"COMPLEXITY CHECK PASSED: {len(metrics)} functions across "
        f"{len(TARGET_FILES)} files; new-function budget <= {baseline['threshold']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
