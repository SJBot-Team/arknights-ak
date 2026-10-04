# -*- coding: utf-8 -*-
"""append_t052_clock.py — 追加"费用条满计数摸底 + 非战斗画面误报满条"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第74轮】★★★★**实现用户方案第①步的摸底：`CostBarClock` 已实现"满条计数"；实机验证暴露"非战斗画面误报满条"**：'
 '①**摸底（先查已有）**：用户方案第①步「统计**费用条满的次数**以记录绝对时间」'
 '—— `plugins/clock/cost_ruler.py::CostBarClock` **已经就是这个语义**：'
 '读 `CostBarRecognizer` 的**条内相位** `frame_in_cost`(0..29) 与 `total_frames`(30)，'
 '**相位回绕即 `_elapsed += cycle`** ⇒ `elapsed_frames` = 满条次数×30 + 相位 = 绝对帧；'
 '⇒ **第①步无需新造**，只需补"在战斗中"门控（见②）与可审计字段；'
 '②**★实机验证（新增 `code/vision/apps/live_clock_probe.py`）**：在演习战斗中连续采样费用条，'
 '**结果：相位恒为 `30/30`（= 判定"满条"），推进 0 帧/秒** ⇒ 与预期 30 帧/秒严重不符；'
 '随后截图定位原因：**当时画面已是「任务失败 MISSION FAILED / 行动结束」结果页**'
 '⇒ **★`CostBarRecognizer` 在非战斗画面会误报"满条"**（把模糊背景读成满条）；'
 '**⇒ 结论：绝对时间基准必须加「在战斗中」门控**（MAA 式：先判定处于战斗 HUD，再信任费用条），'
 '否则时钟会被非战斗画面污染 —— 这是本轮最有价值的实机发现，直接关系到"费用尺级帧识别"的可靠性；'
 '③**实机过程记录**：该演习战斗因**离开期间无人操作而被打穿**（生命 6→0）⇒ 「任务失败」；'
 '**演习不消耗理智**，结算页 **EXP 0/100000、无任何资源变动** ⇒ 合规无虞；'
 '④**收尾**：点击结算页继续退出（回到关卡/主界面）；'
 '⑤**下一步**：**(a)** 给费用条时钟加"在战斗中"门控（战斗 HUD 判定：`ENEMY x/N` + 费用数字 + 暂停按钮三者在位）；'
 '**(b)** 重进演习，用 `live_clock_probe.py` 验证相位 **≈30 帧/秒** 与满条计数正确；'
 '**(c)** 再做「操作前 1s 子弹时间 → 前 5 帧过帧 → 暂停定位 → 部署」闭环；'
 '⑥**合规**：仅图形界面级点击与截图 + 只读识别；未登录、**未消耗理智**、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
