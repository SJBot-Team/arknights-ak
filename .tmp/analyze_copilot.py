# -*- coding: utf-8 -*-
import json, os, collections, glob

BASE = r"D:\__soft\MAA\resource\copilot"
allf = glob.glob(os.path.join(BASE, "**", "*.json"), recursive=True)
print("copilot json files:", len(allf))

top = collections.Counter()
actiontypes = collections.Counter()
deploykeys = collections.Counter()
operkeys = collections.Counter()
types = collections.Counter()
for fp in allf:
    try:
        d = json.loads(open(fp, 'rb').read().decode('utf-8-sig'))
    except Exception as e:
        print("ERR", fp, e); continue
    if not isinstance(d, dict):
        print("NONDICT", fp); continue
    for k in d: top[k] += 1
    types[str(d.get('type'))] += 1
    for a in d.get('actions') or []:
        if isinstance(a, dict):
            actiontypes[str(a.get('type'))] += 1
            if a.get('type') == 'Deploy':
                for k in a: deploykeys[k] += 1
    for o in d.get('opers') or []:
        if isinstance(o, dict):
            for k in o: operkeys[k] += 1

print("\n--- TOP-LEVEL KEYS (count of files) ---")
for k, c in top.most_common(): print("%-28s %d" % (k, c))
print("\n--- 'type' VALUES ---")
for k, c in types.most_common(): print("%-28s %d" % (k, c))
print("\n--- action 'type' VALUES ---")
for k, c in actiontypes.most_common(): print("%-28s %d" % (k, c))
print("\n--- Deploy action KEYS ---")
for k, c in deploykeys.most_common(): print("%-28s %d" % (k, c))
print("\n--- opers[] KEYS ---")
for k, c in operkeys.most_common(): print("%-28s %d" % (k, c))

# pick a representative multi-action copilot
for fp in allf:
    d = json.loads(open(fp, 'rb').read().decode('utf-8-sig'))
    acts = d.get('actions') or []
    kinds = {a.get('type') for a in acts if isinstance(a, dict)}
    if len(kinds) >= 3 and len(acts) > 12:
        print("\n=== REPRESENTATIVE FILE:", fp)
        print(json.dumps(d, ensure_ascii=False, indent=4)[:4000])
        break
