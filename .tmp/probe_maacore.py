# -*- coding: utf-8 -*-
"""最小绑定实验：证明 MaaCore.dll 可被外部程序驱动（不连游戏、不启动任何任务）"""
import ctypes, os, sys, json, time
sys.stdout.reconfigure(encoding="utf-8")
MAA = r"D:\__soft\MAA"
os.add_dll_directory(MAA)
os.environ["PATH"] = MAA + os.pathsep + os.environ["PATH"]
dll = ctypes.CDLL(os.path.join(MAA, "MaaCore.dll"))

# 回调签名： void (*)(int msg, const char* details_json, void* custom_arg)
CB = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)
events = []
@CB
def cb(msg, details, arg):
    try:
        d = details.decode("utf-8", "replace") if details else ""
    except Exception:
        d = str(details)
    events.append((msg, d))
    print(f"  [CB msg={msg}] {d[:300]}")

dll.AsstCreateEx.restype = ctypes.c_void_p
dll.AsstCreateEx.argtypes = [CB, ctypes.c_void_p]
dll.AsstLoadResource.argtypes = [ctypes.c_char_p]
dll.AsstLoadResource.restype = ctypes.c_bool
dll.AsstGetVersion.restype = ctypes.c_char_p
dll.AsstSetStaticOption.argtypes = [ctypes.c_int, ctypes.c_char_p]
dll.AsstSetStaticOption.restype = ctypes.c_bool
dll.AsstGetUUID.argtypes = [ctypes.c_void_p]
dll.AsstGetUUID.restype = ctypes.c_char_p
dll.AsstAppendTask.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
dll.AsstAppendTask.restype = ctypes.c_int
dll.AsstRunning.argtypes = [ctypes.c_void_p]
dll.AsstRunning.restype = ctypes.c_bool
dll.AsstConnected.argtypes = [ctypes.c_void_p]
dll.AsstConnected.restype = ctypes.c_bool
dll.AsstGetTasksList.argtypes = [ctypes.c_void_p]
dll.AsstGetTasksList.restype = ctypes.c_void_p
dll.AsstDestroy.argtypes = [ctypes.c_void_p]
dll.AsstLog.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]

print("AsstGetVersion ->", dll.AsstGetVersion().decode())
# 1) 创建实例 + 注册回调（步进驱动的"结果读回"通道）
inst = dll.AsstCreateEx(cb, None)
print("AsstCreateEx ->", hex(inst) if inst else inst)
# 2) 设置资源目录 + 日志级别（3=INFO，日志可解析）
dll.AsstSetStaticOption(1, MAA.encode())           # StaticOption::RunDirectory?
ok = dll.AsstLoadResource(os.path.join(MAA, "resource").encode())
print("AsstLoadResource ->", ok)
print("AsstGetUUID ->", dll.AsstGetUUID(inst).decode())
print("AsstConnected ->", dll.AsstConnected(inst))
dll.AsstLog(inst, b"agent-probe", b"ctypes binding alive")
time.sleep(0.5)
# 3) 关键：不带 device 号，只验证 append 接口的返回码（-1 = 失败）
tid = dll.AsstAppendTask(inst, b"StartUp", b'{"client_type":"Official","start_game_enabled":false}')
print("AsstAppendTask('StartUp') ->", tid, "(>=0 表示任务被接受并排队)")
print("AsstRunning ->", dll.AsstRunning(inst))
dll.AsstDestroy(inst)
print("\nEVENTS:", len(events))
for m, d in events[:12]:
    print(" ", m, d[:200])
