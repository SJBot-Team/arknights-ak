# -*- coding: utf-8 -*-
"""dump_keymap.py — 解析 MuMu 键鼠方案 JSON，提取"划火柴/暂停/时停"等宏的具体定义

## 为什么（用户指引）
用户指出：**"明日方舟要精确到帧级部署，比如暂停时部署，需要用到划火柴技巧。AFA 有现成的宏"**，
并提示参考 prts+/MAA 的拖拽部署实现。MuMu 官方帮助也说明：
- **W = 划火柴（0 帧部署）**：先按 F/G 暂停 → 按 W → 等 0.1s → 快速从干员区拖出干员（建议 1 倍速）
- **F = 时停操作**：先点干员头像，后按 F，**游戏战斗进程停止，但鼠标仍可拖放干员**

本脚本读取本机 `AppData\\Roaming\\Netease\\MuMuPlayer\\data\\keymapConfig\\*.json`，
按 `keymaps[].icon.description` 找出这些宏，打印它们的：
`虚拟键` / `按下动作(press_actions)` / `松开动作(release_actions)` / `鼠标相对位置(rel_work_position)` / `类型`。
⇒ 用于**照抄其实现**，而不是自己猜时序。
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

KM_DIR = os.path.join(os.environ.get('APPDATA', ''), 'Netease', 'MuMuPlayer', 'data', 'keymapConfig')
KEYS_OF_INTEREST = ('划火柴', '暂停', '时停', '卡帧', '撤退', '技能', '选取', '点击', '倍速', 'return', '返回')


def summarize(path: str, only_interest: bool = True):
    try:
        d = json.load(open(path, encoding='utf-8'))
    except Exception as e:
        print(f'  [读取失败] {os.path.basename(path)}: {e}')
        return
    kms = d.get('keymaps') or []
    print(f'\n=== {os.path.basename(path)}  （{len(kms)} 个键位）===')
    for km in kms:
        icon = km.get('icon') or {}
        desc = str(icon.get('description', '') or '')
        if only_interest and not any(k in desc for k in KEYS_OF_INTEREST):
            continue
        key = km.get('key') or {}
        rp = km.get('rel_work_position') or {}
        pa = km.get('press_actions') or []
        ra = km.get('release_actions') or []
        print(f"  [{desc or '(无描述)'}]  类型={km.get('type')}  "
              f"触发键={key.get('text')}/vk={key.get('virtual_key')}/scan={key.get('scan_code')}")
        print(f"      位置 rel=({rp.get('rel_x')}, {rp.get('rel_y')})")
        print(f"      press  : {pa}")
        print(f"      release: {ra}")
        for extra in ('macro', 'macros', 'actions', 'duration', 'interval'):
            if extra in km:
                print(f"      {extra}: {json.dumps(km[extra], ensure_ascii=False)[:300]}")


def main():
    files = sorted(glob.glob(os.path.join(KM_DIR, '*.json')))
    print(f'键鼠方案目录: {KM_DIR}\n共 {len(files)} 个方案')
    for p in files:
        print(f'  - {os.path.basename(p)}')
    # 优先看 PRTS+/云迹/血狼 的几个
    prio = [p for p in files if any(k in os.path.basename(p) for k in
                                    ('PRTS+', '云迹', '血狼', 'YoStarJP'))]
    for p in (prio or files)[:4]:
        summarize(p)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
