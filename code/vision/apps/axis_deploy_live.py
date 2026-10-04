# -*- coding: utf-8 -*-
"""axis_deploy_live.py — ★**按共用轴表在实机部署**（轴表 → 格像素 → 两段式拖拽）。

## 链路（目标②的关键闭环）
`ak/axis/1-1.yaml` 的 `deploys[].cell`（Excel 宏表格子，如 `D6`）+ `dir`（如 `左`）
  → `plugins/action/grid_px.coord_to_px / dir_to_px`（**唯一真源**，已用出怪格子+绿格三重互证）
  → `Deployer.deploy_two_step_px`（**两段式**：拖到格松手 → 拖朝向松手）
  → 以**费用下降量**验证提交（芬 8 费 ⇒ 费用应 −8）。

## 用法
    python apps/axis_deploy_live.py [轴表名=1-1] [--index 0] [--real]
前两个部署分别对应轴表里的 `deploys[0]`（芬@D6 左）与 `deploys[1]`（月见夜@D4 上）。

安全：仅界面级拖拽与截图；演习不消耗理智；自动导航进关（1-1 演习）。
"""
from __future__ import annotations

import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                      # noqa: E402
from plugins.action.grid_px import deploy_px                    # noqa: E402
from plugins.action.win_input import WinInput                   # noqa: E402
from plugins.capture.emu_window import make_capture             # noqa: E402
from plugins.recognize.battle_hud import BattleHudGate          # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer   # noqa: E402
import nav_to_drill                                             # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
AXIS_DIR = r'C:\Users\23922\Documents\ds_harness\ak\axis'


def read_cost(cap, num):
    fr = cap.grab()
    spec = {'roi': [1795, 730, 1915, 805]}
    if os.path.exists(TPL):
        spec['templates'] = TPL
    ms = num.run(fr.image, spec, None, fr.origin)
    return int(ms[0].extra['cost']) if ms else None


def read_card_cost(cap, num, cx, cy=1007):
    """读某张卡片上方的**费用数字**（卡片按费用升序排列，故按费用选卡最可靠）。"""
    fr = cap.grab()
    spec = {'roi': [int(cx) - 34, int(cy) - 110, int(cx) + 34, int(cy) - 60]}
    if os.path.exists(TPL):
        spec['templates'] = TPL
    ms = num.run(fr.image, spec, None, fr.origin)
    return int(ms[0].extra['cost']) if ms else None


def find_card_by_cost(cap, dep, num, want):
    """在卡片行里找**显示费用 == want** 的卡片中心。"""
    cards = sorted(dep.find_cards(img=cap.grab().image) or [], key=lambda k: k['cx'])
    rows = []
    for c in cards:
        v = read_card_cost(cap, num, c['cx'], c['cy'])
        rows.append((c['cx'], c['cy'], v))
    print('  卡片费用读数:', [(x, v) for x, _, v in rows])
    hit = next((r for r in rows if r[2] == want), None)
    return ((hit[0], hit[1]) if hit else None), rows


def load_card_plan():
    """读 `ak/data/derived/card_plan.json`（由 `sim/draft/card_index.py --export` 生成）。

    结构性方案：卡片行**按费用升序**，已部署干员的卡片会**从行内移除**
    ⇒ 目标干员的卡片序号 = 其在"未部署成员按费用升序"中的位次（**无需任何图像识别**）。
    """
    import json
    p = r'C:\Users\23922\Documents\ds_harness\ak\data\derived\card_plan.json'
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding='utf-8'))


def card_index_for(plan: dict, op_name: str, deployed: set) -> int | None:
    rest = [nm for nm in (plan.get('order') or []) if nm not in deployed]
    return rest.index(op_name) if op_name in rest else None


def fit_card_grid(cxs, n, row_left=66.0, row_right=1880.0):
    """★由"检测到的卡段中心 + 卡片总数 n"拟合**均匀网格**，补全漏检的卡片。

    为什么需要：`find_cards` 的分段依赖梯度/亮度，**会漏检或合并**（实测 10 张只检出 7 张）
    ⇒ 直接按"第 idx 个检测段"取卡会**错位**。卡片行是**等间距**的，
    故用"行列范围 + 张数"解析出每个中心：`pitch = (right − left) / n`，
    `center_i = left + pitch·(i + 0.5)`；再用检测值做**最小二乘微调**（若检测数 ≥ 3）。
    """
    if n <= 0:
        return []
    # 若有检测值，用其首末做一次线性拟合（更贴合实际布局）
    if len(cxs) >= 3:
        xs = sorted(cxs)
        # 以"均匀网格"为初值，把检测值分配到最近格点后线性回归
        pitch0 = (row_right - row_left) / n
        left0 = row_left
        idxs = [int(round((x - left0 - pitch0 / 2) / pitch0)) for x in xs]
        pairs = [(i, x) for i, x in zip(idxs, xs) if 0 <= i < n]
        if len(pairs) >= 3:
            import numpy as np
            A = np.array([[i, 1.0] for i, _ in pairs])
            b = np.array([x for _, x in pairs])
            pitch, left = np.linalg.lstsq(A, b, rcond=None)[0]
        else:
            pitch, left = pitch0, left0
    else:
        pitch = (row_right - row_left) / n
        left = row_left
    return [int(round(left + pitch * (i + 0.5))) for i in range(n)]


