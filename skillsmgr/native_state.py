"""Bounded, read-only observations of selected native agent settings.

These files are only a subset of each consumer's configuration sources.
Observations never establish effective loading or change manager state.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

MAX_CONFIG_BYTES = 1024 * 1024
MAX_RULES = 10_000
MAX_OPENCODE_RULES = 256
MAX_PATTERN = 512
_CLAUDE_VALUES = frozenset(('on', 'name-only', 'user-invocable-only', 'off'))
_OPENCODE_VALUES = frozenset(('allow', 'ask', 'deny'))

#: Default per-entry cap for ``description`` + ``when_to_use`` and the default
#: share of the context window the skill listing is allowed to use, both from
#: ``docs/34-agent-skill-loading-research-2026-11-07.md`` ("Claude Code skill
#: listing budget").  They are defaults, not observations: a settings file that
#: declares one wins, and the evidence always says which source was used.
DEFAULT_LISTING_MAX_DESC_CHARS = 1_536
DEFAULT_LISTING_BUDGET_FRACTION = 0.01
#: A declared cap above this is not a plausible listing cap, so it is reported
#: as unusable evidence instead of applied.
MAX_LISTING_MAX_DESC_CHARS = 1_000_000
#: The environment variable Claude Code documents as a fixed character budget.
LISTING_BUDGET_ENV = 'SLASH_COMMAND_TOOL_CHAR_BUDGET'
_CLAUDE_LISTING_KEYS = ('skillListingMaxDescChars', 'skillListingBudgetFraction')
_CLAUDE_REASON = 'Managed, CLI, and plugin settings are not observed.'


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
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return 'unavailable', None
            data = stream.read(MAX_CONFIG_BYTES + 1)
        if len(data) > MAX_CONFIG_BYTES:
            return 'unavailable', None
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


def observe_native_states(consumer: str, names: list[str], *, home: Path | None = None,
                          project: Path | None = None) -> dict:
    """Observe a batch from one request-local snapshot of each settings file."""
    if not names:
        return {}
    home = Path.home() if home is None else Path(home)
    project = Path(project) if project is not None else None
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
        reason = 'Codex TOML observation is deferred'
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
    home = Path.home() if home is None else Path(home)
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
