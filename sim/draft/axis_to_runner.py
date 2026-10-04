# -*- coding: utf-8 -*-
"""axis_to_runner.py — 把**共用轴表 YAML** 转成**打图端执行器**用的派生轴表 JSON。

用途：让"共用轴表"成为**唯一事实来源** ——
- 模拟器/校验器直接读 YAML（`replay_axis.py`）；
- 打图端读本脚本生成的 JSON（`code/vision/apps/run_axis.py` 的 `axis_runner.axis`）。

用法：
    python axis_to_runner.py 1-1 [--out ak/data/derived/axis_1-1.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from axis_io import axis_to_derived, load_axis     # noqa: E402

AK_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('axis', nargs='?', default='1-1')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    ax = load_axis(a.axis)
    d = axis_to_derived(ax)
    out = a.out or os.path.join(AK_ROOT, 'data', 'derived', f'axis_{a.axis}.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(f'已生成打图端派生轴表：{out}')
    print(f'  level={d["level"]} ops={len(d["ops"])}')
    for o in d['ops']:
        print(f'    frame {o["frame"]:>5} ({o["abs_seconds"]:.3f}s)  {o["op"]:<7}'
              f' {o.get("unit")} {o.get("coord", "")} {o.get("dir", "")}'
              f' cost={o.get("cost")}')
    print('\n打图端用法（见 code/vision/apps/run_axis.py）：')
    print(f'  在 configs/axis_*.json 里把 axis_runner.axis 指向 {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
