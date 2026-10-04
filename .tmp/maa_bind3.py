# -*- coding: utf-8 -*-
"""MaaCore ctypes 绑定验证（最终版）
证明：外部程序可创建 MAA 实例、装资源、排队任务、并通过回调读回结构化结果。
不连接设备、不启动任何任务（AsstStart 不调用）。
"""
import ctypes, os, time

MAA = r"D:\__soft\MAA"
OUT = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\maa_bind_result.txt"
lines = []


def p(*a):
    lines.append(" ".join(str(x) for x in a))
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))


os.add_dll_directory(MAA)
dll = ctypes.CDLL(os.path.join(MAA, "MaaCore.dll"))
dll.AsstGetVersion.restype = ctypes.c_char_p
dll.AsstSetUserDir.argtypes = [ctypes.c_char_p]; dll.AsstSetUserDir.restype = ctypes.c_ubyte
dll.AsstLoadResource.argtypes = [ctypes.c_char_p]; dll.AsstLoadResource.restype = ctypes.c_ubyte
dll.AsstSetStaticOption.argtypes = [ctypes.c_int32, ctypes.c_char_p]; dll.AsstSetStaticOption.restype = ctypes.c_ubyte
CB = ctypes.CFUNCTYPE(None, ctypes.c_int32, ctypes.c_char_p, ctypes.c_void_p)
dll.AsstCreateEx.restype = ctypes.c_void_p; dll.AsstCreateEx.argtypes = [CB, ctypes.c_void_p]
dll.AsstSetInstanceOption.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_char_p]
dll.AsstSetInstanceOption.restype = ctypes.c_ubyte
dll.AsstAppendTask.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
dll.AsstAppendTask.restype = ctypes.c_int32
dll.AsstGetUUID.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint64]
dll.AsstGetUUID.restype = ctypes.c_uint64
dll.AsstConnected.argtypes = [ctypes.c_void_p]; dll.AsstConnected.restype = ctypes.c_ubyte
dll.AsstRunning.argtypes = [ctypes.c_void_p]; dll.AsstRunning.restype = ctypes.c_ubyte
dll.AsstGetTasksList.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64]
dll.AsstGetTasksList.restype = ctypes.c_uint64
dll.AsstDestroy.argtypes = [ctypes.c_void_p]

p("AsstGetVersion:", dll.AsstGetVersion().decode())
p("AsstSetUserDir(MAA):", dll.AsstSetUserDir(MAA.encode()))
p("AsstLoadResource(MAA):", dll.AsstLoadResource(MAA.encode()))
p("AsstSetStaticOption(1 /*CpuOCR*/, 'true'):", dll.AsstSetStaticOption(1, b"true"))

events = []


@CB
def cb(msg, details, arg):
    d = details.decode("utf-8", "replace") if details else ""
    events.append((msg, d))
    p(f"  [CB msg={msg}] {d[:400]}")


h = dll.AsstCreateEx(cb, None)
p("AsstCreateEx ->", ("0x%x" % h) if h else None)
if not h:
    p("FATAL: create failed"); raise SystemExit(0)
time.sleep(1.0)

buf = ctypes.create_string_buffer(256)
n = dll.AsstGetUUID(h, buf, 256)
p("AsstGetUUID n=", n, "uuid=", buf.value.decode(errors="replace"))
p("AsstConnected:", dll.AsstConnected(h))
p("AsstRunning:", dll.AsstRunning(h))

# 实例选项（0=Invalid, 2=TouchMode, 3=DeploymentWithPause, 4=AdbLiteEnabled, 5=KillAdbOnExit）
for k, v in ((2, b"macadam"), (3, b"1"), (4, b"0"), (5, b"1")):
    p(f"AsstSetInstanceOption({k},{v!r}) ->", dll.AsstSetInstanceOption(h, k, v))

# ★核心：排队任务 → 读回 task_id（= agent 的"下达一步"接口）
for ty, ps in (
    ("StartUp", '{"client_type":"Official","start_game_enabled":false}'),
    ("Fight", '{"stage":"1-7","medicine":0,"stone":0,"times":1,"report_to_penguin":false}'),
):
    tid = dll.AsstAppendTask(h, ty.encode(), ps.encode())
    p(f"AsstAppendTask({ty}) -> task_id = {tid}")

buf2 = (ctypes.c_int32 * 16)()
n2 = dll.AsstGetTasksList(h, buf2, ctypes.sizeof(buf2))
p("AsstGetTasksList bytes =", n2, "ids =", [buf2[i] for i in range(min(n2 // 4, 16))])

time.sleep(0.5)
p("callback events:", len(events))
for m, d in events:
    p("   msg=", m, d[:300])
dll.AsstDestroy(h)
p("AsstDestroy OK  => 绑定链路可用")
