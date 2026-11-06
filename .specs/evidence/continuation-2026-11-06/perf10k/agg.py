import json, statistics as st, collections
rows=[json.loads(l) for l in open('results.jsonl')]
meta={r['size']:r for r in rows if r.get('meta')}
g=collections.defaultdict(list)
for r in rows:
    if not r.get('meta'): g[(r['size'],r['ui'],r['screen'])].append(r)
def f(vals):
    v=[x for x in vals if x is not None]
    if not v: return 'n/a'
    return f"{st.median(v):g} ({min(v):g}-{max(v):g})" if len(v)>1 else f"{v[0]:g}"
def get(r,*k):
    for kk in k:
        if r is None: return None
        r=r.get(kk) if isinstance(r,dict) else None
    return r
print("| size | UI | screen | ok | ready ms | API ms | heap MB (post-GC) | DOM nodes | longtasks n / total ms / max ms | max stall ms | PSS MB | errs |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for k in sorted(g):
    a=g[k]
    print(f"| {k[0]} | {k[1]} | {k[2]} | {sum(x['ok'] for x in a)}/{len(a)} | {f([x.get('ready_ms') for x in a])} | {f([x.get('api_skills_ms') for x in a])} | {f([x.get('heap_mb') for x in a])} | {f([x.get('dom_nodes') for x in a])} | {f([x.get('longtask_n') for x in a])} / {f([x.get('longtask_total_ms') for x in a])} / {f([x.get('longtask_max_ms') for x in a])} | {f([x.get('stall_max_ms') for x in a])} | {f([x.get('tree_pss_mb') for x in a])} | {f([x.get('console_error_n') for x in a])} |")
print()
print("INTERACTIONS (ms; first = first list change, last = settled)")
print("| size | UI | search 'audit' first/last | clear | typing input->paint per key (median of max) | filter on | filter off |")
print("|---|---|---|---|---|---|---|")
for k in sorted(g):
    a=[x for x in g[k] if x.get('interaction')]
    if not a: continue
    def t(name,key): return f([get(x,'interaction',name,key) for x in a])
    ty=[max(get(x,'interaction','typing_input_to_paint_ms') or [0]) for x in a]
    print(f"| {k[0]} | {k[1]} | {t('search_single_event','first')} / {t('search_single_event','last')} | {t('search_clear','last')} | {f(ty)} | {t('filter_on','first')} / {t('filter_on','last')} | {t('filter_off','first')} / {t('filter_off','last')} |")
print()
for k in sorted(g):
    if k[1]=='classic':
        print(k,'library_switch_ms',f([x.get('library_switch_ms') for x in g[k]]),'landing',f([x.get('landing_ms') for x in g[k]]))
for k in sorted(g):
    for x in g[k]:
        if not x['ok'] or x.get('crashed') or x.get('ready_ms') is None or x.get('console_error_n') or x.get('failed_requests'):
            print('ISSUE',k,x.get('rep'),x.get('error'),x.get('ready_error'),x.get('crashed'),x.get('console_errors'),x.get('failed_requests'))
print({k:(v['detail'],v['instances']) for k,v in meta.items()})
print('payload', {k:f([x.get('api_skills_bytes') for x in g[(k,'v2','home')]]) for k in meta})
