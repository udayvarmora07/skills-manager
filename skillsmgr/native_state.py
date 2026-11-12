"""Bounded, read-only observations of selected native agent settings.

These files are only a subset of each consumer's configuration sources.
Observations never establish effective loading or change manager state.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tomllib
from pathlib import Path

from .file_reads import read_regular_file
from .paths import home_dir
from .validator import MAX_COMBINED_DESCRIPTION

MAX_CONFIG_BYTES = 1024 * 1024
MAX_RULES = 10_000
MAX_OPENCODE_RULES = 256
MAX_PATTERN = 512
MAX_GEMINI_DISABLED = 1_000
_CLAUDE_VALUES = frozenset(('on', 'name-only', 'user-invocable-only', 'off'))
_OPENCODE_VALUES = frozenset(('allow', 'ask', 'deny'))

#: Default per-entry cap for ``description`` + ``when_to_use`` and the default
#: share of the context window the skill listing is allowed to use, both from
#: ``docs/34-agent-skill-loading-research-2026-11-07.md`` ("Claude Code skill
#: listing budget").  They are defaults, not observations: a settings file that
#: declares one wins, and the evidence always says which source was used.
DEFAULT_LISTING_MAX_DESC_CHARS = MAX_COMBINED_DESCRIPTION
DEFAULT_LISTING_BUDGET_FRACTION = 0.01
#: A declared cap above this is not a plausible listing cap, so it is reported
#: as unusable evidence instead of applied.
MAX_LISTING_MAX_DESC_CHARS = 1_000_000
#: The environment variable Claude Code documents as a fixed character budget.
LISTING_BUDGET_ENV = 'SLASH_COMMAND_TOOL_CHAR_BUDGET'
_CLAUDE_LISTING_KEYS = ('skillListingMaxDescChars', 'skillListingBudgetFraction')
_CLAUDE_REASON = 'Managed, CLI, and plugin settings are not observed.'
#: Gemini CLI system settings files are documented for Linux only, so the other
#: platforms are reported ``unavailable`` rather than guessed at.
_GEMINI_SYSTEM_SOURCES = (
    ('system-defaults', '/etc/gemini-cli/system-defaults.json',
     'GEMINI_CLI_SYSTEM_DEFAULTS_PATH'),
    ('system', '/etc/gemini-cli/settings.json',
     'GEMINI_CLI_SYSTEM_SETTINGS_PATH'),
)
_GEMINI_REASON = (
    'Environment variables and CLI arguments rank above these settings files '
    'and are not observed. Gemini documents disabling by exact skill name; '
    'case sensitivity is not documented.'
)
_GEMINI_NON_LINUX = 'Documented settings path is Linux-only; not observed here.'
#: Codex ``[[skills.config]]`` entries (docs/34, "Codex").  Only the user file
#: is read: CLI flags, profiles, managed requirements and project files are not.
MAX_CODEX_ENTRIES = 1_000
_CODEX_REASON = (
    'Only $CODEX_HOME/config.toml (default ~/.codex/config.toml) is read; CLI '
    'flags, profiles, managed requirements and project configuration are not '
    'observed. A path entry matches one SKILL.md; a name entry matches every '
    'skill with that name; the last matching entry wins.'
)


def _unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _load(path: Path | None) -> tuple[str, dict | None]:
    if path is None:
        return 'unobserved', None
    try:
        data = read_regular_file(path, MAX_CONFIG_BYTES)
        value = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_object)
        if not isinstance(value, dict):
            return 'unavailable', None
        return 'ok', value
    except FileNotFoundError:
        return 'missing', None
    except (OSError, UnicodeError, ValueError, RecursionError):
        return 'unavailable', None


def _glob_match(pattern: str, text: str) -> bool:
    """Match only * and ?; bracket syntax is literal."""
    p = t = 0
    star = -1
    retry = 0
    while t < len(text):
        if p < len(pattern) and (pattern[p] == '?' or pattern[p] == text[t]):
            p += 1
            t += 1
        elif p < len(pattern) and pattern[p] == '*':
            star = p
            p += 1
            retry = t
        elif star >= 0:
            retry += 1
            t = retry
            p = star + 1
        else:
            return False
    return all(char == '*' for char in pattern[p:])


def _prepare_rules(consumer: str, config: dict) -> tuple[str, object]:
    if consumer == 'claude-code':
        rules = config.get('skillOverrides', {})
        allowed = _CLAUDE_VALUES
    else:
        permission = config.get('permission', {})
        if not isinstance(permission, dict):
            return 'invalid', None
        if 'skill' not in permission:
            return 'ok', None
        rules = permission['skill']
        allowed = _OPENCODE_VALUES
        if isinstance(rules, str):
            return ('ok', rules) if rules in allowed else ('invalid', None)
    if not isinstance(rules, dict):
        return 'invalid', None
    limit = MAX_OPENCODE_RULES if consumer == 'opencode' else MAX_RULES
    if len(rules) > limit:
        return 'unavailable', None
    if any(len(key) > MAX_PATTERN or not isinstance(value, str) or value not in allowed for key, value in rules.items()):
        return 'invalid', None
    return 'ok', rules


def _match_rules(consumer: str, rules: object, name: str) -> dict:
    if rules is None:
        return {}
    if isinstance(rules, str):
        return {'declared': rules}
    if consumer == 'claude-code':
        return {'declared': rules[name]} if name in rules else {}
    result = {}
    for pattern, value in rules.items():
        if _glob_match(pattern, name):
            result['declared'] = value
            result['matched_pattern'] = json.dumps(pattern, ensure_ascii=True)[1:-1]
    return result


def _gemini_system_entry(source: str, default: str, env_name: str) -> tuple:
    """One system settings source, or an explicit non-Linux ``unavailable``."""
    configured = os.environ.get(env_name)
    if configured:
        return source, Path(configured), None
    if sys.platform.startswith('linux'):
        return source, Path(default), None
    return source, None, _GEMINI_NON_LINUX


def _gemini_files(home: Path, project: Path | None) -> list[tuple]:
    """Gemini CLI settings files, lowest to highest precedence."""
    return [
        _gemini_system_entry(*_GEMINI_SYSTEM_SOURCES[0]),
        ('user', home / '.gemini/settings.json', None),
        ('project', project / '.gemini/settings.json' if project else None, None),
        _gemini_system_entry(*_GEMINI_SYSTEM_SOURCES[1]),
    ]


def _gemini_names(value: object) -> frozenset | None:
    """A bounded set of exact skill names, or ``None`` when unusable."""
    if not isinstance(value, list):
        return None
    names = set()
    for item in value:
        if not isinstance(item, str) or not item or len(item) > MAX_PATTERN:
            return None
        names.add(item)
    return frozenset(names)


def _gemini_flags(config: dict) -> tuple:
    """Typed ``skills``/``admin.skills`` declarations, without raising."""
    invalid: list = []
    disabled: frozenset = frozenset()
    skills_enabled = None
    admin_enabled = None
    skills = config.get('skills')
    if skills is not None:
        if not isinstance(skills, dict):
            invalid.append('skills')
        else:
            if 'disabled' in skills:
                names = _gemini_names(skills['disabled'])
                if names is None:
                    invalid.append('skills.disabled')
                else:
                    disabled = names
            if 'enabled' in skills:
                if isinstance(skills['enabled'], bool):
                    skills_enabled = skills['enabled']
                else:
                    invalid.append('skills.enabled')
    admin = config.get('admin')
    if admin is not None:
        if not isinstance(admin, dict):
            invalid.append('admin')
        else:
            admin_skills = admin.get('skills')
            if admin_skills is not None:
                if not isinstance(admin_skills, dict):
                    invalid.append('admin.skills')
                elif 'enabled' in admin_skills:
                    if isinstance(admin_skills['enabled'], bool):
                        admin_enabled = admin_skills['enabled']
                    else:
                        invalid.append('admin.skills.enabled')
    return invalid, disabled, skills_enabled, admin_enabled


def _prepare_gemini_source(source: str, status: str, config: dict | None) -> dict:
    """One file's declarations, or an explicit invalid/unavailable status."""
    if config is None:
        return {'source': source, 'status': status}
    skills = config.get('skills')
    raw_names = skills.get('disabled') if isinstance(skills, dict) else None
    if isinstance(raw_names, list) and len(raw_names) > MAX_GEMINI_DISABLED:
        return {'source': source, 'status': 'unavailable'}
    invalid, disabled, skills_enabled, admin_enabled = _gemini_flags(config)
    if invalid:
        return {'source': source, 'status': 'invalid', 'invalid_keys': invalid}
    entry = {'source': source, 'status': 'ok'}
    if disabled:
        entry['disabled_names'] = disabled
    if skills_enabled is not None:
        entry['skills_enabled'] = skills_enabled
    if admin_enabled is not None:
        entry['admin_skills_enabled'] = admin_enabled
    return entry


