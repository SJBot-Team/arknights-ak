# -*- coding: utf-8 -*-
"""grid_px.py — ★**格点 ↔ 像素 唯一真源**（实机标定，已用出怪格子与地图数据交叉验证）。

## 结论（2026-09-15 修正）
```
x(col) = 559 + 124.5 · col          # ★x 随 col **递增**（此前写反成递减，导致 D6/D4 互换）
y(row) = 502 + 138   · (row − 3)    # row 0 在**屏幕上方**
```
- 1920×1080 帧坐标；基准来自 1-1 实机暂停态选卡的**绿格集合**。
- **列方向的决定性证据**：关卡 `routes` 的 `startPosition`/`endPosition`（出怪格子）——
  route1 = `(row3,col0) → (row3,col8)`，而实机敌人**自左向右**移动 ⇒ **x 必须随 col 递增**；
  另有 `tile_start` = (0,4)/(3,0)、`tile_end` = (3,8)/(6,5) 佐证。
- **列原点的决定性证据**：绿格额外格位于 (1057,364)，即"与 6 连排同列、上一行"的某个 road 格；
  1-1 中只有 **col 4** 在 r1/r2 是 road ⇒ `(1057 − 4×124.5) = 559` = col 0 的像素。

## 校验（写成断言，回归时可跑）
- 6 连绿格 x = 807/932/1057/1181/1306/1431 ⇒ 本映射给出 **col 2..7** = 808/932.5/1057/1181.5/1306/1430.5 ✓
- 额外绿格 (1057,364) ⇒ 本映射给出 **(row2, col4) = (1057, 364)** ✓ 且 r2c4 确为 road ✓
- **D6 = (row3,col5) → (1181.5, 502)**、**D4 = (row3,col3) → (932.5, 502)**

## 与 PRTS+ 的 Excel 宏表口径对齐（★2026-09-15 用户更正）
**用户明确**：PRTS+ 的格子表与用户给的标定表都遵守 ——
**「列：左到右，从 1 开始」**；**「行：下到上，从 A 开始」**。

⇒ 字母 A = **屏幕最下方**那一行；数字 1 = **屏幕最左**那一列。
而本项目的 `grid_px` 内部用的是 **mapData 行**（自上而下：row 0 在屏幕上方）。
两者的换算：`row_mapdata = (rows − 1) − (letter_index)`，即 **`rc_rowflip`**（不是 `rc_normal`！）。

> 本项目此前误用 `rc_normal`（把 A 当作屏幕最上方）—— 1-1 是 7 行、且标定只用中间行 **D**，
> 翻转前后 D 都落在 row 3，**故未暴露**；换 9 行（如 h12-4）或用到非中间行即会出错。
> 校验：`D6 → mapData(row3,col5)`（不变）；**`F4 → row1`（屏幕上方）**、**`B4 → row5`（屏幕下方）**。
"""
from __future__ import annotations

# ---- 标定常数（1920×1080 帧坐标）----
X0, COL_PX = 559.0, 124.5        # x = X0 + COL_PX * col（col 左→右递增，1 起）
ROW3_Y, ROW_PX = 502.0, 138.0    # y = ROW3_Y + ROW_PX * (row_mapdata - 3)（row_mapdata 自上而下）
# ★Excel 宏表口径：行「下到上从 A」⇒ 需要 rowflip 才能变成 mapData 行
COORD_TRANSFORM = 'rc_rowflip'

# 绿格实测（用于自检）
GREEN_ROW_Y = 502
GREEN_X = [807, 932, 1057, 1181, 1306, 1431]
GREEN_EXTRA = (1057, 364)
GREEN_EXTRA_RC = (2, 4)

ROAD_1_1 = [(1, 4), (2, 4), (3, 1), (3, 2), (3, 3), (3, 4), (3, 5), (3, 6), (3, 7),
            (4, 5), (5, 5)]


def cell_to_px(row: float, col: float) -> tuple[int, int]:
    """格 (row, col) → 帧像素 (x, y)。"""
    x = X0 + COL_PX * float(col)
    y = ROW3_Y + ROW_PX * (float(row) - 3)
    return int(round(x)), int(round(y))


def px_to_cell(x: float, y: float) -> tuple[float, float]:
    """帧像素 (x, y) → 格 (row, col)（浮点，便于观察偏差）。"""
    col = (float(x) - X0) / COL_PX
    row = 3.0 + (float(y) - ROW3_Y) / ROW_PX
    return round(row, 2), round(col, 2)


def coord_letters_to_rc(coord: str, rows: int = 7, cols: int = 9,
                        transform: str = COORD_TRANSFORM) -> tuple[int, int]:
    """Excel 宏表格子（如 `D6`）→ **mapData 行/列**。

    ★口径（用户 2026-09-15 更正）：**列左→右从 1**、**行下→上从 A**；
    本函数默认 `rc_rowflip` 把"字母（自下而上）"换算成"mapData 行（自上而下）"。
    """
    try:
        from ak_sim_axis_compat import coord_to_rc as _c
        return _c(coord, rows, cols, transform)
    except Exception:                                            # noqa: BLE001
        pass
    s = coord.strip().upper()
    letters = ''.join(ch for ch in s if ch.isalpha())
    digits = ''.join(ch for ch in s if ch.isdigit())
    li = 0
    for ch in letters:
        li = li * 26 + (ord(ch) - ord('A') + 1)
    li -= 1
    ni = int(digits) - 1
    r, c = li, ni
    if transform in ('rc_rowflip', 'rc_bothflip', 'cr_rowflip', 'cr_bothflip'):
        r = (rows - 1) - r
    if transform in ('rc_colflip', 'rc_bothflip', 'cr_colflip', 'cr_bothflip'):
        c = (cols - 1) - c
    if transform.startswith('cr_'):
        r, c = c, r
    return r, c


