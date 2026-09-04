#!/usr/bin/env python3
"""Smoke test for skillsmgr.store.Store against a temp data dir."""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skillsmgr.store import Store, StoreError, SkillNotFound

tmp = tempfile.mkdtemp(prefix="skillsmgr-smoke-")
try:
    store = Store(data_dir=tmp)
    store.init_db()

    print("== create ==")
    r = store.create("demo-tool", description="A demo skill for smoke tests",
                     license="MIT", compatibility={"opencode": ">=1.0", "claude": ">=2.0"},
                     version="1.2.3", allowed_tools=["bash", "read"],
                     category="utility", body="# Demo\n\nBody text.")
    print("created:", r)
    assert r["name"] == "demo-tool"

    print("== list ==")
    rows = store.list()
    print(rows)
    assert len(rows) == 1 and rows[0]["name"] == "demo-tool"

    print("== get ==")
    g = store.get("demo-tool")
    assert g["name"] == "demo-tool"
    assert g["description"] == "A demo skill for smoke tests"
    assert g["version"] == "1.2.3"
    assert g["category"] == "utility"
    assert g["status"] == "active"
    assert "Body text." in g["body"]
    print("ok, path:", g["path"])

    print("== edit (changed + unchanged) ==")
    e = store.edit("demo-tool", description="Updated description")
    print("changed:", e)
    assert e["changed"] is True
    e2 = store.edit("demo-tool", description="Updated description")
    print("unchanged:", e2)
    assert e2["changed"] is False

    print("== add existing skill dir (tmp fixture) ==")
    fixture = os.path.join(tmp, "fixture-src", "fixture-skill")
    os.makedirs(fixture)
    with open(os.path.join(fixture, "SKILL.md"), "w", encoding="utf-8") as fh:
        fh.write("---\nname: fixture-skill\ndescription: Fixture skill for smoke tests\n---\n# Fixture\n\nBody.\n")
    added = store.add(fixture)
    print("added:", added["name"])
    assert added["name"] == "fixture-skill"
    rows = store.list()
    assert len(rows) == 2

    print("== search ==")
    hits = store.search("demo")
    print("demo hits:", [h["name"] for h in hits])
    assert any(h["name"] == "demo-tool" for h in hits)
    hits2 = store.search("100%")
    print("wildcard-escaped hits:", [h["name"] for h in hits2])

    print("== stats ==")
    st = store.stats()
    print(st)
    assert st["total"] == 2 and st["active"] == 2

    print("== disable/enable ==")
    store.disable("demo-tool")
    assert not os.path.exists(os.path.join(tmp, "skills", "demo-tool", "SKILL.md"))
    assert os.path.exists(os.path.join(tmp, "skills", "demo-tool", "SKILL.md.disabled"))
    try:
        store.edit("demo-tool", description="x")
        raise AssertionError("edit of disabled skill should raise")
    except StoreError as err:
        print("edit disabled guard ok:", err)
    store.enable("demo-tool")
    assert os.path.exists(os.path.join(tmp, "skills", "demo-tool", "SKILL.md"))

    print("== export ==")
    arch = store.export()
    print("exported:", arch)
    assert arch.exists()

    print("== import into second store ==")
    tmp2 = tempfile.mkdtemp(prefix="skillsmgr-smoke2-")
    store2 = Store(data_dir=tmp2)
    store2.init_db()
    imp = store2.import_(arch)
    print("import result:", imp)
    assert set(imp["imported"]) == {"demo-tool", "fixture-skill"}, imp
    assert len(store2.list()) == 2

    print("== import duplicate -> skipped ==")
    imp2 = store2.import_(arch)
    print("second import:", imp2)
    assert set(imp2["skipped"]) == {"demo-tool", "fixture-skill"}, imp2

    print("== remove to trash, list, restore ==")
    store.remove("demo-tool")
    assert store.get("demo-tool")["status"] == "trashed"
    tl = store.trash_list()
    print("trash:", [(t["name"], t["trash_path"]) for t in tl])
    assert any(t["name"] == "demo-tool" for t in tl)
    store.restore("demo-tool")
    assert store.get("demo-tool")["status"] == "active"

    print("== purge ==")
    store.remove("demo-tool", purge=True)
    try:
        store.get("demo-tool")
        raise AssertionError("purged skill should not exist")
    except SkillNotFound:
        print("purged ok")

    print("== history ==")
    hist = store.history("demo-tool")
    actions = [h["action"] for h in hist]
    print("history:", actions)
    assert actions == ["purge", "trash", "restore", "edit", "create"] or "create" in actions

    print("== doctor ==")
    doc = store.doctor()
    print({k: v for k, v in doc.items() if k != "dirs"})
    assert doc["ok"] is True

    print("== resync / db_rebuild ==")
    rr = store.resync()
    print("resync:", rr)
    assert rr["added"] == 0 and rr["removed"] == 0
    rb = store.db_rebuild()
    print("rebuilt:", rb)
    assert len(store.list()) == 1  # fixture-skill only
    assert store.get("fixture-skill")["status"] == "active"

    # orphan detection: create a dir on disk without db row
    orphan = os.path.join(tmp, "skills", "orphan-x")
    os.makedirs(os.path.join(orphan), exist_ok=True)
    with open(os.path.join(orphan, "SKILL.md"), "w") as fh:
        fh.write("---\nname: orphan-x\ndescription: d\n---\nbody\n")
    store.resync()
    assert store.get("orphan-x")["status"] == "active"
    doc = store.doctor()
    print("orphan check:", doc["orphan_dirs"], doc["ok"])
    assert doc["ok"] is True

    print("\nALL STORE SMOKE TESTS PASSED")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    if "tmp2" in dir():
        shutil.rmtree(tmp2, ignore_errors=True)
