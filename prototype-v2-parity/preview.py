"""Serve only the design prototype and its existing public fonts/Vue assets."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
PREFIX = "/prototype-v2-parity/"
ASSETS = {
    PREFIX + name: (ROOT / "prototype-v2-parity" / name, mime)
    for name, mime in (
        ("index.html", "text/html; charset=utf-8"),
        ("app.js", "text/javascript; charset=utf-8"),
        ("styles.css", "text/css; charset=utf-8"),
    )
}
ASSETS["/skillsmgr/webui/static/vendor/vue.global.prod.js"] = (
    ROOT / "skillsmgr/webui/static/vendor/vue.global.prod.js",
    "text/javascript; charset=utf-8",
)
ASSETS["/skillsmgr/webui/domain.js"] = (
    ROOT / "skillsmgr/webui/domain.js",
    "text/javascript; charset=utf-8",
)
ASSETS["/skillsmgr/webui/v2/model.js"] = (
    ROOT / "skillsmgr/webui/v2/model.js",
    "text/javascript; charset=utf-8",
)
for family, names in (
    ("v2/fonts", ("PlusJakartaSans-var.woff2", "Newsreader-var.woff2")),
    ("static/fonts", ("IBMPlexMono-400-latin.woff2", "IBMPlexMono-500-latin.woff2", "IBMPlexMono-600-latin.woff2")),
):
    for name in names:
        ASSETS[f"/skillsmgr/webui/{family}/{name}"] = (
            ROOT / "skillsmgr/webui" / family / name,
            "font/woff2",
        )


class PreviewHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def do_GET(self):
        authority = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != authority:
            self.send_error(403)
            return
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.send_error(403)
            return
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + authority:
            self.send_error(403)
            return
        path = urlsplit(self.path).path
        if path in ("/", PREFIX.rstrip("/")):
            self.send_response(302)
            self.send_header("Location", PREFIX)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == PREFIX:
            path = PREFIX + "index.html"
        if path not in ASSETS:
            self.send_error(404)
            return
        asset, content_type = ASSETS[path]
        try:
            content = asset.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), PreviewHandler)
    print("No authentication: localhost binding is the only security boundary. Do not forward, tunnel or publish this port.", flush=True)
    print(f"http://127.0.0.1:{server.server_port}{PREFIX}#/tools", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
