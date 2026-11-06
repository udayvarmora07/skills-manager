# 10,000-skill rendering and performance exercise (skills-manager.ui-final, branch ui/prototype-final)

Setup: isolated HOME and data roots (mode 700) under `$SCRATCH/perf10k/`, fixtures of 100, 1,000 and 10,000 instances over `.claude`, `.codex`, `.config/opencode`, `.agents` (1-6 KB SKILL.md; 10k fixture = 4,757 logical skills, 331 groups with one differing copy, 96 malformed, 43 disabled). Headless Chrome 1440x900, sandbox on, fresh browser per run, 3 runs each, median (min-max). Browser capped at 1.5 GB (cgroup). Host was under memory pressure (swap full), so absolute times are pessimistic. No repo file modified, no git commands. Raw data: `results.jsonl`, `api.txt`; scripts: `gen.py`, `measure.js`, `agg.py`.

Findings: no crash, no console error, no failed request, no main-thread stall over 5 s (worst 1.76 s, classic at 10k).

Ready = navigation start to heading plus first list item visible. Classic ready = landing, then click Library, then first row. "Stall" = longest gap in a 50 ms heartbeat. Longtasks = n / total ms / max ms. Heap is post-GC.

| size | UI/screen | ready ms | /api/skills ms | heap MB | DOM nodes | longtasks | stall ms |
|---|---|---|---|---|---|---|---|
| 100 | v2 home | 261 (249-295) | 114 | 3.5 | 226 | 1/70/64 | 72 |
| 100 | v2 skills | 241 (223-249) | 100 | 3.7 | 700 | 1/54/54 | 83 |
| 100 | v2 skill | 238 (221-241) | 100 | 3.5 | 374 | 1/54/54 | 80 |
| 100 | v2 map | 231 (224-297) | 103 | 3.5 | 189 | 1/57/57 | 84 |
| 100 | v2 inbox | 365 (233-613) | 172 | 3.5 | 300 | 1/61/61 | 155 |
| 100 | classic library | 389 (358-674) | 101 | 5.9 | 702 | 1/113/113 | 212 |
| 1,000 | v2 home | 864 (838-1048) | 698 | 8.4 | 226 | 1/54/54 | 89 |
| 1,000 | v2 skills | 939 (929-945) | 749 | 9.8 | 5,216 | 3/164/58 | 94 |
| 1,000 | v2 skill | 1297 (1031-1439) | 836 | 8.6 | 875 | 2/131/73 | 115 |
| 1,000 | v2 map | 1251 (1183-1594) | 1054 | 8.5 | 250 | 1/87/87 | 118 |
| 1,000 | v2 inbox | 1181 (877-1240) | 922 | 8.3 | 282 | 1/74/74 | 87 |
| 1,000 | classic library | 1144 (1026-1509) | 749 | 14.0 | 5,793 | 3/310/158 | 332 |
| 10,000 | v2 home | 9201 (9184-9571) | 8834 | 56.2 | 226 | 4/427/131 | 247 |
| 10,000 | v2 skills | 11642 (9761-11995) | 11268 | 58.4 | 7,348 | 5/483/139 | 219 |
| 10,000 | v2 skill | 10141 (10048-10195) | 9701 | 56.4 | 867 | 4/454/127 | 229 |
| 10,000 | v2 map | 10306 (9459-13066) | 9728 | 56.3 | 318 | 4/435/127 | 197 |
| 10,000 | v2 inbox | 12507 (11669-14663) | 12111 | 56.2 | 282 | 4/404/137 | 262 |
| 10,000 | classic library | 6025 (4322-11727) | 3760 (2131-10088) | 100.4 | 55,765 | 7/2444/869 | 1484 |

Classic 10k: landing 588 ms, then Library switch 5394 ms (3638-11337). Payload (identical for all screens): 550 KB / 5.75 MB / 56.7 MB. Browser process-tree PSS at 10k: 535-622 MB (v2), 747 MB (classic); 395-447 MB at 1k. Server peak RSS: 35 / 86 / 332 MB.

Interactions on the list screen (ms, median of 3; search "audit" set as one input event, then cleared):

| size | UI | search | clear | worst key, typed | filter on | filter off |
|---|---|---|---|---|---|---|
| 1,000 | v2 | 14 | 87 | 20 | 31 | 43 |
| 1,000 | classic | 257 | 145 | 76 | 25 | 118 |
| 10,000 | v2 | 18 | 184 | 42 | 79 | 64 |
| 10,000 | classic | 941 | 1408 | 562 | 269 | 1978 |

(100 skills: all under 25 ms except classic search at 243 ms, which is its 220 ms debounce.)

## Top 3 bottlenecks

1. **Payload and server time dominate v2.** `GET /api/skills?scope=all` is 56.7 MB at 10k and takes 4.4 s on its own via curl (7.6 s on the first call). In v2, ready minus API is only 0.37-0.44 s. In-page split at 10k: JSON.parse 96-133 ms, `Model.build` 75-172 ms. `body` is 63.8% of the bytes, and without it the payload is 20.5 MB (36%). Each `/api/skills` and `/api/scopes` call alone: 4.4 s and 3.7 s; fired together, as `refresh()` does, 9.4 s and 8.1 s (curl). So the two requests roughly add instead of overlapping.
2. **Classic renders every row.** 10k instances give 55,765 DOM nodes, 100 MB heap, 2.4 s of longtasks (max 869 ms), and typing costs 0.5 s a key. v2 caps each group at 48 cards, giving 7,348 nodes and 58 MB, with a 42 ms worst key.
3. **v2 retains the full records.** Heap grows 3.5 → 8.4 → 56 MB with fixture size because every body is kept. This is not slow today, but it scales with the payload. The LCS diff is not a bottleneck: 200x200 lines took 1.8 ms and the detail screen costs 0.44 s above API time.

## Fix options (locked constraints respected; none was tried)

- **Slimmer list payload, omitting `body`** (36% of bytes, measured on this data): needs the maintainer's R3 decision (API change).
- **Use the existing opt-in `limit`/`offset` paging** (cap 500, `X-Total-Count`): no contract change; v2 could paint the first page early. Whether each page re-scans the whole tree on the server is unmeasured here.
- **Stop `/api/scopes` stalling the list:** cache or defer its token totals, or request it after the first paint. Backend-internal, no contract change, but it touches `webapp.py`/`scopes.py`.
- **gzip the responses** with the stdlib: no new field, but it is a webapp change, and the gain is unmeasured.
- **Classic list:** adopt v2's per-group cap with "Show more", or `content-visibility:auto` on rows. CSS/JS only, no build step; not measured.
