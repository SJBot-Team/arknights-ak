# -*- coding: utf-8 -*-
"""临时：对比两端在每条操作触发时的费用估计（执行端 dp_est vs 模拟 cost_at）"""
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
sim = json.load(open(r'C:\Users\23922\Documents\ds_harness\ak\data\derived\sim_axis_frames_retry.json', encoding='utf-8'))
log = json.load(open(r'C:\Users\23922\Documents\ds_harness\ak\data\derived\logs_h12-4_gated.json', encoding='utf-8'))
s = sim['retry']
r = log['log']
print(f'{"#":>3} {"操作":<7} {"单位":<18} {"sim帧":>6} {"run帧":>6} {"Δ帧":>5} {"sim费":>5} {"run费":>5} {"Δ费":>5}')
for i in range(len(s)):
    a, b = s[i], r[i]
    ca, cb = a.get('cost_at'), b.get('dp_est')
    print(f'{i+1:>3} {a["op"]:<7} {a["unit"]:<18} {a["frame"]:>6} {round(b["frame_before"]):>6} '
          f'{round(b["frame_before"]) - a["frame"]:>5} {str(ca):>5} {str(cb):>5} '
          f'{(cb - ca) if (ca is not None and cb is not None) else "":>5}')
