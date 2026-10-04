# -*- coding: utf-8 -*-
"""逻辑帧时钟（clock）—— 打图端与模拟器对轴的时间基准

为什么需要它
------------
轴表（见 ak/sim/draft/ak_sim/axis.py）的锚点是「费用 + 费用内帧」，而**绝对时间列在费用条满/剿灭等
场景下不可靠**（赛博塑料使用须知第三条）。费用条本身永远在 0→1 循环，与费用消耗无关，因此
「费用条循环计数」是一个不受费用是否满、是否消耗影响的**绝对逻辑帧基准**。

本模块提供两种时钟源，输出统一的 ClockState（含帧内插值）：

  1. RulerClock  —— 费用尺 ArknightsCostBarRuler 的本机 API（127.0.0.1:2606）
       * HTTP  ``GET /``            当前快照（无依赖，轮询即可，localhost 延迟 ~ms）
       * WS    ``ws://…:2606/``     每个已分析帧主动推送；本模块内置纯 stdlib WS 客户端
       * 关键字段：totalElapsedFrames（战斗内累计逻辑帧，绝对）、currentFrame（费用内帧）、
         totalFramesInCycle（周期帧数，边界周期 N+1）、sampleIndex / droppedSincePrevious
         （截图管线是否丢帧）、captureTimestampNs、rawPixelWidth、cursorBlocked、
         timingDebug.advancedFrames（本帧逻辑推进了几帧）
       协议依据：ArknightsCostBarRuler docs/API.md（apiVersion=2）。

  2. CostBarClock —— 自研费用条识别器兜底（plugins/recognize/cost_bar.py）
       自己数周期回绕得到累计帧，精度受截图帧率限制，但零外部依赖。

帧内插值
--------
一次快照给出的是「某一逻辑帧」的状态，而操作发生在其后的任意时刻。因为逻辑帧固定按
1/30 s 推进，可以用 ``frame_now() = elapsed + (perf_counter - 收到快照的时刻) * 30``
把时钟推进到「现在」，从而做到亚帧级的到点判定与同帧多操作。插值上限 interp_cap
（默认 2 帧）防止尺子卡住时时钟无限外推。

合规：本模块只连本机 127.0.0.1 的回环端口 / 只读屏幕像素，不读写游戏文件、不访问进程内存。
"""
from __future__ import annotations

import base64
import json
import math
import os
import socket
import struct
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

FPS = 30.0                 # 明日方舟逻辑帧率
FRAME_S = 1.0 / FPS        # 单逻辑帧秒数


# --------------------------------------------------------------------------------------
# 时钟状态
# --------------------------------------------------------------------------------------
@dataclass
class ClockState:
    """某一时刻的逻辑帧时钟读数。"""
    source: str = 'none'
    ok: bool = False                     # 本帧读数是否有效
    elapsed_frames: int = 0              # 战斗内累计逻辑帧（绝对，来自尺子）
    frame_in_cost: int = 0               # 当前费用循环内的帧，0..cycle-1
    cycle_frames: int = 30               # 当前循环总帧数（边界周期为 N+1）
    running: bool = False                # 是否识别到有效费用条
    age_s: float = 0.0                   # 读数距现在多久（秒）
    dropped: int = 0                     # 与上一已分析帧之间被跳过的截图管线帧数
    sample_index: int = 0
    raw_pixel_width: int | None = None
    battle_state: str | None = None
    time_str: str = ''                   # 尺子格式化计时器 MM:SS:FF
    advanced_frames: int | None = None   # 本帧逻辑推进帧数（timingDebug）
    recv_wall: float = field(default=0.0, repr=False)

    def frame_now(self, interp_cap: float = 2.0) -> float:
        """插值到「现在」的绝对逻辑帧（浮点）。"""
        dt = max(0.0, time.perf_counter() - self.recv_wall)
        return self.elapsed_frames + min(dt * FPS, interp_cap)

    def cost_units(self) -> float:
        """自战斗开始累计自然回复的费用量（浮点，按当前循环帧数折算）。"""
        cf = self.cycle_frames or 30
        return self.elapsed_frames / float(cf)

    def as_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != 'recv_wall'}
        d['frame_now'] = round(self.frame_now(), 3)
        d['cost_units'] = round(self.cost_units(), 3)
        return d


