# -*- coding: utf-8 -*-
"""bench_sim.py — 模拟器速度基准与并行凹概率示例（需求 1.4）

用法：
  python bench_sim.py                # 单局速度 + 逐帧记录开销
  python bench_sim.py --parallel 8   # 8 进程并行跑同一轴不同种子（凹概率场景）
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import fp
from ak_sim.engine import Battle

LEVEL = 'obt/main/level_main_01-07'


def run_once(level: str, seed: int, record: bool, frames: int = 30 * 120):
    b = Battle(level, seed=seed, record=record)
    spots = [(r, c) for r in range(b.map.height) for c in range(b.map.width)
             if b.map.can_deploy(r, c, melee=True)]
    if spots:
        b.deploy('char_1029_yato2', spots[0][0], spots[0][1], '右')
    t0 = time.perf_counter()
    b.run(max_frames=frames)
    dt = time.perf_counter() - t0
    return b, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--parallel', type=int, default=0)
    ap.add_argument('--seeds', type=int, default=0)
    ap.add_argument('--level', default=LEVEL)
    args = ap.parse_args()

    if args.parallel:
        from concurrent.futures import ProcessPoolExecutor
        n = args.parallel
        seeds = list(range(1000, 1000 + n))
        t0 = time.perf_counter()
        with ProcessPoolExecutor(max_workers=n) as ex:
            results = list(ex.map(_worker, [(args.level, s, False, 30 * 120) for s in seeds]))
        dt = time.perf_counter() - t0
        print(f'并行 {n} 局：墙钟 {dt:.2f}s（单局均摊 {dt/n:.2f}s）')
        for r in results:
            print(f'   seed={r["seed"]} 结果={r["result"]} 帧={r["frame"]} 命中={r["hits"]} 击杀={r["kills"]} 漏怪={r["escapes"]}')
        return

    # 单局基准
    for record in (False, True):
        b, dt = run_once(args.level, 1234, record)
        game_s = b.frame / fp.FPS
        print(f'record={record}: {b.frame} 帧（游戏 {game_s:.1f}s）耗时 {dt:.3f}s → '
              f'加速比 {game_s/max(1e-9,dt):.1f}×；切片 {len(b.frames)} 帧')
    # 落盘示例
    b, _ = run_once(args.level, 1234, True)
    out = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'derived',
                                       'frames_1-7_sample.jsonl'))
    b.dump_frames(out)
    print(f'逐帧切片样例已落盘：{out}（{os.path.getsize(out)//1024} KB）')


def _worker(a):
    level, seed, record, frames = a
    b, _ = run_once(level, seed, record, frames)
    return {'seed': seed, 'result': b.result, 'frame': b.frame,
            'hits': sum(1 for l in b.logs if l.kind == 'hit'),
            'kills': sum(1 for l in b.logs if l.kind == 'kill'),
            'escapes': sum(1 for l in b.logs if l.kind == 'escape')}


if __name__ == '__main__':
    main()
