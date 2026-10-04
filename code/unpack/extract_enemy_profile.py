# -*- coding: utf-8 -*-
"""
extract_enemy_profile.py — 敌人档案解包（标准流程取样）
========================================================
用法: python extract_enemy_profile.py <enemyId|名字关键字> [--out out.json]

数据源:
  enemy_handbook_table.json — 图鉴（名称/种族/能力文本/攻击类型/等级区间）
  enemy_database.json       — 逐级数值表（来源: tomimi-dev 仓库解包镜像，ArknightsGameData 未提供）
  collider_report.json      — 本地 prefab 碰撞提取报告（downloads 或 gamedata/derived）
说明: enemy_handbook_table 无逐级数值；逐级数值/攻击形式见 enemy_database.json。
"""
import argparse
import json
import os
import sys

DATA = r"E:\__file\ak_kb\gamedata"
COLLIDER_CANDIDATES = [
    r"E:\__file\ak_kb\downloads\collider_report.json",
    r"E:\__file\ak_kb\gamedata\derived\collider_report.json",
    os.path.join(DATA, "collider_report.json"),
]


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="enemyId 或中文名关键字")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    hb = load("enemy_handbook_table.json")
    ed = hb["enemyData"]
    race = {r["id"]: r.get("raceName", "") for r in hb.get("raceData", {}).values()}

    # resolve enemyId by exact or keyword over Chinese names
    target = None
    if args.query in ed:
        target = args.query
    else:
        for eid, v in ed.items():
            if args.query in (v.get("name") or ""):
                target = eid
                break
    if not target:
        # fall back: keyword in enemyId
        for eid in ed:
            if args.query.lower() in eid.lower():
                target = eid
                break
    if not target:
        sys.exit(f"未找到敌人: {args.query}（enemyData 共 {len(ed)} 条）")
    v = ed[target]

    prof = {
        "enemyId": target,
        "name": v.get("name", ""),
        "enemyIndex": v.get("enemyIndex", ""),       # 图鉴序号
        "enemyLevel": v.get("enemyLevel", ""),       # NORMAL/ELITE/BOSS
        "race": race.get(v.get("race", ""), v.get("race", "")),
        "damageType": v.get("damageType", []),
        "attackType": v.get("attackType"),
        "ability": v.get("ability"),
        "abilityList": v.get("abilityList", []),
        "description": v.get("description", ""),
        "linkEnemies": v.get("linkEnemies", []),
        "hideInHandbook": v.get("hideInHandbook", False),
    }

    # 逐级数值（enemy_database.json，本地镜像）
    try:
        edb = load("enemy_database.json")
        if target in edb:
            e = edb[target]
            prof["stats_by_level"] = e.get("stats", [])
            prof["forms"] = e.get("forms", [])
            prof["enemy_index"] = e.get("id")
    except FileNotFoundError:
        pass

    # 关联碰撞数据（本地解包 prefab）
    col = None
    for cand in COLLIDER_CANDIDATES:
        if os.path.exists(cand):
            try:
                col = json.load(open(cand, encoding="utf-8"))
            except Exception:
                col = None
            break
    if col:
        # report 形态可能是 {enemy_id: {collider...}} 或 list —— 自适应
        hit = None
        if isinstance(col, dict):
            for k, c in col.items():
                if target in k or (v.get("name") or "") in str(c):
                    hit = (k, c)
                    break
        if hit:
            prof["collider_local"] = hit[1]
        else:
            prof["collider_local"] = "<无匹配（报告键数 %d）>" % len(col)

    text = json.dumps(prof, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"OK {target} -> {args.out}")
    else:
        print(text[:2000])


if __name__ == "__main__":
    main()
