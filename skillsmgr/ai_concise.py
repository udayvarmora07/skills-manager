"""Propose a shorter skill and stage it through the source-update review."""
from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path

from . import frontmatter, source_update
from .ai import AiError, AiRun, untrusted_block
from .ai_skills import _save_run
from .sidecar_binding import MANAGER_SIDECARS
from .source_lock import (MAX_SOURCE_FILES, MAX_SOURCE_FILE_BYTES, MAX_SOURCE_TOTAL_BYTES,
                          MAX_SOURCE_PATH_DEPTH)
from .tokens import count_tokens

MAX_BODY = 100_000
MAX_REFS = 12
MAX_REF_BYTES = 32_000
_SYSTEM = ('You help shorten an AI coding-agent skill. Return JSON with body and references. '
           'Keep essential instructions in the body and move details to reference files. '
           'Each reference has a path references/<lowercase-slug>.md and a text field. '
           'The body must link every new reference. Do not change frontmatter.')
_REF_PATH = re.compile(r'^references/[a-z0-9]+(?:-[a-z0-9]+)*\.md$')
_HEADING = re.compile(r'^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$')
_FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')


def _guard_available() -> None:
    if (os.name != 'posix' or not getattr(os, 'O_NOFOLLOW', 0)
            or not getattr(os, 'O_DIRECTORY', 0) or os.open not in os.supports_dir_fd
            or os.stat not in os.supports_dir_fd or os.scandir not in os.supports_fd):
        raise AiError('safe tree capture is unavailable on this platform', 'ai-input')


