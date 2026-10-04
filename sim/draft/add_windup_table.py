# -*- coding: utf-8 -*-
"""add_windup_table.py — 把"前摇比例"改为**按职业/子职业（模板）分组配置**

## 依用户补充（2026-09-15）
> 「不同敌人和不同干员的前摇均可能不同，这可能与**职业模板**有关，
>   也可能与**技能期间的攻击模组**有关，**敌人也是**。」

⇒ 此前"统一比例（干员 0.55 / 敌人 0.10）"只是粗糙近似；
本次改为**表驱动**：
- 命中"子职业/职业"或"敌人模板" ⇒ 用该条目的比例；
- 未命中 ⇒ 回退到默认（干员 0.55 / 敌人 0.10，由 1-1 标定反推）。

**同时**保留 `u._windup_ratio` 单点覆盖能力（便于按标定逐单位校准）。

## 数据来源
- 干员：`character_table.json` 的 `profession`（PIONEER/WARRIOR/SNIPER/…）与 `subProfessionId`；
- 技能模组：技能 `blackboard`（如 `attack@…`）可作为"技能期间攻击模组"的判据；
- 敌人：`enemy_database.json` 的键前缀（如 `enemy_1000_gopro`）与其 tags/motion。

**注**：当前标定素材只有 1-1（芬＝先锋、月见夜＝近卫）⇒ **无法据以细分所有职业**，
故本表先给出**结构**与"已知/默认"值，待更多素材逐项校准。
"""
from __future__ import annotations

import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

ENGINE = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py'

TABLE = '''

# ---------------- ★普攻前摇比例表（按职业/模板分组） ----------------
# 依用户 2026-09-15 补充：不同干员/敌人的前摇可能不同，与**职业模板**及
# **技能期间的攻击模组**有关。
# 数据表无"前摇"字段（见 probe_windup_field.py）⇒ 本表由"标定反推 + 扫描校准"得到。
# 单位：占 `attack_interval_frames` 的比例。未命中则用默认值。
WINDUP_RATIO_BY_PROFESSION = {
    # 干员职业（character_table.profession）
    'PIONEER': 0.55,     # 先锋（芬 1-1 标定反推）
    'WARRIOR': 0.55,     # 近卫（月见夜 1-1 同场，未单独标定 ⇒ 暂用同值）
    # 以下为**待校准**的占位（有素材后按标定逐项修正）
    'SNIPER': 0.50,      # 狙击
    'CASTER': 0.50,      # 术师
    'MEDIC': 0.50,       # 医疗
    'SUPPORT': 0.50,     # 辅助
    'TANK': 0.55,        # 重装
    'SPECIAL': 0.55,     # 特种
}
WINDUP_RATIO_DEFAULT_ALLY = 0.55     # 干员未命中职业表时的默认
WINDUP_RATIO_DEFAULT_ENEMY = 0.10    # 敌人默认（1-1 扫描最优，敌人前摇很短）
'''

NEW_FN = '''    @staticmethod
    def _windup_frames(u) -> int:
        """普攻前摇帧数 = `round(攻击间隔 × 比例)`。

        **比例来源**：数据表无"前摇"字段 ⇒ 由 **1-1 标定反推 + 二维扫描校准**；
        并按用户补充改为**表驱动**（不同干员/敌人可能不同，与**职业模板**、
        **技能期间攻击模组**有关）：
          1. `u._windup_ratio`（单点覆盖，最高优先级，便于逐单位标定）；
          2. `WINDUP_RATIO_BY_PROFESSION[u.profession]`；
          3. `WINDUP_RATIO_DEFAULT_ALLY / _ENEMY`。

        **技能期间攻击模组**：若技能 blackboard 含攻击模组字段（如 `attack@atk_scale`
        等）且技能激活，可按需在 `u._windup_ratio` 上做覆盖 —— 该分支留待素材校准。
        样本规模：18 条事件/1 关卡/1 对局 ⇒ **存在过拟合风险，需交叉验证**。
        """
        r = getattr(u, '_windup_ratio', None)
        if r is None:
            is_ally = getattr(u, 'side', 'ALLY') == 'ALLY'
            if is_ally:
                prof = str(getattr(u, 'profession', '') or getattr(u, 'sub_profession', '') or '')
                r = WINDUP_RATIO_BY_PROFESSION.get(prof.upper(), WINDUP_RATIO_DEFAULT_ALLY)
            else:
                r = WINDUP_RATIO_DEFAULT_ENEMY
        n = int(round(float(u.attack_interval_frames) * float(r)))
        return max(0, n)'''


def main():
    s = io.open(ENGINE, encoding='utf-8').read()
    changed = []
    # ① 插入比例表（放在首个 class/def 之前，即模块级）
    if 'WINDUP_RATIO_BY_PROFESSION' not in s:
        idx = s.find('class ')
        if idx > 0:
            s = s[:idx] + TABLE.strip('\n') + '\n\n\n' + s[idx:]
            changed.append('比例表')
    # ② 替换 _windup_frames
    start = s.find('    @staticmethod\n    def _windup_frames(u) -> int:')
    if start > 0:
        end = s.find('\n    def ', start + 10)
        if end > 0:
            s = s[:start] + NEW_FN + '\n' + s[end + 1:]
            changed.append('_windup_frames')
        else:
            print('★未找到 _windup_frames 结束位置')
    else:
        print('★未找到 _windup_frames')
    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(s)
    print('已修改:', ', '.join(changed) if changed else '（无变化）')


if __name__ == '__main__':
    main()
