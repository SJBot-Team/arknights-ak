# -*- coding: utf-8 -*-
"""append_nav_findings.py — 记录：MAA 章节导航实证 + 选关受阻的现状与下一步。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\48_MAA方案索引_关卡外流程.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **打图侧：MAA 章节导航实证 + 选关现状（2026-09-15）**：'
       '①**完全照 MAA 走通了到「章节总览」的链路**：主界面 → **终端** → 离解复合（EP15）→ 章节详情 → '
       '「前往章节」→ EP15 关卡地图；另发现**底部导航「曲谱」** → 右上角 **「乐章收录」** → '
       '**乐章总览界面**（顶部三档：**默认进度 / 奖励进度 / 完成进度**，横向排列 EP10~EP15 及活动章节卡片）；'
       '②**关键验证：实际 UI 与 MAA 的 roi 完全吻合** —— 实测「乐章收录」按钮位于 @1920 的 (1763,30)-(1860,90)，'
       '而 MAA `ClickChapterNewOverview` 的 `roi [1175,20,65,40]`@1280 换算后正是 (1763,30)-(1860,90)；'
       '顶部「默认进度」也与 MAA `ClickChapterNewDefaultProgress`（OCR text=默认进度）对应 ⇒ '
       '**证明「关卡外严格照 MAA」这条路在真实 UI 上可逐点对上**；'
       '③**同时摸清 MAA 的章节滑动约定**（此前我按底部滑动导致一直无效）：'
       '`ChapterSlowlySwipeToTheLeft` 的 Doc 明确写「**在上面一点滑避免点到关卡划不动**」，'
       '其 `specificRect [300,100,20,20] → rectMove [900,100,20,20]`（**y=100@1280 ⇒ y=150@1920**）；'
       '`SlowlySwipeToTheLeft/Right` 为 `[300,310,100,100]↔[880,310,100,100]`、`specialParams [200,1,2,0]`（duration 200ms）；'
       'MAA 的寻关流程是 `FullStageNavigation`「**右滑 10 次，然后检测关卡并左滑**」+ `ClickStageName`（全屏 OCR 关卡名）'
       '+ `Stage1-7`（OCR text=["1-7"]，`roi [0,190,1080,60]`）；'
       '④**现状（受阻点）**：实测在**章节详情页**与**EP15 关卡地图**用上述参数滑动**均无变化**；'
       '在**乐章总览**界面（y=150 上方）滑动亦无变化 ⇒ **尚未找到 EP1~EP9 的入口**；'
       '观察到乐章总览第一排卡片上方有「EP 08 / EP 07」等字样（疑似还有上一排，或可点击），**待进一步验证**；'
       '⑤**下一步**：(a) 先确认账号（见下）；(b) 试「乐章总览」里 **EP07/EP08 标签可否点击**、或**向上滚动**；'
       '(c) 若仍不通，则**先用当前可进关卡（如 EP15 的 15-1）在演习中验证「关卡内流程」**'
       '（费用尺读取 + 0 帧暂停 + 同帧多操作）—— 这部分与选哪一关无关，是打图的核心；'
       '⑥**⚠ 账号待确认**：主界面实测玩家名「**（玩家名）**」、**UID ***********（尾号 7600），'
       '与用户所说「尾号 ****」不符，请用户确认是否即授权账号（本节仅记录游戏内公开显示信息，未记录任何凭据）；'
       '⑦合规：仅图形界面级操控；未触碰游戏文件/内存；账号凭据一律不碰。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')

extra = '''

---

## 九、章节导航的 MAA 约定与实测（2026-09-15 补充）

| 项 | MAA 定义（来源 `tasks.json`） | 实测 |
|---|---|---|
| 章节总览入口 | `ClickChapterNewOverview`：OCR「乐章」，`roi [1175,20,65,40]` | ✅ 实测「乐章收录」位于 @1920 (1763,30)-(1860,90)，**与换算完全吻合** |
| 进度档位 | `ClickChapterNewDefaultProgress`：OCR「默认进度」 | ✅ 乐章总览顶部存在「默认进度/奖励进度/完成进度」 |
| **章节滑动** | `ChapterSlowlySwipeToTheLeft`：`[300,100,20,20]→[900,100,20,20]`，Doc「在上面一点滑避免点到关卡划不动」 | ❌ 在章节详情页 / EP15 地图 / 乐章总览 均**无变化** |
| 关卡滑动 | `SlowlySwipeToTheLeft/Right`：`[300,310,100,100]↔[880,310,100,100]`，`specialParams [200,1,2,0]` | ❌ 同上 |
| 寻关流程 | `FullStageNavigation`：「右滑 10 次，然后检测关卡并左滑」 | 待验证 |
| 关卡点击 | `ClickStageName`（全屏 OCR）、`Stage1-7`（OCR「1-7」，`roi [0,190,1080,60]`） | 待验证 |

**坐标基准**：MAA 的 roi 为 1280×720 ⇒ 本机 1920×1080 需 **×1.5**。
**推断**：乐章总览第一排卡片上方有「EP 08 / EP 07」字样，疑为**上一排章节**或**可点击标签** ⇒ 下一步优先验证。
'''
s = io.open(DOC, encoding='utf-8').read()
if '九、章节导航的 MAA 约定与实测' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(extra)
    print('已补充 MAA 索引')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