def _prepare_gemini_batch(home: Path, project: Path | None) -> list[dict]:
    """Read each Gemini settings file at most once per scope batch."""
    prepared = []
    for source, path, unavailable in _gemini_files(home, project):
        if unavailable is not None:
            prepared.append({'source': source, 'status': 'unavailable', 'reason': unavailable})
            continue
        status, config = _load(path)
        prepared.append(_prepare_gemini_source(source, status, config))
    return prepared


def _gemini_evidence(name: str, entry: dict) -> dict:
    evidence = {'source': entry['source'], 'status': entry['status']}
    if entry['status'] == 'ok':
        if name in entry.get('disabled_names', ()):
            evidence['declared'] = 'disabled'
        for key in ('skills_enabled', 'admin_skills_enabled'):
            if key in entry:
                evidence[key] = entry[key]
    elif entry.get('invalid_keys'):
        evidence['invalid_keys'] = list(entry['invalid_keys'])
    elif entry.get('reason'):
        evidence['reason'] = entry['reason']
    return evidence


def _last_boolean(sources: list[dict], key: str) -> bool | None:
    """The last source that declares *key* wins, matching settings precedence."""
    value = None
    for entry in sources:
        if key in entry:
            value = entry[key]
    return value


def _gemini_observation(name: str, prepared: list[dict]) -> dict:
    """Per-name evidence; a union list or a global off switch means disabled."""
    sources = [_gemini_evidence(name, entry) for entry in prepared]
    skills_enabled = _last_boolean(sources, 'skills_enabled')
    admin_enabled = _last_boolean(sources, 'admin_skills_enabled')
    disabled = (any(entry.get('declared') == 'disabled' for entry in sources)
                or skills_enabled is False or admin_enabled is False)
    result = {
        'consumer': 'gemini',
        'effective_state': 'unknown',
        # Environment variables and CLI arguments outrank every file and are not
        # observed, so a settings-only read is never complete.
        'partial': True,
        'sources': sources,
        'observed_setting': 'disabled' if disabled else 'not disabled by the files read',
        'reason': _GEMINI_REASON,
    }
    if skills_enabled is not None:
        result['skills_enabled'] = skills_enabled
    if admin_enabled is not None:
        result['admin_skills_enabled'] = admin_enabled
    return result


