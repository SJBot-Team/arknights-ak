# -*- coding: utf-8 -*-
"""test_pipeline.py — 任务流水线引擎的离线测试（用假采集器/假注入器，无需实机）

验证用户点名的三件事：
  A **配置驱动**：从 JSON 读入步骤（含 `_comment` 注释键）
  B **★步进优先**：`step_pause` 动作能被正确执行（先暂停再动作）
  C **MAA 的 next 语义**：next 为候选列表时，选"其 recognize 命中"的那一个；都不命中则兜底取第一个
另断言：动作后**用界面语义判生效**（不是像素差异）—— 测试里直接检查点击序列与最终界面。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.task.pipeline import Pipeline, Step, load_steps       # noqa: E402


class FakeCap:
    """按序列推进"界面名"。真实 Pipeline.grab() 只返回 image，
    所以 UiState 必须能从"最近一次采集"推断界面 —— 这里用共享状态模拟。"""

    def __init__(self, seq):
        self.seq = list(seq)
        self.i = 0
        self.cur_state = 'unknown'

    def grab(self):
        self.cur_state = self.seq[min(self.i, len(self.seq) - 1)]
        self.i += 1
        return type('F', (), {'image': np.zeros((4, 4, 3), 'uint8')})()


class FakeUi:
    def __init__(self, cap):
        self.cap = cap

    def classify(self, img):
        return {'state': self.cap.cur_state, 'hits': {}, 'start_point': None}


class FakeTap:
    def __init__(self):
        self.hits = []

    def __call__(self, x, y):
        self.hits.append((int(x), int(y)))


def case_a_json_roundtrip():
    cfg = {
        '_comment': '这是注释，应被忽略',
        'boot': {'recognize': {'always': True}, 'action': {'type': 'none'},
                 'next': ['battle'], 'desc': '起点'},
        'battle': {'recognize': {'state': 'battle'}, 'action': {'type': 'click', 'x': 1, 'y': 2},
                   'next': ['done']},
    }
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False)
        p = f.name
    steps = load_steps(p)
    os.unlink(p)
    ok = ('boot' in steps and 'battle' in steps and '_comment' not in steps
          and steps['battle'].action['x'] == 1)
    print(f'  {"OK " if ok else "BAD"} A 配置驱动（JSON + 注释键忽略）: 步骤={sorted(steps)}')
    return ok


def case_b_step_pause_first():
    """★步进优先：流水线在"到达战斗"后应先 step_pause（暂停），再继续。"""
    steps = {
        'boot': Step('boot', {'always': True}, {'type': 'none'}, ['battle']),
        'battle': Step('battle', {'state': 'battle'}, {'type': 'none'}, ['pause']),
        'pause': Step('pause', {'state': 'battle'}, {'type': 'step_pause', 'settle': 0.0},
                      ['done']),
    }
    cap, tap = FakeCap(['unknown', 'battle', 'battle', 'battle']), FakeTap(); ui = FakeUi(cap)
    pl = Pipeline(steps, cap, tap, ui, log=lambda *_: None, max_steps=8)
    end = pl.run('boot')
    # step_pause 的默认 tap 是暂停按钮 (1877,76)
    ok = end == 'done' and (1877, 76) in tap.hits
    print(f'  {"OK " if ok else "BAD"} B 步进优先：step_pause 执行 → 终态={end}，点击={tap.hits}')
    return ok


def case_c_next_candidates():
    """MAA 的 next 语义：候选里选"recognize 命中"的那个。"""
    steps = {
        'boot': Step('boot', {'always': True}, {'type': 'none'}, ['squad_path', 'viewport_path']),
        # 画面是 squad ⇒ 应走 squad_path（点开始行动），而不是 viewport_path（点演习）
        'squad_path': Step('squad_path', {'state': 'squad'}, {'type': 'click', 'x': 1655, 'y': 757},
                           ['done']),
        'viewport_path': Step('viewport_path', {'state': 'viewport'},
                              {'type': 'click', 'x': 1441, 'y': 983}, ['done']),
    }
    cap, tap = FakeCap(['squad', 'squad', 'squad']), FakeTap(); ui = FakeUi(cap)
    pl = Pipeline(steps, cap, tap, ui, log=lambda *_: None, max_steps=8)
    end = pl.run('boot')
    ok = end == 'done' and tap.hits == [(1655, 757)]
    print(f'  {"OK " if ok else "BAD"} C next 多候选：命中 squad_path → 点击={tap.hits}，终态={end}')
    return ok


def case_d_fallback_first():
    """候选都不命中时兜底取第一个（不中断流程）。"""
    steps = {
        'boot': Step('boot', {'always': True}, {'type': 'none'}, ['a', 'b']),
        'a': Step('a', {'state': 'battle'}, {'type': 'click', 'x': 10, 'y': 10}, ['done']),
        'b': Step('b', {'state': 'viewport'}, {'type': 'click', 'x': 20, 'y': 20}, ['done']),
    }
    cap, tap = FakeCap(['unknown'] * 4), FakeTap(); ui = FakeUi(cap)
    pl = Pipeline(steps, cap, tap, ui, log=lambda *_: None, max_steps=8)
    end = pl.run('boot')
    ok = end == 'done' and tap.hits == [(10, 10)]
    print(f'  {"OK " if ok else "BAD"} D 候选全不命中 → 兜底第一个：点击={tap.hits}')
    return ok


def case_e_until_semantics():
    """until 语义：命中目标界面即返回（用于"进到战斗就停"）。"""
    steps = {
        'boot': Step('boot', {'always': True}, {'type': 'none'}, ['battle']),
        'battle': Step('battle', {'state': 'battle'}, {'type': 'none'}, ['done']),
    }
    cap, tap = FakeCap(['unknown', 'battle']), FakeTap(); ui = FakeUi(cap)
    pl = Pipeline(steps, cap, tap, ui, log=lambda *_: None, max_steps=8)
    end = pl.run('boot', until={'battle'})
    ok = (end == 'battle')
    print(f'  {"OK " if ok else "BAD"} E until 语义：进入 battle 即返回 → {end}')
    return ok


def main():
    print('任务流水线引擎离线测试：')
    res = [case_a_json_roundtrip(), case_b_step_pause_first(), case_c_next_candidates(),
           case_d_fallback_first(), case_e_until_semantics()]
    print(f'汇总: 流水线 A/B/C/D/E {"全部 PASS" if all(res) else "存在失败"}')
    return 0 if all(res) else 1


if __name__ == '__main__':
    raise SystemExit(main())
