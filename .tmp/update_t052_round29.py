# -*- coding: utf-8 -*-
"""update_t052_round29.py — 写入 T-052 第二十九轮（费用上限经济学 / 实机演习验证）。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    ' **第二十九轮（费用上限经济学 + 实机演习验证）**：'
    '①锁定整份轴表的**真正前置条件**：h12-4 上限 = 20(rune) + 5×被拆储备 + 2×到达平民（天花板 99），'
    '而弦惊 23 费 / 蕾缪安 22 费(满潜 20) / 令 12 费(满潜 10) ⇒ **上限 20 时根本放不下弦惊**，'
    '作者作战记录第 7 行「29.0s 部署弦惊 D11」必须先有 ≥+3 的上限抬升；'
    '②**实机（MuMu12 演习，未消耗理智）验证**：关卡详情原文「我方费用上限大幅降低」「〈街头应急储备〉被摧毁后获得一定费用及费用上限」'
    '与我们黑板模型 `{max_cost:5, cost:5}` 一致；准备阶段 HUD 实测「20 MAX」上限 20、剩余可放置角色 9(=characterLimit)、'
    '卡面费用 10/20(=令/蕾缪安满潜费用) 全部与模拟器吻合；演习链路实机走通（关卡详情→演习→编队(令S3/蕾缪安在队)→开始行动→准备阶段），'
    '推进了需求 2.6 的「自动进关」环节；'
    '③**新增范围覆盖实测 `diag_range_cover.py`**：令 C12→(2,11) 范围 3-1 只罩右侧走廊（不含储备）；'
    '**蕾缪安 G9→(6,8) 范围 3-9 同时覆盖两个储备** ⇒ 她就是设计上的「拆储备位」；'
    '④**未闭合断点**：两条抬升路径按我们的模型都赶不上 29s（平民最早 45.0s 到达=实测吻合；储备只有蕾缪安够得着、'
    '20s 落地起 2.7s/发、最快约 31s 拆掉）⇒ 要么作者「绝对时间」是 PRTS+ 的**按键意图时刻**'
    '（使用须知明确写「轴以费用与费用条为唯一时间参照」且费用到顶时该参照失效，工具会重试），要么还有未建模的上限来源；'
    '下一步用实机每 2s 读右下角费用区，直接测出「MAX 何时消失、费用何时突破 20」来定案；'
    '⑤**两条计划-模拟分歧**（均指向「记录时刻=按键意图」）：蕾缪安 S1 spCost8/攻击回SP/2.7s 一击，作者在落地后 5.1s/7.2s 就按技能'
    '（我们判 SP 不足而拒，对轴模式 skill_reject 14）；'
    '⑥**引擎修复**：`deploy()` 新增**占格不可部署**（occupied）拒绝——此前可以把弦惊放到「街头应急储备」所在的 (5,7)，'
    '实机不可能，且会掩盖"必须先拆储备"的因果；'
    '⑦新增标定/诊断脚本：`code/vision/apps/calibrate_battle_area.py`（9×13→像素，接缝自相关法，'
    '列距 137±7px、行距 100±20px，用两个储备实测列距≈130px 交叉验证；精度待提升，已在执行端 config 记为 TODO）、'
    '`sim/draft/diag_spawn_flow.py`、`diag_civilian.py`、`diag_civilian2.py`、`diag_cost_timeline.py`、`diag_range_cover.py`、'
    '`diag_runes.py`、`diag_sheet1.py`；'
    '⑧**Sheet1 语义解明**：Sheet1 的「66.1过1下龙」等标签里的数字 = 371.9 − 对应作战记录时间（逐行验证常数 371.9），'
    '是**倒计时视图**，不是独立时间源 ⇒ 作者自己记录的首条龙就是 **29.0s**；'
    '⑨回归全绿：sim 技能 4/4、案例顺延 PASS；文档 `knowledge/04/41` 新增 §7.47/§7.48。 | 2026-09-14 |'
)

s = io.open(P, encoding='utf-8').read()
anchor = '\n\n## 冲突记录'
if anchor not in s:
    raise SystemExit('anchor not found')
s = s.replace(anchor, ADD + anchor, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('T-052 已追加第二十九轮；行数 =', len(s.splitlines()))
