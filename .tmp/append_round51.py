# -*- coding: utf-8 -*-
"""append_round51.py — 第 51 轮：渲染闸门、UiState 接入导航、暂停协议边界测试。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.101 两项工程化改进（不依赖实机）

1. **渲染闸门进脚本**：`auto_sample_v2.py` 在置前台后立刻做"画面在变"校验，
   不通过就**直接退出并说明原因**（本轮实测：`★ 渲染仍停止（adb 帧缓冲冻结）—— 实机流程无法进行`）。
   ⇒ 杜绝了"对一张静止旧帧连续判断 10 次"这种浪费轮次的行为（§7.72 规程落地）。
2. **界面判定器接入导航**：导航的判据从"白色占比"换成 `UiState`（MAA 模板），
   且**编队界面的「开始行动」点击点由模板位置直接给出**（实测 (1655,759)，而非硬编 (1675,792)）。
   脚本语法与运行均已验证（本轮因渲染闸门提前退出，未走到点击环节）。

### 7.102 暂停协议边界测试（新增 `apps/test_paused_protocol.py`，5/5 PASS）

暂停驱动是本项目"帧级精度"的核心机制，此前只有一个简单自检。本轮补齐边界：

| 用例 | 断言 | 结果 |
|---|---|---|
| A 暂停遮罩未出现 | `pause()` 必须返回 False（**绝不"以为暂停了"**），且记 `pause_failed` | PASS |
| B 相位永不满足 | `resume_at` 超时返回 False，且 **`paused` 保持 True**（状态一致） | PASS |
| C 多批 stage/commit | 注入顺序 = 排队顺序，commit 后队列清空 | PASS |
| D same_frame_batch | 暂停→注入 2 条→按相位恢复，`resumes == 1`、`paused == False` | PASS |
| E 恢复点间隔规则 | 相位序列 `[1,2,28,29,0,7,8]` 中必须在 **phase=7**（距目标相位 gap=7 ≥ 6）恢复，避开跨费用结算的 ±1 帧歧义 | PASS |

### 7.103 全套离线回归（本轮末）全绿
```
打图端: frame_clock A/B/C/D=PASS | ruler_clock A~G=PASS | costbar_axis 2/2 PASS
        skill_ready 3/3 PASS | nav_flow 4/4 PASS | 暂停协议 A~E PASS | 界面判定 8/8 通过
模拟器: skills 4/4 PASS | case_deferral 解析/对照/执行 3/3 PASS
```

### 7.104 断点（不变）
实机**相位↔墙钟精度验收**（|误差| ≤ 2 帧）仍待跑：脚本（`instant_sample.py` / `auto_sample_v2.py`）
与判定器均已就绪并加了渲染闸门，只差 **模拟器渲染恢复**（需重启实例；重启可能触发重新登录，故等用户决定）。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.100 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.105 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.101~§7.104')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第五十一轮（渲染闸门 + UiState 接入导航 + 暂停协议边界测试）**：渲染仍停止 ⇒ 转做不依赖实机的工程化；'
       '①**渲染闸门进脚本**：置前台后立刻做"画面在变"校验，不通过即**退出并说明原因**'
       '（实测输出 `★ 渲染仍停止（adb 帧缓冲冻结）`）⇒ 杜绝"对静止旧帧连续判断 10 次"的浪费；'
       '②**界面判定器接入导航**：判据由"白色占比"换成 `UiState`（MAA 模板），编队界面「开始行动」点击点'
       '**由模板位置直接给出 (1655,759)**（非硬编 (1675,792)）；脚本语法与运行已验证；'
       '③**新增 `apps/test_paused_protocol.py`，5/5 PASS**：(A) 遮罩未出现 ⇒ pause 必须失败（绝不"以为暂停了"）；'
       '(B) 相位永不满足 ⇒ 恢复超时且 `paused` 保持 True；(C) 多批 stage/commit 顺序与清空；'
       '(D) same_frame_batch 成功路径；(E) 恢复点必须在距目标相位 gap≥6 处（避开跨费用结算 ±1 帧歧义）；'
       '④**全套离线回归全绿**：frame_clock 4/4、ruler_clock 7/7、costbar_axis 2/2、skill_ready 3/3、'
       'nav_flow 4/4、暂停协议 5/5、界面判定 8/8；模拟器侧 skills 4/4、case_deferral 3/3；'
       '⑤**断点不变**：实机相位↔墙钟精度验收待跑，只差**模拟器渲染恢复**（需重启实例，可能触发重新登录，等用户决定）；'
       '⑥合规：全程仅演习、未消耗理智；不碰游戏内存。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第五十一轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
for rel in (r'code\vision\apps\test_paused_protocol.py', r'code\vision\apps\auto_sample_v2.py'):
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel), os.path.join(DST, rel))
print('同步完成')
