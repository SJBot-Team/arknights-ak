# -*- coding: utf-8 -*-
"""test_nav_flow.py — 导航状态机自检（合成"屏幕序列"，无需游戏）

覆盖：
  A. 正常流程：3 步依次「找到按钮 → 点击 → 等到下一个界面」全部通过
  B. 找不到模板：重试后用尽 → 中止（不继续瞎点）
  C. 合规拒绝：步骤名/模板名含登录或挪用资产界面关键词 → 加载期直接拒绝
  D. dry-run 不点击：dry_run=True 时注入后端调用次数为 0
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import numpy as np          # noqa: E402
import cv2                  # noqa: E402

from kernel.registry import TASKS, load_plugins    # noqa: E402

TDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.tmp_tpl')


class Frame:
    def __init__(self, img, origin=(0, 0)):
        self.image = img
        self.origin = origin
        self.shape = img.shape


class MockEngine:
    """按脚本返回屏幕：每次 grab() 推进一帧（可重复同一屏）。"""

    def __init__(self, screens, repeat=2):
        self.screens = screens
        self.repeat = repeat
        self.i = 0
        self.k = 0
        self.clicks = []
        self.config = {}
        self.ctx = None
        self.input = self

    def grab(self):
        img = self.screens[min(self.i, len(self.screens) - 1)]
        self.k += 1
        if self.k >= self.repeat:
            self.k = 0
            self.i += 1
        return Frame(img)

    def click(self, x, y, **kw):
        self.clicks.append((x, y))

    def recognize(self, *a, **kw):
        return []


def make_tpl(name, color, size=(40, 90)):
    os.makedirs(TDIR, exist_ok=True)
    img = np.zeros((size[0], size[1], 3), dtype=np.uint8)
    img[:, :] = color
    cv2.rectangle(img, (4, 4), (size[1] - 5, size[0] - 5), (255, 255, 255), 2)
    p = os.path.join(TDIR, name + '.png')
    cv2.imwrite(p, img)
    return p


def screen_with(tpl_name, pos=(300, 200)):
    """生成一张"含某模板"的屏幕。"""
    img = np.full((720, 1280, 3), 30, dtype=np.uint8)
    tpl = cv2.imread(os.path.join(TDIR, tpl_name + '.png'))
    h, w = tpl.shape[:2]
    x, y = pos
    img[y:y + h, x:x + w] = tpl
    return img


def test_normal_flow():
    print('=== A. 正常流程（3 步）===')
    make_tpl('btn_start', (60, 60, 200))
    make_tpl('scr_battle', (200, 60, 60))
    make_tpl('btn_deploy', (60, 200, 60))
    screens = [screen_with('btn_start'), screen_with('scr_battle'), screen_with('btn_deploy')]
    eng = MockEngine(screens, repeat=2)
    cfg = {'nav_flow': {'templates': TDIR, 'dry_run': False, 'thresh': 0.8, 'steps': [
        {'name': '进入战斗', 'find': 'btn_start', 'expect': 'scr_battle', 'timeout': 3, 'retries': 1},
        {'name': '点击部署', 'find': 'btn_deploy', 'timeout': 3, 'retries': 1},
    ]}}
    eng.config = cfg
    res = TASKS['nav_flow']().run(eng)
    print(f'  ok={res["ok"]} done={res["done"]}/{res["total"]} 点击={len(eng.clicks)} 次')
    for r in res['steps']:
        print(f'    {r["step"]}: {"OK" if r["ok"] else "FAIL"}（{r["tries"]} 次）')
    ok = res['ok'] and res['done'] == 2 and len(eng.clicks) >= 2
    print(f'  {"PASS" if ok else "FAIL"}')
    return ok


def test_timeout_abort():
    print('\n=== B. 找不到模板 → 重试后中止 ===')
    screens = [np.full((720, 1280, 3), 30, dtype=np.uint8)]      # 空白屏：什么都不含
    eng = MockEngine(screens, repeat=1)
    eng.config = {'nav_flow': {'templates': TDIR, 'dry_run': False, 'steps': [
        {'name': '找不到的按钮', 'find': 'btn_start', 'timeout': 0.6, 'retries': 1}]}}
    res = TASKS['nav_flow']().run(eng)
    print(f'  ok={res["ok"]} aborted={res["aborted"]} 点击={len(eng.clicks)} 次（应为 0）')
    ok = (not res['ok']) and res['aborted'] and len(eng.clicks) == 0
    print(f'  {"PASS" if ok else "FAIL"}')
    return ok


def test_compliance_reject():
    print('\n=== C. 合规拒绝（登录 / 挪用资产界面）===')
    cases = [
        ('登录账号', 'btn_login'),
        ('打开仓库', 'btn_depot'),
        ('去抽卡', 'btn_gacha'),
        ('购买礼包', 'btn_shop'),
    ]
    ok = 0
    for name, tpl in cases:
        eng = MockEngine([np.zeros((10, 10, 3), dtype=np.uint8)])
        eng.config = {'nav_flow': {'templates': TDIR, 'dry_run': True, 'steps': [
            {'name': name, 'find': tpl, 'timeout': 0.2, 'retries': 0}]}}
        res = TASKS['nav_flow']().run(eng)
        good = (res.get('error') == 'compliance_rejected')
        ok += good
        print(f'  {name:<10} → {"已拒绝" if good else "未拒绝(!) "} '
              f'{res.get("detail", "")[:40]}')
    print(f'  通过 {ok}/{len(cases)}')
    return ok == len(cases)


def test_dry_run_no_click():
    print('\n=== D. dry-run 不注入 ===')
    screens = [screen_with('btn_start')]
    eng = MockEngine(screens, repeat=2)
    eng.config = {'nav_flow': {'templates': TDIR, 'dry_run': True, 'thresh': 0.8, 'steps': [
        {'name': '进入战斗', 'find': 'btn_start', 'timeout': 2, 'retries': 0}]}}
    res = TASKS['nav_flow']().run(eng)
    print(f'  ok={res["ok"]} 点击={len(eng.clicks)} 次（应为 0）')
    ok = res['ok'] and len(eng.clicks) == 0
    print(f'  {"PASS" if ok else "FAIL"}')
    return ok


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    load_plugins(os.path.join(ROOT, 'plugins'))
    res = {'A_normal': test_normal_flow(), 'B_timeout': test_timeout_abort(),
           'C_compliance': test_compliance_reject(), 'D_dry_run': test_dry_run_no_click()}
    print('\n汇总: ' + '  '.join(f'{k}={"PASS" if v else "FAIL"}' for k, v in res.items()))
    sys.exit(0 if all(res.values()) else 1)
