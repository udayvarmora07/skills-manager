import os, random, sys, json, shutil
from pathlib import Path
total = int(sys.argv[1]); root = Path(sys.argv[2])
if root.exists(): shutil.rmtree(root)
root.mkdir(parents=True); os.chmod(root, 0o700)
home = root/"home"; home.mkdir(); os.chmod(home,0o700)
data = root/"data"; data.mkdir(); os.chmod(data,0o700)
scopes = [".claude/skills", ".codex/skills", ".config/opencode/skills", ".agents/skills"]
for s in scopes: (home/s).mkdir(parents=True)
rnd = random.Random(42)
V = "review plan debug deploy refactor test lint format audit migrate profile document scaffold triage summarize query monitor design extract validate".split()
N = "api database frontend schema pipeline cache auth queue report ticket release config docker kubernetes sql git cli ui email logs metrics".split()
LOREM = ("Use this skill when the task involves the topic described above. Always read the relevant files first, "
 "then propose a plan before editing. Prefer small, reversible changes and run the project's checks after each step. "
 "Report what was verified and what was assumed. Never delete data without confirmation.").split(". ")
def body(size):
    out = ["# Instructions\n"]; n = 0
    i = 0
    while n < size:
        if i % 7 == 0: line = f"\n## Step {i//7+1}\n"
        elif i % 5 == 0: line = f"- {rnd.choice(LOREM)}.\n"
        elif i % 11 == 0: line = "```bash\nrun --check --verbose\n```\n"
        else: line = rnd.choice(LOREM) + ". " + rnd.choice(LOREM) + ".\n"
        out.append(line); n += len(line); i += 1
    return "".join(out)
def doc(name, desc, b, cat): return f"---\nname: {name}\ndescription: {desc}\ncategory: {cat}\nversion: 1.{rnd.randint(0,9)}.0\n---\n\n{b}"
CATS = ["testing","devops","docs","data","security","frontend"]
made = 0; k = 0; stats = dict(malformed=0, disabled=0, differing_groups=0, logical=0)
while made < total:
    k += 1
    name = f"{rnd.choice(V)}-{rnd.choice(N)}-{k:05d}"
    c = rnd.choices([1,2,3,4],[40,25,20,15])[0]; c = min(c, total-made)
    sel = rnd.sample(scopes, c)
    size = rnd.randint(1000, 6000); b = body(size); desc = f"{name.replace('-',' ').capitalize()} helper for agents"
    cat = rnd.choice(CATS); stats["logical"] += 1
    differ = c > 1 and rnd.random() < 0.12
    if differ: stats["differing_groups"] += 1
    for idx, s in enumerate(sel):
        d = home/s/name; d.mkdir()
        text = doc(name, desc, b + ("\n## Local tweak\nExtra agent-specific note.\n" if differ and idx == 0 else ""), cat)
        r = rnd.random(); fn = "SKILL.md"
        if r < 0.005: (d/fn).write_bytes(text.encode()[:80] + b"\xff\xfe\xfa broken " + text.encode()[80:200]); stats["malformed"] += 1
        elif r < 0.01: (d/fn).write_text(f"---\nname: {name}\ndescription: never closed\n\n{b[:300]}"); stats["malformed"] += 1
        else:
            if r < 0.013: fn = "SKILL.md.disabled"; stats["disabled"] += 1
            (d/fn).write_text(text)
        made += 1
stats["instances"] = made
print(json.dumps(stats))
