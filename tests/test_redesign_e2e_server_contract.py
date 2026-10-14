"""No e2e suite may resolve its base URL by itself.

THE DEFECT THIS EXISTS TO KILL
------------------------------
Five suites resolved `SKILLS_MANAGER_URL` with a hard-coded fallback to
`http://127.0.0.1:8791` and each carried a docstring line saying
`Run: .redesign/dev.sh reset && .redesign/dev.sh start`. Nothing started that
server, so a sweep launched without one reported five
`Page.goto: net::ERR_CONNECTION_REFUSED` failures — indistinguishable, in the
output, from five product regressions. `tests/e2e/_live_server.py` (6.2f) owns
the resolution now: use a running server if there is one, otherwise start a
private one, and only then fail.

WHY A GATE AND NOT A CONVENTION
-------------------------------
Because the repo has already recorded, six times, a check that reported PASS
about a path it could not see. A convention in five docstrings is a convention
in six docstrings the moment somebody adds a suite, and the sixth suite is the
one nobody re-reads. These assertions read the shipped files, so the class
cannot come back quietly.

WHAT IS ASSERTED, AND WHAT IS NOT
---------------------------------
Asserted: no suite resolves a base URL outside the helper, and the helper's own
skip/failure text names the command that would have produced a server.

Deliberately NOT asserted: that any particular suite passed. This is a source
contract; the browser suites run in the e2e sweep, one process each.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

#: `tests/e2e/` — the directory itself, not its parent. This file lives in
#: `tests/`, so `parent.parent` would resolve to the repository root and every
#: assertion would pass vacuously against an empty directory.
E2E_DIR = Path(__file__).resolve().parent / "e2e"
HELPER = E2E_DIR / "_live_server.py"

#: The convention this gate enforces, in one place.
HELPER_MODULE = "_live_server"


def _modules() -> list[Path]:
    return sorted(p for p in E2E_DIR.glob("test_*.py") if p.is_file())


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class NoSuiteResolvesItsOwnBaseUrl(unittest.TestCase):
    """A hard-coded fallback port is the shape of the defect, not a smell."""

    def test_the_helper_exists_and_is_not_itself_a_suite(self) -> None:
        self.assertTrue(HELPER.is_file(), f"missing {HELPER}")
        # `test_*.py` is what `verify.sh` discovers. If the helper were named
        # like a suite it would be launched as one, with no TestCase in it.
        self.assertNotIn(HELPER.name, {p.name for p in _modules()})

    def test_no_e2e_suite_hard_codes_the_dev_server_port(self) -> None:
        offenders: dict[str, list[str]] = {}
        for path in _modules():
            lines = []
            for number, line in enumerate(_source(path).splitlines(), 1):
                if "127.0.0.1:8791" in line or "localhost:8791" in line:
                    lines.append(f"{path.name}:{number}: {line.strip()}")
            if lines:
                offenders[path.name] = lines
        self.assertEqual(
            offenders, {},
            "these suites resolve a base URL themselves; `tests/e2e/"
            "_live_server.py` (6.2f) owns that so a sweep without a running "
            "server starts its own instead of reporting a harness fault as a "
            "product failure:\n" + "\n".join(
                line for lines in offenders.values() for line in lines))

    def test_no_e2e_suite_reads_skills_manager_url_directly(self) -> None:
        """The variable is still SUPPORTED — the helper is what may read it.

        Asserting the name is absent everywhere would forbid a suite from
        accepting an operator's URL, which is the point of the variable. What is
        forbidden is reading it somewhere that has no fallback behind it.
        """
        readers = {
            p.name for p in _modules()
            if "os.environ" in _source(p) and "SKILLS_MANAGER_URL" in _source(p)
        }
        self.assertEqual(
            readers, set(),
            "these suites read SKILLS_MANAGER_URL with nothing behind it, so a "
            "dead value is a connection error rather than a suite that still "
            "runs. Read it through tests/e2e/_live_server.py instead.")

    def test_every_suite_that_opens_the_page_resolves_its_base_url(self) -> None:
        """A suite that navigates needs a URL, and there are two honest ways.

        Either it reads one — through the helper, which finds a running server
        or starts one — or it builds one, by constructing a `WebAppServer` on
        port 0 the way `test_honesty_states` does. What is left over is a suite
        that navigates and has neither: those are the ones that need a
        developer's terminal to be open, which is the defect.

        The first version of this asserted "must use the helper" and flagged
        all 33 suites that legitimately start their own server. A gate that
        fails on a correct tree is a gate that gets deleted, so the predicate is
        the union of the good shapes, not one of them.

        "Builds its own" is `WebAppServer` OR `serve_forever`: `test_site.py`
        serves `site/` with a plain `HTTPServer` and needs no product store, so
        a predicate naming only the product's server class would have flagged a
        correct tree a second time.
        """
        offenders: dict[str, list[int]] = {}
        for path in _modules():
            source = _source(path)
            if ".goto(" not in source:
                continue
            if HELPER_MODULE in source or "WebAppServer" in source:
                continue
            if "serve_forever" in source:
                continue
            offenders[path.name] = [
                n for n, line in enumerate(source.splitlines(), 1) if ".goto(" in line
            ]
        self.assertEqual(
            offenders, {},
            "these suites navigate and resolve no base URL: they need either "
            f"`{HELPER_MODULE}` or their own `WebAppServer`, or they need a "
            "terminal someone remembered to open. See "
            "tests/e2e/_live_server.py.")

    def test_the_helper_names_the_command_it_would_have_needed(self) -> None:
        """A failure whose text does not say what to run is half a failure."""
        source = _source(HELPER)
        self.assertRegex(
            source, re.compile(r"\.redesign/dev\.sh"),
            "the helper must name the command that starts a server, so a "
            "reader who hits it is told what to type")

    def test_the_helper_documents_the_order_it_tries_servers_in(self) -> None:
        """Reading prose is not a check. This one parses the module."""
        tree = ast.parse(_source(HELPER))
        names = {node.name for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for required in ("_alive", "_start_isolated", "live_server", "_candidates"):
            self.assertIn(required, names,
                          f"the helper lost {required}; a caller may rely on it")


if __name__ == "__main__":                                     # pragma: no cover
    unittest.main()