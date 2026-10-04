# -*- coding: utf-8 -*-
"""append_t052_live3.py — 追加"格点标定解出 + 拖拽抓取成功 + 落格仍未提交"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第71轮】★★★★**实机：格点→像素标定解出（自洽可校验）；拖拽"抓起干员"成功；"落格提交"仍未通（D1 收窄到释放环节）**：'
 '①**★格点标定（不人肉试坐标）**：暂停+选卡态截图 → `Deployer.find_green_cells(cell_px=130)` 得 **7 个绿格单元**'
 '（一行 6 连：(807/932/1057/1181/1306/1431, 502)，x 步长 ≈124.5；另一格 (1057,364)，正好是"左起第 3 格的上一行"）；'
 '再与**关卡地图**（`mapData.map` + `tiles`：`tile_road`=LOWLAND/MELEE/ALL 才是近战可部署）联立反解，得映射：'
 '**`x(col) = 1556 − 124.5·col`、`y(row) = 502 + 138·(row − 3)`**；'
 '**校验**：预测 **D6=(3,5) → (934,502)**、**D4=(3,3) → (1182,502)** —— **两者都恰好在检测到的绿格集合里**'
 '（实测 932/1181）⇒ 标定自洽；'
 '②**1-1 近战可部署布局（由 tiles 解出）**：r3 有 **7 连排通道 c1..c7**；竖向通道 c4(r1~r3)、c5(r3~r5)；'
 '其余为高台(^)或不可部署(.)；'
 '③**★拖拽抓取成功（新进展）**：`Deployer.motion([card→cell], hold_ms=250)` 的**多点 motionevent 拖拽**'
 '**成功把芬"抓起"** —— 画面出现干员悬停于部署光标、白色菱形指示、**「点击取消」**按钮、生命条高亮；'
 '（此前长期结论是"点选可触发绿格但**落格提交**未复现"，本轮把"抓取"这一步跑通了）；'
 '④**✗ 落格提交仍失败**：在目标格 (934,502) 补一次 `input tap` **无变化**；'
 '再发 `input motionevent UP 934 502` **也无变化**（截图 sha256 完全相同）⇒ 干员一直处于"held"态；'
 '**⇒ D1 收窄为"释放/提交"这一步**（抓取通道可用）；'
 '⑤**下一步（已定位手段）**：改用 **Windows 层真实鼠标拖拽** —— `plugins/action/win_input.py::WinInput.sm_drag(points, steps, hold, between)`，'
 '与既有结论「**划火柴需真实鼠标（宏读 `GetCursorPos`）**；adb keyevent 与 SendInput 均不能触发 MuMu 宏」一致；'
 '⑥**收尾状态（已程序化校验）**：点「点击取消」退出拖拽态（该按钮红色像素占比 = 0.0 ⇒ 已退出）；'
 '**演习战斗仍处暂停**，**未产生任何部署、未消耗理智/资源、未打开禁用界面**；'
 '⑦**新增工具**：`code/vision/apps/calibrate_grid_live.py`（绿格检测 + 关卡地图联立标定）、'
 '`sim/draft/analyze_1_1_grid.py`（1-1 近战可部署布局解析）；'
 '⑧**合规**：仅图形界面级点击/拖拽与截图；未登录（账号本就登录态）、未消耗理智、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
