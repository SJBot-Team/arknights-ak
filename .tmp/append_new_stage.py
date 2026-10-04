# -*- coding: utf-8 -*-
"""append_new_stage.py — 新阶段开工：登记执行计划与差距分析。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\46_执行计划_模拟环境与自动打图.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **新阶段开工（2026-09-15，用户给出完整需求说明 + 方向性修正）**：'
       '①**需求→现状→差距**已整理为 `knowledge/04/46_执行计划_模拟环境与自动打图.md`；'
       '**模拟环境**：1.1 完备框架 ✅（需通用化，目前 `scenario_h124` 专关专用）；'
       '1.2 **标准信息提取流程** 🟡（需一次到位：关卡→关联单位→关联机制，变动项做成外部输入）；'
       '1.4 高速并行 ✅；1.5 **预制验证定位** 🟡（需事件帧钩子）；1.6 **逐帧切片** 🟡（补操作/血量/坐标/攻速/移速/随机判定）；'
       '1.8 **随机数可控** 🟡（已复刻 .NET Random，待与客户端一致性验证）；'
       '**打图**：2.1 精确帧识别 ✅（费用尺三重验证）但**"费用条满后如何精确识别帧数"待探索**；'
       '2.2 同帧多操作 🟡（`paused_protocol` 离线 5/5，待实机）；2.3 共用轴表 🟡（需定"人可读易改"的单一格式）；'
       '2.4 双端通用 🟡；2.5 虚拟鼠标独立 ✅；**2.6 全流程自动启动 🟡（用户点名效率低，需参照 MAA/prts+ 重建）**；'
       '②**分阶段计划**：**P0 重建打图工作流**（参照 MAA `tasks.json` 的识别+roi+action+next+多候选重试，'
       '以及 prts+ 的"**操作前先步进/暂停→定位帧→再执行**"）→ P1 模拟环境标准化（关卡驱动+外部输入+切片补全+事件帧钩子）'
       '→ P2 事件帧验证（视频/实机 ↔ 模拟，先在**弧光/净罪**做，因其费用没满、轴精确）'
       '→ P3 探索"费用条满后"的帧识别（上限锚点之间的计数手段）→ P4 案例验证（H12-4 双人解 / 弧光7 / 净罪7）；'
       '③**资源已定位**：H12-4 轴表与视频（`VideoRecords\\H12-4\\双\\` 4 个 mp4）、**弧光 7 人轴表**'
       '（`E:\\__file\\舟数据\\关卡\\弧光\\赛博塑料弧光7.xlsm`，**费用没满⇒精确参考**）、'
       '弧光参考视频（`VideoRecords\\弧光\\参考轴.mp4` 197MB）、净罪（`净罪作战880.xlsx`，待确认是否即"净罪7人"）；'
       '④**待用户确认 2 点**：(a) "净罪 7 人"的赛博塑料文件是否即 `净罪作战880.xlsx`；'
       '(b) 用户提到的 `E:\\MUMU共享文件夹\\视频\\h12-4 双` 不存在，我在 `VideoRecords\\H12-4\\双\\` 找到 4 个 mp4，是否为同一批；'
       '⑤账号：尾号 ****** 按用户授权自主合规使用（三星全满配、大部分四星满配），'
       '先用**第 1 章简单关卡**练手（目标=事件判定检验模拟准确性 + 跑通打图流程，不追求最优解）；'
       '⑥合规：仅图形界面级操控，不读取/修改运行中的游戏文件、不访问内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已登记新阶段')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
