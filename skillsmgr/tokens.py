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


def window_name(window: str | None) -> str:
    """A known context window name (blank means the default), else ``ValueError``."""
    name = (window or "").strip() or DEFAULT_WINDOW
    if name not in WINDOWS:
        raise ValueError(f"unknown context window {name!r}; choose one of: {', '.join(sorted(WINDOWS))}")
    return name


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


def aggregate(skills: list[dict], window: str = DEFAULT_WINDOW) -> dict:
    """Aggregate token stats over skill dicts that carry ``tokens``."""
    window_tokens = WINDOWS[window]
    total = sum(s.get("tokens", 0) for s in skills)
    largest = sorted(skills, key=lambda s: s.get("tokens", 0), reverse=True)[:5]
    return {
        "total_tokens": total,
        "avg_tokens": total // len(skills) if skills else 0,
        "max_tokens": max((s.get("tokens", 0) for s in skills), default=0),
        "count": len(skills),
        "largest": [{"name": s.get("name"), "tokens": s.get("tokens", 0), "scope": s.get("scope")} for s in largest],
        "has_tiktoken": _HAS_TIKTOKEN,
        "window": window,
        "window_tokens": window_tokens,
        "pct_window": round(total / window_tokens * 100, 1),
    }


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)
