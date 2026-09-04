"""Wildcard-aware search ranking over skill records.

``*`` matches any run of characters and ``?`` matches a single character;
all other characters are matched literally. Records are scored 0-100 by
where the match lands (exact name, name prefix, name substring, then
description/category), so users can type ``k8s-*`` or ``terraform?``.
"""

from __future__ import annotations

import re

__all__ = ["compile_wildcard", "score_match", "rank_results"]


def compile_wildcard(pattern: str) -> re.Pattern:
    """Compile a wildcard pattern into a case-insensitive regex."""
    parts = []
    for ch in pattern:
        if ch == "*":
            parts.append(".*")
        elif ch == "?":
            parts.append(".")
        else:
            parts.append(re.escape(ch))
    return re.compile("".join(parts), re.IGNORECASE)


def score_match(record: dict, rx: re.Pattern, term: str) -> int:
    """Return a 0-100 relevance score for *record* against *rx*."""
    name = record.get("name", "")
    description = record.get("description", "")
    category = record.get("category", "")
    term_l = term.lower()
    name_l = name.lower()
    if name_l == term_l:
        return 100
    if rx.fullmatch(name):
        return 90
    if name_l.startswith(term_l):
        return 80
    if rx.search(name):
        return 70
    if term_l in name_l:
        return 60
    if rx.search(description):
        return 40
    if rx.search(category):
        return 30
    if term_l in description.lower():
        return 25
    return 0


def rank_results(records: list[dict], term: str) -> list[tuple[dict, int]]:
    """Filter and sort *records* by relevance to *term* (best first)."""
    rx = compile_wildcard(term)
    scored = [(rec, score_match(rec, rx, term)) for rec in records]
    scored = [(rec, s) for rec, s in scored if s > 0]
    scored.sort(key=lambda pair: (-pair[1], pair[0].get("name", "").lower()))
    return scored
