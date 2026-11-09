"""Draft and simulate routing for an unsaved skill; model output is untrusted."""
from __future__ import annotations

import re
import os
from pathlib import Path

from . import scopes, validator
from .loader import scan_dir
from .ai import AiError, AiRun, untrusted_block
from .ai_skills import (MAX_LISTED, _egress, _generation_request, _GEN_SYSTEM, _hidden,
                        _items, _listing_text, _route, _save_run, normalize_prompts)

MAX_BRIEF = 10_000
MAX_DRAFT = 64_000
MAX_SAMPLE = 10
_DRAFT_SYSTEM = ('You draft a skill for an AI coding agent from the user brief. '
                 'Return JSON only with a skill field containing complete SKILL.md text. '
                 'Include only name and description frontmatter, followed by instructions. '
                 'Use a lowercase hyphenated name, description at most 1024 characters, '
                 'and at most 500 body lines.')


def _inputs(payload: dict) -> tuple[str, str, str | None]:
    scope, brief, name = payload.get('scope'), payload.get('brief'), payload.get('name')
    if not isinstance(scope, str) or not scope or scope == 'all':
        raise AiError('choose one agent scope', 'ai-input')
    if not isinstance(brief, str) or not brief.strip() or len(brief) > MAX_BRIEF:
        raise AiError(f'brief must be 1 to {MAX_BRIEF} characters', 'ai-input')
    if name not in (None, ''):
        try:
            validator.validate_skill_name(name if isinstance(name, str) else '')
        except ValueError as exc:
            raise AiError(str(exc), 'ai-input') from None
    return scope, brief.strip(), name or None


def _scope_listing(scope: str) -> tuple[dict, set, Path]:
    try:
        info = scopes.scope_by_id(scope)
        if info is None or not info.writable:
            raise ValueError('unknown or non-writable scope')
        records = scan_dir(info.base, recursive=info.recursive, include_husks=True,
                           link_roots=scopes._peer_link_roots(info))
    except Exception as exc:
        raise AiError(f'cannot read scope {scope!r}: {exc}', 'ai-input') from None
    names = {r.get('name') for r in records if isinstance(r.get('name'), str)}
    entries, seen = [], set()
    for record in records:
        name = record.get('name')
        if not isinstance(name, str) or name in seen or _hidden(record):
            continue
        seen.add(name)
        entries.append({'name': name, 'description': _listing_text(record)[:1536]})
    if len(entries) >= MAX_LISTED:
        raise AiError('scope has no room for a draft in the routing test', 'ai-input')
    listing = {'scope': scope, 'entries': entries, 'hidden': len(records) - len(entries),
               'over_cap': [], 'chars': sum(len(e['name']) + len(e['description']) + 4 for e in entries)}
    return listing, names, info.base


def _sample(listing: dict, brief: str) -> list[str]:
    words = set(re.findall(r'[a-z0-9]+', brief.lower()))
    ranked = sorted(listing['entries'], key=lambda e: (-len(words & set(re.findall(
        r'[a-z0-9]+', (e['name'] + ' ' + e['description']).lower()))), e['name']))
    return [e['name'] for e in ranked[:MAX_SAMPLE]]


def _placeholder_name(names: set) -> str:
    for i in range(len(names) + 1):
        suffix = str(i)
        candidate = 'x' * (validator.MAX_NAME - len(suffix)) + suffix
        if candidate not in names:
            return candidate
    raise AiError('cannot construct a draft estimate', 'ai-input')


def _draft_request(brief: str, name: str | None) -> str:
    return ('Create a skill from this brief:\n' + untrusted_block('brief', brief)
            + ('\nRequired name: ' + untrusted_block('name', name) if name else '')
            + '\nReturn {"skill":"<complete SKILL.md>"}.')


def _entry_exists(root: Path, name: str) -> bool:
    try:
        validator.validate_skill_name(name)
    except ValueError:
        return False
    return os.path.lexists(root / name)


def _validate_draft(answer, requested: str | None, names: set, root: Path) -> tuple[dict, dict]:
    text = answer.get('skill') if isinstance(answer, dict) else None
    if not isinstance(text, str) or len(text) > MAX_DRAFT:
        raise AiError('the model did not return a bounded skill document', 'ai-bad-output', 502)
    result = validator.validate_text(text)
    name, description = result.data.get('name'), result.data.get('description')
    try:
        validator.validate_skill_name(name if isinstance(name, str) else '')
    except ValueError as exc:
        result.add('error', str(exc), 'name')
    if requested and name != requested:
        result.add('error', 'draft name does not match the requested name', 'name')
    if isinstance(name, str) and (name in names or _entry_exists(root, name)):
        result.add('error', 'a skill with this name already exists in this scope', 'name')
    if len(result.body.splitlines()) > 500:
        result.add('error', 'body must be at most 500 lines', 'body')
    if set(result.data) - {'name', 'description'}:
        result.add('error', 'draft frontmatter may contain only name and description', 'frontmatter')
    issues = [{'level': issue.level, 'message': issue.message, 'key': issue.key} for issue in result.issues]
    return ({'text': text, 'name': name, 'description': description, 'body': result.body},
            {'valid': result.valid, 'issues': issues})


