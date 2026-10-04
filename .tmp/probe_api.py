# -*- coding: utf-8 -*-
"""Empirical probe: load MaaCore.dll out-of-process and exercise the C API
WITHOUT connecting to any device (no input is ever sent)."""
import ctypes, json, os, sys, time, pathlib

MAA = r"D:\__soft\MAA"
USERDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\maauser"
os.makedirs(USERDIR, exist_ok=True)
os.environ["PATH"] = MAA + os.pathsep + os.environ.get("PATH", "")
os.add_dll_directory(MAA)

lib = ctypes.WinDLL(os.path.join(MAA, "MaaCore.dll"))

# ---- bind ----
def bind(name, res, args):
    f = getattr(lib, name)
    f.restype = res
    f.argtypes = args
    return f

AsstSetUserDir      = bind("AsstSetUserDir", ctypes.c_ubyte, (ctypes.c_char_p,))
AsstLoadResource    = bind("AsstLoadResource", ctypes.c_ubyte, (ctypes.c_char_p,))
AsstGetVersion      = bind("AsstGetVersion", ctypes.c_char_p, ())
AsstCreate          = bind("AsstCreate", ctypes.c_void_p, ())
AsstDestroy         = bind("AsstDestroy", None, (ctypes.c_void_p,))
AsstAppendTask      = bind("AsstAppendTask", ctypes.c_int32, (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p))
AsstSetTaskParams   = bind("AsstSetTaskParams", ctypes.c_ubyte, (ctypes.c_void_p, ctypes.c_int32, ctypes.c_char_p))
AsstStart           = bind("AsstStart", ctypes.c_ubyte, (ctypes.c_void_p,))
AsstStop            = bind("AsstStop", ctypes.c_ubyte, (ctypes.c_void_p,))
AsstRunning         = bind("AsstRunning", ctypes.c_ubyte, (ctypes.c_void_p,))
AsstConnected       = bind("AsstConnected", ctypes.c_ubyte, (ctypes.c_void_p,))
AsstBackToHome      = bind("AsstBackToHome", ctypes.c_ubyte, (ctypes.c_void_p,))
AsstGetImage        = bind("AsstGetImage", ctypes.c_uint64, (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64))
AsstGetImageBgr     = bind("AsstGetImageBgr", ctypes.c_uint64, (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64))
AsstGetUUID         = bind("AsstGetUUID", ctypes.c_uint64, (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint64))
AsstGetTasksList    = bind("AsstGetTasksList", ctypes.c_uint64, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32), ctypes.c_uint64))
AsstGetNullSize     = bind("AsstGetNullSize", ctypes.c_uint64, ())
AsstAsyncClick      = bind("AsstAsyncClick", ctypes.c_int32, (ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32, ctypes.c_ubyte))
AsstAsyncScreencap  = bind("AsstAsyncScreencap", ctypes.c_int32, (ctypes.c_void_p, ctypes.c_ubyte))
AsstSetInstanceOption = bind("AsstSetInstanceOption", ctypes.c_ubyte, (ctypes.c_void_p, ctypes.c_int32, ctypes.c_char_p))

CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int32, ctypes.c_char_p, ctypes.c_void_p)
MSG = {}
try:
    from asst.utils import Message  # optional
except Exception:
    Message = None

events = []
@CALLBACK
def cb(msg, details, arg):
    d = details.decode("utf-8", "replace") if details else ""
    events.append((msg, d))
    print("[CALLBACK] msg=%d details=%s" % (msg, d[:400]))

AsstCreateEx = bind("AsstCreateEx", ctypes.c_void_p, (ctypes.c_void_p, ctypes.c_void_p))

print("== AsstGetVersion ==", AsstGetVersion().decode())
print("== AsstGetNullSize ==", AsstGetNullSize())
print("== AsstSetUserDir ==", AsstSetUserDir(USERDIR.encode()))
t0 = time.time()
print("== AsstLoadResource ==", AsstLoadResource(MAA.encode()), "cost %.0f ms" % ((time.time()-t0)*1000))

h = AsstCreateEx(ctypes.cast(cb, ctypes.c_void_p), None)
print("== AsstCreateEx handle ==", hex(h) if h else h)
h2 = AsstCreate()
print("== AsstCreate handle ==", hex(h2) if h2 else h2)

for k, v, lbl in [(2, b"maatouch", "TouchMode"), (3, b"1", "DeploymentWithPause"),
                  (4, b"1", "AdbLiteEnabled"), (5, b"1", "KillAdbOnExit")]:
    print("== AsstSetInstanceOption(%s=%s) ==" % (lbl, v.decode()), AsstSetInstanceOption(h, k, v))

print("== AsstConnected (no device) ==", AsstConnected(h))

# append tasks WITHOUT starting: proves the task-description pipeline is usable
for t, p in [("StartUp", {"client_type": "Official"}),
             ("Fight", {"stage": "1-7", "times": 1}),
             ("Copilot", {"filename": "copilot/OF-1_credit_fight.json", "formation": False}),
             ("SingleStep", {"type": "copilot", "subtype": "stage", "details": {"stage_name": "1-7"}})]:
    tid = AsstAppendTask(h, t.encode(), json.dumps(p, ensure_ascii=False).encode())
    print("== AsstAppendTask(%s) -> taskid %d ==" % (t, tid))

buf = (ctypes.c_int32 * 32)()
n = AsstGetTasksList(h, buf, ctypes.sizeof(buf))
print("== AsstGetTasksList -> %d, ids=%s ==" % (n, list(buf)[:max(0, n)]))

print("== AsstSetTaskParams(id=2, {'times':5}) ==",
      AsstSetTaskParams(h, 2, json.dumps({"stage": "1-7", "times": 5}).encode()))

print("== AsstRunning ==", AsstRunning(h))
print("== AsstBackToHome (no device) ==", AsstBackToHome(h))

ub = ctypes.create_string_buffer(256)
print("== AsstGetUUID ->", AsstGetUUID(h, ub, 256), repr(ub.value))

img = ctypes.create_string_buffer(1280*720*3)
print("== AsstGetImage(1280*720*3) ->", AsstGetImage(h, img, 1280*720*3))
print("== AsstGetImageBgr ->", AsstGetImageBgr(h, img, 1280*720*3))
print("== AsstAsyncScreencap ->", AsstAsyncScreencap(h, 0))
print("== AsstAsyncClick(640,360) ->", AsstAsyncClick(h, 640, 360, 0))

print("== AsstStop ==", AsstStop(h))
AsstDestroy(h); AsstDestroy(h2)
print("== DONE, %d callbacks ==" % len(events))
