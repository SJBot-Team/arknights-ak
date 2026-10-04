# -*- coding: utf-8 -*-
"""T-052 追加：第四轮（录像费用轨迹读取工具 + 全片结果）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第四轮（录像费用轨迹自动读取）**：①新增离线工具 `code/vision/apps/video_cost_timeline.py`'
    '（bootstrap/scan/montage 三模式：ROI 按「白色连通域分行取最上行」多帧投票锁定、'
    '**数字区学习**（费用图标跨帧位置固定 → 自动剔除，实测 x∈[1459,1495] 16/16 帧命中）、'
    '20 个读数自举 0~9 模板、消耗事件按**局部回费速率**扣除）；'
    '②对 5 个 H12-4 候选录像跑前 90s：样本有效率 96~99%、匹配置信度 0.98~1.00；'
    '③结果：`(128)` 开局 **2 DP/s（2 倍速）**、20 费骤降@17.2s、18@34.8s、18@46.2s、17@69.0s；'
    '`(132)` 18@42.4s；`(134)` 18@9.6s；`(519)` 37@1.8s、30@18.4s；`mkv(13-46)` 30@8s、18@35.6s、18@49.2s、16@72.6s；'
    '④**结论：没有任何候选录像在前 90s 呈现本轴签名（令10→蕾缪安20→弦惊23×N）**，'
    '结合 `(128)` 待部署区 11 张卡 ⇒「双」目录录像是多种不同队伍的解，不能直接作逐帧基准；'
    '⑤曲线出现长时间持平（21~29s 恒为 5）⇒ 录像含**暂停/倍速切换**，逐帧锚定必须先做「暂停检测 + 倍速判定」；'
    '⑥费用数字 ROI 实测值可直接用于 `cost_bar.roi` 标定（各分辨率见 knowledge/04/41 §7.7 表）。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第四轮（录像费用轨迹' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