def coord_to_px(coord: str, rows: int = 7, cols: int = 9) -> tuple[int, int]:
    """Excel 宏表格子（如 `D6`）→ 帧像素。"""
    r, c = coord_letters_to_rc(coord, rows, cols)
    return cell_to_px(r, c)


# ---- 朝向：拖拽方向 = 从格中心指向相邻格中心 ----
# 与格轴一致：**左 = col−1（x −124.5）**、**右 = col+1**、**上 = row−1（y −138）**、**下 = row+1**。
# 已由"芬 D6 朝左、攻击范围含 (3,4)"验证（col4 在 col5 的屏幕左侧）。
DIR_DELTA = {                      # (Δrow, Δcol)
    '左': (0, -1), 'left': (0, -1), 'l': (0, -1),
    '右': (0, +1), 'right': (0, +1), 'r': (0, +1),
    '上': (-1, 0), 'up': (-1, 0), 'u': (-1, 0),
    '下': (+1, 0), 'down': (+1, 0), 'd': (+1, 0),
}


def dir_to_px(cell: tuple[int, int], direction: str) -> tuple[int, int]:
    """给定格像素与朝向，返回**朝向拖拽的目标点**（相邻格中心）。

    用户指点：「先拖拽，松手后**再拖拽朝向**，松手部署」⇒ 第二段拖拽的终点即本函数返回值。
    """
    d = DIR_DELTA.get(str(direction).strip().lower()) or DIR_DELTA.get(str(direction).strip())
    if d is None:
        d = DIR_DELTA['右']
    r, c = px_to_cell(*cell)
    return cell_to_px(round(r) + d[0], round(c) + d[1])


def deploy_px(coord: str, direction: str = '右', rows: int = 7,
              cols: int = 9) -> tuple[tuple[int, int], tuple[int, int]]:
    """Excel 格子 + 朝向 → `(格像素, 朝向拖拽点像素)`，直接喂给 `Deployer.deploy_two_step_px`。"""
    cell = coord_to_px(coord, rows, cols)
    return cell, dir_to_px(cell, direction)


def self_check() -> list[tuple[str, bool, str]]:
    """自检：绿格重投影 + 出怪格子方向 + D6/D4。"""
    out = []
    for i, gx in enumerate(GREEN_X):
        col = 2 + i
        px = cell_to_px(3, col)
        out.append((f'绿格 col{col} → 实测 x={gx}', abs(px[0] - gx) <= 3, f'映射得 {px[0]}'))
    px = cell_to_px(*GREEN_EXTRA_RC)
    out.append((f'额外绿格 {GREEN_EXTRA_RC} → 实测 {GREEN_EXTRA}', 
                abs(px[0] - GREEN_EXTRA[0]) <= 3 and abs(px[1] - GREEN_EXTRA[1]) <= 3,
                f'映射得 {px}'))
    out.append(('额外绿格落在 road 集合内', GREEN_EXTRA_RC in ROAD_1_1, str(GREEN_EXTRA_RC)))
    # 出怪方向：route1 (3,0)→(3,8) 应 x 递增
    x0 = cell_to_px(3, 0)[0]
    x8 = cell_to_px(3, 8)[0]
    out.append(('★route1 (3,0)→(3,8) 的 x 递增（与实机敌人向右移动一致）', x8 > x0,
                f'{x0} → {x8}'))
    d6 = coord_to_px('D6')
    d4 = coord_to_px('D4')
    out.append(('★D6 = (row3,col5) → (1181.5,502)', d6 == (1182, 502) or abs(d6[0] - 1182) <= 2,
                str(d6)))
    out.append(('★D4 = (row3,col3) → (932.5,502)', d4 == (932, 502) or abs(d4[0] - 932) <= 2,
                str(d4)))
    # ★字母"下→上从 A"：F 应在上方（y 小）、B 应在下方（y 大）
    f4 = coord_to_px('F4')
    b4 = coord_to_px('B4')
    out.append(('★字母自下而上：F4 在屏幕上方（y 小）', f4[1] < 400, f'F4={f4}'))
    out.append(('★字母自下而上：B4 在屏幕下方（y 大）', b4[1] > 650, f'B4={b4}'))
    a6 = coord_to_px('A6')
    out.append(('★A = 最下面一行（y 最大）', a6[1] >= 900, f'A6={a6}'))
    return out


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print(f'映射：x = {X0} + {COL_PX}·col ； y = {ROW3_Y} + {ROW_PX}·(row−3)')
    print(f'Excel 口径：{COORD_TRANSFORM}（字母=行 A→row0；数字=列 1→col0）\n')
    bad = 0
    for name, ok, detail in self_check():
        print(f'  {"✅" if ok else "❌"} {name}  — {detail}')
        bad += 0 if ok else 1
    print()
    for c in ('D6', 'D4', 'F4'):
        r, cc = coord_letters_to_rc(c)
        print(f'  {c} → (row {r}, col {cc}) → 像素 {cell_to_px(r, cc)}')
    print('\n  朝向拖拽点（两段式的第二段终点）:')
    for c, d in (('D6', '左'), ('D4', '上'), ('D6', '右')):
        cell, dp = deploy_px(c, d)
        print(f'    {c} 朝{d}: 格 {cell} → 拖向 {dp}')
    raise SystemExit(1 if bad else 0)