# --------------------------------------------------------------------------------------
# 纯 stdlib WebSocket 客户端（服务器→客户端为明文帧；客户端→服务器需掩码）
# --------------------------------------------------------------------------------------
class MiniWS:
    """最小 WebSocket 客户端：够用即可（握手 + 文本帧收发 + ping/pong + close）。"""

    def __init__(self, host: str = '127.0.0.1', port: int = 2606, path: str = '/', timeout: float = 3.0):
        self.host, self.port, self.path = host, port, path
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self._buf = b''

    def connect(self) -> None:
        s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        s.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f'GET {self.path} HTTP/1.1\r\nHost: {self.host}:{self.port}\r\n'
               'Upgrade: websocket\r\nConnection: Upgrade\r\n'
               f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n')
        s.sendall(req.encode())
        head = b''
        while b'\r\n\r\n' not in head:
            chunk = s.recv(1)
            if not chunk:
                raise ConnectionError('WS 握手期间连接关闭')
            head += chunk
            if len(head) > 8192:
                raise ConnectionError('WS 握手响应过长')
        status = head.split(b'\r\n', 1)[0]
        if b'101' not in status:
            raise ConnectionError(f'WS 握手失败: {status!r}')
        self.sock = s
        self._buf = b''

    # ---- 底层帧 ----
    def _recv_exact(self, n: int) -> bytes:
        assert self.sock is not None
        while len(self._buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError('WS 连接关闭')
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        assert self.sock is not None
        head = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack('>H', n)
        else:
            head += bytes([0x80 | 127]) + struct.pack('>Q', n)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(head + mask + masked)

    def send_text(self, text: str) -> None:
        self._send_frame(0x1, text.encode('utf-8'))

    def recv_text(self) -> str | None:
        """读一条文本消息；ping 自动回 pong，close 返回 None，二进制/其余忽略后继续读。"""
        while True:
            b0, b1 = self._recv_exact(2)
            opcode = b0 & 0x0F
            masked = bool(b1 & 0x80)
            ln = b1 & 0x7F
            if ln == 126:
                ln = struct.unpack('>H', self._recv_exact(2))[0]
            elif ln == 127:
                ln = struct.unpack('>Q', self._recv_exact(8))[0]
            key = self._recv_exact(4) if masked else b''
            payload = self._recv_exact(ln) if ln else b''
            if masked:
                payload = bytes(b ^ key[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                return None
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0x1:
                return payload.decode('utf-8', 'replace')
            # 0x0 续帧 / 0xA pong / 0x2 二进制：忽略

    def close(self) -> None:
        if self.sock is not None:
            try:
                self._send_frame(0x8, b'')
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


# --------------------------------------------------------------------------------------
# 时钟源 1：费用尺
# --------------------------------------------------------------------------------------
class RulerClock:
    """费用尺时钟。transport='http'（轮询快照，零依赖）或 'ws'（推送，推荐）。"""

    def __init__(self, host: str = '127.0.0.1', port: int = 2606, transport: str = 'http',
                 poll_hz: float = 120.0, timeout: float = 1.0, stale_s: float = 2.0):
        self.host, self.port = host, port
        self.transport = transport
        self.poll_hz = poll_hz
        self.timeout = timeout
        self.stale_s = stale_s          # 超过该时长没有新快照 → ok=False（防用陈旧时钟打轴）
        self._lock = threading.Lock()
        self._snap: dict | None = None
        self._recv_wall = 0.0
        self._raw = 0
        self._err: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ---- 可用性 ----
    @staticmethod
    def probe(host: str = '127.0.0.1', port: int = 2606, timeout: float = 0.4) -> dict | None:
        """HTTP 探活：返回快照 dict 或 None。用于 auto 选源。"""
        try:
            with urllib.request.urlopen(f'http://{host}:{port}/', timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception:
            return None

    # ---- 生命周期 ----
    def start(self) -> 'RulerClock':
        if self.transport == 'ws':
            self._thread = threading.Thread(target=self._ws_loop, name='ruler-clock', daemon=True)
        else:
            self._thread = threading.Thread(target=self._http_loop, name='ruler-clock', daemon=True)
        self._thread.start()
        # 首帧：等一小会儿拿到读数
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < self.timeout and self._snap is None:
            time.sleep(0.005)
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _http_loop(self) -> None:
        period = 1.0 / max(1.0, self.poll_hz)
        while not self._stop.is_set():
            t0 = time.perf_counter()
            snap = self.probe(self.host, self.port, self.timeout)
            self._store(snap)
            time.sleep(max(0.0, period - (time.perf_counter() - t0)))

    def _ws_loop(self) -> None:
        while not self._stop.is_set():
            ws = None
            try:
                ws = MiniWS(self.host, self.port, '/', timeout=max(1.0, self.timeout))
                ws.connect()
                while not self._stop.is_set():
                    txt = ws.recv_text()
                    if txt is None:
                        break
                    try:
                        self._store(json.loads(txt))
                    except Exception:
                        pass
            except Exception as ex:
                with self._lock:
                    self._err = repr(ex)
                time.sleep(0.2)
            finally:
                if ws:
                    ws.close()

    def _store(self, snap: dict | None) -> None:
        with self._lock:
            if snap is None:
                self._err = 'no snapshot'
                return
            self._snap = snap
            self._recv_wall = time.perf_counter()
            self._raw += 1
            self._err = None

    # ---- 读取 ----
    def read(self) -> ClockState:
        with self._lock:
            snap, wall, err = self._snap, self._recv_wall, self._err
        st = ClockState(source=f'ruler:{self.transport}')
        if not snap:
            st.ok = False
            st.recv_wall = time.perf_counter()
            return st
        st.age_s = round(time.perf_counter() - wall, 4)
        st.recv_wall = wall
        st.elapsed_frames = int(snap.get('totalElapsedFrames') or 0)
        st.frame_in_cost = int(snap.get('currentFrame') or 0)
        st.cycle_frames = int(snap.get('totalFramesInCycle') or 30)
        st.running = bool(snap.get('isRunning'))
        st.dropped = int(snap.get('droppedSincePrevious') or 0)
        st.sample_index = int(snap.get('sampleIndex') or 0)
        st.raw_pixel_width = snap.get('rawPixelWidth')
        st.battle_state = snap.get('battleState')
        st.time_str = snap.get('time') or ''
        td = snap.get('timingDebug') or {}
        st.advanced_frames = td.get('advancedFrames')
        # 有效性：识别到费用条 + 读数没过期
        st.ok = bool(st.running and st.age_s <= self.stale_s)
        return st

    def command(self, **payload) -> dict | None:
        """下发一条控制命令（仅 WS 传输支持）。"""
        if self.transport != 'ws':
            return None
        ws = MiniWS(self.host, self.port, '/', timeout=self.timeout)
        try:
            ws.connect()
            payload.setdefault('requestId', f'r{int(time.time()*1000)}')
            ws.send_text(json.dumps(payload, ensure_ascii=False))
            # 读一条响应或一条推送快照
            for _ in range(4):
                txt = ws.recv_text()
                if txt is None:
                    break
                obj = json.loads(txt)
                if obj.get('type') in ('ack', 'error'):
                    return obj
            return None
        except Exception as ex:
            return {'type': 'error', 'code': 'transport', 'message': repr(ex)}
        finally:
            ws.close()


# --------------------------------------------------------------------------------------
# 时钟源 2：自研费用条识别器（兜底）
# --------------------------------------------------------------------------------------
class CostBarClock:
    """截图 + 费用条识别器兜底时钟：靠周期回绕累加绝对帧。"""

    def __init__(self, engine, spec: dict | None = None, stale_s: float = 2.0):
        self.engine = engine
        self.spec = dict(spec or {})
        self.stale_s = stale_s
        self._elapsed = 0
        self._prev_fin: int | None = None
        self._last_wall = 0.0
        self._last_fin = 0
        self._cycle = 30
        # ★战斗 HUD 门控（实机教训 2026-09-15）：在非战斗画面（如"任务失败/结算"）上，
        #   CostBarRecognizer 会把模糊背景读成"满条(frame=30/26)" ⇒ 污染绝对时间基准。
        #   故默认**要求确实在战斗中**；置 spec['require_battle']=False 可关闭（仅对照用）。
        self.require_battle = bool(self.spec.get('require_battle', True))
        self._gate = None
        self.gate_state: dict | None = None

    def start(self) -> 'CostBarClock':
        self.read()
        return self

    def stop(self) -> None:
        return None

    def read(self) -> ClockState:
        st = ClockState(source='cost_bar')
        try:
            fr = self.engine.grab()
            # ---- ★战斗 HUD 门控：不在战斗中直接拒绝读数（不推进、不回绕）----
            if self.require_battle:
                if self._gate is None:
                    from plugins.recognize.battle_hud import BattleHudGate
                    self._gate = BattleHudGate()
                self.gate_state = self._gate.check(fr.image)
                if not self.gate_state['in_battle']:
                    st.ok = False
                    st.elapsed_frames = self._elapsed
                    st.recv_wall = time.perf_counter()
                    try:
                        st.battle_state = False      # 门控：非战斗（详见 gate_state['reason']）
                    except Exception:                # noqa: BLE001
                        pass
                    return st
            from plugins.recognize.cost_bar import CostBarRecognizer
            ms = CostBarRecognizer().run(fr.image, self.spec, None, fr.origin)
        except Exception:
            ms = []
        if not ms:
            st.ok = False
            st.elapsed_frames = self._elapsed
            st.recv_wall = time.perf_counter()
            return st
        m = ms[0]
        fin = int(m.extra.get('frame', 0))
        self._cycle = int(m.extra.get('total_frames', self._cycle) or self._cycle)
        if self._prev_fin is not None and fin < self._prev_fin:
            self._elapsed += self._cycle
        self._prev_fin = fin
        self._last_fin = fin
        self._last_wall = time.perf_counter()
        st.ok = True
        st.elapsed_frames = self._elapsed
        st.frame_in_cost = fin
        st.cycle_frames = self._cycle
        st.running = True
        st.raw_pixel_width = m.extra.get('fill_px')
        st.recv_wall = self._last_wall
        # 兜底时钟无法插值（不知道自己落后多少），只给整数帧
        return st


# --------------------------------------------------------------------------------------
# 时钟源 3：画面上的「费用数字」（实机可用，无需外部尺子）
# --------------------------------------------------------------------------------------
class CostNumberClock:
    """从截图读右下角**费用数字**，配合调用方的消耗记账换算成绝对逻辑帧。

    原理（与案例验证过的费用模型一致）：
        显示费用 = 初始费用 + 自然回复量 − 净消耗
        ⇒ 自然回复量（秒）= 显示费用 − 初始费用 + 净消耗
        ⇒ 绝对帧 = 自然回复量 × 每费帧数（+ 收到读数后的墙钟插值，上限 1 帧）

    `spent` 由执行器在每次部署/撤退后回填（`set_spent`），因为脚本自己知道消耗了多少。
    首次成功读到费用数字的时刻被视为**战斗开始**（用作基准 0）。
    """

    def __init__(self, grab_fn, spec: dict | None = None, initial_cost: float = 10.0,
                 frames_per_cost: int = 30, stale_s: float = 2.0):
        self.grab = grab_fn
        self.spec = dict(spec or {})
        self.initial = float(initial_cost)
        self.fpc = int(frames_per_cost)
        self.stale_s = stale_s
        self.spent = 0.0
        self._t0_wall: float | None = None
        self._last = 0.0
        self._last_wall = 0.0
        self._running = False
        self._tpl = None
        self._err: str | None = None

    # ---- 供执行器回填 ----
    def set_spent(self, spent: float) -> None:
        self.spent = float(spent)

    def start(self):
        self.read()
        return self

    def stop(self):
        return None

    def _load_tpl(self):
        if self._tpl is None:
            p = self.spec.get('templates')
            self._tpl = load_templates(p) if p else {}
        return self._tpl

    def _read_number(self) -> int | None:
        from plugins.recognize.cost_number import CostNumberRecognizer
        fr = self.grab()
        ms = CostNumberRecognizer().run(fr.image, self.spec, None, fr.origin)
        if not ms:
            return None
        return ms[0].extra.get('cost')

    def read(self) -> ClockState:
        st = ClockState(source='cost_number')
        try:
            num = self._read_number()
        except Exception as ex:
            self._err = repr(ex)
            num = None
        now = time.perf_counter()
        if num is None:
            self._running = False
            st.ok = False
            st.elapsed_frames = self._last
            st.recv_wall = now
            return st
        if not self._running:                     # 首次读到 → 视为战斗开始
            self._running = True
            self._t0_wall = now
        elapsed = max(0.0, (float(num) - self.initial + self.spent)) * self.fpc
        elapsed = max(elapsed, self._last)        # 单调
        self._last, self._last_wall = elapsed, now
        st.ok = True
        st.running = True
        st.elapsed_frames = int(elapsed)
        st.frame_in_cost = int(elapsed) % self.fpc
        st.cycle_frames = self.fpc
        st.raw_pixel_width = num
        st.recv_wall = now
        return st
def make_clock(engine=None, cfg: dict | None = None):
    """按配置创建时钟。cfg: {source:'auto'|'ruler'|'cost_bar'|'cost_number'|'frame_clock', ...}

    source='frame_clock' 时走 `plugins.clock.frame_clock.FrameClock`（帧级融合时钟）：
    用法见 knowledge/04/41 §7.55 —— 它把「费用格+费用条相位（方法1）」「待部署十分位（方法2）」
    「墙钟×倍速（方法3）」按优先级融合，输出**绝对逻辑帧（±0 帧）**。
    cfg 需要给出：
        initial_cost / frames_per_cost / bar_roi（费用条 ROI，绝对像素或相对）
        cost_roi + templates（费用数字识别，用于取整数格）
        read_digits()（可选，方法2 的十分位读取器，由调用方注入）
        read_speed()/read_paused()（可选，方法3）
    """
    cfg = dict(cfg or {})
    src = str(cfg.get('source', 'auto')).lower()
    host = cfg.get('host', '127.0.0.1')
    port = int(cfg.get('port', 2606))
    if src == 'frame_clock':
        if engine is None:
            raise RuntimeError('frame_clock 需要 engine（截图+识别）')
        from plugins.clock.frame_clock import CostLatticeClock, FrameClock, RedeployTenthsClock, WallRateClock
        sources, order = [], []
        # 方法1：费用格 + 费用条相位
        num_spec = dict(cfg.get('cost_number') or {})
        num_spec.setdefault('roi', cfg.get('cost_roi'))
        num_spec.setdefault('templates', cfg.get('templates'))

        def _read_cost():
            from plugins.recognize.cost_number import CostNumberRecognizer
            fr = engine.grab()
            ms = CostNumberRecognizer().run(getattr(fr, 'image', fr), num_spec, None,
                                            getattr(fr, 'origin', (0, 0)))
            return int(ms[0].extra['cost']) if ms else None

        lattice = CostLatticeClock(engine.grab, _read_cost,
                                   {'initial_cost': float(cfg.get('initial_cost', 10)),
                                    'frames_per_cost': int(cfg.get('frames_per_cost', 30)),
                                    'bar_roi': cfg.get('bar_roi'),
                                    'thr_ratio': float(cfg.get('thr_ratio', 0.55)),
                                    'full_px': cfg.get('full_px'),
                                    'stall_tolerance': int(cfg.get('stall_tolerance', 12))})
        sources.append(lattice)
        order.append(lattice.name)
        # 方法2：待部署十分位（调用方注入读取器）
        if callable(cfg.get('read_digits')):
            tenths = RedeployTenthsClock(cfg['read_digits'],
                                         {'n_operators': int(cfg.get('n_operators', 3)),
                                          'anchor_frame': int(cfg.get('anchor_frame', 0))})
            sources.append(tenths)
            order.append(tenths.name)
        # 方法3：墙钟 × 倍速（可选）
        if callable(cfg.get('read_speed')) and callable(cfg.get('read_paused')):
            sources.append(WallRateClock(cfg['read_speed'], cfg['read_paused']))
            order.append(WallRateClock.name)
        # 方法4：外部尺子（若在跑，作为最高优先级的旁证源）
        snap = RulerClock.probe(host, port, timeout=float(cfg.get('probe_timeout', 0.3)))
        if snap is not None:
            rc = RulerClock(host, port, transport=cfg.get('transport', 'http'),
                            poll_hz=float(cfg.get('poll_hz', 120)))
            rc.start()
            return rc, 'ruler'
        prio = cfg.get('priority') or order
        return FrameClock(sources, priority=prio), 'frame_clock'
    if src == 'cost_number':
        if engine is None:
            raise RuntimeError('cost_number 时钟需要 engine（截图）')
        clock = CostNumberClock(engine.grab, cfg, initial_cost=float(cfg.get('initial_cost', 10)),
                                frames_per_cost=int(cfg.get('frames_per_cost', 30)))
        return clock.start(), 'cost_number'
    if src in ('auto', 'ruler'):
        snap = RulerClock.probe(host, port, timeout=float(cfg.get('probe_timeout', 0.4)))
        if snap is not None:
            clock = RulerClock(host, port, transport=cfg.get('transport', 'http'),
                               poll_hz=float(cfg.get('poll_hz', 120)),
                               stale_s=float(cfg.get('stale_s', 2.0)))
            return clock.start(), 'ruler'
        if src == 'ruler':
            raise RuntimeError(f'费用尺 API 不可用（http://{host}:{port}/）：请先启动 ArknightsCostBarRuler')
    if engine is None:
        raise RuntimeError('cost_bar 时钟需要 engine（截图+识别）')
    clock = CostBarClock(engine, cfg.get('cost_bar') or {})
    return clock.start(), 'cost_bar'


# --------------------------------------------------------------------------------------
# 轴表 → 绝对帧调度
# --------------------------------------------------------------------------------------
def build_frame_schedule(ops: list[dict], initial_cost: int = 10, frames_per_cost: int = 30,
                         unit_costs: dict[str, int] | None = None,
                         spent_of: dict[str, int] | None = None,
                         refund_ratio: float = 0.5,
                         timebase: str = 'cost-relative') -> list[dict]:
    """把「费用 + 费用内帧」锚点轴表换算成**绝对逻辑帧**计划。

    两种时基（PRTS+ 轴表的两种读法，默认前者）：
      * ``cost-relative``（默认）：费用读数行为锚点，其余行按「帧数」列相对上一行推进。
            绝对帧 = (费用读数 − 初始费用 + 净累计消耗) × 每费帧数 + 费用内帧
        理由：PRTS+ 使用须知第三条明确「轴将以费用与费用条作为唯一游戏时间参照」，
        「绝对时间」列在费用条满后不可靠。
      * ``abs-seconds``：直接采信表内「绝对时间」列 D（秒）+ 帧数 C/30。
        仅作对照/复现作者时间轴用。

    推导：显示费用 = 初始费用 + 自然回复量 − 净累计消耗（撤退返还 50%）
          → 自然回复量 = 显示费用 − 初始费用 + 净累计消耗
    """
    unit_costs = unit_costs or {}
    spent_of = spent_of or {}

    def _c(u: str) -> float:
        return float(spent_of.get(u, unit_costs.get(u, 0)) or 0)

    out: list[dict] = []
    spent = 0.0
    cursor = 0.0
    for i, o in enumerate(ops):
        item = dict(o)
        item['idx'] = i
        c = o.get('cost')
        foff = int(o.get('foff', 0) or 0)
        raw = cursor
        if timebase == 'abs-seconds' and o.get('abs_seconds') is not None:
            raw = float(o['abs_seconds']) * frames_per_cost
        elif c is not None:
            raw = (int(c) - initial_cost + spent) * frames_per_cost + foff
        else:
            raw = cursor + foff
        # 轴表是【顺序】语义：锚点算出的时刻若早于上一条，说明费用消耗记账与实际不符，
        # 此时按顺序语义夹紧到上一条（并记录 clamp 量与原因，供费用模型反查）。
        if raw < cursor - 1e-9:
            item['clamped_from'] = round(raw, 3)
            item['clamp_frames'] = round(cursor - raw, 3)
            cursor = cursor
        else:
            cursor = raw
        item['frame'] = int(round(cursor))
        item['cost_anchor'] = c
        item['spent_before'] = round(spent, 3)
        item['timebase'] = timebase
        out.append(item)
        if o.get('op') == 'deploy':
            spent += _c(o.get('unit', ''))
        elif o.get('op') == 'retreat':
            spent -= _c(o.get('unit', '')) * refund_ratio
    return out


def group_same_frame(plan: list[dict]) -> list[list[dict]]:
    """把绝对帧相同的操作分组（同帧顺序多操作）。"""
    groups: list[list[dict]] = []
    for it in plan:
        if groups and groups[-1][0]['frame'] == it['frame']:
            groups[-1].append(it)
        else:
            groups.append([it])
    return groups


def display_cost(elapsed_frames: float, initial_cost: float, net_spent: float,
                 frames_per_cost: float = 30.0) -> int:
    """估算**显示费用**（整数显示值）：初始费用 + 自然回复量 − 净消耗，向下取整。

    与模拟器 `Battle.cost_clock()` 同一语义（`int(self.cost)`）。
    """
    return int(initial_cost + elapsed_frames / max(1e-9, frames_per_cost) - net_spent + 1e-9)


def anchor_ready(elapsed_frames: float, initial_cost: float, net_spent: float, anchor: int,
                 foff: int, frames_per_cost: float = 30.0) -> tuple[bool, int, int]:
    """判断「费用锚点行」是否到点，返回 (是否就绪, 显示费用, 费用内帧)。

    与 PRTS+ / 模拟器一致的判定：显示费用 == 锚点读数 且 费用内帧 ≥ foff；
    显示费用已超过锚点也视为就绪（费用单调推进，不会回退）。费用内帧取 `elapsed % 每费帧数`。
    """
    e = int(elapsed_frames)
    disp = display_cost(e, initial_cost, net_spent, frames_per_cost)
    fpc = int(frames_per_cost)
    phase = e % fpc
    return (disp > anchor or (disp == anchor and phase >= int(foff))), disp, phase


def ideal_anchor_frame(initial_cost: float, net_spent: float, anchor: int, foff: int,
                       frames_per_cost: float = 30.0) -> int:
    """锚点行「理论最早可触发帧」：与 anchor_ready 同一判据下最小的整数逻辑帧。

    说明：净消耗含撤退返还（可能为 .5），故不能简单写成 (锚点 − 初始 + 消耗) × 每费帧数 + foff，
    必须按「显示费用向下取整 + 费用内帧相位」求解；本函数与 anchor_ready 严格对应。
    """
    fpc = max(1, int(frames_per_cost))
    base = (anchor - initial_cost + net_spent) * frames_per_cost
    e = max(0, int(math.ceil(base - 1e-9)))
    for _ in range(fpc + 2):
        ok, disp, phase = anchor_ready(e, initial_cost, net_spent, anchor, foff, frames_per_cost)
        if ok:
            return e
        e += 1
    return int(round(base)) + int(foff)
