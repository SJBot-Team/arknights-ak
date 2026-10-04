# -*- coding: utf-8 -*-
"""在 tasks_registry.md 的 T-052 行追加「合规声明（2026-09-14）」记要"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**合规声明（用户 2026-09-14 追加，与客户端合规声明同等重要）**：①登录必须**逐次**获用户同意、'
    '仅限指定账号，**禁止使用任何来源的「登录界面未保存的账号」**；②**顶号/断线后再登录不属于首次登录**，'
    '需再次同意；同意换号且已登录时须**先退出再登录**确认；③**禁止动用除「理智」外的任何账号资源**，'
    '禁止打开仓库/基建/抽卡/商店/邮件/养成/模组等界面（误触立即退出）；④练度/技能/模组/潜能/信赖不匹配时'
    '**禁止自行提升**，须请示用户（换号或提供助战）；⑤任何可能构成作弊或动用虚拟资产的操作 **AI 禁止自行尝试**。'
    '**本次授权**：账号尾号 ******，**MuMu12 模拟器 1 次 + PC 端 1 次**（共 2 次登录额度，已用 0/0），'
    '允许消耗仅「理智」。落地：`ak/meta/合规声明_自动打图与账号.md`（+`ak/docs/` 镜像）、`ak/README.md`、'
    '`management/AI_GUIDE.md`「自动打图 / 账号合规准则」、`knowledge/04/41` §八.2、`code/vision/AUTO_PLAY.md` 文首，'
    '并在 `configs/axis_h12-4.json` 增加 `compliance` 段 + `apps/run_axis.py` 实注入守卫'
    '（未同意时 `--live` 直接拒绝，退出码 2；登录动作默认禁用）。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip()), row[-60:]
assert '合规声明（用户 2026-09-14 追加' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