def observe_native_states(consumer: str, names: list[str], *, home: Path | None = None,
                          project: Path | None = None) -> dict:
    """Observe a batch from one request-local snapshot of each settings file."""
    if not names:
        return {}
    home = home_dir() if home is None else Path(home)
    project = Path(project) if project is not None else None
    if consumer == 'gemini':
        prepared = _prepare_gemini_batch(home, project)
        return {name: _gemini_observation(name, prepared) for name in names}
    files = []
    if consumer == 'claude-code':
        files = [('user', home / '.claude/settings.json'),
                 ('project', project / '.claude/settings.json' if project else None),
                 ('project-local', project / '.claude/settings.local.json' if project else None)]
        reason = _CLAUDE_REASON
    elif consumer == 'opencode':
        files = [('user', home / '.config/opencode/opencode.json'),
                 ('project', project / 'opencode.json' if project else None)]
        reason = 'Environment, remote, .opencode, and managed settings are not observed; cross-file rule merging is not inferred.'
    elif consumer == 'codex':
        states = observe_codex_states([(name, None) for name in names], home=home)
        return dict(zip(names, states))
    else:
        reason = 'native settings observation is unsupported for this consumer'
    prepared = []
    for source, path in files:
        status, config = _load(path)
        rules = None
        if config is not None:
            status, rules = _prepare_rules(consumer, config)
        prepared.append((source, status, rules))
    return {name: _observation(consumer, name, reason, prepared) for name in names}


