# -*- coding: utf-8 -*-
"""
extract_animations.py — 提取战斗 prefab 的动画信息（AnimationClip 名/时长 + AnimatorController 状态）
====================================================================================================
用法: python extract_animations.py <ab文件> [--out out.json]

背景（2026-09-04 探明）:
  明日方舟干员技能/攻击表现层动画位于 battle/prefabs/effects/<干员>.ab（如 makoto.ab，
  已备份为 battle_skill_makoto.ab），内含 AnimationClip（m_MuscleClip.m_StopTime=时长秒，
  m_SampleRate=帧率 30fps）与 AnimatorController（状态机，驱动粒子/模型动画）。
  表现层动画时长与战斗数值时间轴（base_attack_time / 技能 duration）配合决定：
  攻击速度上下限、伤害命中时刻、部分效果生效检测（以动画事件/Ability duration 为锚点）。

  注意：数值时间轴（攻击间隔/伤害时刻）的权威源是技能/天赋黑板上限 + buff 模板节点；
  动画时长主要用于核对表现层是否匹配（如攻击动画 > 攻击间隔 → 攻速上限受动画钳制）。

输出:
  { clips: [{name, duration_s, sample_rate, stop_time, loop}],
    animators: [{controller, states:[{name, ...}]}] }
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper
import ak_lz4ak

CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = ak_lz4ak.decompress_lz4ak
import UnityPy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ab_file")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    env = UnityPy.load(args.ab_file)
    clips = []
    animators = []
    for obj in env.objects:
        t = obj.type.name
        if t == "AnimationClip":
            tt = obj.read_typetree()
            mc = tt.get("m_MuscleClip") or {}
            name = tt.get("m_Name", "")
            clips.append({
                "name": name,
                "duration_s": mc.get("m_StopTime", 0.0),
                "sample_rate": tt.get("m_SampleRate", 30.0),
                "loop": mc.get("m_LoopTime", False),
                "events": len(tt.get("m_Events") or []),
            })
        elif t == "AnimatorController":
            try:
                d = obj.read()
                nm = getattr(d, "m_Name", "")
                animators.append({"controller": nm, "size": obj.byte_size})
            except Exception:
                pass
    clips.sort(key=lambda c: (c["name"], c["duration_s"]))
    out = {"source": os.path.basename(args.ab_file), "clips": clips, "animators": animators}
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"OK {len(clips)} clips -> {args.out}")
    else:
        print(f"clips: {len(clips)}, animators: {len(animators)}")
        for c in clips:
            print(f"  {c['name']:<60} {c['duration_s']:>6.3f}s @{c['sample_rate']:.0f}fps loop={c['loop']} events={c['events']}")


if __name__ == "__main__":
    main()
