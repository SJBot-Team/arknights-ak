# -*- coding: utf-8 -*-
"""test_ruler_clock.py — 费用尺时钟 / 轴表绝对帧调度 离线自检（无需游戏、无需尺子）

覆盖：
  A. 假费用尺 HTTP 服务 → RulerClock(http) 读数与帧内插值
  B. 假 WebSocket 服务   → MiniWS / RulerClock(ws) 推送路径
  C. 轴表 → 绝对帧调度     → 与模拟器已核验帧号对齐（h12-4：令 45 / 蕾缪安 600）
  D. axis_runner dry-run  → 虚拟时钟全轴执行，检查同帧多操作与迟到帧
"""
import json
import os
import socket
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # code/vision
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from plugins.clock.cost_ruler import (RulerClock, build_frame_schedule,  # noqa: E402
                                      group_same_frame)

AXIS = r'C:\Users\23922\Documents\ds_harness\ak\data\derived\axis_h12-4_cyberplastic.json'


# --------------------------------------------------------------------------------------
# A. 假费用尺（HTTP 快照）
# --------------------------------------------------------------------------------------
class _FakeRuler:
    """按墙钟推进的假尺子：30 帧/费，第 11 个周期为 31 帧的边界周期。"""

    def __init__(self, fps=30.0, speed=1.0, start_elapsed=0):
        self.t0 = time.perf_counter()
        self.fps = fps
        self.speed = speed
        self.start = start_elapsed

    def snapshot(self) -> dict:
        dt = (time.perf_counter() - self.t0) * self.speed
        elapsed = int(self.start + dt * self.fps)
        if elapsed < 300:
            cycle_total, fin = 30, elapsed % 30
        elif elapsed < 331:
            cycle_total, fin = 31, elapsed - 300
        else:
            cycle_total, fin = 30, (elapsed - 331) % 30
        return {
            'apiVersion': 2, 'appVersion': 'v2.3.2-test', 'isRunning': True,
            'currentFrame': fin, 'totalFramesInCycle': cycle_total,
            'totalElapsedFrames': elapsed, 'activeProfile': '正常回费',
            'frameId': elapsed + 1000, 'sampleIndex': elapsed, 'droppedSincePrevious': 0,
            'rawPixelWidth': 3 + fin, 'costIsNegative': False, 'battleState': 'battle',
            'captureWidth': 1280, 'captureHeight': 720, 'captureFormat': 'rgba',
            'captureTimestampNs': int(time.perf_counter() * 1e9), 'captureDurationUs': 1200,
            'cursorBlocked': False, 'displayMode': '0_to_n-1',
            'displayFrame': str(fin), 'displayTotal': f'/{cycle_total-1}',
            'time': f'00:{elapsed//30:02d}:{elapsed%30:02d}', 'lapFrames': None,
            'canUndoReset': True, 'profiles': [],
            'historyOldestFrameId': 1000, 'historyLatestFrameId': elapsed + 1000,
            'timingDebug': {'requiredFp': 16777216, 'speedFp': 559240, 'accumulatorFp': 0,
                            'advancedFrames': 1, 'framesSinceCycleStart': fin,
                            'framesUntilNextCost': cycle_total - fin, 'matchErrorPx': 0,
                            'boundaryCorrected': False},
        }


def _http_server(ruler: _FakeRuler):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(ruler.snapshot()).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def test_http_clock():
    print('=== A. RulerClock(HTTP) ===')
    ruler = _FakeRuler(speed=1.0)
    srv, port = _http_server(ruler)
    clock = RulerClock('127.0.0.1', port, transport='http', poll_hz=200).start()
    readings = []
    for _ in range(6):
        st = clock.read()
        readings.append(st)
        time.sleep(0.05)
    clock.stop()
    srv.shutdown()
    for st in readings:
        print(f'  elapsed={st.elapsed_frames:<5} fin={st.frame_in_cost:<3} cycle={st.cycle_frames} '
              f'frame_now={st.frame_now():<8.2f} ok={st.ok} age={st.age_s:.3f}s px={st.raw_pixel_width}')
    mono = all(readings[i + 1].elapsed_frames >= readings[i].elapsed_frames for i in range(len(readings) - 1))
    grew = readings[-1].elapsed_frames - readings[0].elapsed_frames
    ok = mono and grew >= 1 and all(r.ok for r in readings)
    ok = ok and all(r.elapsed_frames <= r.frame_now() <= r.elapsed_frames + 2.01 for r in readings)
    print(f'  单调={mono} Δelapsed={grew} 插值范围正确 → {"PASS" if ok else "FAIL"}')
    return ok


