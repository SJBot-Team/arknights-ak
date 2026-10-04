# -*- coding: utf-8 -*-
"""T-052 追加：第二十二轮（定位到"过早阵亡"与"敌人到得晚"两个根因）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第二十二轮（打不到人：定位到两个根因）**：①先修正上一轮判据——改用**逐帧实测敌人占据格**'
    '（`check_coverage_empirical.py`）后，`rc_rowflip` 下令的射程覆盖 **5 格（不是 0）**'
    '⇒ 坐标变换**不是主因**（`rc_colflip` 覆盖最多 24 但合法率仅 27%）；'
    '②`diag_targeting.py` 逐单位统计暴露真因：**令在 21.2s 就阵亡**（存活仅 592 帧、出手 1 次）、'
    '**蕾缪安 183.4s 阵亡**；且即便存活也只有 **6% 的帧有目标**（实机里令从 ~5s 起就在输出）；'
    '③⇒ 两个根因：**(a) 敌人关卡实例数值（enemyDbRefs.overwrittenData + runes）未正确叠加 / 干员减伤链未建**'
    '（我们这边岗哨密探长单次 662 伤害 vs 令 1429 HP ⇒ 3 击阵亡）；**(b) 敌人出场/移动时序与实机有差距**'
    '（moveMultiplier、波次 preDelay、路线跟随保真度）；'
    '④**确立调试顺序**：先修「敌人数值叠加 + 干员生存」→ 再谈伤害/SP/技能 → 最后才是时间线对齐；'
    '⑤新一轮的判据脚本与诊断脚本已入库并同步镜像。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第二十二轮（打不到人' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
