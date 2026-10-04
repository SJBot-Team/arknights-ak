# -*- coding: utf-8 -*-
"""
engine.py — 战斗主循环（模拟核心）

结构（对应 knowledge/24 伪代码）：
  每帧 tick：①费用回复 ②波次出生 ③单位 tick（敌人→干员）④buff 收尾 ⑤结算检查
  敌人 tick：状态机 → 寻路移动（方向+避障+惯性）→ 检查点/终点判定 → 阻挡判定 → 攻击
  干员 tick：SP 回复 → 索敌 → 攻击 → 技能触发

已复刻（T1/T2）：伤害公式、攻击间隔帧化、费用回复、波次时序、阻挡半径、仇恨(部署时间)
待核（🟡/🔴）：同帧执行顺序、阻挡偏移、前摇时序、坐标变换细节、危机合约词条
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from . import combat, fp
from .battlemap import BattleMap, Route, build_routes
from .data import get_enemy, get_operator, get_range, load_level
from .rng import AKRandom
from .units import Unit, make_enemy, make_operator

FPS = fp.FPS
MOVE_MULTIPLIER_DEFAULT = 0.5      # 关卡 options.moveMultiplier（1-7 实测 0.5）
COST_REGEN_PER_SEC = 1.0
COST_MAX_DEFAULT = 99
BLOCK_RADIUS = 0.7071              # 阻挡判定半径（knowledge/02、23）
# ★阻挡判定的"最大接近距离"（格）：欧氏距离 ≤ 该值即被阻挡。
#   由 1-1 标定校准为 **1.0**（约等于"相邻格中心距离"）：
#   - 原 `BLOCK_RADIUS+0.5 = 1.2071` **过松** ⇒ 对角方向 1.2 格也被判阻挡，
#     敌人停在 1.2 格处 ⇒ 游走出近战 1 格范围 ⇒ 我方打不到；
#   - "格坐标 4 邻接" **过严** ⇒ 敌人的格坐标只在跨格时变化，必须走进单位所在格才判阻挡。
BLOCK_DISTANCE = 1.0
BLOCK_SCAN_INTERVAL = 3            # 每 3 帧扫描（knowledge/21、38）
AGGRO_PRECISION_FRAMES = 3         # 仇恨 0.1 精度 → 3 帧一组（knowledge/21 cv39950636）
CHECKPOINT_RADIUS = 0.05           # 检查点完成半径（knowledge/20）
RETRYABLE_REASONS = ("cost", "sp", "occupied", "tile")

# 轴操作「可重试」的失败原因：打图端（PRTS+）的做法是**反复按同一行直到成功**，
# 所以「费用不足 / SP 不足 / 目标格被占用 / 格子不可部署」都应视为**暂时性**失败并重试，
# 而不是把这一行当作失败跳过。作者作战记录里的时间因此是「按键意图时刻」，§7.45/§7.51
CHECKPOINT_ARRIVE_PAD = 0.0        # 检查点到达宽容（关卡 reachDistance=0 ⇒ 必须走到点上，见 §7.51）        # 到达检查点的额外宽容（过大会让敌人提前拐弯、抄近路，见 §7.51）
RANGE_ROW_SIGN = -1                # 范围表 row 方向 → 世界 y 方向（🟡 待比对固化）

DIRECTIONS = {'右': (1, 0), '左': (-1, 0), '上': (0, 1), '下': (0, -1),
              'RIGHT': (1, 0), 'LEFT': (-1, 0), 'UP': (0, 1), 'DOWN': (0, -1)}


# ================= ★★「体积 / 范围」的五个语义必须区分（用户 2026-09-15 明确） =================
#
# 用户原话要点（★作为实现约束）：
#   1. **攻击索敌应以「方格范围」判定** —— 选目标时按格计算范围；
#   2. **索敌时需要考虑「受击判定体积」** —— 单位有一个受击判定体积，索敌阶段要纳入；
#   3. **该体积主要用于完成一次索敌**，而**不是**用于判断"是否被范围攻击命中"；
#   4. **部分范围攻击判定的是「目标中心是否位于选定格内」** ⇒ 这类命中与体积**无关**。
#
# ┌────┬──────────────┬────────────────────────┬──────────────────────┬──────────────────┐
# │ #  │ 语义          │ 参数                    │ **关联事件**（logs/切片）│ 代码路径          │
# ├────┼──────────────┼────────────────────────┼──────────────────────┼──────────────────┤
# │ ①  │ **碰撞体积**   │ `collider_radius(u)`    │ `block`、`block_snap` │ `_block_scan`    │
# │ ②  │ **受击判定体积**│ `hit_radius(u)`         │ **`target_select`**   │ `is_targetable`  │
# │ ③  │ **攻击范围**   │ `cells_in_range(u)` 方格 │ 索敌的**主判据**       │ `cells_in_range` │
# │ ④  │ **阻挡判定**   │ `BLOCK_CAPTURE_DISTANCE`│ `block`、`block_snap` │ `_block_scan`    │
# │ ⑤  │ **范围攻击命中**│ `aoe_targets(cells)`    │ `hit`（AoE 结算）      │ `aoe_targets`    │
# └────┴──────────────┴────────────────────────┴──────────────────────┴──────────────────┘
#
# ★★★用户 2026-09-15 进一步明确"**两个阵营的范围表示不同**"：
#   **(A) 我方（干员）索敌 = 方格范围**
#       - 近战干员（如芬）的索敌范围 = **2 个方格**（自身格 + 朝向前方 1 格，表驱动）；
#       - **无阻挡时**，**敌人的 0.1 圆进入该范围** ⇒ 干员索敌并起前摇。
#       ⇒ 判据 = `cell(敌人中心) ∈ 范围格` ∨ `dist(敌人中心, 范围格) ≤ 0.1`
#   **(B) 远程敌人索敌 = 半径圆**
#       - 远程敌人的攻击范围 = **一个确定半径的圆**（`enemy_database.rangeRadius`）；
#       - **干员的 0.25 圆处于该圆内** ⇒ 敌人开始攻击。
#       ⇒ 判据 = `dist(敌人, 干员) ≤ rangeRadius ± 0.25`（见 `Battle.enemy_reach`）
#   ⇒ 两侧**不要互相套用**：干员侧是"格 + 目标体积"，敌方远程是"圆 + 我方体积"。
#
# ★三条硬约束（写死在实现里，避免混用）：
#   - **碰撞体积**只用于"物理接触 / 阻挡 / 位移"；**不得**用于索敌；
#   - **受击判定体积**只用于"能否被选为目标"；**不得**用于 AoE 命中；
#   - **AoE 命中**只看"目标中心落在哪一格"，与**任何**体积无关。
#
# 数据来源：客户端 prefab 实测（`knowledge/04/16_…碰撞半径.md`、
# `E:\__file\ak_kb\downloads\collider_report.json`）：**458 个干员主碰撞体 = CircleCollider2D 0.25**；
# 敌人半径分布 0.1（2037）/0.5（124）/1.0（1028）/1.5（84）/2.0（313）/2.5（78）/3.0（36）。
COLLIDER_RADIUS_ALLY = 0.25            # ① 碰撞体积（干员）
COLLIDER_RADIUS_ENEMY_DEFAULT = 0.1    # ① 碰撞体积（敌人，小怪默认）
HIT_VOLUME_ALLY = 0.25                 # ② 受击判定体积（干员）
# ② 受击判定体积（敌人）：★这是**索敌用**的半径。
#   两层来源：
#   - **数据层**：小怪碰撞体实测 **0.1**（`collider_report.json`，2037 个敌人为 0.1）；
#   - **标定层**：1-1 反推的"等效半格"约 0.5（早期用"中心距 ≤ 1.5"近似它）。
#   默认取**数据层 0.1**（有客户端 prefab 依据）；逐单位真实值需从 prefab 抽取后覆盖。
HIT_VOLUME_ENEMY_DEFAULT = 0.1
# ④ 阻挡判定：阻挡者"捕获"敌人的**最大接近距离**（格）。与①碰撞体积**不同**——
#   它是"什么时候算挡下"的规则距离，不是两个圆的半径和。
#   ★2026-09-15 三次演进（务必按顺序理解，否则会调错参数）：
#     ① 初值 1.0（"欧氏距离 ≤ 1.0"）—— 在**错误的索敌语义**（中心距 ≤1.5）下凑出来的；
#     ② 索敌语义按用户指示改为"方格范围 ∪ 敌人 0.1 圆"后，1.0 会让第 2 只敌人
#        "要等被挡下并吸附才打得到"（帧 432 偏差 +18）⇒ 当时改 1.5 补偿；
#     ③ **用户指出"敌人出生速度 0、有加速过程"并按玩家模型补齐后**，
#        敌人到达范围格的时刻由 432 → **417**（标定 414），
#        ⇒ **不需要再用 1.5 补偿**：此时**格判定** `cell_3x3_round` 最优（平均 2.19、≤6帧 15、最大 7）。
#   ⇒ **★默认改用格判定**：`block_rule='cell_3x3_round'`（敌人进入"阻挡者格 + 8 邻格"的 1 格邻域）；
#     `'capture_distance'`（径向）与 `'cell_3x3'`（切比雪夫）保留供对照。
BLOCK_CAPTURE_DISTANCE = 1.5
_HIT_RADIUS_CACHE: dict | None = None


def _load_enemy_hit_radius() -> dict:
    """读**逐敌受击判定半径**表（**带模块级缓存**，避免每场战斗重复读文件）。

    来源优先级：①`data/derived/enemy_hit_radius.json`（人工/标定校正）
    ②`data/derived/enemy_colliders.json`（**客户端 prefab 实测**，由
    `scripts/export_all_enemy_radii.py` 导出：2123 个敌人，分布 0.1(2070)/0.09(1)/0.25(6)/0.3(18)/
    0.35(1)/0.4(2)/1.48(2) ⇒ **"一律 0.1"在原作中近乎实情**）。

    ★语义：这是**受击判定体积**（`CircleCollider2D`, `is_trigger=True`），**不是**碰撞体积；
    阻挡判据用的是干员侧的 `Consts.BLOCK_RADIUS = 0.7071`（见 `BLOCK_RADIUS_DEFAULT`）。
    """
    import json
    import os
    global _HIT_RADIUS_CACHE
    if _HIT_RADIUS_CACHE is not None:
        return dict(_HIT_RADIUS_CACHE)
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(os.path.dirname(here)))      # ak/
    out: dict = {}
    # ② 客户端实测（先读，随后被①覆盖）
    pc = os.path.join(root, 'data', 'derived', 'enemy_colliders.json')
    if os.path.exists(pc):
        try:
            d = json.load(open(pc, encoding='utf-8'))
            for nm, rec in (d.get('enemies') or {}).items():
                for c in (rec.get('colliders') or []):
                    if c.get('type') == 'CircleCollider2D' and c.get('radius') is not None:
                        out[nm] = float(c['radius'])
                        break
        except Exception:                                            # noqa: BLE001
            pass
    # ① 人工/标定校正（覆盖实测）
    p = os.path.join(root, 'data', 'derived', 'enemy_hit_radius.json')
    if os.path.exists(p):
        try:
            d = json.load(open(p, encoding='utf-8'))
            out.update({k: float(v) for k, v in (d.get('radius') or {}).items()})
        except Exception:                                            # noqa: BLE001
            pass
    _HIT_RADIUS_CACHE = dict(out)
    return out


BLOCK_RULE_DEFAULT = 'radius'
# ★④**阻挡半径（统一）** —— 依据知识库（B站 cv25694535 + 代码核验 `knowledge/04/37_阻挡与阻挡偏移_代码核验.md` §一）：
#   `Consts.BLOCK_RADIUS = 0.7071`（= 0.5√2，边长 1 正方形对角线的一半）、`BLOCK_RADIUS_SQUARE = 0.49999037`；
#   大号 = 0.8944（√0.8）。**判定规则：角色类单位的"中点"与敌人的"中点"距离 ≤ 阻挡半径 ⇒ 可被阻挡；
#   阻挡半径只存在于角色类单位身上，敌人没有** ⇒ **对全体单位统一，不存在"逐敌差异"**（用户 2026-09-15 明确）。
#   ★扫描节奏：`Character.FIND_BLOCKEE_TICK = 3` ⇒ **每 3 帧扫描一次**，多个可阻挡时取**最近**的。
BLOCK_RADIUS_DEFAULT = 0.7071
BLOCK_RADIUS_LARGE = 0.8944
# ★**阻挡偏移**常量（`BlockBalancer.CalculateBlockOffset`，RVA 0x7C1050；见 `knowledge/04/37` §三）
BLOCK_OFFSET_MIN_DIST = 1e-5      # 中点重合阈值（重合 ⇒ 不偏移；例 5-3 开局术士）
BLOCK_OFFSET_MIN_LEN = 0.5        # ①长度延长的下限
BLOCK_TWEEN_FRAMES = 6            # `Enemy.BLOCKING_TWEEN_DURATION = 0.2s` ⇒ 6 帧
# 阻挡偏移模式：`'code'` = 文档化算法（默认）；`'cell_center'` = 旧自造"吸附到相邻格中心"（对照用）
BLOCK_OFFSET_MODE_DEFAULT = 'code'
# ★④'边界余量：**实测确定为 0.1**（≈"敌人进入阻挡者所在格"）。
#   依据（第104/105轮）：`margin 1.0`（进 3×3 邻域）偏差**恒定 −32/−31**；
#   **`margin 0.1` 偏差恒定 −4/−1**（阻挡帧 [232,442] vs 标定 [236,443]）⇒ 判据形状对、阈值应取"进入该格"。
#   旧默认 1.0 之所以"伤害更好"，是靠**提前吸附掩盖了"受击体积一律 0.1"这一错误**（见逐敌半径）。
BLOCK_CELL_MARGIN_DEFAULT = 0.1
BLOCK_DISTANCE = BLOCK_CAPTURE_DISTANCE      # 兼容旧名（勿在新代码使用）


def build_schedule(level: dict, rng=None) -> list[dict]:
    """波次时间轴展开。

    ## 算法（★**已与知识库既有沉淀对齐，勿重复推导**）
    来源：`knowledge/04/…/27_露托数据源与出怪时序本地化.md` §三.2（与露托 `parseWaves` 核验过）：
    ```
    waveStart = wave.preDelay
    fragments 串行: fragStart = 上一 frag 结束时刻 + frag.preDelay（首 frag: waveStart + preDelay）
    每只怪 c: 时刻 = fragStart + action.preDelay + action.interval * c   (c = 0..count-1)
    frag 结束时刻 = 本 frag 全部动作的最大时刻
    ```
    字段来源：`knowledge/04/…/33_cpp层战斗类结构与字段速查.md` §4.4（`ActionData` 偏移表）。

    ## ★本轮（2026-09-15）按用户指示先做**字段普查**后的实现边界
    普查脚本 `probe_schedule_fields.py` / `probe_schedule_detail.py`
    （本地 15 个关卡：主线 1-1~1-12、h12-4、肉鸽 1-1、act54side）：

    | 调度特性 | 本地关卡实际使用情况 | 本实现 |
    |---|---|---|
    | `preDelay`/`interval`/`count` 展开 | **全部关卡** | ✅ 已实现（静态时间轴） |
    | `maxTimeWaitingForNextWave` | **全部 = −1（未启用超时清场）** | ➖ 暂不需要（K-021 记为待办） |
    | `blockFragment=True` | **仅 1-11 的一个 TUTORIAL 动作**（非 SPAWN） | ➖ 不影响出怪时刻 |
    | `dontBlockWave` | 本地无 | ➖ |
    | **`randomSpawnGroupKey` + `weight`** | **仅肉鸽 1-1（17 条，g1/g2/g3）** | ✅ **本轮实现**（见下） |
    | `isUnharmfulAndAlwaysCountAsKilled` | h12-4 有 14 条（"无害且恒计为击杀"） | ➖ 影响**计数**不影响出怪时刻（登记待办） |

    ## ★加权随机出怪组（`randomSpawnGroupKey` / `weight`）
    同一 `randomSpawnGroupKey` 内的动作**互斥**：整组按 `weight` **加权随机抽一个**执行
    （`key` 为空串 = "抽到则不刷怪"，肉鸽里确实存在该分支）。
    `randomType` / `refreshType` 的刷新语义尚属推断，
    ⇒ **每次战斗开局抽一次并记录事件**（`spawn_random_pick`），
       由 `Battle` 的**可控随机数**驱动 ⇒ 同 seed 完全可复现（对应需求"随机数可控且尽量与客户端一致"）。
    """
    actions: list[dict] = []
    for wi, w in enumerate(level.get('waves') or []):
        if not w.get('fragments'):
            continue
        t = w.get('preDelay', 0.0)
        for fi, frag in enumerate(w.get('fragments') or []):
            t += frag.get('preDelay', 0.0)
            frag_end = t
            # ★先按"随机出怪组"归并：同组互斥，整组按权重抽一条
            raws = list(frag.get('actions') or [])
            groups: dict[str, list[dict]] = {}
            for a in raws:
                gk = a.get('randomSpawnGroupKey')
                if gk:
                    groups.setdefault(gk, []).append(a)
            chosen: set[int] = set()
            if groups and rng is not None:
                for gk, members in groups.items():
                    weights = [max(0, int(m.get('weight') or 0)) for m in members]
                    total = sum(weights)
                    if total <= 0:
                        pick = 0
                    else:
                        r = rng.next_int(total)
                        acc, pick = 0, len(members) - 1
                        for i, wt in enumerate(weights):
                            acc += wt
                            if r < acc:
                                pick = i
                                break
                    chosen.add(id(members[pick]))
                    actions.append({'t': None, 'type': '__RANDOM_PICK__', 'group': gk,
                                    'key': members[pick].get('key'),
                                    'weight': weights[pick], 'weights': weights,
                                    'wave': wi, 'frag': fi})
            for a in raws:
                if a.get('randomSpawnGroupKey') and id(a) not in chosen:
                    continue          # 同组未中选 ⇒ 本次不执行
                cnt = a.get('count', 1)
                for c in range(cnt):
                    # ★调度起点偏移（T-200e `04/74` §4 建议）：本体消费端走
                    #   `AsyncUtil.WaitForFixedSeconds 0x35293A0`（**定帧**）而非 `WaitForSeconds`，
                    #   调度链自身有固有起点延迟 ⇒ 标定表比模拟器晚 4~7 帧（90→94、360→367）。
                    #   `scheduler_start_offset` 单位=**帧**，默认 0（不改变既有回归），1-1 可试 4。
                    at = (t + a.get('preDelay', 0.0) + a.get('interval', 0.0) * c
                          + SCHED_START_OFFSET_FRAMES / 30.0)
                    frag_end = max(frag_end, at)
                    actions.append({
                        't': at, 'type': a.get('actionType'), 'key': a.get('key'),
                        'route': a.get('routeIndex'), 'wave': wi, 'frag': fi,
                        'hiddenGroup': a.get('hiddenGroup'),
                        'harmless_counted': bool(a.get('isUnharmfulAndAlwaysCountAsKilled')),
                        'blockFragment': bool(a.get('blockFragment')),
                    })
            t = frag_end
    # 随机抽签事件（t=None）排在最前，按 wave/frag 顺序
    picks = [a for a in actions if a['t'] is None]
    rest = [a for a in actions if a['t'] is not None]
    rest.sort(key=lambda x: x['t'])
    return picks + rest


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
WINDUP_RATIO_DEFAULT_ENEMY = 0.25    # 敌人默认（1-1 扫描最优：平均偏差 1.93 帧、最大 7）


@dataclass


class OpLog:
    frame: int
    kind: str
    detail: dict


# ★调度起点偏移（帧）：本体消费端用 AsyncUtil.WaitForFixedSeconds（定帧）⇒ 调度链有固有起点延迟。
#   由环境变量 AK_SIM_SCHED_OFFSET_FRAMES 控制（默认 0，不改变既有回归）。见 4/74 §4。
#   ★默认改为 4 帧（T-200e `04/74`：本体消费端走 `WaitForFixedSeconds` 定帧，调度链有固有起点延迟；
#     实测 +4 后 1-1 的出生帧与标定表**精确一致**：90→94、360→364）。
SCHED_START_OFFSET_FRAMES = float(os.environ.get('AK_SIM_SCHED_OFFSET_FRAMES', '4') or 0)

# ★敌方普攻前摇覆盖（帧，0=不覆盖）：本体 `_preDelay`=0、真值在动画事件帧（见 04/78）。
#   1-1 标定反推值 = 19（236 阻挡 → 255 命中）。用 `AK_SIM_ENEMY_WINDUP` 控制。
#   ★默认 22：由 1-1 标定**扫描**得到（0/15/19/22 → 平均 |Δ| 2.08/3.38/2.88/**1.80**，
#     且命中帧 255↔255、297↔298 基本精确）。**必须**在读出动画事件帧后替换为真值。
ENEMY_WINDUP_OVERRIDE = int(os.environ.get('AK_SIM_ENEMY_WINDUP', '22') or 0)


class Battle:
    """一局战斗的完整状态机。"""

    def __init__(self, level_id: str, seed: int = 0, record: bool = True,
                 record_every: int = 1, max_frames: int = 30 * 600,
                 options: dict | None = None):
        self.level_id = level_id
        self.level = load_level(level_id)
        self.map = BattleMap(self.level)
        self.routes: list[Route] = build_routes(self.level)
        # ★随机出怪组需要 RNG ⇒ 先在关卡里取 seed，建 RNG，再展开时间轴
        self.random_seed = self.level.get('randomSeed', 0)
        self.rng = AKRandom(self.random_seed if seed in (None, 0) else seed)
        self.schedule = build_schedule(self.level, rng=self.rng)
        # 抽签事件（`randomSpawnGroupKey`）落进日志，便于复现与审计（延迟到 logs 建立后）
        self._random_picks = [a for a in self.schedule if a.get('type') == '__RANDOM_PICK__']
        self._pending_pick_logs = [
            OpLog(0, 'spawn_random_pick', {
                'group': _pk['group'], 'key': _pk.get('key'), 'weight': _pk.get('weight'),
                'weights': _pk.get('weights'), 'wave': _pk.get('wave'), 'frag': _pk.get('frag')})
            for _pk in self._random_picks]
        self.sched_by_frame: dict[int, list[dict]] = {}
        for a in self.schedule:
            if a.get('t') is None:
                continue
            self.sched_by_frame.setdefault(int(round(a['t'] * FPS)), []).append(a)

        # 关卡自带 options 为底，调用方 options 覆盖（模拟器开关，如 projectile/auto_skill）
        opts = dict(self.level.get('options') or {})
        opts.update(options or {})
        self.cost_max = opts.get('maxCost', COST_MAX_DEFAULT)
        # ★敌方索敌相位开关（`knowledge/03_外部学习/30`：出生帧+2、每 3 帧一循环）
        #   ⚠️ 1-1 标定 A/B 实测：**加上相位后敌→我伤害更晚**（+2→+4/+6/+9）
        #      ⇒ **默认仍为 `every_frame`**；`'spawn+2'` 保留供别的关卡/单位复验。
        self.enemy_search_phase = str(opts.get('enemy_search_phase', 'every_frame'))
        # ---- 关卡 rune（磨难/环境词条）叠加：费用上限修正 ----
        # h12-4 实测：runes 里 cbuff_max_cost 把 max_cost 压到 20（max_cost_ceil 99），
        # 对应关卡文本「我方费用上限大幅降低」「<街头应急储备>被摧毁后获得一定费用及费用上限」。
        self.cost_max_base = float(self.cost_max)
        self.runes = list(self.level.get('runes') or [])
        self.cost_cap_ceil = None
        for r in self.runes:
            bb = {b.get('key'): (b.get('valueStr') if b.get('valueStr') is not None else b.get('value'))
                  for b in (r.get('blackboard') or [])}
            if 'max_cost' in bb and bb['max_cost'] is not None:
                try:
                    self.cost_max = float(bb['max_cost'])
                except Exception:
                    pass
            if 'max_cost_ceil' in bb and bb['max_cost_ceil'] is not None:
                try:
                    self.cost_cap_ceil = float(bb['max_cost_ceil'])
                except Exception:
                    pass
        self.cost_cap_bonus = 0.0      # 由「储备物被摧毁」等机制抬升（见 add_cost_cap）
        # ---- rune：敌人属性乘区（h12-4: enemy_attribute_mul {atk:1.2, def:1.2, max_hp:1.2}）----
        self.enemy_attr_mul: dict[str, float] = {}
        for r in (self.level.get('runes') or []):
            if r.get('key') != 'enemy_attribute_mul':
                continue
            for b in (r.get('blackboard') or []):
                k = b.get('key')
                v = b.get('valueStr')
                v = v if v is not None else b.get('value')
                if k in ('atk', 'def', 'max_hp') and v is not None:
                    self.enemy_attr_mul[k] = float(self.enemy_attr_mul.get(k, 1.0)) * float(v)
        self.cost_cap_rune = float(self.cost_max)   # rune 施加后的基数（h12-4 = 20）
        self.cost = float(opts.get('initialCost', 10))
        self.move_multiplier = opts.get('moveMultiplier', MOVE_MULTIPLIER_DEFAULT)
        # ★诊断用覆盖：不修改关卡数据，仅覆盖"敌人有效移速倍率"（扫描用）
        if opts.get('move_multiplier_override') is not None:
            self.move_multiplier = float(opts['move_multiplier_override'])
        # 预置装置是否算作阻挡者（⇒ 会被敌人攻击/拆掉）。默认 False：按用户 2026-09-14 更正
        # 「应急储备不被敌人攻击、只影响寻路」。开关保留用于 A/B（§7.53）。
        self.devices_block_enemies = bool(opts.get('devicesBlockEnemies', False))
        self.enemies_attack_devices = bool(opts.get('enemiesAttackDevices', False))
        self.life_max = int(opts.get('maxLifePoint', 3))
        self.life = self.life_max

        self.frame = 0
        # ★弹道（投射物）：远程攻击的"延迟结算队列"
        #   依用户 2026-09-15 补充：远程攻击若带弹道，则"命中时刻"晚于"出手时刻"，
        #   且随距离变化（子弹需飞向目标/追击）。本队列保存"待结算的伤害"。
        #   可用 options={'projectile': False} 关闭以恢复旧行为。
        self.projectile_enabled = bool(opts.get('projectile', True))
        # ★直线寻路（对齐 routes 的 allowDiagonalMove 语义；False 回退逐格 navmap）
        self.straight_path = bool(opts.get('straight_path', True))
        # ★阻挡吸附：被挡后把敌人对齐到阻挡者相邻格中心（依 1-1 标定反推）
        self.block_snap = bool(opts.get('block_snap', False))
        # ★职业特性(trait) atk_scale（如月见夜远程 ×0.8）
        self.trait_scale = bool(opts.get('trait_scale', True))
        # ★AUTO 技能自动发动（`skill_table.skillType == 'AUTO'`；如芬「冲锋号令·α型」）：
        #   SP 满即发动、并按其 `blackboard.cost` 回复费用（视频侧已证实 +6）。
        self.auto_skill = bool(opts.get('auto_skill', True))
        # ★②**受击判定体积**（敌人，索敌用）：由 1-1 标定反推的默认值，可用 options 覆盖/扫描。
        self.hit_volume_enemy = float(opts.get('hit_volume_enemy', HIT_VOLUME_ENEMY_DEFAULT))
        # ★①**碰撞体积**（敌人，阻挡/位移用）：与②**不同源**、也**不同值**。
        self.collider_radius_enemy = float(
            opts.get('collider_radius_enemy', COLLIDER_RADIUS_ENEMY_DEFAULT))
        # ★④阻挡判定用的**捕获距离**（与①碰撞体积无关，见文件头部对照表）
        self.block_capture_distance = float(
            opts.get('block_capture_distance', BLOCK_CAPTURE_DISTANCE))
        # ★④阻挡判据：默认 `cell_3x3_round`（进入阻挡者格的 1 格邻域）——
        #   在"敌人出生速度 0 + 加速"补齐后，它是精度最好且语义最干净的规则（见文件头部注释）。
        self.block_rule = str(opts.get('block_rule', BLOCK_RULE_DEFAULT))
        # ★④阻挡半径（统一值；`block_rule='radius'` 时生效）—— 默认 0.7071（代码常量）
        self.block_radius = float(opts.get('block_radius', BLOCK_RADIUS_DEFAULT))
        # ★阻挡偏移模式：'code' = 文档化 `CalculateBlockOffset`（默认）；'cell_center' = 旧自造吸附
        self.block_offset_mode = str(opts.get('block_offset_mode', BLOCK_OFFSET_MODE_DEFAULT))
        # ★阻挡扫描相位：'per_unit'（默认，每角色独立 ticker，相位随部署帧）/ 'global'（旧全局帧时钟）
        self.block_scan_phase = str(opts.get('block_scan_phase', 'per_unit'))
        # ★阻挡扫描相位（`PeriodicTicker` 初值/自增顺序，**反汇编未见证据 ⇒ 由标定反推**）：
        #   1-1 标定的两次阻挡帧 **236 与 443**，相对芬的部署帧 10 分别是 226、433 ——
        #   **两者都 ≡ 1 (mod 3)** ⇒ **两次事件共同指向相位 1**（若相位取 0 则二者应 ≡ 0）。
        #   ⇒ 默认取 **1**；`block_ticker_phase` 仍可覆盖，用于后续其它关卡的再核验。
        self.block_ticker_phase = int(opts.get('block_ticker_phase', 1))
        # ★索敌有效余量是否加入阻挡半径（候选规则，默认关）—— 见 `is_targetable`
        self.acquire_uses_block_radius = bool(opts.get('acquire_uses_block_radius', False))
        # ★④'cell_3x3_round' 的边界余量（到格方格的距离上限；1.0 = 一格的邻域）
        self.block_cell_margin = float(opts.get('block_cell_margin', BLOCK_CELL_MARGIN_DEFAULT))
        # ★出生点坐标约定：True = 用路线起点的字面坐标 (col,row)（而非格中心）
        self.spawn_at_route_point = bool(opts.get('spawn_at_route_point', False))
        # ★②' 干员**受击判定圆**（0.25）：用于"**远程敌人的圆 vs 干员圆**"的索敌判据
        self.ally_hit_radius = float(opts.get('ally_hit_radius', HIT_VOLUME_ALLY))
        # ★②'按敌人 key 覆盖受击判定体积（客户端 prefab 的逐敌 `CircleCollider2D.m_Radius` 不同：
        #   实测分布 0.1/0.5/1.0/1.5/2.0/2.5/3.0 ⇒ "所有敌人一律 0.1" 只是近似）。
        #   数据来自 `ak/data/derived/enemy_hit_radius.json`（标定反推 + 后续以客户端 prefab 校正），
        #   可被 `options['hit_radius_by_key']` 覆盖。
        self.hit_radius_by_key = dict(_load_enemy_hit_radius())
        # ★优先级：**显式 `hit_radius`（诊断用全局覆盖）> 逐敌表 > 默认**。
        #   否则逐敌表会遮蔽 `sweep_hit_volume.py` / `verify_semantics.py` 的全局扫描（A3 曾因此失败）。
        #   注意：诊断用的全局键有**两个别名** —— `hit_radius` 与 `hit_volume_enemy`（历史命名），
        #   任一显式给出即视为"全局覆盖"。
        _explicit = opts.get('hit_radius', opts.get('hit_volume_enemy'))
        self.hit_radius_override = (None if _explicit is None else float(_explicit))
        self.hit_radius_by_key.update(dict(opts.get('hit_radius_by_key') or {}))
        # ★远程敌人索敌的取交方式：'intersect'（两圆相交即算进入，默认）/ 'contain'（干员圆完全在内）
        self.enemy_range_mode = str(opts.get('enemy_range_mode', 'intersect'))
        # ★★★移动惯性（用户 2026-09-15 指出）：敌人**出生速度 0**、按 `v ← v+(v_desired−v)·8·dt`
        #   加速（等价每帧 ×4/15，与玩家侧模型 `通用__PATH_FIND.m` 一致）。
        #   `move_inertia=False` 回退为"瞬时达到上限速度"（用于 A/B）。
        self.move_inertia = bool(opts.get('move_inertia', True))
        # ★命中范围容差（格）：**旧口径参数，仅在 `targeting_model='legacy_center_distance'`
        #   时生效**。标定反推：实机"帧432 芬命中猎狗"⇒ 起手 = 432 − 前摇18 = **414**，
        #   而帧 414 的欧氏距离恰为 **1.50**（≈1 格 + 半格）。
        #   ★用户 2026-09-15 明确：索敌应按"**方格范围 + 受击判定体积**"，而不是"中心距 ≤ N"。
        self.range_distance_tol = opts.get('range_distance_tol', 1.5)
        # ★②索敌模型（用户 2026-09-15 指定；见 `is_targetable` 文档）
        #   `grid_plus_hit_volume` = 方格范围 ∪ 受击圆∩范围格（★默认，语义正确）
        #   `legacy_center_distance` = 旧口径（中心距 ≤ tol）—— 1-1 标定 16/16 即在该口径下拟合
        self.targeting_model = str(opts.get('targeting_model', 'grid_plus_hit_volume'))
        self.pending_hits = []
        self.max_frames = max_frames
        self.units: dict[int, Unit] = {}
        self._uid = 1
        self.logs: list[OpLog] = []
        self.record = record
        self.record_every = record_every
        self.frames: list[dict] = []          # 逐帧切片
        self.rng_draws: list[dict] = []
        self.finished = False
        self.result: str | None = None
        self.skill_gate = True                # 技能是否要求 SP 充足（两端对轴时可关闭以隔离变量）
        self.sp_assume_attacking = False      # True：攻击回复型技能按「理想攻击速率」充能
        #                                       （打图端无法预知实际攻击次数，两端对轴时用同一假设）
        self._deployed_names: dict[str, int] = {}
        self._deploy_history: list[dict] = []

        # 敌人索引（关卡 enemyDbRefs → 实际数值）
        self.enemy_refs = {r['id']: r for r in (self.level.get('enemyDbRefs') or [])}

        # 召唤物 → 拥有者映射（由 character_table 各干员技能的 overrideTokenKey 反查）
        # 用途：轴表里「部署 弦惊」这类召唤物操作需被识别为 token 并绑定 owner，
        #       否则召唤者技能期间的范围伤害（如令 S3 的 AoE）不会触发（见 §7.42）。
        self.token_owner_map: dict[str, str] = {}
        try:
            from .data import load_table
            ct = load_table('character_table.json')
            for cid, c in ct.items():
                for sk in (c.get('skills') or []):
                    tk = sk.get('overrideTokenKey')
                    if tk:
                        self.token_owner_map.setdefault(tk, cid)
        except Exception:
            pass

        # ---- 预置装置（predefines.tokenInsts）：如 h12-4 的「街头应急储备」 ----
        # 数据：character_table 的 profession=TRAP，天赋黑板给出 on-death 效果
        # （trap_111_wdfarm：被击败后恢复 5 点费用上限及费用，见 knowledge/04/41 §7.26）
        for inst in ((self.level.get('predefines') or {}).get('tokenInsts') or []):
            key = ((inst.get('inst') or {}).get('characterKey') or '')
            pos = inst.get('position') or {}
            if not key or 'row' not in pos or 'col' not in pos:
                continue
            try:
                spec = get_operator(key, elite=0, level=1)
            except Exception:
                continue
            row, col = int(pos['row']), int(pos['col'])
            dev = make_operator(self._uid, spec, self.map.grid_to_world(row, col), 0,
                                get_range(spec.get('rangeId') or '1-1'))
            dev.side = 'DEVICE'
            dev.block_cnt = int(spec['attrs'].get('blockCnt') or 0)
            bb = {}
            for t in (spec.get('talents') or []):
                for cand in (t.get('candidates') or []):
                    for b in (cand.get('blackboard') or []):
                        v = b.get('valueStr')
                        bb[b['key']] = v if v is not None else b.get('value')
            dev.extra['device_key'] = key
            dev.extra['on_death'] = bb
            self.units[self._uid] = dev
            # 装置占据的格子会**影响敌人寻路**（用户更正：储备挡住敌人路线）
            try:
                self.map.device_blocked.add((row, col))
                self.map._nav_cache.clear()
            except Exception:
                pass
            self.logs.append(OpLog(0, 'device_spawn', {'key': key, 'name': dev.name,
                                                       'row': row, 'col': col, 'hp': dev.max_hp}))
            self._uid += 1

        # RNG（复刻 .NET System.Random，knowledge/34）
        # ★注意：RNG 已在 `__init__` 开头建立并**已被 `build_schedule` 的随机出怪组抽签消耗**，
        #   此处**不得**重建（否则抽签结果与后续随机序列会脱节）。
        assert getattr(self, 'rng', None) is not None, 'RNG 应在 build_schedule 之前建立'
        # 随机出怪抽签事件入日志（此时 logs 已建立）
        for _l in getattr(self, '_pending_pick_logs', []):
            self.logs.append(_l)

        # 导航距离场缓存（以路线终点为目标的距离场 → 用于索敌"最靠近终点"与移动）
        self._nav_by_route: dict[int, dict] = {}

    # ---------------- 查询 ----------------
    def route(self, idx: int) -> Route | None:
        for r in self.routes:
            if r.index == idx:
                return r
        return None

    def navmap_for_route(self, idx: int) -> dict | None:
        if idx in self._nav_by_route:
            return self._nav_by_route[idx]
        r = self.route(idx)
        if r is None:
            return None
        nm = self.map.build_navmap(r.end)
        self._nav_by_route[idx] = nm
        return nm

    def remaining_distance(self, u: Unit) -> float:
        """敌人到终点的剩余代价（用于索敌：优先最靠近保护目标者）。"""
        nm = u.navmap or {}
        if not nm:
            return 1e9
        g = u.grid()
        return nm.get(g, 1e9)

    # ---------------- 操作 ----------------
    def deploy(self, char_id: str, row: int, col: int, direction: str = '右',
               elite: int = 2, level: int = 90, potential: int = 6, trust: int = 200,
               module: str | None = None, module_level: int = 3,
               skill_index: int = 0, skill_level: int = 10, is_token: bool = False,
               token_owner: str | None = None, cost: int | None = None) -> Unit | None:
        melee = True
        spec = get_operator(char_id, elite=elite, level=level, potential=potential, trust=trust,
                            module=module, module_level=module_level, skill_index=skill_index,
                            skill_level=skill_level)
        if spec.get('position') == 'RANGED':
            melee = False
        if not self.map.can_deploy(row, col, melee=melee):
            self.logs.append(OpLog(self.frame, 'deploy_failed', {'char': char_id, 'row': row, 'col': col, 'reason': 'tile'}))
            return None
        # 格子已被占用就不能再放（含预置装置）：实机里「街头应急储备」占着的格子放不下任何单位，
        # 所以轴表里「弦惊 F8 = (5,7)」这类操作只有在储备已被摧毁后才可能成立（§7.45）
        for other in self.units.values():
            if other.alive and other.grid() == (row, col):
                self.logs.append(OpLog(self.frame, 'deploy_failed',
                                       {'char': char_id, 'row': row, 'col': col, 'reason': 'occupied',
                                        'by': other.name}))
                return None
        need = cost if cost is not None else int(spec['attrs']['cost'])
        # 召唤物的**模组加值/减免**（battle_equip_table.tokenAttributeBlackboard）：
        # 令的模组 uniequip_002_ling 给 token_10020_ling_soul3（弦惊）**cost −5**（另加 max_hp +250 / atk +60）。
        # 这是 h12-4 前半段的关键：弦惊原价 23 > 关卡上限 20，**戴模组后只要 18** ⇒ 29.0s 就能落地（§7.53）。
        tok_bb = None
        if is_token:
            owner_uid = self._deployed_names.get(token_owner, token_owner) \
                if isinstance(token_owner, str) else token_owner
            ou = self.units.get(owner_uid) if owner_uid is not None else None
            mi = (ou.extra.get('module_info') if ou is not None else None) or {}
            tok_bb = (mi.get('tokenAttributeBlackboard') or {}).get(char_id)
            if tok_bb:
                for bb in tok_bb:
                    if bb.get('key') == 'cost':
                        need += int(bb.get('value') or 0)
        if self.cost + 1e-9 < need:
            self.logs.append(OpLog(self.frame, 'deploy_failed', {'char': char_id, 'reason': 'cost', 'need': need, 'have': self.cost}))
            return None
        self.cost -= need
        rg = get_range(spec.get('rangeId') or '1-1')
        u = make_operator(self._uid, spec, self.map.grid_to_world(row, col), self.frame, rg)
        u.extra['direction'] = direction
        u.extra['skill_ready'] = False
        u.extra['module_info'] = spec.get('moduleInfo') or {}
        if is_token:
            u.is_token = True
            # owner 统一存 **uid**（units 以 uid 为键）；若传入的是 charId 则先反查
            if isinstance(token_owner, str) and token_owner:
                token_owner = self._deployed_names.get(token_owner, token_owner)
            u.extra['owner'] = token_owner
            # 模组对召唤物本体的加值（max_hp / atk / def）
            for bb in (tok_bb or []):
                k = {'max_hp': 'max_hp', 'atk': 'atk', 'def': 'def'}.get(bb.get('key'))
                if k == 'max_hp':
                    u.max_hp += int(bb.get('value') or 0)
                    u.hp = u.max_hp
                elif k == 'atk':
                    u.atk += int(bb.get('value') or 0)
                elif k == 'def':
                    u.df += int(bb.get('value') or 0)
        self.units[self._uid] = u
        self._deployed_names[spec['name']] = self._uid
        self._deployed_names[char_id] = self._uid
        self._uid += 1
        self.logs.append(OpLog(self.frame, 'deploy', {'char': char_id, 'name': spec['name'],
                                                      'row': row, 'col': col, 'dir': direction,
                                                      'cost': need, 'cost_after': round(self.cost, 3)}))
        self._deploy_history.append({'char': char_id, 'frame': self.frame, 'row': row, 'col': col})
        return u

    def find_unit(self, ident: str) -> Unit | None:
        if ident in self._deployed_names:
            uid = self._deployed_names[ident]
            u = self.units.get(uid)
            if u and u.alive:
                return u
        for u in self.units.values():
            if u.alive and (u.name == ident or u.key == ident):
                return u
        return None

    def add_cost_cap(self, delta: float) -> float:
        """抬升费用上限（对应「<街头应急储备>被摧毁后获得…费用上限」），不超过 max_cost_ceil。

        语义：rune 把上限压到 `max_cost`（h12-4 = 20），此后每次抬升在此基数上累加，
        最终不超过 `max_cost_ceil`（= 99）。
        """
        self.cost_cap_bonus += float(delta)
        cap = self.cost_cap_rune + self.cost_cap_bonus
        self.cost_max = min(self.cost_cap_ceil, cap) if self.cost_cap_ceil is not None else cap
        self.logs.append(OpLog(self.frame, 'cost_cap_up', {'cost_max': self.cost_max,
                                                           'bonus': self.cost_cap_bonus}))
        return self.cost_max

    def retreat(self, ident: str) -> bool:
        u = self.find_unit(ident)
        if not u:
            return False
        u.dead = True
        u.state = 'RETREAT'
        if u.is_token:
            self._on_token_lost(u)
        # 返还 50% 费用（简化）
        self.cost = min(self.cost_max, self.cost + u.cost * 0.5)
        self.logs.append(OpLog(self.frame, 'retreat', {'unit': u.name, 'cost_after': round(self.cost, 3)}))
        return True

    def use_skill(self, ident: str) -> bool:
        """释放技能（表驱动）：SP 满才可释放。`ident` = 干员名/单位 key（见 `find_unit`）。

        ★注意：`find_unit` **不接受 uid**（它按名字/key 查）；需要按单位对象直接发动时
        请调用 `_activate_skill(u)`（AUTO 技能自动发动走这条路）。
        """
        u = self.find_unit(ident)
        if not u:
            return False
        return self._activate_skill(u)

    def _activate_skill(self, u: Unit) -> bool:
        """实际发动技能：应用 blackboard 加成；处理时长/弹药、召唤物发放、**费用回复**。"""
        if not u or not u.skill:
            return False
        if u.skill_active:
            self.logs.append(OpLog(self.frame, 'skill_reject', {'unit': u.name, 'reason': 'active'}))
            return False
        if self.skill_gate and u.sp + 1e-9 < u.sp_cost:
            self.logs.append(OpLog(self.frame, 'skill_reject',
                                   {'unit': u.name, 'reason': 'sp', 'have': round(u.sp, 2),
                                    'need': u.sp_cost}))
            return False
        bb = u.skill.get('blackboard') or {}
        u.sp = 0.0
        u.skill_charge = 0
        u.skill_active = True
        u.skill_active_until = None
        dur = u.skill.get('duration')
        u.skill_until = (self.frame + int(round(float(dur) * FPS))) if (dur is not None and float(dur) > 0) else None
        # 弹药型（duration = -1 且描述含"弹药"）：用触发次数作为弹药数
        ammo = bb.get('attack@trigger_time')
        u.skill_ammo = int(float(ammo)) if (u.skill_until is None and ammo is not None) else None
        # 增益（blackboard：atk/def/attack_speed 为百分比或加值）
        u.buffs.append({'src': u.skill.get('name'), 'atk': float(bb.get('atk') or 0.0),
                        'def': float(bb.get('def') or 0.0),
                        'attack_speed': float(bb.get('attack_speed') or 0.0),
                        'until': u.skill_until})
        u.recompute_attack_interval()
        # ★技能发动时**回复费用**（先锋技能，如芬「冲锋号令·α型」`blackboard.cost = 6`）
        #   来源：`skill_table.json` 的 `blackboard[{key:'cost'}]`；描述为"立即获得 N 点部署费用"。
        #   1-1 视频侧图像识别独立验证：费用在游戏帧 581 / 1333 出现 **+6** 跳变，
        #   与 `spCost=25 / initSp=6 / inc=1.0/s`（技能等级 7）预测的 580 / 1330 相差 1~3 帧。
        gain = float(getattr(u, 'skill_cost_gain', 0.0) or 0.0)
        if gain:
            before = self.cost
            self.cost = min(self.cost_max, self.cost + gain)
            self.logs.append(OpLog(self.frame, 'cost_recover',
                                   {'unit': u.name, 'skill': u.skill.get('name'),
                                    'gain': gain, 'from': round(before, 3),
                                    'to': round(self.cost, 3)}))
        # 召唤物发放：S1 类「技能开启时获得1个召唤物」
        if u.skill.get('overrideTokenKey') and self._grants_summon_on_activation(u):
            u.summon_charges += 1
            self.logs.append(OpLog(self.frame, 'summon_charge',
                                   {'unit': u.name, 'charges': u.summon_charges, 'when': 'activation'}))
        self.logs.append(OpLog(self.frame, 'skill', {'unit': u.name, 'skill': u.skill.get('name'),
                                                     'until': u.skill_until, 'ammo': u.skill_ammo}))
        # ★瞬发技能（`durationType == 'NONE'` / `duration == 0`）：立即结束，以便重新充能。
        #   典型：先锋的「冲锋号令·α型」（只回费，无持续时间）。
        #   若不立即结束，`skill_active` 会永久为真 ⇒ SP 不再充能、技能只发动一次。
        _dt = str((u.skill or {}).get('durationType') or '').upper()
        _dur = u.skill.get('duration')
        if u.skill_active and (_dt == 'NONE'
                               or (_dur is not None and float(_dur) == 0.0)):
            self._end_skill(u)
        return True

    def _grants_summon_on_activation(self, u: Unit) -> bool:
        """召唤物是在「技能开启时」还是「技能结束时」获得：按技能描述判定（表里有原文）。"""
        desc = u.skill.get('description') or ''
        if '技能开启时获得1个召唤物' in desc:
            return True
        return False

    def _end_skill(self, u: Unit) -> None:
        desc = u.skill.get('description') or ''
        u.skill_active = False
        u.skill_active_until = self.frame
        u.skill_until = None
        u.skill_ammo = None
        u.buffs = [b for b in u.buffs if b.get('src') != u.skill.get('name')]
        u.recompute_attack_interval()
        if u.skill.get('overrideTokenKey') and '技能结束时获得1个召唤物' in desc:
            u.summon_charges += 1
            self.logs.append(OpLog(self.frame, 'summon_charge',
                                   {'unit': u.name, 'charges': u.summon_charges, 'when': 'end'}))
        self.logs.append(OpLog(self.frame, 'skill_end', {'unit': u.name, 'skill': u.skill.get('name')}))

    # ---------------- 范围与索敌（★五个语义分列，见文件头部对照表） ----------------
    @staticmethod
    def cell_square(cell: tuple[int, int]) -> tuple[float, float, float, float]:
        """格 → 世界坐标下的**方格区域** `(x0, y0, x1, y1)`（`x = col`、`y = row`，格边长 1）。"""
        r, c = cell
        return float(c), float(r), float(c) + 1.0, float(r) + 1.0

    @classmethod
    def point_to_cell_distance(cls, x: float, y: float,
                               cell: tuple[int, int]) -> float:
        """点 → 方格区域的**最短距离**（点在格内 = 0）。

        这是"受击判定体积"与"方格范围"求交的几何基础：
        受击圆与格相交 ⇔ `point_to_cell_distance(中心, 格) ≤ 受击半径`。
        """
        x0, y0, x1, y1 = cls.cell_square(cell)
        dx = 0.0 if x0 <= x <= x1 else (x0 - x if x < x0 else x - x1)
        dy = 0.0 if y0 <= y <= y1 else (y0 - y if y < y0 else y - y1)
        return (dx * dx + dy * dy) ** 0.5

    def range_circumradius(self, u: Unit) -> float | None:
        """★**攻击范围区域的外接圆半径**（由范围表导出，无拟合参数）。

        = `max over 范围格 of (该格最远角 到 干员中心 的距离)`，格边长 1。
        例：2 格范围（自身格 + 前 1 格）⇒ 相对中心 x∈[−0.5, 1.5], y∈[−0.5, 0.5]
        ⇒ 最远角 (1.5, 0.5) ⇒ **R = √(1.5² + 0.5²) = 1.5811**（1-1 的芬即此值）。
        用于 `targeting_model='range_circumradius'`（第115轮由 1-1 数据判定的口径）。
        """
        try:
            cells = self.cells_in_range(u)
        except Exception:                                        # noqa: BLE001
            return None
        if not cells:
            return None
        ox, oy = fp.to_float(u.pos[0]), fp.to_float(u.pos[1])
        best = 0.0
        for (r, c) in cells:
            for ccx in (c, c + 1.0):
                for ccy in (r, r + 1.0):
                    d = ((ccx - ox) ** 2 + (ccy - oy) ** 2) ** 0.5
                    if d > best:
                        best = d
        return best

    def is_targetable(self, u: Unit, e: Unit) -> tuple[bool, str]:
        """★**索敌判定**（对应事件 `target_select`）—— 用户三点约束的直接实现。

        判据（**只用方格范围 + 受击判定体积**）：
          ① `cell(目标中心) ∈ 攻击范围格集合`                ⇒ `'grid'`
          ② `受击圆(目标中心, hit_radius) ∩ 任一范围格 ≠ ∅`   ⇒ `'hit_volume'`
             即 `point_to_cell_distance(目标中心, 格) ≤ hit_radius(目标)`

        ★**不使用碰撞体积**（碰撞体积只用于阻挡/位移，见 `_block_scan`）。

        **模式开关** `self.targeting_model`（`options={'targeting_model': …}`）：
          - `'grid_plus_hit_volume'`（★默认，用户 2026-09-15 指定的语义）
          - `'grid_only'`            纯方格范围（把受击体积置 0 即可等价）
          - `'legacy_center_distance'` 旧口径：`dist(目标中心, 自身中心) ≤ tol`
             ★这是**两种语义混用**的近似（把"范围"当成了以自身为心的圆），
               1-1 标定的 16/16（平均 1.81 帧）是在该口径下拟合出来的；
               保留它只为**复现历史结果**，新代码不应默认使用。
        """
        model = getattr(self, 'targeting_model', 'grid_plus_hit_volume')
        if model == 'range_circumradius':
            # ★**索敌 = 中心距 ≤ 攻击范围区域的外接圆半径**（第115轮由 1-1 数据判定）。
            #   半径**由范围表导出、无拟合参数**：对每个范围格取"由干员中心到该格最远角"的距离，取最大值。
            #   例：2 格范围（自身格 + 前 1 格）⇒ 最远角 (1.5, 0.5) ⇒ R = √(1.5²+0.5²) = **1.5811**。
            #   ★动机：用户指定语义（方格范围 ∪ 受击圆∩范围格）**无法同时满足两条链** ——
            #     `猎狗pro` 要求"中心进范围格"（正面进入），`猎狗` 要求"中心距 ≤ 1.58"（斜向逼近），
            #     二者对同一余量参数要求**相反**；而外接圆口径对两者的还原为 **−3~0 帧与 −1 帧**，
            #     整体伤害平均 **4.50→2.06**、最大 **25→7**。
            R = self.range_circumradius(u)
            if R is not None and e.dist_to(u) <= float(R):
                return True, 'range_circle'
            return False, 'out'
        if model == 'legacy_center_distance':
            tol = getattr(self, 'range_distance_tol', 1.5)
            if tol is not None and e.dist_to(u) <= float(tol):
                return True, 'distance_legacy'
            # 旧口径下若同时给定了语义判据，也允许命中（便于对照）
            if self.cells_in_range(u) and e.grid() in self.cells_in_range(u):
                return True, 'grid'
            return False, 'out'
        cells = self.cells_in_range(u)
        if e.grid() in cells:
            return True, 'grid'
        if model == 'grid_only':
            return False, 'out'
        hr = float(getattr(e, 'hit_radius', HIT_VOLUME_ENEMY_DEFAULT) or 0.0)
        # ★**候选规则（选项开关，默认关）**：索敌的有效余量 = **敌人受击半径 + 阻挡者(干员)阻挡半径 0.7071**
        #   ⇒ `0.7071 + 0.1 = 0.8071`。动机（第114轮）：1-1 的 `芬→猎狗` 索敌需比现值**多约 0.81 格**，
        #   而 0.8071 由**两个既有代码常量**（`Consts.BLOCK_RADIUS=0.7071` 与客户端 prefab 的敌人半径 0.1）
        #   组合而成，**不含任何拟合参数**。用于检验"范围区域是否按干员半径外扩"。
        if getattr(self, 'acquire_uses_block_radius', False):
            hr = hr + float(getattr(self, 'block_radius', BLOCK_RADIUS_DEFAULT))
        if hr <= 0:
            return False, 'out'
        ox, oy = getattr(e, 'hit_offset', (0.0, 0.0)) or (0.0, 0.0)
        ex = fp.to_float(e.pos[0]) + float(ox)
        ey = fp.to_float(e.pos[1]) + float(oy)
        for c in cells:
            if self.point_to_cell_distance(ex, ey, c) <= hr:
                return True, 'hit_volume'
        return False, 'out'

    def cells_in_range(self, u: Unit, range_grids: list[list[int]] | None = None) -> set[tuple[int, int]]:
        """③ **攻击范围（方格集合，表驱动）** —— 索敌的**主判据**。

        语义：`attack_range` 表给出"以自身格为原点、按朝向旋转后的格偏移"，
        返回世界格坐标集合。**与体积无关**（体积只在 `is_targetable` 里作为补充判据）。
        """
        rg = range_grids if range_grids is not None else u.range_grids
        row, col = u.grid()
        dx, dy = DIRECTIONS.get(u.extra.get('direction', '右'), (1, 0))
        cells = set()
        for g in rg or [[0, 0]]:
            c, r = (g[0], g[1]) if len(g) >= 2 else (0, 0)
            # 朝向变换：右=+x, 上=+y, 左=-x, 下=-y
            fwd = c
            lat = r * RANGE_ROW_SIGN
            if dx == 1:
                wr, wc = row + lat, col + fwd
            elif dx == -1:
                wr, wc = row - lat, col - fwd
            elif dy == 1:
                wr, wc = row + fwd, col - lat
            else:
                wr, wc = row - fwd, col + lat
            cells.add((wr, wc))
        return cells

    def aoe_targets(self, cells: set[tuple[int, int]]) -> list[Unit]:
        """⑤ **范围攻击命中判定**（对应事件 `hit` 的 AoE 分支）。

        ★依用户第 4 点：**只看"目标中心是否位于选定格内"**，与**受击判定体积无关**。
        （反例：不要写成"目标受击圆与格相交"——那是索敌的判据，不是 AoE 的判据。）
        """
        out = []
        for e in self.units.values():
            if e.side != 'ENEMY' or not e.alive:
                continue
            if e.grid() in cells:
                out.append(e)
        return out

    def aoe_cells_around(self, cell: tuple[int, int],
                         cross_only: bool = True) -> set[tuple[int, int]]:
        """以某格为中心的四邻（或九宫）格集合 —— 供 `aoe_targets` 使用。"""
        r, c = cell
        offs = ((-1, 0), (1, 0), (0, -1), (0, 1)) if cross_only else \
               tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1))
        return {(r + dr, c + dc) for dr, dc in offs}

    def enemies_in_range(self, u: Unit) -> list[Unit]:
        """**索敌候选**：走 `is_targetable`（方格范围 ∪ 受击判定体积）。

        历史说明（保留可追溯）：1-1 标定显示"芬（近战 1 格、朝左）"
        在敌人"格坐标不在范围内、但身体已探进范围格"时就能命中
        ⇒ 这正是"**索敌要考虑受击判定体积**"的表现。早期用
        `距离 ≤ 1.5` 近似 ⇒ 现改为语义正确的"受击圆 ∩ 范围格"。
        """
        out = []
        for e in self.units.values():
            if e.side != 'ENEMY' or not e.alive:
                continue
            ok, _why = self.is_targetable(u, e)
            if ok:
                out.append(e)
        return out

    def pick_operator_target(self, u: Unit) -> Unit | None:
        cands = self.enemies_in_range(u)
        if not cands:
            # 无敌人时打**预置装置**（如「街头应急储备」——玩家的输出可将其摧毁以换取费用上限）
            cells = self.cells_in_range(u)
            devs = [d for d in self.units.values()
                    if d.side == 'DEVICE' and d.alive and d.grid() in cells]
            if devs:
                return min(devs, key=lambda d: (d.created_frame, d.uid))
            return None
        # 优先级：被自己阻挡 > 最靠近终点（剩余距离小）> 创建更早
        def keyf(e: Unit):
            blocked_by_self = 0 if u.uid in e.blocked_by else 1
            return (blocked_by_self, self.remaining_distance(e), e.created_frame, e.uid)
        return min(cands, key=keyf)

    def _enemy_can_reach(self, e: Unit, o: Unit) -> bool:
        """**地面敌人无法触及高台单位**（飞行敌人不受限）。

        这是"令/蕾缪安站在高台却被近战敌人打死"的根因：实机里高台单位对地面敌人是安全位
        （只能被远程/飞行敌人攻击），我们的模拟此前只按格距判定。
        """
        if e.flying or str(e.extra.get('motion') or '').upper().startswith('FLY'):
            return True
        t = self.map.tile(*o.grid())
        if t is None:
            return False
        return str(getattr(t, 'height_type', 'LOWLAND')).upper() != 'HIGHLAND'

    def enemy_reach(self, e: Unit) -> tuple[float, str]:
        """★**远程敌人的攻击范围是"确定半径的圆"**（用户 2026-09-15 明确）。

        数据来源：`enemy_database` 的 `rangeRadius`（近战为 0）+ `applyWay`（MELEE/RANGED）。
        判据：**干员的 0.25 圆**处于该圆内 ⇒ 敌人开始攻击。
          - `mode='intersect'`（默认）：两圆**相交**即算"处于范围内"
            ⇒ 有效触及 = `rangeRadius + ally_hit_radius(0.25)`
          - `mode='contain'`：干员圆需**完全落在这个圆内**
            ⇒ 有效触及 = `rangeRadius − ally_hit_radius(0.25)`

        返回 `(有效触及半径, 判据名)`；判据名会写进 `target_select` 事件。
        """
        r = float(e.extra.get('rangeRadius') or 0.0)
        mode = str(getattr(self, 'enemy_range_mode', 'intersect'))
        orad = float(getattr(self, 'ally_hit_radius', HIT_VOLUME_ALLY) or 0.0)
        if r <= 0:
            return 0.0, 'melee'
        reach = r + orad if mode == 'intersect' else max(0.0, r - orad)
        return reach, f'circle_{mode}'

    def operators_attackable_by(self, e: Unit) -> list[Unit]:
        """★**敌方索敌**（事件 `target_select`，`side='ENEMY'`）。

        判据（两类，**语义不同**）：
          - **被阻挡** ⇒ 只能打当前阻挡者（`judge='blocked'`）；
          - **近战敌人**（`rangeRadius=0`）⇒ 相邻格（切比雪夫 ≤1，`judge='melee_adjacent'`）；
          - **远程敌人** ⇒ **圆 vs 干员圆**（`judge='circle_intersect'/'circle_contain'`）：
            `dist(敌人, 干员) ≤ rangeRadius ± 干员受击半径(0.25)`。
        ⚠️与干员侧**不同**：干员侧是"**方格范围** + 敌人 0.1 圆"；敌方远程是"**半径圆** + 干员 0.25 圆"。
        """
        if e.blocked_by:
            # 预置装置（应急储备）默认**不阻挡、不被攻击**（用户 2026-09-14 更正）；
            # enemies_attack_devices=True 时恢复「装置阻挡并被反击拆掉」的旧语义，用于 A/B（§7.53）
            return [self.units[uid] for uid in e.blocked_by
                    if uid in self.units and self.units[uid].alive
                    and (self.units[uid].side == 'ALLY' or self.enemies_attack_devices)]
        reach, judge = self.enemy_reach(e)
        out = []
        for o in list(self.units.values()):
            # 注意（用户 2026-09-14 更正）：**敌人不会攻击应急储备**，因此这里**不**把 DEVICE 纳入敌方目标；
            # 储备的作用是「挡住敌人寻路」，而我方单位可以主动打它以换取费用/上限（见 §7.38）
            if (o.side != 'ALLY' and not self.enemies_attack_devices) or not o.alive:
                continue
            if not self._enemy_can_reach(e, o):
                continue          # 地面敌人打不到高台单位（§7.36 的关键规则，勿删）
            if judge == 'melee':
                # ★2026-09-29（T-200c）：**近战敌人的索敌必须用"物理接触"，不能只用"格相邻"**。
                #   旧写法 `max(|Δrow|,|Δcol|) <= 1` 会让敌人在**还差 1.4 格**时就起手
                #   （实测：猎狗pro 在 x=4.02、芬在 x=5.5 时就被判可攻击 ⇒ 提前 ~37 帧打出第一下 218，
                #    而标定表里它必须先被阻挡、到 255 才命中）。
                #   本体口径：**接触半径**（`04/37` 的阻挡判定圆盘 0.7071）+ 干员受击半径(0.25)。
                #   `options['enemy_melee_contact']=False` 可回退旧行为做 A/B。
                if bool(getattr(self, 'enemy_melee_contact', True)):
                    # ★近战敌人**只打"当前阻挡者"**（本体语义：`judge='blocked'` 优先，
                    #   没被阻挡就不起手——标定表里猎狗pro 必须先"芬 阻挡"再"命中"，间隔 19 帧）。
                    #   旧写法允许"格相邻即打" ⇒ 敌人在 1.4 格外就起手，提前 ~37 帧。
                    if getattr(e, 'blocked_by', None):
                        rad = float(getattr(self, 'block_radius', 0.7071))
                        orad0 = float(getattr(self, 'ally_hit_radius', HIT_VOLUME_ALLY) or 0.0)
                        if e.dist_to(o) <= rad + orad0:
                            out.append(o)
                else:
                    gr, gc = e.grid()
                    orr, occ = o.grid()
                    if max(abs(gr - orr), abs(gc - occ)) <= 1:
                        out.append(o)
            elif e.dist_to(o) <= reach:
                out.append(o)
        # 仇恨：嘲讽等级 → 部署时间早者（3 帧一组）
        out.sort(key=lambda o: (-(o.extra.get('taunt', 0) or 0),
                                (o.deploy_time_frame // AGGRO_PRECISION_FRAMES) * AGGRO_PRECISION_FRAMES,
                                o.uid))
        if out:
            e.extra['_last_target_judge'] = judge
        return out

    # ---------------- 帧推进 ----------------
    def tick(self) -> None:
        f = self.frame
        # ① 费用回复（每秒 +1）
        #   ★相位修正（依 1-1 实机标定）：`f` 是"进入本 tick 时的帧号"，而 `self.frame`
        #   在本 tick **末尾**才 +1 ⇒ 若在 `f % 30 == 0` 时增长，则"帧 30n"的切片仍是旧值，
        #   要到"帧 30n+1"才看到增长（实测即 31/61/91）。
        #   标定表要求"**该秒的第 0 帧**"就已增长（帧 0/30/60…）⇒ 应在 `f % 30 == 29` 时增长，
        #   这样"帧 30n"的切片恰好包含这次 +1。
        if f % FPS == FPS - 1:
            self.cost = min(self.cost_max, self.cost + COST_REGEN_PER_SEC)

        # ② 波次出生
        for a in self.sched_by_frame.get(f, []):
            if a['type'] == 'SPAWN':
                self._spawn_enemy(a)

        # ★②'为**新出现的单位**打上"创建帧"戳（出生/部署当帧）。
        #   用途：`Character.m_findBlockeeTicker` 是**每角色**的 `PeriodicTicker`（偏移 0x380），
        #   其相位由**该角色被创建的时刻**决定 ⇒ 阻挡扫描相位须以此为准（见 `_block_ticker_fires`）。
        #   放在这里可覆盖"敌人出生""干员部署""装置落地"三条路径，无需各处分别埋点。
        for _u in self.units.values():
            if getattr(_u, 'spawn_frame', None) is None:
                _u.spawn_frame = f

        # ③ 单位 tick（敌人先于干员，knowledge/24 §2）
        for u in list(self.units.values()):
            if u.side == 'ENEMY':
                self._enemy_tick(u)
        for u in list(self.units.values()):
            if u.side == 'ALLY':
                self._operator_tick(u)

        # 清理死亡/离场
        for uid in [uid for uid, u in self.units.items() if not u.alive]:
            gone = self.units[uid]
            if gone.side == 'DEVICE':
                # 装置被摧毁 → 触发其 on-death 效果（h12-4：+5 费用上限与 +5 费用）
                bb = gone.extra.get('on_death') or {}
                if bb.get('max_cost'):
                    self.add_cost_cap(float(bb['max_cost']))
                if bb.get('cost'):
                    self.cost = min(self.cost_max, self.cost + float(bb['cost']))
                # 装置消失后不再占格：必须从寻路障碍里移除，否则敌人会永远绕着一个空位走
                try:
                    self.map.device_blocked.discard(gone.grid())
                    self.map._nav_cache.clear()
                except Exception:
                    pass
                self.logs.append(OpLog(self.frame, 'device_destroyed',
                                       {'key': gone.extra.get('device_key'), 'name': gone.name,
                                        'cost_max': self.cost_max, 'cost': round(self.cost, 2),
                                        'by': gone.extra.get('killed_by')}))
            if gone.is_token and gone.state != 'RETREAT':
                self._on_token_lost(gone)          # 召唤物被击倒/吸收 → 触发召唤者天赋
            for other in self.units.values():
                if uid in other.blocked_by:
                    other.blocked_by.remove(uid)
                if uid in other.blocking:
                    other.blocking.remove(uid)
            del self.units[uid]

        # ⑤ 结算
        if self.life <= 0:
            self.finished = True
            self.result = 'FAIL'
        elif self._all_cleared():
            self.finished = True
            self.result = 'WIN'

        # ★弹道结算：到期（子弹到达）的伤害在此落地
        self._tick_pending_hits()
        if self.record and f % self.record_every == 0:
            self._record_frame()
        self.frame += 1
        if self.frame >= self.max_frames:
            self.finished = True
            self.result = self.result or 'TIMEOUT'

    def _all_cleared(self) -> bool:
        if self.frame < 1:
            return False
        last = max((int(round(a['t'] * FPS)) for a in self.schedule), default=0)
        if self.frame <= last:
            return False
        return not any(u.side == 'ENEMY' and u.alive for u in self.units.values())

    def _spawn_enemy(self, a: dict) -> None:
        route = self.route(a['route'])
        if route is None:
            return
        ref = self.enemy_refs.get(a['key']) or {}
        try:
            edata = get_enemy(a['key'], level=int(ref.get('level', 0) or 0),
                              overwrite=ref.get('overwrittenData'))
            # 平民类单位标记：其技能 key 形如 wdfmr_cost（到达终点 → 我方费用上限 +2，不扣生命）
            sk = edata.get('skills') or {}
            if isinstance(sk, dict):
                sk_keys = list(sk.keys())
            else:
                sk_keys = [s.get('skillId') for s in (sk or []) if isinstance(s, dict)]
            if any('wdfmr_cost' in str(k) for k in sk_keys) or 'wdfmr' in str(a['key']):
                edata = dict(edata)
                edata['_is_civilian'] = True
        except KeyError:
            return
        pos = self.map.grid_to_world(route.start[0], route.start[1])
        # ★出生点约定（可切换）：`spawn_at_route_point=True` ⇒ 用路线起点的**字面坐标** (col, row)
        #   而不是"格中心 (col+0.5,row+0.5)"。
        #   动机（D14 诊断）：1-1 第 2 只（route4 起点 row6/col4）在两种约定下相差 0.5 格，
        #   手算显示"字面坐标"能把「芬 阻挡 猎狗（标定 443）」对上，而"格中心"给出 459。
        if getattr(self, 'spawn_at_route_point', False):
            pos = (fp.from_float(float(route.start[1])), fp.from_float(float(route.start[0])))
        u = make_enemy(self._uid, edata, pos, route, self.frame)
        # ★②受击判定体积（索敌用）：显式全局 `hit_radius` > 逐敌表 > 默认
        _ovr = getattr(self, 'hit_radius_override', None)
        u.hit_radius = float(_ovr if _ovr is not None else
                             self.hit_radius_by_key.get(getattr(u, 'key', ''),
                                                        self.hit_volume_enemy))
        u.collider_radius = float(getattr(self, 'collider_radius_enemy', 0.1))
        # ★「无害且恒计为击杀」（出怪动作的 `isUnharmfulAndAlwaysCountAsKilled`）：
        #   到终点**不扣生命、不触发警报**，只计"已处理"（见 `_check_escape`）
        u.extra['harmless_and_counted'] = bool(a.get('harmless_counted'))
        # 关卡 rune 的敌人属性乘区（h12-4: atk/def/max_hp ×1.2）
        if self.enemy_attr_mul and not u.extra.get('is_civilian'):
            m = self.enemy_attr_mul
            if m.get('max_hp'):
                u.max_hp = int(round(u.max_hp * m['max_hp']))
                u.hp = u.max_hp
            if m.get('atk'):
                u.atk = int(round(u.atk * m['atk']))
            if m.get('def'):
                u.df = int(round(u.df * m['def']))
        u.navmap = self.navmap_for_route(route.index)
        self.units[self._uid] = u
        self._uid += 1
        self.logs.append(OpLog(self.frame, 'spawn', {'enemy': u.name, 'key': u.key,
                                                     'route': route.index, 'hp': u.max_hp}))

    def _enemy_search_fires(self, e) -> bool:
        """★**敌方索敌相位**：`出生帧 + 2`，之后 **每 3 帧一循环**。

        依据（T2，社区口径，`knowledge/03_外部学习/30_神奇答疑课1…` §花的索敌帧）：
        > 「花的索敌帧，是从**出生开始后 2 帧**开始，**三帧一循环**的」
        例：7 帧出生 ⇒ 索敌帧 9/12/15…

        开关：`options['enemy_search_phase']`
          · `'every_frame'`（**默认**：1-1 标定 A/B 实测相位会**变差**，见 04/73 §6）
          · `'spawn+2'`（社区口径，保留供别的关卡/单位复验）
        """
        if str(getattr(self, 'enemy_search_phase', 'every_frame')) == 'every_frame':
            return True
        base = int(getattr(e, 'created_frame', 0) or 0) + 2
        return (self.frame - base) % 3 == 0

    def _enemy_tick(self, e: Unit) -> None:
        if not e.alive:
            return
        # 检查点状态机（WAIT_FOR_SECONDS / DISAPPEAR / APPEAR_AT_POS / MOVE …）
        self._process_checkpoints(e)
        if e.hidden:
            return                      # 已离场（等 APPEAR_AT_POS），不移动、不被索敌
        # 攻击冷却
        # ★阻挡偏移 tween（0.2s = 6 帧内强制移动到稳定阻挡位置）：**接管位置**但**不跳过**本帧其余结算
        #   （早期版本在此 `return` 会连带跳过攻击冷却递减，实测使伤害偏差由 4.50 漂到 4.62）。
        if self._step_block_tween(e):
            e.state = 'BLOCKED'
        if e.attack_cd_frames > 0:
            e.attack_cd_frames -= 1
        # 阻挡扫描：★恢复**每 3 帧**（权威节奏 `Character.FIND_BLOCKEE_TICK = 3`，见 `knowledge/04/37` §二）。
        #   历史：曾因"按格判定"的判窗极窄（敌人一帧推进 1/30 格，正交相邻的判窗只有很短一段）
        #   而改成**每帧扫描**以免漏怪；**改用权威规则（半径 0.7071 的圆盘）后**，
        #   敌人以 0.95 格/秒穿过该圆盘需约 44 帧 ⇒ **3 帧扫描不会再漏**。
        #   `options={'block_scan_every_frame': True}` 可回退为每帧（对照用）。
        #   ★注意：**只有 `block_scan_phase='global'` 才用这道外层门**。
        #   相位改为"每角色 ticker"后，外层若仍按全局帧门控，会与内层形成**双重门控**
        #   （实测相位 1/2 因此永不成立 ⇒ 完全无阻挡）⇒ 此时外层必须**每帧**调用，
        #   由各阻挡者自己的相位在 `_block_ticker_fires` 内决定。
        if str(getattr(self, 'block_scan_phase', 'per_unit')) == 'global':
            if getattr(self, 'block_scan_every_frame', False) or \
                    (self.frame % max(1, int(BLOCK_SCAN_INTERVAL)) == 0):
                self._block_scan(e)
        else:
            self._block_scan(e)
        if e.blocked_by:
            e.state = 'BLOCKED'
            # ★被阻挡时速度清零（实机"被挡下即停"）：解除阻挡后需**重新加速**
            e.inertia = (0, 0)
        elif e.wait_until is not None:
            e.state = 'WAIT'
            e.inertia = (0, 0)
        else:
            e.state = 'MOVE'
            self._enemy_move(e)
        # 攻击（★与干员侧一致：加入普攻前摇）
        #   1-1 标定显示"猎狗命中芬"晚于"芬命中猎狗"，说明敌人同样有前摇；
        #   此前敌人侧是"冷却归零即结算"（前摇 0），会导致敌→我伤害整体提前。
        # ★普攻时序：与干员侧相同的"统一时间基准"（见 _operator_tick 注释）
        st = getattr(e, 'atk_start_frame', None)
        if st is None:
            # ★★索敌闸门（2026-09-29，依 T-200e 的 `04/74` 指令级结论修正）★
            #   `SelectorTrigger.Search 0x714210` 的闸门在 `0x7142E7`：`!ticker.isReady && !force ⇒ return`
            #   ⇒ **首次取目标走 `force=true`（不受 3 帧节拍限制）**；
            #   **丢了目标之后的重新索敌**才回到 3 帧节拍。
            #   而"已有目标时的攻击推进"**根本不经过索敌**：
            #   `AttackState.OnTick 0x71AAD0 → _NextAttackOrExit 0x71B210 → _GetTarget 0x71B0C0`
            #   的 `0x71B17E [rdx+0x1b8]`(Slot 8 = TargetTrigger.get_target) **纯读缓存**。
            #   ⇒ 所以"给攻击推进加相位"必然把时序整体推后（本轮 A/B 的教训）。
            if getattr(e, 'had_target', False) and not self._enemy_search_fires(e):
                return
            targets = self.operators_attackable_by(e)
            if targets:
                e.had_target = True
            if targets:
                e.atk_start_frame = self.frame
                e.atk_hit_done = False
                e.atk_target = targets[0]
                e.attack_windup_left = self._windup_frames(e)
                e.attack_cd_frames = e.attack_interval_frames
                # ★事件与语义显式关联（敌方侧）：`blocked` / `melee_adjacent` / `circle_*`
                _reach, _judge = self.enemy_reach(e)
                if e.blocked_by:
                    _judge = 'blocked'
                self.logs.append(OpLog(self.frame, 'target_select', {
                    'side': 'ENEMY', 'unit': e.name, 'target': targets[0].name,
                    'judge': _judge, 'range_radius': float(e.extra.get('rangeRadius') or 0.0),
                    'reach': round(_reach, 3),
                    'ally_hit_radius': round(float(getattr(self, 'ally_hit_radius', 0.0)), 3)}))
        else:
            el = self.frame - st
            if el >= e.attack_interval_frames:
                # ★★同帧重启（T-200h `04/78` 的 off-by-one 修复）★
                #   旧写法 `atk_start_frame = None` 会让"周期结束帧"变成**空转帧**，
                #   下一次起手被推到 next frame ⇒ 实际周期 = interval+1
                #   （实测：芬 [33,33,33,…] 而 interval=32；猎狗pro [43,43,…] 而 interval=42）。
                #   本体是 `PeriodicTimer` 连续推进，**没有空转帧**。
                tgt = getattr(e, 'atk_target', None)
                if tgt is not None and getattr(tgt, 'alive', False):
                    e.atk_start_frame = self.frame
                    e.atk_hit_done = False
                    e.attack_windup_left = self._windup_frames(e)
                    e.attack_cd_frames = e.attack_interval_frames
                else:
                    e.atk_start_frame = None
                    e.attack_cd_frames = 0
                    e.attack_windup_left = None
            else:
                e.attack_cd_frames = e.attack_interval_frames - el
                wl = self._windup_frames(e)
                e.attack_windup_left = max(0, wl - el)
                if (not getattr(e, 'atk_hit_done', False)) and el >= wl:
                    tgt = getattr(e, 'atk_target', None)
                    if tgt is not None and getattr(tgt, 'alive', False):
                        self._do_attack(e, tgt)
                    e.atk_hit_done = True
        # 终点判定（进点）
        self._check_escape(e)

    def _process_checkpoints(self, e: Unit) -> None:
        """按关卡 routes 的检查点序列推进（此前只认 MOVE，导致 WAIT/DISAPPEAR 之后卡死）。

        类型：MOVE/PATROL_MOVE（走到即过）、WAIT_FOR_SECONDS（原地等 time 秒）、
        DISAPPEAR（离场）、APPEAR_AT_POS（在新位置出现）、其余（DEFAULT/TRIGGER）直接跳过。
        """
        cps = e.checkpoints or []
        guard = 0
        while e.checkpoint_idx < len(cps) and guard < 64:
            guard += 1
            cp = cps[e.checkpoint_idx]
            if not isinstance(cp, dict):
                e.checkpoint_idx += 1
                continue
            ctype = str(cp.get('type') or '').upper()
            # 检查点坐标：优先顶层 row/col（build_routes 已归一化），再回退 position 字典。
            # ⚠ 早期只读 position 字典，而 build_routes 曾把 position 存成裸整数 ⇒ **MOVE 检查点全被
            #    瞬间跳过**，敌人直奔 route_end 绕开检查点绕行（里程 13.38 vs 折线 16.0 格，整条流水线
            #    偏快 ~7s，与实机锚定测量的偏差吻合，见 §7.51）。
            crow, ccol = cp.get('row'), cp.get('col')
            if crow is None or ccol is None:
                pos_d = cp.get('position')
                if isinstance(pos_d, dict):
                    crow, ccol = pos_d.get('row'), pos_d.get('col')
            if ctype in ('MOVE', 'PATROL_MOVE'):
                if crow is None or ccol is None:
                    e.checkpoint_idx += 1
                    continue
                cx, cy = float(ccol) + 0.5, float(crow) + 0.5
                off = cp.get('reachOffset') or {}
                cx += float(off.get('x') or 0.0)
                cy += float(off.get('y') or 0.0)
                rad = float(cp.get('reachDistance') or 0.0) or CHECKPOINT_RADIUS
                if math.hypot(fp.to_float(e.pos[0]) - cx, fp.to_float(e.pos[1]) - cy) <= rad + CHECKPOINT_ARRIVE_PAD:
                    e.checkpoint_idx += 1
                    continue
                break
            if ctype == 'WAIT_FOR_SECONDS':
                if e.wait_until is None:
                    e.wait_until = self.frame + int(round(float(cp.get('time') or 0.0) * FPS))
                if self.frame >= e.wait_until:
                    e.wait_until = None
                    e.checkpoint_idx += 1
                    continue
                break
            if ctype == 'DISAPPEAR':
                e.hidden = True
                e.inertia = (0, 0)
                e.checkpoint_idx += 1
                self.logs.append(OpLog(self.frame, 'enemy_disappear', {'enemy': e.name}))
                continue
            if ctype == 'APPEAR_AT_POS':
                if crow is not None and ccol is not None:
                    e.pos = (fp.from_float(float(ccol) + 0.5),
                             fp.from_float(float(crow) + 0.5))
                e.hidden = False
                e.wait_until = None
                e.inertia = (0, 0)
                e.checkpoint_idx += 1
                self.logs.append(OpLog(self.frame, 'enemy_appear',
                                       {'enemy': e.name, 'row': crow, 'col': ccol}))
                continue
            e.checkpoint_idx += 1      # 未知类型：跳过

    def _enemy_move(self, e: Unit) -> None:
        """敌人移动：**目标点选择**（直线优先 / navmap）+ **统一的惯性积分**。

        ★★★用户 2026-09-15 指出的机制（**已按玩家理解补齐**）：
          > 「大部分敌人出生时初速度为 0，有一个加速的过程；加速度方向与寻路有关；
          >   加速度大小与当前速度与速度上限的差有关。」
        玩家侧模型（`ak/raw/zhoudata/text/通用__PATH_FIND.m`，逐帧 1/30 s）：
          ```matlab
          initialV = [0,0];                          % 出生速度 0
          v_desired = v0 * unitDir;                  % v0 = 速度上限；方向 = 朝当前目标点
          v = v + (v_desired - v) * (4/15);          % ★速度向期望值**指数逼近**
          pos = pos + v * dt;
          ```
        **换算**：`4/15 = 8 × (1/30)` ⇒ 等价于"每秒速率 8"的连续形式
          `v ← v + (v_desired − v) · 8 · dt`，与本项目 `knowledge/20` 的
          「惯性：地面 8 / 飞行 20」**完全一致** ⇒ **两条独立来源互相印证**。
        ⇒ 因此本函数把**所有分支**的期望速度交给同一段惯性积分，
          并保证 **`e.inertia` 初值为 0（出生静止）**。
          可用 `options={'move_inertia': False}` 关闭（回退为"瞬时达到上限速度"）。
        """
        if e.route_end is None:
            return
        # 当前目标：检查点（MOVE 类型）或终点
        target_tile = None
        if e.checkpoints and e.checkpoint_idx < len(e.checkpoints):
            cp = e.checkpoints[e.checkpoint_idx]
            if cp.get('type') in ('MOVE', 'PATROL_MOVE'):
                target_tile = (int(cp.get('row', 0)), int(cp.get('col', 0)))
        if target_tile is None:
            target_tile = e.route_end
        # 朝【当前目标】建距离场（此前恒用 route_end 的场，检查点等于没生效，敌人会抄近路穿墙）
        nm = self.map.build_navmap(target_tile, flying=e.flying)
        g0 = (int(fp.to_float(e.pos[1])), int(fp.to_float(e.pos[0])))
        if g0 not in nm:
            # 装置把唯一通路堵死时的兜底：允许从装置格上「挤过去」，避免敌人原地卡死
            nm2 = self.map.build_navmap(target_tile, flying=e.flying, devices_block=False)
            if g0 in nm2:
                nm = nm2
        r, c = e.grid()
        speed = fp.to_float(e.move_speed) * self.move_multiplier
        desired = None          # 期望速度向量（大小 = speed）
        avoid = (0.0, 0.0)      # 避障附加力（仅 navmap 分支使用）
        # ★直线优先（依 routes 的 `allowDiagonalMove: true` / `visitEveryTileCenter: false` 语义）：
        #   若"当前位置 → 目标格中心"的线段不穿过不可通行格，则直接朝目标中心直线推进；
        #   否则回退到 navmap 逐格导航（贴墙/绕障）。
        if getattr(self, 'straight_path', True):
            ex0, ey0 = fp.to_float(e.pos[0]), fp.to_float(e.pos[1])
            gx, gy = target_tile[1] + 0.5, target_tile[0] + 0.5
            if (abs(gx - ex0) + abs(gy - ey0)) > 1e-6 and \
                    self.map.line_is_clear((ex0, ey0), (gx, gy), flying=e.flying):
                dvx, dvy = gx - ex0, gy - ey0
                norm = math.hypot(dvx, dvy) or 1.0
                desired = (dvx / norm * speed, dvy / norm * speed)
                e.next_node = None
        if desired is None:
            # 期望方向 = 朝下一节点（贴墙/边界时自动吸附回可走格，避免永久卡死）
            # ★ 航点锁定（strict_waypoints）：走到当前目标格之前不换目标。
            #   逐帧重选「距离更小的相邻格」会让敌人斜切拐角，实测里程 13.38 格 vs 检查点折线 ~15.6 格，
            #   导致整条敌人流水线比实机快约 19%（实机首漏 44.3s vs 模拟 37.3s，见 §7.49）。
            if getattr(self, 'strict_waypoints', False):
                tgt = e.next_node
                if tgt is None or (r, c) == tgt or tgt not in nm:
                    tgt, need_snap = self.map.nav_step_target((r, c), nm)
                    if need_snap:
                        e.pos = self.map.grid_to_world(tgt[0], tgt[1])
                        e.inertia = (0, 0)
                        r, c = tgt
                    e.next_node = tgt
                nxt = tgt
            else:
                nxt, need_snap = self.map.nav_step_target((r, c), nm)
                if need_snap:
                    e.pos = self.map.grid_to_world(nxt[0], nxt[1])
                    e.inertia = (0, 0)
                    r, c = nxt
            tr, tc = nxt
            ex, ey = fp.to_float(e.pos[0]), fp.to_float(e.pos[1])
            goal_x, goal_y = tc + 0.5, tr + 0.5
            dvx, dvy = goal_x - ex, goal_y - ey
            norm = math.hypot(dvx, dvy) or 1.0
            desired = (dvx / norm * speed, dvy / norm * speed)
            # 避障力（每 3 帧）；简化：若下一格不可通行则侧向推
            if self.frame % 3 == 0:
                av = (0.0, 0.0)
                for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                    if not self.map.is_passable(r + dr, c + dc, e.flying) or \
                            (r + dr, c + dc) in getattr(self.map, 'device_blocked', ()):
                        av = (av[0] - dc * 0.5, av[1] - dr * 0.5)
                e.cached_avoid = (fp.from_float(av[0]), fp.from_float(av[1]))
            avoid = (fp.to_float(e.cached_avoid[0]), fp.to_float(e.cached_avoid[1]))
        # ---------------- ★惯性积分（出生速度 0 ⇒ 加速过程） ----------------
        dvx, dvy = desired
        cur_vx, cur_vy = fp.to_float(e.inertia[0]), fp.to_float(e.inertia[1])
        if getattr(self, 'move_inertia', True):
            # 惯性/转向（地面 steeringFactor 8 / 飞行 20，knowledge/20、`02/24` §4）
            # ★等价于每帧 ×4/15（4/15 = 8 × 1/30），与玩家侧模型 `PATH_FIND.m` 一致。
            sf = 20.0 if e.flying else 8.0
            ax = (dvx - cur_vx) * sf + avoid[0]
            ay = (dvy - cur_vy) * sf + avoid[1]
            # ★加速度上限 `maxSteeringForce`（**10 或 100**，取决于单位设置；`02/24` §4、
            #   `03/22` R-029）：超限时**方向不变、模长收缩到上限**。
            amax = float(getattr(e, 'max_steering_force', 0.0) or 0.0)
            if amax <= 0:
                amax = 100.0 if e.flying else 10.0
            an = math.hypot(ax, ay)
            if an > amax and an > 0:
                ax, ay = ax / an * amax, ay / an * amax
            vx = cur_vx + ax * fp.to_float(fp.FRAME_TIME)
            vy = cur_vy + ay * fp.to_float(fp.FRAME_TIME)
        else:
            vx, vy = dvx + avoid[0], dvy + avoid[1]
        # 速度上限（= moveSpeed × moveMultiplier）
        vnorm = math.hypot(vx, vy)
        if vnorm > speed and vnorm > 0:
            vx, vy = vx / vnorm * speed, vy / vnorm * speed
        e.inertia = (fp.from_float(vx), fp.from_float(vy))
        dx = vx * fp.to_float(fp.FRAME_TIME)
        dy = vy * fp.to_float(fp.FRAME_TIME)
        # 硬碰撞 + **贴墙滑行**：整体位移不可走时，退化为只走 x 或只走 y。
        # 只做「整体位移合法才移动」会让单位在墙角（如 (2,1) 的斜向入口）永久卡死：
        # 斜向一步会先踩进隔壁的墙格。滑行是实机里敌人沿墙走的表现（§7.4x）。
        moved = self._try_step(e, dx, dy)
        if moved is None:
            moved = self._try_step(e, dx, 0.0)
            if moved is not None:
                e.inertia = (e.inertia[0], 0)
            else:
                moved = self._try_step(e, 0.0, dy)
                if moved is not None:
                    e.inertia = (0, e.inertia[1])
                else:
                    e.inertia = (0, 0)
        if moved is not None:
            e.pos = moved

    def _try_step(self, e: Unit, dx: float, dy: float):
        """尝试位移 (dx, dy)：落在可通行格则返回新位置，否则 None。"""
        x = fp.to_float(e.pos[0]) + dx
        y = fp.to_float(e.pos[1]) + dy
        nr, nc = int(math.floor(y)), int(math.floor(x))
        if not self.map.in_bounds(nr, nc):
            return None
        if not self.map.is_passable(nr, nc, e.flying):
            return None
        if (nr, nc) in getattr(self.map, 'device_blocked', ()):
            return None
        return (fp.from_float(x), fp.from_float(y))

    def _check_escape(self, e: Unit) -> None:
        if e.route_end is None:
            return
        er, ec = e.route_end
        ex, ey = fp.to_float(e.pos[0]), fp.to_float(e.pos[1])
        if math.hypot(ex - (ec + 0.5), ey - (er + 0.5)) <= CHECKPOINT_RADIUS + 0.5:
            e.escaped = True
            # 平民类单位（如 h12-4 的「诺伯特平民」，技能 key = wdfmr_cost）：
            # 鉴定完成后不可阻挡，**到达路径终点时我方费用上限 +2**（不扣生命、不回费）
            # 依据：enemy_skills.json → wdfmr_cost tooltip「到达路径终点时，我方费用上限+2」（见 §7.38）
            if e.extra.get('is_civilian'):
                gain = float(e.extra.get('civilian_max_cost') or 2.0)
                self.add_cost_cap(gain)
                self.logs.append(OpLog(self.frame, 'civilian_arrived',
                                       {'enemy': e.name, 'max_cost_gain': gain,
                                        'cost_max': self.cost_max}))
                return
            # ★②「无害目标」（`ActionData.isUnharmfulAndAlwaysCountAsKilled`）：
            #   依知识库 `02_作战机制.md`：「无害目标：到达路径终点**不扣关卡生命值、不触发警报**」，
            #   且"**只计已处理**"（恒计为击杀）⇒ 不扣命、记 `escape_harmless` 事件。
            if e.extra.get('harmless_and_counted'):
                self.logs.append(OpLog(self.frame, 'escape_harmless',
                                       {'enemy': e.name, 'counted_as_handled': True,
                                        'life': self.life}))
                return
            self.life -= e.life_point_reduce
            self.logs.append(OpLog(self.frame, 'escape', {'enemy': e.name, 'life': self.life}))

    def _block_ticker_fires(self, o: 'Unit') -> bool:
        """★阻挡扫描**相位**：判据属于**阻挡者（Character）自身**，而非全局帧时钟。

        依据（用户 2026-09-15 提醒 + 知识库）：
        「阻挡扫描帧与**干员部署帧**高度相关，且**不同干员存在差异**」
        —— `m_findBlockeeTicker` 是 `Character` 上的 **`PeriodicTicker`** 字段（偏移 0x380，
        见 `knowledge/04/33_cpp层战斗类结构与字段速查.md`）⇒ **每角色独立计时**，
        相位由其**被创建（部署）的时刻**决定 ⇒ 全局 `frame % 3` 只在"部署帧 ≡ 0 (mod 3)"时才巧合相等。

        **待补（无权威来源）**：`PeriodicTicker` 在角色创建时的**初值**与"先自增后判定 / 先判定后自增"
        的顺序未从反汇编中确认 ⇒ 这里用 `options['block_ticker_phase']` 暴露 0/1/2 三种相位供标定，
        默认 0（= 部署当帧即扫描）。
        """
        mode = str(getattr(self, 'block_scan_phase', 'per_unit'))
        if mode == 'global':                       # 旧行为（对照用）：全局帧时钟
            return self.frame % max(1, int(BLOCK_SCAN_INTERVAL)) == 0
        # 每角色相位：由"该角色被创建（部署/出生）的帧"导出 ⇒ 无需额外维护自增状态，也不会冻结。
        base = (getattr(o, 'spawn_frame', None)
                if getattr(o, 'spawn_frame', None) is not None
                else getattr(o, 'deploy_frame', 0))
        t = int(base or 0) + int(getattr(self, 'block_ticker_phase', 0))
        return (self.frame - t) % max(1, int(BLOCK_SCAN_INTERVAL)) == 0

    def _block_scan(self, e: Unit) -> None:
        if e.blocked_by:
            return
        r, c = e.grid()
        best = None
        best_d = 1e9
        for o in self.units.values():            # 预置装置（h12-4「街头应急储备」）**不阻挡敌人**：它只作为寻路障碍（device_blocked），
            # 敌人绕开它走；敌人不会攻击它，我方单位可以主动打它换取费用/上限（用户 2026-09-14 更正）。
            # 若把 DEVICE 算作阻挡者，敌人会被卡住并反手拆掉储备（曾导致 24.7s 两个储备被敌人打死，见 §7.4x）
            if (o.side != 'ALLY' and not self.devices_block_enemies) or not o.alive or o.block_cnt <= 0:
                continue
            if not self._enemy_can_reach(e, o):
                continue          # 地面敌人不会被高台单位阻挡
            if not self._block_ticker_fires(o):
                continue          # ★阻挡者的**自身相位**未到 ⇒ 本帧不扫描（见 `_block_ticker_fires`）
            if len(o.blocking) >= o.block_cnt:
                continue
            # ★④**阻挡判定**（对应事件 `block` / `block_snap`）：
            #   判据 = 敌人中心与阻挡者中心的欧氏距离 ≤ `block_capture_distance`
            #   —— 这是"**捕获距离**"语义，**不是**"两个碰撞体积之和"。
            #   演进：①`BLOCK_RADIUS+0.5=1.2071` 过松（对角 1.2 格也判阻挡，敌人停在 1.2 格、
            #   游走出近战范围）；②"格坐标 4 邻接"过严（必须走进同格才判）；
            #   ③正解 = 欧氏 ≤ **1.0**（≈相邻格中心距）。
            #   ★①**碰撞体积**（`collider_radius`）在本判定中**不参与** —— 见文件头部对照表。
            # ★两种可选的**阻挡判据**（`options={'block_rule': …}`）：
            #   - `'capture_distance'`（默认）：`dist(敌人中心, 阻挡者中心) ≤ block_capture_distance`
            #   - `'cell_3x3'`：敌人进入**阻挡者所在格或其 8 邻格**（＝到该格方格的最短距离 ≤ 1.0）
            #     —— "格"语义，与用户对阻挡/范围的"方格"表述一致，供对照实验用。
            if str(getattr(self, 'block_rule', 'radius')) == 'radius':
                # ★④**权威规则（默认）**：`dist(敌人中点, 阻挡者中点) ≤ 阻挡半径(0.7071)`
                #   —— 与 B站 cv25694535 / `knowledge/04/37` §一 逐字一致；半径**统一**、无逐敌差异。
                d = e.dist_to(o)
                if d > float(getattr(self, 'block_radius', BLOCK_RADIUS_DEFAULT)):
                    continue
            elif str(getattr(self, 'block_rule', 'radius')) == 'cell_3x3':
                # 敌人**进入阻挡者所在格或其 8 邻格**（切比雪夫格距 ≤ 1）——"格"语义
                gr, gc = e.grid()
                orr, occ = o.grid()
                if max(abs(gr - orr), abs(gc - occ)) > 1:
                    continue
                d = e.dist_to(o)
            elif str(getattr(self, 'block_rule', 'capture_distance')) == 'cell_3x3_round':
                # 同上但用"到该格方格的最短距离 ≤ block_cell_margin"（角部更严）
                ex, ey = fp.to_float(e.pos[0]), fp.to_float(e.pos[1])
                if self.point_to_cell_distance(ex, ey, o.grid()) > float(
                        getattr(self, 'block_cell_margin', 1.0)):
                    continue
                d = e.dist_to(o)
            elif str(getattr(self, 'block_rule', 'capture_distance')) == 'collision_pair':
                # ★"碰撞对"语义：两个**碰撞体积**相接触 ⇒ 距离 ≤ 干员碰撞半径 + 敌人碰撞半径
                #   （①碰撞体积第一次真正参与判定；其余规则都不用①）
                d = e.dist_to(o)
                if d > float(getattr(o, 'collider_radius', COLLIDER_RADIUS_ALLY)) + \
                        float(getattr(e, 'collider_radius', COLLIDER_RADIUS_ENEMY_DEFAULT)):
                    continue
            elif str(getattr(self, 'block_rule', 'capture_distance')) == 'cell_3x3_hit':
                # ★"**敌人的 0.1 圆**与『阻挡者格 + 8 邻格』相交" ⇒ 与 ②索敌同一体积语义
                ex, ey = fp.to_float(e.pos[0]), fp.to_float(e.pos[1])
                hr = float(getattr(e, 'hit_radius', HIT_VOLUME_ENEMY_DEFAULT) or 0.0)
                if self.point_to_cell_distance(ex, ey, o.grid()) > 1.0 + hr:
                    continue
                d = e.dist_to(o)
            else:
                d = e.dist_to(o)
                if d > float(getattr(self, 'block_capture_distance', BLOCK_CAPTURE_DISTANCE)):
                    continue
            if d < best_d:
                best, best_d = o, d
        if best is not None:
            e.blocked_by.append(best.uid)
            best.blocking.append(e.uid)
            self.logs.append(OpLog(self.frame, 'block', {'enemy': e.name, 'by': best.name}))
            # ★阻挡吸附（依 1-1 标定反推）：把敌人对齐到"与阻挡者相邻的格中心"。
            #   理由：1-1 第 2 只沿 route4 直线逼近芬，**直线最近距离 1.083 格 > 近战 1 格**
            #   ⇒ 若停在接触点，芬永远打不到它；但实机标定中芬确实打了它
            #   ⇒ AK 语义应是"被挡后停在阻挡者相邻格"。
            # ★**阻挡偏移**（`BlockBalancer.CalculateBlockOffset`）：
            #   默认按文档化算法求 F 并**在 0.2s（6 帧）内强制移动**过去；F 记为该敌人的**稳定阻挡位置**。
            #   旧自造版"吸附到相邻格中心"保留为 `block_offset_mode='cell_center'` 作对照。
            if str(getattr(self, 'block_offset_mode', 'code')) == 'cell_center':
                if getattr(self, 'block_snap', False):
                    self._snap_blocked_enemy(e, best)
            else:
                F = self._block_offset(e, best)
                self._start_block_tween(e, F)


    def _block_offset(self, e: 'Unit', blocker: 'Unit') -> tuple[int, int]:
        """★**阻挡偏移**：`BlockBalancer.CalculateBlockOffset`（RVA 0x7C1050）。

        逐字对应 `knowledge/04/37_阻挡与阻挡偏移_代码核验.md` §三（源：B站 cv25694535 + 反汇编）：

        ```
        输入 A = 阻挡者中点, B = 敌人中点
        ① 长度延长：AC = AB；若 |AB| < 0.5 → AC = normalize(AB) * 0.5
        ② 累加修正（仅当 C 点 0.1 半径内存在**其它已被 A 阻挡**的敌人）：
             d = |D − C|（D 取该敌人的**稳定阻挡位置**）
             d < 0.1        → corr += normalize( rot90CW(A→D) )
             0.1 ≤ d < 0.4  → corr += (0.4 − d) × 50 × normalize(D − C)
             d ≥ 0.4        → 无事
        ③ 合成：CE = normalize(corr) × 0.2 ；AE = AC + CE ；AF = normalize(AE) × |AC|
        ④ 结果：F = A + AF（敌人 0.2s 内强制移动到 F；F 即其"稳定阻挡位置"）
        ```
        """
        import math as _m
        ax, ay = fp.to_float(blocker.pos[0]), fp.to_float(blocker.pos[1])
        bx, by = fp.to_float(e.pos[0]), fp.to_float(e.pos[1])
        abx, aby = bx - ax, by - ay
        d_ab = _m.hypot(abx, aby)
        if d_ab <= BLOCK_OFFSET_MIN_DIST:            # 中点重合 ⇒ 不产生任何偏移（例：5-3 开局术士）
            return (e.pos[0], e.pos[1])
        if d_ab < 0.5:                                # ① 长度延长到 0.5（只改长度、不改方向）
            acx, acy = abx / d_ab * 0.5, aby / d_ab * 0.5
        else:
            acx, acy = abx, aby
        cx_, cy_ = ax + acx, ay + acy
        corr_x = corr_y = 0.0
        for uid in list(getattr(blocker, 'blocking', []) or []):
            if uid == e.uid:
                continue
            o = self.units.get(uid)
            if o is None:
                continue
            sp = getattr(o, 'stable_block_pos', None) or o.pos     # ★取"稳定阻挡位置"
            dx_, dy_ = fp.to_float(sp[0]), fp.to_float(sp[1])
            d = _m.hypot(dx_ - cx_, dy_ - cy_)
            vx, vy = dx_ - ax, dy_ - ay                            # A→D
            if d < 0.1:                                            # 把 A→D 绕 A 顺时针 90°
                vx, vy = vy, -vx
                n = _m.hypot(vx, vy) or 1.0
                corr_x += vx / n
                corr_y += vy / n
            elif d < 0.4:
                n = _m.hypot(dx_ - cx_, dy_ - cy_) or 1.0
                k = (0.4 - d) * 50.0
                corr_x += k * (dx_ - cx_) / n
                corr_y += k * (dy_ - cy_) / n
        if abs(corr_x) > 1e-9 or abs(corr_y) > 1e-9:
            n = _m.hypot(corr_x, corr_y)
            cex, cey = corr_x / n * 0.2, corr_y / n * 0.2             # ③ CE 长度固定 0.2
        else:
            cex = cey = 0.0
        aex, aey = acx + cex, acy + cey
        n = _m.hypot(aex, aey) or 1.0
        ac_len = _m.hypot(acx, acy)
        afx, afy = aex / n * ac_len, aey / n * ac_len                 # AF 长度设回 |AC|
        return (fp.from_float(ax + afx), fp.from_float(ay + afy))

    def _start_block_tween(self, e: 'Unit', F) -> None:
        """敌人 B 在 **0.2s（6 帧）** 内强制移动到 F（`Enemy.BLOCKING_TWEEN_DURATION`）。"""
        import math as _m
        e.stable_block_pos = F                       # ★F = 该敌人的"稳定阻挡位置"
        e.block_tween = {'from': (e.pos[0], e.pos[1]), 'to': F,
                         'frames': BLOCK_TWEEN_FRAMES, 'k': 0}
        e.inertia = (0, 0)
        e.next_node = None
        ex, ey = fp.to_float(e.pos[0]), fp.to_float(e.pos[1])
        fx, fy = fp.to_float(F[0]), fp.to_float(F[1])
        self.logs.append(OpLog(self.frame, 'block_offset',
                               {'enemy': e.name, 'from': (round(ex, 3), round(ey, 3)),
                                'to': (round(fx, 3), round(fy, 3)),
                                'dist': round(_m.hypot(fx - ex, fy - ey), 4)}))

    def _step_block_tween(self, e: 'Unit') -> bool:
        """推进阻挡偏移 tween（每帧一步）；返回 True 表示本帧位置由 tween 决定。"""
        tw = getattr(e, 'block_tween', None)
        if not tw:
            return False
        tw['k'] += 1
        t = min(1.0, tw['k'] / max(1, tw['frames']))
        x0, y0 = fp.to_float(tw['from'][0]), fp.to_float(tw['from'][1])
        x1, y1 = fp.to_float(tw['to'][0]), fp.to_float(tw['to'][1])
        e.pos = (fp.from_float(x0 + (x1 - x0) * t), fp.from_float(y0 + (y1 - y0) * t))
        if tw['k'] >= tw['frames']:
            e.pos = tw['to']
            e.block_tween = None
        return True

    def _snap_blocked_enemy(self, e: Unit, blocker: Unit) -> None:
        """把被阻挡的敌人吸附到"与阻挡者相邻（4 邻接）且可通行"的格中心。"""
        import math as _m
        br, bc = blocker.grid()
        ex, ey = fp.to_float(e.pos[0]), fp.to_float(e.pos[1])
        best, best_d = None, 1e9
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            r, c = br + dr, bc + dc
            if not self.map.is_passable(r, c, flying=e.flying):
                continue
            cx, cy = c + 0.5, r + 0.5
            d = _m.hypot(cx - ex, cy - ey)
            if d < best_d:
                best, best_d = (r, c), d
        if best is not None:
            e.pos = self.map.grid_to_world(best[0], best[1])
            e.inertia = (0, 0)
            e.next_node = None
            self.logs.append(OpLog(self.frame, 'block_snap',
                                   {'enemy': e.name, 'by': blocker.name, 'to': best}))

    def _on_token_lost(self, tok: Unit) -> None:
        """召唤物被撤退/击倒/回收：触发召唤者天赋（令「随付笺咏醉屠苏」→ +SP 与叠层攻击力）。"""
        owner = self.units.get(tok.extra.get('owner'))
        if owner is None:
            return
        sp_gain = owner.talent_bb('sp')
        atk_per = owner.talent_bb('atk')
        max_stack = int(owner.talent_bb('max_stack_cnt') or 0)
        if sp_gain:
            owner.sp = min(owner.sp_cost, owner.sp + float(sp_gain))
            owner.skill_charge = int(owner.sp)
        if atk_per and max_stack:
            stacks = min(max_stack, int(owner.extra.get('talent_atk_stacks', 0)) + 1)
            owner.extra['talent_atk_stacks'] = stacks
            owner.buffs = [b for b in owner.buffs if b.get('src') != '天赋:随付笺咏醉屠苏']
            owner.buffs.append({'src': '天赋:随付笺咏醉屠苏', 'atk': float(atk_per) * stacks,
                                'until': None})
        self.logs.append(OpLog(self.frame, 'talent_token_lost',
                               {'owner': owner.name, 'token': tok.name,
                                'sp_gain': float(sp_gain or 0),
                                'atk_stacks': int(owner.extra.get('talent_atk_stacks', 0))}))

    def _operator_tick(self, u: Unit) -> None:
        if not u.alive:
            return
        u.purge_expired_buffs(self.frame)
        if u.attack_cd_frames > 0:
            u.attack_cd_frames -= 1
        # ---- 技能：结束判定 + SP 回复（表驱动 spData）----
        if u.skill_active and u.skill_until is not None and self.frame >= u.skill_until:
            self._end_skill(u)
        if not u.skill_active and u.sp_type == 'INCREASE_WITH_TIME':
            u.sp = min(u.sp_cost, u.sp + u.sp_increment / FPS)
            u.skill_charge = int(u.sp)
        elif not u.skill_active and u.sp_type == 'INCREASE_WHEN_ATTACK' and self.sp_assume_attacking:
            # 理想攻击速率充能（每 baseAttackTime 秒 +increment）：与打图端的假设保持一致
            bat_s = max(1e-3, fp.to_float(u.base_attack_time))
            u.sp = min(u.sp_cost, u.sp + u.sp_increment / bat_s / FPS)
            u.skill_charge = int(u.sp)
        # ★AUTO 技能：SP 满即**自动发动**（无需玩家点击）
        #   判据来自 `skill_table.json` 顶层的 `skillType == 'AUTO'`（如芬「冲锋号令·α型」）。
        #   与视频侧一致：1-1 中该技能在游戏帧 581 自动发动并回复 6 费用。
        if (self.auto_skill and not u.skill_active and u.skill
                and str(getattr(u, 'skill_type', '') or '').upper() == 'AUTO'
                and u.sp_cost > 0 and u.sp + 1e-9 >= u.sp_cost):
            self._activate_skill(u)
        # 令 S3「宁作吾」：技能期间召唤物每 interval 秒对周围四格造成法术伤害
        self._summon_aoe_tick(u)
        # ★普攻时序：**统一时间基准**（`atk_start_frame`）——
        #   命中在 `start + windup`、下一周期从 `start + interval` 起算
        #   ⇒ **命中间隔恒为 `interval`**（前摇含在周期内，结构上不可能叠加）。
        st = getattr(u, 'atk_start_frame', None)
        if st is None:
            tgt = self.pick_operator_target(u)
            if tgt is not None:
                u.atk_start_frame = self.frame
                u.atk_hit_done = False
                u.atk_target = tgt
                u.attack_windup_left = self._windup_frames(u)
                u.attack_cd_frames = u.attack_interval_frames
                # ★事件与语义的显式关联（用户要求"从代码层面明确"）：
                #   每次**索敌成功**记一条 `target_select`，并带上**判据**：
                #     `grid`        = 目标中心所在格在攻击范围格集合内（③方格范围）
                #     `hit_volume`  = 目标受击圆与某个范围格相交（②受击判定体积）
                #     `distance_legacy` = 旧口径（中心距 ≤ N，兼容开关开启时才会出现）
                #   ⇒ 复盘时可直接按事件过滤，看"哪一次索敌是靠体积完成的"。
                _ok, why = self.is_targetable(u, tgt)
                self.logs.append(OpLog(self.frame, 'target_select', {
                    'unit': u.name, 'target': tgt.name, 'judge': why,
                    'hit_radius': round(float(getattr(tgt, 'hit_radius', 0.0) or 0.0), 3)}))
            # 无目标 ⇒ 保持空闲
        else:
            el = self.frame - st
            if el >= u.attack_interval_frames:
                # ★★同帧重启（同 `_enemy_tick`，T-200h `04/78` off-by-one 修复）★
                tgt = getattr(u, 'atk_target', None)
                if tgt is not None and getattr(tgt, 'alive', False):
                    u.atk_start_frame = self.frame
                    u.atk_hit_done = False
                    u.attack_windup_left = self._windup_frames(u)
                    u.attack_cd_frames = u.attack_interval_frames
                else:
                    u.atk_start_frame = None          # 无有效目标 ⇒ 空闲（下一帧可再起手）
                    u.attack_cd_frames = 0
                    u.attack_windup_left = None
            else:
                u.attack_cd_frames = u.attack_interval_frames - el
                u.attack_windup_left = max(0, self._windup_frames(u) - el)
                wl = self._windup_frames(u)
                if (not getattr(u, 'atk_hit_done', False)) and el >= wl:
                    tgt = getattr(u, 'atk_target', None)
                    if tgt is not None and getattr(tgt, 'alive', False):
                        self._do_attack(u, tgt)
                    u.atk_hit_done = True

    @staticmethod
    def _windup_frames(u) -> int:
        """普攻前摇帧数 —— **走时间层唯一换算点**（`ak_sim.timeline.windup_fp`）。

        ★2026-09-29（T-200c）改造：优先级 = 真值 > 单点覆盖 > 职业比例表 > 默认。
          1. `u.pre_delay_fp` / `u.pre_delay_sec`：**本体真值**（`AbstractAnimatedAbility._preDelay //0x180`
             → `m_preDelay //0x1A0`），本地 JSON 表**没有**该字段，需从 prefab 提取（见 04/69）；
          2. `u._windup_ratio`：单点覆盖（逐单位标定用）；
          3. `WINDUP_RATIO_BY_PROFESSION` / 默认值：**反推的兜底**（🟡，必须记来源）。

        ★**语义要点**：前摇**属于攻击周期之内**
        （即"命中间隔 = `attack_interval_frames`"，而非"间隔 = 前摇 + 周期"）。
        因此调用方必须**在"起手"时就重置 `attack_cd_frames = attack_interval_frames`**，
        到前摇结束才结算伤害。
        """
        from ak_sim import timeline, fp as _fp
        # ★敌方前摇标定覆盖（T2 反推，`04/78` 建议）：本体 `_preDelay` 全为 0，
        #   前摇真值在**动画事件帧**里；在从 prefab 读出该帧号之前，用标定反推值过渡。
        #   来源：1-1 标定 236「芬 阻挡」→ 255「猎狗pro 命中」= **19 帧**。
        if ENEMY_WINDUP_OVERRIDE > 0 and not getattr(u, 'is_operator', False):
            u._windup_source = f'calibrated({ENEMY_WINDUP_OVERRIDE})'
            return int(ENEMY_WINDUP_OVERRIDE)
        iv_fp = getattr(u, 'attack_interval_fp', None)
        if iv_fp is None:
            iv_fp = _fp.from_float(float(u.attack_interval_frames) / float(FPS))
        wu_fp, src = timeline.windup_fp(u, iv_fp)
        n = timeline.interval_frames(wu_fp)
        u._windup_source = src            # 记录来源（'prefab' / 'ratio' / 'ratio_default'）
        return max(0, n)

    def _summon_aoe_tick(self, u: Unit) -> None:
        """令 S3：自身技能期间，其召唤物每 interval 秒对周围四格敌人造成 atk_scale×令攻击力 的法术伤害。"""
        for tok in list(self.units.values()):
            if not tok.alive or not tok.is_token:
                continue
            owner = self.units.get(tok.extra.get('owner'))
            if owner is None or owner.uid != u.uid or not owner.skill_active:
                continue
            bb = (owner.skill or {}).get('blackboard') or {}
            interval = float(bb.get('interval') or 0.0)
            scale = float(bb.get('atk_scale') or 0.0)
            if interval <= 0 or scale <= 0:
                continue
            acc = tok.extra.get('aoe_acc', 0.0) + 1.0 / FPS
            if acc + 1e-9 < interval:
                tok.extra['aoe_acc'] = acc
                continue
            tok.extra['aoe_acc'] = acc - interval
            # ★⑤**范围攻击命中**（事件 `summon_aoe`）：走 `aoe_targets` ——
            #   **只看"目标中心是否位于选定格内"**，★与受击判定体积**无关**（用户第 4 点）。
            cells = self.aoe_cells_around(tok.grid(), cross_only=True)
            for e in self.aoe_targets(cells):
                dmg = combat.calc_damage(fp.from_int(int(owner.eff_atk())), fp.from_float(scale),
                                         combat.MAGICAL, target_def=e.df, target_res=e.res)
                combat.apply_damage(e, dmg)
                self.logs.append(OpLog(self.frame, 'summon_aoe',
                                       {'src': tok.name, 'tgt': e.name,
                                        'dmg': round(fp.to_float(dmg), 2), 'hp_after': e.hp}))
                if e.dead:
                    self.logs.append(OpLog(self.frame, 'kill', {'tgt': e.name, 'by': tok.name}))


    # ---------------- ★弹道（投射物） ----------------
    PROJECTILE_SPEED_CELLS_PER_FRAME = 0.1667   # ≈1 格 / 6 帧（由 1-1 标定反推）

    @staticmethod
    def _is_ranged(u) -> bool:
        """是否远程单位（带弹道的候选）。

        依据 `rangeId`：芬（近战）为 `1-1`，月见夜（远程）为 `2-3`
        ⇒ 首段数字 > 1 视为远程。数据表中没有直接的"是否弹道"字段（见 probe_projectile.py），
        故用攻击范围作启发式；后续可按干员/皮肤细化"发射点偏移"。
        """
        rid = str(getattr(u, 'range_id', '') or '')
        head = rid.split('-')[0].strip()
        try:
            return int(head) > 1 if head.isdigit() else False
        except Exception:
            return False

    def _projectile_frames(self, src, tgt) -> int:
        """子弹飞行帧数 = round(格距 / 速度)。随距离变化 ⇒ 体现"追击"的时序后果。"""
        try:
            sx, sy = float(src.x), float(src.y)
            tx, ty = float(tgt.x), float(tgt.y)
            dist = ((sx - tx) ** 2 + (sy - ty) ** 2) ** 0.5
        except Exception:
            dist = 1.0
        spd = float(getattr(self, 'projectile_speed', self.PROJECTILE_SPEED_CELLS_PER_FRAME))
        return max(0, int(round(dist / max(1e-6, spd))))

    def _tick_pending_hits(self) -> None:
        """结算到期的"弹道伤害"。"""
        if not self.pending_hits:
            return
        keep = []
        for ph in self.pending_hits:
            if self.frame < ph['f']:
                keep.append(ph)
                continue
            t = ph['tgt']
            src = ph['src']
            if getattr(t, 'alive', False):
                combat.apply_damage(t, ph['dmg'])
                self.logs.append(OpLog(self.frame, 'hit', {
                    'src': src.name if src else '?', 'tgt': t.name,
                    'dmg': round(fp.to_float(ph['dmg']), 2), 'hp_after': t.hp}))
                if t.dead:
                    t.extra['killed_by'] = src.name if src else '?'
                    if t.side == 'DEVICE':
                        self.logs.append(OpLog(self.frame, 'device_killed',
                                               {'tgt': t.name, 'by': src.name if src else '?'}))
                    else:
                        self.logs.append(OpLog(self.frame, 'kill',
                                               {'tgt': t.name, 'by': src.name if src else '?'}))
            # 目标已死 ⇒ 子弹消散（不结算）
        self.pending_hits = keep


    # ---------------- ★职业特性（trait）atk_scale ----------------
    TRAIT_RANGED_DIST = 0.99    # 目标距离 ≥ 该值 视为"远程攻击"（≥1 格；含恰为 1.00 的边界）

    def _trait_atk_scale(self, src: Unit, tgt: Unit):
        """取"职业特性"里的 `atk_scale`；仅当本次攻击为"远程"时生效。

        - 数据来源：干员 spec 的 `trait`（`blackboard` 中的 `atk_scale`），
          若 spec 未带 `trait`，则回退到 `character_table.json` 现取一次并缓存；
        - **判据**：`src.dist_to(tgt) > TRAIT_RANGED_DIST`（远程）⇒ 应用缩放；否则返还 1.0。
        """
        key = getattr(src, 'key', None)
        if not key or not getattr(src, 'is_operator', False):
            return None
        cache = getattr(self, '_trait_scale_cache', None)
        if cache is None:
            cache = {}
            self._trait_scale_cache = cache
        if key not in cache:
            val = None
            try:
                from . import data as _D
                ct = _D.load_table('character_table.json')
                c = ct.get(key) or {}
                for cand in ((c.get('trait') or {}).get('candidates') or []):
                    for bb in (cand.get('blackboard') or []):
                        if bb.get('key') == 'atk_scale' and bb.get('value') is not None:
                            val = float(bb['value'])
                            break
                    if val is not None:
                        break
            except Exception:
                val = None
            cache[key] = val
        val = cache.get(key)
        if val is None:
            return None
        try:
            d = src.dist_to(tgt)
        except Exception:
            return None
        return val if d >= self.TRAIT_RANGED_DIST else 1.0

    def _do_attack(self, src: Unit, tgt: Unit) -> None:
        bb = (src.skill or {}).get('blackboard') or {}
        scale_v = 1.0
        # ★职业特性（trait）的 atk_scale：如月见夜（lord 远程近卫）远程攻击 ×0.8。
        #   依 1-1 标定反推：实机"432 芬325 + 438 月见夜455(=569×0.8) = 780 < 820 ⇒ 不致死"，
        #   接着"464 芬再打 325 ⇒ 击杀" ⇒ 与标定完全吻合；若缺该特性则会 439 即死。
        if getattr(self, 'trait_scale', True):
            ts = self._trait_atk_scale(src, tgt)
            if ts is not None and ts != 1.0:
                scale_v *= float(ts)
        extra_targets = 0
        if src.skill_active:
            for k in ('attack@atk_scale', 'atk_scale'):
                if bb.get(k) is not None:
                    scale_v = float(bb[k])
                    break
            # 蕾缪安 S1「重逢问候」：额外攻击 1 名敌人
            if bb.get('attack@trigger_time') is not None and bb.get('attack@aim_interval') is None \
                    and bb.get('attack@atk_scale') is not None:
                extra_targets = 1
        targets = [tgt]
        if extra_targets:
            for e in self.enemies_in_range(src):
                if e.uid != tgt.uid:
                    targets.append(e)
                    break
        for t in targets:
            dmg = combat.calc_damage(fp.from_int(int(src.eff_atk())), fp.from_float(scale_v),
                                     combat.PHYSIC, target_def=t.df, target_res=t.res)
            # ★弹道判定：远程攻击若带弹道 ⇒ 伤害改为"延迟到子弹到达时结算"
            if self.projectile_enabled and self._is_ranged(src):
                n = self._projectile_frames(src, t)
                self.pending_hits.append({'f': self.frame + n, 'tgt': t, 'dmg': dmg,
                                          'src': src, 'born': self.frame})
                self.logs.append(OpLog(self.frame, 'projectile', {
                    'src': src.name, 'tgt': t.name, 'frames': n}))
                continue
            dealt = combat.apply_damage(t, dmg)
            self.logs.append(OpLog(self.frame, 'hit', {'src': src.name, 'tgt': t.name,
                                                       'dmg': round(fp.to_float(dmg), 2), 'hp_after': t.hp}))
            if t.dead:
                t.extra['killed_by'] = src.name
                if t.side == 'DEVICE':
                    # 我方打掉应急储备：+费用/上限在 on-death 结算里生效
                    self.logs.append(OpLog(self.frame, 'device_killed',
                                           {'tgt': t.name, 'by': src.name}))
                else:
                    self.logs.append(OpLog(self.frame, 'kill', {'tgt': t.name, 'by': src.name}))
        # SP：攻击回复型
        if src.sp_type == 'INCREASE_WHEN_ATTACK' and not src.skill_active:
            src.sp = min(src.sp_cost, src.sp + src.sp_increment)
            src.skill_charge = int(src.sp)
        # 弹药型技能：每次攻击消耗 1 发
        if src.skill_active and src.skill_ammo is not None:
            src.skill_ammo -= 1
            if src.skill_ammo <= 0:
                self._end_skill(src)

    # ---------------- 记录 ----------------
    def dump_frames(self, path: str, fmt: str = 'jsonl', include_units: bool = True) -> str:
        """把逐帧切片落盘（需求 1.6）。

        fmt: jsonl（逐行一帧，便于流式读取/大文件）| json（整体）
        """
        import json as _json
        import os as _os
        _os.makedirs(_os.path.dirname(path) or '.', exist_ok=True)
        recs = self.frames
        if not include_units:
            recs = [{k: v for k, v in fr.items() if k != 'units'} for fr in recs]
        if fmt == 'jsonl':
            with open(path, 'w', encoding='utf-8') as f:
                for fr in recs:
                    f.write(_json.dumps(fr, ensure_ascii=False) + '\n')
        else:
            with open(path, 'w', encoding='utf-8') as f:
                _json.dump({'level': self.level_id, 'result': self.result,
                            'frames': recs}, f, ensure_ascii=False)
        return path

    def dump_logs(self, path: str) -> str:
        import json as _json
        import os as _os
        _os.makedirs(_os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump([{'frame': l.frame, 'kind': l.kind, 'detail': l.detail} for l in self.logs],
                       f, ensure_ascii=False, indent=1)
        return path

    def _rng_frame_events(self) -> list:
        """本帧发生的**随机判定明细**（供逐帧切片审计/复现）。

        来源：`self.rng` 若提供 `frame_events()`（记录"何时抽了什么"），否则退化为
        "本帧抽取次数 > 0 时给一条计数记录"，保证切片里**总能看到随机判定是否发生**。
        """
        fn = getattr(self.rng, 'frame_events', None)
        if callable(fn):
            try:
                return list(fn(self.frame) or [])
            except Exception:                                     # noqa: BLE001
                pass
        prev = getattr(self, '_rng_draws_prev', 0)
        now = int(getattr(self.rng, 'draws', 0))
        n = now - prev
        return [{'draws': n}] if n > 0 else []

    def _record_frame(self) -> None:
        # ★ 需求 1.6：逐帧完整切片 —— 补全"操作 / 攻速 / 移速 / 阻挡 / 技能 / 随机判定"
        ops_this = [{'kind': l.kind, 'detail': l.detail}
                    for l in self.logs if l.frame == self.frame]
        snap = {
            'f': self.frame,
            'cost': round(self.cost, 4),
            'life': self.life,
            'ops': ops_this,                      # 本帧发生的操作（顺序即执行顺序，对应"同帧多操作"）
            'units': [{
                'uid': u.uid, 'side': u.side, 'key': u.key, 'name': u.name,
                'hp': u.hp, 'max_hp': u.max_hp,
                'x': round(fp.to_float(u.pos[0]), 4), 'y': round(fp.to_float(u.pos[1]), 4),
                'state': u.state, 'cd': u.attack_cd_frames, 'blocked': len(u.blocked_by),
                'blocking': len(u.blocking), 'sp': u.skill_charge,
                # ↓ 需求 1.6 补全项
                'atk': u.atk, 'df': u.df, 'res': float(u.res),
                'base_attack_time': round(fp.to_float(u.base_attack_time), 4),
                'attack_speed': float(u.attack_speed),
                'atk_interval_frames': u.attack_interval_frames,
                'move_speed': round(fp.to_float(u.move_speed), 4),
                # ★需求 1.6 补全：**当前速度向量**（惯性实现后"实际移速"与"速度上限"不同，
                #   只记 move_speed（上限）不足以复现轨迹/核对"出生初速为 0 的加速过程"）
                'vx': round(fp.to_float(u.inertia[0]) if getattr(u, 'inertia', None) else 0.0, 4),
                'vy': round(fp.to_float(u.inertia[1]) if getattr(u, 'inertia', None) else 0.0, 4),
                'v_abs': round(math.hypot(
                    fp.to_float(u.inertia[0]) if getattr(u, 'inertia', None) else 0.0,
                    fp.to_float(u.inertia[1]) if getattr(u, 'inertia', None) else 0.0), 4),
                # ★需求 1.6 补全：**攻击时序**（前摇剩余/剩余冷却），
                #   只记 interval 无法核对"前摇 18 帧后命中"这类事件帧。
                #   注意字段真名是 `attack_windup_left`（无前摇时为 None）。
                'atk_windup_left': (None if getattr(u, 'attack_windup_left', None) is None
                                    else int(u.attack_windup_left)),
                'atk_cd_frames': int(getattr(u, 'attack_cd_frames', 0) or 0),
                'block_cnt': u.block_cnt, 'weight': u.weight, 'flying': bool(u.flying),
                'route_index': u.route_index, 'hidden': bool(getattr(u, 'hidden', False)),
                'is_operator': bool(u.is_operator), 'is_token': bool(u.is_token),
                'skill_active': bool(getattr(u, 'skill_active', False)),
                'sp_raw': round(float(getattr(u, 'sp', 0.0)), 4),
                'buffs': len(getattr(u, 'buffs', []) or []),
                'talents': len(getattr(u, 'talents', []) or []),
            } for u in sorted(self.units.values(), key=lambda z: z.uid)],
            'rng_state': self.rng.state_snapshot(),
            'rng_draws': int(getattr(self.rng, 'draws', 0)),   # 累计随机抽取次数（帧间差=本帧判定次数）
            # ★需求 1.6 补全：**本帧的随机判定明细**（此前只有累计次数，切片里看不到"判了什么"）
            'rng_events': self._rng_frame_events(),
        }
        self.frames.append(snap)

    def run(self, max_frames: int | None = None, ops: list[dict] | None = None,
            callback: Callable[['Battle'], None] | None = None) -> 'Battle':
        """运行至结束或 max_frames。ops 为 {frame, kind, ...} 操作表（与轴表共用格式）。"""
        ops = sorted(ops or [], key=lambda o: o['frame'])
        oi = 0
        limit = max_frames if max_frames is not None else self.max_frames
        while not self.finished and self.frame < limit:
            while oi < len(ops) and ops[oi]['frame'] == self.frame:
                self._apply_op(ops[oi])
                oi += 1
            if callback:
                callback(self)
            self.tick()
        return self

    def _apply_op(self, op: dict) -> None:
        kind = op.get('kind')
        if kind == 'deploy':
            self.deploy(op['char'], op['row'], op['col'], op.get('dir', '右'),
                        module=op.get('module'), module_level=op.get('module_level', 3),
                        skill_index=op.get('skill_index', 0), skill_level=op.get('skill_level', 10),
                        elite=op.get('elite', 2), level=op.get('level', 90),
                        potential=op.get('potential', 6), trust=op.get('trust', 200),
                        is_token=op.get('is_token', False), cost=op.get('cost'))
        elif kind == 'retreat':
            self.retreat(op['target'])
        elif kind == 'skill':
            self.use_skill(op['target'])

    # ---------------- 轴执行（费用时钟，与打图执行器同语义） ----------------
    def cost_clock(self) -> tuple[int, int]:
        """当前（费用读数, 费用内帧偏移）。两者即轴表的同步锚点。"""
        return int(self.cost // 1), self.frame % FPS

    def run_axis(self, ops: list[dict], name_map: dict | None = None,
                 coord_transform: str = 'rc_normal', stop_on_error: bool = False,
                 max_frames: int | None = None, continue_after_fail: bool = False,
                 retry_on_cost: bool = False, retry_max_frames: int = 30 * 60,
                 schedule: list[int] | None = None, retry_on_sp: bool = False) -> list[dict]:
        """按 (cost, foff) 锚点执行轴表操作；返回实际触发记录（含绝对帧）。

        ops 元素：{cost, foff, op, unit, coord, dir, ...}
        name_map：干员名/简称 → charId（缺省时按 character_table 名称查找）
        continue_after_fail：战斗判定失败后仍继续跑完整轴（用于"轴 vs 模拟"机械比对）
        retry_on_cost：部署因费用不足失败时**不推进轴**，逐帧重试直到可部署
            （对应实际打图脚本「费用不足则该操作顺延到费用足够的那一帧」的行为；
             轴表的相对帧偏移对这类操作只是下界）
        schedule：可选的**逐条绝对帧计划**（如 axis.resolve_frames(timebase='abs-seconds') 的结果）。
            给出时，无费用锚点的操作改用它给出的绝对帧作为目标（而非"上一条 + foff"），
            与打图端 `axis_runner(timebase='abs-seconds')` 保持同语义。
        """
        # 轴表为【顺序】语义：每条要么给出费用锚点(cost,foff)，要么给出绝对帧/相对帧
        pending = [dict(o) for o in ops]
        fired: list[dict] = []
        retries: list[dict] = []
        limit = max_frames if max_frames is not None else self.max_frames
        pi = 0
        last_pi = -1
        wait_until_frame: int | None = None
        wait_start_frame = 0
        while self.frame < limit:
            if self.finished:
                if not continue_after_fail:
                    break
                # 轴比对模式：判负/胜后仍推进时间轴（冻结战场继续对轴）
                self.finished = False
                self.result = None
                self.life = max(self.life, 1)
            if pi >= len(pending):
                self.tick()
                continue
            o = pending[pi]
            if pi != last_pi:
                # 换到下一条操作：重置等待基准（重试时不重置，避免偏移漂移）
                foff0 = int(o.get('foff', 0) or 0)
                if o.get('cost') is not None:
                    wait_until_frame = None
                elif schedule is not None and pi < len(schedule):
                    wait_until_frame = int(schedule[pi])
                else:
                    wait_until_frame = self.frame + foff0
                wait_start_frame = self.frame
                last_pi = pi
            target_cost = o.get('cost')
            ready = False
            if target_cost is not None:
                cur_cost, cur_foff = self.cost_clock()
                if cur_cost > target_cost:
                    ready = True
                elif cur_cost == target_cost and cur_foff >= int(o.get('foff', 0)):
                    ready = True
            else:
                ready = self.frame >= (wait_until_frame or 0)
            if ready:
                cur_cost, cur_foff = self.cost_clock()
                rec = self._exec_axis_op(o, name_map, coord_transform)
                rec['frame'] = self.frame
                rec['cost_at'] = cur_cost
                rec['cost_ref'] = target_cost
                rec['foff'] = o.get('foff', 0)
                rec['abs_ref_frames'] = (o.get('raw') or {}).get('abs_frames')
                retry_reasons = ('cost', 'occupied', 'tile') + (('sp',) if retry_on_sp else ())
                if (not rec.get('ok')) and retry_on_cost and \
                        rec.get('reason') in retry_reasons \
                        and (self.frame - wait_start_frame) < retry_max_frames:
                    retries.append({'idx': pi, 'frame': self.frame, 'op': o.get('op'),
                                    'unit': o.get('unit'), 'reason': rec.get('reason')})
                    self.tick()
                    continue
                rec['wait_frames'] = self.frame - wait_start_frame
                fired.append(rec)
                pi += 1
                if stop_on_error and not rec.get('ok', True):
                    self.finished = True
                    self.result = 'AXIS_ERROR'
                    return fired
                continue
            self.tick()
        self.axis_retries = retries
        return fired

    def _exec_axis_op(self, o: dict, name_map: dict | None, coord_transform: str) -> dict:
        kind = o.get('op')
        unit_name = (o.get('unit') or '').strip()
        unit_name = (name_map or {}).get(unit_name, unit_name)
        if not unit_name and o.get('short'):
            unit_name = (name_map or {}).get(o['short'], o['short'])
        rec = {'op': kind, 'unit': unit_name, 'ok': False}
        if kind == 'deploy':
            coord = (o.get('coord') or '').strip()
            if not coord:
                rec['reason'] = 'no_coord'
                return rec
            from .axis import coord_to_rc
            r, c = coord_to_rc(coord, self.map.height, self.map.width, coord_transform)
            # 召唤物（token_*）需识别为 token 并绑定拥有者，否则召唤者技能的范围伤害不会触发
            is_tok = str(unit_name).startswith('token_')
            owner = self.token_owner_map.get(unit_name)
            u = self.deploy(unit_name, r, c, o.get('dir') or '右',
                            module=o.get('module'), module_level=o.get('module_level', 3),
                            skill_index=o.get('skill_index', 0), skill_level=o.get('skill_level', 10),
                            elite=o.get('elite', 2), level=o.get('level', 90),
                            potential=o.get('potential', 6), trust=o.get('trust', 200),
                            is_token=is_tok, token_owner=owner,
                            cost=o.get('cost_override'))
            rec['ok'] = u is not None
            if u is None and self.logs:
                last = self.logs[-1]
                if last.kind == 'deploy_failed':
                    rec['reason'] = last.detail.get('reason')
                    rec['need'] = last.detail.get('need')
                    rec['have'] = last.detail.get('have')
            rec['row'], rec['col'] = r, c
            rec['unit'] = unit_name
        elif kind == 'retreat':
            rec['ok'] = self.retreat(unit_name)
        elif kind == 'skill':
            rec['ok'] = self.use_skill(unit_name)
            if not rec['ok'] and self.logs:
                last = self.logs[-1]
                if last.kind in ('skill_reject',):
                    rec['reason'] = last.detail.get('reason')
                    rec['have'] = last.detail.get('have')
                    rec['need'] = last.detail.get('need')
            if not rec['ok'] and 'reason' not in rec:
                rec['reason'] = 'no_skill'
        else:
            rec['reason'] = 'unknown_op'
        return rec
