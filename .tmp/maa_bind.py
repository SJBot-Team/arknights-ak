# -*- coding: utf-8 -*-
"""MaaCore 绑定验证（正确签名版）：证明可创建实例+装资源+排队任务+收回调"""
import ctypes, os, time, sys
MAA = r"D:\__soft\MAA"
OUT = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\maa_bind_result.txt"
lines=[]
def p(*a):
    s = " ".join(str(x) for x in a); lines.append(s)
    open(OUT,"w",encoding="utf-8").write("\n".join(lines))
os.add_dll_directory(MAA)
dll = ctypes.CDLL(os.path.join(MAA, "MaaCore.dll"))

uint64 = ctypes.c_uint64; csize = ctypes.c_uint64
dll.AsstGetVersion.restype = ctypes.c_char_p
dll.AsstSetUserDir.argtypes=[ctypes.c_char_p]; dll.AsstSetUserDir.restype=ctypes.c_ubyte
dll.AsstLoadResource.argtypes=[ctypes.c_char_p]; dll.AsstLoadResource.restype=ctypes.c_ubyte
dll.AsstSetStaticOption.argtypes=[ctypes.c_int32, ctypes.c_char_p]; dll.AsstSetStaticOption.restype=ctypes.c_ubyte
dll.AsstCreate.restype = ctypes.c_void_p; dll.AsstCreate.argtypes=[]
CB = ctypes.CFUNCTYPE(None, ctypes.c_int32, ctypes.c_char_p, ctypes.c_void_p)
dll.AsstCreateEx.restype = ctypes.c_void_p; dll.AsstCreateEx.argtypes=[CB, ctypes.c_void_p]
dll.AsstSetInstanceOption.argtypes=[ctypes.c_void_p, ctypes.c_int32, ctypes.c_char_p]; dll.AsstSetInstanceOption.restype=ctypes.c_ubyte
dll.AsstAppendTask.argtypes=[ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]; dll.AsstAppendTask.restype=ctypes.c_int32
dll.AsstGetUUID.argtypes=[ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint64]; dll.AsstGetUUID.restype=ctypes.c_uint64
dll.AsstGetNullSize.restype = ctypes.c_uint64
dll.AsstConnected.argtypes=[ctypes.c_void_p]; dll.AsstConnected.restype=ctypes.c_ubyte
dll.AsstRunning.argtypes=[ctypes.c_void_p]; dll.AsstRunning.restype=ctypes.c_ubyte
dll.AsstGetImage.argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64]; dll.AsstGetImage.restype=ctypes.c_uint64
dll.AsstDestroy.argtypes=[ctypes.c_void_p]

p("version:", dll.AsstGetVersion().decode())
p("AsstSetUserDir:", dll.AsstSetUserDir(MAA.encode()))
events=[]
@CB
def cb(msg, details, arg):
    d = details.decode("utf-8","replace") if details else ""
    events.append((msg,d)); p(f"  [CB {msg}] {d[:300]}")
h = dll.AsstCreateEx(cb, None)
p("AsstCreateEx ->", ("0x%x"%h) if h else None)
if not h:
    p("AsstCreateEx 返回空，改试 AsstCreate()")
    h = dll.AsstCreate(); p("AsstCreate ->", ("0x%x"%h) if h else None)
if not h:
    p("FATAL: 无法创建实例"); raise SystemExit(0)
p("AsstLoadResource:", dll.AsstLoadResource(os.path.join(MAA,"resource").encode()))
time.sleep(1.0)
buf = ctypes.create_string_buffer(128)
n = dll.AsstGetUUID(h, buf, 128); p("AsstGetUUID n=", n, "uuid=", buf.value.decode(errors="replace"))
p("AsstConnected:", dll.AsstConnected(h))
p("AsstRunning:", dll.AsstRunning(h))
p("AsstGetNullSize:", dll.AsstGetNullSize())
# ★核心：排队一个任务并读回 task_id（步进驱动的"下达"接口）
tid = dll.AsstAppendTask(h, b"StartUp", b'{"client_type":"Official","start_game_enabled":false}')
p("AsstAppendTask('StartUp') -> task_id =", tid)
tid2 = dll.AsstAppendTask(h, b"Fight", b'{"stage":"1-7","medicine":0,"stone":0,"times":1,"report_to_penguin":false}')
p("AsstAppendTask('Fight') -> task_id =", tid2)
buf2 = (ctypes.c_int32*16)()
n2 = dll.AsstGetTasksList(h, buf2, ctypes.sizeof(buf2))
p("AsstGetTasksList n=", n2, "ids=", [buf2[i] for i in range(min(n2//4,16))])
p("AsstSetInstanceOption(handle,0,'') ->", dll.AsstSetInstanceOption(h, 0, b""))
p("callback events so far:", len(events))
for m,d in events: p("   ", m, d[:200])
dll.AsstDestroy(h); p("destroyed OK")
