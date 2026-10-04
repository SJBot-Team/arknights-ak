# -*- coding: utf-8 -*-
"""T-052 追加：第十六轮（实机首日：环境打通 + 费用数字时钟落地）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第十六轮（实机首日）**：用户授权实机验证（并补充合规：**一般优先用演习模式**，避免理智消耗，'
    '只有以通关为目标时才用理智）。①**环境打通**：MuMu12 adb `127.0.0.1:16384` 可连，'
    '`adb exec-out screencap` 取到 1920×1080 画面（注意 PowerShell 重定向会破坏二进制，需用 cmd /c）；'
    '②**无需登录**——用户已在 MuMu 内把 h12-4 编队摆好（令 Lv90 + 蕾缪安 Lv90，正好是案例阵容），'
    '登录额度（MuMu12/PC 各 1 次）**未动用**；③**进入战斗并确认是「演习中」**（消耗演习券而非理智），'
    '按新补充的合规说明继续；④**新增实机时钟**：`plugins/recognize/cost_number.py`（读右下角费用数字）'
    '+ `CostNumberClock`（费用数字 + 脚本自身消耗记账 → 绝对帧），实测 **MuMu 画面读数为「20」、'
    '置信度 0.962**，且战斗外界面（任务失败页）正确返回 None；**录像自举的 0~9 模板可直接跨分辨率复用**；'
    '⑤标定成果写回配置：费用数字 ROI `(1795,730,1915,805)`、卡槽（令 [1637,975] / 蕾缪安 [1825,975]）、'
    'battle_area 粗估；⑥**待办**：`battle_area` 的 9×13 格点→像素映射需精确标定（当前粗估），'
    '以及技能/撤退按钮 ROI——之后即可做实注入跑轴。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第十六轮（实机首日）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
