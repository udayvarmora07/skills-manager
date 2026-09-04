"""Token and context-size estimation for SKILL.md.

Stdlib-only, with optional tiktoken for exact counts.

Heuristic fallback is chars/4 (27.8% avg error vs tiktoken 0.2% — see
Markaicode benchmark). We keep it as fallback so CLI stays stdlib-only
(locked constraint). When tiktoken is installed, we use it for exact BPE
counts without extra API calls.

Context windows (tokens) — updated 2026-08-15 from latest vendor docs:
  Claude 1M (Opus 5 / Sonnet 5 / Fable 5; Haiku 200k), GPT-5.6 1.05M
  (ChatGPT GPT-5 400k; GPT-4o 128k legacy), Gemini 1M / 2M.
  Percentages are shown vs selected window; budget bar colors:
  <50% green, 50-80% yellow, >80% red.
"""

from __future__ import annotations

WINDOWS: dict[str, int] = {
    "claude": 1_000_000,
    "claude-haiku": 200_000,
    "gpt-4o": 128_000,
    "gpt-5": 400_000,
    "gpt-5.6": 1_050_000,
    "gemini": 1_000_000,
    "gemini-2m": 2_000_000,
}

DEFAULT_WINDOW = "claude"

try:
    import tiktoken as _tiktoken  # type: ignore

    _ENC = _tiktoken.get_encoding("cl100k_base")

    def _exact_tokens(text: str) -> int | None:
        try:
            return len(_ENC.encode(text))
        except Exception:
            return None

    _HAS_TIKTOKEN = True
except Exception:
    _HAS_TIKTOKEN = False

    def _exact_tokens(text: str) -> int | None:  # type: ignore[no-redef]
        return None


def count_tokens(text: str) -> tuple[int, str]:
    """Return (tokens, method) for text.

    method is "tiktoken" when exact, else "heuristic".
    """
    if not text:
        return 0, "heuristic"
    exact = _exact_tokens(text)
    if exact is not None:
        return exact, "tiktoken"
    # Heuristic: chars / 4, at least 1 for non-empty.
    # Slightly better than naive: max(chars/4, words*1.3) blended.
    chars = len(text)
    words = len(text.split())
    h1 = chars / 4.0
    h2 = words * 1.3
    # Weighted average reduces error on code-heavy bodies.
    heuristic = int(round((h1 * 0.7) + (h2 * 0.3)))
    return max(1, heuristic), "heuristic"


def estimate(text: str, window: str = DEFAULT_WINDOW) -> dict:
    """Full estimate for one SKILL.md text."""
    tokens, method = count_tokens(text)
    chars = len(text)
    lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0) if text else 0
    win = WINDOWS.get(window, WINDOWS[DEFAULT_WINDOW])
    pct = (tokens / win * 100) if win else 0
    return {
        "tokens": tokens,
        "chars": chars,
        "lines": lines,
        "method": method,
        "window": window,
        "window_tokens": win,
        "pct_window": round(pct, 2),
        "has_tiktoken": _HAS_TIKTOKEN,
    }


def estimate_skill_text(description: str, body: str, extra_frontmatter: str = "") -> dict:
    """Estimate for a skill from its parts (description + body + frontmatter snippet)."""
    combined = "\n".join(p for p in (extra_frontmatter, description or "", body or "") if p)
    return estimate(combined)


def aggregate(skills: list[dict]) -> dict:
    """Aggregate token stats over a list of skill dicts that have 'tokens'."""
    if not skills:
        return {"total_tokens": 0, "avg_tokens": 0, "max_tokens": 0, "count": 0, "largest": []}
    toks = [(s.get("tokens", 0), s.get("name", "")) for s in skills]
    total = sum(t for t, _ in toks)
    avg = total // len(toks) if toks else 0
    mx = max(t for t, _ in toks) if toks else 0
    largest = sorted(skills, key=lambda s: s.get("tokens", 0), reverse=True)[:5]
    largest = [{"name": s.get("name"), "tokens": s.get("tokens", 0), "scope": s.get("scope")} for s in largest]
    return {
        "total_tokens": total,
        "avg_tokens": avg,
        "max_tokens": mx,
        "count": len(skills),
        "largest": largest,
        "has_tiktoken": _HAS_TIKTOKEN,
    }


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)
