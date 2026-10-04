# -*- coding: utf-8 -*-
"""验证 MAA 的"步进驱动 + 结果读回"闭环（不连游戏、不启动任务）
- AsstGetImage 缓冲尺寸协议
- AsstGetTasksList 尺寸协议
- AsstStart 的错误回调（结构化读回）
"""
import ctypes, os, time

MAA = r"D:\__soft\MAA"
OUT = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\maa_step_result.txt"
lines = []
def p(*a):
    lines.append(" ".join(str(x) for x in a))
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))

os.add_dll_directory(MAA)
dll = ctypes.CDLL(os.path.join(MAA, "MaaCore.dll"))
dll.AsstGetVersion.restype = ctypes.c_char_p
dll.AsstLoadResource.argtypes = [ctypes.c_char_p]; dll.AsstLoadResource.restype = ctypes.c_ubyte
dll.AsstSetUserDir.argtypes = [ctypes.c_char_p]; dll.AsstSetUserDir.restype = ctypes.c_ubyte
CB = ctypes.CFUNCTYPE(None, ctypes.c_int32, ctypes.c_char_p, ctypes.c_void_p)
dll.AsstCreateEx.restype = ctypes.c_void_p; dll.AsstCreateEx.argtypes = [CB, ctypes.c_void_p]
dll.AsstAppendTask.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
dll.AsstAppendTask.restype = ctypes.c_int32
dll.AsstStart.argtypes = [ctypes.c_void_p]; dll.AsstStart.restype = ctypes.c_ubyte
dll.AsstRunning.argtypes = [ctypes.c_void_p]; dll.AsstRunning.restype = ctypes.c_ubyte
dll.AsstGetImage.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64]
dll.AsstGetImage.restype = ctypes.c_uint64
dll.AsstGetTasksList.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64]
dll.AsstGetTasksList.restype = ctypes.c_uint64
dll.AsstGetNullSize.restype = ctypes.c_uint64
dll.AsstDestroy.argtypes = [ctypes.c_void_p]

dll.AsstSetUserDir(MAA.encode()); p("loadres:", dll.AsstLoadResource(MAA.encode()))
events = []
@CB
def cb(msg, details, arg):
    d = details.decode("utf-8", "replace") if details else ""
    events.append((msg, d)); p(f"[CB {msg}] {d[:500]}")

h = dll.AsstCreateEx(cb, None)
time.sleep(0.5)
p("handle:", hex(h))
p("AsstGetNullSize():", dll.AsstGetNullSize())
p("AsstGetImage(h, None, 0) 请求尺寸 ->", dll.AsstGetImage(h, None, 0))
p("AsstGetTasksList(h, None, 0) 请求尺寸 ->", dll.AsstGetTasksList(h, None, 0))

tid = dll.AsstAppendTask(h, b"StartUp", b'{"client_type":"Official","start_game_enabled":false}')
p("append StartUp -> task_id", tid)
p("AsstGetTasksList(h,None,0) after append ->", dll.AsstGetTasksList(h, None, 0))

# ★ 步进：AsstStart 启动；未连接设备 ⇒ 应通过回调返回结构化错误
p("AsstStart ->", dll.AsstStart(h))
for i in range(20):
    time.sleep(0.3)
    if not dll.AsstRunning(h):
        p(f"  running=False after {0.3*(i+1):.1f}s"); break
p("events:", len(events))
for m, d in events:
    p("  msg", m, d[:400])
dll.AsstDestroy(h)
p("OK")