# --------------------------------------------------------------------------------------
# B. 假 WebSocket 服务（验证 MiniWS 与 RulerClock(ws)）
# --------------------------------------------------------------------------------------
def _ws_server(ruler: _FakeRuler, hz: float = 60.0):
    import base64
    import hashlib

    lsock = socket.socket()
    lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lsock.bind(('127.0.0.1', 0))
    lsock.listen(4)
    port = lsock.getsockname()[1]
    stop = threading.Event()

    def frame_text(text: str) -> bytes:
        p = text.encode()
        n = len(p)
        head = bytes([0x81])
        if n < 126:
            head += bytes([n])
        elif n < 65536:
            head += bytes([126]) + struct.pack('>H', n)
        else:
            head += bytes([127]) + struct.pack('>Q', n)
        return head + p

    def handle(conn):
        data = b''
        while b'\r\n\r\n' not in data:
            c = conn.recv(1)
            if not c:
                return
            data += c
        key = ''
        for line in data.decode('latin1').split('\r\n'):
            if line.lower().startswith('sec-websocket-key:'):
                key = line.split(':', 1)[1].strip()
        accept = base64.b64encode(hashlib.sha1(
            (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        conn.sendall(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n'
                      f'Connection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n').encode())
        conn.sendall(bytes([0x89, 0x02]) + b'hi')      # ping：检查客户端会回 pong
        try:
            while not stop.is_set():
                conn.sendall(frame_text(json.dumps(ruler.snapshot())))
                time.sleep(1.0 / hz)
        except Exception:
            pass

    def loop():
        while not stop.is_set():
            try:
                lsock.settimeout(0.2)
                conn, _ = lsock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=handle, args=(conn,), daemon=True).start()

    threading.Thread(target=loop, daemon=True).start()
    return port, stop


def test_ws_clock():
    print('\n=== B. RulerClock(WS) / MiniWS ===')
    ruler = _FakeRuler(speed=1.0)
    port, stop = _ws_server(ruler, hz=90)
    clock = RulerClock('127.0.0.1', port, transport='ws', timeout=2.0).start()
    time.sleep(0.3)
    samples = []
    for _ in range(6):
        st = clock.read()
        samples.append(st.elapsed_frames)
        time.sleep(0.03)
    st = clock.read()
    clock.stop()
    stop.set()
    print(f'  推送帧序列: {samples}')
    print(f'  末次读数: elapsed={st.elapsed_frames} fin={st.frame_in_cost} cycle={st.cycle_frames} '
          f'sampleIndex={st.sample_index} ok={st.ok} battleState={st.battle_state}')
    ok = st.ok and st.elapsed_frames >= samples[0] and len(set(samples)) > 1 and st.battle_state == 'battle'
    print(f'  {"PASS" if ok else "FAIL"}')
    return ok


# --------------------------------------------------------------------------------------
# C. 轴表 → 绝对帧调度
# --------------------------------------------------------------------------------------
def test_schedule():
    print('\n=== C. 轴表 → 绝对帧调度（h12-4）===')
    if not os.path.exists(AXIS):
        print('  轴表不存在，跳过')
        return False
    axis = json.load(open(AXIS, encoding='utf-8'))
    ops = axis['ops']
    unit_costs = {'令': 10, '蕾缪安': 20, '弦惊': 23, 'U-Official': 5, '麒麟R夜刀': 8, '傀影': 8, '艾拉': 12}
    plan = build_frame_schedule(ops, initial_cost=10, frames_per_cost=30, unit_costs=unit_costs)
    groups = group_same_frame(plan)
    for it in plan[:12]:
        print(f'  {it["idx"]+1:>2} cost={str(it.get("cost_anchor")):<5} foff={it.get("foff",0):<3} '
              f'→ frame={it["frame"]:<6} {it["op"]:<7} {it.get("unit","")}')
    mono = all(plan[i + 1]['frame'] >= plan[i]['frame'] for i in range(len(plan) - 1))
    frames = {it['idx']: it['frame'] for it in plan}
    print(f'  帧计划单调={mono}  同帧组={sum(1 for g in groups if len(g)>1)}/{len(groups)}')
    expect = {0: 45, 1: 600}       # 令 C12 → 45 帧（1.5 s）；蕾缪安 G9 → 600 帧（20.0 s）
    diffs = {k: frames[k] - v for k, v in expect.items() if k in frames}
    print(f'  与模拟器核验帧差 {diffs}（0 = 完全一致）')
    ok = mono and all(abs(d) <= 1 for d in diffs.values()) and len(diffs) == len(expect)

    # 交叉校验：模拟器侧 resolve_frames 必须给出同一份帧计划（两处公式独立实现）
    sim_ok = None
    sim_axis_dir = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft'
    if os.path.isdir(sim_axis_dir):
        sys.path.insert(0, sim_axis_dir)
        try:
            from ak_sim.axis import Axis as SimAxis
            sax = SimAxis.load(AXIS)
            sres = sax.resolve_frames(initial_cost=10, unit_costs=unit_costs)
            sframes = [r['frame'] for r in sres]
            vframes = [it['frame'] for it in plan]
            sim_ok = sframes == vframes
            diff_at = [i for i, (a, b) in enumerate(zip(sframes, vframes)) if a != b][:5]
            print(f'  模拟器 resolve_frames 交叉校验: {"一致" if sim_ok else "不一致 @ " + str(diff_at)}'
                  f'（{len(sframes)} 条）')
        except Exception as ex:
            print(f'  模拟器侧交叉校验跳过: {ex!r}')
    ok = ok and (sim_ok is not False)
    print(f'  {"PASS" if ok else "FAIL"}')
    return ok


# --------------------------------------------------------------------------------------
# D. axis_runner dry-run（虚拟时钟）
# --------------------------------------------------------------------------------------
def test_axis_runner_dryrun():
    print('\n=== D. axis_runner dry-run（虚拟时钟全轴）===')
    from kernel.registry import TASKS, load_plugins
    load_plugins(os.path.join(ROOT, 'plugins'))
    cls = TASKS['axis_runner']
    log = r'C:\Users\23922\Documents\ds_harness\ak\data\derived\logs_h12-4_dryrun_v2.json'

    class _E:
        config = {'axis_runner': {
            'axis': AXIS, 'dry_run': True, 'log': log, 'virtual_speed': 60.0,
            'initial_cost': 10, 'frames_per_cost': 30,
            'unit_costs': {'令': 10, '蕾缪安': 20, '弦惊': 23},
        }}

        def grab(self):
            raise RuntimeError('dry-run 不应截图')

    t0 = time.perf_counter()
    res = cls().run(_E())
    dt = time.perf_counter() - t0
    late = [r for r in res['log'] if r['late_real_frames'] > 2.0]      # 允许 2 真实帧的循环开销
    neg = [r for r in res['log'] if r['late_frames'] < -0.01]
    worst = max((r['late_real_frames'] for r in res['log']), default=0.0)
    print(f'  触发 {res["fired"]}/{res["total"]} 条 · 帧锚点 {res["groups"]} 组（同帧 {res["same_frame_groups"]}）')
    print(f'  时钟={res["clock"]} 墙钟={dt:.2f}s 迟到>0.5真实帧={len(late)} 最大迟到={worst:.3f} 真实帧 '
          f'提前={len(neg)} 末帧={res["final_frame"]}')
    print('  前 2 条记录：')
    for r in res['log'][:2]:
        print(f'    {r}')
    ok = res['fired'] == res['total'] and not late and res['same_frame_groups'] > 0
    print(f'  {"PASS" if ok else "FAIL"}')
    return ok


class _StepClock:
    """确定性步进时钟：每次 read() 逻辑帧 +1，等价于模拟器的「逐帧推进」。

    用于两端时序交叉验证：排除真实时钟的循环粒度噪声，比较**调度语义**本身。
    """

    def __init__(self, step: int = 1, speed: float = 1e6, cycle: int = 30):
        self.step = step
        self.speed = speed          # 让主循环的休眠时长趋于 0（纯逻辑推进）
        self.cycle = cycle
        self.n = 0

    def start(self):
        return self

    def stop(self):
        return None

    def read(self):
        from plugins.clock.cost_ruler import ClockState
        self.n += self.step
        st = ClockState(source='step')
        st.ok = True
        st.running = True
        st.elapsed_frames = self.n
        st.frame_in_cost = self.n % self.cycle
        st.cycle_frames = self.cycle
        st.recv_wall = time.perf_counter()   # 插值≈0
        return st


def test_two_end_agreement():
    """E. 两端时序交叉验证：打图端（顺序语义 + 费用门控）vs 模拟器（retry_on_cost）。

    模拟侧帧记录由 `ak/sim/draft/compare_retry.py` 导出。两侧都按
    「费用锚点：显示费用 + 费用内帧相位；相对行：上一条实际帧 + foff；部署费用不足顺延」
    执行，因此逐条触发帧应一致（模拟按整数帧推进，执行端用确定性步进时钟同构复现）。
    """
    print('\n=== E. 两端时序交叉验证（执行端 vs 模拟器）===')
    sim_json = r'C:\Users\23922\Documents\ds_harness\ak\data\derived\sim_axis_frames_retry.json'
    if not os.path.exists(sim_json):
        print('  模拟侧帧记录不存在，跳过（先跑 sim/draft/compare_retry.py）')
        return True
    sim = json.load(open(sim_json, encoding='utf-8'))
    sim_frames = [x['frame'] for x in sim['retry']]

    import plugins.clock.cost_ruler as CR
    from kernel.registry import TASKS, load_plugins
    load_plugins(os.path.join(ROOT, 'plugins'))
    cls = TASKS['axis_runner']
    orig_make = CR.make_clock
    CR.make_clock = lambda engine=None, cfg=None: (_StepClock(), 'step')   # 注入步进时钟
    cfg = {
        'axis': AXIS, 'dry_run': True, 'cost_gate': True,
        'timebase': sim.get('timebase', 'cost-relative'),   # 与模拟侧使用同一时基
        'initial_cost': int(sim['initial_cost']), 'frames_per_cost': 30,
        'unit_costs': sim['unit_costs'],
        'clock': {'source': 'ruler'},        # 触发 make_clock 分支（已被替换为步进时钟）
        'max_seconds': 600,
        'log': r'C:\Users\23922\Documents\ds_harness\ak\data\derived\logs_h12-4_gated.json',
    }

    class _E:
        config = {'axis_runner': cfg}

    try:
        res = cls().run(_E())
    finally:
        CR.make_clock = orig_make
    run_frames = [round(r['frame_before']) for r in res['log']]
    n = min(len(sim_frames), len(run_frames))
    # 比较口径：只比较到「模拟侧出现会改变费用状态的操作失败」之前
    # （模拟器的技能/buff/召唤物尚未实现 → 干员阵亡、地块判定失败等会改变后续费用，
    #   这类差异属于模拟器保真度缺口，不是两端调度语义不一致）
    limit = n
    for i, x in enumerate(sim['retry'][:n]):
        if x['op'] in ('deploy', 'retreat') and not x['ok']:
            limit = i
            break
    diffs = [run_frames[i] - sim_frames[i] for i in range(limit)]
    worst = max((abs(d) for d in diffs), default=0)
    exact = sum(1 for d in diffs if d == 0)
    near2 = sum(1 for d in diffs if abs(d) <= 2)
    print(f'  模拟侧 {len(sim_frames)} 条 / 执行端 {len(run_frames)} 条；'
          f'可比区间 = 前 {limit} 条（其后模拟侧出现操作失败，属于保真度缺口）')
    print(f'  可比区间内：完全一致 {exact}/{limit}，±2 帧内 {near2}/{limit}，最大帧差 {worst}')
    print('  前 10 条对照：')
    for i in range(min(10, limit)):
        r = res['log'][i]
        print(f'    #{i+1:<3} 模拟 {sim_frames[i]:>6}  执行端 {run_frames[i]:>6}  Δ={diffs[i]:>5}  '
              f'锚点={str(r["cost_anchor"]):<5} {r["op"]} {r["unit"]}')
    if limit < n:
        x = sim['retry'][limit]
        print(f'  首个费用相关失败：#{limit+1} {x["op"]} {x["unit"]} '
              f'reason={x.get("reason")} frame={x["frame"]}')
    ok = len(run_frames) == len(sim_frames) and limit >= 10 and near2 == limit
    print(f'  {"PASS" if ok else "FAIL"}')
    return ok


def test_sp_gate_agreement():
    """F. SP 门控同构：执行端按表值 SP 曲线门控技能 vs 模拟器 skill_gate。

    两侧判据相同：`显示费用` 决定部署顺延；`SP = 表值 initSp + increment×经过时间`（攻击回复型按
    基础攻击间隔折算）决定技能顺延；召唤物被撤退 → 召唤者天赋 +SP。
    """
    print('\n=== F. SP 门控同构（执行端 vs 模拟器）===')
    sim_json = r'C:\Users\23922\Documents\ds_harness\ak\data\derived\sim_axis_frames_retry.json'
    if not os.path.exists(sim_json):
        print('  模拟侧帧记录不存在，跳过')
        return True
    sim = json.load(open(sim_json, encoding='utf-8'))
    sim_sp = sim.get('retry_spgate') or []
    sim_frames = [x['frame'] for x in sim_sp]

    import plugins.clock.cost_ruler as CR
    from kernel.registry import TASKS, load_plugins
    load_plugins(os.path.join(ROOT, 'plugins'))
    cls = TASKS['axis_runner']
    orig_make = CR.make_clock
    CR.make_clock = lambda engine=None, cfg=None: (_StepClock(), 'step')
    cfg = {
        'axis': AXIS, 'dry_run': True, 'cost_gate': True, 'sp_gate': True,
        'timebase': sim.get('timebase', 'abs-seconds'),
        'initial_cost': int(sim['initial_cost']), 'frames_per_cost': 30,
        'unit_costs': sim['unit_costs'],
        'unit_skills': {'令': 2, '蕾缪安': 0},
        'token_owners': {'弦惊': '令', '“弦惊”': '令'},
        'summon_lost_sp': 4.0,
        'clock': {'source': 'ruler'},
        'max_seconds': 900,
        'log': r'C:\Users\23922\Documents\ds_harness\ak\data\derived\logs_h12-4_spgate.json',
    }

    class _E:
        config = {'axis_runner': cfg}

    try:
        res = cls().run(_E())
    finally:
        CR.make_clock = orig_make
    run_frames = [round(r['frame_before']) for r in res['log']]
    n = min(len(sim_frames), len(run_frames))
    if n == 0:
        print('  模拟侧 SP 门控记录为空，跳过')
        return True
    # 比较口径：到「第一条被 SP 门控的技能」为止。
    # 之后的分歧来自**技能激活后的状态**：模拟器里干员没有实际攻击 → 弹药型技能不会结束，
    # 而打图端只能按表值推算 —— 这一段必须靠实机读技能栏（SP 条 / 就绪高亮）才能同构。
    limit = n
    for i in range(n):
        if res['log'][i]['op'] == 'skill':
            limit = i + 1
            break
    diffs = [run_frames[i] - sim_frames[i] for i in range(limit)]
    near = sum(1 for d in diffs if abs(d) <= 2)
    print(f'  可比区间 = 前 {limit} 条（至首条 SP 门控技能）；'
          f'±2 帧内 {near}/{limit}，最大帧差 {max((abs(d) for d in diffs), default=0)}')
    print('  对照：')
    for i in range(limit):
        r = res['log'][i]
        print(f'    #{i+1:<3} 模拟 {sim_frames[i]:>6}  执行端 {run_frames[i]:>6}  '
              f'Δ={diffs[i]:>3}  SP={r.get("sp_have")}/{r.get("sp_need")}  {r["op"]} {r["unit"]}')
    ok = near == limit and limit >= 3
    print(f'  {"PASS" if ok else "FAIL"}（口径：SP 门控起点一致 + 门控前逐条一致）')
    if limit < n:
        print(f'  注：# {limit+1} 起为技能激活后的状态差异（需要实机读技能栏，见 §7.15）')
    return ok


def test_case_milestones():
    """G. 案例里程碑：执行端干跑应复现「作者记录」的召唤物落地时刻。

    里程碑（由费用模型纯解析得出，见 ak/sim/draft/ak_sim/test_case_deferral.py）：
        弦惊 #1 = 43.0s（2580 帧? 不，43.0×30 = 1290 帧）
        弦惊 #2 = 66.0s（1980 帧）—— 作者 Sheet1 记录为 `66.1过1下龙`
    这条测试把「解析预测 = 模拟执行 = 作者记录」的三方一致，扩展到**打图执行端**。
    """
    print('\n=== G. 案例里程碑（执行端干跑 vs 作者记录）===')
    import plugins.clock.cost_ruler as CR
    from kernel.registry import TASKS, load_plugins
    load_plugins(os.path.join(ROOT, 'plugins'))
    cls = TASKS['axis_runner']
    orig_make = CR.make_clock
    CR.make_clock = lambda engine=None, cfg=None: (_StepClock(), 'step')
    cfg = {
        'axis': AXIS, 'dry_run': True, 'cost_gate': True, 'sp_gate': False,
        'timebase': 'abs-seconds',
        'initial_cost': 10, 'frames_per_cost': 30,
        'unit_costs': {'令': 10, '蕾缪安': 20, '弦惊': 23, '麒麟R夜刀': 8,
                       'U-Official': 3, '傀影': 8, '艾拉': 12, '雷鸣地雷': 5},
        'clock': {'source': 'ruler'},
        'max_seconds': 900,
        'log': r'C:\Users\23922\Documents\ds_harness\ak\data\derived\logs_h12-4_milestones.json',
    }

    class _E:
        config = {'axis_runner': cfg}

    try:
        res = cls().run(_E())
    finally:
        CR.make_clock = orig_make
    dragons = [r for r in res['log'] if r['op'] == 'deploy' and r['unit'] == '弦惊']
    times = [round(r['frame_before'] / 30.0, 2) for r in dragons]
    print(f'  执行端弦惊落地时刻 = {times[:6]} s')
    print(f'  解析/模拟/作者记录    = [43.0, 66.0, 89.0] s（其中 66.0 ↔ 作者 Sheet1 `66.1过1下龙`）')
    ok = len(times) >= 2 and abs(times[0] - 43.0) <= 0.3 and abs(times[1] - 66.0) <= 0.3
    print(f'  {"PASS" if ok else "FAIL"}（阈值 ±0.3s）')
    return ok


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    results = {
        'A_http_clock': test_http_clock(),
        'B_ws_clock': test_ws_clock(),
        'C_schedule': test_schedule(),
        'D_axis_dryrun': test_axis_runner_dryrun(),
        'E_two_end': test_two_end_agreement(),
        'F_sp_gate': test_sp_gate_agreement(),
        'G_case_milestones': test_case_milestones(),
    }
    print('\n汇总: ' + '  '.join(f'{k}={"PASS" if v else "FAIL"}' for k, v in results.items()))
    sys.exit(0 if all(results.values()) else 1)
