# -*- coding: utf-8 -*-
"""T-052 追加：第十五轮（需求 2.6 导航状态机骨架）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第十五轮（需求 2.6 导航骨架）**：①新增 `code/vision/plugins/task/nav_flow.py`——'
    '受合规约束的导航状态机：单步语义「等模板出现（可重试）→ 点击 → 等预期界面」，任一步失败**立即中止不瞎点**；'
    '**合规内建**：步骤名/模板名命中「登录/login/account/仓库/基建/抽卡/商店/邮件/养成/精英化/模组/购买/领取」'
    '→ **加载期直接拒绝**（返回 compliance_rejected），登录须用户逐次同意后单独处理；`dry_run=true` 为默认安全值；'
    '②`apps/test_nav_flow.py` 合成屏幕序列自检 **4/4 通过**（正常流程 / 超时中止且 0 次点击 / 合规拒绝 4 例 / dry-run 不注入）；'
    '③配置样例 `configs/nav_h12-4.json`（终端→作战→章节→关卡→开始行动→编队出战六步，模板名待实机截图填充）；'
    '④需求 2.6 状态由 🔴 **转为 🟡**（状态机与合规护栏就绪，缺真实模板与选干员/技能/模组步骤）；'
    '⑤验收文档 `knowledge/04/42` 的 2.6 行与未完成项 B 已同步更新。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第十五轮（需求 2.6 导航骨架）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
