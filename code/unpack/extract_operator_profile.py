# -*- coding: utf-8 -*-
"""
extract_operator_profile.py — 干员档案解包（标准流程取样）
=========================================================
用法: python extract_operator_profile.py <charId> [--out out.json]

数据源（本地 ArknightsGameData 镜像）:
  character_table.json — 干员基础/阶段属性/天赋/技能引用
  skill_table.json     — 技能详情（技能名/SP/描述/黑板书）
  token_table.json     — 召唤物/装置
输出: 单干员结构化档案 JSON（属性成长全阶段、天赋、技能、潜能）。
"""
import argparse
import json
import os
import sys

DATA = r"E:\__file\ak_kb\gamedata"


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("char_id")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    chars = load("character_table.json")
    skills = load("skill_table.json")
    tokens = load("token_table.json")
    if args.char_id not in chars:
        sys.exit(f"char_id {args.char_id} 不存在（共 {len(chars)} 干员）")
    c = chars[args.char_id]

    prof = {
        "charId": args.char_id,
        "name": c["name"],
        "appellation": c.get("appellation", ""),
        "profession": c["profession"],
        "subProfessionId": c.get("subProfessionId", ""),
        "rarity": c["rarity"],
        "position": c["position"],
        "tagList": c.get("tagList", []),
        "nationId": c.get("nationId", ""),
        "phases": [],      # 精英化阶段属性
        "skills": [],      # 技能
        "talents": [],     # 天赋
        "trait": c.get("trait", {}),  # 特性
        "potentialRanks": c.get("potentialRanks", []),
        "favorKeyFrames": c.get("favorKeyFrames", []),
    }
    # phases: 每阶 (0,1,2) 的 maxLevel + 关键属性帧
    for ph in c.get("phases", []):
        entry = {"prefabKey": ph.get("characterPrefabKey"), "rangeId": ph.get("rangeId"),
                 "maxLevel": ph.get("maxLevel"),
                 "attributes": ph.get("attributesKeyFrames", [])}
        # 只保留 level/属性精简（去掉免疫布尔，保留数值）
        slim = []
        for f in entry["attributes"]:
            d = f["data"]
            slim.append({"level": f["level"],
                         "maxHp": d["maxHp"], "atk": d["atk"], "def": d["def"],
                         "magicResistance": d["magicResistance"], "cost": d["cost"],
                         "blockCnt": d["blockCnt"], "baseAttackTime": d["baseAttackTime"],
                         "respawnTime": d["respawnTime"], "attackSpeed": d["attackSpeed"],
                         "moveSpeed": d["moveSpeed"]})
        entry["attributes"] = slim
        prof["phases"].append(entry)

    # skills: 展开 skillId → skill_table 详情
    for sk in c.get("skills", []):
        sid = sk.get("skillId")
        info = {"skillId": sid, "unlockCondition": sk.get("unlockCond", {}),
                "levels": []}
        if sid and sid in skills:
            s = skills[sid]
            info["skillName"] = s.get("name", "")
            info["skillType"] = s.get("skillType", "")
            info["spType"] = s.get("spType", "")
            info["prefabKey"] = s.get("prefabKey", "")
            for lv in s.get("levels", []):
                info["levels"].append({
                    "level": lv.get("levelId"),
                    "name": lv.get("name"),
                    "rangeId": lv.get("rangeId"),
                    "spData": lv.get("spData", {}),
                    "description": lv.get("description", ""),
                    "blackboard": lv.get("blackboard", []),
                })
        prof["skills"].append(info)

    # talents: 阶段解锁
    for t in c.get("talents", []):
        cands = []
        for cand in t.get("candidates", []):
            cands.append({"unlockCondition": cand.get("unlockCondition", {}),
                          "name": cand.get("name"), "description": cand.get("description"),
                          "blackboard": cand.get("blackboard", [])})
        prof["talents"].append({"talents": cands})

    # 关联召唤物/装置
    tok = c.get("displayTokenDict") or {}
    prof["tokens"] = []
    for tk_id in tok:
        if tk_id in tokens:
            tk = tokens[tk_id]
            prof["tokens"].append({"tokenId": tk_id, "name": tk.get("name", ""),
                                   "phases": len(tk.get("phases", []))})

    text = json.dumps(prof, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"OK -> {args.out}")
    else:
        # 控制台精简显示
        p2 = dict(prof)
        for ph in p2["phases"]:
            ph["attributes"] = ph["attributes"][:2] + ["..."] if len(ph["attributes"]) > 2 else ph["attributes"]
        print(json.dumps(p2, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