def _observation(consumer: str, name: str, reason: str, prepared: list) -> dict:
    result = {'consumer': consumer, 'effective_state': 'unknown', 'partial': True,
              'sources': [], 'reason': reason}
    for source, status, rules in prepared:
        entry = {'source': source, 'status': status}
        if status == 'ok':
            entry.update(_match_rules(consumer, rules, name))
        result['sources'].append(entry)
    # ``unobserved`` means the caller supplied no project context, not that a
    # file was unreadable -- so it must not suppress a declaration that *was*
    # observed.  ``partial`` stays true and ``effective_state`` stays unknown,
    # because a project file we never looked at could still override it.
    if consumer == 'claude-code' and all(
        e['status'] in ('ok', 'missing', 'unobserved') for e in result['sources']
    ):
        declarations = [e['declared'] for e in result['sources'] if 'declared' in e]
        if declarations:
            result['observed_setting'] = declarations[-1]
    return result


def observe_native_state(consumer: str, name: str, *, home: Path | None = None,
                         project: Path | None = None) -> dict:
    """Observe selected settings without inferring effective state or loading."""
    return observe_native_states(consumer, [name], home=home, project=project)[name]


def _listing_cap(value: object) -> int | None:
    """A declared per-entry cap, or ``None`` when it is not usable evidence."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 < value <= MAX_LISTING_MAX_DESC_CHARS else None


def _listing_fraction(value: object) -> float | None:
    """A declared window share, or ``None`` when it is not usable evidence."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if 0.0 < value <= 1.0 else None


def _listing_entry(source: str, path: Path | None) -> dict:
    """Read one settings file's listing declarations, bounded and typed."""
    status, config = _load(path)
    entry = {'source': source, 'status': status}
    if config is None:
        return entry
    declared = {}
    cap = _listing_cap(config.get('skillListingMaxDescChars'))
    if cap is not None:
        declared['skillListingMaxDescChars'] = cap
    fraction = _listing_fraction(config.get('skillListingBudgetFraction'))
    if fraction is not None:
        declared['skillListingBudgetFraction'] = fraction
    if declared:
        entry['declared'] = declared
    invalid = sorted(key for key in _CLAUDE_LISTING_KEYS if key in config and key not in declared)
    if invalid:
        entry['invalid_keys'] = invalid
    return entry


def _last_declared(sources: list[dict], key: str):
    """The last source that declares *key* wins, mirroring rule observation.

    The file order is the documented settings order (``user`` then ``project``
    then ``project-local``), so the last declaration is the most specific one.
    This is an observed declaration, never a claim about effective state.
    """
    value = None
    for entry in sources:
        declared = entry.get('declared')
        if isinstance(declared, dict) and key in declared:
            value = declared[key]
    return value


def _env_budget() -> dict:
    """Read the documented fixed character budget from the environment."""
    raw = os.environ.get(LISTING_BUDGET_ENV)
    if raw is None:
        return {'status': 'unset', 'value': None}
    text = raw.strip()
    if not (text.isascii() and text.isdigit()) or int(text) <= 0:
        # The value is never echoed: an environment variable is not a place to
        # assume a number, and this report is rendered in a terminal.
        return {'status': 'invalid', 'value': None, 'reason': 'not a positive integer'}
    return {'status': 'set', 'value': int(text)}