def _open_root(path: Path) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open('/', flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_file(parent: int, name: str) -> tuple[bytes, int]:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0), dir_fd=parent)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SOURCE_FILE_BYTES:
            raise ValueError('non-regular or oversized file')
        chunks, total = [], 0
        while total <= MAX_SOURCE_FILE_BYTES:
            chunk = os.read(fd, min(65536, MAX_SOURCE_FILE_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(fd)
        if total > MAX_SOURCE_FILE_BYTES or (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('file changed or exceeds size limit')
        return b''.join(chunks), stat.S_IMODE(info.st_mode) & 0o777
    finally:
        os.close(fd)


def _walk(directory: int, prefix: str, files: dict, directories: dict, budget: list) -> None:
    names = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name in MANAGER_SIDECARS:
                continue
            names.append(entry.name)
            if len(names) + len(files) + len(directories) > MAX_SOURCE_FILES:
                raise ValueError('skill tree exceeds item count limit')
    for name in sorted(names):
        relative = f'{prefix}/{name}' if prefix else name
        if len(relative.split('/')) > MAX_SOURCE_PATH_DEPTH or '\\' in relative:
            raise ValueError('unsafe or overly deep path')
        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if len(files) + len(directories) >= MAX_SOURCE_FILES:
            raise ValueError('skill tree exceeds item count limit')
        if stat.S_ISDIR(info.st_mode):
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            try:
                directories[relative] = stat.S_IMODE(os.fstat(fd).st_mode) & 0o777
                _walk(fd, relative, files, directories, budget)
            finally:
                os.close(fd)
        elif stat.S_ISREG(info.st_mode):
            raw, mode = _read_file(directory, name)
            budget[0] += len(raw)
            if budget[0] > MAX_SOURCE_TOTAL_BYTES or len(files) >= MAX_SOURCE_FILES:
                raise ValueError('skill tree exceeds size or file count limits')
            files[relative] = (raw, mode)
        else:
            raise ValueError('skill tree contains a symlink or special file')


def _tree_hash(files: dict) -> str:
    digest = hashlib.sha256()
    for path, (raw, _mode) in sorted(files.items()):
        encoded = path.encode('utf-8')
        digest.update(len(encoded).to_bytes(8, 'big'))
        digest.update(encoded)
        digest.update(raw)
    return digest.hexdigest()


def _capture(path: Path) -> tuple[dict, dict, str]:
    _guard_available()
    try:
        fd = _open_root(path)
        try:
            files, directories = {}, {'': stat.S_IMODE(os.fstat(fd).st_mode) & 0o777}
            _walk(fd, '', files, directories, [0])
        finally:
            os.close(fd)
        return files, directories, _tree_hash(files)
    except (OSError, ValueError, UnicodeError) as exc:
        raise AiError(f'cannot safely capture skill tree: {exc}', 'ai-input') from None


def _document(files: dict, disabled: bool, name: str) -> tuple[str, str, str]:
    primary = 'SKILL.md.disabled' if disabled else 'SKILL.md'
    try:
        text = files[primary][0].decode('utf-8')
        data, body = frontmatter.parse_frontmatter(text)
        lines = text.split('\n')
        normalized = frontmatter._normalize_crlf(text.removeprefix('\ufeff')).split('\n')
        end = frontmatter._find_closing_marker(normalized) if normalized and frontmatter._DOC_MARKER.match(normalized[0].strip()) else None
        if end is None or data.get('name') != name:
            raise ValueError('frontmatter or skill name is invalid')
        prefix = '\n'.join(lines[:end + 1]) + '\n'
        if len(prefix + body) > MAX_BODY:
            raise ValueError('skill document exceeds model input limit')
        return primary, prefix, body
    except (KeyError, UnicodeError, frontmatter.FrontmatterError, ValueError) as exc:
        raise AiError(f'cannot read skill document: {exc}', 'ai-input') from None


def _section_row(heading: str, line: int, text: str) -> dict:
    tokens, method = count_tokens(text)
    return {'heading': heading, 'line': line, 'tokens': tokens, 'method': method}


def _sections(body: str) -> list[dict]:
    sections, chunk = [], []
    heading, start, fence = 'Preamble', 1, None
    for number, line in enumerate(body.splitlines(keepends=True), 1):
        match = _FENCE.match(line.rstrip('\r\n'))
        if match:
            marker, tail = match.groups()
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not tail.strip():
                fence = None
        title = _HEADING.match(line.rstrip('\r\n')) if fence is None and not match else None
        if title:
            if chunk:
                sections.append(_section_row(heading, start, ''.join(chunk)))
            heading, start, chunk = title.group(2), number, []
        chunk.append(line)
    if chunk:
        sections.append(_section_row(heading, start, ''.join(chunk)))
    return sections


def _utf8_size(text: str) -> int:
    try:
        return len(text.encode('utf-8'))
    except UnicodeError:
        raise AiError('model returned text that is not valid UTF-8', 'ai-bad-output', 502) from None


def _reference(item, existing: set) -> dict:
    if not isinstance(item, dict):
        raise AiError('model returned invalid reference', 'ai-bad-output', 502)
    path, text = item.get('path'), item.get('text')
    if (not isinstance(path, str) or len(path) > 200 or not _REF_PATH.fullmatch(path)
            or path.casefold() in existing or not isinstance(text, str) or _utf8_size(text) > MAX_REF_BYTES):
        raise AiError('model reference has an unsafe path, collision, or oversized text', 'ai-bad-output', 502)
    existing.add(path.casefold())
    tokens, method = count_tokens(text)
    return {'path': path, 'text': text, 'tokens': tokens, 'method': method}


def _references(answer: dict, files: dict, directories: dict) -> list[dict]:
    raw = answer.get('references')
    if not isinstance(raw, list) or len(raw) > MAX_REFS:
        raise AiError('model returned invalid references', 'ai-bad-output', 502)
    existing = {p.casefold() for p in files} | {p.casefold() for p in directories}
    if ('references' in {p.casefold() for p in files}
            or any(p.casefold() == 'references' and p != 'references' for p in directories)):
        raise AiError('references path conflicts with an existing entry', 'ai-input')
    return [_reference(item, existing) for item in raw]


def _visible_markdown(body: str) -> str:
    body = re.sub(r'<!--.*?(?:-->|\Z)', '', body, flags=re.DOTALL)
    visible, fence = [], None
    for line in body.splitlines():
        match = _FENCE.match(line)
        if match:
            marker, tail = match.groups()
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not tail.strip():
                fence = None
            continue
        if fence is None:
            visible.append(re.sub(r'`+[^`]*`+', '', line))
    return '\n'.join(visible)


def _has_reference_link(body: str, path: str) -> bool:
    pattern = r'(?<!!)\[[^]\n]+\]\((?:' + re.escape(path) + r'|<' + re.escape(path) + r'>)\)'
    return bool(re.search(pattern, _visible_markdown(body)))


def _proposal(answer, files: dict, directories: dict) -> dict:
    if not isinstance(answer, dict) or not isinstance(answer.get('body'), str):
        raise AiError('model returned no proposed body', 'ai-bad-output', 502)
    body = answer['body']
    if not body.strip() or len(body) > MAX_BODY or _utf8_size(body) > MAX_SOURCE_FILE_BYTES:
        raise AiError('model returned an empty or oversized body', 'ai-bad-output', 502)
    refs = _references(answer, files, directories)
    for ref in refs:
        if not _has_reference_link(body, ref['path']):
            raise AiError('the proposed body must link each new reference', 'ai-bad-output', 502)
    return {'body': body, 'references': refs}


def _counts(original: str, modified: str | None, refs: list[dict]) -> dict:
    before, method = count_tokens(original)
    after, after_method = count_tokens(modified) if modified is not None else (None, None)
    added = sum(r['tokens'] for r in refs)
    return {'primary_before': before, 'primary_after': after, 'reference_added': added if modified is not None else None,
            'total_before': before, 'total_after': after + added if after is not None else None,
            'method': method, 'primary_after_method': after_method, 'primary_saved': before - after if after is not None else None,
            'total_saved': before - after - added if after is not None else None,
            'scope': 'primary document plus newly added references; existing companions excluded'}


def _write_candidate(root: Path, files: dict, directories: dict) -> None:
    for directory in sorted(directories, key=lambda p: (p.count('/'), p)):
        if directory:
            (root / directory).mkdir(parents=True, exist_ok=True)
    for path, (raw, mode) in files.items():
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as handle:
            handle.write(raw)
        destination.chmod(mode)
    for directory in sorted(directories, key=lambda p: (-p.count('/'), p)):
        (root / directory).chmod(directories[directory])


def _stage(data_dir: Path, target: dict, original: dict, directories: dict, digest: str,
           primary: str, prefix: str, proposal: dict) -> dict:
    files = dict(original)
    files[primary] = ((prefix + proposal['body']).encode('utf-8'), original[primary][1])
    for ref in proposal['references']:
        files[ref['path']] = (ref['text'].encode('utf-8'), 0o600)
    with tempfile.TemporaryDirectory(prefix='skillsmgr-concise-') as temp:
        candidate = Path(temp) / 'candidate'
        candidate.mkdir(mode=0o700)
        _write_candidate(candidate, files, directories)
        review = source_update.prepare_local_update(data_dir, target['name'], target['scope'], candidate,
                                                    target_path=target['physical_path'],
                                                    source_value='skillsmgr-ai-concise')
    try:
        current_files, current_directories, current_digest = _capture(Path(target['physical_path']))
        if (review.get('current_hash') != digest or current_digest != digest
                or current_files != original or current_directories != directories):
            raise AiError('skill changed while the proposal was being prepared', 'ai-conflict', 409)
    except Exception:
        if review.get('review_id'):
            source_update.cancel_update_review(data_dir, review['review_id'])
        raise
    return review


def concise_skill(data_dir: Path, payload: dict) -> dict:
    """Estimate or stage a proposed skill rewrite without changing the live tree."""
    payload = payload if isinstance(payload, dict) else {}
    name, scope = payload.get('name'), payload.get('scope')
    try:
        target = source_update._resolve_target(Path(data_dir), name, scope, payload.get('target_path'))
    except (source_update.SourceUpdateError, ValueError, TypeError) as exc:
        raise AiError(str(exc), 'ai-input') from None
    files, directories, digest = _capture(Path(target['physical_path']))
    primary, prefix, body = _document(files, target['disabled'], name)
    original_text = files[primary][0].decode('utf-8')
    estimate = bool(payload.get('estimate'))
    run = AiRun(data_dir, 'concise', estimate_only=estimate)
    request = ('Shorten this skill and propose reference files.\n' + untrusted_block('skill', prefix + body)
               + '\nReturn JSON: {"body":"...","references":[{"path":"references/name.md","text":"..."}]}')
    answer = run.ask_json(_SYSTEM, request, max_output=4000)
    result = {'kind': 'concise', 'scope': scope, 'name': name, 'status': 'estimate',
              'sections': _sections(body), 'tokens': _counts(original_text, None, []),
              'proposal': None, 'review': None,
              'egress': [f'The full primary skill document for {name} goes to the configured model.'],
              'run': run.label()}
    if not estimate:
        proposal = _proposal(answer, files, directories)
        review = _stage(data_dir, target, files, directories, digest, primary, prefix, proposal)
        status = {'pending': 'review-required', 'blocked': 'blocked', 'no-change': 'no-change'}.get(
            review.get('review_state'), 'blocked')
        result.update({'status': status, 'proposal': proposal, 'review': review,
                       'tokens': _counts(original_text, prefix + proposal['body'], proposal['references'])})
        try:
            result['run_id'] = _save_run(data_dir, result)
        except Exception:
            if review.get('review_id'):
                source_update.cancel_update_review(data_dir, review['review_id'])
            raise
    return result
