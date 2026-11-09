"""Documented frontmatter key support per consumer (read-only, no I/O).

The table is copied from ``docs/34-agent-skill-loading-research-2026-11-07.md``
("Documented frontmatter keys"), whose rows were read from each vendor's own
page on 2026-11-07. A key a consumer does not document is reported as "no
documented effect" -- which is deliberately different from "rejected": only the
claude.ai upload and Skills API surfaces are documented to reject unknown keys.
Nothing here reads the filesystem, writes, or makes a network request.
"""

from __future__ import annotations

#: Keys with a documented behavioural effect in Claude Code.  The hygiene
#: finding only reports one of these when it appears in an instance's top-level
#: frontmatter and the reading consumer does not document it.  Unknown keys that
#: no agent documents are not reported, because there is no effect to lose.
BEHAVIOURAL_KEYS = (
    "disable-model-invocation",
    "user-invocable",
    "allowed-tools",
    "disallowed-tools",
    "model",
    "effort",
    "context",
    "agent",
    "background",
    "hooks",
    "paths",
    "shell",
    "arguments",
    "argument-hint",
    "when_to_use",
)

DOCUMENTED_KEYS: dict[str, dict] = {
    "claude-code": {
        "label": "Claude Code",
        "source": "https://code.claude.com/docs/en/skills",
        "keys": (
            "name",
            "description",
            "when_to_use",
            "argument-hint",
            "arguments",
            "disable-model-invocation",
            "user-invocable",
            "allowed-tools",
            "disallowed-tools",
            "model",
            "effort",
            "context",
            "agent",
            "background",
            "hooks",
            "paths",
            "shell",
            "metadata",
            "license",
            "compatibility",
        ),
        "unknown_keys": "ignores unrecognized keys without reporting an error",
    },
    "claude.ai-api": {
        "label": "Claude.ai / Skills API",
        "source": "https://code.claude.com/docs/en/skills",
        "keys": (
            "name",
            "description",
            "license",
            "compatibility",
            "metadata",
            "allowed-tools",
        ),
        "unknown_keys": "Other keys cause a hard error",
    },
    "codex": {
        "label": "Codex",
        "source": "https://learn.chatgpt.com/docs/build-skills",
        "keys": ("name", "description"),
        "note": "implicit invocation is set in agents/openai.yaml -> "
        "policy.allow_implicit_invocation",
    },
    "gemini": {
        "label": "Gemini CLI",
        "source": "https://geminicli.com/docs/cli/skills/",
        "keys": ("name", "description"),
    },
    "opencode": {
        "label": "OpenCode",
        "source": "https://opencode.ai/docs/skills/",
        "keys": (
            "name",
            "description",
            "metadata.opencode/autoinvoke",
            "disable-model-invocation",
            "license",
            "compatibility",
        ),
        "note": "license/compatibility are accepted but not interpreted",
    },
    "cline": {
        "label": "Cline",
        "source": "https://docs.cline.bot/features/skills",
        "keys": ("name", "description"),
    },
    "kiro": {
        "label": "Kiro",
        "source": "https://kiro.dev/docs/skills/",
        "keys": ("name", "description", "license", "compatibility", "metadata"),
    },
    "amp": {
        "label": "Amp",
        "source": "https://ampcode.com/docs/customize/skills",
        "keys": ("name", "description", "mcpServers"),
        "note": "the page states its list is incomplete",
    },
    "roo": {
        "label": "Roo Code",
        "source": "https://roocodeinc.github.io/Roo-Code/features/skills",
        "keys": ("name", "description"),
    },
    "zed": {
        "label": "Zed",
        "source": "https://zed.dev/docs/ai/skills",
        "keys": ("name", "description", "disable-model-invocation"),
        "note": "other specification fields are planned but not yet supported",
    },
}


def known_consumers() -> tuple[str, ...]:
    """Return the consumers with a documented key list."""
    return tuple(sorted(DOCUMENTED_KEYS))


def label(consumer: str) -> str:
    """Human-readable label for *consumer* (the id itself when unknown)."""
    entry = DOCUMENTED_KEYS.get(consumer)
    return entry["label"] if entry else consumer


def source(consumer: str) -> str | None:
    """Primary source URL for *consumer*, or ``None`` when unrecorded."""
    entry = DOCUMENTED_KEYS.get(consumer)
    return entry["source"] if entry else None


def documented_keys(consumer: str) -> tuple[str, ...]:
    """Keys the consumer's own page documents (empty when unrecorded)."""
    entry = DOCUMENTED_KEYS.get(consumer)
    return entry["keys"] if entry else ()


def documents(consumer: str, key: str) -> bool:
    """True when *consumer* documents *key*.

    A dotted entry such as ``metadata.opencode/autoinvoke`` documents its
    top-level key (``metadata``), because that is the key a document carries.
    """
    for documented in documented_keys(consumer):
        if documented == key or documented.split(".", 1)[0] == key:
            return True
    return False


__all__ = [
    "BEHAVIOURAL_KEYS",
    "DOCUMENTED_KEYS",
    "documented_keys",
    "documents",
    "known_consumers",
    "label",
    "source",
]
