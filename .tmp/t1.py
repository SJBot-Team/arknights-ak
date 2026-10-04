import ctypes, os, sys, time, traceback
LOG = open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\probe_out.txt", "w", encoding="utf-8")
def p(*a):
    print(*a); print(*a, file=LOG); LOG.flush()
MAA = r"D:\__soft\MAA"
os.add_dll_directory(MAA)
dll = ctypes.CDLL(os.path.join(MAA, "MaaCore.dll"))
p("dll loaded")
CB = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)
events = []
@CB
def cb(msg, details, arg):
    d = details.decode("utf-8","replace") if details else ""
    events.append((msg,d)); p(f"[CB {msg}] {d[:400]}")
dll.AsstCreateEx.restype = ctypes.c_void_p
dll.AsstCreateEx.argtypes = [CB, ctypes.c_void_p]
p("calling AsstCreateEx...")
inst = dll.AsstCreateEx(cb, None)
p("inst =", inst)
dll.AsstLoadResource.argtypes=[ctypes.c_char_p]; dll.AsstLoadResource.restype=ctypes.c_bool
p("calling AsstLoadResource...")
p("load =", dll.AsstLoadResource(os.path.join(MAA,"resource").encode()))
time.sleep(0.5)
p("events so far:", len(events))
p("done")
LOG.close()
