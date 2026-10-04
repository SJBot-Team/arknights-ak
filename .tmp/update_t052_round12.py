# -*- coding: utf-8 -*-
"""T-052 追加：第十二轮（实机标定助手）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第十二轮（实机标定助手）**：①新增 `code/vision/apps/calibrate.py`——'
    '`auto`（自动探测费用数字 ROI、待部署卡槽行与等距卡槽、战场区域估计、技能图标候选，输出标注图+配置补丁）、'
    '`mark`（手工标注任意 ROI）、`grid`（像素坐标网格便于人工读坐标）、'
    '`apply`（补丁合并进配置，自动备份 .bak）；'
    '②**用真实游戏录像帧验证**（无需游戏进程）：1600×900 下费用数字 ROI 探测 **一次命中**'
    '`(1525,619,1565,670)`（标注图核对完全正确）；判据由"取最上面一行"改为**取字号最大的一行** '
    '（费用数字明显大于「剩余可放置角色」等小字）+ 白色低饱和过滤——这是本轮踩坑后的关键改进；'
    '③卡槽行改用**按整行等距重建 12 槽**（x 中心 66…1533，与画面一致），比逐卡检测稳；'
    '④战场区域与技能图标仍为粗估，需实机微调；⑤标定流程落地为「离线先跑一遍 → 现场只确认」，'
    '把实机会话的现场工作量压到最小。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第十二轮（实机标定助手）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
