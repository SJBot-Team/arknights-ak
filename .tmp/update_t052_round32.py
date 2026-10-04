# -*- coding: utf-8 -*-
"""update_t052_round32.py — 写入 T-052 第三十二轮（★找到缺失机制：令的模组把弦惊费用降到 18）。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    ' **第三十二轮（★★找到缺失机制：令的模组 → 弦惊费用 23→18）**：'
    '①**结论**：`battle_equip_table.json` 的 `uniequip_002_ling`（令的模组）带 `tokenAttributeBlackboard`，'
    '按召唤物给加值：soul1 cost−3 / soul2 cost−3 / **soul3（弦惊）cost −5、max_hp +250、atk +60** ⇒ '
    '**戴模组的令，弦惊只要 18 费**，而 h12-4 上限是 20 ⇒ **作者 29.0s 那条弦惊本来就放得下**；'
    '我此前"上限 20 放不下 23 费弦惊、29.0s 只能是按键意图"的整条推理**前提错了**——错在把"满配"当作只含等级/信赖/潜能，漏了模组；'
    '②**实现缺口**：`data.get_operator()` 早已读模组的 `attributeBlackboard`（干员自身）并把 phase 存进 `moduleInfo`，'
    '但**没人把 `tokenAttributeBlackboard` 用到召唤物上** ⇒ 弦惊一直按 23 费算、本体加值也没生效；'
    '③**修复**：`engine.deploy()` 部署召唤物时反查 owner 的 `module_info.tokenAttributeBlackboard[本 token key]`，'
    '**先按 cost 调整需求量（在费用检查之前）**，再给本体应用 max_hp/atk/def 加值；干员的 `module_info` 存入 `unit.extra`；'
    '④**连锁效果**：弦惊费用 23→**18**；首条弦惊 55.8s→**38.8s**；前三条 38.8/56.0/**83.0**s（作者 29.0/49.2/**83.0**，第三条完全一致）；'
    '严格模式 FAIL@51.5s→**FAIL@53.7s 且首次出现击杀**；召唤物 AoE 19→**53 次**；上限 22→24；'
    '⑤**剩余 ~10s/7s 偏差已定位**：目标格 (3,10) 被路过敌人占用（修复流速后敌人真按检查点走、占用更久），'
    '轴执行器按"重试直到成功"等待（= PRTS+ 行为）⇒ 下一步核对该等待窗口/格位空闲预判；'
    '⑥**另一条独立验证**：实机（无干员）费用全程保持 `20 MAX` 直到 51.5s 判负 ⇒ 51.5s 前无平民到达、无储备被拆，'
    '与模拟器"上限 20 保持不变"一致；叠加实机漏怪 44.3/46.0/51.5 与模拟 42.0/44.5/51.5 ⇒ **三条证据链咬合，29.0s 之谜关闭**；'
    '⑦**装置语义 A/B**：新增开关 `devices_block_enemies` / `enemies_attack_devices`（默认 False，按用户更正）；'
    '打开后储备仍在 57.2s/100s 才被拆 ⇒ **任何装置语义都无法解释 29.0s 落龙**，进一步佐证真因是模组；'
    '⑧回归全绿：sim 技能 4/4、案例顺延 PASS；文档 `knowledge/04/41` 新增 §7.53/§7.54。 | 2026-09-14 |'
)

s = io.open(P, encoding='utf-8').read()
anchor = '\n\n## 冲突记录'
if anchor not in s:
    raise SystemExit('anchor not found')
s = s.replace(anchor, ADD + anchor, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('T-052 已追加第三十二轮；行数 =', len(s.splitlines()))
