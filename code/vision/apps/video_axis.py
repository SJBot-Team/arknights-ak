# -*- coding: utf-8 -*-
"""video_axis.py — 由 HUD 扫描结果构建「视频帧 → 游戏帧」时间轴（★与速度状态无关）

## 为什么不能"线性映射"
视频里游戏**不是匀速推进**：开场有加载段、之后 暂停 / 1X / 极慢 交替
（历史结论见 54 号报告 §十七~§十九）。所以"视频帧 × 常数 = 游戏帧"必然失败。

## 两条独立的时钟（本脚本同时算、并相互印证）
### 时钟 A：**相位累加**（只用费用条填充）
游戏原生 HUD 的费用条填充直接给出 **`游戏帧 mod 30`**：
```
g(f) = 填充px / FULL * 30                      （0 ~ 30）
d(f) = g(f) - g(f-1)；若 < -10 则 +30（跨秒回绕）；抖动/异常置 0
A(f) = Σ d
```
暂停时 g 恒定 ⇒ A 不前进（**正确**：暂停即游戏时间不前进）；倍速被逐帧累加自动吸收。

### 时钟 B：**回费计数**（只用费用数字）
费用**自然回复 +1 = 恰好 30 游戏帧**（1 秒），与视频速度无关：
```
game_frame(f) = 30 * k(f) + g(f) - c0
k(f) = f 之前检出的"自然回费(+1)"次数
```
技能回费（芬「冲锋号令·α型」**+6**）与部署扣费（−8 / −14）**不改变时间**，
必须与 +1 区分开——否则会把技能当成 6 秒。

## 输出
- `--out` JSONL：每帧 `{f, px, g, A, B, cost}`
- 控制台：段表（速度状态）、费用变化表（含类型判读）、A/B 差异（漂移量）、锚点表

用法：
    python apps/video_axis.py <hud_scan.jsonl> <axis.jsonl> [--full 174] [--anchor 621] [--anchors 621,5961]
"""
from __future__ import annotations

import argparse
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

