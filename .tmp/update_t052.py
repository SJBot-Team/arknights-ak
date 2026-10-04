# -*- coding: utf-8 -*-
"""在 tasks_registry.md 的 T-052 行追加第二轮进展（安全：只改该行尾部）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第二轮（费用尺时钟 + 轴表语义修正）**：①`code/vision/plugins/clock/cost_ruler.py` 落地**逻辑帧时钟**'
    '（费用尺本机 API：纯 stdlib WS 客户端 + HTTP 快照；自研费用条识别器兜底；虚拟时钟用于 dry-run），'
    '含**帧内插值**（frame_now = totalElapsedFrames + 收到快照后墙钟×30，上限 2 帧）、'
    '**Windows timeBeginPeriod(1)** 精度保障、丢帧/遮挡诊断；据此明确「费用条满以后的精确帧」由尺子 '
    '`totalElapsedFrames`（费用条循环累计帧，与消耗无关）直接解决；②`axis_runner` 重写 v2：绝对帧调度 + '
    '同帧多操作分组 + 执行诊断（迟到真实帧/读数年龄/丢帧/像素宽）；③**轴表语义修正**（重要）：'
    '费用列仅 8 行为稀疏锚点（空值不可顺延）、换算须含「累计已消耗 + 撤退 50% 返还」，'
    '并新增顺序语义夹紧诊断；④**两端公式交叉校验一致**（`ak_sim.axis.resolve_frames` vs '
    '`build_frame_schedule`，h12-4 全 50 条帧计划完全相同）；⑤离线自检 `apps/test_ruler_clock.py` **4/4 通过**'
    '（假尺子 HTTP + 假 WS 服务器 + 虚拟时钟全轴 dry-run，最大迟到 0.032 真实帧）；'
    '⑥时基对照：`cost-relative` 与模拟动态执行 **±2 帧内 16/50**（前 16 条），`abs-seconds` 仅 2/50；'
    '费用锚点自检 **7/8 完全一致**；⑦新增 `retry_on_cost`（费用不足顺延）执行语义：成功 26→32、最大帧差 4599→2593；'
    '⑧**开放问题**：弦惊（23 费）在轴表两种时基下都排在费用不足的时刻（21~29s 时费用仅 1~9）→ 需实机/录像判定；'
    'E 盘 2025-11 录像经抽查与本轴（2026-02 修改）不对应，视频逐帧核对待换对应录像。'
    '详见 `knowledge/04/41` §七。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip()), row[-60:]
assert '第二轮' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，行长度', len(row), '→', len(row2))
