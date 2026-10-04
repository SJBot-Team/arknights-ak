# -*- coding: utf-8 -*-
"""T-052 追加：第二十一轮（技能放不出的根因：打不到人 → 坐标/射程疑点）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第二十一轮（打不到人 = 技能放不出的根因）**：①正确上限模型下跑完整轴后诊断：'
    '**我方出手仅 令 1 次 / 蕾缪安 2 次**（敌人出手 27+ 次），蕾缪安 SP 恒为 0/8（靠攻击回 SP）⇒ '
    '技能永远不满；部署因费用不足被拒 448 次；②⇒ 说明**部署位置或射程解释有问题**（实机里这两人是主力输出）；'
    '③新增判据脚本 `check_transform_by_route.py`：用「射程是否覆盖敌人路线格」评估 4 种坐标变换——'
    '`rc_normal` 覆盖 30 格且令@C12 覆盖 6 格，**当前使用的 `rc_rowflip` 虽然部署合法率最高（95%）'
    '却让令的射程覆盖 0 个路线格**；④**矛盾点**：合法率与覆盖度两个判据互相打架，必有一处解释错，'
    '候选：坐标变换本身 / 射程-朝向的旋转约定（`range_table.grids` 的 {row,col} 与我们的 [col,row]）/ '
    '路线格近似过于粗糙（仅 45 格样本）；⑤**该问题优先级高于继续对时间线**——不解决则模拟器永远打不到人、'
    '永远没有 SP、技能永远放不出；⑥案例测试与技能自检保持通过（它们不依赖实战命中）。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第二十一轮（打不到人' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