def main() -> int:
    import yaml
    name = next((a for a in sys.argv[1:] if not a.startswith('-')), '1-1')
    idx = int(sys.argv[sys.argv.index('--index') + 1]) if '--index' in sys.argv else 0
    use_real = '--real' in sys.argv

    ax = yaml.safe_load(open(os.path.join(AXIS_DIR, f'{name}.yaml'), encoding='utf-8'))
    d = (ax.get('deploys') or [])[idx]
    coord, direction, cost_need = d['cell'], d.get('dir', '右'), d.get('cost')
    print(f"轴表 {name} deploys[{idx}]: {d.get('op')} @ {coord} 朝{direction} 费用 {cost_need}")

    cell, dirpt = deploy_px(coord, direction)
    print(f'  格像素 = {cell}；朝向拖拽点 = {dirpt}')

    cap = make_capture('adb')
    dep, gate, num, wi = Deployer(cap), BattleHudGate(), CostNumberRecognizer(), WinInput()
    if not gate.check(cap.grab().image)['in_battle']:
        print('不在战斗 → 自动导航')
        if nav_to_drill.main() != 0:
            return 1

    # 攒够费用（部署需 cost ≥ 该干员费用）
    c = read_cost(cap, num)
    print(f'当前费用 = {c}')
    if c is None or (cost_need and c < cost_need):
        wi.post_key('f')                                  # 恢复运行
        time.sleep(0.4)
        t0 = time.time()
        while time.time() - t0 < 90:
            c = read_cost(cap, num)
            if c is not None and cost_need and c >= cost_need:
                break
            time.sleep(0.2)
        wi.post_key('f')                                  # 暂停
        time.sleep(0.6)
        print(f'攒费后（已暂停）费用 = {c}')

    # ★卡片定位：**头像识别快速通道**（单次截屏），失败再退回"名称 OCR 自校验扫描"
    from card_select import select_card_by_avatar, select_card_by_name
    plan = load_card_plan()
    op_name = d.get('op')
    deployed = set()
    if '--deployed' in sys.argv:
        deployed = set(sys.argv[sys.argv.index('--deployed') + 1].split(','))
    predict = card_index_for(plan, op_name, deployed) if plan else None
    print(f'费用预测位次 = {predict}')
    card = select_card_by_avatar(cap, dep, op_name, plan=plan, deployed=deployed,
                                 squad=list(plan['squad'].keys()) if plan else None)
    if card is not None:
        print(f'★头像识别命中「{op_name}」⇒ 卡片中心 {card}')
    else:
        print('头像识别未命中 → 退回"名称 OCR 自校验扫描"')
        card = select_card_by_name(cap, dep, op_name, plan=plan, deployed=deployed,
                                   try_first=predict, cancel_at=(960, 880))
    if card is None:
        print(f'⚠️ 两种识别均未确认「{op_name}」的卡片 → 回退第 1 张')
        cards = sorted(dep.find_cards(img=cap.grab().image) or [], key=lambda k: k['cx'])
        card = (cards[0]['cx'], cards[0]['cy']) if cards else (230, 1007)
    print(f'目标卡中心 = {card}')

    c0 = read_cost(cap, num)
    r = dep.deploy_two_step_px(card, cell, dirpt, use_real_mouse=use_real)
    time.sleep(1.4)
    c1 = read_cost(cap, num)
    cv2.imwrite(os.path.join(TMP, f'axisdep_{coord}.png'), cap.grab().image)
    print(f'执行 {r}')
    print(f'费用 {c0} → {c1}（应下降 {cost_need}）')
    ok = (c0 is not None and c1 is not None and cost_need and (c0 - c1) >= cost_need - 1)
    print('✅ **按轴表部署成功**' if ok else '⚠️ 未见费用按预期下降，请查看截图')
    print(f'截图: {TMP}\\axisdep_{coord}.png')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
