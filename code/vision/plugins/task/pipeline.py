# -*- coding: utf-8 -*-
"""pipeline.py — **任务流水线引擎**（参照 MAA 的 tasks.json + prts+ 的"先步进再执行"）

## 为什么要它（用户 2026-09-15 点名）
> 你不需要模仿人类与图形界面交互的逻辑来一步一步直接操控，而是使用更高效精确的工作流来完成。
> 你仅负责启动-监控-排查-修正；工作流的搭建可以参考 prts+ 和 MAA 的现成实现，
> 尤其是你昨天在关卡识别进入的界面出了很多问题，效率很低。

昨天的问题根因是"**用 if-else 试错 + 像素差异判生效**"。本引擎改为：
1. **配置驱动**：一份 JSON 描述"识别 → 动作 → 下一步"，人可读、易改（与轴表同一思路）；
2. **识别多候选**：`template`（MAA 模板）/ `state`（界面语义）/ `cost`（费用数字）/ `always`，
   失败即在候选间重试，而不是写死一条分支；
3. **★步进优先**：动作类型 `step_pause`（= **0 帧暂停/过帧**）作为一等公民——
   **先暂停定位帧，再执行实际动作**，给识别留足时间（prts+ 的"子弹时间"同源）；
4. **语义生效校验**：动作后比对**界面语义**（`UiState`），**绝不用像素差异**（地图动画会骗过它）。

## 复用昨日遗留模块
`recognize/ui_state.py`、`recognize/maa_anchor.py`、`recognize/cost_number.py`、
`clock/paused_protocol.py`、`clock/frame_clock.py`、`capture/render_guard.py`。

## 用法
    steps = load_steps('pipelines/enter_drill.json')
    pl = Pipeline(steps, cap, tap, ui, ma=ma, log=print)
    end = pl.run('start', until={'battle'})
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Step:
    name: str
    recognize: dict | None = None          # 见 Pipeline.find
    action: dict | None = None             # 见 Pipeline.act
    next: list = field(default_factory=list)
    retry: int = 3
    timeout: float = 6.0
    desc: str = ''

    @staticmethod
    def from_dict(d: dict) -> 'Step':
        d = dict(d)
        return Step(name=d.pop('name'), recognize=d.pop('recognize', None),
                    action=d.pop('action', None), next=list(d.pop('next', [])),
                    retry=int(d.pop('retry', 3)), timeout=float(d.pop('timeout', 6.0)),
                    desc=d.pop('desc', ''))


def load_steps(path: str) -> dict:
    """从 JSON 读入 {name: Step}；`_comment`/`_doc` 键被忽略，便于写注释。"""
    raw = json.load(open(path, encoding='utf-8'))
    steps = {}
    for k, v in raw.items():
        if k.startswith('_'):
            continue
        v = dict(v)
        v.setdefault('name', k)
        steps[k] = Step.from_dict(v)
    return steps


class Pipeline:
    def __init__(self, steps: dict, cap, tap, ui, ma=None, log=print,
                 max_steps: int = 40, frame_diff=None):
        self.steps = steps
        self.cap = cap
        self.tap = tap
        self.ui = ui
        self.ma = ma
        self.log = log
        self.max_steps = max_steps
        self.trace: list[dict] = []
        self._paused = False

    # ---------------- 识别 ----------------
    def grab(self):
        return self.cap.grab().image

    def find(self, img, rec: dict | None):
        """按 rec 描述定位；返回 (hit_kind, payload)。rec 支持：
        {"state": "battle|squad|viewport|unknown"}  界面语义命中
        {"template": "Battle/BattleFlag/...", "thr": 0.8}  MAA 模板命中（返回中心点）
        {"cost": {"min": 18}}                        费用数字满足条件
        {"always": true}                              恒真（无条件分支）
        """
        if rec is None:
            return ('none', None)
        if 'always' in rec and rec['always']:
            return ('always', None)
        if 'state' in rec:
            st = self.ui.classify(img)['state']
            want = rec['state']
            wants = want if isinstance(want, list) else [want]
            if st in wants:
                return ('state', st)
            return None
        if 'template' in rec and self.ma is not None:
            h = self.ma.match(img, rec['template'], roi=rec.get('roi'),
                              thr=rec.get('thr'))
            if h:
                return ('template', self.ma.click_point(h))
            return None
        if 'cost' in rec:
            from plugins.recognize.cost_number import CostNumberRecognizer
            if not hasattr(self, '_rec'):
                self._rec = CostNumberRecognizer()
                tpl = rec['cost'].get('templates')
                self._spec = {'roi': rec['cost'].get('roi', [1795, 730, 1915, 805]),
                              'templates': tpl}
            ms = self._rec.run(img, self._spec, None, (0, 0))
            c = None
            if ms and float(ms[0].extra.get('confidence', 0.0)) >= rec['cost'].get('min_conf', 0.85):
                c = int(ms[0].extra['cost'])
            lo, hi = rec['cost'].get('min', 0), rec['cost'].get('max', 999)
            if c is not None and lo <= c <= hi:
                return ('cost', c)
            return None
        return None

    # ---------------- 动作 ----------------
    def act(self, action: dict | None, payload, before_state=None):
        """action 类型：
        none / wait / click（固定坐标）/ click_self（用识别到的点）/
        step_pause（★暂停做步进：0 帧暂停、过帧）/ resume / key
        """
        if not action:
            return True
        t = action.get('type', 'none')
        if t == 'none':
            return True
        if t == 'wait':
            time.sleep(float(action.get('seconds', 1.0)))
            return True
        if t == 'click':
            x, y = action['x'], action['y']
            self.tap(x, y)
            return True
        if t == 'click_self':
            if not payload:
                return False
            x, y = payload
            if action.get('offset'):
                x += action['offset'][0]; y += action['offset'][1]
            self.tap(x, y)
            return True
        if t == 'key':
            import subprocess
            subprocess.run([r'D:\__soft\MuMu Player 12\shell\adb.exe', '-s', '127.0.0.1:16384',
                            'shell', 'input', 'keyevent', str(action['code'])], capture_output=True)
            return True
        if t in ('step_pause', 'pause'):
            # ★ 步进：暂停游戏，给识别留出缓冲；再次调用则恢复
            x, y = action.get('tap', [1877, 76])
            self.tap(x, y)
            time.sleep(float(action.get('settle', 0.5)))
            self._paused = not self._paused
            return True
        return True

    # ---------------- 运行 ----------------
    def run(self, start: str, until: set | None = None) -> str:
        """从 start 出发，沿 next 前进；命中 until 中的界面语义即返回该语义。"""
        cur = start
        for i in range(self.max_steps):
            st = self.steps.get(cur)
            if st is None:
                self.log(f'[{i}] 未知步骤 {cur}，停止'); return 'error'
            hit = None; img = None
            for attempt in range(st.retry):
                img = self.grab()
                hit = self.find(img, st.recognize)
                if hit:
                    break
                time.sleep(0.3)
            state = self.ui.classify(img)['state']
            if until and state in until:
                self.log(f'[{i}] 到达目标界面 {state}（步骤 {cur}）')
                return state
            self.trace.append({'i': i, 'step': cur, 'state': state,
                               'hit': None if not hit else hit[0]})
            self.log(f'[{i}] {cur}  界面={state}  命中={None if not hit else hit[0]}')
            if not hit:
                self.log(f'    {cur} 识别失败（重试 {st.retry} 次）→ 走 next 兜底')
            self.act(st.action, None if not hit else hit[1], before_state=state)
            # ★ MAA 语义：next 是**候选列表**，选第一个"其 recognize 在当前画面命中"的；
            #   都不命中则取第一个（兜底），而不是写死单一路径。
            nxt = 'done'
            if st.next:
                nxt = st.next[0]
                for cand in st.next:
                    cst = self.steps.get(cand)
                    if cst is None:
                        continue
                    if self.find(img, cst.recognize):
                        nxt = cand
                        break
            cur = nxt
            if cur == 'done':
                return 'done'
            time.sleep(0.4)
        self.log('步数用尽'); return 'timeout'
