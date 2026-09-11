#!/usr/bin/env python3
"""Optional, unbundled desktop window for the existing local web UI (issue #9).

The recorded verdict on issue #9 REJECTS wrapping the UI in ``pywebview`` (or any
third-party webview): that needs a third-party install plus OS webview runtimes
and would add native failure modes to a product whose reason for having a web UI
is that it is dependency-free. The same verdict allows exactly one artefact — "an
unbundled loopback-only launcher script is the most that should ever exist, never
replacing the dependency-free browser path".

This is that script, and nothing more:

* it does **not** ship in the wheel (``pyproject.toml`` packages only
  ``skillsmgr*``), so ``skills-mgr webui`` stays the only supported entry point;
* it adds **no** runtime dependency: it drives a Chromium-family browser the user
  already has via ``--app=<url>``, which renders the page in a chromeless window
  that behaves like a desktop app;
* it falls back to the plain default browser when no Chromium-family browser
  exists, so the canonical path is never worse for having this script;
* it refuses any non-loopback host, exactly like ``WebAppServer``, and it binds
  and links the *same* host so the ``Host`` header always matches the server's
  allowlist (see issue #14 F-2).

Usage::

    python3 desktop_launcher.py [--port 8765] [--data-dir DIR] [--plain] [--print-only]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

#: Chromium-family launchers, in preference order. ``--app=`` is what turns the
#: page into a chromeless window; browsers without it fall back to a normal tab
#: through :mod:`webbrowser`.
CHROMIUM_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
    "microsoft-edge-stable",
    "brave-browser",
    "vivaldi",
)

LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")

DEFAULT_PORT = 8765

EXIT_OK = 0
EXIT_USAGE = 2


class LauncherError(RuntimeError):
    """A clean, user-facing launcher failure (never a traceback)."""


def validate_host(host: str) -> str:
    """Return ``host`` when it is loopback, else raise :class:`LauncherError`."""
    if host not in LOOPBACK_HOSTS:
        raise LauncherError(
            f"refusing to bind {host!r}: the launcher is loopback-only "
            f"(choose one of {', '.join(LOOPBACK_HOSTS)})"
        )
    return host


def find_chromium(which=shutil.which) -> str | None:
    """Return the first installed Chromium-family launcher, or ``None``."""
    for name in CHROMIUM_CANDIDATES:
        path = which(name)
        if path:
            return path
    return None


def window_command(browser: str, url: str) -> list[str]:
    """The chromeless-window argv for a Chromium-family browser."""
    return [browser, f"--app={url}", "--new-window"]


def describe(browser: str | None, url: str, *, plain: bool = False) -> str:
    """One honest line about what will happen."""
    if browser and not plain:
        return f"desktop window: {Path(browser).name} --app={url}"
    if browser:
        return f"default browser (--plain): {url}"
    return (
        "no Chromium-family browser found; falling back to the default browser "
        f"at {url}"
    )


def open_target(url: str, *, browser: str | None, plain: bool,
                popen=subprocess.Popen, opener=webbrowser.open) -> str:
    """Open ``url`` in a chromeless window when possible, else the default browser.

    Returns ``"window"`` or ``"browser"`` so callers (and tests) can tell which
    path ran. A browser that fails to start is not fatal: the server keeps
    serving and the printed URL stays usable.
    """
    if browser and not plain:
        try:
            popen(
                window_command(browser, url),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return "window"
        except OSError:
            pass
    opener(url)
    return "browser"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="desktop_launcher.py",
        description="Open the Skills Manager web UI in a chromeless desktop window "
                    "(optional and unbundled; `skills-mgr webui` remains canonical).",
    )
    parser.add_argument("--host", default="127.0.0.1",
                        help="loopback host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"port to bind (default {DEFAULT_PORT})")
    parser.add_argument("--data-dir", default=None, help="override the data directory")
    parser.add_argument("--plain", action="store_true",
                        help="use the default browser instead of an app window")
    parser.add_argument("--print-only", action="store_true",
                        help="print what would happen and exit without serving")
    return parser


def run(argv: list[str] | None = None, *, server_factory=None,
        which=shutil.which, popen=subprocess.Popen, opener=webbrowser.open,
        out=print) -> int:
    """Serve the web UI on loopback and open it in a window (or the browser)."""
    args = build_parser().parse_args(argv)
    try:
        host = validate_host(args.host)
    except LauncherError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    url = f"http://{host}:{args.port}/"
    browser = find_chromium(which)
    out(describe(browser, url, plain=args.plain))
    if args.print_only:
        return EXIT_OK

    if server_factory is None:
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        store = Store(data_dir=Path(args.data_dir) if args.data_dir else None)
        server_factory = lambda: WebAppServer(store, host, args.port)  # noqa: E731

    server = server_factory()
    try:
        out(f"serving {url}")
        out("press Ctrl+C to stop")
        threading.Timer(
            0.4,
            lambda: open_target(url, browser=browser, plain=args.plain,
                                popen=popen, opener=opener),
        ).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            out("stopped")
    finally:
        server.shutdown()
    return EXIT_OK


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
