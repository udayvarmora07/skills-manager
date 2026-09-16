# Deep Audit — Loop-Engineering Bugs & Security Vulnerabilities

**Project:** `skills-manager` (`skillsmgr`) v1.0.1 — Python stdlib CLI + local Web UI
**Audit date:** 2026-09-11
**Baseline commit:** `0b82094` (clean tree; only `.autogit` untracked)
**Code under review:** 9,662 LOC Python (`skillsmgr/`), 2,806 LOC frontend (`skillsmgr/webui/`), 8,037 LOC tests
**Scope:** all of `skillsmgr/`, `skillsmgr/webui/`, `tests/`, `*.py` harness scripts, `pyproject.toml`, `.github/`, `desktop_launcher.py`, `browser_harness.py`, `check_*.py`
**Status of this document:** **findings only, as originally written — no fixes were applied by the audit itself.** It is kept unedited as the point-in-time record of what was found at `0b82094`.
**Remediation status is tracked separately:** [`docs/13-audit-remediation-status-2026-09-11.md`](docs/13-audit-remediation-status-2026-09-11.md) holds one row per finding ID with its current disposition (**67 fixed, 1 partial, 1 accepted, 33 open** as of the 2026-09-12 batch). Do not read the findings below as still-open by default.

---

## 0. How this audit was performed

**Method.** Seven parallel workstreams, each combining full-file reading with *executed* differential/fuzz/hostile-input probes (never code-reading alone for anything marked *Confirmed*):

| Workstream | Surface |
|---|---|
| Automated tooling | ruff, bandit, semgrep, mypy, vulture, radon/xenon, pip-audit, detect-secrets, trivy, shellcheck |
| HTTP layer (this agent) | `webapp.py`, `web_security.py`, `web_upload.py`, `web_serialization.py`, live-server probes |
| Store / data integrity | `store.py`, `archive.py`, `atomic_io.py`, `path_safety.py`, `observations.py` |
| Scope resolution | `scopes.py`, `effective.py`, `loader.py`, `root_discovery.py`, `paths.py` |
| Document parsing | `frontmatter.py`, `validator.py`, `templates.py` + a 25,000-document round-trip fuzz campaign |
| CLI / registry / evals | `cli_handlers.py`, `cli_parser.py`, `insights.py`, `evals.py` (workstream **in flight** — see §6) |
| CI / packaging / launchers | `.github/workflows/`, `pyproject.toml`, `check_package_data.py`, `desktop_launcher.py`, `browser_harness.py` |
| Frontend | `index.html`, `app.js`, `domain.js`, vendored Vue, CSP |

**Toolchain installed for this audit** (isolated venv at `/tmp/sm-audit/venv`, nothing added to the repo):

```text
ruff 0.16.7        bandit 1.9.4       semgrep 1.177.0    mypy 2.3.1
pip-audit 2.10.1   detect-secrets 1.5.0   vulture 2.16   radon 6.0.1 / xenon 0.9.3
trivy 0.73.0 (system)   shellcheck (system)   node v22.22.3
```

**Rulesets applied:** `ruff --select S,B,PT,RUF,ASYNC,DTZ,LOG,SLF,TRY,PLE,PLW,ARG`; `bandit -r --severity-level low --confidence-level low`; `semgrep --config=p/security-audit --config=p/python --config=p/secrets --config=p/owasp-top-ten`; `trivy fs --scanners vuln,secret,misconfig`.

**Confidence vocabulary.** *Confirmed* = reproduced on the real code with the command and output shown. *Likely* = strong code-reading evidence, no reproduction. *Speculative* = hypothesis with a named experiment.

**Isolation discipline.** Every probe ran against a fresh `tempfile.mkdtemp()` data root and, where relevant, a fresh throwaway `HOME`. No probe touched `~/.local/share/skills-manager`, `~/.claude`, `~/.codex`, `~/.agents`, or `~/.cursor`. The one exception is reported honestly in **SEC-3**, where the *product code itself* reads the real user directories — that is the finding, not a probe accident.

---

## 1. Verification snapshot

| Gate | Result |
|---|---|
| `python3 -m unittest discover -s tests` | **477 tests OK** (35.9 s, Python 3.12.3) |
| `python3 -m py_compile` (all modules) | PASS |
| `check_docs.py` | (not re-run; unchanged by this audit) |
| `check_complexity.py` | (not re-run; unchanged by this audit) |
| `ruff check` (all rules) | **185 findings** in `skillsmgr/` + tests |
| `bandit` | **20 findings**: 0 High, 1 Medium, 19 Low, 0 `#nosec` |
| `semgrep` (security-audit/python/secrets/owasp) | 2 substantive: 1 ERROR (tainted-env subprocess), 1 WARNING (dynamic urllib) |
| `mypy` | 28 type errors |
| `vulture` | 3 dead-code items |
| `xenon` (max-absolute C) | **14 blocks above C**: 2 rank F, 4 rank E, 8 rank D |
| `detect-secrets` / `trivy secret` | 0 secrets |
| `pip-audit` (runtime deps) | **N/A — zero third-party runtime dependencies** (locked constraint holds) |
| `trivy fs vuln` | no language-specific manifests; nothing to scan |

### Findings at a glance

| Severity | Count | IDs |
|---|---|---|
| **Critical** | **2** | FM-1, STORE-1 |
| **High** | **14** | SEC-1, SEC-2, SEC-3, STORE-2, STORE-3, STORE-4, STORE-5, SCOPE-1, SCOPE-2, SCOPE-3, BUG-1, BUG-2, FM-2, FM-3 |
| **Medium** | **35** | SEC-4…SEC-9 (6), STORE-6…STORE-11 (6), SCOPE-4…SCOPE-11 (8), BUG-3…BUG-6 (4), FM-4…FM-10 + FM-12 (8), CLI-1…CLI-3 (3) |
| **Low / Info** | **51** | SEC-10…SEC-19 (10), STORE-12…STORE-14 (3), SCOPE-12…SCOPE-18 (7), BUG-7…BUG-15 (9), FM-11 + FM-13…FM-21 (10), CLI-4…CLI-11 (8), EVAL-2 (1), INS-1 + INS-2 (2), INFO-1 (1) |
| **Total distinct findings** | **102** | across seven audited subsystems (SEC 19, STORE 14, SCOPE 18, FM 21, BUG 15, CLI 11, EVAL 1, INS 2, INFO 1) — sums to 102; every ID below appears exactly once in §2.1–§2.4 |

> **Naming note.** The eval-harness ReDoS is filed as **CLI-1** (not `EVAL-1`) because it is driven end-to-end through the CLI and the REST route; `EVAL-2` covers `record_runs` iteration atomicity. The seventh workstream's `EVAL-1` label is therefore `CLI-1` here.

Roughly **68% of the Medium-and-above findings are reproducible data-integrity, crash, or silent-corruption defects rather than remote-attack issues** — which fits the product: it is local desktop software, and the dominant risk is that it quietly damages the user's skills rather than that someone attacks it over the network.

