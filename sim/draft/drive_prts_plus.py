# -*- coding: utf-8 -*-
"""drive_prts_plus.py — 运行赛博塑料（PRTS+）并捕获它的输出（含内部计时）

## 背景
用户 2026-09-14 已切换好游戏界面，授权直接运行 PRTS+ 观察其内部计时与"费用满"时的现象，
并提示："注意选择干员界面开始的选项"。

## 做法
PRTS+ 是控制台程序，启动后会**交互式询问**（先要 Excel 轴表路径，可能再问起始界面）。
本脚本用 Popen 驱动它：读它的提示 → 按规则喂输入 → 持续回显输出 → 到时限后终止。
所有输出都会顺手写入 `.tmp/prts_run_<时间戳>.log`，便于事后逐字复盘。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding='utf-8')

EXE = r'D:\__soft\ak\prts+\prts+.exe'
CWD = r'D:\__soft\ak\prts+'
XLSM = r'E:\__file\舟数据\关卡\h12-4\赛博塑料h12-4.xlsm'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'

ANSI = re.compile(r'\x1b\[[0-9;]*m')


def main():
    run_s = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0
    log_path = os.path.join(TMP, 'prts_run_%s.log' % time.strftime('%H%M%S'))
    log = open(log_path, 'w', encoding='utf-8')
    print(f'启动 {EXE}\n  轴表: {XLSM}\n  日志: {log_path}\n')

    p = subprocess.Popen([EXE], cwd=CWD, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         bufsize=0)
    buf = {'s': ''}
    lock = threading.Lock()
    done = {'v': False}

    def reader():
        while True:
            chunk = p.stdout.read(1)
            if not chunk:
                break
            ch = chunk.decode('utf-8', 'replace')
            with lock:
                buf['s'] += ch
                if ch == '\n':
                    line = ANSI.sub('', buf['s']).rstrip()
                    buf['s'] = ''
                    print('  |', line, flush=True)
                    log.write(line + '\n')
                    log.flush()

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    sent_path = sent_ui = False
    t0 = time.time()
    while time.time() - t0 < run_s:
        with lock:
            pending = ANSI.sub('', buf['s'])
        low = pending.lower()
        # 需要轴表路径
        if (not sent_path) and ('xlsx' in low or 'xlsm' in low or '文件' in pending or 'excel' in low):
            p.stdin.write((XLSM + '\n').encode('utf-8'))
            p.stdin.flush()
            sent_path = True
            print(f'  >>> 输入轴表路径', flush=True)
            with lock:
                buf['s'] = ''
        # 起始界面：优先选"干员界面/编队"（用户提示）
        elif sent_path and (not sent_ui) and ('选择' in pending or '界面' in pending or '开始' in pending
                                             or ':' in pending or '？' in pending):
            p.stdin.write('干员界面\n'.encode('utf-8'))
            p.stdin.flush()
            sent_ui = True
            print('  >>> 输入「干员界面」', flush=True)
            with lock:
                buf['s'] = ''
        time.sleep(0.2)
        if p.poll() is not None:
            break

    try:
        p.terminate()
        time.sleep(0.5)
        if p.poll() is None:
            p.kill()
    except Exception:
        pass
    time.sleep(0.3)
    print(f'\n进程退出码: {p.returncode}；日志已存 {log_path}')
    log.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
