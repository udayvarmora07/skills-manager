# Static Analysis Decision Record

**Version 1.0.0**

**AI manifest**: Maintained record of the narrow undefined-name gate and the
dated Bandit review for skills-manager. Re-run the commands below after
changes to the owning symbols; do not treat this document as a security
certificate.

**[SPEC]** Static analysis is advisory evidence, not proof of security. Ruff
guards the three undefined-name classes that can survive compilation and
reach rarely executed code. Bandit findings are reviewed against the actual
callers, input validation, and regression contracts; a clean scan does not
prove that the application is secure.

## Tool scope and commands

**[SPEC]** The mandatory CI gate uses Ruff 0.16.8 through the full-SHA-pinned
`astral-sh/ruff-action` v4.1.0. Its only selected rules are `F821`, `F822`, and
`F823`, with `py310` as the target. The source set is the first-party Python
surface listed in `.github/workflows/ci.yml`; the action runs once on Ubuntu,
outside the Python-version matrix. Ruff is a developer/CI tool, never a
runtime or build dependency, and CI does not auto-fix or format files.

```text
ruff 0.16.8
ruff check --select F821,F822,F823 skillsmgr tests smoke_store.py smoke_web.py browser_harness.py desktop_launcher.py check_complexity.py check_docs.py check_package_data.py
```

The reviewed Bandit command is:

```text
bandit 1.9.4
bandit -r skillsmgr -q
```

No baseline, global skip list, severity threshold, or bare `# nosec` is
allowed. Accepted findings use a named line-local suppression and retain a
nearby invariant or test anchor.

## Bandit 1.9.4 review — 2026-09-22

**[NOTE]** The baseline scan found 18 findings (three medium and fifteen low).
The rows below record the reviewed disposition by module and owning symbol;
line numbers are intentionally not the identity because source lines move.

| Rule | Module / symbol | Disposition | Rationale and regression anchor |
|---|---|---|---|
| B202 | `skillsmgr.archive.extract_members` | accepted | Tar members pass path, type, count, depth, size, duplicate, and layout validation; Python versions with `data_filter` use it and older versions use the contained-path fallback. `tests.test_archive_contracts` covers traversal, links, devices, size, and compression limits. |
| B404 | `skillsmgr.backup_sync` subprocess import | accepted | Remote operations use the trusted Git executable and bounded, list-based argv. `tests.test_backup_sync_contracts` covers Git metadata/fetch and credential redaction. |
| B603 | `backup_sync._run_git` | accepted | Repository paths, timeout, executable, prompts, output size, and Git arguments are controlled before the shell-free call. `tests.test_backup_sync_contracts` covers the real local Git seam. |
| B105 | `bundles.verify_manifest` | accepted | `secret_redacted` is a boolean trust-report field, not a credential. Bundle verification tests assert the public safety explanation and never carry secret material. |
| B404 | `skillsmgr.cli_handlers` subprocess import | accepted | The module has two separately reviewed boundaries: explicit editor launch and allowlisted installer execution. CLI contracts assert their command construction. |
| B603 | `cli_handlers.cmd_open` | accepted | Opening `$EDITOR`/`$VISUAL` is the command's explicit purpose; `shlex.split` produces list argv and the skill path is one final argument with shell execution disabled by default. `tests.test_cli_contract` covers the adapter. |
| B110 | `cli_handlers.cmd_doctor` JSON duplicate enrichment | fixed | The best-effort duplicate scan now emits a diagnostic, preserves `duplicates: []`, and adds an existing-style `degraded` entry rather than claiming complete evidence. Doctor JSON contracts cover the response shape. |
| B110 | `cli_handlers.cmd_doctor` text scope enrichment | fixed | The human path now emits a diagnostic and a concise stderr notice while preserving the base Doctor result. CLI Doctor scope tests cover clean output and exit behavior. |
| B603 | `cli_handlers.cmd_install` | accepted | Runner and source/options are allowlisted and rendered as list argv; no shell string is accepted. Install preview and execution contracts cover the boundary. |
| B105 | `evals.aggregate_benchmark` | accepted | `pass_rate_meaning` is explanatory prose describing a metric, never a password or secret. Eval aggregate tests cover the returned evidence. |
| B110 | `scopes.get_skill` global token enrichment | fixed | Optional token enrichment now reports through diagnostics and retains the base skill record if estimation fails. Scope/detail contracts cover best-effort enrichment. |
| B110 | `scopes.get_skill` scoped metadata enrichment | fixed | Optional frontmatter/token enrichment now reports through diagnostics and retains the loaded record. Scope contracts cover malformed and readable documents. |
| B608 | `store._live_index_totals` disabled query | accepted | Only an internally generated comma-separated sequence of literal `?` placeholders enters SQL; all skill names remain DB-API parameters. Store stats contracts cover live-name totals. |
| B608 | `store._live_index_totals` category query | accepted | The category query uses the same bounded placeholder construction and parameter binding. Store stats/category contracts cover the result. |
| B404 | `skillsmgr.webapp` subprocess import | accepted | The only process boundaries are the allowlisted installer and the trusted browser opener, each reviewed at its call site. REST install contracts cover the former and browser opener contracts cover the latter. |
| B603 | `webapp` install runner execution | accepted | Runner/options are allowlisted and argv is built without a shell; timeout and output are bounded. Web install preview/execution contracts cover this path. |
| B607 | `webapp._open_browser` | fixed | The unresolved `xdg-open` PATH lookup was replaced with `launcher_security.trusted_executable`, which checks ownership, permissions, and every PATH candidate. `tests.test_webapp.BrowserOpenerTests` covers unsafe-first, missing, and trusted cases. |
| B603 | `webapp._open_browser` | accepted | The opener receives an absolute executable and one URL argument with `shell=False`; browser opening is optional and launch errors are diagnosed. `tests.test_webapp.BrowserOpenerTests` covers argv and failure behavior. |

## Review policy

**[SPEC]** A future Bandit finding must be read in the full owning function and
its callers. Fix behavior first when the finding exposes silent failure,
PATH-dependent execution, shell-like input, unbounded work, or missing
validation. If a finding is a false positive or an explicit product boundary,
use only `# nosec BNNN` on the exact reviewed line, document the invariant and
test anchor here, and rerun the complete scan. Any new process, archive,
request, SQL, or credential-handling behavior requires a fresh review rather
than a copied suppression.

Contributors can run both tools in a disposable environment outside the
repository. Neither tool belongs in `[project].dependencies`, the wheel, or
the installed CLI import path.
