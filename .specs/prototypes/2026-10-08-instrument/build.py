#!/usr/bin/env python3
"""Emit every prototype screen from one shell.

The shell (sidebar, topbar, status bar) is identical across screens in the
real product, so it is written once here. Editing the shell then edits twelve
screens, and a screenshot can never disagree with another about what the
navigation looks like.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "screens"

NAV = [
    ("group", "Workspace"),
    ("item", "overview", "Overview",
     "M3 12h4l2.5-7 4 14 2.5-7h5", None),
    ("item", "skills", "Library", "M4 5h16M4 5v14h16V5M4 10h16M9 5v14", ("ok", "638")),
    ("item", "quality", "Quality",
     "M12 3l7 3.5v5c0 4.4-3 7.6-7 8.5-4-0.9-7-4.1-7-8.5v-5zM9 12l2 2 4-4", None),
    ("group", "Operations"),
    ("item", "install", "Install",
     "M12 3v10m0 0l4-4m-4 4l-4-4M4 19h16", None),
    ("item", "recovery", "Recovery", "M3 12a9 9 0 1 0 3-6.7M3 4v5h5", None),
    ("item", "profiles", "Profiles",
     "M4 5h16v14H4zM4 10h16M9 5v14", None),
    ("item", "workspaces", "Workspaces",
     "M3 7l9-4 9 4-9 4zM3 12l9 4 9-4M3 17l9 4 9-4", None),
]

SCOPES = [
    ("Opencode", "515", "96.8", "over", "121%"),
    ("Codex", "480", "95.2", "over", "119%"),
    ("Gemini", "450", "88.8", "over", "111%"),
    ("Claude Code", "329", "4", "", "5%"),
    ("Agents", "123", "32.8", "", "41%"),
    ("Command Code", "60", "4", "", "5%"),
    ("Global", "5", "0.8", "", "1%"),
]


def nav(active: str) -> str:
    out = []
    for kind, *rest in NAV:
        if kind == "group":
            out.append(f'        <div class="nav-label">{rest[0]}</div>')
            continue
        _key, label, path, pip = rest
        cur = ' aria-current="page"' if _key == active else ""
        badge = ""
        if pip:
            tone, txt = pip
            badge = f'<span class="nav-pip {tone}">{txt}</span>'
        out.append(
            f'        <a class="nav-item" href="#"{cur}>\n'
            f'          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="{path}"/></svg>\n'
            f'          <span class="label">{label}</span>{badge}\n'
            f'        </a>'
        )
    return "\n".join(out)


def scope_ledger(active: str = "Opencode") -> str:
    out = ['        <div class="nav-label">Scope roots <span class="nav-count">7 detected</span></div>']
    for name, count, width, tone, pct in SCOPES:
        cur = ' aria-current="true"' if name == active else ""
        cls = f"scope-bar {tone}".strip()
        pcls = f"scope-pct {tone}".strip()
        out.append(
            f'        <button class="scope-row"{cur}>\n'
            f'          <span class="scope-name">{name} <span class="meta">{count}</span></span>\n'
            f'          <span class="{pcls}">{pct}</span>\n'
            f'          <span class="{cls}"><i style="width:{width}%"></i></span>\n'
            f'        </button>'
        )
    return "\n".join(out)


SHELL = """<!DOCTYPE html>
<html lang="en" data-theme="__THEME__">
<head>
<meta charset="utf-8">
<title>__TITLE__ — Instrument</title>
<link rel="stylesheet" href="../assets/tokens.css">
<link rel="stylesheet" href="../assets/proto.css">
</head>
<body>
<div class="app">

  <aside class="side">
    <div class="brand">
      <div class="brand-mark">
        <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M4 12h10M4 17h7"/></svg>
      </div>
      <div>
        <div class="brand-name">Skills Manager</div>
        <div class="brand-sub">this machine only</div>
      </div>
    </div>

    <div class="side-search">
      <div class="search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
        <span class="ph">Search skills and paths…</span>
        <span class="kbd">/</span>
      </div>
    </div>

    <div class="side-scroll">
      <div class="nav-group">
__NAV__
      </div>

      <div class="nav-group scope-ledger">
__SCOPES__
      </div>

      <div class="nav-group">
        <div class="nav-label">Preferences</div>
        <a class="nav-item" href="#">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 9 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8V9a1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 9a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/></svg>
          <span class="label">Settings</span>
        </a>
      </div>
    </div>

    <div style="padding:0 var(--s4) var(--s4)">
      <div class="budget-picker">
        <div class="budget-head"><span>Context window</span><span class="mono">1,000,000</span></div>
        <select class="select" style="height:28px;font-size:12px">
          <option>Claude 1M</option><option>Claude Haiku 200k</option><option>Gemini 2M</option>
        </select>
      </div>
    </div>
  </aside>

  <main class="main">
    <header class="topbar">
__TOPBAR__
    </header>
__BODY__
  </main>

  <footer class="statusbar">
    <span>638 logical skills · 1,163 physical copies · 4 attention items</span>
    <span class="spacer"></span>
    <span class="mark warn"><i></i>index in sync</span>
    <span>data stays on this machine · loopback only</span>
  </footer>
</div>
__OVERLAY__
</body>
</html>
"""


def topbar(title, meta="", actions=()):
    parts = ['<span class="crumb-title">%s</span>' % title]
    if meta:
        parts.append('<span class="crumb-meta">%s</span>' % meta)
    acts = "".join(actions)
    return (
        '      <div class="crumb">%s</div>\n'
        '      <div class="topbar-actions">%s</div>' % ("".join(parts), acts)
    )


def btn(label, kind="secondary", icon=None):
    ic = ""
    if icon:
        ic = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="%s"/></svg>' % icon)
    return f'<button class="btn btn-{kind}">{ic}{label}</button>'


IC_GEAR = "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8"
IC_PLUS = "M12 5v14M5 12h14"
IC_CHART = "M4 19V9m5 10V5m5 14v-7m5 7V7"


def build(name, active, tb_title, tb_meta, actions, body, overlay=""):
    html = (
        SHELL.replace("__NAV__", nav(active))
        .replace("__SCOPES__", scope_ledger())
        .replace("__TOPBAR__", topbar(tb_title, tb_meta, actions))
        .replace("__BODY__", body)
        .replace("__OVERLAY__", overlay)
        .replace("__TITLE__", tb_title)
        .replace("__THEME__", "light")
    )
    (OUT / name).write_text(html)
    return name


if __name__ == "__main__":
    import screens_data
    made = []
    for spec in screens_data.SCREENS:
        made.append(build(**spec))
    print("\n".join(made))
    sys.exit(0)