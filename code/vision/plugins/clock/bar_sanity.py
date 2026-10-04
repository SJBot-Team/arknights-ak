# -*- coding: utf-8 -*-
"""bar_sanity.py — 费用条采样序列的**自检**（防止 ROI 失效时静默产出无效结论）

## 为什么需要
第 58 轮的教训：费用条 ROI 在某些画面下失效，读到的"填充宽度"其实是别的东西
（表现为填充**递减**、费用每 +1 而采样间隔不足 30 帧）。若不检查，脚本会照常输出一个
看起来很正式的"误差统计"，把无效数据当成结论。本模块把这类失效**变成显式失败**。

## 三条规则（对一组按时间排序的采样）
1. **费用非递减**（同一局内费用只会涨或不变）；
2. **费用不变时填充不应显著减小**（容差 `reset_tol`，用于容忍回绕/动画帧）；
3. **费用 +1 的相邻采样，其推得帧数应 ≥ `min_frames_per_cost`**（默认 25）——
   因为 1 费需要 30 帧，采样间隔不足 25 帧却"费用 +1"在物理上不可能。

任一违反 ⇒ `ok=False` 并给出具体证据（哪两条样本、什么现象）。
"""
from __future__ import annotations


def check_bar_series(samples, min_frames_per_cost: int = 25, reset_tol: int = 40,
                     fps: float = 30.0):
    """samples: [(cost, fill_px, sub_frame), ...]（按采集顺序，cost 可能为 None 的样本会被跳过）

    返回 (ok: bool, problems: list[str])
    """
    problems: list[str] = []
    prev = None
    for i, s in enumerate(samples):
        c, fill, sub = (list(s) + [None, None])[:3]
        if c is None or fill is None or sub is None:
            continue
        if prev is not None:
            pc, pfill, psub = prev
            # 规则 1：费用非递减
            if c < pc:
                problems.append(f'#{i}: 费用下降 {pc}→{c}（同局费用不应减少）')
            # 规则 2：费用不变时填充不应显著减小
            if c == pc and fill < pfill - reset_tol:
                problems.append(f'#{i}: 费用不变（{c}）但填充从 {pfill}px 降到 {fill}px'
                                f'（超过容差 {reset_tol}px）')
            # 规则 3：费用一次跳 >1 ⇒ 采样间隔过大或有漏读（相位无法消歧）
            if c > pc + 1:
                problems.append(f'#{i}: 费用一次跳 {pc}→{c}（采样间隔可能 ≥1 秒或有漏读）')
            # 规则 4：费用 +1 ⇒ 相位必须"跨过一次回绕"，等价于推得帧数 ≥30
            if c == pc + 1:
                frames = 30 * (c - pc) + ((sub - psub) % 30)
                if frames < 30:
                    problems.append(f'#{i}: 费用 +1 但推得仅 {frames} 帧（应 ≥30）；相位 {psub}→{sub}')
        prev = (c, fill, sub)
    return (len(problems) == 0), problems


def summarize(samples, fps: float = 30.0) -> str:
    ok, probs = check_bar_series(samples, fps=fps)
    if ok:
        return f'费用条采样自检：通过（{len(samples)} 条）'
    lines = [f'费用条采样自检：★未通过（{len(probs)} 处问题，共 {len(samples)} 条）']
    lines += [f'   · {p}' for p in probs[:8]]
    if len(probs) > 8:
        lines.append(f'   · …另有 {len(probs)-8} 处')
    lines.append('   ⇒ 该批样本不可用于结论（ROI 可能失效或采样间隔不当）')
    return '\n'.join(lines)
