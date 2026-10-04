# -*- coding: utf-8 -*-
import json, os, collections

BASE = r"D:\__soft\MAA\resource"
P = os.path.join(BASE, "tasks", "tasks.json")
data = json.loads(open(P, 'rb').read().decode('utf-8-sig'))

def dump(name):
    print("=" * 70)
    print("### TASK:", name)
    print("=" * 70)
    if name in data:
        print(json.dumps({name: data[name]}, ensure_ascii=False, indent=4))
    else:
        # search
        hits = [k for k in data if name.lower() in k.lower()]
        print("NOT FOUND. similar:", hits[:20])

for n in ["StartUp", "Fight", "BattleStart", "BattleOperAvailable", "Copilot", "CopilotStart", "CopilotBegin", "CopilotReady"]:
    dump(n)

print("\n\n======== ALL TASK NAMES (869) ========")
for k in data:
    print(k)
