# -*- coding: utf-8 -*-
"""
fetch_level_lutonada.py — 从露托(lutonada.online) API 抓取关卡完整数据
======================================================================
用法: python fetch_level_lutonada.py <levelId> [--out 保存路径] [--print-head]

背景（2026-09-02 探明）:
  露托 = 明日方舟地图模拟器（Vite SPA）。静态站 http://lutonada.online 仅 HTTP(80)，
  HTTPS 未开；后端 API = http://152.136.189.98:3000（axios baseURL）。
  数据与 ArknightsGameData 主仓 levels/ 同构（waves/routes/enemyDbRefs/mapData 逐字段一致），
  但**更新更快**：新活动（如 act54side）主仓还没有，露托 API 有 → 本地缺新关卡时用本脚本。

露托 API 端点清单（供后续复用）:
  GET  /json/story{CN|EN|JP|KR}.json   关卡索引（含 levelId/关卡名/简介, 1MB）
  GET  /levels/{levelId}.json          关卡完整数据（options/mapData/routes/waves/enemyDbRefs/runes...）
  POST /enemy/data  {language, enemyRefs:[{useDb,id,level,...}]}  关卡敌人实例数值（含 overwrittenData 覆盖）
  POST /recalRune/getData {levelId: 短名, language}   指标词条(tag)数据（固定+可选 rune，含属性修正 blackboard）
  POST /ccb/getData     {mapId}        关卡背景/演出数据
  GET  /recalruneTags/*.png            词条图标
  POST /assets/getTrapsKey | getTokenCards | getMeshsKey  模型资源（3D 展示用）
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.parse

API = "http://152.136.189.98:3000"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
DEFAULT_OUT_DIR = r"E:\__file\ak_kb\gamedata\levels"


def fetch_level(level_id, timeout=120):
    url = API + "/levels/" + urllib.parse.quote(level_id, safe="") + ".json"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("level_id")
    ap.add_argument("--out", default=None)
    ap.add_argument("--print-head", action="store_true")
    args = ap.parse_args()

    data = fetch_level(args.level_id)
    out = args.out or os.path.join(DEFAULT_OUT_DIR, args.level_id + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        f.write(data)
    print(f"OK {args.level_id} -> {out} ({len(data)} bytes) [lutonada API]")

    if args.print_head:
        d = json.loads(data)
        print("keys:", list(d.keys()))
        print("routes:", len(d.get("routes") or []), "waves:", len(d.get("waves") or []),
              "enemyDbRefs:", len(d.get("enemyDbRefs") or []))


if __name__ == "__main__":
    main()
