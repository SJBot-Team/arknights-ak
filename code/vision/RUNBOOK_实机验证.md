# RUNBOOK — h12-4 实机验证规程（一页版）

> 目标：在 MuMu12 上用**费用尺时钟 + ADB 注入**跑通 h12-4 轴表前半段，验收三条实机链路，
> 并测出「首次召唤物时刻 / 当时费用读数」以完成案例的最终对齐。
> **合规前置**：`ak/meta/合规声明_自动打图与账号.md`（与客户端合规声明同等效力）。任何一步触犯即停并上报。

---

## 0. 合规检查点（每步动手前默念）

| # | 检查 |
|---|---|
| 1 | 登录**必须逐次获用户同意**；仅限用户指定账号（本次：尾号 ******）；**禁止使用登录界面未保存的账号** |
| 2 | 额度：**MuMu12 1 次 + PC 1 次**（用尽即停、再问）；顶号/断线后重新登录需**再次同意** |
| 3 | **禁止动用除「理智」外的任何资源**；**禁开**仓库/基建/抽卡/商店/邮件/养成/模组，误触立即退出 |
| 4 | 练度/模组不匹配 → **停下问用户**（换号或助战），**不得自行提升** |
| 5 | 任何可能构成作弊或动用虚拟资产的操作，**AI 不得自行尝试** |

## 1. 起手（离线预演，不用游戏）

```powershell
cd C:\Users\23922\Documents\ds_harness\ak\code\vision
& '.\.venv\Scripts\python.exe' -X utf8 apps\test_ruler_clock.py    # 7 项自检应全 PASS
& '.\.venv\Scripts\python.exe' -X utf8 apps\test_skill_ready.py    # 13 项自检应全 PASS
& '.\.venv\Scripts\python.exe' -X utf8 apps\run_axis.py --config configs\axis_h12-4.json --speed 300
#   预期：50/50 条触发；弦惊落地 43.0 / 66.0 / 89.0s
```

## 2. 启动费用尺并验证 API（游戏可已运行，只读本机回环端口）

```powershell
# 启动 D:\__soft\ak\ArknightsCostBarRuler-v2.3.2 里的尺子，然后在关卡内运行：
Invoke-RestMethod http://127.0.0.1:2606/ | ConvertTo-Json -Depth 3
#   需看到 isRunning=true、totalElapsedFrames 递增、battleState=battle
```

## 3. 标定（新工具，离线先跑一遍 → 现场只确认）

```powershell
# 3.1 截一张战斗界面图（任意方式；模拟器截图/本工具采集均可）
# 3.2 自动探测：费用数字 ROI / 卡槽行 / 战场区域估计 / 技能图标候选
& '.\.venv\Scripts\python.exe' -X utf8 apps\calibrate.py auto --image shot.png --out marked.png --patch patch.json --cards 12
# 3.3 目视核对 marked.png；不对的项用 grid 读坐标后手工标注：
& '.\.venv\Scripts\python.exe' -X utf8 apps\calibrate.py grid --image shot.png --step 100 --out grid.png
& '.\.venv\Scripts\python.exe' -X utf8 apps\calibrate.py mark --image shot.png --out m2.png --patch patch2.json `
    --boxes "ui.skill_button=x0,y0,x1,y1" "ui.retreat_button=x0,y0,x1,y1" "ui.skill_sp_roi=x0,y0,x1,y1"
# 3.4 合并进配置（自动备份 .bak）
& '.\.venv\Scripts\python.exe' -X utf8 apps\calibrate.py apply --patch patch.json --config configs\axis_h12-4.json
```

**本机已知可复用值（1600×900 录像帧实测）**：费用数字 ROI ≈ `(1525,619,1565,670)`；卡槽行 y 带 ≈ `684~891`，12 槽 x 中心 ≈ `66,200,333,…,1533`。分辨率不同需重测。

## 4. dry-run 对轴（不注入任何输入）

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 apps\run_axis.py --config configs\axis_h12-4.json --clock ruler
#   验收：每条打印 目标帧/实际帧/迟到帧；弦惊两条应在 43.0s、66.0s 附近
#   时钟掉线保护：非虚拟时钟连续 5s 无有效读数会自动中止
```

## 5. 实注入（需用户当场同意；先把编队摆好并进入关卡）

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 apps\run_axis.py --config configs\axis_h12-4.json --clock ruler --live --i-have-consent
#   缺 --i-have-consent 且配置未置 live_run_consent=true 时会被合规守卫拒绝（退出码 2）
```

**急停**：Ctrl+C；或把鼠标甩到屏幕角落（若使用 directinput 后端）。ADB 后端不占宿主鼠标，急停靠 Ctrl+C。
**回滚**：`configs\axis_h12-4.json.bak` 可还原标定前配置。

## 6. 记录与验收

| 验收项 | 判据 |
|---|---|
| 费用尺时钟 | `totalElapsedFrames` 与游戏计时一致；dry-run 的到点误差 ≤ 2 帧 |
| 首次召唤物 | 实测时刻 ≈ **43.0s**（解析/模拟/执行端三方一致） |
| 第二批召唤物 | 实测时刻 ≈ **66.0s**（作者 Sheet1 记录 `66.1过1下龙`，Δ0.1s） |
| 当时费用读数 | 部署前显示费用 ≈ **23**（若明显不同 → 回填修正费用模型） |
| 同帧多操作 | 同一帧内的多条操作按序注入且落在同一逻辑帧 |
| 技能门控 | 技能按钮未就绪时不点击（`skill_ready` 识别结果与实际一致） |

**记录**：执行记录 JSON（`data/derived/logs_h12-4_axisrun.json`）+ 台账 T-052（含登录时间/端/账号尾号与额度使用）。

## 7. 若某步失败

1. 时钟类失败 → 检查尺子是否在跑、`isRunning` 是否为 true、分辨率是否 16:9；
2. 标定类失败 → 用 `grid` 手工读坐标重新 `mark` + `apply`；
3. 注入类失败 → 先确认 ADB 设备（`adb devices`）、窗口焦点策略；PC 端改用 directinput 后端；
4. 任何与账号资源相关的情形 → **立即停止并询问用户**。
