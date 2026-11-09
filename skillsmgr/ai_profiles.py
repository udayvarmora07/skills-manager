"""Suggest a catalog profile from bounded, metadata-only project signals."""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

from . import adapters, catalog, scopes
from .ai import AiError, AiRun, untrusted_block
from .ai_concise import _guard_available, _open_root
from .ai_skills import _listing_text, _save_run
from .context import bound_store
from .loader import scan_dir
from .store import Store, StoreError
from .validator import validate_skill_name

MAX_ENTRIES = 10_000
MAX_PER_DIR = 1_000
MAX_DEPTH = 3
MAX_SKILLS = 600
MAX_DIRECTORY_NAMES = 100
_SKIP_DIRS = frozenset({'node_modules', 'vendor', 'dist', 'build', 'target', '__pycache__',
                        '.git', '.hg', '.svn', '.venv', 'venv', '.tox', '.mypy_cache', '.pytest_cache'})
_MANIFESTS = frozenset({'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock',
                        'pyproject.toml', 'requirements.txt', 'Pipfile', 'poetry.lock',
                        'Cargo.toml', 'Cargo.lock', 'go.mod', 'go.sum', 'Gemfile',
                        'Gemfile.lock', 'composer.json', 'pom.xml', 'build.gradle',
                        'build.gradle.kts', 'Dockerfile', 'Makefile'})
_SAFE_DIR = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')
_EXTENSION = re.compile(r'^\.[a-z0-9]{1,12}$')
_SYSTEM = ('Suggest a named catalog profile of useful existing AI coding-agent skills '
           'for the given project signals. Select only names from the provided skill listing. '
           'Return JSON with name, description, and skills (an array of names).')


def _project(project, roots: list[Path]) -> Path:
    try:
        observation = adapters.project_observation(project, roots)
    except (OSError, ValueError, TypeError, StoreError):
        raise AiError('the project could not be inspected within managed roots', 'ai-input') from None
    if observation.get('status') != 'accepted':
        raise AiError('the project is unavailable or outside managed roots', 'ai-input', 403)
    return Path(observation['path'])


def _open_project(project: Path, roots: list[Path]) -> int:
    _guard_available()
    candidates = [root for root in roots if project == root or root in project.parents]
    if not candidates:
        raise AiError('the project is unavailable or outside managed roots', 'ai-input', 403)
    root = max(candidates, key=lambda p: len(p.parts))
    try:
        fd = _open_root(root)
        try:
            for component in project.relative_to(root).parts:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            return fd
        except BaseException:
            os.close(fd)
            raise
    except OSError:
        raise AiError('the project changed or cannot be accessed safely', 'ai-input') from None


def _entry_names(fd: int, state: dict) -> list[str]:
    names = []
    with os.scandir(fd) as entries:
        for entry in entries:
            if len(names) >= MAX_PER_DIR or state['entries_scanned'] + len(names) >= MAX_ENTRIES:
                state['truncated'] = True
                break
            names.append(entry.name)
    return sorted(names)


def _record_file(name: str, state: dict) -> None:
    if name in _MANIFESTS:
        state['manifests'].add(name)
    suffix = Path(name).suffix.lower()
    if _EXTENSION.fullmatch(suffix):
        state['extensions'][suffix] = state['extensions'].get(suffix, 0) + 1


def _child_dir(fd: int, name: str, depth: int, state: dict) -> None:
    if name in _SKIP_DIRS or name.startswith('.'):
        return
    if depth == 0 and _SAFE_DIR.fullmatch(name):
        if len(state['top_level_dirs']) < MAX_DIRECTORY_NAMES:
            state['top_level_dirs'].append(name)
        else:
            state['truncated'] = True
    if depth >= MAX_DEPTH:
        state['truncated'] = True
        return
    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
    try:
        _walk(child, depth + 1, state)
    finally:
        os.close(child)


def _walk(fd: int, depth: int, state: dict) -> None:
    for name in _entry_names(fd, state):
        if state['entries_scanned'] >= MAX_ENTRIES:
            state['truncated'] = True
            break
        state['entries_scanned'] += 1
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            _child_dir(fd, name, depth, state)
        elif stat.S_ISREG(info.st_mode) and not name.startswith('.'):
            _record_file(name, state)


def _signals(project: Path, roots: list[Path]) -> dict:
    state = {'extensions': {}, 'manifests': set(), 'top_level_dirs': [],
             'entries_scanned': 0, 'truncated': False}
    fd = _open_project(project, roots)
    try:
        try:
            _walk(fd, 0, state)
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeError):
        raise AiError('the project changed or cannot be inspected safely', 'ai-input') from None
    state['extensions'] = [{'extension': ext, 'count': count}
                           for ext, count in sorted(state['extensions'].items())]
    state['manifests'] = sorted(state['manifests'])
    state['top_level_dirs'].sort()
    return state


