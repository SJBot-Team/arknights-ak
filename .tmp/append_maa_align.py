# -*- coding: utf-8 -*-
"""append_maa_align.py — 登记：MAA 方案索引 + 按 MAA 定义的识别引擎 + 环境状态。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **按用户要求：关卡外严格对照 MAA 现有实现（2026-09-15）**：'
       '①**新建 `knowledge/04/48_MAA方案索引_关卡外流程.md`**，来源明确标注为 '
       '`D:\\__soft\\MAA\\resource\\tasks\\tasks.json`（MAA 的任务流水线定义 = "图像识别→操作步骤"可执行索引，869 个任务），'
       '内容含：主界面判定（`StartUp`/`Fight` 用模板 `SwitchTheme@ToggleSettingsMenu.png`，roi [227,327,159,152]，'
       'MAA 原文"多检测几次，一直在主界面才算完成"）、启动分流（`StartUpThemes` 的 12 项候选 next）、'
       '加载/弹窗（`LoadingIcon` roi [480,210,320,280]、`OfflineConfirm`、`CloseHomeSanity`）、'
       '**★账号/登录（安全关键）**（`AccountManager` 点账号管理 roi [855,660,150,40]；`AccountManagerLoginButton` '
       '**OCR「登录」** roi [423,329,448,147]；`AccountCurrentOCR` **OCR 读账号名**；`AccountListSwipeToTop` Swipe）、'
       '选关（`ClickStageName` 全屏 OCR + `ocrReplace` 纠错表、`ClickedCorrectStage` roi [845,72,220,50]、'
       '`EnterEpisodeNew-Click` OCR「前往章节」）、进关（`BattleStartPre` OCR 六种「开始…」措辞 roi [1000,600,280,120] → '
       '@1920 = 中心 (1710,990)）；**并注明坐标基准 1280×720 ⇒ ×1.5**；'
       '②**安全约束（照 MAA）**：登录只做"点账号管理 → OCR 读账号名 → 点登录"的**界面级动作**，'
       '**绝不读取/记录/推断账号密码**、日志与文档不留凭据，需人工输入时**交回用户**，换号前先 `AccountCurrentOCR` 确认身份；'
       '③**新建 `plugins/recognize/maa_task.py`：按 MAA 定义做识别**（不自行发明）：直接读 tasks.json，'
       '按 `template`/`roi`/`algorithm`/`templThreshold` 判定"当前画面命中了哪些 MAA 任务"，并换算到 1920×1080；'
       '期间摸清 **MAA 的两个关键约定**：(a) **368 个任务没写 `template` ⇒ 默认用任务名当模板名**'
       '（例 `00@EnterEpisodeNew` ⇒ `StageNavigation/Episode/00@EnterEpisodeNew.png`）；'
       '(b) **`template` 与 `templThreshold` 都可以是数组**（如 `ChangeToRaidDifficulty` 的双模板），'
       '需按数组逐个尝试；另发现 MAA 的 `empty.png` = "不做图像匹配"的约定；'
       '④**净尘七轴处理**（用户 2026-09-15 指定 `E:\\__file\\舟数据\\关卡\\净尘1000有模组.xlsm`）：'
       '**第一个空行在第 24 行** ⇒ 机械段 = 行 2~23（22 条，约 3~25 秒），已导出 '
       '`knowledge/04/47_净尘七轴_机械段核对清单.md`；**该表列语义与 h12-4 不同**（"帧数"列实为秒、'
       '"绝对时间"列实为与上一操作的间隔）；**参考视频本地不可得**（`VideoRecords\\净罪\\` 下 8 个录像全是"净罪五星队"）'
       '⇒ 按用户第 3 条指示**转向第一章地图自动打图作自主核验**；'
       '⑤**环境状态**：模拟器原已关闭，已用 `MuMuManager control -v 0 launch` 启动'
       '（新 render_wnd=0031035C）、adb 已连（127.0.0.1:16384）、已启动官服 `com.hypergryph.arknights`；'
       '游戏目前在**启动加载画面**（"天灾/维多利亚帝国"介绍，版本 2.7.71），全任务扫描**无 MAA 任务命中**（合理）；'
       '⑥**下一步**：等游戏到主界面后，按 §48 索引做"主界面判定 → 终端 → 选关 → 编队 → 出战"的流水线，'
       '并用尾号 **** 账号在第 1 章关卡跑通全流程；'
       '⑦合规：仅图形界面级操控（adb/窗口/OCR/模板），**不读取或修改游戏文件、不访问内存**；账号凭据一律不碰。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已登记 MAA 对齐')

for rel in (r'knowledge\04_数据对应与核验\48_MAA方案索引_关卡外流程.md',
            r'code\vision\plugins\recognize\maa_task.py',
            r'code\vision\apps\probe_ui.py'):
    d = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel), d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
