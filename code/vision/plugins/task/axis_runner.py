# -*- coding: utf-8 -*-
"""轴执行器任务（task: axis_runner）v2 —— 逻辑帧时钟驱动的共用轴表执行

与模拟器共用同一份轴表（ak/sim/draft/ak_sim/axis.py 产出，锚点=费用+费用内帧）。
执行端只做「读时钟 → 注入操作」，不读写游戏文件、不访问进程内存（GUI/ADB 级）。

v2 相对 v1 的变化
-----------------
1. **时钟抽象**：不再自带费用条循环计数，改用 plugins/clock/cost_ruler.py
   - ruler   ：费用尺本机 API（最精确，含 totalElapsedFrames 绝对帧 + 丢帧诊断）
   - cost_bar：自研识别器兜底
   - virtual ：dry-run / 单元测试用的虚拟时钟（按实时 30fps 或加速倍率推进）
2. **绝对帧调度**：轴表先经 build_frame_schedule 换算成绝对逻辑帧：
   绝对帧 = (显示费用 − 初始费用 + 累计已消耗) × 每费帧数 + 费用内帧，
   绕开「费用条满后绝对时间列不可靠」的问题（赛博塑料使用须知第三条）。
3. **同帧多操作**：同一绝对帧的操作成组，组内顺序执行且不再重复读时钟。
4. **执行诊断**：每条操作记录目标帧 / 实际帧 / 迟到帧数 / 时钟源 / 读数年龄，
   可直接与模拟器逐帧切片比对。

配置（engine.config['axis_runner']）：
  axis            轴表 JSON
  clock           {source:'auto'|'ruler'|'cost_bar'|'virtual', host, port, transport, poll_hz, stale_s}
  initial_cost    关卡初始费用（默认 10）
  frames_per_cost 每费帧数（默认 30）
  unit_costs      单位→部署费用（用于消耗记账）
  spent_of        单位→实际扣费（覆盖 unit_costs）
  frame_offset    时钟帧 → 轴表帧 的偏移（默认 0）
  wait_battle     true=等到时钟 running 才开始执行
  dry_run         true=不注入任何输入（默认 true，安全）
  grid/battle_area/coord_transform/unit_slots/ui/wait1..3  同 v1
  loop_hz         主循环频率（默认 240，>60 才能捕捉同帧窗口）
  max_seconds     最长运行时间
  log             执行记录输出路径
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from kernel.registry import task

FPS_DEFAULT = 30
FPS = FPS_DEFAULT
FRAME_S = 1.0 / FPS_DEFAULT


# --------------------------------------------------------------------------------------
# 虚拟时钟（dry-run / 测试）
# --------------------------------------------------------------------------------------
class VirtualClock:
    """按墙钟推进的虚拟逻辑帧时钟；speed>1 可加速测试。"""

    def __init__(self, speed: float = 1.0, start_frame: int = 0, frames_per_cost: int = 30):
        self.speed = float(speed)
        self.cycle = int(frames_per_cost)
        self._t0 = time.perf_counter()
        self._start = int(start_frame)

    def start(self):
        self._t0 = time.perf_counter()
        return self

    def stop(self):
        return None

    def read(self):
        from plugins.clock.cost_ruler import ClockState
        st = ClockState(source='virtual')
        st.recv_wall = time.perf_counter()
        # 浮点累计帧：虚拟时钟可以比真实时钟更细，便于验证亚帧调度
        st.elapsed_frames = self._start + (st.recv_wall - self._t0) * FPS_DEFAULT * self.speed
        st.frame_in_cost = int(st.elapsed_frames) % self.cycle
        st.cycle_frames = self.cycle
        st.running = True
        st.ok = True
        return st


# --------------------------------------------------------------------------------------
# 坐标/朝向工具
# --------------------------------------------------------------------------------------
def _tile_to_point(cfg: dict, row: int, col: int) -> tuple[int, int]:
    ba = cfg['battle_area']
    g = cfg['grid']
    rows, cols = g['rows'], g['cols']
    r = row if g.get('row_from', 'bottom') == 'bottom' else (rows - 1 - row)
    c = col if g.get('col_from', 'left') == 'left' else (cols - 1 - col)
    x = ba['left'] + (c + 0.5) * (ba['right'] - ba['left']) / cols
    y = ba['top'] + (r + 0.5) * (ba['bottom'] - ba['top']) / rows
    return int(x), int(y)


def _dir_vector(direction: str) -> tuple[int, int]:
    return {'右': (1, 0), '左': (-1, 0), '上': (0, -1), '下': (0, 1),
            'RIGHT': (1, 0), 'LEFT': (-1, 0), 'UP': (0, -1), 'DOWN': (0, 1)}.get(direction, (1, 0))


def _tile_point(cfg, row, col):
    return _tile_to_point(cfg, row, col)


def _time_begin_period(ms: int = 1):
    """Windows：把系统定时器精度提到 1 ms，否则 time.sleep 粒度可达 15.6 ms（对轴致命）。"""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        ctypes.windll.winmm.timeBeginPeriod(ms)
        return True
    except Exception:
        return False


def _time_end_period(active: bool) -> None:
    if not active:
        return
    try:
        import ctypes
        ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass


@task("axis_runner")
class AxisRunner:
    def run(self, engine) -> dict:
        cfg = (engine.config or {}).get('axis_runner', {}) if engine is not None else {}
        axis_path = cfg.get('axis')
        if not axis_path or not os.path.exists(axis_path):
            return {'ok': False, 'error': f'axis not found: {axis_path}'}
        with open(axis_path, encoding='utf-8') as f:
            axis = json.load(f)
        ops = axis.get('ops', [])
        dry = bool(cfg.get('dry_run', True))

        # ---- 轴表 → 绝对帧计划 ----
        from plugins.clock.cost_ruler import (build_frame_schedule, group_same_frame,
                                              anchor_ready, display_cost, ideal_anchor_frame)
        timebase = str(cfg.get('timebase', 'cost-relative'))
        plan = build_frame_schedule(ops,
                                    initial_cost=int(cfg.get('initial_cost', 10)),
                                    frames_per_cost=int(cfg.get('frames_per_cost', FPS_DEFAULT)),
                                    unit_costs=cfg.get('unit_costs') or {},
                                    spent_of=cfg.get('spent_of') or {},
                                    timebase=timebase)
        groups = group_same_frame(plan)
        multi = [g for g in groups if len(g) > 1]
        print(f'[axis_runner] 轴表 {os.path.basename(axis_path)}：{len(ops)} 条操作 / '
              f'{len(groups)} 个帧锚点（同帧多操作 {len(multi)} 组），timebase={axis.get("timebase", "cost")}')
        print(self._table(plan))

        # ---- 时钟 ----
        ccfg = dict(cfg.get('clock') or {})
        src = str(ccfg.get('source', 'auto'))
        if src == 'virtual' or (dry and src in ('auto', '')):
            # dry-run 且未指定真实时钟 → 虚拟时钟（无需游戏/尺子，可加速）
            clock = VirtualClock(speed=float(cfg.get('virtual_speed', 1.0)),
                                 frames_per_cost=int(cfg.get('frames_per_cost', FPS_DEFAULT)),
                                 start_frame=int(cfg.get('frame_offset', 0)))
            clock.start()
            clock_src = 'virtual'
        else:
            from plugins.clock.cost_ruler import make_clock
            clock, clock_src = make_clock(engine, ccfg)
        off = int(cfg.get('frame_offset', 0))

        backend = None
        if not dry:
            backend = engine.input
            if hasattr(backend, 'set_screen'):
                fr = engine.grab()
                backend.set_screen(fr.shape[1], fr.shape[0])

        # ---- 主循环 ----
        # 顺序语义（与模拟器 Battle.run_axis 完全一致）：
        #   * 费用锚点行 → 目标帧 = max(游标, 锚点推算帧)
        #   * 无锚点行   → 目标帧 = 游标 + foff（游标 = 上一条**实际**触发帧）
        #   * cost_gate  → 部署类操作在「估算显示费用 < 该单位费用」时**顺延**（对应实机脚本行为）
        fired: list[dict] = []
        idx = 0
        cursor = 0.0
        spent = 0.0                       # 净累计消耗（部署 +、撤退 50% 返还 −）
        init_cost = float(cfg.get('initial_cost', 10))
        fpc = float(cfg.get('frames_per_cost', FPS_DEFAULT))
        ucost = {k: float(v or 0) for k, v in (cfg.get('unit_costs') or {}).items()}
        ucost.update({k: float(v or 0) for k, v in (cfg.get('spent_of') or {}).items()})
        gate = bool(cfg.get('cost_gate', False))
        sp_gate = bool(cfg.get('sp_gate', False))          # 技能需 SP 足够（与模拟器同判据）
        unit_skills = {k: int(v) for k, v in (cfg.get('unit_skills') or {}).items()}
        sp_state: dict[str, dict] = {}                     # 单位 → {profile, t0, active}
        sp_defer = 0
        if sp_gate:
            try:
                from ak_sim_axis_compat import skill_sp_profile
                print('[axis_runner] SP 门控已启用；技能参数：'
                      + ', '.join(f'{u}#{i}' for u, i in unit_skills.items()))
            except Exception as ex:
                print(f'[axis_runner] SP 门控不可用：{ex!r}')
                sp_gate = False
        # ---- ★同帧多操作：冻结控制器（"操作前先步进/暂停定位帧再执行"）----
        #   `same_frame_mode='freeze'` 时，同一目标帧的多条操作会在**一次冻结**内连续下发，
        #   保证它们确实落在同一游戏帧；`'sequential'`（默认）保持既有顺序语义。
        same_frame_mode = str(cfg.get('same_frame_mode', 'sequential'))
        freeze = None
        frozen_groups = 0
        frozen_ops = 0
        frozen_mismatch = 0
        if same_frame_mode == 'freeze':
            from plugins.clock.frame_lock import make_freeze
            freeze = make_freeze(engine, dict(cfg.get('freeze') or {}), dry)
            if freeze.errors:
                print(f'[axis_runner] ★冻结控制器不可用（{freeze.errors}）→ 回退顺序模式')
                freeze = None
                same_frame_mode = 'sequential'
            else:
                print(f'[axis_runner] ★同帧多操作：冻结模式（mode={freeze.mode}）')

        def _tgt_of(it, cur):
            """复刻循环里的目标帧推算（供"同目标帧分组"用，不改状态）。"""
            aa = it.get('cost_anchor')
            ff = int(it.get('foff', 0) or 0)
            if aa is None:
                if timebase in ('abs-seconds', 'hybrid'):
                    return max(cur, float(it['frame']))
                return cur + ff
            return float(ideal_anchor_frame(init_cost, spent, int(aa), ff, fpc))

        t_end = float(cfg.get('max_seconds', 600))
        t0 = time.perf_counter()
        wait_battle = bool(cfg.get('wait_battle', False))
        last = clock.read()
        sp = float(getattr(clock, 'speed', 1.0) or 1.0)
        clock_timeout = float(cfg.get('clock_timeout', 5.0))    # 时钟连续不可用多久就中止
        last_ok_wall = time.perf_counter() if last.ok else 0.0
        aborted = None
        gated_total = 0
        op_gated = False          # 当前这条是否被门控顺延过
        _tbp = _time_begin_period(1)          # Windows：把定时器精度提到 1 ms
        try:
            while idx < len(plan) and (time.perf_counter() - t0) < t_end:
                st = clock.read()
                if st.ok:
                    last = st
                    last_ok_wall = time.perf_counter()
                elif clock_src != 'virtual' and (time.perf_counter() - max(last_ok_wall, t0)) > clock_timeout:
                    aborted = (f'时钟 {clock_src} 连续 {clock_timeout:.0f}s 无有效读数'
                               f'（尺子未运行 / 费用条未识别）→ 中止，避免盲打')
                    break
                if wait_battle and not last.running:
                    time.sleep(1.0 / hz)
                    continue
                fnow = last.frame_now() - off
                item = plan[idx]
                fpc_i = max(1, int(fpc))
                e_int = int(last.elapsed_frames)
                disp = display_cost(e_int, init_cost, spent, fpc)
                dp_float = init_cost + e_int / max(1e-9, fpc) - spent     # 游戏内真实费用（浮点）
                u_unit = ucost.get(item.get('unit', ''), 0.0)
                need = u_unit if item.get('op') == 'deploy' else 0.0
                A = item.get('cost_anchor')
                foff_i = int(item.get('foff', 0) or 0)
                if A is None:
                    if timebase == 'abs-seconds' or timebase == 'hybrid':
                        # 绝对/混合时基：无费用锚点的行直接用表内绝对帧（与模拟端 schedule 同语义）
                        tgt = max(cursor, float(item['frame']))
                    else:
                        # 相对帧行：以「上一条实际触发帧」为基准（与模拟器 run_axis 同语义）
                        tgt = cursor + foff_i
                    ready = fnow + 1e-9 >= tgt
                else:
                    # 费用锚点行：与 PRTS+/模拟器同一判据（显示费用 + 费用内帧相位）
                    ready, disp, phase = anchor_ready(e_int, init_cost, spent, int(A), foff_i, fpc)
                    tgt = float(ideal_anchor_frame(init_cost, spent, int(A), foff_i, fpc))
                gated = False
                if ready and gate and need > 0 and dp_float + 1e-6 < need:
                    ready, gated = False, True       # 到点但费用不足 → 顺延（实机脚本行为）
                # ---- 技能 SP 门控（与模拟器 Battle.use_skill 同判据）----
                sp_info = None
                if ready and sp_gate and item.get('op') == 'skill':
                    from ak_sim_axis_compat import skill_sp_profile, sp_after
                    uname = item.get('unit', '')
                    mode = str(cfg.get('sp_gate_mode', 'analytic'))
                    if mode == 'image':
                        # 画面判据：点选干员 → 抓帧 → 读技能按钮（就绪/充能/激活）
                        ok_img, ex = self._skill_ready_image(engine, backend, cfg, item)
                        sp_info = {'sp': None, 'need': None, 'ready': ok_img,
                                   'why': ex.get('state') if ex else 'no_frame'}
                        if not ok_img:
                            ready = False
                    else:
                        st_ = sp_state.get(uname)
                    if st_ is None:
                        prof = skill_sp_profile(uname, unit_skills.get(uname, 0))
                        st_ = {'profile': prof, 't0': fnow, 'active': False}
                        sp_state[uname] = st_
                    prof = st_['profile']
                    if not prof:
                        sp_info = {'sp': None, 'need': None, 'ready': True}
                    elif (st_.get('active') and prof.get('duration', 0) > 0
                          and (fnow - st_['t0']) / FPS < prof['duration']):
                        # 技能仍在激活：游戏会忽略这次点击 → 与模拟器一致，**不阻塞**，照发并推进
                        sp_info = {'sp': 0.0, 'need': prof['cost'], 'ready': True,
                                   'why': 'active_ignored'}
                    else:
                        have = sp_after((fnow - st_['t0']) / FPS, prof)
                        ok_sp = have + 1e-6 >= prof['cost']
                        sp_info = {'sp': round(have, 2), 'need': prof['cost'],
                                   'ready': ok_sp, 'skill': prof.get('name')}
                        if not ok_sp:
                            ready = False
                if not ready:
                    if gated:
                        gated_total += 1
                    if sp_info and not sp_info.get('ready'):
                        sp_defer += 1
                    if gated or (sp_info and not sp_info.get('ready')):
                        op_gated = True          # 本条被门控顺延过 → 其"迟到量"不算精度损失
                else:
                    # ---- 触发（★支持"同帧多操作"：一次冻结内连续下发同一目标帧的操作）----
                    grp = [item]
                    if freeze is not None:
                        j = idx + 1
                        while j < len(plan) and abs(_tgt_of(plan[j], cursor) - tgt) < 0.5:
                            grp.append(plan[j])
                            j += 1
                    frozen = bool(freeze is not None and len(grp) >= 2)
                    fz = {'ok': True, 'mode': 'sim', 'paused_frame': float(tgt), 'steps': 0,
                          'note': '单条操作，未冻结'}
                    if frozen:
                        fz = freeze.freeze_at(tgt, clock, off)
                        if fz.get('ok'):
                            frozen_groups += 1
                        else:
                            frozen_mismatch += 1
                            print(f'[axis_runner] ★冻结失败：{fz.get("note")}'
                                  f' → 该组回退为顺序执行')
                            frozen, grp = False, [item]
                    gfid = None
                    if frozen:
                        gfid = f'f{int(round(tgt))}_{idx}'
                    for it_g in grp:
                        need_g = ucost.get(it_g.get('unit', ''), 0.0) \
                            if it_g.get('op') == 'deploy' else 0.0
                        f_before = fnow
                        rec = self._exec(engine, backend, cfg, it_g, dry)
                        now = time.perf_counter()
                        late = f_before - tgt
                        rec.update({
                            'idx': it_g['idx'], 'target_frame': int(round(tgt)),
                            'plan_frame': it_g.get('frame'),
                            'frame_before': round(f_before, 3), 'late_frames': round(late, 3),
                            'late_real_frames': round(late / sp, 3),
                            'cost_anchor': it_g.get('cost_anchor'),
                            'spent_before': round(spent, 3),
                            'dp_est': disp, 'need': need_g, 'cost_gate': gate,
                            'gated': bool(op_gated),
                            'gated_frames': round(f_before - float(it_g['frame']), 3) if gate else None,
                            'clock': clock_src, 'age_s': st.age_s, 'wall': round(now - t0, 4),
                            'sample_index': st.sample_index, 'dropped': st.dropped,
                            'raw_pixel_width': st.raw_pixel_width,
                            # ★同帧多操作的可审计字段
                            'group_id': gfid, 'group_size': len(grp), 'frozen': frozen,
                            'frozen_frame': fz.get('paused_frame') if frozen else None,
                            'frozen_mode': fz.get('mode') if frozen else None,
                            'frozen_steps': fz.get('steps') if frozen else None,
                        })
                        fired.append(rec)
                        if frozen:
                            frozen_ops += 1
                        # 记账（与模拟器同规则）：部署扣该单位费用，撤退返还 50%
                        if it_g.get('op') == 'deploy':
                            spent += need_g
                            # 部署即初始化该单位的 SP 计时（表值 initSp 由 sp_after 起步）
                            if sp_gate and it_g.get('unit'):
                                try:
                                    from ak_sim_axis_compat import skill_sp_profile
                                    prof = skill_sp_profile(it_g['unit'],
                                                            unit_skills.get(it_g['unit'], 0))
                                    if prof:
                                        sp_state[it_g['unit']] = {'profile': prof, 't0': fnow,
                                                                  'active': False}
                                except Exception:
                                    pass
                        elif it_g.get('op') == 'retreat':
                            spent -= (ucost.get(it_g.get('unit', ''), 0.0)
                                      * float(cfg.get('refund_ratio', 0.5)))
                            # 召唤物被撤退 → 召唤者天赋 +SP（令：+4 SP / 次）
                            owner = (cfg.get('token_owners') or {}).get(it_g.get('unit', ''))
                            if sp_gate and owner and owner in sp_state:
                                gain = float(cfg.get('summon_lost_sp', 4.0))
                                st_o = sp_state[owner]
                                st_o['t0'] -= (gain / max(1e-6, (st_o['profile'].get('inc') or 1.0))
                                               * FPS)
                        if it_g.get('op') == 'skill' and sp_gate \
                                and it_g.get('unit') in sp_state:
                            st_k = sp_state[it_g['unit']]
                            st_k['t0'], st_k['active'] = fnow, True
                        if sp_info and it_g is item:
                            rec['sp_have'] = sp_info.get('sp')
                            rec['sp_need'] = sp_info.get('need')
                            rec['skill_name'] = sp_info.get('skill')
                    if frozen:
                        rel = freeze.release()
                        if not rel.get('ok'):
                            print(f'[axis_runner] ★解冻失败：{rel.get("note")}')
                    cursor = f_before
                    idx += len(grp)
                    op_gated = False
                    continue
                # 分级休眠：远则粗睡，临近帧边界改用短睡保证亚帧到点精度
                remain = tgt - fnow
                if remain > 2.0:
                    time.sleep(min(0.02, (remain - 1.0) * FRAME_S / sp))
                elif remain > 0.0:
                    time.sleep(0.0005)
        finally:
            _time_end_period(_tbp)

        runtime = round(time.perf_counter() - t0, 3)
        result = {'ok': aborted is None, 'error': aborted, 'fired': len(fired), 'total': len(ops),
                  'groups': len(groups), 'same_frame_groups': len(multi),
                  'clock': clock_src, 'dry_run': dry, 'runtime_s': runtime,
                  'cost_gate': gate, 'gated_cycles': gated_total,
                  'same_frame_mode': same_frame_mode,
                  'frozen_groups': frozen_groups, 'frozen_ops': frozen_ops,
                  'frozen_mismatch': frozen_mismatch,
                  'final_frame': round(last.frame_now() - off, 3), 'log': fired}
        for c in (clock,):
            try:
                c.stop()
            except Exception:
                pass
        out = cfg.get('log')
        if out:
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=1)
            print(f'[axis_runner] 执行记录 → {out}')
        late = [r for r in fired if r.get('late_real_frames', 0) > 0.5 and not r.get('gated')]
        worst = max((r.get('late_real_frames', 0) for r in fired if not r.get('gated')), default=0.0)
        gated_n = sum(1 for r in fired if r.get('gated'))
        gated = [r for r in fired if (r.get('gated_frames') or 0) > 0.5]
        print(f'[axis_runner] 完成 {len(fired)}/{len(ops)} 条，时钟={clock_src}，'
              f'迟到>0.5 帧 {len(late)} 条（最大 {worst:.3f} 帧，已排除被门控顺延的 {gated_n} 条），耗时 {runtime}s'
              + (f'；费用门控顺延 {len(gated)} 条' if gate else '')
              + (f'；SP 门控顺延 {sp_defer} 次' if sp_gate else '')
              + (f'；中止：{aborted}' if aborted else ''))
        return result

    # ---------- 内部 ----------
    def _skill_ready_image(self, engine, backend, cfg, item: dict):
        """画面判据：点选干员 → 抓帧 → 用 `skill_ready` 识别器读技能按钮状态。

        返回 (ready, extra)。需要配置 `ui.skill_sp_roi`（技能按钮 ROI，相对或绝对像素）
        与 `ui.unit_points`/`last_point`（干员在场位置）；dry-run 或无截图能力时返回 (True, None)
        —— 即"不阻塞"，避免在无画面时误判。
        """
        if engine is None or backend is None or not hasattr(engine, 'grab'):
            return True, None
        roi_spec = (cfg.get('ui') or {}).get('skill_sp_roi')
        if not roi_spec:
            return True, None
        unit = item.get('unit', '')
        pt = (cfg.get('unit_points') or {}).get(unit) or cfg.get('last_point')
        try:
            if pt and hasattr(backend, 'click'):
                backend.click(*pt)
                time.sleep(float(cfg.get('wait1', 0.02)))
            fr = engine.grab()
            spec = dict(cfg.get('skill_sp') or {})
            spec.setdefault('mode', 'ready')
            from plugins.recognize.skill_ready import SkillReadyRecognizer
            ms = SkillReadyRecognizer().run(fr.image, spec, None, fr.origin)
            if not ms:
                return True, None
            ex = ms[0].extra
            return bool(ex.get('ready')), ex
        except Exception as ex:
            return True, {'error': repr(ex)}

    def _exec(self, engine, backend, cfg, o: dict, dry: bool) -> dict:
        kind = o.get('op')
        unit = o.get('unit', '')
        coord = o.get('coord', '')
        rec = {'op': kind, 'unit': unit, 'coord': coord, 'ok': True, 'dry': dry}
        if dry or backend is None:
            return rec
        try:
            if kind == 'deploy':
                slot = cfg.get('unit_slots', {}).get(unit)
                if slot is None:
                    rec.update({'ok': False, 'error': 'no unit slot'})
                    return rec
                backend.click(*slot)
                time.sleep(cfg.get('wait1', 0.02))
                pt = None
                if coord:
                    from ak_sim_axis_compat import coord_to_rc
                    g = cfg['grid']
                    d = cfg.get('coord_transform', 'rc_rowflip')
                    r, c = coord_to_rc(coord, g['rows'], g['cols'], d)
                    pt = _tile_point(cfg, r, c)
                else:
                    pt = cfg.get('last_point')
                if pt:
                    backend.click(*pt)
                    cfg['last_point'] = pt
                    time.sleep(cfg.get('wait2', 0.1))
                    dx, dy = _dir_vector(o.get('dir', '右'))
                    backend.drag(pt[0], pt[1], pt[0] + dx * 40, pt[1] + dy * 40, 0.1)
                    time.sleep(cfg.get('wait3', 0.3))
            elif kind == 'skill':
                pt = cfg.get('last_point') or cfg.get('unit_points', {}).get(unit)
                if pt:
                    backend.click(*pt)
                    time.sleep(cfg.get('wait1', 0.02))
                    sb = (cfg.get('ui') or {}).get('skill_button')
                    if sb:
                        backend.click(*sb)
            elif kind == 'retreat':
                pt = cfg.get('last_point') or cfg.get('unit_points', {}).get(unit)
                if pt:
                    backend.click(*pt)
                    time.sleep(cfg.get('wait1', 0.02))
                    rb = (cfg.get('ui') or {}).get('retreat_button')
                    if rb:
                        backend.click(*rb)
        except Exception as ex:
            rec.update({'ok': False, 'error': str(ex)})
        return rec

    def _table(self, plan: list[dict]) -> str:
        lines = ['  #   目标帧  费用锚 帧  操作      单位        坐标   朝向']
        for it in plan[:30]:
            lines.append(f'  {it["idx"]+1:<4} {it["frame"]:<7} {str(it.get("cost_anchor", "")):<6} '
                         f'{it.get("foff", 0):<3} {it.get("op", ""):<8} {it.get("unit", ""):<10} '
                         f'{it.get("coord", ""):<6} {it.get("dir", "")}')
        if len(plan) > 30:
            lines.append(f'  ...（共 {len(plan)} 条）')
        return '\n'.join(lines)