def _redact_description(text: str) -> str:
    return ' '.join('[path]' if any(c in word for c in ('/', '\\', '~', ':')) else word
                    for word in text.split())[:1536]


def _usable_record(record: dict) -> bool:
    if record.get('decode_error') or record.get('document_missing') or record.get('malformed'):
        return False
    if record.get('addressable') is False:
        return False
    try:
        validate_skill_name(record.get('name'))
        return True
    except ValueError:
        return False


def _skills(data_dir: Path, scope: str) -> list[dict]:
    if not isinstance(scope, str) or not scope or scope == 'all':
        raise AiError('choose one agent scope', 'ai-input')
    try:
        with bound_store(Store(data_dir=data_dir)):
            target = scopes.scope_by_id(scope)
            if target is None:
                raise ValueError('unknown scope')
            roots = () if scope == 'global' else scopes._peer_link_roots(target)
            records = scan_dir(target.base, recursive=target.recursive, link_roots=roots)
    except (OSError, ValueError):
        raise AiError('the selected scope cannot be inspected', 'ai-input') from None
    seen, skills = set(), []
    for record in records:
        if not _usable_record(record) or record['name'] in seen:
            continue
        seen.add(record['name'])
        skills.append({'name': record['name'], 'description': _redact_description(_listing_text(record))})
        if len(skills) > MAX_SKILLS:
            raise AiError(f'this scope has more than {MAX_SKILLS} readable skills', 'ai-input')
    return skills


def _profile(answer, scope: str, skills: list[dict]) -> tuple[dict, int]:
    if not isinstance(answer, dict) or not isinstance(answer.get('skills'), list):
        raise AiError('the model did not return a profile with a skills list', 'ai-bad-output', 502)
    selected = answer['skills']
    if len(selected) > 1000 or not all(isinstance(n, str) for n in selected):
        raise AiError('the model returned an invalid skills list', 'ai-bad-output', 502)
    allowed = {item['name'] for item in skills}
    selected_known = sorted({n for n in selected if n in allowed}, key=str.casefold)
    dropped = sum(n not in allowed for n in selected)
    raw = {'name': answer.get('name'), 'description': answer.get('description'),
           'skills': selected_known, 'targets': [scope]}
    try:
        name = catalog._identifier(raw['name'], 'profile name')
        normalized = catalog.normalize_catalog({'profiles': {name: raw}})['profiles'][name]
    except (catalog.CatalogError, TypeError, ValueError):
        raise AiError('the model returned an invalid profile name or description', 'ai-bad-output', 502) from None
    return {'name': name, **normalized}, dropped


def _managed_roots(data_dir: Path, supplied) -> list[Path]:
    if supplied is not None and not isinstance(supplied, (list, tuple)):
        raise AiError('managed roots are unavailable', 'ai-input')
    selected = supplied or [data_dir]
    try:
        if any(not isinstance(root, (str, Path)) or not str(root).strip() for root in selected):
            raise ValueError('empty managed root')
        return [Path(root).expanduser().resolve() for root in selected]
    except (OSError, ValueError, RuntimeError, TypeError):
        raise AiError('managed roots are unavailable', 'ai-input') from None


def suggest_profile(data_dir: Path, payload: dict, *, allowed_roots=None) -> dict:
    """Suggest, but do not save, a profile using only bounded project metadata."""
    payload = payload if isinstance(payload, dict) else {}
    roots = _managed_roots(data_dir, allowed_roots)
    project = _project(payload.get('project'), roots)
    signals = _signals(project, roots)
    scope = payload.get('scope')
    skills = _skills(Path(data_dir), scope)
    result = {'kind': 'suggest-profile', 'scope': scope, 'status': 'empty', 'signals': signals,
              'profile': None, 'dropped_names': 0, 'egress': [], 'run': None}
    if not skills:
        return result
    estimate = bool(payload.get('estimate'))
    run = AiRun(data_dir, 'suggest-profile', estimate_only=estimate)
    user = ('Project metadata:\n' + untrusted_block('project-metadata', json.dumps(signals, sort_keys=True))
            + '\n\nAvailable skills:\n' + untrusted_block('skill-listing', json.dumps(skills, sort_keys=True))
            + '\nReturn {"name":"<profile-name>","description":"...","skills":["<skill-name>"]}.')
    answer = run.ask_json(_SYSTEM, user, max_output=2000)
    result.update({'status': 'estimate' if estimate else 'suggested', 'run': run.label(),
                   'egress': ['Project file extensions, known manifest names, top-level directory names, '
                              'and selected-scope skill names and descriptions go to the configured model.']})
    if not estimate:
        result['profile'], result['dropped_names'] = _profile(answer, scope, skills)
        result['run_id'] = _save_run(data_dir, result)
    return result
