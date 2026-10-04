# -*- coding: utf-8 -*-
"""append_handover_check.py — 收尾：全套回归确认 + 交接清单。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\45_资产索引_可复用工具与脚本.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''

---

## 八、收工前的可用性确认（2026-09-14 末轮实测）

下次接续前，**全部离线回归已跑通**（11 项）：

| 测试 | 结果 |
|---|---|
| `test_frame_clock` | A_bar_phase / B_cost_lattice / C_redeploy / D_fusion 全 PASS |
| `test_ruler_clock` | A~G 全 PASS（含 G_case_milestones 对轴） |
| `test_costbar_axis` | cost_bar / axis_dryrun PASS |
| `test_skill_ready` | A/B/C PASS |
| `test_nav_flow` | A_normal / B_timeout / C_compliance / D_dry_run PASS |
| `test_paused_protocol` | A/B/C/D/E 全 PASS |
| `test_auto_enter` | A/B/C/D 全 PASS（含"绝不点消耗理智按钮"断言） |
| `test_frames_between` | 手算 5/5 + 两轮真实样本 PASS |
| `test_bar_sanity` | A/B/C 全 PASS |
| `ui_state` 自检 | 界面判定 8/8 通过 |
| 模拟器侧 | `test_skills` 4/4、`test_case_deferral` 3/3 |

⇒ **代码资产处于"可直接接续"状态**；未完成项（实机暂停闭环、与 PRTS+ 并排对照、
封顶边界 ±1 秒方向）见 §四断点清单。

## 九、交接时的注意事项（避免重蹈本阶段低效）
1. **实机脚本一律先过 `render_guard`**，并对"静止界面"放宽阈值或改用 `UiState` 语义判定；
2. **判"状态是否改变"必须用语义**（界面类型/模板命中/OCR 文本），**不可用像素差异**；
3. **任何数值判据先用手算样例验证公式方向**（`frames_between` 就是被这个坑教出来的）；
4. **采集一律优先 adb display 通道**（窗口抓屏会被遮挡且抓到别的窗口）；
5. **费用条采样间隔取 0.5~0.9s**（更短则量化误差占比升高，更长则相位绕圈歧义）；
6. **PRTS+ 相关**：路径必须 ASCII；`--autoenter` = 局外自动进关；局内开始时须**在第一秒内暂停**；
   它在费用封顶的关卡会卡死（H12-4 上限 20，必然发生）。
'''

s = io.open(DOC, encoding='utf-8').read()
if '收工前的可用性确认' in s:
    print('已有该节，跳过')
else:
    io.open(DOC, 'a', encoding='utf-8').write(SEC)
    print('已追加可用性确认与交接注意事项')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第七十五轮（收尾：全套回归确认 + 交接注意事项）**：本轮为轮次上限末轮，用户已收工待方向，'
       '故只做可用性确认与交接整理：'
       '①**全套离线回归 11 项全绿**——`test_frame_clock` 4/4、`test_ruler_clock` A~G、`test_costbar_axis` 2/2、'
       '`test_skill_ready` 3/3、`test_nav_flow` 4/4、`test_paused_protocol` 5/5、`test_auto_enter` 4/4、'
       '`test_frames_between`（手算+两轮真实样本）、`test_bar_sanity` 3/3、`ui_state` 自检 8/8、'
       '模拟器侧 `test_skills` 4/4 与 `test_case_deferral` 3/3 ⇒ **代码资产处于可直接接续状态**；'
       '②**写入交接注意事项**（`knowledge/04/45` §八/§九，避免重蹈本阶段低效）：实机脚本先过 `render_guard`、'
       '判"状态改变"必须用语义不可用像素差异、数值判据先手算验证公式方向、采集优先 adb display 通道、'
       '费用条采样间隔取 0.5~0.9s、PRTS+ 的 ASCII 路径与"第一秒内暂停"及封顶会卡死等；'
       '③**未完成项**（见 `44_阶段总结` §四）：实机暂停闭环、与 PRTS+ 并排对照、封顶边界 ±1 秒方向；'
       '④**等待用户整理的修改方向**后继续；'
       '⑤合规：仅跑本地离线测试与整理文档；未触碰游戏、未消耗理智。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第七十五轮')

for f, sub in ((DOC, r'knowledge\04_数据对应与核验'), (REG, 'management')):
    shutil.copy2(f, os.path.join(DST, sub, os.path.basename(f)))
print('同步完成')
