# -*- coding: utf-8 -*-
"""diag_runes.py — 打印关卡全部 runes/optionalRunes/globalBuffs 的黑板，找「费用上限」相关机制。

要弄清：H12-4 里费用上限除了「打储备 +5」「平民到达 +2」之外，还有没有别的抬升来源
（例如击杀/波次/时间）。这决定了作者作战记录里 29.0s 落龙（弦惊 23 费 > 上限 20）是否可能。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle                      # noqa: E402
from ak_sim import scenario_h124 as S                 # noqa: E402


def main():
    b = Battle(S.LEVEL, seed=0, record=False)
    lv = b.level
    for key in ('runes', 'optionalRunes', 'globalBuffs'):
        print(f'===== {key} =====')
        for r in (lv.get(key) or []):
            bb = r.get('blackboard')
            print(f'  {r.get("key")} mask={r.get("difficultyMask")} buildable={r.get("buildableMask")}')
            for x in (bb or []):
                print(f'      bb {x.get("key")} = {x.get("value")} / {x.get("valueStr")}')
    print('===== options =====')
    print(json.dumps(lv.get('options'), ensure_ascii=False))
    print('===== 引擎已实现的上限来源 =====')
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'ak_sim', 'engine.py'), encoding='utf-8').read()
    for i, line in enumerate(src.splitlines(), 1):
        if 'add_cost_cap' in line or 'cost_max' in line:
            print(f'  engine.py:{i}: {line.strip()[:110]}')


if __name__ == '__main__':
    main()
