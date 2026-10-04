"""导航流程任务（task: nav_flow）—— 需求 2.6「自动启动 → 选关 → 选人出战」的状态机骨架

设计原则（合规优先）：
  * **只做"点界面"**：每一步是「等模板出现 → 点它 → 等预期模板出现」，不读写游戏文件、不碰内存；
  * **登录不在本任务内**：模板/步骤名中若出现登录相关关键词，**加载期直接拒绝**（见 `FORBIDDEN`）；
  * **禁止界面**：仓库/基建/抽卡/商店/邮件/养成/模组等关键词的步骤同样在加载期拒绝；
  * **失败即停**：超时或找不到模板 → 立即中止并报告，不做"猜着点"的动作。

配置（engine.config['nav_flow']）：
  steps      步骤列表，每步：
               {name, find: 模板名, expect: 模板名(可选), click: true|false,
                offset: [dx,dy](可选), timeout: 秒, retries: 次数, wait_after: 秒}
  templates  模板目录（PNG，文件名即模板名，可带 .png 后缀省略）
  thresh     模板匹配阈值（默认 0.85）
  dry_run    true=只走状态机不点击（默认 true）

返回 {ok, done, steps: [...每步结果...], aborted}
"""
from __future__ import annotations

import os
import time

from kernel.registry import task

# 合规：这些关键词出现在步骤名/模板名里一律拒绝（登录 + 动用虚拟资产的界面）
FORBIDDEN = ('login', 'signin', 'sign_in', 'account', '登录', '登入', '换号',
             '仓库', '基建', '抽卡', '寻访', '商店', '商城', '邮件', '邮箱',
             '养成', '精英化', '技能升级', '模组', '购买', '领取')


def _forbidden(text: str) -> str | None:
    low = (text or '').lower()
    for kw in FORBIDDEN:
        if kw in low or kw in (text or ''):
            return kw
    return None


@task("nav_flow")
class NavFlow:
    def run(self, engine) -> dict:
        cfg = (engine.config or {}).get('nav_flow', {}) if engine is not None else {}
        steps = list(cfg.get('steps') or [])
        tdir = cfg.get('templates')
        thresh = float(cfg.get('thresh', 0.85))
        dry = bool(cfg.get('dry_run', True))
        if not steps:
            return {'ok': False, 'error': 'no steps'}

        # ---- 加载期合规检查 ----
        bad = []
        for st in steps:
            for field in ('name', 'find', 'expect'):
                kw = _forbidden(str(st.get(field) or ''))
                if kw:
                    bad.append((st.get('name'), field, kw))
        if bad:
            msg = '；'.join(f'{n}.{f} 命中禁用关键词「{kw}」' for n, f, kw in bad)
            print(f'[nav_flow] 合规拒绝：{msg}')
            return {'ok': False, 'error': 'compliance_rejected', 'detail': msg,
                    'note': '登录与动用虚拟资产的界面不在本任务范围内，需用户逐次同意并单独处理'}

        results = []
        aborted = None
        t_start = time.perf_counter()
        for i, st in enumerate(steps):
            name = st.get('name') or f'step{i+1}'
            timeout = float(st.get('timeout', 15))
            retries = int(st.get('retries', 2))
            tries = 0
            ok = False
            reason = None
            while tries <= retries and (time.perf_counter() - t_start) < float(cfg.get('max_seconds', 300)):
                tries += 1
                frame = engine.grab()
                m = self._find(engine, frame, tdir, st.get('find'), thresh)
                if m is None:
                    reason = f'未找到模板 {st.get("find")}'
                    time.sleep(0.3)
                    continue
                if not dry and st.get('click', True):
                    dx, dy = (st.get('offset') or [0, 0])
                    pt = (m['x'] + m['w'] // 2 + int(dx), m['y'] + m['h'] // 2 + int(dy))
                    engine.input.click(*pt)
                time.sleep(float(st.get('wait_after', 0.5)))
                if st.get('expect'):
                    ok2, m2 = self._wait_for(engine, tdir, st['expect'], thresh,
                                             float(st.get('timeout', 15)))
                    if not ok2:
                        reason = f'未等到预期界面 {st["expect"]}'
                        continue
                ok = True
                break
            results.append({'step': name, 'ok': ok, 'tries': tries, 'reason': reason,
                            't': round(time.perf_counter() - t_start, 2)})
            print(f'[nav_flow] {i+1}/{len(steps)} {name}: {"OK" if ok else "FAIL"} '
                  f'（尝试 {tries} 次{"，" + reason if reason else ""}）')
            if not ok:
                aborted = f'步骤 {name} 失败：{reason}'
                break
        out = {'ok': aborted is None, 'done': sum(1 for r in results if r['ok']),
               'total': len(steps), 'steps': results, 'aborted': aborted, 'dry_run': dry}
        if aborted:
            print(f'[nav_flow] 中止：{aborted}')
        return out

    # ---------- 内部 ----------
    def _tpl_path(self, tdir: str, name: str):
        if not tdir or not name:
            return None
        for cand in (name, name + '.png'):
            p = os.path.join(tdir, cand)
            if os.path.exists(p):
                return p
        return None

    def _find(self, engine, frame, tdir: str, name: str, thresh: float):
        """在帧内找模板，返回 {x,y,w,h,score} 或 None。

        优先用内核的模板匹配识别器；不可用时退回主仓内置的 cv2 匹配。
        """
        if not name:
            return None
        try:
            ms = engine.recognize({'use': 'template', 'spec': {'template': self._tpl_path(tdir, name),
                                                               'thresh': thresh}}, frame, engine.ctx)
            if ms:
                r = ms[0].rect
                return {'x': r.x, 'y': r.y, 'w': r.w, 'h': r.h, 'score': ms[0].score}
        except Exception:
            pass
        return self._cv_match(frame, self._tpl_path(tdir, name), thresh)

    def _cv_match(self, frame, tpl_path: str, thresh: float):
        if not tpl_path:
            return None
        try:
            import cv2
            tpl = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
            img = frame.image
            if img.ndim == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if tpl is None or tpl.shape[0] > img.shape[0] or tpl.shape[1] > img.shape[1]:
                return None
            res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
            _mn, mx, _ml, ml = cv2.minMaxLoc(res)
            if mx < thresh:
                return None
            x, y = ml
            ox, oy = getattr(frame, 'origin', (0, 0))
            return {'x': int(x + ox), 'y': int(y + oy), 'w': tpl.shape[1], 'h': tpl.shape[0],
                    'score': float(mx)}
        except Exception:
            return None

    def _wait_for(self, engine, tdir: str, name: str, thresh: float, timeout: float):
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < timeout:
            frame = engine.grab()
            m = self._find(engine, frame, tdir, name, thresh)
            if m is not None:
                return True, m
            time.sleep(0.2)
        return False, None
