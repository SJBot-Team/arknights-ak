# -*- coding: utf-8 -*-
"""
fetch_lutonada_tag.py — 从露托 API 抓取「指标词条(tag)」数据（选 tag 看敌方属性）
=================================================================================
用法:
  python fetch_lutonada_tag.py recalrune <levelName>   # 词条: levelName 如 level_recalrune_01-01
  python fetch_lutonada_tag.py enemy <levelJson>       # 敌人实例数值: 从关卡 json 抽 enemyDbRefs 查

背景（2026-09-02 探明，用户点名功能）:
  露托的「自主选择 tag 查看不同 tag 敌方属性」= recalRune（指标词条）系统:
  POST /recalRune/getData {levelId: '<尾段名>', language:'CN'} →
    { stageId, levelName(如 "#爱国者之死"), levelCode(如 "7-18"),
      fixedRuneSeriesName(如 "指标·死而不朽"),
      parsedRunes: [ {runeId, essential, exclusiveGroupId, runeIcon,
                      description[], runes:[{key, selector{...}, blackboard[{key,value,valueStr}]}]} ] }
  词条经 runesHelper 应用: 按 calMethod(add/addmul/mul/set) 修正敌方属性
  （黑盒应用逻辑在 lutonada 前端 runesHelper；原始词条数据即本脚本输出）。

enemy/data 接口返回关卡实例敌人数值（属性经关卡 overwrittenData/词条修正，
与 enemy_database 基值不同；enemyRefs 传关卡 json 的 enemyDbRefs 数组）。
"""
import argparse
import json
import os
import sys
import urllib.request

API = "http://152.136.189.98:3000"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
OUT_DIR = r"E:\__file\ak_kb\gamedata"


def post(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode("utf-8"),
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["recalrune", "enemy"])
    ap.add_argument("arg", help="recalrune: 关卡名(level_recalrune_xx)；enemy: 关卡 json 路径")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.mode == "recalrune":
        d = post("/recalRune/getData", {"levelId": args.arg, "language": "CN"})
        out = args.out or os.path.join(OUT_DIR, "derived", f"tag_{args.arg}.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        data = d.get("data") or {}
        print(f"OK tag {args.arg} -> {out}")
        print("  stage:", data.get("levelName"), "| code:", data.get("levelCode"),
              "| 系列:", data.get("fixedRuneSeriesName"))
        runes = data.get("parsedRunes") or []
        print(f"  rune 组数: {len(runes)}")
        for r in runes:
            print("   -", r.get("runeId"), "essential=", r.get("essential"),
                  "| desc:", (r.get("description") or ["?"])[0][:60])
    else:
        lv = json.load(open(args.arg, encoding="utf-8"))
        refs = lv.get("enemyDbRefs") or []
        print(f"关卡 {args.arg} 敌人引用 {len(refs)} 个")
        if refs:
            d = post("/enemy/data", {"language": "CN", "enemyRefs": refs})
            out = args.out or os.path.join(OUT_DIR, "derived",
                                           "enemy_inst_" + os.path.basename(args.arg).replace(".json", "") + ".json")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            datas = (d.get("data") or {}).get("EnemyDatas") or []
            print(f"OK enemy 实例 -> {out} ({len(datas)} 个)")
            for e in datas[:8]:
                at = e.get("attributes") or {}
                print(f"   {e.get('name')} ({e.get('key')}) HP={at.get('maxHp')} ATK={at.get('atk')} "
                      f"DEF={at.get('def')} 间隔={at.get('baseAttackTime')} 移速={at.get('moveSpeed')}")


if __name__ == "__main__":
    main()
