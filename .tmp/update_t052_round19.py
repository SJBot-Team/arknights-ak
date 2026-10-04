# -*- coding: utf-8 -*-
"""T-052 追加：第十九轮（储备摧毁方查明 = 敌人；并推翻此前的案例时间线）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第十九轮（储备摧毁方查明 + 推翻此前时间线）**：①枚举轴表**全部 19 个部署点**的射程，'
    '**没有任何一个覆盖**储备 (5,6)/(5,7) ⇒「我方打掉储备」不成立；结合储备 **block=5**、HP 8000、'
    '位于敌人行进路线 ⇒ **敌人会打它**，关卡文本「被摧毁后获得费用及费用上限」是**补偿玩家**；'
    '②已实现：敌人索敌与阻挡判定纳入 `DEVICE`；实测跑完整轴得到 '
    '**装置被摧毁于 f=668（22.3s）cap 20→25、f=758（25.3s）cap 25→30**（远早于 43s）✓ 机制完全闭合；'
    '③**但这同时推翻了此前的「四方一致」**：在正确上限模型下重跑，弦惊落地为 '
    '**141.0/157.0/277.0/397.0s**，而作者记录为 66.1/86.4/153.3s ⇒ §7.13 那组「43.0/66.0/89.0s 三方吻合」'
    '**是错误上限（99）下的巧合，不能作为案例已对齐的证据**；④原因：上限 20→30 后，轴表其它操作'
    '（U-Official 3、夜刀 8、傀影 8、艾拉 12、雷鸣地雷 5×3…）与弦惊（23）在 DP 上竞争，'
    '按"不足即顺延"语义弦惊被反复挤后；⑤**下一步**：用正确上限+储备机制重做案例对齐，'
    '输出**逐条 DP 账本**（谁花多少、何时顺延），并与 Sheet1 的 15 个时间点重新对齐；'
    '验收文档 42 已在"四方一致"处加⚠️更正说明。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第十九轮（储备摧毁方查明' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
