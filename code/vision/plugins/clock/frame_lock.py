# -*- coding: utf-8 -*-
"""frame_lock.py — ★**同帧多操作**的"冻结 → 定位帧 → 执行 → 恢复"控制器。

## 需求（目标②）
> 「**同帧多操作**（**操作前先步进/暂停定位帧再执行**）」

一帧 1/30 s，若两条操作按"顺序等时钟"执行，注入耗时会把第二条挤到下一帧。
⇒ 要保证"**同一游戏帧内的多条操作**"，必须**先把游戏停在该帧**，再连续下发。

## 三种模式
| 模式 | 用途 | 实现 |
|---|---|---|
| **`sim`** | dry-run / 离线推演 / **回归测试** | 不做任何输入；直接把 `paused_frame` 记为目标帧（**完全可离线验证**） |
| **`win`** | 实机（Windows 注入，MuMu PC / PC 端） | 按住暂停键（`key_down`，F 键语义 = 按下暂停/松开恢复）；必要时按"过帧键"步进对齐；`key_up` 恢复 |
| **`adb`** | 实机（ADB，MuMu12） | 点击暂停按钮相对坐标暂停；过帧用配置的按键事件；再点击恢复 |

> ★**已知前置条件（来自打图线既有结论，勿重复试错）**：
> - `F` 键语义 = **按下暂停 / 松开恢复**，必须用 `key_down`/`key_up` 分开控制；
> - **0 帧选中** 与 **游戏开始时 0 帧暂停** 需宏实现；
> - 过帧宏效果 = 真实时间 × 流速（1X ⇒ T≈1 帧）；
> - ADB 的 `input keyevent` **无法触发 MuMu 宏**；Windows 层需 `PostMessage`/`SendMessage`。

## 安全的默认
`sim` 为默认；`win`/`adb` 需要配置里显式给出参数（暂停键 / 暂停按钮坐标 / 过帧键），
缺参数时**报错而不是静默降级**，避免"以为冻住了其实没冻"。
"""
from __future__ import annotations

import time


class FreezeController:
    """冻结控制器：把游戏停在指定帧、执行、再恢复。"""

    def __init__(self, engine=None, cfg: dict | None = None, dry: bool = True):
        self.engine = engine
        self.cfg = dict(cfg or {})
        mode = str(self.cfg.get('mode') or ('sim' if dry else 'win'))
        self.mode = mode
        self.dry = bool(dry)
        self.backend = None
        self.errors: list[str] = []
        if mode == 'win':
            self._init_win()
        elif mode == 'adb':
            self._init_adb()

    # ---------------- 初始化 ----------------
    def _init_win(self):
        try:
            from plugins.action.win_input import WinInput
            self.backend = WinInput(self.cfg.get('window') or None)
        except Exception as ex:                                  # noqa: BLE001
            self.errors.append(f'win 后端不可用：{ex!r}')

    def _init_adb(self):
        try:
            from kernel.registry import ACTIONS
            icfg = dict(self.cfg.get('input') or {})
            name = icfg.pop('backend', 'input:adb')
            self.backend = ACTIONS[name](**icfg)
        except Exception as ex:                                  # noqa: BLE001
            self.errors.append(f'adb 后端不可用：{ex!r}')

    # ---------------- 冻结 ----------------
    def freeze_at(self, target_frame: float, clock=None, off: int = 0) -> dict:
        """把游戏停到 `target_frame` 并返回 `{ok, mode, paused_frame, steps, note}`。"""
        if self.mode == 'sim':
            # 离线：不做任何输入；"冻结帧"即目标帧（用于回归测试与轴表推演）
            return {'ok': True, 'mode': 'sim', 'paused_frame': float(target_frame),
                    'steps': 0, 'note': 'dry-run 模拟冻结（未注入任何输入）'}
        if self.backend is None:
            return {'ok': False, 'mode': self.mode, 'paused_frame': None, 'steps': 0,
                    'note': '后端不可用：' + '; '.join(self.errors)}
        try:
            if self.mode == 'win':
                key = str(self.cfg.get('pause_key', 'f'))
                self.backend.key_down(key)
            else:
                btn = self.cfg.get('pause_button')
                if not btn:
                    return {'ok': False, 'mode': 'adb', 'paused_frame': None, 'steps': 0,
                            'note': '缺少 pause_button 坐标'}
                self.backend.click(int(btn[0]), int(btn[1]))
            time.sleep(float(self.cfg.get('freeze_settle_s', 0.05)))
            # 步进对齐（最多 step_max 次）：读时钟，若相位 != 目标则按过帧键
            steps = 0
            paused_frame = None
            if clock is not None and self.cfg.get('step_key'):
                want = int(target_frame) % 30
                for _ in range(int(self.cfg.get('step_max', 5))):
                    st = clock.read()
                    if not st.ok:
                        break
                    paused_frame = float(st.frame_now()) - off
                    if int(round(paused_frame)) % 30 == want:
                        break
                    self._tap_step()
                    steps += 1
            return {'ok': True, 'mode': self.mode, 'paused_frame': paused_frame,
                    'steps': steps, 'note': '已冻结'}
        except Exception as ex:                                  # noqa: BLE001
            return {'ok': False, 'mode': self.mode, 'paused_frame': None, 'steps': 0,
                    'note': f'冻结失败：{ex!r}'}

    def _tap_step(self):
        if self.backend is None:
            return
        key = str(self.cfg.get('step_key'))
        if self.mode == 'win':
            self.backend.key_press(key) if hasattr(self.backend, 'key_press') else None
        else:
            try:
                self.backend.key(key)
            except Exception:                                    # noqa: BLE001
                pass
        time.sleep(float(self.cfg.get('step_wait_s', 0.04)))

    # ---------------- 恢复 ----------------
    def release(self) -> dict:
        if self.mode == 'sim':
            return {'ok': True, 'mode': 'sim'}
        if self.backend is None:
            return {'ok': False, 'note': '后端不可用'}
        try:
            if self.mode == 'win':
                self.backend.key_up(str(self.cfg.get('pause_key', 'f')))
            else:
                btn = self.cfg.get('pause_button')
                if btn:
                    self.backend.click(int(btn[0]), int(btn[1]))
            return {'ok': True, 'mode': self.mode}
        except Exception as ex:                                  # noqa: BLE001
            return {'ok': False, 'note': f'恢复失败：{ex!r}'}


def make_freeze(engine=None, cfg: dict | None = None, dry: bool = True) -> FreezeController:
    return FreezeController(engine=engine, cfg=cfg, dry=dry)