def observe_claude_listing(*, home: Path | None = None,
                           project: Path | None = None) -> dict:
    """Observe the Claude Code skill-listing budget inputs (read-only).

    Reads only the two documented settings keys from the same three settings
    files :func:`observe_native_states` reads, plus the documented
    ``SLASH_COMMAND_TOOL_CHAR_BUDGET`` environment variable.  Nothing is
    cached, written, or treated as effective state: ``partial`` is true when a
    settings file exists but could not be parsed, which is exactly the case
    where a hidden ``skillOverrides`` declaration could exist.
    """
    home = home_dir() if home is None else Path(home)
    project = Path(project) if project is not None else None
    files = [('user', home / '.claude/settings.json'),
             ('project', project / '.claude/settings.json' if project else None),
             ('project-local', project / '.claude/settings.local.json' if project else None)]
    sources = [_listing_entry(source, path) for source, path in files]
    return {
        'consumer': 'claude-code',
        'effective_state': 'unknown',
        # ``unobserved`` (no project context) and ``missing`` (no file) cannot
        # hide a declaration.  A file that exists but could not be parsed can,
        # which is what ``partial`` means everywhere in this module.
        'partial': any(entry['status'] in ('unavailable', 'invalid') for entry in sources),
        'sources': sources,
        'max_desc_chars': _last_declared(sources, 'skillListingMaxDescChars'),
        'budget_fraction': _last_declared(sources, 'skillListingBudgetFraction'),
        'env_budget': _env_budget(),
        'reason': _CLAUDE_REASON,
    }


def _load_toml(path: Path) -> tuple[str, dict | None]:
    """Read one bounded TOML file; never raises (mirrors :func:`_load`)."""
    try:
        data = read_regular_file(path, MAX_CONFIG_BYTES)
        return 'ok', tomllib.loads(data.decode('utf-8'))
    except FileNotFoundError:
        return 'missing', None
    except (OSError, UnicodeError, ValueError, RecursionError):
        return 'unavailable', None


def _codex_config_path(home: Path) -> Path:
    root = os.environ.get('CODEX_HOME', '').strip()
    return (Path(root).expanduser() if root else home / '.codex') / 'config.toml'


def _codex_rule(entry: object) -> tuple | None:
    """One valid ``(selector, value, enabled)`` rule, or ``None`` if invalid."""
    if not isinstance(entry, dict) or not isinstance(entry.get('enabled'), bool):
        return None
    selectors = [key for key in ('path', 'name') if key in entry]
    if len(selectors) != 1 or not isinstance(entry[selectors[0]], str):
        return None
    value = entry[selectors[0]]
    if not value or len(value) > MAX_PATTERN or '\x00' in value:
        return None
    if selectors[0] == 'path':
        expanded = os.path.expanduser(value)
        if not os.path.isabs(expanded):
            return None
        value = os.path.realpath(expanded)
    return selectors[0], value, entry['enabled']


def _prepare_codex(home: Path) -> dict:
    status, config = _load_toml(_codex_config_path(home))
    prepared = {'status': status, 'rules': [], 'invalid_entries': 0}
    if config is None:
        return prepared
    skills = config.get('skills', {})
    entries = skills.get('config', []) if isinstance(skills, dict) else None
    if not isinstance(entries, list):
        prepared['status'] = 'invalid'
        return prepared
    if len(entries) > MAX_CODEX_ENTRIES:
        prepared['status'] = 'unavailable'
        return prepared
    for entry in entries:
        rule = _codex_rule(entry)
        if rule is None:
            prepared['invalid_entries'] += 1
        else:
            prepared['rules'].append(rule)
    return prepared


#: At most this many unmatchable ``[[skills.config]]`` entries are listed.
MAX_DEAD_ENTRIES = 50


def _dead_entry_problem(value: str) -> tuple[str | None, str | None]:
    """Why a Codex ``path`` entry can never match a skill, and the path to use."""
    target = Path(os.path.realpath(os.path.expanduser(value)))
    try:
        mode = target.stat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return 'missing', None
    except OSError:
        return None, None  # unreadable: Codex may still match it, so say nothing
    if stat.S_ISDIR(mode):
        document = target / 'SKILL.md'
        return 'folder', str(document) if document.is_file() else None
    return (None, None) if target.name == 'SKILL.md' else ('not-skill-document', None)


