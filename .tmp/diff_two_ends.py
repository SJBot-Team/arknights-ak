# -*- coding: utf-8 -*-
"""临时：定位两端帧差从第几条开始发散"""
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
sim = json.load(open(r'C:\Users\23922\Documents\ds_harness\ak\data\derived\sim_axis_frames_retry.json', encoding='utf-8'))
log = json.load(open(r'C:\Users\23922\Documents\ds_harness\ak\data\derived\logs_h12-4_gated.json', encoding='utf-8'))
sf = [x['frame'] for x in sim['retry']]
rf = [round(r['frame_before']) for r in log['log']]
prev = 0
print('=== 帧差变化点（|Δ变化| > 5）===')
for i, (a, b) in enumerate(zip(sf, rf)):
    d = b - a
    if abs(d - prev) > 5:
        x = sim['retry'][i]
        print(f'#{i+1:<3} sim={a:<6} run={b:<6} Δ={d:<6} {x["op"]:<7} {x["unit"]:<16} '
              f'sim_ok={x["ok"]} reason={x.get("reason")} need={x.get("need")} have={x.get("have")}')
    prev = d
print('\n=== 全部对照 ===')
for i in range(len(sf)):
    print(f'#{i+1:<3} sim={sf[i]:<6} run={rf[i]:<6} Δ={rf[i]-sf[i]:<6} {sim["retry"][i]["op"]:<7} {sim["retry"][i]["unit"]}')
