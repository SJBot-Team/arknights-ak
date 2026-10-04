import json, os, collections
MAA = r"D:\__soft\MAA\resource\copilot"
o=[]
def p(*a): o.append(" ".join(str(x) for x in a))
types = collections.Counter()
best = None
bestn = 0
for root, dirs, files in os.walk(MAA):
    for f in files:
        if not f.endswith(".json"): continue
        fp = os.path.join(root, f)
        try: j = json.load(open(fp, encoding="utf-8"))
        except Exception: continue
        acts = j.get("actions") or j.get("operation") or []
        if isinstance(acts, list):
            for a in acts:
                if isinstance(a, dict): types[a.get("type", "?")] += 1
        # old format: strategy/actions inside stages?
        s = json.dumps(j, ensure_ascii=False)
        n = s.count('"type"')
        if n > bestn:
            bestn = n; best = (fp, j)
p("=== action type 频次 ===")
for k,v in types.most_common(): p(f"  {k}: {v}")
p(f"\n=== 字段最丰富的作业: {best[0]}  (type 出现 {bestn} 次) ===")
j = best[1]
p("top-level keys: " + ", ".join(j.keys()))
# print first 2 actions fully + a skill/retreat example
acts = j.get("actions") or []
for a in acts[:3]: p(json.dumps(a, ensure_ascii=False))
for a in acts:
    if isinstance(a, dict) and a.get("type") in ("Skill", "Retreat", "Deploy"):
        p(json.dumps(a, ensure_ascii=False))
# also dump 'opers' sample and 'type'/'strategy'
for k in ("type","strategy","stages","opers","doc","minimum_required","buff","equipment","tool_men"):
    if k in j:
        v = json.dumps(j[k], ensure_ascii=False)
        p(f"{k}: {v[:600]}")
open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\copilot_sample.txt","w",encoding="utf-8").write("\n".join(o))
print("ok")
