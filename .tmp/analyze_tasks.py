# -*- coding: utf-8 -*-
import json, collections, io, sys, os

P = r"D:\__soft\MAA\resource\tasks\tasks.json"
raw = open(P, 'rb').read().decode('utf-8-sig')

dup = []
def hook(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            dup.append(k)
        seen[k] = v
    return seen

data = json.loads(raw, object_pairs_hook=hook)

print("TOTAL_TASKS:", len(data))
print("DUPLICATE_KEYS_IN_FILE:", sorted(set(dup))[:30], "count=", len(dup))

fieldcount = collections.Counter()
for name, body in data.items():
    if not isinstance(body, dict):
        print("NON-DICT TASK:", name, type(body)); continue
    for f in body:
        fieldcount[f] += 1

print("\n--- FIELD FREQUENCY (field: #tasks) ---")
for f, c in fieldcount.most_common():
    print("%-32s %d" % (f, c))

# algorithm values
alg = collections.Counter()
for name, body in data.items():
    if isinstance(body, dict):
        alg[body.get('algorithm', '<none>')] += 1
print("\n--- algorithm VALUES ---")
for a, c in alg.most_common():
    print("%-32s %d" % (a, c))

# action values
act = collections.Counter()
for name, body in data.items():
    if isinstance(body, dict) and 'action' in body:
        act[str(body['action'])] += 1
print("\n--- action VALUES ---")
for a, c in act.most_common():
    print("%-24s %d" % (a, c))

# sub-task files
print("\n--- SUB TASK FILES (from tasks/) key counts ---")
base = r"D:\__soft\MAA\resource\tasks"
for root, dirs, files in os.walk(base):
    for fn in files:
        if fn.endswith('.json'):
            fp = os.path.join(root, fn)
            if fp == P: continue
            try:
                d = json.loads(open(fp, 'rb').read().decode('utf-8-sig'), object_pairs_hook=hook)
                print("%-60s %d" % (os.path.relpath(fp, base), len(d) if isinstance(d, dict) else -1))
            except Exception as e:
                print("%-60s ERR %s" % (os.path.relpath(fp, base), e))