**The five findings I would act on before anything else** (see §7 for the full ordered list): **FM-1** (silent truncation on every write path, one-line fix), **STORE-1** (unrecoverable destruction of the user's only copy), **SEC-1** (GET bypasses the entire request policy), **STORE-3**/**SCOPE-13** (a normal accident destroys one of two documents on any later toggle), and **STORE-4** (import silently discards a committed edit while `doctor()` reports healthy).

---

**Zero third-party runtime dependencies is the single strongest structural control in this project** and it removes entire vulnerability classes (dependency CVEs, transitive supply chain, install-time code execution). It is worth protecting deliberately.

---

## 2. Findings summary

Severity is assigned for the **realistic threat model of this product**: local desktop software that binds `127.0.0.1` and runs while the user has a browser open. The primary attacker is therefore *a web page the user visits*, and secondarily *a hostile skill bundle the user is asked to import*.

### 2.1 Master table — Critical

| ID | Area | Title | Where |
|---|---|---|---|
| **FM-1** | Round-trip / data loss | An indented `---` line inside a multi-line frontmatter value **terminates the block early**, silently truncating the value — and every rewrite persists the corruption | `frontmatter.py:31`, `:70-73` |
| **STORE-1** | Atomicity / data loss | An interrupt (Ctrl-C) during `import_`'s commit move **destroys the user's only copy of the skill** — the staging dir holding the displaced original is deleted by the `finally` | `store.py:1478-1488`, `archive.py:332-364` |

### 2.2 Master table — High

| ID | Area | Title |
|---|---|---|
| **SEC-1** | Web / authz | `GET` routes bypass the entire Host/Origin/Fetch-Metadata policy — read + full-archive exfiltration from any web page |
| **SEC-2** | Web / DoS | `GET /api/doctor?explain=…&project=/` triggers an unbounded `rglob` of an attacker-chosen directory; the request never completes |
| **SEC-3** | Web / disclosure | `GET /api/doctor?explain=…` discloses the user's real `~/.agents/skills` + `~/.cursor/skills` inventory (names, descriptions, absolute paths), the home directory, and `data_dir` |
| **STORE-2** | Concurrency | `add()` copies into the live tree with **no lock**; a concurrent `remove()` leaves a 20,000-file husk that `doctor()` calls healthy |
| **STORE-3** | Invariant violation | `add()` installs a skill containing **both** `SKILL.md` and `SKILL.md.disabled`; a later `disable()`/`enable()` silently destroys one document |
| **STORE-4** | Lost update | `import_(force=True)` silently discards an already-committed, lock-holding `edit()` — and `doctor()` reports `ok: True` |
| **STORE-5** | Concurrency + divergence | `restore()`/`purge_trash()` are not mutually exclusive: a raw `FileNotFoundError` escapes, and a lost race creates a `trashed` row with no trash dir that `resync()` can **never** repair |
| **SCOPE-1** | Symlink / confidentiality | `sync_skill` copies symlinks as **content** — reads files outside every managed root and materializes them into another agent scope (88-byte skill → 65 KB exfiltrated) |
| **SCOPE-2** | Symlink / inconsistency | An escaping symlink in a scope root is invisible to every read view but blocks every write — the exact shape `skills-mgr install` produces |
| **SCOPE-3** | Symlink / data loss | In-root symlink alias: `remove`/`toggle`/`edit` mutate a **different** skill than the one named; the physical skill is double-counted and misnamed |
| **BUG-1** | Store init | `Store.create()` on a fresh data dir raises a raw `sqlite3.OperationalError: no such table: skills`; only `list`/`get`/`search`/`stats`/`resync`/`export`/`doctor`/`add`/`import_`/`history` self-initialize |
| **BUG-2** | Diagnostic accuracy | `loader.scan_dir` and `effective.explain` report a document with **no frontmatter at all** (missing required `name` and `description`) as `state: "loadable"`, while `validate_skill` reports two `error`s |
| **FM-2** | Crash | A top-level YAML sequence in `SKILL.md` makes `parse_frontmatter` return a `list`; every consumer then dies with a raw `AttributeError` (doctor, resync, db_rebuild, validate, scan) |
| **FM-3** | Crash | Out-of-range `\U` escapes raise raw `ValueError`/`OverflowError` that bypass every `FrontmatterError` guard |

### 2.3 Master table — Medium

| ID | Area | Title |
|---|---|---|
| **SEC-4** | Web / CSP | `script-src 'unsafe-eval'` is genuinely required by the in-DOM Vue template; it removes the main barrier that would stop a future HTML-injection sink from escalating to JS execution |
| **SEC-5** | Web / hardening | CSP lacks `form-action`; 501 responses from unmatched methods are emitted with **no** security headers |
| **SEC-6** | Web / robustness | `/api/import` multipart upload returns `500 internal error` on a filename/directory collision (`IsADirectoryError`) and leaks raw exception text |
| **SEC-7** | Supply chain | Release job holding `contents: write` `pip install`s and executes a distribution fetched from public PyPI at release time |
| **SEC-8** | Supply chain | Published/attested artifacts are built by an unpinned, unhashed toolchain (`setuptools>=61`), so the attesting build is not reproducible |
| **SEC-9** | Supply chain | Vendored `vue.global.prod.js` (158 KB, minified, same-origin, executes the app) has no hash/SRI/integrity assertion on any CI or release gate |
| **STORE-6** | SQL / concurrency | `purge_trash()` holds one SQLite write transaction open across every `rmtree`; a concurrent writer stalls 10 s then fails with a raw `sqlite3.OperationalError` |
| **STORE-7** | Atomicity | `remove(purge=True)` is non-transactional and leaks a raw `PermissionError`; a partial purge leaves the skill listed `active` with its document already deleted |
| **STORE-8** | Atomicity | `export()` is non-atomic, reuses a second-resolution filename (`backup()` silently overwrites `export()`), and leaves a truncated archive in place on failure |
| **STORE-9** | Path safety | `export()`/`_tree_content_hash()` follow symlinks: a skill containing a symlink exports to an archive `import_` **rejects outright**, and the manifest hash covers bytes outside the managed root |
| **STORE-10** | Index divergence | Read paths trust SQLite over the filesystem: an `active` row with no directory is still returned by `list()`/`get()`/`search()` and counted by `stats()` |
| **STORE-11** | Concurrency | The mutation lock is process-local only: cross-process mutations leak raw `FileNotFoundError`, strand `.skillsmgr-tmp` files in trash copies, and leave `doctor()` permanently unhealthy |
| **SCOPE-4** | Error handling | One unreadable `SKILL.md` (or skill dir) aborts **every** scope view with a raw `PermissionError` → `/api/scopes`, `/api/skills?scope=all`, `/api/tokens` all HTTP 500 |
| **SCOPE-5** | Path safety | `_safe_scope_skill_path` mixes a resolved path with an unresolved root, so nested skills become unreachable when any ancestor of the scope root is a symlink (the macOS `/tmp → /private/tmp` shape) |
| **SCOPE-6** | Precedence | `explain()` reports top-level `resolution: "resolved"` when **no** skill has a winner; a nested-only Claude skill is called `no-instances` while a loadable instance is listed |
| **SCOPE-7** | Precedence | `effective.explain` never deduplicates physical roots: one file reported as two candidates (false `ambiguous`) and the winner reported as its own `shadowed` copy |
| **SCOPE-8** | Sync atomicity | `sync_skill` failures: raw `OSError` to callers (REST 500), partial multi-target updates with no report, read-only targets accepted |
| **SCOPE-9** | Env root | "global" has two identities: `known_scopes()` derives it from the environment while `scan_scope("global")` derives it from the injected `Store` — sync creates a destination that is never indexed |
| **SCOPE-10** | Global state | Module-global `_GLOBAL_STORE`: a second in-process `WebAppServer` silently redirects the first server's global reads **and** its snapshot writes to another data dir |
| **SCOPE-11** | View inconsistency | `list_all()` silently collapses same-name instances inside one recursive scope and erases the duplicate/divergent signal |
| **BUG-3** | Frontend state | `selectSkill` compares only `selectedName`, so selecting a same-named skill in another scope is a no-op and the detail pane goes stale |
| **BUG-4** | Frontend state | Search/scope/view state desync: `query` stays visible while the list shows unfiltered data after a scope change or a Trash round-trip |
| **BUG-5** | Frontend data loss | Destructive remove re-derives its scope from live `this.selected` instead of the record the modal was opened for |
| **BUG-6** | Frontend | `modals.validate.error` is assigned but never rendered — validation failures are completely silent |
| **CLI-1** | DoS (ReDoS) | A regex assertion in `evals/evals.json` causes catastrophic backtracking: the CLI hangs forever and the **web UI process freezes GIL-wide** (even Ctrl-C cannot run). Reproduced independently here. |
| **CLI-2** | Document corruption | `--metadata` accepts a newline inside a KEY, writing a `SKILL.md` the tool cannot parse; a later `edit` then writes a **second** frontmatter block. Exit 0 throughout, `doctor` says `ok`. |
| **CLI-3** | Terminal injection | Hostile skill descriptions/categories are printed raw: an ANSI/CR payload from an imported archive or a foreign scope directory spoofs `list`/`view` output and corrupts column widths |
| **FM-4** | Crash | Lone surrogates (`\uD800`) are accepted and validation passes, then every write dies with a raw `UnicodeEncodeError` |
| **FM-5** | Block scalar | Common leading indentation of a multi-line value is eaten on round trip |
| **FM-6** | Block scalar | Whitespace-only lines inside a block scalar lose their whitespace |
| **FM-7** | Round trip | CR characters inside a block scalar are stripped from the re-parsed value |
| **FM-8** | Type coercion | `#` after a **TAB** is a comment to the parser but is not quoted by the dumper — the value is silently truncated |
| **FM-9** | Dumper | The dumper emits output its own parser rejects for keys containing a newline — and the parser can produce such keys |
| **FM-10** | Block scalar | A value consisting only of newlines collapses to the empty string |
| **FM-12** | Block scalar | Chomping indicators mis-handle trailing blank lines (clip keeps too many, keep drops one) |

### 2.4 Master table — Low and Info

| ID | Area | Title |
|---|---|---|
| **SEC-10** | Web / DoS | `/api/tokens` (and several `/api/skills` paths) perform a **full multi-scope filesystem rescan on every request** — 2.4–2.7 s of CPU per unauthenticated GET |
| **SEC-11** | Web / parser | `parse_multipart` silently truncates uploaded content at `--<boundary>` and strips trailing newlines, so stored skills differ from what the user uploaded |
| **SEC-12** | Concurrency | `mutation_lock` is **process-local only** (`threading.RLock`); concurrent CLI + Web UI on one data dir have no mutual exclusion (measured corroboration in STORE-11) |
| **SEC-13** | Packaging | sdist ships `tests/test*.py` and no gate inspects non-`webui` archive members |
| **SEC-14** | GHA hardening | Provenance-signing and other first-party actions run on mutable major tags although the exact SHAs are already recorded in the workflow comments |
| **SEC-15** | Launcher | `browser_harness.py` runs Chrome with `--no-sandbox` and an unauthenticated loopback CDP endpoint, in CI and locally |
| **SEC-16** | Launcher | Chromium/Node discovery executes the first `PATH` match with no ownership/permission check |
| **SEC-17** | Governance | No `CODEOWNERS`, no `dependabot.yml`; the only `contents: write` job has no `environment:` gate |
| **SEC-18** | Secrets hygiene | `.gitignore` has no rule for `.env`, `*.db`, `*.pem`, `*.key`, `.netrc` |
| **SEC-19** | Trust root | `SKILLS_MANAGER_DATA` / `XDG_DATA_HOME` select an unvalidated read/write root (containment is only enforced *below* it) |
| **STORE-12** | Concurrency | `resync()` and `db_rebuild()` mutate the index with no lock; `db_rebuild()` `unlink()`s the DB under live connections |
| **STORE-13** | Index divergence | `doctor()` cannot see real damage: document-less directories in `skills/` are invisible, and it can report a permanent `ok: False` that `resync()` cannot fix |
| **STORE-14** | Contract mismatch | Five documented `Store` API contracts contradict the implementation (`__init__` "creates layout, inits DB", `list(include_disabled=…)`, `create`/`edit` return shapes, `_TRASH_TS_RE` literal) |
| **SCOPE-12** | Error handling | `edit_skill` corrupts a malformed document (writes two frontmatter blocks) and clears the `malformed` flag |
| **SCOPE-13** | Data loss | `toggle_skill` on a mixed state (`SKILL.md` **and** `SKILL.md.disabled`) silently destroys one document, with no snapshot |
| **SCOPE-14** | View inconsistency | On-disk names that fail NAME_RE are listed but cannot be addressed by any operation |
| **SCOPE-15** | View inconsistency | One rogue/legacy index row with a non-NAME_RE name kills all global aggregates while `list_scopes` still renders |
| **SCOPE-16** | Precedence | `_both_load`/`_facade_warnings` read instances outside the documented `MAX_INSTANCES` budget, without the truncation warning |
| **SCOPE-17** | Env root | Empty `$HOME` moves every user scope to `/`; unset `$HOME` silently uses the real home; relative data-dir overrides follow the CWD |
| **SCOPE-18** | Precedence | The flat-path short-circuit in `_safe_scope_skill_path` hides a nested skill when a grouping directory shares its name |
| **BUG-7** | Frontend render | `budget.window_tokens.toLocaleString()` throws in the template when the backend's swallowed stats-enrichment failure omits the key |
| **BUG-8** | Web / error contract | Nine `except Exception: pass` blocks in `webapp.py` silently drop real failures |
| **BUG-9** | Web / static | `/api/…` requests with the wrong arity are served through `_serve_static` and produce a **404** rather than a routing error |
| **BUG-10** | Loader | A dot-directory under a scope root is listed as a skill named `.hidden-skill`; a non-UTF-8 document is advertised with a replacement-character description |
| **BUG-11** | Templates | `create_template` acquires the mutation lock before `templates_dir.mkdir()` |
| **BUG-12** | Memory | `_MUTATION_LOCKS` grows without bound — one `RLock` retained per distinct resolved path ever touched |
| **BUG-13** | Packaging | `check_package_data.py` filters inspected members to `skillsmgr/webui/`, so `tests/`, `docs/`, `.env` or a DB file added to a build would never be flagged |
| **BUG-14** | Gate integrity | The SHA-pin contract regex cannot match reusable-workflow refs (`owner/repo/.github/workflows/x.yml@main`) |
| **BUG-15** | Dead code | `_scopeParam`/`_scopeQs` defined but never called; `esc` exported but unused; `webbrowser` imported but unused; 2 dead locals |
| **CLI-4** | Path safety | `--workspace` is not contained: eval run data can be written **inside the managed `skills/` tree** and is then shipped by `export`/`backup`, contradicting ADR-003 §3 |
| **CLI-5** | Exit code | `doctor --scope X` never checks that scope and silently accepts an unknown one, while every other scope-aware command rejects it |
| **CLI-6** | JSON contract | `view --raw --json` emits raw Markdown instead of JSON with exit 0 — the only `--json` invariant break in 48 invocations |
| **CLI-7** | Registry bridge | `install --list-only` prints the command but never runs the runner, so it lists nothing (REST executes it) |
| **CLI-8** | Command injection | `--agent`/`--skill`/SOURCE validation blocks option injection but accepts traversal-shaped and absolute values (`..`, `/etc/passwd`, `C:/Windows`) with no length cap; shared with REST, so not a parity gap |
| **CLI-9** | Output contract | `trash purge` prints the store's Python **list** instead of a count |
| **CLI-10** | Parser | Silently ignored flag combinations; `validate nosuch --all` reports green results for unrelated skills |
| **CLI-11** | Path safety | Eval case `files` entries accept a Windows drive-prefixed path (`C:/Windows/...`) — file-existence oracle only |
| **EVAL-2** | Atomicity | `record_runs` is not atomic per iteration: a failed run leaves a partial iteration, and re-recording with fewer runs leaves stale outputs contradicting `benchmark.json` |
| **INS-1** | Static analysis | `insights._SCRIPT_RE` is an unsound heuristic (`\| bash`, `base64 \| sh`, `rm -r -f`, `shell=True`, `eval` all bypass it) — dormant, zero product callers |
| **INS-2** | Registry bridge | `trust_confirmed`/`may_install`/`hash_status` are self-asserted with nothing verified; `may_install` flips purely on a caller flag |
| **INFO-1** | False positive | `cli_handlers.py:289` (`cmd_open`, Semgrep's only ERROR): **verified not a vulnerability** — no shell, hostile names cannot reach it, the path is absolute |
| **FM-11** | Validator rule | `validate_skill` compares the frontmatter name with the **caller's** `name`, never `skill_dir.name` — the documented directory-name rule is silently unenforced |
| **FM-13** | Block scalar | Folded `>` scalars mis-fold more-indented lines |
| **FM-14** | Block scalar | Explicit indentation indicators (`\|2`) are treated as absolute instead of parent-relative |
| **FM-15** | Name validation | Reserved Windows device names (`con`, `nul`, `aux`, `prn`, `com1`, `lpt1`) pass `validate_skill_name` |
| **FM-16** | Crash | A NUL byte in a link target or layout mention makes `validate_text` raise a raw `ValueError` |
| **FM-17** | Validator rule | `validate_text(text)` without `name=` never applies `NAME_RE` — `name: ../evil` yields zero errors |
| **FM-18** | Validator rule | Use-context detection misses "should be used when …" (false warning) |
| **FM-19** | Validator rule | Link/mention warnings fire for existing targets with `#fragment`, `%20`, `?query`, trailing punctuation |
| **FM-20** | Crash | `dump_frontmatter` has no depth guard → raw `RecursionError` at 2000 nesting levels |
| **FM-21** | Name validation | `templates.py` re-implements the name rule without the length cap (300 chars → raw `OSError`) or the reserved-name check |

### 2.5 Verified controls — examined and found **correct**

These were actively attacked and held. They are recorded so future changes do not silently regress them.

| Control | Evidence |
|---|---|
| **Archive extraction containment** | 11 hostile tar shapes (`../`, deep traversal, absolute, backslash, drive letter, symlink, hardlink, device node, dot segment, empty segment) — **all rejected** with `ArchiveError`; the single clean control case extracted only inside the destination. Nothing landed outside. |
| **Archive resource limits** | Per-member, per-archive expanded bytes, member count, path length, nesting depth, and both per-member and cumulative compression-ratio caps. |
| **Static file serving** | 8 traversal variants (`/static/../../etc/passwd`, `..%2f`, `%2e%2e`, double-encoded, `....//`) — all `404`. |
| **Skill-name validation** | 22 adversarial names (leading/embedded `-`, `.dot`, `dot.`, `CON`, `NUL`, `a\b`, `a:b`, `a b`, `a/b`, 250 chars, NFC vs NFD `é`, `..`, `...`, whitespace-padded, embedded `\n`, embedded ANSI `\x1b[31m`) — **all rejected**; only canonical `[a-z0-9]` names accepted. |
| **Path containment** | `contained_path` resolves the root, rejects absolute parts, rejects `\` and drive-letter prefixes on every platform, then re-checks `is_relative_to` after `.resolve()`. |
| **API path traversal** | `..%2f`, `%2e%2e`, double-encoded and `%2F`-embedded names all rejected at the canonical-name guard with a clean `400`. |
| **Frontend XSS** | The **only** HTML sinks are two `v-html` call sites (`index.html:267`, `:373`), both routed through `renderMarkdown`. Every emitter calls `esc()` **before** any tag is inserted, so a raw `<` can never reach the DOM. Verified with targeted payloads plus a 200,000-iteration randomized fuzz: 0 raw-`<` leaks, 0 unknown tag names, 0 non-whitelisted attributes, 0 throws. |
| **Frontend URL handling** | Zero `:href`/`:src` bindings; the only markdown link regex requires `https?://` and carries `rel="noopener"`, so `javascript:` cannot be reached. `tokenBarWidth` is numeric-only and clamp-bounded, so `:style` injection is impossible. |
| **Frontend DOM clobbering** | Every `id`/`name` in `index.html` enumerated; none collides with the globals `app.js` reads. Mount uses the string selector `#app`; DOM access uses `getElementById`/`$refs`. |
| **Web storage** | Only three non-sensitive keys (`skillsmgr-theme`, `skillsmgr-scope`, `skillsmgr-budget-window`); no tokens, paths, or bodies. |
| **Command injection (CLI install)** | `_SAFE_SOURCE_RE` + leading-`-` rejection shared by CLI and REST (`cli_handlers.py:33`, `:1013-1032`). Verified rejected: `-g`, `--`, `a b`, `a;b`, `a\|b`, `a$(id)`, `` a`id` ``, `a&&b`, `a\nb`, `a\\b`, `a'b`, `a"b`, `a>b`, `a<b`, `a*b`, `a?b`, `a\x00b`, `a\tb`. Runner allowlisted (`sh`, `bash`, `; rm -rf /`, `npx --evil` all rejected). No `shell=True`, `os.system` or `os.popen` **anywhere** in the codebase; all six subprocess call sites are argv-list form. |
| **Eval-harness path safety** | Independently probed: `workspace_for` applies `validate_skill_name`; `case_dir` applies `re.fullmatch(r"[a-z0-9][a-z0-9-]*")` to the slug; `variant_dir` validates the variant against `VARIANTS`; `iteration_dir` rejects `0`, `-1`, `True`, `1.5` and `"2"`; every result is re-checked with `contained_path`. `'../../etc'`, `'a/b'`, `'..'`, `''` and over-long names are all rejected at every entry point, and the workspace reliably stays under `<data>/evals/`. |
| **`load_cases` no-raise contract** | Truncated (`{invalid`), empty, `[]` and `null` `evals.json` all return a report with an `issues` entry instead of raising — the documented contract holds. |
| **CLI exit codes** | Independently probed against the documented 0/1/2 contract: success `0`; operational errors (`duplicate skill`, `bad name`, empty description, missing skill on view/remove/edit) all `1` with a clean one-line `error:` message and **no traceback**; unknown flag and unknown subcommand both `2` with usage text. |
| **CLI `--json` contract** | All eight JSON-capable commands (`list`, `stats`, `trash list`, `doctor`, `history`, `db resync`, `scopes`, `validate`) emit **valid JSON on stdout**, and `create --json` emits nothing before the JSON — so the output is safe to pipe into a parser. |
| **Trust gate** | `registry_bridge_plan(trust_confirmed=False)` emits the blocker "trust not confirmed: review the source and audit links, then confirm explicitly"; the plan is offline and performs no request. |
| **Command injection (REST install)** | `source`/`agents`/`skills` validated by `re.fullmatch(r"[A-Za-z0-9_@./:+-]+")` + leading-`-` rejection; runner allowlisted; executed as an **argv list with no `shell=True`**. |
| **GHA pwn-request class** | No `pull_request_target`, no `workflow_run`, no self-hosted runners, no checkout of a PR head, and **zero `${{ }}` expressions inside any `run:` block**. |
| **GHA permissions** | Top-level `permissions: contents: read` in both workflows; `id-token: write` confined to three jobs that contain **no `run:` step**. |
| **OIDC publishing** | Trusted publishing via `pypa/gh-action-pypi-publish@dc37677b…` with protected environments; no long-lived PyPI token anywhere. |
| **Secrets** | 110 tracked files × 9 credential patterns → zero matches; no tracked `.env`, key, DB, or credential file. |
| **Install-time execution** | No `setup.py`, no custom build backend, and no `eval`/`exec` in `skillsmgr/` — nothing repo-supplied runs at `pip install`. |
| **Loopback enforcement** | `desktop_launcher.validate_host` **and** `WebAppServer.__init__` independently reject any non-loopback host. |
| **SQL injection** | Every statement is parameterized; no string-interpolated SQL found. |
| **Terminal injection** | Skill names cannot contain ANSI escapes (rejected by the canonical-name regex). |
| **Concurrency deadlock** | No ABBA lock ordering found; the mutation lock is a single per-path `RLock`. |

---

## 3. Security findings — detail

### SEC-1 — `GET` routes bypass the entire Host/Origin/Fetch-Metadata policy *(High)*

**Location:** `skillsmgr/webapp.py:234-238` vs `:240-266`; policy at `skillsmgr/web_security.py:24-56`

```python
234:    def do_GET(self):
235:        try:
236:            self._route_get()
237:        except Exception as exc:
238:            self._handle_exception(exc)
```

```python
240:    def do_POST(self):
241:        try:
242:            self._validate_mutation_request()
243:            self._route_post()
```

`do_GET` is the **only** verb handler that never calls `_validate_mutation_request()`. `web_security.validate_mutation_request` is therefore a *mutation-only* policy, despite the `Host` header check being meaningful for every request — a `Host` check is a DNS-rebinding defence, not a CSRF defence. The docstring at `web_security.py:30-35` records this as intentional ("Header-absent local CLI/test clients remain valid"), but the consequence is that **all 18 read endpoints are unprotected**.

**Exploitability.** A web page the user visits issues `fetch("http://127.0.0.1:8765/api/skills", {mode:"no-cors"})`. `no-cors` sends the request and the `Host` header is automatically `127.0.0.1:8765`, which *satisfies* the allowlist — but even a mismatched `Host` is irrelevant because the check never runs. The response body is opaque to an attacker page that cannot read it cross-origin; however:
* an attacker page on a host that resolves to `127.0.0.1` (DNS rebinding) reads the body **in full**;
* `/api/export` returns a `Content-Disposition: attachment` archive, and a same-origin-navigated download, `<iframe>`, or rebinding read extracts it;
* any local non-browser process (and any other user on a shared machine) can read everything with a one-line `curl` that sets an unrelated `Host`.

**Confirmed evidence** — a live `WebAppServer` on `127.0.0.1:<port>`, request sent with `Host: evil.attacker.example:<port>`:

```text
allowed_hosts = ['127.0.0.1:33619']
allowed_origins = ['http://127.0.0.1:33619']

### A) GET /api/skills with attacker-controlled Host
HTTP 200
BODY: [{"name": "demo-skill", "status": "active", "description": "a demo skill",
       ... "provenance": {"path": "/tmp/probe-host-.../skills/demo-skil...

### B) control: correct Host
HTTP 200 | bytes: 825

### C) GET /api/export?full=1 with attacker Host (mass exfil)
HTTP 200 | bytes: 561 | gzip: True
   member: skills/demo-skill/SKILL.md
   member: manifest.json
   ---- SKILL.md content exfiltrated ----
   ---
   name: demo-skill
   description: a demo skill
   ---
   # Demo

   SENSITIVE BODY CONTENT

### D) control: POST /api/rebuild with attacker Host (should 403)
HTTP 403 b'{"error": "invalid Host header"}'

### E) GET with cross-site Sec-Fetch-Site + Origin + Referer (all hostile)
HTTP 200 | bytes: 825      <-- still served
```

Cases **A**, **C** and **E** all returned full data despite a hostile `Host`, hostile `Origin`, hostile `Referer`, **and** `Sec-Fetch-Site: cross-site` — the strongest possible browser signal that the request is not from the app itself. Case **D** shows the guard works perfectly on the mutation path, which isolates the defect to the missing call in `do_GET`.

**Impact statement.** While the server runs, any web page the user visits (or any local process) can enumerate every installed skill, read every `SKILL.md` body and frontmatter, read the trash, templates and history, and download the complete export archive — with no authentication and no origin check.

**Suggested fix (not applied).** Call the same policy from `do_GET` (rename it `validate_request`), or add a separate read policy that still enforces `Host` and rejects `Sec-Fetch-Site: cross-site`. Either way, keep the loopback-only bind as defence in depth rather than the sole control.

---

### SEC-2 — Unbounded `rglob` of an attacker-chosen directory *(High, availability)*

**Location:** `skillsmgr/effective.py:258-272` (`_nested_roots`), bounded only by `MAX_ROOTS` at `effective.py:36`; reached from `skillsmgr/webapp.py:126-134` via `GET /api/doctor?explain=…&project=…`

```python
258: def _nested_roots(project: Path | None, rel: str) -> list[Path]:
259:     """Project-relative roots below the project root (nested discovery)."""
260:     if project is None or not project.is_dir():
261:         return []
262:     top = project / rel
263:     found: list[Path] = []
264:     try:
265:         for candidate in project.rglob(rel):     # <-- walks the WHOLE tree
266:             if len(found) >= MAX_ROOTS:          # <-- breaks only ON A MATCH
267:                 break
```

`MAX_ROOTS` caps the number of *results*, not the amount of *work*. `Path.rglob` is a generator that must descend the entire directory tree to prove no further match exists, so when `project` contains **no** `.cursor/skills` directory the loop runs to completion over every file and directory. `project` is taken verbatim from the query string with no allowlist, no confinement to the data dir, and no time budget:

```python
132:            (qs.get("project", [""])[0] or "").strip() or None,
```

**Confirmed evidence** — every request below used `Host: evil.example:<port>` (see SEC-1) and `GET`, so no policy was consulted:

```text
built synthetic project: 14400 leaf dirs under /tmp/probe-proj-...
--- baseline: lightweight GET ---            (200, 2, 0.0041s)
--- GET /api/doctor?explain=cursor&project=<14400 dirs> ---
status=200 bytes=86803 elapsed=0.72s
--- same but project=/ (real filesystem root), 25s cap ---
status=None bytes=None elapsed=25.02s err=timed out
```

```text
### A. rglob cost scales with the tree, Host-agnostic ###
  missing project    -> 200 968B in 0.00s
  small dir          -> 200 86794B in 0.04s
  /usr (medium)      -> 200 86749B in 8.68s
### B. project=/ (whole filesystem) with 60s budget ###
  -> ERR:TimeoutError 0B in 60.06s
### C. other consumers also rglob (nested roots) ###
  cursor         -> 200 6.50s
  opencode       -> 200 0.62s
  windsurf       -> 200 0.00s
  claude-code    -> 200 2.29s
  codex          -> 200 0.41s
  gemini         -> 200 0.34s
### D. concurrency: 40 parallel slow requests
  40 concurrent doctor requests finished in 61.18s
  sample results: [('ERR:TimeoutError', 0, 60.06s), ('ERR:TimeoutError', 0, 60.06s), ...]
  server threads: 43
### E. does a slow GET block a normal one?
  concurrent trivial GET: (200, 784, 0.041s)
```

**Notes on severity.** `ThreadingHTTPServer` spawns one thread per connection with no cap or timeout, so 40 concurrent requests produced 43 live threads; an attacker can hold arbitrarily many by opening more connections. Test **E** shows a well-behaved request is *not* blocked while a walk runs, which is the one mitigating fact — this is resource exhaustion, not a service outage, on a fast machine. On a machine with a large `/home` or a network mount it becomes practically total. The unauthenticated `curl` variant needs no browser at all.

**Root cause.** `MAX_ROOTS` is a result cap guarding an unbounded search. The correct bound is on *work*: an iteration budget, a `os.scandir`-based depth-limited walk, an allowlist restricting `project` to the data dir or an explicit project root, plus a per-request timeout.

---

### SEC-3 — `GET /api/doctor?explain=…` discloses the user's real agent-skill inventory *(High, confidentiality)*

**Location:** `skillsmgr/effective.py:237-244` (`_facade_root` → `scopes.known_scopes()`), surfaced by `skillsmgr/webapp.py:109-135`

```python
237: def _facade_root(scope_id: str) -> Path | None:
238:     """Return one facade root by scope id, or ``None`` when it is unknown."""
239:     from . import scopes
240:     for scope in scopes.known_scopes():
241:         if scope.id == scope_id:
242:             return scope.base
```

A `user`-tier root resolves to the **real** `~/.cursor/skills`, and `user-agents` to the **real** `~/.agents/skills`, regardless of which data dir the server was constructed against. `_doctor_payload` then merges the whole `store.doctor()` payload — which includes an absolute `data_dir` — with a full instance listing including `name`, `description`, and absolute `path` for every skill the user has installed for their coding agents.

**Confirmed evidence** — a deliberately hostile request (`Host: totally-not-loopback.example`, `Sec-Fetch-Site: cross-site`, `Sec-Fetch-Mode: no-cors`, hostile `Origin` and `Referer`), two skills in the server's own data dir, `project=/tmp`:

```text
HTTP 200  89052 bytes

data_dir LEAKED: /tmp/probe-leak4-6fvlqg0z

INSTANCES LEAKED (from the user's real agent dirs): 62
  [user-agents] add-task
          desc: creates draft task file in .specs/tasks/draft/ with original user inte
          path: /home/uday-varmora/.agents/skills/add-task
  [user-agents] agent-only
          desc: needle in agent scope
          path: /home/uday-varmora/.agents/skills/agent-only
  [user-agents] analyse
          desc: Auto-selects best Kaizen method (Gemba Walk, Value Stream, or Muda) fo
          path: /home/uday-varmora/.agents/skills/analyse
  [user-agents] chrome-devtools
          desc: Uses Chrome DevTools via MCP for efficient debugging, troubleshooting
          path: /home/uday-varmora/.agents/skills/chrome-devtools
  ... and 58 more
```

The same endpoint is an **arbitrary-directory oracle** for roots:

```text
=== project=/etc  resolution=undocumented-precedence ===
  tier=user             roots=1 inst=0 skipped=0   /home/uday-varmora/.cursor/skills
  tier=user-agents      roots=1 inst=60 skipped=2  /home/uday-varmora/.agents/skills
  tier=project          roots=1 inst=0 skipped=0   /etc/.cursor/skills
  tier=project-agents   roots=1 inst=0 skipped=0   /etc/.agents/skills
  DISCLOSED PATHS (4):
      /home/uday-varmora/.cursor/skills
      /home/uday-varmora/.agents/skills
      /etc/.cursor/skills
      /etc/.agents/skills
```

**Impact.** A visited web page learns: the OS username and home directory, the exact `data_dir`, which agent tools the user uses, and the complete name/description/path inventory of every skill installed for those tools. Skill descriptions routinely describe the user's internal workflows, tools, and systems (`gha-security-review`, `first-principles-production-engineering`, customer-specific skills). An unreadable directory (`/root`) still distinguishes itself via `HTTP 500` vs `200`, giving a directory-existence oracle.

**Note on the honest caveat.** The disclosure is delivered as a JSON body, so plain `no-cors` cross-origin `fetch` cannot read it; DNS rebinding or a non-browser local client can. It is nevertheless a confidentiality defect independent of SEC-1: the endpoint should never return the user's real agent-skill inventory to an unauthenticated HTTP caller, and the existing `/api/skills?scope=all` already exposes a *narrower*, data-dir-scoped view for the UI's needs.

**Suggested fix (not applied).** Restrict `explain` to a project path that is inside an allowlisted root, or gate the `explain` block behind the same origin policy as mutations and behind an explicit `--diagnostics` opt-in.

---

### SEC-4 — `script-src 'unsafe-eval'` is required by the in-DOM template *(Medium)*

**Location:** `skillsmgr/webapp.py:198-202`, `skillsmgr/webui/app.js:12` and `:983`

```python
198:        self.send_header(
199:            "Content-Security-Policy",
200:            "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
201:            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
202:        )
```

```js
 12: createApp({          // no `template:` and no `render:` option
983: }).mount("#app");     // compiles the in-DOM markup of index.html at runtime
```

The vendored bundle is the **runtime + compiler** build (`vue v3.5.13`; `compileToFunction` present), and `app.js` passes no `template`/`render`, so Vue compiles `index.html`'s `#app` markup with `Function(code)()` at startup. **Removing `'unsafe-eval'` would break the app entirely** — this is a build-shape consequence, not an oversight. The locked constraint "Web UI: stdlib backend, no build step" (`AGENTS.md`) is the direct cause.

**Assessment.** Not attacker-reachable on its own: the frontend audit found no HTML-injection primitive (see §2.3), and `'unsafe-inline'` is correctly **absent** from `script-src`, so an injected `<script>` or `onerror=` would still be blocked. Its real cost is that it pre-emptively neutralises CSP as the barrier that would otherwise contain *the next* injection bug — and a markdown renderer handling attacker-authored `SKILL.md` files is exactly the code most likely to grow one.

**Suggested fix (not applied).** Either (a) document it in `docs/08-web-ui.md` as a reasoned trade-off so it is not "fixed" by accident, or (b) ship a precompiled `render` function beside `index.html` and drop `'unsafe-eval'` — the only real fix, and it requires a build step.

---

### SEC-5 — CSP gaps and header-less 501 responses *(Medium)*

**Location:** `skillsmgr/webapp.py:193-202`, and the inherited `BaseHTTPRequestHandler.send_error` path

```python
    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
```

Confirmed by probing the live server:

```text
### 5. methods not implemented (HEAD/OPTIONS/TRACE) ###
  HEAD     -> 501 b''            CSP=False
  OPTIONS  -> 501 b'<!DOCTYPE HTML>\n<html lang="en">\n    <head>\n        <meta ch' CSP=False
  TRACE    -> 501 b'<!DOCTYPE HTML>\n<html lang="en">\n    <head>\n        <meta ch' CSP=False
  PATCH    -> 404 b'{"error": "unknown endpoint"}' CSP=True
### 6. security headers present on an error response? ###
  404 -> 404; nosniff / DENY / CSP=True
  403 -> 403; headers=[..., 'Content-Security-Policy', ...]
```

Two distinct gaps:
1. `form-action` is **absent**. `form-action` does not fall back to `default-src`, so a future injected `<form action="https://attacker/">` would be allowed to submit despite `default-src 'self'`. There is no `<form>` element today, so this is defence-in-depth and cheap to close.
2. Unmatched methods (`HEAD`, `OPTIONS`, `TRACE`) fall through to `BaseHTTPRequestHandler.send_error`, which emits a 30-line **HTML** error page **with none of the security headers** — including no `nosniff` and no framing protection. Every other response path (including the 403 from the mutation policy) carries them, which shows the miss is accidental rather than considered.

`TRACE` returning `501` rather than echoing the request is correct and worth preserving.

**Suggested fix (not applied).** Add `; form-action 'none'` to the CSP string, and override `send_error` (or the `do_*` fallbacks) to route through `self._send` so every response carries the header set.

---

### SEC-6 — `/api/import` multipart crashes with `500` on a filename collision *(Medium)*

**Location:** `skillsmgr/web_upload.py:86-98`; reached from `skillsmgr/webapp.py:875-882`

```python
 86:        for part in file_parts:
 87:            rel = part["filename"]
 88:            if not rel or rel.startswith("/") or ".." in Path(rel).parts:
 89:                continue
 90:            target = (tmp_root / rel).resolve()
 ...
 97:            target.parent.mkdir(parents=True, exist_ok=True)
 98:            target.write_bytes(part["content"])
```

**Confirmed evidence** — a two-part upload where one part is `a/b/SKILL.md` (creating directory `a`) and the next is `a` (a file at that path):

```text
webui internal error: IsADirectoryError(21, 'Is a directory')
### endpoint: file/dir name collision -> ? ###
   (500, b'{"error": "internal error"}')
### endpoint: NUL byte in filename -> ? ###
   (400, b'{"error": "embedded null byte"}')
### endpoint: normal upload (control) ###
   200 b'{"imported": ["good"], "skipped": []}'
```

`IsADirectoryError` is an `OSError`, not a `StoreError`, so it escapes the `except StoreError` handling in `_route_put` and reaches the generic handler, which prints the raw exception to the server's stderr and returns `500 internal error`. The NUL case happens to be caught one layer up but still returns a raw Python error string to the client. A hostile or merely unlucky upload therefore crashes the request and leaks diagnostics to the server log, and the client gets a message that describes nothing actionable.

**Suggested fix (not applied).** Wrap the staging loop and translate `OSError`/`ValueError` into `StoreError`, and detect the collision explicitly so the user gets "a file and a directory share the name `a`".

---

### SEC-7 — Release job with `contents: write` executes a PyPI distribution *(Medium)*

**Location:** `.github/workflows/release.yml:153-158` and `:182-188`

```yaml
  github-release:
    name: github release + post-publish verification
    permissions:
      contents: write
```
```yaml
        run: |
          python3 -m venv /tmp/pypi-verify-venv
          /tmp/pypi-verify-venv/bin/python -m pip install --no-deps "skill-control-plane==${GITHUB_REF_NAME#v}"
          /tmp/pypi-verify-venv/bin/python -m skillsmgr --help
```

This job is **not** covered by an `environment:` gate (unlike `publish-testpypi` at `:118` and `publish-pypi` at `:138`), yet its `GITHUB_TOKEN` can write repository contents, push refs, and create or delete releases. A poisoned or takeover-renamed distribution on the public index therefore executes attacker Python while a write-capable token is live. The wheel is already downloaded locally at `:164-168`, so the network fetch is unnecessary for the check.

**Suggested fix (not applied).** Verify the local `dist/*.whl` instead, or split the network install into a `permissions: { contents: read }` step.

---

### SEC-8 — Attested artifacts are built by an unpinned toolchain *(Medium)*

**Location:** `pyproject.toml:1-3`, consumed at `.github/workflows/release.yml:53-56` and `ci.yml:69-72`

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"
```

The backend is resolved fresh inside `build`'s isolated environment on every release run, so whatever `setuptools` PyPI serves at that moment determines the bytes of the wheel and sdist. `actions/attest-build-provenance` (`release.yml:109-112`) then **truthfully attests** that those bytes came from this workflow, and trusted publishing republishes them. Reproducibility is the premise of provenance; a floating build backend undermines exactly the guarantee the pipeline advertises.

**Suggested fix (not applied).** Pin the backend (`requires = ["setuptools==<exact>"]`) and install build tooling with `--require-hashes` from a checked-in lock, or build inside a pinned container digest.

---

### SEC-9 — Vendored Vue has no integrity assertion on any gate *(Medium)*

**Location:** `check_package_data.py:125-127`; also `.github/workflows/release.yml:177`, `:187`, `smoke_web.py:43-44`

```python
    vue = files.get(VUE_MEMBER, b"")
    if not vue:
        raise AssertionError(f"{path.name} contains no vendored Vue payload: {VUE_MEMBER}")
```

Every existing check is *existence* or *non-emptiness* shaped. `node --check` runs only on `app.js`/`domain.js` (`ci.yml:137-138`), never on the vendor file. Consequently a PR whose only change is the 158 KB minified `skillsmgr/webui/static/vendor/vue.global.prod.js` is green in `unit`, `adversarial`, `package`, `xplat`, and `browser` — and that file executes same-origin with full access to the local REST API, including every mutation endpoint. A diff that large is also effectively unreviewable by a human. This is the highest-leverage packaging finding: it is the only path by which a single unreviewable file becomes arbitrary code execution in every user's app.

**Suggested fix (not applied).** Record the upstream Vue version and expected SHA-256 in the repo and assert `hashlib.sha256(vue).hexdigest()` in `check_package_data.py::inspect_archive` and `tests/test_package_data.py`.

---

### SEC-10 — Full multi-scope filesystem rescan per unauthenticated request *(Low, availability)*

`GET /api/tokens` with no `name` calls `scopes.list_all()`, which reads and parses every `SKILL.md` across every scope and estimates tokens for each. It runs before any `name`/`text` short-circuit, and with an unknown `name` it *still* calls `list_all()` first.

**Confirmed evidence:**

```text
### 7. /api/tokens expensive path (list_all) unauthenticated ###
  200 2.688s bytes=497
  name=missing -> 404 2.435s b'{"error": "skill \'does-not-exist\' not found"}'
```

`GET /api/skills?scope=all` and `GET /api/stats` do the same. 2.4–2.7 s of CPU per request, repeatable, unauthenticated, with no caching and no concurrency cap. This pairs with SEC-1 and SEC-2 into a cheap amplification primitive.

---

### SEC-11 — Multipart parser silently alters uploaded content *(Low)*

**Location:** `skillsmgr/web_upload.py:29-52`

```python
29:    delimiter = b"--" + boundary.encode()
30:    parts = []
31:    for chunk in raw.split(delimiter):      # <-- splits anywhere in file bytes
32:        chunk = chunk.strip(b"\r\n")
...
38:        content = content.rstrip(b"\r\n")   # <-- strips real trailing newlines
```

**Confirmed evidence:**

```text
### exact delimiter '--'+boundary inside file content ###
  parts=1
  content=b'---\nname: x\ndescription: d\n---\nbefore'
  original len=75 parsed len=37
  *** SILENT TRUNCATION: True

### 1. trailing newlines of uploaded content are lost? ###
  original (39B): b'---\nname: x\ndescription: d\n---\nline1\n\n\n'
  parsed   (36B): b'---\nname: x\ndescription: d\n---\nline1'
  *** CONTENT CHANGED: True  (lost 3 trailing bytes)

### endpoint: normal upload (control) ###
   200 b'{"imported": ["good"], "skipped": []}'
  stored bytes: '---\nname: good\ndescription: a good skill\n---\n\n\nbody'
```

The control case is the damaging one: a user uploading a folder through the Web UI gets a **stored `SKILL.md` that differs from the file on their disk** — trailing blank lines are removed, and content is silently cut at any literal `--<boundary>` sequence. The `--boundary` collision needs the attacker/browser to know the boundary (browsers generate it randomly), so it is unlikely in practice; the trailing-newline stripping is unconditional and affects every upload.

Also confirmed: `parse_multipart` builds the filename match with `re.search(r'filename="([^"]*)"', disposition)`, so a filename containing `"` is silently truncated — `a" evil/SKILL.md` parsed as `a`.

**Suggested fix (not applied).** Strip exactly one trailing `\r\n` (the part delimiter) rather than using `rstrip`, parse `Content-Disposition` with `email.message.Message.get_filename()` instead of a regex, and reject a boundary appearing inside part content.

---

### SEC-12 — `mutation_lock` is process-local only *(Low)*

**Location:** `skillsmgr/atomic_io.py:12-20`

```python
12: _MUTATION_LOCKS: dict[str, threading.RLock] = {}
13: _MUTATION_LOCKS_GUARD = threading.Lock()
14:
16: def mutation_lock(path: Path) -> threading.RLock:
17:     """Return a process-local lock for one resolved mutation path."""
18:     key = str(Path(path).expanduser().resolve())
19:     with _MUTATION_LOCKS_GUARD:
20:         return _MUTATION_LOCKS.setdefault(key, threading.RLock())
```

The docstring is honest ("process-local"), so this is a documented limitation rather than a hidden bug — but it is a **real** data-integrity exposure for this product's normal usage: `skillsmgr webui` may be running while the user runs `skillsmgr edit` in a terminal, or while a second `skillsmgr` process runs from a script. Both processes mutate the same `<data>/skills/<name>/SKILL.md` with no lock between them. The in-process races that `mutation_lock` *does* cover are handled; the cross-process ones are not covered by anything.

The follow-up `atomic_write_text` cleanup (`atomic_io.py:59-71`) documents "a concurrent whole-directory move (cross-process trash/remove) may have carried the unique temp file away" — that comment acknowledges cross-process activity while the lock that would prevent it does not exist. This is the clearest internal inconsistency in the concurrency design.

**Suggested fix (not applied).** Add an `fcntl.flock`-based advisory lock (with a Windows fallback) keyed on the same path, or document the single-process requirement in `SECURITY.md` and refuse to start the Web UI when another instance holds the data dir.

---

### SEC-13 — sdist ships `tests/` and no gate inspects non-`webui` members *(Low)*

**Location:** `pyproject.toml:40-44` (no `MANIFEST.in`), `check_package_data.py:115`

```text
tar -tzf dist/skills_manager-1.0.0.tar.gz | grep tests/     -> 19 tests/test_*.py members
```

Mechanism is the distutils default `optional = ['tests/test*.py', 'test/test*.py', 'setup.cfg']` (`setuptools/_distutils/command/sdist.py:295`). `check_package_data.py:115` computes `actual` filtered to `name.startswith("skillsmgr/webui/")`, so `tests/`, `docs/`, `.env`, or a `skills-manager.db` added to a build would never be flagged. Today the leaked content is only test sources; the finding matters because there is a *silent* path for anything else to ship.

**Suggested fix (not applied).** Add `MANIFEST.in` with `prune tests` and make `check_package_data.py` fail on any member outside `skillsmgr/`, `LICENSE`, `README.md`, `pyproject.toml`, `*.egg-info/*`.

---

### SEC-14 — Provenance-signing actions on mutable tags *(Low)*

**Location:** `.github/workflows/release.yml:110` (`actions/attest-build-provenance@v2`) and the `@v4`/`@v5` refs throughout both workflows.

Third-party actions are correctly SHA-pinned (`pypa/gh-action-pypi-publish@dc37677b…`, `softprops/action-gh-release@6cbd405e…`) and `tests/test_ci_release_contracts.py:120-130` enforces it. First-party `actions/*` are exempted by the regex and run on moving major tags. Notably `release.yml:11-12` **already records the exact SHA** for `attest-build-provenance@v2 = 96b4a1ef7235a096b17240c259729fdd70c83d45` — the pin was verified for the comment but not applied to the `uses:`.

**Suggested fix (not applied).** Apply the recorded SHAs to the publish/provenance-adjacent actions, keeping the version comments.

---

### SEC-15 / SEC-16 — Browser harness hardening *(Low)*

**Location:** `browser_harness.py:114`, `browser_harness.py:33-38`, `desktop_launcher.py:75-81`

```python
chrome = subprocess.Popen([_chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--remote-debugging-port=0", "--user-data-dir=" + str(profile), "about:blank"], ...)
```

`--no-sandbox` removes the renderer sandbox while the browser renders repository- and PR-supplied HTML/JS, in the CI `browser` job (`ci.yml:139`) and locally per `CONTRIBUTING.md`; the CDP endpoint it exposes is unauthenticated by design. Separately, both `find_chromium` and the harness's Node lookup execute the **first `PATH` match** with no ownership or permission verification, so an attacker-influenced `PATH` (cron/systemd wrapper, container image, world-writable directory earlier in `PATH`) yields arbitrary execution. Both require local/env influence, hence Low; they are cheap to close.

---

### SEC-17 / SEC-18 / SEC-19 — Governance, gitignore, trust root *(Info)*

* **SEC-17** No `.github/CODEOWNERS`, no `.github/dependabot.yml`; nothing enforces review of `.github/workflows/**`, and the only `contents: write` job lacks the `environment:` gate its siblings have.
* **SEC-18** `.gitignore` states the intent ("Data dirs created at runtime (never commit user skills)") in a comment but has no rule for `.env`, `*.db`, `*.sqlite*`, `*.pem`, `*.key`, `.netrc`. Nothing sensitive is tracked today; this is preventive.
* **SEC-19** `skillsmgr/paths.py:19-30` accepts `SKILLS_MANAGER_DATA`/`XDG_DATA_HOME` with no confinement or ownership check, and that value *is* the trust root for `contained_path`. Containment is therefore only enforced **below** an attacker-chosen root. Not remotely exploitable (it needs environment control of the user's own process, and tests/`CONTRIBUTING.md:32` depend on it), but it deserves an explicit note in `SECURITY.md`.

---

## 4. Correctness / loop-engineering bug findings — detail

### BUG-1 — `Store.create()` raises a raw `sqlite3.OperationalError` on a fresh data dir *(High)*

**Location:** `skillsmgr/store.py:746-775` (`create`, no `_init_db()`), `:840` (`_upsert_entry`), `:519` (the failing statement)

`_init_db()` is called from exactly eleven methods — `resync` (591/600), `list` (653), `get` (692), `search` (728), `add` (892), `stats` (1266), `export` (1308), `import_` (1376), `history` (1505), `doctor` (1525) — but **not** from `create`. Every other public entry point bootstraps the schema; `create` does not.

**Confirmed evidence** — first-ever mutation on an empty data dir:

```text
method         outcome
------------------------------------------------------------------------------
create         *** RAW sqlite3.OperationalError: no such table: skills
list           OK
get            StoreError (clean): skill 'alpha' is not installed
search         OK
stats          OK
history        OK
trash_list     OK
doctor         OK
db_rebuild     OK
resync         OK
purge_trash    OK
export         OK

=== second: create() after a successful read path (list) on same fresh store ===
list() -> OK (schema created)
create() after list -> OK: beta
```

The last block isolates the condition precisely: `create` works as soon as *any* read path has run first, which is why the defect survives a 477-test suite in which `setUp` calls `init_db()` (`tests/test_store_contracts.py:38-39`).

**Why High.** `store.py`'s own docstring states the DB is "a rebuildable index over that tree". Rebuildability implies any operation can recreate its index, and `create` violates that. Worse, the failure is **not** clean: `_create_unlocked`'s `except Exception` handler (`store.py:847-862`) attempts a rollback that itself fails (`no such table: history`), logs `create cleanup failed for 'demo-skill'` to stderr, and then re-raises the **raw** driver exception. `cli.py:107` catches `(StoreError, ValueError, OSError)` — `sqlite3.OperationalError` is none of those, so it falls to `cli.py:113` and the user sees `unexpected error: no such table: skills`, which is precisely the raw-traceback class `AGENTS.md` forbids. The Web UI returns `500 internal error`. On the CLI the window is narrow (`cli_handlers.make_store` calls `store.init_db()` at `:129`), but **any embedding of `Store` as a library** — including a future module, a script, or a test that omits `init_db()` — hits it, and the artifact left behind is a skill directory that was `mkdir`'d before the failure.

**Suggested fix (not applied).** Call `_init_db()` at the top of `create` (matching `add`, `list`, `get`), and convert `sqlite3.Error` into `StoreError` at the `_connect`/`_upsert_entry` seam so no driver exception can escape.

---

### BUG-2 — `loader`/`effective` call an invalid document `loadable` while `validator` calls it an error *(High)*

**Location:** `skillsmgr/effective.py:291-305` (`_classify`) and `skillsmgr/loader.py`; compare `skillsmgr/validator.py:129+` (`validate_text`)

`_classify` marks an instance loadable unless it is `disabled` or `malformed`. `malformed` is set only for a **decode** failure, not for a **missing or invalid frontmatter**. A `SKILL.md` containing nothing but a markdown heading is therefore reported as a healthy, effective, loadable skill.

**Confirmed evidence** — a `SKILL.md` with no frontmatter at all, in a project `.cursor/skills/broken/`:

```text
resolution: undocumented-precedence
skill entry: {
 "skill": "broken",
 "resolution": "undocumented-precedence",
 "candidates": [
  {
   "name": "broken",
   "path": "/tmp/probe-nofm-home-.../proj/.cursor/skills/broken",
   "tier": "project",
   "state": "loadable",            <-- reported healthy
   "disabled": false,
   "malformed": false,
   "description": "",              <-- empty, silently
   "effective_state": "unresolved"
  }
 ],
 "shadowed": [],
  LOADABLE tier=project name='broken' state=loadable desc='' malformed=False

validate_skill says:
  valid: False
   [error] name: 'name' is required
   [error] description: 'description' is required
   [warning] description: description is very short; expand it to a full sentence

loader says:
  [{'name': 'broken', 'disabled': 0, 'malformed': False, ... 'description': '', ...}]
```

Two `error`-level validator issues, three tiers apart from the loader's verdict. `effective.py:1-23` states the module's purpose as deriving "which instance of a skill a consumer would load … and say so" while never guessing; reporting a consumer-loadable state for a document the validator rejects as invalid *is* a guess, and it is the exact failure mode the `skipped_reason` machinery (`effective.py:296-304`) exists to prevent.

**Impact.** The `doctor --explain` diagnostic — whose entire value proposition is trustworthiness — will report an invalid skill as effective and shadowing a valid one in a lower tier. A user debugging "why is my skill not loading?" gets a confidently wrong answer. It also means `effective` and `validate` disagree about the same file, so the UI can show a green "loadable" state for a skill the Validate dialog reports as broken.

**Suggested fix (not applied).** Have `loader` set `malformed=True` (or a distinct `invalid`) when `parse_frontmatter` yields no `name`/`description`, matching `validate_text`; or have `_classify` consult `validator.validate_text` for the validity verdict instead of relying on a decode-only flag.

---

### BUG-3 — same-named skill in another scope cannot be selected *(Medium)*

**Location:** `skillsmgr/webui/app.js:342-345`

```js
    selectSkill(s) {
      if (this.selectedName === s.name) return;
      this.loadDetail(s.name, s.scope);
    },
```

`index.html:124` keys rows by `s.scope + '/' + s.name` and `:132` displays `s.scope_label`, so the UI explicitly supports the same name in several scopes; `index.html:125` computes the row highlight from `selected.scope`. But `selectSkill` compares only the name, so clicking the other scope's copy is a no-op. `find_duplicates()` exists and the Doctor modal surfaces these duplicates (`index.html:490-499`), so multi-scope names are an expected state, not an edge case.

**Impact.** The detail pane keeps showing the first scope's record — including its `path` and body — while the user believes they selected the second. Subsequent edit/toggle/remove actions then target the wrong scope, and (per BUG-5) the destructive path can be irreversible.

**Suggested fix (not applied).** `if (this.selectedName === s.name && this.selected && this.selected.scope === s.scope) return;`

---

### BUG-4 — search/scope/view state desync *(Medium)*

**Location:** `skillsmgr/webui/app.js:276-279` and `:93-98`

```js
    async applySearch() {
      const q = this.query.trim();
      if (!q) { this.loadSkills(); return; }
      if (this.view !== "skills") return;
```
```js
      activeScope(v) {
        localStorage.setItem("skillsmgr-scope", v);
        this.selectedName = null;
        this.selected = null;
        this.loadSkills();
        this.loadStatsTokens();
      },
```

`switchView('trash')` (`app.js:351-354`) leaves `query` populated while `applySearch` returns early for non-skills views; changing scope calls `loadSkills()` (the full list) instead of `applySearch()`. The search box still displays the term while the list shows unfiltered data. `filteredTrash` (`app.js:70-74`) *does* filter client-side, so the two views behave inconsistently.

**Impact.** The list visibly disagrees with the search input — the user may conclude a skill is missing or act on an unfiltered set believing it is filtered.

**Suggested fix (not applied).** In the `activeScope` watcher use `this.query ? this.applySearch() : this.loadSkills()`, and re-apply the query when entering the `skills` view.

---

### BUG-5 — destructive remove re-derives its scope at confirm time *(Medium)*

**Location:** `skillsmgr/webui/app.js:619-642`

```js
619:    confirmRemove(record) {
622:      this.modals.remove = { name: record.name, mode: "trash" };   // scope discarded
...
639:    async removeSkill(name, purge) {
640:      const sc = (this.selected && this.selected.scope) ? this.selected.scope : (this.activeScope !== "all" ? this.activeScope : "global");
641:      const qp = "?scope=" + encodeURIComponent(sc) + "&purge=" + (purge ? "1" : "0");
642:      await api("/api/skills/" + encodeURIComponent(name) + qp, { method: "DELETE" });
```

`confirmRemove` receives the full record but keeps only `name`; the scope is re-read from the live `this.selected` at delete time. If `selected` changes while the dialog is open — a background `loadSkills()`/`loadScopes()` completing is the realistic path — the `DELETE` targets a different scope than the one the user saw, and with `purge=1` that removal is **permanent**.

**Mitigation present.** The overlays set `inert` on `header`/`main` (`index.html:15`, `:78`, `:308`) and Escape closes the dialog, which blocks mouse-driven changes. The exposure is the async refresh, not user misclick.

**Suggested fix (not applied).** Carry the scope in the modal: `this.modals.remove = { name: record.name, scope: record.scope, mode: "trash" }` and use `m.scope` in `removeSkill`.

---

### BUG-6 — validate errors are never displayed *(Medium)*

**Location:** producer `skillsmgr/webui/app.js:731-732`; consumer `skillsmgr/webui/index.html:441-455`

```js
          } catch (e) {
            m.error = e.message;
```
```html
          <div v-if="modals.validate.result">
```

`grep -n "validate.error" index.html app.js` returns nothing. The field is initialised at `app.js:715` (`error: null`), so the intent is clear; the binding was simply never added. Every user-visible validation failure (unknown skill, backend `StoreError`) produces a dialog that resets `loading` to false and renders **nothing** — no error text, no banner — indistinguishable from "no result".

---

### BUG-7 — template throws when `window_tokens` is missing *(Low)*

**Location:** `skillsmgr/webui/index.html:92`, fed by `skillsmgr/webapp.py:514-545`

```html
  <div v-if="budget" class="budgetbar" :title="'Context: ' + budget.window + ' (' + budget.window_tokens.toLocaleString() + ' tok)'">
```

`window_tokens` is built inside a `try` whose failure is swallowed at `webapp.py:543-544` and still answers `200`; `store.stats()` has no such key, so a swallowed failure yields a 200 JSON without it. `v-if="budget"` then passes, and `.toLocaleString()` on `undefined` throws inside the render function. Every other access on `:104`, `:105`, `:108`, `:109` tolerates `undefined` (`formatTokens` returns `"—"`, `tokenBarWidth` degrades to `"NaN%"`); `:92` is the only throwing one.

---

### BUG-8 — nine silent `except Exception: pass` blocks in `webapp.py` *(Low)*

**Location:** `skillsmgr/webapp.py:124-125`, `:382-383`, `:406-407`, `:481-482`, `:534-535`, `:541-542`, `:543-544`, `:573-574`, `:953-954`

All nine are confirmed by `bandit` (B110, 9 hits) and `ruff` (S110). The consequence is visible: the stats-enrichment failure at `:543` is exactly what produces BUG-7 (a `200` response that is *missing* a documented key), and the SSE/`explain=all` failure at `:124-125` means `/api/doctor?scope=all` silently returns a payload **without** `scopes`/`duplicates` while still reporting success. A client cannot distinguish "no duplicates" from "the duplicate scan crashed". At `:953-954` the swallow hides a failure to inject the global `Store`, whose fallback is a default-root `Store()` (SEC-19 territory).

**Suggested fix (not applied).** Replace with `diagnose(...)` calls (the module already imports it at `webapp.py:24` and uses it in `store.py`) so failures reach stderr, and make the payload report the degradation explicitly.

---

### BUG-9 — wrong-arity `/api/…` paths are served by the static handler *(Low)*

**Location:** `skillsmgr/webapp.py:300-322` (`_serve_static`), called first in `_route_get` at `:328`

`_serve_static` returns `False` only when `rel == "api"`, and `rel` is `parts[0]`. Any `/api/…` path with arity the router does not recognise falls through to the final `else` as `404 unknown endpoint` — correct — but the routing is expressed as a long `if`-chain ending in a generic `404` rather than a dispatch table, and `_route_get`/`_route_post` carry cyclomatic complexity **F (95)** and **F (81)** (radon), the two worst blocks in the codebase. Confirmed reachable: `PATCH` of an unknown path returns `404 unknown endpoint` with security headers, while `HEAD`/`OPTIONS`/`TRACE` return a header-less `501` HTML page (SEC-5).

**Assessment.** Not a live vulnerability; recorded because `_route_get`/`_route_post` being rank F is the structural reason a guard can be omitted from one verb (SEC-1) without any test noticing.

---

### BUG-10 — loader inconsistencies: dot-directories and mojibake descriptions *(Low)*

**Location:** `skillsmgr/loader.py`

```text
=== scan_dir(default) ===
  {"name": ".hidden-skill", "disabled": 0, "malformed": false, "decode_error": null, "description": "hidden dir"}
  {"name": "badenc", "disabled": 0, "malformed": true, "decode_error": "... is not valid UTF-8 (byte 0xff at offset 30)...", "description": "\ufffd\ufffd bad"}
  {"name": "nofm", "disabled": 0, "malformed": false, "decode_error": null, "description": ""}
```

1. A dot-directory in a scope root is listed as a skill whose name includes the leading dot — a name that `validate_skill_name` would **reject**, so the loader can emit records the rest of the system considers impossible. Such a record cannot be edited or removed through the canonical path (every writer validates the name), so it is effectively stuck in the scope listing.
2. A non-UTF-8 document is correctly flagged `malformed` with an excellent `decode_error` — but its `description` is still populated with **replacement characters** (`\ufffd\ufffd bad`) rather than suppressed. That mojibake is then displayed in the UI and counted in stats.
3. `nofm` (no frontmatter) is `malformed: false` with an empty description — the same defect as BUG-2, observed at the loader layer.

---

### BUG-11 — template lock acquired before the directory exists *(Low)*

**Location:** `skillsmgr/templates.py:63-74`

```python
63: def create_template(templates_dir: Path, name: str, body: str | None = None) -> Path:
67:     path = template_path(templates_dir, name)
68:     with _mutation_lock(path):
69:         if path.exists():
70:             raise FileExistsError(f"template '{name}' already exists")
71:         templates_dir.mkdir(parents=True, exist_ok=True)
72:         content = body if body is not None else DEFAULT_TEMPLATE.format(name=name)
73:         _atomic_write_text(path, content)
```

`_mutation_lock` is only an in-memory `RLock` lookup (`atomic_io.py:16-20`) so it does not touch the filesystem and this does not crash today — but the ordering is fragile: it reads as though the lock guards the directory creation, and any future change making the lock file-backed will create a lock file in a directory that does not yet exist. `create_template` is reachable from `POST /api/templates` (`webapp.py:783-799`), and `FileExistsError`/`ValueError` are correctly translated to `StoreError` there — that part is right.

---

### BUG-12 — `_MUTATION_LOCKS` grows without bound *(Low)*

**Location:** `skillsmgr/atomic_io.py:12-20`

One `RLock` is retained per distinct resolved path ever touched, forever, with no eviction. A long-lived Web UI process that creates, trashes, restores and re-creates skills accumulates an entry per unique trash name (`name-<ts>` is unique per removal by construction) — so routine use grows the dict monotonically. Each entry is small, so this is a slow leak, not a practical DoS; it is reported because the fix is trivial and because `mutation_lock` is called on every mutation.

---

### BUG-13 / BUG-14 — packaging and gate blind spots *(Low)*

* **BUG-13** `check_package_data.py:115` filters inspected members to `name.startswith("skillsmgr/webui/")`, so the gate can never see `tests/`, `docs/`, `.env`, or a DB file. See SEC-13.
* **BUG-14** `tests/test_ci_release_contracts.py:19-21`:
  ```python
  _THIRD_PARTY_PIN_RE = re.compile(
      r"^\s*-\s*uses:\s*(?!actions/|github/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([^\s#]+)"
  )
  ```
  The path segment before `@` allows no slashes, so the regex matches neither `owner/repo/.github/workflows/build.yml@main` nor `owner/repo/.github/actions/thing@v1` — exactly the refs that can run arbitrary jobs with the caller's permissions. Adding `uses: attacker/repo/.github/workflows/x.yml@main` to the `id-token: write` job would keep this test green.

---

### BUG-15 — dead code *(Info)*

`vulture` (≥80% confidence) plus manual confirmation:

| Item | Location |
|---|---|
| `_scopeParam()` and `_scopeQs(qs)` defined, never called | `skillsmgr/webui/app.js:243-251` |
| `esc` exported from the frozen interface, never used by `app.js` | `skillsmgr/webui/domain.js:151` |
| unused import `webbrowser` | `skillsmgr/webapp.py:18` |
| unused variable `close_ch` | `skillsmgr/frontmatter.py:429` |
| unused parameter `fmt` | `skillsmgr/webapp.py:181` |

`_scopeQs` is the notable one: scope-qualified URLs are instead built inline in roughly a dozen places (`app.js:260, 286, 311/318, 504, 539, 546, 604, 641, 692, 795, 902`), which is the drift pattern that silently drops or double-adds `?scope=` — the same class as BUG-5.

---

## 4b. Store / data-integrity findings — detail

Findings from the dedicated `store.py` / `archive.py` / `atomic_io.py` workstream. Every item below was reproduced by executed probes under `/tmp/probes/`, each creating its own isolated `SKILLS_MANAGER_DATA`. (Verified afterwards that the real `~/.local/share/skills-manager/skills-manager.db` retained its original mtime — no probe touched real user data.)

### Measured lock coverage (the backbone of STORE-2/4/5/11/12)

| Public method | Lock(s) acquired |
|---|---|
| `create`, `edit`, `remove`, `restore` (trash + snapshot), `disable`, `enable` | `skills/<name>/SKILL.md` |
| `write_snapshot` | `snapshots/<scope>/<name>` |
| **`add`, `import_`, `purge_trash`, `export`/`backup`, `resync`, `db_rebuild`, `init_db`** | **none** |

The only lock primitive is `atomic_io.mutation_lock()`; no global, file-based, or cross-process lock exists anywhere in `store.py` or `atomic_io.py`.

---

### STORE-1 — An interrupt during `import_`'s commit move destroys the user's only copy *(Critical)*

**Location:** `skillsmgr/store.py:1478-1488` + `skillsmgr/archive.py:332-364`

```text
1478:             if full:
1479:                 try:
...
1487:         finally:
1488:             shutil.rmtree(tmp, ignore_errors=True)
```
```text
332:         if dest.exists():
333:             move(str(dest), str(backup))      # user's original -> <tmp>/commit-staging/<name>.backup
334:             moved_original = True
335:         move(str(staged), str(dest))          # <= Ctrl-C here
...
342:     except Exception as exc:                  # BaseException is NOT caught
```

`commit_staged_skill` moves `skills/demo` → `/tmp/skillsmgr-import-XXXX/commit-staging/demo.backup`, then begins `move(staged, dest)`. A SIGINT (`KeyboardInterrupt`), `MemoryError`, or `SystemExit` there is a `BaseException`, so archive.py's `except Exception` rollback never runs; the exception unwinds into `import_`, whose `finally` deletes the whole temp root — **including `demo.backup`, the user's original**. `dest` does not exist, the trash is empty, and nothing remains on disk.

**Confirmed evidence** — `KeyboardInterrupt` injected at the second `shutil.move`, exactly where a real SIGINT can land:

```text
raised: KeyboardInterrupt simulated Ctrl-C during commit move
moves performed: [('.../skills-manager/skills/demo', '/tmp/skillsmgr-import-ph2p9x2a/commit-staging/demo.backup'),
                  ('/tmp/skillsmgr-import-ph2p9x2a/commit-staging/demo', '.../skills-manager/skills/demo')]
live skill dir exists: False
SKILL.md exists: False
staging temp dirs still on disk: []
db row: [('demo', 'active', 'ORIGINAL description')]
doctor: {'ok': False, 'stale_rows': ['demo'], ...}
```
```text
raised: KeyboardInterrupt
rmtree calls (finally clause): ['/tmp/skillsmgr-import-otayzmbu']   # the dir holding the backup
recoverable anywhere under data_dir: []
live dir exists: False
list() still reports: [('demo', 'ORIGINAL')]
get() body: 'ORIGINAL PRECIOUS BODY\n'
resync: {'added': 0, 'updated': 0, 'removed': 1} -> doctor ok: True   # index healed, data gone
SKILL.md on disk after heal: False
```

**Why Critical.** The user's only copy is gone, the tool reports recovery succeeded, and the surviving DB body — the last fragment of the document — is silently discarded by `resync()`. Note the contrast: the same file's `except Exception` path is carefully written and correct for ordinary exceptions. The hole is specifically `BaseException`.

**Suggested fix (not applied).** Keep the displaced original inside the data dir (e.g. `<data>/trash/.skillsmgr-backup-<name>`, same filesystem) and make the rollback `except BaseException`; or wrap the commit in `try/finally` that restores `backup` whenever `dest` is absent, and never `rmtree` a directory that still holds a backup.

---

### STORE-2 — `add()` copies into the live tree with no lock *(High)*

**Location:** `skillsmgr/store.py:865-901`

```text
892:         self._init_db()
893:         shutil.copytree(source, skill_dir)
894:         self._upsert_entry(chosen)
```

Position matters: `remove()` at `store.py:1042-1045` carries a comment promising this cannot happen —

```text
1042:         # Whole-directory moves must serialize with create/edit/restore which
1043:         # lock the same per-skill path; otherwise a concurrent writer can
1044:         # strand its temp file inside a trash copy (see atomic_io).
1046:         return _with_skill_lock(skill_dir, self._remove_unlocked, name, purge=purge)
```

— but `add()` never takes that lock. `add()` begins `copytree` (SKILL.md first, bulk still copying); a concurrent `remove()` takes the lock `add()` does not hold, sees a directory, and moves it to trash. `copytree` then re-creates `skills/fresh` and finishes, and `_upsert_entry` raises. Result: 20,000 orphan files in a live husk, the document only in trash, no index row — and `doctor()` reports `ok: True`.

**Confirmed evidence** — real `copytree` over a 20,001-file source, one poller thread, no monkeypatching:

```text
add() in flight (SKILL.md copied, bulk still copying): True
add -> None skillsmgr.store.SkillNotFound: skill 'fresh' has no SKILL.md (or SKILL.md.disabled) (1.79s)
remove -> ('trashed', 'fresh-2026-09-11_10-08-30Z') None
trash entries: ['fresh-2026-09-11_10-08-30Z']
  fresh-2026-09-11_10-08-30Z: 1 files (source had 20001)
husk skills/fresh exists: True | files: 20000
scan_dir sees it: []
list(): []
doctor ok: True | trash_count: 1 | temporary_files: []
```

A separate probe shows `add()` also leaves a **partially copied** skill and leaks a raw `shutil.Error` (compare `create()`, which cleans up at `store.py:847-862`), and that a subsequent `resync()` silently indexes the partial copy as a valid skill:

```text
EXC type: shutil.Error | EXC is StoreError: False
leftover dest exists: True
leftover tree: ['SKILL.md', 'references', 'scripts', 'scripts/run.sh']
doctor ok: False orphan_dirs: ['broken']
resync: {'added': 1, ...} -> doctor ok: True      # partial copy silently indexed as a skill
```

---

### STORE-3 — `add()` installs a skill with both documents; a later toggle destroys one *(High)*

**Location:** `skillsmgr/store.py:872-875`; contrast `skillsmgr/archive.py:291-296`

```text
872:         if not (source / "SKILL.md").is_file():
873:             raise StoreError(
874:                 f"source must contain SKILL.md (got {source / 'SKILL.md'!s})"
875:             )
```

The invariant *is* implemented — but only the import path calls it:

```text
294:     if enabled and disabled:
295:         raise ArchiveError(f"skill directory contains both enabled and disabled documents: {source.name!r}")
```

`loader.py:69-76` silently prefers `SKILL.md` when both exist, so no view reports the anomaly.

**Confirmed evidence:**

```text
add -> {'name': 'dual', 'path': '.../skills/dual'}
files on disk: ['SKILL.md', 'SKILL.md.disabled']
doctor ok: True      (stale/orphan/drift all [])
resync: {'added': 0, 'updated': 0, 'removed': 0} doctor ok now: True
db_rebuild: {'added': 1, ...} doctor ok now: True
after disable, disabled content: '---\nname: dual\ndescription: Enabled doc\n---\nENABLED BODY\n'
DISABLED BODY lost: True
```
```text
add() -> dual (both documents accepted)
import_ rejects the very same directory: skill directory contains both enabled and disabled documents: 'dual'
enable() on a both-docs skill: {'name': 'dual', 'disabled': False}   # rename overwrote SKILL.md.disabled
```

`Path.rename` replaces the target on POSIX, so `disable()`/`enable()` destroy a document with no error, no `StoreError`, and no snapshot.

---

### STORE-4 — `import_(force=True)` silently discards a committed `edit()` *(High)*

**Location:** `skillsmgr/store.py:1447-1468` (no lock) + `skillsmgr/archive.py:328-341`

The import's `copytree` staging takes time. During that window `edit('demo', body=…)` runs to completion — it takes the per-skill lock, writes atomically, and commits its index row and history. `import_`, holding nothing, then moves the just-edited live directory aside and replaces it with the archive copy; `if backup.exists(): rmtree(backup)` deletes the user's edit. The import's own `_upsert_entry` rewrites the row, so file and index **agree** on the imported version and `doctor()` says `ok: True`.

**Confirmed evidence:**

```text
edit() -> {'name': 'demo', 'changed': True}
edit committed to DB: USER EDIT BODY
import result: {'import': {'imported': ['demo'], 'skipped': [], ...}}
live file content: '---\nname: demo\ndescription: REPLACEMENT\n---\nREPLACEMENT BODY\n'
DB row content: 'REPLACEMENT BODY\n'
history: [('import', 'demo'), ('edit', 'demo'), ('create', 'demo')]
USER EDIT survived anywhere: False
doctor ok: True
```

This is the most dangerous *class* of bug in the report: a silent lost update that every consistency check reports as healthy.

---

### STORE-5 — `restore()`/`purge_trash()` race: raw exception + unrepairable divergence *(High)*

**Location:** `skillsmgr/store.py:1124-1137` (candidate scan **outside** any lock), `:1139-1146`, `:1238-1262` (no lock at all)

Two distinct failures:

**(A, contract)** `restore(name)` selects a trash entry, then `purge_trash()` deletes it; `shutil.move` raises `FileNotFoundError`, which is not caught anywhere in `restore()` → a **raw `OSError` escapes the Store API**, violating `docs/04-store-api.md:13` and `:21`.

**(B, permanent divergence)** purge unlinks the document and `restore()` then moves the husk into `skills/<name>`; `_upsert_entry` raises `SkillNotFound` **before** touching the row, so the row stays `status='trashed'` while the trash directory is gone. `doctor()`'s `ok` predicate includes `not (trashed_names - trash_names)` (`store.py:1579`), so it reports `ok: False` forever; `resync()` only deletes `active` rows (`store.py:638-641`) and never reconciles `trashed` rows. Only `db_rebuild()` heals it — directly contradicting `docs/04-store-api.md:74` ("… and repair guidance via `db resync`").

**Confirmed evidence:**

```text
=== variant A: purge wins between restore()'s scan and its move ===
restore raised: builtins.FileNotFoundError | is StoreError: False | [Errno 2] No such file or directory: '.../trash/demo-...Z'

=== variant B: real purge_trash() thread deletes the document mid-race ===
restore raised: skillsmgr.store.SkillNotFound | skill 'demo' has no SKILL.md (or SKILL.md.disabled)
purge errors: ["StoreError: could not purge trash: [Errno 2] No such file or directory: '.../trash/demo-...Z'"]
live dir exists: True | has SKILL.md: False
live tree: []
index rows: [('demo', 'trashed')]
trash dir entries: []
doctor ok: False | stale_rows: [] | trash_count: 0
resync(): {'added': 0, 'updated': 0, 'removed': 0} -> doctor ok: False
db_rebuild(): {'added': 0, 'updated': 0, 'removed': 0} -> doctor ok: True
```

---

### STORE-6 — `purge_trash()` holds a write transaction across every `rmtree` *(Medium)*

**Location:** `skillsmgr/store.py:1242-1262`

```text
1242:         conn = self._connect()
1243:         try:
1244:             purged = _purge_trash_entries(conn, self.trash_dir, self._purge_entry)
1245:             conn.commit()
```
```text
1253:             shutil.rmtree(path)          # filesystem I/O while the DELETE txn is open
...
1258:         conn.execute(
1259:             "DELETE FROM skills WHERE name = ? AND status = 'trashed'",
```

Python's default `isolation_level=""` keeps the write transaction open until `commit()`; entries 2..N are `rmtree`d inside it. Any other connection then stalls for sqlite3's default 5 s busy timeout and fails with a **raw** `sqlite3.OperationalError`, which `create()` re-raises unchanged.

**Confirmed evidence** (the `rmtree` hook only *slows* the real delete; ordering and transaction lifetime are the code's own):

```text
trash entries: ['t1-...Z', 't0-...Z', 't2-...Z']
purge_trash finished after 12.0s
concurrent create() FAILED after 10.5s: sqlite3.OperationalError | is StoreError: False | database is locked
purge errors: []
concurrent skill on disk: False
index rows: []
```

---

### STORE-7 — `remove(purge=True)` is non-transactional and leaks a raw `PermissionError` *(Medium)*

**Location:** `skillsmgr/store.py:1061-1066`

```text
1061:             if purge:
1062:                 if skill_dir.is_dir():
1063:                     shutil.rmtree(skill_dir)
1064:                 conn.execute("DELETE FROM skills WHERE name = ?", (name,))
1065:                 self._history(conn, name, "purge")
```

`rmtree` fails part-way (unwritable subdirectory, NFS, `ENOTEMPTY`); `SKILL.md` has already been unlinked; the exception escapes as a raw `PermissionError` — note `purge_trash()`'s own path deliberately wraps the identical call into `StoreError` (`store.py:1254-1257`), so the inconsistency is `remove`'s. The row is still `active`, so `list()` keeps advertising a skill whose document no longer exists.

**Confirmed evidence** (no patching; `scripts/` chmod 0500, uid 1000):

```text
remove(purge=True) raised: builtins.PermissionError | is StoreError: False | [Errno 13] Permission denied: 'run.sh'
live dir still exists: True
remaining tree: ['scripts', 'scripts/run.sh']       # SKILL.md already deleted
list(): [('demo', 'active')]
doctor ok: False | drift: [] | stale: ['demo']
resync: {'added': 0, 'updated': 0, 'removed': 1} -> doctor ok: True | list(): []
```

---

### STORE-8 — `export()` non-atomic, filename collision, truncation on failure *(Medium)*

**Location:** `skillsmgr/store.py:1310-1312`, `:1337`

```text
1310:         if dest is None:
1311:             stem = "full-export" if full else "export"
1312:             dest = self.backups_dir / f"{stem}-{_trash_timestamp()}.tar.gz"
```
```text
1337:         with tarfile.open(dest, "w:gz") as tar:      # writes the final path directly
```

`_trash_timestamp()` has one-second resolution and `export()`/`backup()` share the stem `export`, so two calls in the same second write the same path — the second archive silently replaces the first. `remove()` guards against exactly this with a `-<n>` counter (`store.py:1072-1077`); `export()` does not. Because the tar stream is written straight to `dest`, a failure part-way leaves a truncated, manifest-less file **occupying the good archive's path**.

**Confirmed evidence:**

```text
=== 8a: two archives in the same second share one filename ===
export() -> export-2026-09-11_10-06-05Z.tar.gz
backup() -> export-2026-09-11_10-06-05Z.tar.gz
same path: True
files in backups_dir: ['export-2026-09-11_10-06-05Z.tar.gz']

=== 8b: a failed export truncates the archive in place ===
good archive: .../export-2026-09-11_10-00-00Z.tar.gz 513 bytes, manifest present: True
export raised: OSError [Errno 5] Input/output error
destination after failure: .../export-2026-09-11_10-00-00Z.tar.gz 257 bytes (was 513 )
still readable, members: ['skills/demo/SKILL.md']      # manifest gone: import_ will reject it
```

---

### STORE-9 — Export follows symlinks, producing archives that `import_` rejects *(Medium)*

**Location:** `skillsmgr/store.py:1328-1330`, `:1340-1342`; `skillsmgr/atomic_io.py:75-84`

```text
1340:                 for file in sorted(source.rglob("*")):
1341:                     if file.is_file():
1342:                         tar.add(file, arcname=f"skills/{entry['name']}/{file.relative_to(source)}")
```
```text
81:     for path in sorted(root.rglob("*")):
82:         if path.is_file():              # is_file() follows symlinks
83:             digest.update(str(path.relative_to(root)).encode("utf-8"))
84:             digest.update(path.read_bytes())
```

A skill with an ordinary `scripts/link.sh -> real.sh` symlink exports "successfully", but `tar.add` stores it as a `SYMTYPE` member while `_tree_content_hash` hashed the *followed* bytes — so the manifest hash does not describe the archived tree, and `archive.validate_members` (which allows only `isdir()`/`isreg()`, `archive.py:126-127`) rejects the archive. **The entire archive — every skill in it — becomes non-importable**, so the backup cannot be restored. For links escaping the data dir, the hash also reads files outside the managed root, handing a hash oracle over external data and leaking the absolute target path into the archive.

**Confirmed evidence:**

```text
  member 'skills/demo/scripts/escape.md'  type=b'2' linkname='/tmp/p11b-.../outside.txt'
  member 'skills/demo/scripts/link.sh'    type=b'2' linkname='real.sh'
manifest hash: 6abdf951...
hash over the followed symlink bytes: 6abdf951... (outside.txt bytes are hashed)
import_ FAILED: unsupported archive member type: 'skills/demo/scripts/escape.md'
b has demo: False
```

---

### STORE-10 — Read paths trust SQLite over the filesystem *(Medium)*

**Location:** `skillsmgr/store.py:656-685` (`list`), `:695-720` (`get`), `:731-742` (`search`), `:1269-1278` (`stats`)

```text
664:             for record in result:
665:                 skill_dir = _safe_skill_path(self.skills_dir, record["name"])
666:                 try:
667:                     observed = load_skill(skill_dir)
668:                 except (OSError, SkillNotFound, UnicodeError):
669:                     continue               # row is kept anyway; body/description stay from SQLite
```
```text
702:             result["path"] = str(skill_dir) if skill_dir.is_dir() else None
```

Any crash after the filesystem mutation and before the index commit — `remove()`'s `shutil.move` (`:1078`) → commit (`:1086`) is an 8-line window; STORE-1 is the same shape. Afterwards the FS has no `skills/demo` but SQLite says `active`, so `list()`/`search()` report the skill, `stats()` counts it as active, and `get()` returns the stale stored `body` (only `path: None` hints at reality). This contradicts the project's central documented invariant ("never trust SQLite over the filesystem", `docs/04-store-api.md:11`).

**Confirmed evidence:**

```text
remove raised: simulated crash after the FS move
skills/demo on disk: False
trash entries: ['demo-2026-09-11_10-05-56Z']
index rows: [('demo', 'active')]
list()  -> [('demo', 'Use when probing')]
get()   -> BODY | path: None
search('BODY') -> ['demo']
stats() -> active: 1 trashed: 0
doctor ok: False stale_rows: ['demo']
resync(): {'added': 0, 'updated': 0, 'removed': 1} -> doctor ok: True | list(): []
```

---

### STORE-11 — Process-local lock: cross-process breakage with residue *(Medium)*

**Location:** `skillsmgr/atomic_io.py:12-20`

Two real processes on one data dir (the normal CLI + Web UI situation) produce a raw `FileNotFoundError` out of `enable()` → `Path.rename` (`store.py:1201`) and strand `.skillsmgr-tmp` files inside trash copies — exactly the artifact `mutation_lock` documents itself as preventing, and which `resync()` cannot remove, so `doctor().ok` stays `False` until a human deletes them by hand.

**Confirmed evidence** (seeded `raced` skill; A: `edit` + `disable`/`enable` churn; B: `remove` + `create` churn):

```text
PROC-A raw errors: 1 ["toggle FileNotFoundError: [Errno 2] No such file or directory: '.../skills/raced/SKILL.md.disabled' -> '.../skills/raced/SKILL.md'"]
PROC-B raw errors: 0 []
resync: {'added': 0, 'updated': 0, 'removed': 0}
doctor ok: False | stale: [] | orphan: [] | drift: [] | tmp-artifacts: ['trash/raced-...-1/.SKILL.md.33qk_vvy.skillsmgr-tmp', 'trash/raced-...-20/.SKILL.md.4mzwz2st.skillsmgr-tmp']
trash entries: 150
```

---

### STORE-12 — `resync()` / `db_rebuild()` mutate the index with no lock *(Low)*

**Location:** `skillsmgr/store.py:601-649`, `:1606-1610`

```text
638:             for row in conn.execute("SELECT name FROM skills WHERE status = 'active'"):
639:                 if row["name"] not in scanned:
640:                     conn.execute("DELETE FROM skills WHERE name = ?", (row["name"],))
641:                     removed += 1
```
```text
1606:     def db_rebuild(self) -> dict:
1608:         if self.db_path.exists():
1609:             self.db_path.unlink()
1610:         return self.resync()
```

(a) A skill created between the scan (`:601`) and the delete loop (`:638`) has a live directory but no row — `resync()` reports `removed: 1` for a skill that exists. (b) `db_rebuild()` `unlink()`s the database while another process holds a connection open, and the stale `-journal`/`-wal` siblings are not cleaned either.

**Confirmed evidence:**

```text
=== A: resync() (no lock) deletes the row of a skill created while it scanned ===
resync -> {'added': 0, 'updated': 0, 'removed': 1}
skills/late on disk: True
list(): ['existing']
doctor ok: False | orphan_dirs: ['late']
second resync: {'added': 1, 'updated': 0, 'removed': 0} -> doctor ok: True

=== B: db_rebuild() unlinks the DB under a live connection ===
db_rebuild -> {'added': 1, 'updated': 0, 'removed': 0}
write through the old connection failed with a raw error: sqlite3.OperationalError | attempt to write a readonly database
```

---

### STORE-13 — `doctor()` cannot see real damage *(Low)*

**Location:** `skillsmgr/store.py:1547-1580`

```text
1547:         orphan_dirs = sorted(set(scanned) - active_names)
```

`scanned` comes from `loader.scan_dir`, which skips any directory whose `load_skill` raises `SkillNotFound`, so a directory with no document is neither an orphan dir nor drift. Consequences: the 20,000-file husk from STORE-2, the `scripts/run.sh` leftovers from STORE-7, and the husk from STORE-5 are all invisible; and the `.skillsmgr-tmp` residue from STORE-11 makes `ok: False` with **no supported repair path**, contradicting `docs/04-store-api.md:74`.

**Confirmed evidence:**

```text
=== empty junk dir in skills/ is invisible to scan/doctor ===
doctor ok: True | orphan_dirs: [] | skills_on_disk: 1
resync(): {'added': 0, 'updated': 0, 'removed': 0} | doctor ok: True
husk still there: True
```

---

### STORE-14 — Documented `Store` contract vs implementation *(Low)*

**Location:** `docs/04-store-api.md` lines 27, 33, 34, 35, 116 vs `store.py:465-471`, `651`, `863`, `1037`, `71`

| Doc claims | Actual |
|---|---|
| `:27` `Store(data_dir=None)` "creates layout, inits DB" | constructor only assigns paths (`:465-471`); `data_dir` does not exist afterwards |
| `:35` `list(self, include_disabled=False) -> list[dict]` | `def list(self) -> list[dict]` (`:651`) — documented kwarg raises `TypeError` |
| `:33` `create` "Returns skill dict" | returns `{"name", "path"}` (`:863`) |
| `:34` `edit` "Returns updated skill dict" | returns `{"name", "changed"}` (`:1037`) |
| `:116` `_TRASH_TS_RE` `…(?:-\d+)?Z?$` | code is `…(?:-\d+)?Z?(?:-\d+)?$` (`:71`) — also accepts a `-<n>` suffix after a missing `Z` |

**Confirmed evidence:**

```text
docs/04-store-api.md:27 claims Store(...) 'creates layout, inits DB'
  data_dir exists after ctor: False
  Store().create() -> sqlite3.OperationalError | is StoreError: False | no such table: skills
docs line 35: list(self, include_disabled=False) -> actual (self) -> 'list[dict]'
  store.list(include_disabled=True) -> TypeError | Store.list() got an unexpected keyword argument 'include_disabled'
trash_list() sees: ['d2', 'demo', 'demo', 'demo']
purge_trash() removes: {'purged': ['d2', 'demo']}
```

The `_TRASH_TS_RE` divergence is the consequential one: a tool following the documented regex treats `trash/demo-2024-01-01_00-00-00` (no `Z`) as not-trash while `purge_trash()` deletes it.

**Likely (code-reading only, probes named but not run):**
* `_create_unlocked`'s cleanup (`store.py:851`) runs `DELETE FROM history WHERE name = ? AND action = 'create'`, matching *every* earlier `create` of that name — a failed re-create of a once-removed skill erases its original creation record.
* `archive.py:371-375` swallows a failed rollback silently (`except OSError: pass`), leaving the user's payload only under a dotted backup name with no `_diagnose` line (contrast `store.py`'s consistent `_diagnose` use at 856-861, 1026-1035, 1120-1121).
* `_is_temporary_file`/`_doctor_artifacts` (`store.py:260-267`, `288-304`) flag any file whose name merely ends in `.tmp`/`.temp` anywhere under the data dir, so a user's own `notes.tmp` inside a skill turns `doctor().ok` into `False` with no API-accessible fix.

---

## 4c. Scope-resolution findings — detail

Findings from the dedicated `scopes.py` / `effective.py` / `loader.py` / `root_discovery.py` / `paths.py` workstream. All probes used a fresh isolated `HOME` **and** `SKILLS_MANAGER_DATA`; the real `~/.claude`, `~/.codex`, `~/.agents`, `~/.cursor` and real data dir were never written. Python 3.12.3, uid 1000 (non-root, so permission probes are meaningful).

### The dominant root cause, in one sentence

`scopes.py`/`loader.py` treat symlinks as either transparent or nonexistent: they are **followed** when copying (`copytree(symlinks=False)`), **discarded** when the target escapes the root, and **resolved-to-target** when mutating — with no `is_symlink()` call anywhere in the resolution layer, unlike `archive.py`/`store.py`, which check it consistently (`archive.py:408`, `:421`; `store.py:240`).

---

### SCOPE-1 — `sync_skill` copies symlinks as content *(High)*

**Location:** `skillsmgr/scopes.py:630`

```python
        stage = scope.base / f".{name}.skillsmgr-stage"
        backup = scope.base / f".{name}.skillsmgr-backup"
        try:
            if stage.exists():
                shutil.rmtree(stage)
            if backup.exists():
                shutil.rmtree(backup)
            shutil.copytree(src_dir, stage)      # symlinks=False (default) => follow links
```

Any skill in scope A containing a symlink pointing outside the root causes `sync_skill(name, "A", ["B"])` to walk **through** the link and write real copies of the target's bytes into scope B, where the agent loads them. No `is_symlink()` check, no containment check on the copy source, no size budget.

**Confirmed evidence:**

```text
src references: [('big.bin', 'link'), ('notes.md', 'file'), ('secret-dir', 'link')]
src size: 88
sync: {'name': 'shared-skill', 'from_scope': 'agents', 'synced': ['gemini'], 'skipped': []}
dest references: [('big.bin', 'file'), ('notes.md', 'file'), ('secret-dir', 'file')]
EXFILTRATED as a real file: True | 'SECRET-TOKEN-1234'
big.bin is a copy of an outside file: True 65536
```

An **88-byte** skill produced **65 KB** of files that lived outside the skill directory being copied into `~/.gemini/skills/shared-skill/`. A symlink loop (`loop -> <scope root>`) made `copytree` recurse 40 levels deep and then raise a multi-KB `shutil.Error`.

---

### SCOPE-2 — Escaping symlink: invisible to reads, blocks every write *(High)*

**Location:** `skillsmgr/loader.py:131-135`, `skillsmgr/scopes.py:47`

```python
        try:
            relative = child.relative_to(root)
            child = contained_path(root, *relative.parts)
        except (ValueError, OSError):
            continue
```

`~/.claude/skills/<name>` symlinked outside the root is precisely what the documented install workflow creates (`docs/03-cli-surface.md:155`: "`--copy` copies instead of symlinking"; `insights.install_argv` only appends `--copy` when explicitly requested, `insights.py:572-573`). `scan_dir` detects the escape and `continue`s, so the scope reports **empty** while every name-addressed operation raises `StoreError: path escapes managed root`. The agent itself follows the symlink and loads the skill perfectly. The tool can neither list, view, disable, edit, remove nor re-sync the skills it installed itself.

**Confirmed evidence:**

```text
on disk: [('myskill', True, PosixPath('/tmp/audit_p2_.../npm-cache/myskill'))]
list_scopes count: {'claude-code': 0}
scan_scope rows  : []
list_all rows    : []
find_duplicates  : []
get_skill  -> StoreError: path escapes managed root: /tmp/audit_p2_.../npm-cache/myskill
get_raw    -> StoreError: path escapes managed root: ...
toggle     -> StoreError: path escapes managed root: ...
remove     -> StoreError: path escapes managed root: ...
edit       -> StoreError: path escapes managed root: ...
create     -> StoreError: path escapes managed root: ...
snapshots  -> ok: []
```

Internal inconsistency worth noting: `list_snapshots_for` (which never resolves the skill path, `scopes.py:652-659`) **succeeds** where all seven siblings fail.

---

### SCOPE-3 — In-root symlink alias mutates the wrong skill *(High)*

**Location:** `skillsmgr/scopes.py:47`, `:312`, `:523-527`, `:540`, `:551-558`

`paths.safe_skill_path` → `contained_path` returns the **resolved** path, so the final component (the link name) is thrown away while still passing the NAME_RE check.

**Confirmed evidence** — `~/.claude/skills/alias -> ~/.claude/skills/real`:

```text
on disk             : ['alias', 'real']
list_scopes count   : {'claude-code': 2}
scan_scope rows     : [('real', '.claude/skills/real', ['duplicated']), ('real', '.claude/skills/real', ['duplicated'])]
list_all rows       : [('claude-code', 'real')]
find_duplicates     : []
tokens per scope    : {'claude-code': 26}
get_skill name asked : alias
get_skill name got   : real | path: .claude/skills/real
toggle('alias', off) : {'name': 'alias', 'disabled': True, 'scope': 'claude-code'}
```
```text
edit via alias -> {'name': 'alias', 'changed': True, 'scope': 'claude-code'}
real body now  : 'EDITED THROUGH ALIAS\n'
remove via alias: {'name': 'alias', 'action': 'trashed', 'scope': 'claude-code',
                   'trash_path': '.../.claude/trash/claude-code__alias-...Z'}
real dir exists: False
alias is dangling symlink: True | .exists() -> False
scan_scope now : []
```

`remove_skill("claude-code","alias")` moves **`real/`** to trash under the name `claude-code__alias-…`, leaving the alias dangling and the real skill gone; `edit` rewrites `real/SKILL.md` and snapshots it under the id `alias`; the single physical skill is reported twice as `duplicated` and double-counted in token totals.

---

### SCOPE-4 — One unreadable file aborts every scope view *(Medium)*

**Location:** `skillsmgr/loader.py:69-73`, `:28`; `skillsmgr/scopes.py:138`, `:200`, `:217`

```python
    if (skill_dir / "SKILL.md").is_file():          # loader.py:69  -> stat() raises PermissionError
```

`load_skill` catches only `SkillNotFound`; `scan_dir`'s handler (`loader.py:136-142`) likewise. So one unreadable document makes `scan_scope`, `list_scopes`, `list_all`, `find_duplicates`, `search_all`, `get_skill`, `get_raw` **and** `effective.explain` all fail. This contradicts the documented issue-#13 policy at `loader.py:115-118` ("A directory whose document is unreadable is *kept* and marked ``malformed``"), implemented only for *decode* errors.

**Confirmed evidence:**

```text
scan_scope           -> builtins.PermissionError: [Errno 13] Permission denied: '.../.agents/skills/locked/SKILL.md'
list_scopes          -> builtins.PermissionError: ...
list_all             -> builtins.PermissionError: ...
find_duplicates      -> builtins.PermissionError: ...
get_skill(healthy)   -> healthy
explain(codex)       -> builtins.PermissionError: ...
```
```text
/api/scopes                      -> (500, '{"error": "internal error"}')
/api/skills?scope=all            -> (500, '{"error": "internal error"}')
/api/tokens?scope=agents         -> (500, '{"error": "internal error"}')
```

---

### SCOPE-5 — Resolved path vs unresolved root makes nested skills unreachable *(Medium)*

**Location:** `skillsmgr/scopes.py:53-55`

```python
        for record in scan_dir(scope.base, recursive=True):
            if record.get("name") == name and record.get("path"):
                return paths.contained_path(scope.base, Path(record["path"]).relative_to(scope.base))
```

`record["path"]` is produced by `contained_path` ⇒ **resolved** (`loader.py:133`), while `scope.base` is the raw `Path.home()/.cursor/skills` string, so `Path.relative_to` raises `ValueError`, converted by the blanket handler into a **misleading** `StoreError`. Any symlink in the scope-root path triggers it — the macOS `/tmp → /private/tmp` shape, a dotfiles-managed `~`, a `~/work/current → …` link. Flat skills are unaffected because `direct.is_dir()` short-circuits.

**Confirmed evidence:**

```text
HOME            : /tmp/audit_p3_.../linkhome -> /tmp/audit_p3_.../realhome
scope base      : /tmp/audit_p3_.../linkhome/.cursor/skills
scan_scope rows : [('nested-skill', '/tmp/audit_p3_.../realhome/.cursor/skills/category/nested-skill'), ...]
get_skill(top)  : /tmp/audit_p3_.../realhome/.cursor/skills/top-skill
get_skill    nested-skill -> StoreError: '/tmp/.../realhome/.../category/nested-skill' is not in the subpath of '/tmp/.../linkhome/.cursor/skills'
get_raw      nested-skill -> StoreError: (same)
toggle_skill nested-skill -> StoreError: (same)
remove_skill nested-skill -> StoreError: (same)
```

---

### SCOPE-6 / SCOPE-7 — `explain()` precedence reporting defects *(Medium)*

**SCOPE-6** — `skillsmgr/effective.py:472-482` (`_overall`), used at `:624-625`:

```python
def _overall(policy: str, skills: dict[str, dict]) -> str:
    if not skills:
        return "no-instances"
    if policy != "ordered":
        return POLICY_OUTCOMES[policy]
    resolutions = {entry["resolution"] for entry in skills.values()}
    if resolutions == {"ambiguous"}:
        return "ambiguous"
    if "ambiguous" in resolutions:
        return "partially-ambiguous"
    return POLICY_OUTCOMES[policy]          # "resolved", even if every entry is no-instances
```

**Confirmed evidence:**

```text
[A] only a DISABLED copy exists
  top-level resolution : resolved | skill_count: 1
  skill resolution     : no-instances | winner: None
[B] only a NESTED (both-load) claude copy exists
  top-level resolution : resolved
  skill resolution     : no-instances | winner: None
  also_loads           : ['.../project/apps/web/.claude/skills/review']
  reason               : no loadable instance of 'review' in any documented root
[C] one loadable skill + one disabled-only skill
  top-level resolution : resolved
  per-skill            : {'deploy': 'resolved', 'review': 'no-instances'}
```

Case **B** is a self-contradiction: the reason says no loadable instance exists while `also_loads` lists that very loadable instance (nested `.claude/skills` is documented as *loading*, `docs/12` lines 26/81).

**SCOPE-7** — `skillsmgr/effective.py:275-288`, `:349-390`, `:258-272`: no use of `root_discovery.unique_physical_scopes`/`resolved_root` anywhere in the module, so one physical file appears as two candidates.

**Confirmed evidence:**

```text
[a] gemini workspace tier: .gemini/skills -> .agents/skills (one physical file)
  resolution: ambiguous | candidates: ['.../project/.gemini/skills/deploy', '.../project/.agents/skills/deploy']
  reason    : tier 'workspace' holds 2 copies of 'deploy' and no order between its roots is recorded
[b] claude-code: project/.claude/skills -> ~/.claude/skills
  winner_tier: personal | winner: .../home/.claude/skills/deploy
  shadowed   : [('project', '.../project2/.claude/skills/deploy')]
  same inode : True
[c] commandcode: ~/.commandcode/skills -> ~/.agents/skills
  winner_tier: user-commandcode | winner: .../home/.commandcode/skills/review
  shadowed   : [('user-agents', '.../home/.agents/skills/review')]
```

Case **b** reports a skill as shadowed by **itself**. This contradicts ADR-002 invariant 1 ("aliases and symlinks do not create a second root for aggregate counts…"), which `_unique_physical_scopes` implements for the facade.

---

### SCOPE-8 — `sync_skill` failure handling *(Medium)*

**Location:** `skillsmgr/scopes.py:636-642`, `:585`

```python
        except OSError:
            ...
            raise                     # raw OSError/shutil.Error escapes the scope layer
```
```python
            to_scopes = [d["id"] for d in list_scopes() if d["id"] != "global" and d["writable"] and d["exists"]]
```

`writable` is the *declared* `Scope` field (always `True`, `scopes.py:100-108`); the computed `availability` ("read-only", `root_discovery.py:33`) is exposed in the same descriptor but ignored. Multi-target sync is not atomic and discards the `synced` list on failure.

**Confirmed evidence:**

```text
  raised builtins.PermissionError: [Errno 13] Permission denied: '.../home/.gemini/skills/.deploy.skillsmgr-stage'
codex got the skill     : True          # first target already committed
gemini got the skill    : False
```
```text
[sync to codex+gemini, gemini read-only]
  (500, '{"error": "internal error"}')
  codex skill written before the failure: True
[sync with a file squatting the stage path]
  (500, '{"error": "internal error"}')
```

Rollback *within* one target is correct (a failed force-sync restores the destination's original content), so the gap is specifically cross-target reporting and error translation.

---

### SCOPE-9 / SCOPE-10 — "global" has two identities; module-global store cross-talk *(Medium)*

**SCOPE-9** — `scopes.py:101` derives the global root from the environment while `:164-166` derives it from the injected `Store`.

```python
        Scope("global", "Global", paths.skills_dir(), "global", True, consumer="skills-manager"),
```
```python
    snapshot_data_dir = _global_store().data_dir        # scopes.py:593
```

**Confirmed evidence:**

```text
env global root  : /tmp/audit_p9_.../data/skills-manager/skills
store.data_dir   : /tmp/audit_p9_.../other-data/skills-manager
sync result      : {'name': 'deploy', 'from_scope': 'agents', 'synced': ['global'], 'skipped': []}
landed in env root   : True
landed in store dir  : False
store.list()         : []
scan_scope('global') : []
list_scopes global   : {'global': ('/tmp/.../data/skills-manager/skills', 1, True)}
list_all             : [('agents', 'deploy')]
get_skill(global)    : SkillNotFound skill 'deploy' is not installed
```

Five views disagree about the same on-disk state, and `sync` reports success while creating a destination that is never indexed.

**SCOPE-10** — `skillsmgr/scopes.py:31-41` + `skillsmgr/webapp.py:949-953`: the last `set_global_store` wins for every path that goes through `_global_store()`. The existing contract test only covers `/api/search` + `/api/skills?q=…`, which pass `store=self.store` explicitly; the no-query All view, `/api/stats`, `/api/tokens`, `/api/scopes` and `list_snapshots_for` do not.

**Confirmed evidence:**

```text
  server_a /api/skills?scope=global -> [{"name": "a-only", ... "description": "in data-a" ...}]
  server_a /api/skills?scope=all    -> [{"name": "b-only", ... "description": "in data-b" ...}]
  server_b /api/skills?scope=global -> [{"name": "b-only", ...}]
```
```text
edit an AGENT-scope skill while _GLOBAL_STORE points at data-b:
   {'name': 'cursorless', 'changed': True, 'scope': 'agents'}
  snapshots under data-a: []
  snapshots under data-b: ['snapshots/agents/cursorless/2026-09-11_10-10-23Z.md']
```

Server A **mutates server B's data dir**. There is no reset (`set_global_store(None)`) anywhere in product code.

---

### SCOPE-11 — `list_all()` erases the duplicate signal *(Medium)*

**Location:** `skillsmgr/scopes.py:220-233`

```python
    seen: set[tuple[str, str]] = set()
    for desc in list_scopes(include_missing=include_missing):
        sid = desc["id"]
        for rec in scan_scope(sid):
            key = (sid, rec["name"])
            if key in seen:
                continue
```

**Confirmed evidence** — a monorepo with `apps/web/docs` and `apps/api/docs`, the documented recursive-nested shape:

```text
on disk            : ['apps/api/docs/SKILL.md', 'apps/web/docs/SKILL.md', 'apps/web/web-only/SKILL.md']
scan_scope(cursor) : [('docs', 'apps/api/docs', ['duplicated', 'divergent'], 'api docs skill'),
                      ('docs', 'apps/web/docs', ['duplicated', 'divergent'], 'web docs skill'),
                      ('web-only', 'apps/web/web-only', ['active'], 'unique skill')]
list_all           : [('cursor', 'docs', ['active'], 'api docs skill'), ('cursor', 'web-only', ['active'], 'unique skill')]
find_duplicates    : []
list_scopes counts : {'cursor': 3}
  -> /api/stats all_total (webapp sum of counts): 3
  -> /api/skills?scope=all length (list_all)    : 2
```

The second copy is dropped, the survivor is re-annotated as `['active']`, and `find_duplicates()` reports nothing — so the Web UI's All-scopes table hides a real duplicate with divergent content.

---

### SCOPE-12 to SCOPE-18 — remaining resolution defects *(Low)*

* **SCOPE-12** (`scopes.py:466-471`, writing at `:504-513`): on a `FrontmatterError` the handler sets `data, orig_body = {}, text`, so `edit_skill` writes `dump_frontmatter({}) + whole_original_text` — **two** frontmatter blocks, with the stale one inside the body — and the outer document now parses, so the `malformed` flag *clears* and the corruption stops being surfaced as drift.
  ```text
  before: '---\nname: [broken\ndescription: still readable\n---\nORIGINAL BODY\n'
  load_skill malformed: True
  after : '---\ndescription: A new description\n---\n---\nname: [broken\ndescription: still readable\n---\nORIGINAL BODY\n'
  frontmatter blocks now: 4
  reload: malformed=False
  ```
* **SCOPE-13** (`scopes.py:551-558`): `src.rename(dst)` on a mixed state destroys a document with no snapshot (`toggle` never calls `write_snapshot`).
  ```text
  before: ['SKILL.md', 'SKILL.md.disabled']
  toggle(enable=False) -> {'name': 'mixed', 'disabled': True, 'scope': 'agents'}
  after : ['SKILL.md.disabled'] | content: '---\nname: mixed\ndescription: enabled doc'
  ```
* **SCOPE-14** (`scopes.py:200-217` vs the NAME_RE check on every write): `Upper-Case`, `with_underscore`, and the NFC/NFD pair `café`/`cafe\u0301` are **listed** by `scan_scope`/`list_all` but every name-addressed operation raises `StoreError: invalid skill name …` — the user sees rows that error when clicked and can never clean them up through the tool. (No aliasing bug exists: the two café directories are listed separately on Linux.)
* **SCOPE-15** (`scopes.py:164-196` via `store.py:665`): one index row whose name fails NAME_RE makes `scan_scope("global")`, `list_all()` and `search_all()` fail together while `list_scopes()` (filesystem-only) still renders — so the UI shows scope counts next to an erroring All list.
* **SCOPE-16** (`effective.py:507-534`, budget only enforced in `_build_tier` `:367-374`): a large monorepo yields 640 instances despite `MAX_INSTANCES = 500`, with **no** truncation warning, contradicting the module docstring at `effective.py:35-37`.
* **SCOPE-17** (`scopes.py:98`, `paths.py:21-30`, `root_discovery.py:9-11`): `HOME=""` makes `Path.home()` return `/`, so the agent scopes become `/.claude/skills`, `/.codex/skills`, … — both read **and write** targets at the filesystem root. `HOME` unset silently falls back to the passwd entry, so a "hermetic" environment reads the real `~/.claude`. Relative `SKILLS_MANAGER_DATA`/`XDG_DATA_HOME` follow the CWD.
  ```text
  Path.home() with HOME=''    : '/'
  with HOME='' the agent scopes are:
     [('global', '/tmp/.../data/skills-manager/skills'), ('claude-code', '/.claude/skills'), ('codex', '/.codex/skills'), ('cursor', '/.cursor/skills')]
    create_skill('claude-code','demo') -> StoreError could not create skill 'demo' safely: [Errno 13] Permission denied: '/.claude'
  ```
* **SCOPE-18** (`scopes.py:47-49`): with the layout `~/.cursor/skills/deploy/deploy/SKILL.md`, `scan_scope` lists the skill at `deploy/deploy` while `get_skill` returns the *grouping* directory `…/deploy` and `load_skill` then reports `SkillNotFound` — the two views contradict each other.

---

## 4d. Frontmatter / validator findings — detail

Findings from the dedicated `frontmatter.py` (hand-written YAML-subset parser/dumper, no PyYAML — a locked constraint, so "use PyYAML" is not an available fix) and `validator.py` / `templates.py` workstream. All probes ran from `/tmp`; `git status --porcelain` is unchanged.

**Scale of the round-trip problem — measured, not estimated.** A fuzz campaign over **25,000 generated documents** (20,000 value-side + 5,000 hostile-key, plus ~3,000 exploratory, ~250 hand-written, and an 87-scalar × 5-placement sweep) found **4,023 round-trip failures = 16.1%**:

| Campaign | Documents | Failures | Rate |
|---|---|---|---|
| Value-side | 20,000 | 2,397 | 12.0% |
| Hostile-key | 5,000 | 1,626 | 32.5% |
| **Combined** | **25,000** | **4,023** | **16.1%** |

Idempotence held: all 20,977 documents that round-tripped once also satisfied `dump(parse(dump(parse(x)))) == dump(parse(x))`, so the defect is a *first-pass* fidelity problem rather than a divergent fixed point.

Attribution across the value campaign: whitespace-only line 636, `---` line inside a value 580, CR in value 575, common leading indentation 238, tab-before-`#` 162, newlines-only value 128, other scalar 78. (Each failing document is attributed to its highest-priority class, so these are upper bounds; every class below also has a hand-written minimal probe.)

---

### FM-1 — Indented `---` inside frontmatter truncates the document *(Critical)*

**Location:** `skillsmgr/frontmatter.py:31` and `:70-73`

```python
_DOC_MARKER = re.compile(r"^---(?:\s+#.*)?$")
...
    for i in range(1, len(lines)):
        if _DOC_MARKER.match(lines[i].strip()):      # <-- .strip() accepts "  ---"
            end = i
            break
```

A YAML document marker must start at column 0 and is never recognised inside a block scalar. Because the marker is tested against `lines[i].strip()`, **any indented `---` line ends the frontmatter block early** — including the perfectly ordinary case of a description that continues onto a line containing a horizontal rule.

**Confirmed evidence** — I reproduced and extended this directly. Minimal counterexample:

```text
in        : {'description': 'Use this skill when a doc has\n---\na rule in it.'}
dumped    : '---\ndescription: |-\n  Use this skill when a doc has\n  ---\n  a rule in it.\n---\n'
re-parsed : {'description': 'Use this skill when a doc has'}
body      : '  a rule in it.\n---\n'
ROUND TRIP OK : False
LOST TEXT     : '\n---\na rule in it.'
```

Hand-written variants are affected too — the parser does not need the dumper to hit this:

```text
input : '---\nk: |\n  a\n  ---\n  b\n---\nbody\n'
parsed: ({'k': 'a\n'}, '  b\n---\nbody\n')
```

**It persists through real edits, and the tool cannot see it.** Driving the actual `Store.edit()`:

```text
edit -> {'name': 'docs-skill', 'changed': True}
ON DISK:
'---\nname: docs-skill\ndescription: |-\n  Use this skill when a doc has\n  ---\n  a rule in it.\n---\n# b\n'
description now: 'Use this skill when a doc has'
body now       : '  a rule in it.\n---\n# b\n'
*** ORIGINAL TEXT GONE: True
```

The truncated description **plus** the leaked tail lines are written to disk, so the corruption is now the persisted state. The workstream additionally confirmed that `python3 -m skillsmgr validate --path <that skill>` prints `ok` — the component that owns the file reports it as healthy. Because `store.py:835`, `store.py:1008` and `scopes.py:422`/`:511` all funnel through this dumper/parser pair, **every write path in the product** can persist the truncation.

**Suggested fix (not applied).** Match the marker at column 0 without `.strip()` — e.g. `re.fullmatch(r"---(\s+#.*)?", lines[i])` after removing only a trailing `\r`; ideally also track block-scalar state so a marker can never terminate inside one.

---

### FM-2 — A sequence root makes `parse_frontmatter` return a `list` *(High)*

**Location:** `skillsmgr/frontmatter.py:153-160`; declared return type `tuple[dict, str]` at `:53`

```python
    def parse_document(self) -> dict:
        ...
        if self._is_list_marker(stripped):
            items, _ = self._parse_block_list(idx, self._indent(self.lines[idx]))
            return items          # <-- a list, not a dict
```

**Confirmed evidence** — I verified this directly:

```text
parse_frontmatter("---\n- a\n- b\n---\nbody\n")  ->  (['a', 'b'], 'body\n')
```

Consumers then do `data.get(...)`: `validator.py:302`, `loader.py:83`. The workstream confirmed the downstream blast radius end-to-end:

```text
validate_text(seq_text, name='a')  *** RAW AttributeError ... validator.py, line 302
loader.load_skill(dir)             *** RAW AttributeError ... loader.py, line 83
loader.scan_dir(root)              *** RAW AttributeError ... loader.py, line 83
validate_skill('seq', dir)         *** RAW AttributeError ... validator.py, line 302
store.doctor() / store.resync() / store.db_rebuild()   *** RAW AttributeError
$ SKILLS_MANAGER_DATA=<tmp> python3 -m skillsmgr doctor
error: unexpected error: 'list' object has no attribute 'get'
$ python3 -m skillsmgr list --scope agents
error: unexpected error: 'list' object has no attribute 'get'
```

`loader.scan_dir` catches only `SkillNotFound` (`loader.py:141`), so **one malformed file makes the entire data dir or scope unmanageable** — `doctor`, `resync`, `db_rebuild`, `validate` and `list` all abort. Over REST this is `500 internal error` (`webapp.py:268-278`).

**Suggested fix (not applied).** Raise `FrontmatterError("frontmatter must be a mapping, found a sequence")` when the document root is a sequence, and add defensive `isinstance(data, dict)` guards at the consumer boundaries.

---

### FM-3 — Out-of-range `\U` escapes raise raw `ValueError`/`OverflowError` *(High)*

**Location:** `skillsmgr/frontmatter.py:601-602`

```python
                    if len(digits) == width and _is_hex(digits):
                        result.append(chr(int(digits, 16)))   # no code-point range check
```

**Confirmed evidence** — I verified directly:

```text
---\ndescription: "x \U00110000 y"\n---\nb\n  -> RAW ValueError: chr() arg not in range(0x110000)
---\ndescription: "x \UFFFFFFFF y"\n---\nb\n  -> RAW OverflowError: Python int too large to convert to C int
```

Neither is a `FrontmatterError`, so both escape `validator.py:139-144` and `loader.py:79-83` entirely. The workstream confirmed `validate_text`, `loader.scan_dir`, `store.doctor()`, `store.resync()`, `store.db_rebuild()` and `validate_skill()` all abort with the raw exception — the same single-file-kills-everything shape as FM-2.

**Suggested fix (not applied).** Bound-check before `chr()`: `cp = int(digits, 16); if cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF: raise FrontmatterError(...)`.

---

### FM-4 — Lone surrogates pass validation, then every write fails *(Medium)*

**Location:** `skillsmgr/frontmatter.py:594-604` (same `chr()` call as FM-3)

**Confirmed evidence:**

```text
  parsed  : {'name': 'n', 'description': 'a\ud800b'}
  dumped  : '---\nname: n\ndescription: a\ud800b\n---\n'
  dumped.encode('utf-8')   *** RAW UnicodeEncodeError ... surrogates not allowed
  validate_text (name check passes)  OK -> []          <-- validation reports NO error
  store.edit(category=tools) *** RAW UnicodeEncodeError (raised at atomic_io.py, line 39)
```

The parser accepts an unencodable `str`, validation reports it clean, and the failure surfaces much later as a raw `UnicodeEncodeError` from the atomic-write layer. The same range check as FM-3 fixes it.

---

### FM-5 to FM-10, FM-12 — Silent value corruption on dump→parse *(Medium)*

Each has a hand-written minimal probe (not merely a fuzz hit). All are `EQUAL: False` on a `dump → parse` cycle of a value the dumper itself produced or accepted.

| ID | Counterexample | Dumped | Re-parsed | Note |
|---|---|---|---|---|
| **FM-5** | `{"description": "  code line 1\n  code line 2"}` | `'---\ndescription: \|-\n    code line 1\n    code line 2\n---\n'` | `'code line 1\ncode line 2'` | min-indent heuristic (`:335-346`) + fixed pad (`:968-983`) eat the common indentation |
| **FM-6** | `{"description": "a\n  \nb"}` | `'---\ndescription: \|-\n  a\n    \n  b\n---\n'` | `'a\n\nb'` | whitespace-only line treated as blank (`_is_blank` `:129-131`). Worst case `{"k": " \n "}` → `{'k': ''}` — the whole value is lost |
| **FM-7** | `{"description": "line1\r\nline2"}` | `'---\ndescription: \|-\n  line1\r\n  line2\n---\n'` | `'line1\nline2'` | `:78` `rstrip("\r")` cannot distinguish a terminator CR from CR content |
| **FM-8** | `{"description": "a\t#b"}` | `'---\ndescription: a\t#b\n---\n'` | `'a'` | parser accepts TAB before `#` (`:699`), dumper only checks `" #"` (`:995`) → silent truncation |
| **FM-9** | `{"a\nb": "v"}`, and reachable from real content: `metadata: {"a\nb": c}` | `'---\na\nb: v\n---\n'` | `FrontmatterError` | the dumper emits a document **its own parser rejects** (`:1010-1018`); `_clean_key` already understands double-quoted escapes, so quoting the key would round-trip. Also `{1:'x','1':'y'}` → `duplicate frontmatter key` |
| **FM-10** | `{"description": "\n"}` | `'---\ndescription: \|\n  \n---\n'` | `''` | the falsy `""` never regains its newline (`:353-360`). `"\n\n"` happens to round-trip |
| **FM-12** | hand-written `"---\nk: \|\n  a\n\n\nz: 1\n---\n"` and `\|+` variants | — | — | clip keeps too many / keep drops one vs PyYAML 6.0.1 used purely as an optional reference: `'a\n\n'` vs `'a\n'`; `'a\n'` vs `'a\n\n'` |

**The FM-8 mechanism is the most insidious**: it needs no unusual input. A description containing a literal tab immediately followed by `#` is silently truncated to the text before the tab, and nothing in the toolchain reports it.

---

### FM-11, FM-15 to FM-21 — Validator and name-validation defects *(Low)*

* **FM-11** (`validator.py:397-403`): the comparison is against the **caller's** `name` argument, never `skill_dir.name`. `validate_skill('other-name', <dir 'dir-name'>)` → `errors == []`, while `validate_skill('dir-name', <same dir>)` correctly errors. Any caller whose `name` is not the directory basename gets no mismatch signal.
  ```text
  validate_skill('other-name', <dir 'dir-name'>).errors: []
  validate_skill('dir-name',   <dir 'dir-name'>).errors: ["frontmatter name 'other-name' does not match directory name 'dir-name'"]
  ```
* **FM-15** (`validator.py:51-52`, `:71-85`): `con`, `nul`, `aux`, `prn`, `com1`…`lpt1` all **pass** `validate_skill_name`, and `store.create` then `mkdir`s that name. Everything else tested is correctly rejected (`.`, `..`, `a\b`, `a:b`, `a/b`, `café`, `My-Skill`, 65 chars, ZWSP, NBSP). Windows-side failure is *Likely* (not testable on this Linux host) — but `validate_skill_name` is documented as the single gate before a name becomes a path, so the gate should be host-independent.
* **FM-16** (`validator.py:339`, `:281`): a NUL byte in a link target or layout mention (valid UTF-8, so the file decodes cleanly) → raw `ValueError: embedded null byte` from `Path.resolve()`.
* **FM-17** (`validator.py:148-164`): `validate_text(text)` without `name=` never applies `NAME_RE` — `name: ../evil`, `Foo Bar`, `with_underscore`, `UPPER` all produce zero errors. `smoke_store.py:128-135` calls it that way.
* **FM-18** (`validator.py:62-64`): `_USE_CONTEXT_RE` requires a bare `\buse\b`, so the most natural phrasing — "This skill **should be used when** reviewing pull requests." — produces a false "no use-context" warning. Same for "It is used when …".
* **FM-19** (`validator.py:323-360`, `:61`, `:277-291`): seven spurious warnings for a target that exists when the reference carries `#fragment`, `%20`, `?query`, or trailing sentence punctuation (`scripts/run.py.`).
* **FM-20** (`frontmatter.py:758-776`): no depth guard on the dump recursion (the flow-list path *does* cap via `_check_depth`/`MAX_NESTING_DEPTH = 64`) → raw `RecursionError` at 2000 nesting levels. Only reachable programmatically, since parsed documents are capped at depth 64.
* **FM-21** (`templates.py:23`, `:49-55`): `TEMPLATE_NAME_RE` duplicates the skill name rule without `MAX_NAME` or the reserved-name check — `create_template(dir, "a"*300)` → raw `OSError: [Errno 36] File name too long`, and a 200-char name **succeeds silently**, so the drift is invisible until the filesystem refuses.
* **FM-13 / FM-14** (block scalars): folded `>` joins every non-empty line with a space, so an intentionally more-indented line loses its break (`'a   indented b'` vs the correct `'a\n  indented\nb'`); explicit indentation indicators are treated as absolute rather than parent-relative, so `outer:\n  k: |2\n    a` fabricates two leading spaces. Plain folding and top-level `|2` are correct.

**Suggested fixes for this group (not applied):** compare against `skill_dir.resolve().name`; reject reserved device names in `validate_skill_name`; wrap both `resolve()` calls in `try/except (ValueError, OSError)`; apply `NAME_RE` whenever a frontmatter `name` is a non-empty string, independent of the argument; allow `\buse[sd]?\b` in the use-context regex; strip `#fragment`/`?query` and `unquote()` before the existence check; thread a `depth` argument through the dump recursion; share `validate_skill_name` in `templates.template_path`.

---

## 4e. CLI / registry / eval-harness findings — detail

Findings from the `cli_handlers.py` / `cli_parser.py` / `cli_output.py` / `colors.py` / `insights.py` / `evals.py` workstream. Probes under `/tmp/probe/`, every run with an isolated `SKILLS_MANAGER_DATA` and `HOME`.

### CLI-1 — Regex assertion in `evals/evals.json` causes catastrophic backtracking *(Medium)*

**Location:** `skillsmgr/evals.py:299-305` (evaluation), `:149-159` (the only guard)

```python
299:    if kind == "regex":
300:        try:
301:            match = re.search(needle, output[:MAX_REGEX_INPUT])
302:        except re.error as exc:  # pragma: no cover - patterns are pre-validated
303:            return {"type": kind, "passed": False, "detail": f"invalid pattern: {exc}"}
```
```text
153:            if len(pattern) > MAX_PATTERN_LENGTH:
154:                raise ValueError(f"regex assertion pattern exceeds {MAX_PATTERN_LENGTH} characters")
155:            try:
156:                re.compile(pattern)
```

`MAX_PATTERN_LENGTH = 200` and `MAX_REGEX_INPUT = 50_000`. The guard checks only *length* and *compilability* — there is **no** `signal.alarm`, no timeout, no `regex` module, and no nested-quantifier rejection anywhere in `evals.py` (verified: grep for `signal\.|alarm|timeout` in that file returns nothing, and I re-confirmed the constants at lines 47-48).

**Confirmed evidence — I reproduced the hang myself:**

```text
$ grep -n "MAX_PATTERN_LENGTH\|MAX_REGEX_INPUT" skillsmgr/evals.py
47:MAX_PATTERN_LENGTH = 200
48:MAX_REGEX_INPUT = 50_000
153:            if len(pattern) > MAX_PATTERN_LENGTH:
154:                raise ValueError(f"regex assertion pattern exceeds {MAX_PATTERN_LENGTH} characters")
301:            match = re.search(needle, output[:MAX_REGEX_INPUT])

$ grep -rn "signal\.\|alarm\|timeout" skillsmgr/evals.py
NO timeout/signal guard in evals.py

$ timeout 12 python3 -c "…grade a 40-char 'a'-run against '(a+)+\$'…"
EXIT=124 (124 = timed out = ReDoS confirmed)
```

The workstream established the full blast radius:

```text
CLI:  exit=124 after 11s   (a 30-char input hangs too — MAX_REGEX_INPUT truncation is not the issue)
REST: POST /api/validate -> client TimeoutError after 5.1s; server process still alive at 90.4% CPU
      second request -> ConnectionResetError
GIL:  with client and server in ONE process, the client never even reached its own
      socket timeout — `re` holds the GIL, so every thread is frozen and the process
      must be SIGKILLed
```

**Why this is Medium rather than High.** It requires the user to run a validate with `--evals-run` on a skill whose `evals.json` carries a hostile pattern — but that is exactly the workflow for third-party skills, and `evals.json` ships *inside* the skill bundle, which is the untrusted input this product's whole design centres on. The GIL-wide freeze is the sharp edge: unlike SEC-2 (one slow request in its own thread), this stops the entire server process and cannot be interrupted.

**Suggested fix (not applied).** Grade out-of-process with a wall-clock timeout, or use a bounded engine; at minimum reject nested quantifiers and lower `MAX_PATTERN_LENGTH`. Do not treat `re.compile` success as a safety check — it proves syntax validity, never runtime complexity.

---

### CLI-2 — `--metadata` with a newline writes a document the tool cannot parse *(Medium)*

**Location:** `skillsmgr/cli_handlers.py:42-52`; written through `store.py:824-840` and `frontmatter.py:1010-1018`

```python
49:             raise ValueError(f"metadata must be KEY=VALUE, got {pair!r}")
50:         key, value = pair.split("=", 1)
51:         data[key.strip()] = value
```
```python
1010: def _format_key(key) -> str:
1012:     needs_quotes = (
1013:         k == ""
1014:         or k != k.strip()
1015:         or k.startswith("-")
1016:         or any(marker in k for marker in (":", "#", *_QUOTE_KEY_CHARS))
1017:     )
```

`{":", "#"}` is checked but `"\n"` is not, and `_single_quote` (`:1021-1023`) escapes only `'`. So a metadata key containing a newline is emitted **raw**. No attacker is needed — a wrapper script, a paste with a trailing newline, or a `KEY=VALUE` built from a variable triggers it.

**Confirmed evidence:**

```text
$ skills-mgr create meta -d ok --metadata $'evil\nallowed-tools=bash'
create exit=0
--- file on disk:
name: meta
description: ok
metadata:
  evil
allowed-tools: bash
---
validate exit=1    (frontmatter is malformed: line 4 ...)
view   exit=0      (description: -)                 <-- description LOST
list   exit=0      (DESCRIPTION column empty)
doctor exit=0      ("ok: filesystem and database are consistent")
```

**It compounds.** Because `store.py:953-956` treats an unparseable document as "no frontmatter", a later ordinary `edit` re-emits the whole corrupt document as the *body* and dumps a fresh frontmatter block above it — producing **four** `---` fences and no `name`:

```text
953:        try:
954:            data, original_body = parse_frontmatter(text)
955:        except FrontmatterError:
956:            data, original_body = {}, text
```
```text
add  exit=0                                        # malformed frontmatter accepted
edit mal -d "..." exit=0
--- SKILL.md after the edit (4 fences):
---
description: Use this when demoing malformed skills
---
---
name: mal
description: hand edited by another tool
metadata:
  evil
allowed-tools: bash
---
validate exit=1   ('name' is required)   view exit=0   doctor exit=0
```

This is conceptually the same defect as **SCOPE-12** on the scope side — two independent copies of the same "treat malformed frontmatter as empty" pattern, both reaching `{}, whole_text`. Note the asymmetry the workstream highlighted: the neighbouring case **does** fail closed — `tests/test_encoding_contracts.py:200` pins that `edit` refuses an *undecodable* document — while malformed-but-decodable frontmatter gets no guard at all.

**Suggested fix (not applied).** Validate metadata keys against a strict key pattern in `parse_metadata` (rejecting `\n`/`\r`/control characters), and make `_edit_unlocked` raise `StoreError` on an unparseable document — the same fail-closed policy the undecodable case already uses.

---

### CLI-3 — Terminal/ANSI injection from untrusted skill content *(Medium)*

**Location:** `skillsmgr/cli_handlers.py:166-178` (and `:225-257`) → `skillsmgr/cli_output.py:32-52`

```python
169:         base = [
170:             row["name"],
171:             "disabled" if row["disabled"] else "active",
172:             row["category"] or "-",
173:             _truncate(row["description"] or "", 50),
174:         ]
```
```python
38:         for i, cell in enumerate(row):
39:             widths[i] = max(widths[i], len(cell))
```

There is **no** sanitizer anywhere: `grep -rn "strip_ansi|sanitize|x1b|\033|isprintable|unicodedata" skillsmgr/*.py` matches only `colors.py:33` (its own SGR emission) and `frontmatter.py:571` (YAML `\e` decoding). Disabling colour does **not** sanitize — the raw bytes pass straight through when piped.

**Confirmed evidence** — a hand-crafted archive with a *correct* `content_hash` (which the attacker can trivially recompute), then `import`:

```text
$ skills-mgr import hostile.tar.gz --json      exit: 0   ("imported": ["evil"])
$ skills-mgr list
'NAME   STATUS   CATEGORY        DESCRIPTION\nevil   active   uncategorized   \x1b[2K\x1b[32mTRUSTED  active  verified-by-admin\x1b[0m\n'
```
```text
$ skills-mgr list        # skill written by another tool into an agent scope
SCOPE         NAME    STATUS   CATEGORY        DESCRIPTION
claude-code   rogue   active   uncategorized   ^[[2K^[[33mWARNING: all skills are up to date^[[0m
```

The escape bytes also poison the width computation (`len(cell)`), so a payload can erase and re-align adjacent columns — display spoofing that can hide a skill row or fabricate a "verified" line. Names themselves are safe: `NAME_RE` rejects escapes (independently confirmed in §2.5).

**Suggested fix (not applied).** Strip/replace C0/C1 and `ESC` in `truncate`/`render_table` and in the `view`/`doctor`/`search` output paths.

---

### CLI-4 to CLI-11, EVAL-2, INS-1, INS-2 — remaining CLI findings *(Low)*

* **CLI-4** (`cli_handlers.py:410-419`): `--workspace` is returned unchecked. The guarded routes (`workspace_for_dir`, `workspace_for`, `contained_path`) are correct, but the override bypasses them, so `validate demo --evals-run runs.json --workspace "$DATA/skills-manager/skills/demo"` writes the iteration tree **inside the managed `skills/` root**, and `export` then ships it:
  ```text
  $ tar tzf out.tar.gz
  skills/demo/SKILL.md
  skills/demo/iteration-1/benchmark.json
  skills/demo/iteration-1/eval-p/with_skill/outputs/output.txt
  ...
  ```
  ADR-003 §3 claims run data never reaches the archive. `doctor`/`validate` stay "ok", so the pollution is silent.
* **CLI-5** (`cli_handlers.py:593-608`): `store.doctor()` takes no scope argument, yet `docs/03-cli-surface.md:114` documents "With a scope, checks that scope's dir". A broken document in an agent scope is reported `ok` with exit 0, and `doctor --scope bogus` also succeeds — while every other scope-aware command rejects an unknown scope with exit 1.
* **CLI-6** (`cli_handlers.py:238-244`): `--raw` is tested before `--json` and the parser has no mutually exclusive group despite the docs writing `[--raw|--json]`, so `view demo --raw --json` prints raw Markdown with exit 0. In a 48-invocation `--json` sweep this was the **only** exit-0 non-JSON output.
* **CLI-7** (`cli_handlers.py:1049-1054`, `:1059`): `--list-only` returns before execution and the real path hard-codes `list_only=False`, so the documented "list available skills" runs nothing. The REST route builds the same argv and **does** execute it — the one genuine CLI/REST divergence found.
* **CLI-8** (`cli_handlers.py:1013-1032`, `:33`): option injection is blocked (leading `-`), but `_SAFE_SOURCE_RE` permits `.` and `/`, so `--agent ../../../../tmp/pwn`, `--agent ..`, `--agent /etc/passwd`, `--agent C:/Windows` all pass, with no length cap (a 300,000-char argv element was accepted). Argv is list-form everywhere, so this is runner-interpreted traversal rather than shell injection; REST uses the identical regex, so it is a shared gap rather than a parity gap.
* **CLI-9** (`cli_handlers.py:763-769`): `store.purge_trash()` returns `{"purged": [names]}`, so the human path interpolates a Python list: `purged ['doomed', 'doomed-two'] trashed skills`.
* **CLI-10**: silently ignored flag combinations — `validate --all demo` (NAMES ignored), `tokens demo --text "hello"` (NAME ignored), `install --dry-run --trust-confirmed` (trust flags inert). The sharpest is `validate nosuch --all`, which exits 0 with green results for *unrelated* skills.
* **CLI-11** (`evals.py:120-133`): `_case_files` rejects absolute, `..` and backslash entries but not a drive prefix, because on POSIX `Path("C:/x").parts == ("C:", "x")` so it passes; on Windows it would be absolute. Impact is bounded — entries are only existence-checked, never read — so the observable effect is a file-existence oracle.
* **EVAL-2** (`evals.py:443-474`): each *file* is written atomically, which the workstream verified positively (no torn JSON after a SIGKILL). But the iteration has no staging, no completeness marker, and no cleanup: a case with an invalid derived slug leaves a partial iteration with no `benchmark.json` (144 of 178 files after a mid-loop SIGKILL, plus one stray `.skillsmgr-tmp`), and re-recording an iteration with *fewer* runs rewrites `benchmark.json` while leaving the previous runs' outputs on disk — so the benchmark no longer describes what is present.
* **INS-1** (`insights.py:75-78`): `_SCRIPT_RE` is an unsound security-shaped heuristic — it flags `rm -rf` and `curl | sh` but **not** `curl | bash`, `wget | bash`, `base64 -d | sh`, `rm -r -f`, `rm --recursive --force`, `chmod 777`, or even `shell=True`/`eval`. It is dormant (zero product callers, verified by grep), so this is a latent trap rather than an exploitable bypass: it must never be wired up as a gate.
* **INS-2** (`insights.py:604-623`, `:637-639`): `trust_confirmed`, `may_install` and `hash_status` are self-asserted — nothing is fetched and nothing is compared, yet with `--trust-confirmed --registry-hash deadbeef` the payload reports `{"trust_confirmed": true, "may_install": true, "hash_status": "provided", "blockers": []}`. The plan **is** honest elsewhere (`description_status: not-provided`, an explicit `provenance_note`, no network module loaded — re-verified in-process and pinned by `tests/test_registry_bridge_contracts.py:184`), so the defect is narrow naming/semantics rather than a false claim of verification.
* **INFO-1** — **verified false positive.** `cli_handlers.py:289` (`cmd_open`) is Semgrep's only ERROR. Confirmed not exploitable: no shell (a metachar `EDITOR` stays an inert argv element — `EDITOR="never-exists-bin; touch /tmp/PWNED"` produced `FileNotFoundError: 'never-exists-bin;'` and no marker file); an unbalanced quote raises `ValueError` → clean `error: No closing quotation` exit 1; and the only non-env argument is an **absolute** path from `store.get(name)["path"]`, with `validate_cli_names` rejecting hostile names *before* the store is touched. A failing editor exits 1 and correctly skips `resync()`. Any attacker who controls `EDITOR` already has code execution, so there is no privilege gain.

---

## 5. Static-analysis and tooling backlog (not individually detailed)

These are real but low-value to enumerate one by one; they are recorded so the counts in §1 are traceable.

* **Type errors (28, `mypy`).** The substantive ones: `store.py:436-437` assigns a `list[tuple[ZipInfo, str]]` into a variable typed for `TarInfo` — the tar/zip extraction branches are conflated in one function and only type-checking catches it; `frontmatter.py:160` returns `list[Any]` where `dict` is declared; `frontmatter.py:653` returns `(None, None, bool)` where `tuple[str|None, str, bool]` is declared — both are places where the declared contract and the code disagree, which is where BUG-2-style defects hide.
* **Complexity (worst-first).** `_route_get` **F(95)**, `_route_post` **F(81)**, `Store._edit_unlocked` **E(37)**, `scopes.sync_skill` **E(31)**, `Store.import_` **E(33)**, `validator.validate_text` **D(29)**, `scopes.edit_skill` **D(28)**, `cli_handlers.cmd_validate` **D(28)**, `cli_handlers.cmd_tokens` **D(27)**, `effective.explain` **D(26)**, `archive.validate_manifest` **D(25)**, `frontmatter._Parser._parse_block_scalar` **D(23)**, `Store._create_unlocked` **D(24)**, `cli_handlers.cmd_view` **D(21)**. `AGENTS.md`'s own `check_complexity.py` ratchet evidently permits these.
* **Broad exception handling.** `ruff` reports 20 `BLE001` (blind `except Exception`) and 9 `S110` (`try`/`except`/`pass`) in `skillsmgr/` — see BUG-8 for the nine most consequential.
* **Subprocess.** `semgrep` ERROR `dangerous-subprocess-use-tainted-env-args` at `cli_handlers.py:289` (`shlex.split(os.environ["EDITOR"])`); `bandit` B603/B607 at `cli_handlers.py:289`, `:1064`, `webapp.py:721`, `webapp.py:970`. All are argv-list form with no `shell=True`; the `$EDITOR` value is attacker-influenced only under prior environment compromise. Reported for completeness; no parity gap between the CLI and REST install validators was found beyond the shared regex.
* **`bandit` B202** at `archive.py:271` (`tarfile.extractall(members=…)`): investigated directly — `validate_members` (`archive.py:118-137`) rejects every hostile member type *before* extraction, and `extract_members` uses `tarfile.data_filter` when available. **Not a finding**; see §2.3.
* **`bandit` B105** at `evals.py:415` is a false positive (the string `"cases whose every assertion passed / graded cases"` matched a password heuristic).

---

## 6. What was NOT covered (honest limitations)

* **No live browser exploitation of SEC-1/SEC-3.** The DNS-rebinding read path was reasoned from the `no-cors`/opaque-response behaviour plus the confirmed absence of the guard, not executed in a real browser. The `curl`-equivalent (a hostile `Host` header) was executed and is what the evidence shows.
* **Repository settings are unverifiable from source**: branch protection, required reviewers, whether the `release` environment requires approval, and the PyPI trusted-publisher binding. The workflow comments asserting them (`release.yml:13-15`) are unverified claims.
* **`check_docs.py` and `check_complexity.py` were not re-run**; nothing in this audit changed the repo, so their status is unchanged from `0b82094`.
* **Cross-platform behaviour on Windows/macOS is unverified.** FM-15's Windows-reserved-name failure in particular is *Likely*, not *Confirmed* — the validation acceptance is confirmed, the OS-level consequence is not testable here. The traversal defences are written to be host-independent and read soundly, but were exercised only on Linux/Python 3.12.
* **Timing.** SEC-2/SEC-10 latencies are from this machine's filesystem; absolute numbers will differ elsewhere — the *scaling* behaviour, not the constants, is the finding.
* **Three STORE items remain code-reading only** (marked *Likely* in §4b): the `_create_unlocked` history-deletion over-match, the silently swallowed `_rollback_full_install` failure, and `_is_temporary_file` flagging user files. Probe designs are given for each.
* **The fuzz per-class counts are upper bounds.** Each failing document is attributed to its highest-priority class, and a delta-debug round collapsed every value-side failure to its smallest instance (`{'k': '\n'}`), so the class *existence* claims rest on the hand-written minimal probes, not on the fuzzer's counts.
* **Coverage is now complete across all seven workstreams.** The one caveat is depth: `insights.py` exposes ten further advisory functions (`risk_scan`, `registry_preview`, `quarantine_plan`, `update_preview`, `eval_plan`, `bundle_policy`, `ownership_states`, `consumer_view`, `diff_three_way`) that the workstream confirmed have **zero product callers**; they were read for injection/path issues but not fuzzed, since nothing in the shipped product reaches them.
* **`webapp.py:970` (`["xdg-open", url]`)** is the third and last `subprocess` site in the package; it is shell-free and takes a server-computed URL, but was not exercised under a hostile `PATH` (that scenario is covered as SEC-16 for the launcher, which shares the pattern).

---

## 7. Recommended remediation order

Ordered by *expected loss avoided per unit of work*, not by ID.

**Stop the bleeding — data loss and unrecoverable states (do these first):**

1. **FM-1** — remove `.strip()` from the document-marker test. A one-line change that stops silent truncation of user-authored descriptions on **every write path** (`store.create`, `store.edit`, `scopes.edit_skill`, `create_skill`). Highest impact-to-diff ratio in the report.
2. **STORE-1** — never `rmtree` a staging directory that still holds a displaced original; make the rollback `except BaseException`. This is the only finding that destroys a user's sole copy with no trace.
3. **STORE-3** + **SCOPE-13** — enforce the one-document invariant in `add()`, `disable()`, `enable()`, `doctor()`, `toggle_skill()`. Today a normal accident (hand-disabling a skill, then pasting a new `SKILL.md`) silently destroys one document on any later toggle.
4. **STORE-4** — take the destination's per-skill lock in `import_` around `commit_staged_skill`, so an import cannot silently discard a committed `edit()`. Silent lost update with `doctor()` reporting healthy.
5. **STORE-5** — give the trash directory its own lock and reconcile `trashed` rows in `resync()`; wrap `restore()`'s move so no raw `OSError` escapes.
6. **STORE-2** — put `add()` under the existing per-skill lock, copy to a staging dir, and `os.replace` it into place.

**Fix the crashes that make the whole tool unusable on one bad file:**

7. **FM-2** + **FM-3** — raise `FrontmatterError` for a sequence root and for out-of-range/surrogate escapes. One malformed `SKILL.md` currently takes down `doctor`, `resync`, `db_rebuild`, `validate`, `list` and every scope view.
8. **BUG-1** — `_init_db()` in `create` (matching `add`/`list`/`get`), plus convert `sqlite3.Error` to `StoreError` at the `_connect`/`_upsert_entry` seam so no driver exception escapes.
9. **SCOPE-4** — catch `OSError` around the `is_file()`/`read_bytes()` pair in `load_skill` and mark the entry `malformed`, so one unreadable file does not abort every scope view.

**Close the remote attack surface:**

10. **SEC-1** — apply the request policy to `do_GET` (rename `validate_mutation_request` → `validate_request`). Smallest diff with the largest reduction in remote risk.
11. **SEC-3** — stop returning the real agent-skill inventory and `data_dir` from an unauthenticated endpoint.
12. **SEC-2** — bound the nested-root search by *work* (iteration budget / depth-limited `scandir`), not by result count; allowlist `project`.

**Bound the untrusted-input processing:**

13. **CLI-1** — bound the eval regex (out-of-process grading or a wall-clock timeout). A hostile `evals.json` currently hangs the CLI forever and freezes the whole web-UI process GIL-wide; `re.compile` success is not a safety check.
14. **CLI-2** + **SCOPE-12** — reject control characters in metadata keys, and make `_edit_unlocked`/`edit_skill` fail closed on an unparseable document (mirroring the undecodable-document policy that already exists and is test-pinned). One fix pattern, two call sites.
15. **CLI-3** — strip C0/C1 and `ESC` in all display paths; this is a display-spoofing primitive reachable from any imported archive.

**Correctness and silent failure:**

16. **FM-4** — same range check as FM-3.
17. **FM-5**–**FM-12** — the medium round-trip defects. FM-8 first (a tab before `#` truncates a value with no unusual input), then FM-9 (the dumper emitting output its own parser rejects), then the block-scalar fidelity group.
18. **BUG-2** — align `loader`/`effective` validity with `validate_skill`; the diagnostic currently contradicts the validator.
19. **SCOPE-1**, **SCOPE-2**, **SCOPE-3** — settle the symlink policy in one place: `copytree(symlinks=True)` or reject, and make reads and writes address the same entry.
20. **SCOPE-6**, **SCOPE-7**, **SCOPE-9**, **SCOPE-10** — precedence reporting, root deduplication, one owner for "global", and no module-global store.
21. **SCOPE-11**, **SCOPE-14**, **SCOPE-15**, **SCOPE-16**, **SCOPE-18** — view consistency.
22. **BUG-5**, **BUG-3**, **BUG-4**, **BUG-6** — frontend state and error surfacing; **BUG-5** first because it can remove the wrong skill permanently.
23. **BUG-8** — replace the nine silent swallows with `diagnose()` (also removes BUG-7's trigger).
24. **SEC-11**, **SEC-6** — upload fidelity and clean error translation.
25. **STORE-6**–**STORE-13**, **FM-11**–**FM-21** — remaining medium/low items.
26. **SEC-9** — hash-pin the vendored Vue. Highest-leverage supply-chain fix: one unreviewable file currently becomes code execution in every user's app.
27. **SEC-7**, **SEC-8**, **SEC-14**, **SEC-13**, **BUG-14** — release-pipeline integrity.
28. **SEC-4**, **SEC-5**, **SEC-10**, **SEC-12**, **STORE-11** — CSP, headers, caching, cross-process locking (the last is one change serving both SEC-12 and STORE-11).
29. **SEC-15**–**SEC-19**, **BUG-10**–**BUG-12**, **BUG-15**, **STORE-14** — launchers, governance, hygiene, dead code, documentation drift.

**Suggested regression tests to add alongside the fixes** (the existing 477 all pass with every bug above present, so each fix needs its own red-first test): the FM-1 marker-in-block-scalar case; an interrupt injected at `import_`'s commit move; concurrent `add`+`remove`; `add` of a both-documents directory followed by a toggle; concurrent `purge_trash`+`restore`; a sequence-root and an out-of-range-escape `SKILL.md` driven through `doctor`/`resync`/`validate`; `Store.create()` on a truly fresh dir with **no** `init_db()` in `setUp`.

---

## 8. Appendix — reproduction index

Every *Confirmed* finding above is reproducible with an isolated data root. Probe scripts live in `/tmp` (not in the repo, by design).

**This workstream (§3, §4, and the §2.5 verified controls):** `probe_host2.py` (SEC-1), `probe_dos2.py` (SEC-2), `probe_leak4.py` (SEC-3), `probe_web3.py` + `probe_smuggle.py` (SEC-5, BUG-9), `probe_upload2.py` (SEC-6, SEC-11), `probe_init.py` (BUG-1), `probe_nofm.py` (BUG-2), `probe_loader.py` (BUG-10), `probe_tar.py` (verified archive controls), `probe_infoleak.py` (SEC-2/SEC-3 oracle).

**Store workstream (§4b):** `/tmp/probes/p01_add_both_docs.py`, `p02_add_failure.py`, `p03_import_interrupt.py`, `p03b_tmp_gone.py`, `p04_lock_coverage.py`, `p05_import_edit_lost_update.py`, `p06_purge_restore_race.py`, `p07_db_trust.py`, `p08_export.py`, `p09_purge_txn.py`, `p10_contracts.py`, `p11b_symlink_roundtrip.py`, `p13b_add_no_lock_real.py`, `p14_resync_rebuild_race.py`, `p15_purge_partial.py`, `p16_names.py`, `p17_both_docs_asymmetry.py`, plus `p12/churn.py` + `p12/remover.py` for the two-process run.

**Scope workstream (§4c):** `/tmp/audit_probes/p1c_flat_alias.py`, `p1d_alias_write.py`, `p2_escape_symlink.py`, `p3_symlinked_home.py`, `p3b_grouping_collision.py`, `p4b_sync_symlink_content.py`, `p5_sync_failures.py`, `p5c_stage_squatter.py`, `p6_rest.py`, `p7_global_path_divergence.py`, `p8_env_roots.py`, `p9_sync_global_injected_store.py`, `p10_malformed_edit.py`, `p11_permission.py`, `p12_misc.py`, `p13_view_consistency.py`, `p14_unicode_case.py`, `p15_states_and_encoding.py`, `p16_dangling.py`, `p17_snapshot_crosstalk.py`, `p18_rest_scan_abort.py`, `e1_overall_resolution.py`, `e2_symlink_roots.py`, `e3_budget.py`.

**Frontmatter workstream (§4d):** `/tmp/probe_findings.py` (60 targeted cases, prints the `[FM-n]` labels), `probe_hostile.py` (45), `probe_validator.py`, `probe_e2e.py` (the Store-level corruption), `probe_downstream.py`, `probe_keys.py`, `probe_templates.py` (FM-21), `fuzz_final.py` (the 25,000-document campaign), `fuzz_roundtrip.py` / `fuzz_shrink.py` (exploratory + minimisation). Full report also at `/tmp/skillsmgr-frontmatter-audit.md`.

**CLI / registry / evals workstream (§4e):** `/tmp/probe/p01_ansi.sh`, `p02_archive_ansi.sh`, `p03_hostile_archive.py`, `p04_matrix.sh`, `p05_evals.py`, `p06_json_matrix.py`, `p07_generic_errors.py`, `p08_misc.sh`, `p09_open_evidence.sh` (the INFO-1 false-positive disproof), `p10_insights.py`, `p11_evals_cli.sh` (the CLI ReDoS), `p12_rest_redos.py` (GIL freeze), `p13_rest_redos_2proc.py` (REST ReDoS, two processes).

**My own reproductions in this session** (in addition to aggregating the workstreams): `probe_host2.py`, `probe_dos.py`, `probe_dos2.py`, `probe_leak2.py`, `probe_leak3.py`, `probe_leak4.py`, `probe_infoleak.py`, `probe_web3.py`, `probe_smuggle.py`, `probe_upload.py`, `probe_upload2.py`, `probe_init.py`, `probe_tar.py`, `probe_loader.py`, `probe_nofm.py`, `probe_host.py`, plus inline probes for FM-1/FM-2/FM-3/FM-4, the install-validation matrix, the eval path-safety matrix, the CLI exit-code/JSON matrix, and the ReDoS hang.

The standard harness shapes used throughout:

```python
# HTTP / web findings
import os, sys, tempfile, threading, http.client
sys.path.insert(0, '/home/uday-varmora/skills-manager')
from skillsmgr.store import Store
from skillsmgr import webapp

data = tempfile.mkdtemp(prefix="probe-")
store = Store(data_dir=data); store.init_db()   # BUG-1: without init_db(), create() raises
srv = webapp.WebAppServer(store, "127.0.0.1", 0)
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.port

# Hostile request: attacker Host + cross-site Fetch Metadata, no credentials
c = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
c.request("GET", "/api/skills", headers={
    "Host": "evil.example:1", "Sec-Fetch-Site": "cross-site",
    "Origin": "https://evil.example", "Referer": "https://evil.example/p"})
print(c.getresponse().status, c.getresponse().read()[:200])
```

```python
# Frontmatter round-trip harness (FM-1, FM-2, FM-3 reproduced in this session)
import sys, tempfile
sys.path.insert(0, '/home/uday-varmora/skills-manager')
from skillsmgr.frontmatter import dump_frontmatter, parse_frontmatter

# FM-1: an indented '---' ends the block early
d = {"description": "Use this skill when a doc has\n---\na rule in it."}
doc = dump_frontmatter(d)
print(repr(doc)); print(parse_frontmatter(doc))     # -> ('Use this skill when a doc has', '  a rule in it.\n---\n')

# FM-2: a sequence root returns a list, not a dict
print(parse_frontmatter("---\n- a\n- b\n---\nbody\n"))          # -> (['a', 'b'], 'body\n')

# FM-3: out-of-range escapes raise raw ValueError / OverflowError
parse_frontmatter('---\ndescription: "x \\U00110000 y"\n---\nb\n')
```

---

*End of report. No files in the repository were modified by this audit — the only file created is this report itself (`DEEP-AUDIT-2026-09-11.md`) plus the tooling venv and probe scripts outside the repo, all under `/tmp`.*