def _dead_entries(entries: list) -> list[dict]:
    dead = []
    for index, entry in enumerate(entries):
        rule = _codex_rule(entry)
        if rule is None or rule[0] != 'path':
            continue
        problem, suggested = _dead_entry_problem(entry['path'])
        if problem:
            dead.append({'index': index, 'path': entry['path'], 'enabled': rule[2],
                         'problem': problem, 'suggested_path': suggested})
    return dead


def codex_config_dead_entries(*, home: Path | None = None) -> dict:
    """Codex ``path`` entries that name a folder, a missing file or a non-``SKILL.md``.

    Codex compares a ``path`` entry with the skill's ``SKILL.md`` file, so such
    an entry silently changes nothing (openai/codex#51044).  Read-only.
    """
    path = _codex_config_path(home_dir() if home is None else Path(home))
    status, config = _load_toml(path)
    report = {'state': status, 'config_path': str(path), 'entries': [], 'total': 0, 'omitted': 0}
    if config is None:
        return report
    skills = config.get('skills', {})
    entries = skills.get('config', []) if isinstance(skills, dict) else None
    if not isinstance(entries, list) or len(entries) > MAX_CODEX_ENTRIES:
        report['state'] = 'invalid' if not isinstance(entries, list) else 'unavailable'
        return report
    dead = _dead_entries(entries)
    report.update(state='observed', entries=dead[:MAX_DEAD_ENTRIES], total=len(dead),
                  omitted=max(0, len(dead) - MAX_DEAD_ENTRIES))
    return report


def _codex_match(name: str, document: Path | None, rules: list, resolved: dict) -> tuple | None:
    """The last matching ``(selector, enabled)``; resolves *document* lazily."""
    match = None
    for selector, value, enabled in rules:
        if selector == 'name':
            hit = value == name
        elif document is None:
            hit = False
        else:
            if 'path' not in resolved:
                resolved['path'] = os.path.realpath(document)
            hit = resolved['path'] == value
        if hit:
            match = (selector, enabled)
    return match


def _codex_observation(name: str, document: Path | None, prepared: dict) -> dict:
    evidence = {'source': 'user', 'status': prepared['status']}
    if prepared['invalid_entries']:
        evidence['invalid_entries'] = prepared['invalid_entries']
    result = {'consumer': 'codex', 'effective_state': 'unknown', 'partial': True,
              'sources': [evidence], 'reason': _CODEX_REASON}
    if prepared['status'] not in ('ok', 'missing'):
        return result
    match = _codex_match(name, document, prepared['rules'], {})
    if match is None:
        result['observed_setting'] = 'not disabled by the files read'
        return result
    evidence['declared'] = 'enabled' if match[1] else 'disabled'
    evidence['matched_selector'] = match[0]
    result['observed_setting'] = evidence['declared']
    return result


def observe_codex_states(entries: list[tuple[str, Path | None]], *,
                         home: Path | None = None) -> list[dict]:
    """Observe Codex's ``[[skills.config]]`` switch for each ``(name, SKILL.md)``.

    The config file is read once per batch.  A ``None`` document can still be
    matched by a ``name`` entry, never by a ``path`` entry.  Read-only: no file
    is written and ``effective_state`` stays unknown.
    """
    if not entries:
        return []
    prepared = _prepare_codex(home_dir() if home is None else Path(home))
    return [_codex_observation(name, document, prepared) for name, document in entries]


def observe_native_entries(consumer: str, entries: list[tuple[str, Path | None]], *,
                           home: Path | None = None, project: Path | None = None) -> list[dict]:
    """Per-row observations, aligned with *entries* of ``(name, SKILL.md path)``.

    Codex matches a document path, so it is observed per row; every other
    consumer matches by name and shares one batch read.
    """
    if consumer == 'codex':
        return observe_codex_states(entries, home=home)
    states = observe_native_states(consumer, [name for name, _ in entries], home=home, project=project)
    return [states[name] for name, _ in entries]
