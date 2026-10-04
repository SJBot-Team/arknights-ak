# -*- coding: utf-8 -*-
r"""t200_rounding_probe.py — **用 1-1 标定数据反推"FP 秒 → 帧"的取整口径**（T-200c）

## 问题（用户 2026-09-29 任务 1-③）
本体 `BattleFormula.CalculateAttackInterval`（RVA `0x3584F10`）**公式层零取整**（04/68 实证），
那"攻击间隔多少帧"到底在哪一层、按什么方向取整？本脚本**不靠猜**，用**实机标定数据**判别。

## 方法
标定表（`C:\Users\23922\Desktop\1-1标定.xlsx`，见 `04/54` 与 `sim/draft/replay_11calib.py`）
里同一条**不间断攻击链**的命中帧差 = 该单位在实机上的**真实攻击间隔帧数**：

| 单位 | 数据表 BAT/攻速 | 标定命中帧 | 帧差 |
|---|---|---|---|
| 芬 `char_123_fang` | 1.05 / 100 | 221, 253, 285, 317, 349 | **32, 32, 32, 32** |
| 猎狗pro `enemy_1000_gopro_2` | 1.4 / 100 | 255, 298, 340 | **43, 42** |

对每种候选口径，用时间层算出差序列，与实测比较。

## 候选口径
- `native`      ：FP 逐帧累加，跨过阈值那一帧（默认；本体口径）
- `legacy`      ：`ceil(秒×30 − 1e-9)`（`04/41` 首版）
- `floor`/`round`：对照
- 每种再分 `carry=False`（每周期把累加器清零）/ `carry=True`（保留溢出量，本体更可能如此）

用法：`python ak_sim/t200_rounding_probe.py`
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import fp, timeline                      # noqa: E402

# ---------------- 实测（来源：1-1 标定表 → 04/54 §五） ----------------
OBSERVED = [
    {'name': '芬', 'key': 'char_123_fang', 'bat': 1.05, 'aspd': 100.0,
     'hits': [221, 253, 285, 317, 349], 'note': '标定「芬 命中」221/253/285/317/349'},
    {'name': '猎狗pro', 'key': 'enemy_1000_gopro_2', 'bat': 1.4, 'aspd': 100.0,
     'hits': [255, 298, 340], 'note': '标定「猎狗pro 1 命中」255/298/340'},
]
MODES = ['fp_accumulate', 'frame_ceil', 'floor', 'round']


def spacings(hits: list[int]) -> list[int]:
    return [hits[i + 1] - hits[i] for i in range(len(hits) - 1)]


def predict(bat: float, aspd: float, mode: str, carry: bool, n_cycles: int) -> list[int]:
    """按给定口径预测**命中帧差**序列（纯时间层，不含战斗逻辑）。

    周期语义（同 `timeline.AttackCycle`）：起手 → 累加至 ≥ 前摇 ⇒ 出手（=命中帧）
    → 累加至 ≥ 间隔 ⇒ 本周期结束。`carry=True` 时结束时**减去间隔**保留溢出量。
    """
    bat_fp = fp.from_float(bat)
    iv_fp = timeline.attack_interval_fp(bat_fp, aspd)
    if mode == 'frame_ceil':
        iv_frames = timeline.interval_frames_legacy(bat_fp, aspd)
        iv_fp = fp.mul(fp.from_int(iv_frames), timeline.FRAME_TIME_FP)
    elif mode == 'fp_accumulate':
        # ★修正（2026-09-29 19:4x）：FP 累加口径必须用**未量化的 FP 间隔**再比较，
        #   先把间隔量化成整数帧会把这个口径"退化成 frame_ceil"（旧版 bug）。
        pass
    else:
        iv_frames = timeline.frames_for(bat_fp, aspd, mode)
        iv_fp = fp.mul(fp.from_int(iv_frames), timeline.FRAME_TIME_FP)

    # 前摇：本反推只关心**帧差**，前摇取任意固定值不影响差序列（各周期相同）
    pre_fp = fp.mul(iv_fp, fp.from_float(0.55))

    out, elapsed, frame, fired = [], 0, 0, False
    guard = 0
    while len(out) < n_cycles + 1 and guard < 100000:
        guard += 1
        frame += 1
        elapsed = fp.add(elapsed, timeline.FRAME_TIME_FP)
        if not fired and elapsed >= pre_fp:
            fired = True
            out.append(frame)                      # 命中帧
        if elapsed >= iv_fp:
            elapsed = fp.sub(elapsed, iv_fp) if carry else 0
            fired = False
    return spacings(out[:n_cycles + 1])


def main() -> int:
    print('=== 1-1 标定反推：FP 秒 → 帧 的取整口径 ===')
    print(f'timeline.TIME_MODE = {timeline.TIME_MODE}｜FRAME_TIME_FP = {timeline.FRAME_TIME_FP}')
    print('（注：本脚本对各口径**独立**计算，不受 TIME_MODE 影响）\n')

    results = []
    for u in OBSERVED:
        obs = spacings(u['hits'])
        # ★首个帧差可能含"起手瞬态"（第一次攻击的起手相位未知）⇒ 另算**稳态帧差**
        obs_stable = obs[1:] if len(obs) > 1 else obs
        print(f"■ {u['name']} ({u['key']})  BAT={u['bat']}s  攻速={u['aspd']}")
        print(f"  实测帧差（来自标定）: {obs}   ← {u['note']}")
        print(f"  稳态帧差（去掉首个）: {obs_stable}")
        row = {'unit': u['name'], 'key': u['key'], 'observed': obs,
               'observed_stable': obs_stable, 'candidates': []}
        for mode in MODES:
            for carry in (False, True):
                pred = predict(u['bat'], u['aspd'], mode, carry, len(obs))
                pred_stable = pred[1:] if len(pred) > 1 else pred
                ok = (pred == obs)
                ok_stable = (pred_stable == obs_stable)
                tag = ('✅稳态吻合' if ok_stable else '★稳态不符') + ('（整段也吻合）' if ok else '')
                print(f'    {mode:<13} carry={str(carry):<5} → {pred}   {tag}')
                row['candidates'].append({'mode': mode, 'carry': carry, 'pred': pred,
                                          'exact': ok, 'exact_stable': ok_stable})
        results.append(row)
        print()

    # ---- 综合评分：以**稳态帧差**为准（去掉首个瞬态），两种 carry 都不区分则并列 ----
    print('=== 综合判定（按**稳态帧差**，需同时吻合两个单位） ===')
    score = {}
    for mode in MODES:
        for carry in (False, True):
            hits = [c['exact_stable'] for r in results for c in r['candidates']
                    if c['mode'] == mode and c['carry'] == carry]
            exact = sum(1 for h in hits if h)
            score[f'{mode}|carry={carry}'] = exact
            verdict = '★★ 两单位都吻合 ⇒ **该口径即实机口径**' if exact == len(results) else (
                '1 个单位吻合' if exact else '✗ 不吻合')
            print(f'  {mode:<13} carry={str(carry):<5}  稳态吻合 {exact}/{len(results)}   {verdict}')

    print('\n结论提示：')
    print('  · 被否证的口径会**给出确定的不同值**（如 fp_accumulate 对 BAT=1.4 给 43，实机 42）⇒ 该假设排除。')
    print('  · 若多个口径同时吻合 ⇒ 用更多样本（其它关卡/更长攻击链）继续区分；')
    print('    当前样本已足以排除 `floor`/`round`（芬 会给 31 ≠ 32）与 `fp_accumulate`（猎狗 43 ≠ 42）。')

    out = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp', 't200_rounding_probe.json')
    json.dump({'frame_time_fp': timeline.FRAME_TIME_FP, 'results': results,
               'score': score},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n明细已写 {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