WRAP_DROP = -10.0
MAX_STEP = 5.0            # 单帧相位增量上限（1X≈1.03、2X≈2.07）；超过判为读数异常


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('hud')
    ap.add_argument('out')
    ap.add_argument('--full', type=float, default=174.0,
                    help='满条填充 px（= 30 游戏帧）；本片实测最大填充 174px')
    ap.add_argument('--anchor-frame', type=int, default=621,
                    help='锚点视频帧：此处 cost 刚从初始值跌落（= 部署干员）')
    ap.add_argument('--anchor-game', type=float, default=10.0,
                    help='锚点对应的游戏帧（1-1 标定：帧 10 部署芬）')
    ap.add_argument('--anchors', default='')
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.hud, encoding='utf-8')]
    print(f'读入 {len(rows)} 帧 HUD 记录；满条 {a.full}px ⇒ {a.full / 30:.3f}px/帧')

    # ---------- 时钟 A：相位累加 ----------
    prev_f = prev_g = None
    A = 0.0
    a_list = []
    for r in rows:
        f, px = r['f'], r['bar_px']
        g = px / a.full * 30.0
        if prev_f is None or f - prev_f != 1:
            d = 0.0
        else:
            d = g - prev_g
            if d < WRAP_DROP:
                d += 30.0
            if d < 0 or d > MAX_STEP:
                d = 0.0
        A += d
        a_list.append(A)
        prev_f, prev_g = f, g

    # ---------- 时钟 B：回费计数 ----------
    # 找锚点：锚点帧之前最后一段"cost 恒定且相位恒定"的稳定读数 → 用锚点帧的相位定基准
    g_of = {r['f']: r['bar_px'] / a.full * 30.0 for r in rows}
    idx = {r['f']: i for i, r in enumerate(rows)}
    g_anchor = g_of.get(a.anchor_frame)
    if g_anchor is None:
        print(f'★锚点帧 {a.anchor_frame} 无读数，改用最近有效帧')
        for off in range(1, 60):
            if g_of.get(a.anchor_frame + off) is not None:
                g_anchor = g_of[a.anchor_frame + off]
                break
    c0 = g_anchor - a.anchor_game          # 使 30*k + g - c0 在锚点处 = anchor_game

    k = 0.0
    prev_cost = None
    b_list = []
    events = []
    for i, r in enumerate(rows):
        if r['cost'] is not None and prev_cost is not None and r['cost'] != prev_cost:
            dc = r['cost'] - prev_cost
            if dc == 1:
                k += 1
                events.append((r['f'], prev_cost, r['cost'], dc, '自然回费'))
            elif dc > 1:
                events.append((r['f'], prev_cost, r['cost'], dc, '技能回费/其他'))
            else:
                events.append((r['f'], prev_cost, r['cost'], dc, '部署/撤退扣费'))
        if r['cost'] is not None:
            prev_cost = r['cost']
        b_list.append(30.0 * k + g_of[r['f']] - c0)

    # ---------- 段表 ----------
    segs = []
    cur = None
    for i, r in enumerate(rows):
        d = b_list[i] - b_list[i - 1] if i > 0 and rows[i]['f'] - rows[i - 1]['f'] == 1 else 0.0
        state = 'PAUSE' if d < 0.05 else ('RUN' if d < 1.6 else 'FAST')
        if cur is None or cur['state'] != state:
            if cur is not None:
                segs.append(cur)
            cur = {'state': state, 'f0': r['f'], 'f1': r['f'], 'A0': b_list[i], 'A1': b_list[i]}
        else:
            cur['f1'] = r['f']
            cur['A1'] = b_list[i]
    if cur is not None:
        segs.append(cur)

    with open(a.out, 'w', encoding='utf-8') as fh:
        for i, r in enumerate(rows):
            fh.write(json.dumps({'f': r['f'], 'px': r['bar_px'], 'g': round(g_of[r['f']], 3),
                                 'A': round(a_list[i], 3), 'B': round(b_list[i], 3),
                                 'cost': r['cost']}, ensure_ascii=False) + '\n')
    print(f'已写出 {a.out}（{len(rows)} 行）')
    print(f'锚点：视频帧 {a.anchor_frame} 相位 {g_anchor:.2f} ⇒ 游戏帧 {a.anchor_game}'
          f'（基准 c0={c0:.2f}）；检出回费事件 {sum(1 for e in events if e[4] == "自然回费")} 次')

    print('\n★段表（按游戏推进速度；只列 ≥10 帧的段）')
    print(f'{"状态":>6} {"起始":>7} {"结束":>7} {"帧数":>6} {"游戏帧起":>10} {"游戏帧止":>10} '
          f'{"游戏帧/视频帧":>13}')
    tot_run = 0.0
    for s in segs:
        n = s['f1'] - s['f0'] + 1
        if n < 10:
            continue
        ratio = (s['A1'] - s['A0']) / max(1, n)
        tot_run += s['A1'] - s['A0']
        print(f'{s["state"]:>6} {s["f0"]:>7} {s["f1"]:>7} {n:>6} {s["A0"]:>10.1f} '
              f'{s["A1"]:>10.1f} {ratio:>13.3f}')
    print(f'（以上段合计推进 {tot_run:.1f} 游戏帧）')

    print('\n★费用变化表（含类型判读）')
    print(f'{"视频帧":>7} {"游戏帧B":>9} {"费用":>12} {"差值":>6}  判读')
    for f, c0v, c1v, dc, kind in events:
        print(f'{f:>7} {b_list[idx[f]]:>9.1f} {str(c0v) + "->" + str(c1v):>12} {dc:>+6}  {kind}')

    print('\n★两时钟一致性（A 相位累加 vs B 回费计数）')
    print('  抽检点：')
    for t in (0, 400, 621, 4401, 4618, 5950, 5961, 8878, 10578):
        i = idx.get(t)
        if i is None:
            continue
        print(f'    视频帧 {t:>6}: A={a_list[i]:>8.1f}  B={b_list[i]:>8.1f}  '
              f'差(A-B)={a_list[i] - b_list[i]:>+8.1f}')

    if a.anchors:
        print('\n★指定帧的轴值')
        for t in (int(v) for v in a.anchors.split(',') if v.strip()):
            i = idx.get(t)
            if i is None:
                print(f'  视频帧 {t}: 无记录')
                continue
            print(f'  视频帧 {t} → B(游戏帧)={b_list[i]:.1f}  px={rows[i]["bar_px"]}'
                  f'  cost={rows[i]["cost"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