def _generate(run: AiRun, listing: dict, targets: list[str], near: int) -> list[dict]:
    if not targets:
        return []
    user = _generation_request(listing, targets, 3, near)
    answer = run.ask_json(_GEN_SYSTEM, user, max_output=min(4000, 120 * (3 * len(targets) + near) + 200))
    if run.estimate_only:
        return ([{'text': 'x ' * 300, 'expected': n} for n in targets for _ in range(3)]
                + [{'text': 'x ' * 300, 'expected': None} for _ in range(near)])
    out, counts = [], {}
    for item in _items(answer, 'prompts'):
        target, text = item.get('skill'), item.get('text')
        if target in targets and isinstance(text, str) and text.strip() and counts.get(target, 0) < 3:
            out.append({'text': text[:600], 'expected': target})
            counts[target] = counts.get(target, 0) + 1
    for item in _items(answer, 'near_misses')[:near]:
        text = item.get('text')
        if isinstance(text, str) and text.strip():
            out.append({'text': text[:600], 'expected': None})
    return out


def _steals(prompts: list[dict], before: dict, after: dict, name: str) -> list[dict]:
    stolen = {}
    for prompt in prompts:
        old, new = before.get(prompt['id']), after.get(prompt['id'])
        if old and new and old[0] == prompt['expected'] and new[0] == name:
            row = stolen.setdefault(prompt['expected'], {'name': prompt['expected'], 'count': 0, 'prompts': []})
            row['count'] += 1
            row['prompts'].append(prompt['text'])
    return list(stolen.values())


def _answer_rate(prompts: list[dict], answers: dict, name: str) -> float | None:
    choices = [answers[p['id']][0] for p in prompts if p['id'] in answers]
    return sum(v == name for v in choices) / len(choices) if choices else None


def _evidence_counts(prompts: list[dict], before: dict, after: dict, sampled: list[str]) -> tuple[int, int]:
    missing = sum(p['id'] not in after for p in prompts) + sum(
        p['id'] not in before for p in prompts if p['expected'] in sampled)
    invalid = sum(value[0] == '?invalid' for value in list(before.values()) + list(after.values()))
    return missing, invalid


def _verification(prompts: list[dict], before: dict, after: dict, name: str, sampled: list[str], total: int) -> dict:
    own = [p for p in prompts if p['expected'] == name]
    near = [p for p in prompts if p['expected'] is None]
    missing, invalid = _evidence_counts(prompts, before, after, sampled)
    complete = bool(own and near) and all(any(p['expected'] == n for p in prompts) for n in sampled)
    return {'draft_hit_rate': _answer_rate(own, after, name),
            'near_miss_false_trigger_rate': _answer_rate(near, after, name),
            'stolen': _steals([p for p in prompts if p['expected'] in sampled], before, after, name),
            'existing_skills_sampled': len(sampled), 'existing_skills_total': total,
            'missing_answers': missing, 'invalid_answers': invalid,
            'complete': complete and not missing and not invalid,
            'prompts': [{'text': p['text'], 'expected': p['expected'],
                         'before': before.get(p['id'], (None,))[0],
                         'after': after.get(p['id'], (None,))[0]} for p in prompts]}


def _evaluate(run: AiRun, listing: dict, draft: dict, sampled: list[str]) -> dict:
    name = draft['name']
    augmented = {**listing, 'entries': listing['entries'] + [{'name': name, 'description': draft['description']}]}
    own = _generate(run, augmented, [name], 3)
    existing = _generate(run, listing, sampled, 0)
    raw = own + existing
    if not raw:
        return _verification([], {}, {}, name, sampled, len(listing['entries']))
    prompts = normalize_prompts(raw, {e['name'] for e in augmented['entries']})
    old_prompts = [p for p in prompts if p['expected'] in sampled]
    before = _route(run, listing, old_prompts, {}, 0)
    after = _route(run, augmented, prompts, {}, 0)
    return _verification(prompts, before, after, name, sampled, len(listing['entries']))


def draft_skill(data_dir: Path, payload: dict) -> dict:
    """Produce and verify a draft without writing to any skill directory."""
    payload = payload if isinstance(payload, dict) else {}
    scope, brief, requested = _inputs(payload)
    listing, names, root = _scope_listing(scope)
    if requested and (requested in names or _entry_exists(root, requested)):
        raise AiError('a skill with this name already exists in this scope', 'ai-input', 409)
    estimate = bool(payload.get('estimate'))
    run = AiRun(data_dir, 'draft-skill', estimate_only=estimate)
    answer = run.ask_json(_DRAFT_SYSTEM, _draft_request(brief, requested), max_output=4000)
    sampled = _sample(listing, brief)
    result = {'kind': 'draft-skill', 'scope': scope, 'status': 'estimate', 'draft': None,
              'validation': None, 'verification': None,
              'egress': _egress(listing, 3 * (len(sampled) + 2),
                                ['Your brief and generated draft go to the model for drafting and verification.'], run)}
    if estimate:
        draft = {'name': requested or _placeholder_name(names), 'description': 'x ' * 512}
        _evaluate(run, listing, draft, sampled)
    else:
        draft, validation = _validate_draft(answer, requested, names, root)
        result.update({'draft': draft, 'validation': validation, 'status': 'invalid'})
        if validation['valid']:
            verification = _evaluate(run, listing, draft, sampled)
            result['verification'] = verification
            result['status'] = 'verified' if verification['complete'] else 'unverified'
    result['run'] = run.label()
    if not estimate:
        result['run_id'] = _save_run(data_dir, result)
    return result
