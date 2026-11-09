#!/usr/bin/env python3
"""Compare a saved trigger simulation with explicit, bounded Claude CLI observations.

Dry-run is the default. This is a development tool, not a sandbox or a product CLI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_STDOUT_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
MAX_CASES = 20
MAX_PROMPTS = 500
MAX_PROMPT_CHARS = 600
_NAME = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
_LABEL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$')
_ACTUAL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$')
_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')


class FidelityError(ValueError):
    """A safe, non-sensitive input or execution error."""


def _read_json(path: str) -> tuple[dict, str]:
    try:
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT_BYTES:
                raise ValueError
            chunks, length = [], 0
            while length <= MAX_INPUT_BYTES:
                chunk = os.read(fd, min(65536, MAX_INPUT_BYTES + 1 - length))
                if not chunk:
                    break
                chunks.append(chunk)
                length += len(chunk)
            if length > MAX_INPUT_BYTES:
                raise ValueError
            raw = b''.join(chunks)
        finally:
            os.close(fd)
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return value, hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, UnicodeError, TypeError, RecursionError):
        raise FidelityError('input file is inaccessible, oversized, or invalid JSON') from None


def _key(row: object) -> tuple[str, str | None]:
    if not isinstance(row, dict):
        raise FidelityError('prompt entry is invalid')
    text, expected = row.get('text'), row.get('expected')
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_PROMPT_CHARS:
        raise FidelityError('prompt text is invalid or oversized')
    try:
        text.encode('utf-8')
    except UnicodeError:
        raise FidelityError('prompt text is invalid or oversized') from None
    if expected is not None and (not isinstance(expected, str) or not _NAME.fullmatch(expected) or len(expected) > 64):
        raise FidelityError('expected skill name is invalid')
    return text, expected


def _valid_choice(name, count) -> bool:
    return (isinstance(name, str) and (name == '(none)' or (len(name) <= 64 and bool(_NAME.fullmatch(name))))
            and type(count) is int and count > 0)


def _choice(row: dict, repeats: int) -> str | None:
    choices = row.get('choices')
    if (not isinstance(choices, dict) or not choices or type(row.get('answered')) is not int
            or row.get('answered') != repeats):
        raise FidelityError('simulation contains incomplete choices')
    for name, count in choices.items():
        if not _valid_choice(name, count):
            raise FidelityError('simulation contains invalid choices')
    if sum(choices.values()) != repeats:
        raise FidelityError('simulation contains incomplete choices')
    largest = max(choices.values())
    winners = [name for name, count in choices.items() if count == largest]
    if len(winners) != 1:
        raise FidelityError('simulation contains tied choices')
    return None if winners[0] == '(none)' else winners[0]


def _valid_provenance(model, provider, started) -> bool:
    return (isinstance(model, str) and bool(_LABEL.fullmatch(model))
            and isinstance(provider, str) and bool(_LABEL.fullmatch(provider))
            and isinstance(started, str) and bool(_DATE.fullmatch(started)))


def _simulation_meta(run: dict) -> dict:
    meta = run.get('run')
    if (run.get('kind') != 'trigger-test' or run.get('scope') != 'claude-code'
            or run.get('prompt_source') != 'saved' or run.get('status') not in (None, 'complete')
            or not isinstance(meta, dict) or meta.get('estimate_only') is not False
            or type(run.get('missing_answers')) is not int or run.get('missing_answers') != 0
            or type(run.get('invalid_answers')) is not int or run.get('invalid_answers') != 0):
        raise FidelityError('simulation must be a complete saved-prompt Claude Code run')
    model, provider, started = meta.get('model'), meta.get('provider'), meta.get('started')
    if not _valid_provenance(model, provider, started):
        raise FidelityError('simulation provenance is invalid')
    return {'scope': 'claude-code', 'model': model, 'provider': provider, 'started': started,
            'listing_snapshot_unavailable': True}


def _joined(prompt_set: dict, run: dict) -> tuple[list[dict], dict]:
    meta = _simulation_meta(run)
    if prompt_set.get('scope') != 'claude-code':
        raise FidelityError('prompt-set scope must be claude-code')
    prompts, rows, repeats = prompt_set.get('prompts'), run.get('prompts'), run.get('repeats')
    if (not isinstance(prompts, list) or not 1 <= len(prompts) <= MAX_PROMPTS
            or not isinstance(rows, list) or len(rows) != len(prompts)
            or isinstance(repeats, bool) or not isinstance(repeats, int) or not 1 <= repeats <= 5):
        raise FidelityError('prompt set and simulation do not match')
    expected = [_key(item) for item in prompts]
    if len(set(expected)) != len(expected):
        raise FidelityError('prompt set contains duplicate entries')
    scored = {}
    for row in rows:
        key = _key(row)
        if key in scored:
            raise FidelityError('simulation contains duplicate entries')
        scored[key] = _choice(row, repeats)
    if set(expected) != set(scored):
        raise FidelityError('prompt set and simulation do not match')
    return [{'text': text, 'expected': name, 'simulated': scored[(text, name)]} for text, name in expected], meta


def _failure(reason: str) -> dict:
    return {'status': 'inconclusive', 'reason': reason, 'actual': None, 'observed_skills': [],
            'multiple': False, 'observed_model': None}


def _event_content(event: dict) -> list:
    message = event.get('message')
    if not isinstance(message, dict) or not isinstance(message.get('content'), list):
        raise ValueError
    return message['content']


def _collect_call(block: dict, calls: list) -> None:
    identifier, tool = block.get('id'), block.get('name')
    if not isinstance(identifier, str) or not identifier or tool not in ('Skill', 'EndConversation'):
        raise ValueError
    details = block.get('input')
    if not isinstance(details, dict):
        raise ValueError
    name = details.get('skill') if tool == 'Skill' else None
    if tool == 'Skill' and (not isinstance(name, str) or not _ACTUAL.fullmatch(name)):
        raise ValueError
    calls.append((identifier, tool, name))


def _collect_result(block: dict, results: dict) -> None:
    identifier = block.get('tool_use_id')
    error = block.get('is_error', False)
    if not isinstance(identifier, str) or not identifier or type(error) is not bool or identifier in results:
        raise ValueError
    results[identifier] = not error


def _collect_tools(event: dict, calls: list, results: dict) -> None:
    for block in _event_content(event):
        if not isinstance(block, dict):
            raise ValueError
        kind = block.get('type')
        if kind == 'tool_use':
            if event.get('type') != 'assistant':
                raise ValueError
            _collect_call(block, calls)
        elif kind == 'tool_result':
            if event.get('type') != 'user':
                raise ValueError
            _collect_result(block, results)
        elif kind == 'text':
            if not isinstance(block.get('text'), str):
                raise ValueError
        elif kind not in ('thinking', 'redacted_thinking'):
            raise ValueError


def _stream_event(event: dict, calls: list, results: dict) -> bool:
    kind = event.get('type')
    if event.get('error'):
        raise ValueError
    if kind in ('assistant', 'user'):
        message = event.get('message')
        if isinstance(message, dict) and message.get('stop_reason') in (
                'max_tokens', 'model_context_window_exceeded', 'pause_turn'):
            raise ValueError
        _collect_tools(event, calls, results)
    elif kind == 'result':
        if event.get('subtype') != 'success' or event.get('is_error') is not False:
            raise ValueError
        return True
    elif kind not in ('system', 'rate_limit_event', 'auth_status'):
        raise ValueError
    return False


def _assistant_evidence(event: dict) -> bool:
    if event.get('type') != 'assistant':
        return False
    return any(isinstance(block, dict) and (
        (block.get('type') == 'text' and isinstance(block.get('text'), str))
        or (block.get('type') == 'tool_use' and block.get('name') in ('Skill', 'EndConversation')))
        for block in _event_content(event))


def _model_label(event: dict) -> str | None:
    label = event.get('model')
    if (event.get('type') == 'system' and event.get('subtype') == 'init' and isinstance(label, str)
            and _LABEL.fullmatch(label) and not label.lower().startswith('sk-')):
        return label
    return None


def parse_stream(raw: bytes) -> dict:
    """Accept only completed successful Skill tool calls from the JSON event stream."""
    calls, results, terminal, observed_model, assistant = [], {}, False, None, False
    try:
        for line in raw.splitlines():
            event = json.loads(line)
            if not isinstance(event, dict) or terminal:
                raise ValueError
            observed_model = _model_label(event) or observed_model
            assistant = _assistant_evidence(event) or assistant
            terminal = _stream_event(event, calls, results)
        ids = [identifier for identifier, _, _ in calls]
        if not terminal or not assistant or len(ids) != len(set(ids)) or set(ids) != set(results) or not all(results.values()):
            raise ValueError
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return _failure('incomplete-or-invalid-stream')
    observed = [name for _, tool, name in calls if tool == 'Skill']
    return {'status': 'conclusive', 'reason': None, 'actual': observed[0] if observed else None,
            'observed_skills': observed, 'multiple': len(observed) > 1, 'observed_model': observed_model}


def _stop(process) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    finally:
        process.wait()


def _command(args) -> list[str]:
    command = [args.agent_bin, '-p', '--output-format', 'stream-json', '--verbose',
               '--tools', 'Skill', '--allowedTools', 'Skill', '--strict-mcp-config',
               '--mcp-config', '{"mcpServers":{}}', '--disallowedTools', 'mcp__*',
               '--no-session-persistence', '--max-turns', '2', '--max-budget-usd', str(args.max_budget_usd),
               '--permission-prompts', 'none']
    if args.model:
        command.extend(['--model', args.model])
    return command


def _drain(process, timeout: float) -> tuple[bytes, str | None]:
    deadline = time.monotonic() + timeout
    output, stderr_size = bytearray(), 0
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
        selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return b'', 'timeout'
            for key, _ in selector.select(min(remaining, 0.25)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                elif key.data == 'stdout':
                    output.extend(chunk)
                    if len(output) > MAX_STDOUT_BYTES:
                        return b'', 'output-limit'
                else:
                    stderr_size += len(chunk)
                    if stderr_size > MAX_STDERR_BYTES:
                        return b'', 'output-limit'
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return b'', 'timeout'
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            return b'', 'timeout'
    return bytes(output), None


def _invoke(args, prompt: str) -> dict:
    try:
        process = subprocess.Popen(_command(args), cwd=args.cwd, shell=False, start_new_session=True,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, ValueError):
        return _failure('agent-unavailable')
    try:
        try:
            process.stdin.write(prompt.encode('utf-8'))
            process.stdin.close()
            raw, error = _drain(process, args.timeout)
        except (OSError, UnicodeError, ValueError):
            return _failure('agent-io-error')
        if error:
            return _failure(error)
        if process.returncode != 0:
            return _failure('agent-failed')
        return parse_stream(raw)
    finally:
        _stop(process)
        for pipe in (process.stdin, process.stdout, process.stderr):
            pipe.close()


def _arguments(argv):
    parser = argparse.ArgumentParser(description='Compare a saved simulation with Claude Code (dry-run by default).')
    parser.add_argument('--prompt-set', required=True)
    parser.add_argument('--simulation', required=True)
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--max-budget-usd', type=float, default=0.10)
    parser.add_argument('--agent-bin', default='claude')
    parser.add_argument('--model')
    parser.add_argument('--cwd')
    parser.add_argument('--run-agent', action='store_true')
    parser.add_argument('--maintainer-present', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= MAX_CASES or not math.isfinite(args.timeout) or not 0 < args.timeout <= 120:
        raise FidelityError('limit or timeout is outside permitted bounds')
    if not math.isfinite(args.max_budget_usd) or not 0 < args.max_budget_usd <= 1:
        raise FidelityError('per-call budget must be positive and at most $1')
    if args.model is not None and not _LABEL.fullmatch(args.model):
        raise FidelityError('model label is invalid')
    if args.run_agent != args.maintainer_present:
        raise FidelityError('execution requires both --run-agent and --maintainer-present')
    if args.run_agent and (os.name != 'posix' or not args.cwd or not Path(args.cwd).is_dir()):
        raise FidelityError('execution requires POSIX process groups and an existing --cwd')
    return args


def _group_agreement(name: str, cases: list[dict]) -> dict:
    group = [case for case in cases if (case['expected'] or '(none)') == name]
    conclusive = [case for case in group if case['status'] == 'conclusive']
    wins = sum(case['agree'] for case in conclusive)
    return {'skill': name, 'requested': len(group), 'matched': wins, 'compared': len(conclusive),
            'inconclusive': sum(case['status'] == 'inconclusive' for case in group),
            'rate': wins / len(conclusive) if conclusive else None}


def _agreement(cases: list[dict]) -> dict:
    conclusive = [case for case in cases if case['status'] == 'conclusive']
    matched = sum(case['agree'] for case in conclusive)
    names = sorted({case['expected'] or '(none)' for case in cases})
    return {'metric': 'first-successful-skill', 'matched': matched, 'compared': len(conclusive),
            'rate': matched / len(conclusive) if conclusive else None,
            'by_expected': [_group_agreement(name, cases) for name in names]}


def execute(argv: list[str]) -> dict:
    args = _arguments(argv)
    prompt_set, prompt_hash = _read_json(args.prompt_set)
    simulation, run_hash = _read_json(args.simulation)
    joined, meta = _joined(prompt_set, simulation)
    cases = []
    for item in joined[:args.limit]:
        observation = _invoke(args, item['text']) if args.run_agent else {
            'status': 'not-run', 'reason': None, 'actual': None, 'observed_skills': [],
            'multiple': False, 'observed_model': None}
        case = {'prompt_sha256': hashlib.sha256(item['text'].encode('utf-8')).hexdigest(),
                'expected': item['expected'], 'simulated': item['simulated'], **observation}
        case['agree'] = (case['actual'] == case['simulated']) if case['status'] == 'conclusive' else None
        cases.append(case)
    agreement = _agreement(cases)
    return {'schema': 1, 'status': 'complete' if args.run_agent else 'dry-run',
            'simulation': {**meta, 'run_sha256': run_hash, 'prompt_set_sha256': prompt_hash},
            'policy': {'max_budget_usd_per_call': args.max_budget_usd, 'timeout_seconds': args.timeout,
                       'max_turns': 2, 'agent_model_requested': args.model,
                       'nominal_total_budget_usd': round(len(cases) * args.max_budget_usd, 4),
                       'notice': 'Budget is approximate and can be exceeded; this is not a sandbox. '
                                 'Hooks, configuration and dynamic skills may run. '
                                 'Saved listing equivalence and default-agent fidelity are unverified.'},
            'coverage': {'available': len(joined), 'requested': len(cases),
                         'unselected': len(joined) - len(cases), 'conclusive': agreement['compared'],
                         'inconclusive': sum(case['status'] == 'inconclusive' for case in cases),
                         'multiple': sum(case['multiple'] for case in cases)},
            'agreement': agreement, 'cases': cases}


def main() -> int:
    try:
        report = execute(sys.argv[1:])
    except FidelityError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
