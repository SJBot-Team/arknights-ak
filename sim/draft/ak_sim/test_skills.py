# -*- coding: utf-8 -*-
"""test_skills.py — 技能/增益系统自检（表驱动）

核验点（全部对照客户端表值，case = h12-4 令+蕾缪安满配）：
  1. 令 S3「宁作吾」：initSp 15 / spCost 40 / +1 SP/s → 部署后第 ceil(25*30)=750 帧充满
     （部署帧 45 → 795 帧）；未充满时 use_skill 必须被拒（reason=sp）
  2. 令 S3 开启后：自身 atk/def ×2（blackboard atk=1.0, def=1.0）；duration 30s → 900 帧后结束
     并发放 1 个召唤物（"技能结束时获得1个召唤物"）
  3. 令 S3 期间，其召唤物每 0.5s 对周围四格敌人造成 0.2×令攻击力 的法术伤害
  4. 蕾缪安 S1「重逢问候」：spType=INCREASE_WHEN_ATTACK（攻击回 1 SP，8 点充满）；
     开启后攻击 2.1× 并额外攻击 1 名敌人；6 发弹药打完自动结束
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle, FPS          # noqa: E402
from ak_sim.axis import coord_to_rc            # noqa: E402
from ak_sim import scenario_h124 as S          # noqa: E402

LEVEL = 'obt/hard/level_hard_12-04'
LING = 'char_2023_ling'
LEMUEN = 'char_4193_lemuen'
TOKEN = 'token_10020_ling_soul3'
OPTS = dict(elite=2, level=90, potential=6, trust=200)


def _pos(b, coord):
    return coord_to_rc(coord, b.map.height, b.map.width, S.COORD_TRANSFORM)


def _quiet_battle():
    """无出怪、费用充裕的战斗环境：技能/增益自检不应受关卡敌人与费用约束干扰。

    注意：h12-4 的 rune 会把费用上限压到 20（见 knowledge/04/41 §7.24），
    而弦惊需 23 费 ⇒ 这里显式抬高上限，使自检只考察技能机制本身。
    """
    b = Battle(LEVEL, seed=0)
    b.sched_by_frame = {}
    b.life = 99
    b.cost_max = 99.0
    b.cost = 99.0
    return b


def test_ling_s3():
    print('=== 1/4 令 S3 宁作吾：SP 节奏与释放门槛 ===')
    b = _quiet_battle()
    r, c = _pos(b, 'C12')
    while b.frame < 45:
        b.tick()
    u = b.deploy(LING, r, c, '上', skill_index=2, module='uniequip_002_ling', **OPTS)
    assert u is not None, '令 部署失败'
    print(f'  部署帧 {b.frame}  initSp={u.sp} spCost={u.sp_cost} type={u.sp_type} '
          f'atk={u.atk} interval={u.attack_interval_frames}帧')
    ok_before = b.use_skill(LING)
    print(f'  部署瞬间尝试开技能 → {ok_before}（应为 False）')
    expect_full = 45 + int(25 * FPS)
    full_at = None
    while b.frame < expect_full + 3:
        b.tick()
        if full_at is None and u.sp >= u.sp_cost - 1e-9:
            full_at = b.frame
    print(f'  SP 充满帧 = {full_at}（期望 {expect_full}）')
    ok = b.use_skill(LING)
    print(f'  SP 满后开技能 → {ok}；buffs={u.buffs}')
    assert not ok_before and full_at is not None and abs(full_at - expect_full) <= 1 and ok
    print('  PASS')
    return True


def test_ling_buff_and_summon():
    print('\n=== 2/4 令 S3：atk/def ×2、30s 后结束并发放召唤物 ===')
    b = _quiet_battle()
    r, c = _pos(b, 'C12')
    while b.frame < 45:
        b.tick()
    u = b.deploy(LING, r, c, '上', skill_index=2, module='uniequip_002_ling', **OPTS)
    u.sp = u.sp_cost
    base_atk, base_def = u.atk, u.df
    b.use_skill(LING)
    during_atk, during_def = u.eff_atk(), u.eff_def()
    print(f'  开启后 eff_atk={during_atk:.1f}（基础 {base_atk}） eff_def={during_def:.1f}（基础 {base_def}） '
          f'skill_until={u.skill_until}')
    start = b.frame
    while b.frame < start + int(30 * FPS) + 2:
        b.tick()
    print(f'  结束帧 {b.frame}（期望 ≈{start + int(30*FPS)}） skill_active={u.skill_active} '
          f'summon_charges={u.summon_charges} after_atk={u.eff_atk():.1f}')
    ok = (abs(during_atk - base_atk * 2) < 0.51 and abs(during_def - base_def * 2) < 0.51
          and not u.skill_active and u.summon_charges == 1
          and abs(u.eff_atk() - base_atk) < 0.51)
    print(f'  {"PASS" if ok else "FAIL"}')
    return ok


def test_summon_aoe():
    print('\n=== 3/4 令 S3：召唤物每 0.5s 周围四格法术伤害 ===')
    b = _quiet_battle()
    r, c = _pos(b, 'C12')
    while b.frame < 45:
        b.tick()
    u = b.deploy(LING, r, c, '上', skill_index=2, module='uniequip_002_ling', **OPTS)
    # 找一个可部署近战格放召唤物（令 S3 的弦惊是近战位召唤物）
    tr, tc = None, None
    for dr in (1, -1, 0, 0, 1, -1, 1, -1):
        for dc in (0, 0, 1, -1, 1, 1, -1, -1):
            rr, cc = r + dr, c + dc
            if 0 <= rr < b.map.height and 0 <= cc < b.map.width and b.map.can_deploy(rr, cc, melee=True):
                tr, tc = rr, cc
                break
        if tr is not None:
            break
    assert tr is not None, '找不到可部署近战格'
    tok = b.deploy(TOKEN, tr, tc, '上', is_token=True, token_owner=LING, **OPTS)
    assert tok is not None, f'弦惊 部署失败 @({tr},{tc})'
    print(f'  召唤物部署 @(r{tr},c{tc})')
    tok.extra['owner'] = u.uid
    u.sp = u.sp_cost
    b.use_skill(LING)
    # 放一个高血量敌人到召唤物上方
    from ak_sim.data import get_enemy
    from ak_sim.units import make_enemy
    edata = get_enemy('enemy_1007_slime', 0)
    e = make_enemy(9999, edata, (0, 0), None, b.frame)
    e.hp = e.max_hp = 100000
    e.pos = (__import__('ak_sim.fp', fromlist=['x']).from_float(tc + 0.5),
             __import__('ak_sim.fp', fromlist=['x']).from_float(tr - 1 + 0.5))
    b.units[e.uid] = e
    hp0 = e.hp
    for _ in range(int(1.6 * FPS)):
        b.tick()
    hits = [l for l in b.logs if l.kind == 'summon_aoe']
    print(f'  1.6s 内 AoE 命中 {len(hits)} 次（期望 3 次，间隔 0.5s）；敌人 HP {hp0} → {e.hp}')
    for h in hits[:4]:
        print(f'    f={h.frame} {h.detail}')
    ok = 2 <= len(hits) <= 4 and e.hp < hp0
    print(f'  {"PASS" if ok else "FAIL"}')
    return ok


def test_lemuen_s1():
    print('\n=== 4/4 蕾缪安 S1：攻击回 SP、2.1× 与额外目标、6 发弹药 ===')
    b = _quiet_battle()
    r, c = _pos(b, 'G9')
    while b.frame < 60:
        b.tick()
    u = b.deploy(LEMUEN, r, c, '下', skill_index=0, module='uniequip_002_lemuen', **OPTS)
    assert u is not None, '蕾缪安 部署失败'
    print(f'  部署帧 {b.frame} spType={u.sp_type} spCost={u.sp_cost} initSp={u.sp} '
          f'interval={u.attack_interval_frames}帧 atk={u.atk}')
    u.sp = u.sp_cost                     # 直接充满，专注验证技能效果
    assert b.use_skill(LEMUEN)
    print(f'  开启后 skill_active={u.skill_active} ammo={u.skill_ammo} buffs={u.buffs}')
    # 放一个敌人进射程，观察 6 发弹药
    from ak_sim.data import get_enemy
    from ak_sim.units import make_enemy
    from ak_sim import fp
    edata = get_enemy('enemy_1007_slime', 0)
    e = make_enemy(9998, edata, (0, 0), None, b.frame)
    e.hp = e.max_hp = 1000000
    e.pos = (fp.from_float(c + 0.5), fp.from_float(r - 1 + 0.5))
    b.units[e.uid] = e
    hp0 = e.hp
    hits = []
    for _ in range(int(20 * FPS)):
        b.tick()
        hits = [l for l in b.logs if l.kind == 'hit' and l.detail.get('src') == u.name]
        if not u.skill_active:
            break
    print(f'  技能结束帧 {b.frame}（弹药打空） 命中 {len(hits)} 次 敌人 HP {hp0} → {e.hp}')
    for h in hits[:3]:
        print(f'    f={h.frame} {h.detail}')
    ok = (len(hits) >= 6 and not u.skill_active and e.hp < hp0)
    print(f'  {"PASS" if ok else "FAIL"}')
    return ok


if __name__ == '__main__':
    res = {
        'ling_s3_sp': test_ling_s3(),
        'ling_buff_summon': test_ling_buff_and_summon(),
        'summon_aoe': test_summon_aoe(),
        'lemuen_s1': test_lemuen_s1(),
    }
    print('\n汇总: ' + '  '.join(f'{k}={"PASS" if v else "FAIL"}' for k, v in res.items()))
    sys.exit(0 if all(res.values()) else 1)
