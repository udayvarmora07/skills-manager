#!/usr/bin/env python3
"""Smoke test for the skillsmgr.webapp REST API against a temp data dir.

Starts WebAppServer on an ephemeral port and exercises every endpoint
the web UI uses. Run: python3 smoke_web.py
"""
import json
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer

tmp = tempfile.mkdtemp(prefix="skillsmgr-web-")
try:
    store = Store(data_dir=tmp)
    store.init_db()
    server = WebAppServer(store, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = server.url

    def req(method, path, body=None, ctype="application/json"):
        data = None
        headers = {}
        if body is not None:
            if isinstance(body, bytes):
                data = body
            else:
                data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = ctype
        r = Request(base + path, data=data, headers=headers, method=method)
        with urlopen(r) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            return resp.status, (json.loads(raw) if "json" in ct else raw)

    print("== static ==")
    status, html = req("GET", "/")
    assert status == 200 and b"Skills Manager" in html
    status, css = req("GET", "/styles.css")
    assert status == 200 and b"--accent" in css
    status, js = req("GET", "/app.js")
    assert status == 200 and b"createApp" in js
    status, vue = req("GET", "/static/vendor/vue.global.prod.js")
    assert status == 200 and b"Vue" in vue
    print("static ok")

    print("== skills CRUD ==")
    status, rows = req("GET", "/api/skills")
    assert status == 200 and rows == []
    status, created = req("POST", "/api/skills", {
        "name": "demo-tool",
        "description": "A demo skill for the web smoke test",
        "category": "utility",
        "version": "1.0.0",
        "license": "MIT",
        "body": "# Demo\n\nBody text.",
    })
    assert status == 201 and created["name"] == "demo-tool"
    status, rows = req("GET", "/api/skills")
    assert len(rows) == 1 and rows[0]["name"] == "demo-tool"
    status, record = req("GET", "/api/skills/demo-tool")
    assert record["description"] == "A demo skill for the web smoke test"
    assert "Body text." in record["body"]
    status, raw = req("GET", "/api/skills/demo-tool/raw")
    assert b"Body text." in raw
    status, edited = req("PATCH", "/api/skills/demo-tool", {"description": "Updated description"})
    assert edited["changed"] is True
    status, edited2 = req("PATCH", "/api/skills/demo-tool", {"description": "Updated description"})
    assert edited2["changed"] is False
    print("CRUD ok")

    print("== search ==")
    status, hits = req("GET", "/api/search?q=demo")
    assert any(h["name"] == "demo-tool" for h in hits)
    status, none = req("GET", "/api/search?q=zzz-nope")
    assert none == []
    print("search ok")

    print("== validate ==")
    status, vres = req("POST", "/api/validate", {"name": "demo-tool"})
    assert status == 200 and vres["valid"] is True
    print("validate ok")

    print("== disable/enable ==")
    status, _ = req("POST", "/api/skills/demo-tool/disable")
    assert status == 200
    status, record = req("GET", "/api/skills/demo-tool")
    assert record["disabled"] == 1
    status, _ = req("POST", "/api/skills/demo-tool/enable")
    status, record = req("GET", "/api/skills/demo-tool")
    assert record["disabled"] == 0
    print("toggle ok")

    print("== stats / doctor / history ==")
    status, stats = req("GET", "/api/stats")
    assert stats["total"] == 1 and stats["active"] == 1
    status, doc = req("GET", "/api/doctor")
    assert doc["ok"] is True
    status, doc_all = req("GET", "/api/doctor?scope=all")
    assert status == 200 and "duplicates" in doc_all and "scopes" in doc_all
    assert isinstance(doc_all["duplicates"], list)  # env may have real agent dirs
    print("misc ok")
    status, hist = req("GET", "/api/history?limit=20")
    assert len(hist) >= 3  # create, edit, disable/enable...
    print("misc ok")

    print("== templates ==")
    status, tpl = req("POST", "/api/templates", {"name": "starter", "body": "# Starter"})
    assert status == 201 and tpl["name"] == "starter"
    status, tpls = req("GET", "/api/templates")
    assert "starter" in tpls["templates"]
    print("templates ok")

    print("== export/import archive ==")
    status, blob = req("GET", "/api/export")
    assert status == 200 and blob[:2] == b"\x1f\x8b"  # gzip magic
    tmp2 = tempfile.mkdtemp(prefix="skillsmgr-web2-")
    store2 = Store(data_dir=tmp2)
    store2.init_db()
    server2 = WebAppServer(store2, "127.0.0.1", 0)
    t2 = threading.Thread(target=server2.serve_forever, daemon=True)
    t2.start()
    r = Request(
        server2.url + "api/import?filename=export.tar.gz",
        data=blob,
        method="PUT",
    )
    with urlopen(r) as resp:
        imported = json.loads(resp.read())
    assert imported["imported"] == ["demo-tool"], imported
    assert len(store2.list()) == 1
    server2.shutdown()
    shutil.rmtree(tmp2, ignore_errors=True)
    print("export/import ok")

    print("== trash / restore / purge ==")
    status, _ = req("DELETE", "/api/skills/demo-tool?purge=0")
    status, trash = req("GET", "/api/trash")
    assert len(trash) == 1 and trash[0]["name"] == "demo-tool"
    status, rows = req("GET", "/api/skills")
    assert rows == []  # trashed skill no longer listed
    status, restored = req("POST", "/api/trash/demo-tool")
    assert status == 200
    status, rows = req("GET", "/api/skills")
    assert len(rows) == 1
    status, _ = req("DELETE", "/api/skills/demo-tool?purge=0")
    status, purged = req("POST", "/api/trash/purge")
    assert purged["purged"] == ["demo-tool"]
    status, trash = req("GET", "/api/trash")
    assert trash == []
    print("trash ok")

    print("== rebuild / resync ==")
    status, rb = req("POST", "/api/rebuild")
    assert rb["added"] == 0
    status, rs = req("POST", "/api/resync")
    assert rs["added"] == 0
    print("index ops ok")

    print("== multipart folder upload ==")
    boundary = "smokeboundary"
    files = [
        ("skills/skill-folder/SKILL.md",
         b"---\nname: skill-folder\ndescription: uploaded skill\n---\n# folder\n"),
    ]
    body = b""
    for name, content in files:
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    status, up = req("PUT", "/api/import", body, ctype=f"multipart/form-data; boundary={boundary}")
    assert status == 200 and up["imported"] == ["skill-folder"], up
    status, rows = req("GET", "/api/skills")
    assert any(r["name"] == "skill-folder" for r in rows)
    print("upload ok")

    print("== error paths ==")
    from urllib.error import HTTPError

    try:
        req("GET", "/api/skills/missing-skill")
        raise AssertionError("should have raised 404")
    except HTTPError as exc:
        assert exc.code == 404, exc.code
    try:
        req("POST", "/api/skills", {"name": "x"})
        raise AssertionError("should have raised 400")
    except HTTPError as exc:
        assert exc.code == 400, exc.code
    try:
        req("GET", "/api/nonexistent")
        raise AssertionError("should have raised 404")
    except HTTPError as exc:
        assert exc.code == 404, exc.code
    print("errors ok")

    print("\nALL WEB SMOKE TESTS PASSED")
finally:
    server.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
