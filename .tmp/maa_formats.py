# -*- coding: utf-8 -*-
"""提取 MAA 数据格式样本：tasks.json 关键任务 + copilot 作业 + Copilot 任务参数"""
import json, re, os, sys

MAA = r"D:\__soft\MAA"
OUT = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\maa_formats.txt"
o = []
def p(*a):
    o.append(" ".join(str(x) for x in a))

def load_tasks():
    raw = open(os.path.join(MAA, "resource", "tasks", "tasks.json"), encoding="utf-8").read()
    return json.loads(re.sub(r"^\s*//.*$", "", raw, flags=re.M))

d = load_tasks()
p("=== 任务总数:", len(d))
p("\n=== 代表性任务的完整 JSON ===\n")
for k in ["StartUp", "StartUpBegin", "Fight", "Terminal-Entry", "BattleHasStarted",
          "BattleDeployWhenPause", "BattleOperAvailable", "BattleOperAvatar",
          "BattleDeployDirectionRectMove", "BattleStartPre", "Copilot",
          "Copilot@ClickStart", "Copilot@DeployOper", "Copilot@UseSkill",
          "ClickStageName", "ClickedCorrectStage", "StageBegin", "LoadingIcon"]:
    if k in d:
        p(f"--- {k} ---")
        p(json.dumps(d[k], ensure_ascii=False, indent=2))
        p("")
    else:
        p(f"--- {k} --- (NOT FOUND)")

# Copilot 相关任务名清单
p("\n=== 含 Copilot 的任务名 ===")
p(", ".join(sorted(k for k in d if "Copilot" in k)))
# Battle 相关
p("\n=== 含 Battle 的任务名 ===")
p(", ".join(sorted(k for k in d if k.startswith("Battle"))))

# copilot 作业样例
cp = os.path.join(MAA, "resource", "copilot", "OF-1_credit_fight.json")
p(f"\n=== copilot 作业样例: {cp} ===")
p(open(cp, encoding="utf-8").read())

# 找一个带 skill/retreat 的作业
for root, dirs, files in os.walk(os.path.join(MAA, "resource", "copilot")):
    for f in files:
        if f.endswith(".json"):
            fp = os.path.join(root, f)
            try:
                j = json.load(open(fp, encoding="utf-8"))
            except Exception:
                continue
            acts = j.get("actions", j.get("operation", []))
            if isinstance(acts, list) and acts:
                kinds = set()
                for a in acts:
                    if isinstance(a, dict):
                        kinds |= set(a.keys())
                if {"Deploy", "Skill", "Retreat"} & kinds or "Deploy" in kinds:
                    p(f"\n=== 作业样例（含 deploy/skill）: {fp} ===")
                    p(json.dumps(j, ensure_ascii=False)[:3000])
                    break
    else:
        continue
    break

# 统计 action 键集合
keys = {}
cnt = 0
for root, dirs, files in os.walk(os.path.join(MAA, "resource", "copilot")):
    for f in files:
        if not f.endswith(".json"):
            continue
        try:
            j = json.load(open(os.path.join(root, f), encoding="utf-8"))
        except Exception:
            continue
        cnt += 1
        acts = j.get("actions") or j.get("operation") or []
        if isinstance(acts, list):
            for a in acts:
                if isinstance(a, dict):
                    for kk in a:
                        keys[kk] = keys.get(kk, 0) + 1
        for kk in j:
            keys.setdefault("__TOP__" + kk, 0)
            keys["__TOP__" + kk] += 1
p(f"\n=== copilot 作业文件数: {cnt} ===")
p("=== copilot 字段频次 ===")
for k, v in sorted(keys.items(), key=lambda x: -x[1]):
    p(f"  {k}: {v}")

open(OUT, "w", encoding="utf-8").write("\n".join(o))
print("written", OUT)
