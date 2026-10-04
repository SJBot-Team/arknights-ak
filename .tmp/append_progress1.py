# -*- coding: utf-8 -*-
"""append_progress1.py — 里程碑记录：照 MAA 流程进入主界面 + OCR 接入 + 断点。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\48_MAA方案索引_关卡外流程.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **★里程碑：照 MAA 流程成功进入主界面 + OCR 接入（2026-09-15）**：'
       '①**模拟器原已关闭**，用 `MuMuManager control -v 0 launch` 启动（新 render_wnd=0031035C）、'
       '`adb connect 127.0.0.1:16384`、启动官服 `com.hypergryph.arknights`；'
       '②**完全照 MAA 的启动流程**推进成功（新建 `apps/maa_wakeup.py`）：'
       '`GameStart` 命中 **0.997** → 按 MAA `ClickSelf` 点 (960,1022)（MAA roi [550,600,200,120]@1280 ⇒ 换算后正落此点，'
       '**参数完全吻合**）→ 加载 → `StartToWakeUp` 命中 **0.926** → 点 (962,769) → '
       '`NextAfterLoadingIcon` 命中 **0.998** → **`StartUp` 命中 0.994 = 主界面** ✓'
       '⇒ **验证了"关卡外严格照 MAA 实现"这条路线可行**；'
       '③**OCR 接入**（MAA 的选关/进关/登录大量依赖 OCR）：使用 PRTS+ 自带的 '
       '`D:\\__soft\\ak\\prts+\\_internal\\Tesseract-OCR\\tesseract.exe`（v5.3.0），'
       'tessdata 含 **`chi_sim`(42MB)、`eng`、`arknights_digit`/`ark_digit` 专用数字模型**与自定义词表；'
       '`MaaTask.ocr_roi()` 按 MAA 的 **roi 裁剪 + 2× 放大 + psm 6** 识别；'
       '**踩坑并修正**：(a) `subprocess` 未指定编码 ⇒ 中文乱码（`绂?浠?搴?`），改 `encoding=\"utf-8\"` 后正常读出「仓库」等中文；'
       '(b) MAA 里 `text: []` 的任务（如 `ClickStageName`/`ClickChapter`）是"**由调用方传入目标文本**"的语义，'
       '我原先误当"任意文本即命中"⇒ 已改为返回 `needs_target`，不猜；'
       '④**主界面实际信息**（截图确认）：玩家名「**（玩家名）**」、UID *************、**理智 528/210**、'
       '主线进度 **15-1**；右上角为「**终端**」（选关入口）⇒ **⚠ 该账号 UID 尾号是 7600，与用户所说"尾号 ****"不符**，'
       '待用户确认（本节只记录游戏内**公开显示**的 UID，未记录任何凭据）；'
       '⑤**MAA 索引的重要补充**（写回 `48_MAA方案索引_关卡外流程.md`）：'
       '`Terminal-Entry` **不在主 tasks.json**，而在 **`tasks/UiTheme/Terminal.json`** —— '
       '它以 `JustReturn` + `next: [TerminalDefault, TerminalDark, TerminalSami, ...]` 的形式'
       '**按 UI 主题列出多个终端按钮候选**（`crop_doc.roi=[903,120,97,58]`）；'
       '章节切换：`ClickChapter`（OCR，`text:[]` 由外部传入，roi [142,43,250,150]），'
       '**`ClickChapter1` 的 text = ["觉醒"] ⇒ 第一章名为「觉醒」**；`ToChapter1` 为候选链；'
       '⑥**下一步（断点）**：读 `tasks/UiTheme/Terminal.json` 找到**当前主题**的终端按钮 → 点击进入终端 → '
       '按 MAA 选第 1 章「觉醒」的关卡 → 编队 → 出战（**优先演习**，第 1 章已通关故可演习）；'
       '并继续把「主界面→终端→选关→编队→出战」写成 `pipeline` 配置；'
       '⑦合规：仅图形界面级操控（adb/模板/OCR），**不读取或修改游戏文件、不访问内存**；'
       '**账号凭据一律不碰**；本节仅记录游戏内公开显示的信息。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录里程碑')

s = io.open(DOC, encoding='utf-8').read()
extra = '''

---

## 八、实战补充（2026-09-15，照 MAA 实跑中发现）

| 发现 | 内容 |
|---|---|
| `Terminal-Entry` 的位置 | **不在主 `tasks.json`**，在 **`tasks/UiTheme/Terminal.json`**；形式为 `JustReturn` + `next:[TerminalDefault, TerminalDark, TerminalSami, TerminalMistCity, TerminalSiege, TerminalSarkaz, TerminalDelicious, …]`，`crop_doc.roi=[903,120,97,58]` ⇒ **终端按钮按 UI 主题有多套外观，需逐个候选尝试** |
| 章节切换 | `ClickChapter`：**OCR**（`text:[]` 由调用方传入目标章节名），`roi [142,43,250,150]`；**`ClickChapter1` 的 text = ["觉醒"]** ⇒ **第一章名为「觉醒」**；`ToChapter1` 为候选链（`ClickChapterNew` 优先） |
| 启动候选链实测 | `GameStart`(0.997) → `StartToWakeUp`(0.926) → `NextAfterLoadingIcon`(0.998) → `StartUp`(0.994) 全部命中 ⇒ 照 MAA 可行 |
| OCR 引擎 | PRTS+ 自带 Tesseract v5.3.0（`chi_sim`/`eng`/`arknights_digit`/`ark_digit`）；**调用必须显式 `encoding="utf-8"`**，否则中文乱码 |
| `text:[]` 的语义 | MAA 里表示"**目标文本由调用方给出**"（如关卡名、章节名），**不是**"任意文本即命中" |
'''
if '实战补充（2026-09-15' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(extra)
    print('已补充 MAA 索引')

for rel in (r'knowledge\04_数据对应与核验\48_MAA方案索引_关卡外流程.md',
            r'code\vision\plugins\recognize\maa_task.py',
            r'code\vision\apps\maa_wakeup.py'):
    d = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel), d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
