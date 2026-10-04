# -*- coding: utf-8 -*-
"""T-052 追加：第十轮（执行端 SP 门控 + 技能栏读取边界）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第十轮（执行端 SP 门控同构）**：①`ak_sim_axis_compat.py` 新增 `skill_sp_profile/sp_after`'
    '（直读 gamedata 表，与模拟器同一套 SP 参数）；②`axis_runner` 新增 `sp_gate`：按表值推算 SP，'
    '不足则顺延技能行，召唤物撤退给召唤者 +4 SP（令天赋），技能激活中按"游戏忽略该点击"处理；'
    '③模拟器新增 `sp_assume_attacking`（攻击回复按理想速率），两端使用同一假设；'
    '④**自检新增段 F：`apps/test_ruler_clock.py` 现 6 项全通过**——SP 门控起点一致'
    '（模拟 1250 帧 vs 执行端 1248 帧，Δ2；门控前逐条 ±1 帧）；'
    '⑤**发现边界（重要）**：技能"激活之后"的状态（是否仍在激活、弹药余量、按钮是否就绪）'
    '**无法仅靠表值同构**——模拟器里干员未实际攻击则弹药技能不结束，打图端也无法预知实际攻击次数；'
    '⇒ 必须实机读取技能栏（就绪高亮/SP 条），已登记为打图端缺口 12（计划新增识别器 `skill_ready`，'
    '先用合成图离线自检）。这说明实机验证不只是验收，而是**补齐模型所必需**的一环。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第十轮（执行端 SP 门控同构）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
