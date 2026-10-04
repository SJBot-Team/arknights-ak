# -*- coding: utf-8 -*-
"""append_t052_cal.py — 追加"费用条标定精修（bar_px 132→140）+ 长窗复核"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第77轮】★★★★**费用条标定精修（`bar_px` 132→140）并用长窗实测复核**：'
 '①**探针增强**：`apps/live_clock_probe.py` 增打 **`fill_px`** 并统计「最小/中位/p95/最大」，'
 '以便用实测数据反推"满条真实像素长度"，不再依赖目测；'
 '②**★长窗实测（14 s）**：`fill_px` **最大 140**（= ROI 宽度）、中位 94、p95 137；'
 '**415 帧 / 13.96 s = 29.7 帧/秒**（1X 应为 30.0）、满条 **14 次**（≈1/s）'
 '⇒ **满条长度应为 140px，而非原先目测的 132px**（132 会让末段 8px 被削平成 `frame=30`，'
 '每周期约 **1.7 帧死区**）；'
 '③**越界钳位**：`DEFAULT_BAR_PX = 140`（= ROI 宽度），并写入实测依据注释；'
 '④**复核**：**离线回归 `test_costbar_roi` 仍全通过**（`fill_px=63`、`frame=14`、`bar_px=140`）；'
 '**实机短窗（6.35 s）**：满条 **6 次**、推进 **194 帧 ⇒ 30.6 帧/秒**（偏差来源已定性为**采样混叠**：'
 '每次 adb 截图+识别 ≈0.65s，而条周期 1.0s，约 1.7 采样/周期）；'
 '⑤**结论**：费用条时钟在实机上的**绝对帧基准已可用**（满条次数×30 + 相位），'
 '运行态 ~30 帧/秒、暂停态冻结 —— 用户方案第①步与第④步的判据均已具备；'
 '⑥**下一步**：**(a)** 双通道互验精修（「填充比例 ↔ 费用数字跳变」两端对齐，'
 '把残差从 ~2% 收敛）；**(b)** 第②步**子弹时间**（操作前 ≈1s 拖出干员，用相位推进速率验证确已减速）；'
 '**(c)** 第③步**过帧**（接 MuMu 过帧宏）；**(d)** 第④⑤步按轴表部署 芬@D6(934,502)、月见夜@D4(1182,502)；'
 '**(e)** D1 提交通道的新尝试：**真实光标 `SetCursorPos` + `PostMessage` 宏键**（宏动作含 `click_rel:mouse`）；'
 '⑦**合规**：仅图形界面级点击与截图 + 只读识别；未登录、未消耗理智、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
