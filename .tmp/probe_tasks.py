# -*- coding: utf-8 -*-
import ctypes, json, os, time
MAA = r"D:\__soft\MAA"
USERDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\maauser"
os.environ["PATH"] = MAA + os.pathsep + os.environ.get("PATH", "")
os.add_dll_directory(MAA)
lib = ctypes.WinDLL(os.path.join(MAA, "MaaCore.dll"))
def bind(n, r, a):
    f = getattr(lib, n); f.restype = r; f.argtypes = a; return f
AsstSetUserDir = bind("AsstSetUserDir", ctypes.c_ubyte, (ctypes.c_char_p,))
AsstLoadResource = bind("AsstLoadResource", ctypes.c_ubyte, (ctypes.c_char_p,))
AsstCreate = bind("AsstCreate", ctypes.c_void_p, ())
AsstDestroy = bind("AsstDestroy", None, (ctypes.c_void_p,))
AsstAppendTask = bind("AsstAppendTask", ctypes.c_int32, (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p))
AsstGetVersion = bind("AsstGetVersion", ctypes.c_char_p, ())

AsstSetUserDir(USERDIR.encode()); AsstLoadResource(MAA.encode())
h = AsstCreate()
print("version:", AsstGetVersion().decode())

cases = [
    ("Copilot-rel",  "Copilot",    {"filename": "copilot/OF-1_credit_fight.json"}),
    ("Copilot-abs",  "Copilot",    {"filename": r"D:\__soft\MAA\resource\copilot\OF-1_credit_fight.json"}),
    ("SingleStep-stage", "SingleStep", {"type": "copilot", "subtype": "stage", "details": {"stage_name": "1-7"}}),
    ("SingleStep-start", "SingleStep", {"type": "copilot", "subtype": "start"}),
    ("SingleStep-action", "SingleStep", {"type": "copilot", "subtype": "action",
        "details": {"name": "史尔特尔", "location": [4, 5], "direction": "左"}}),
    ("Custom-AwardBegin", "Custom", {"task_names": ["AwardBegin"]}),
    ("Bogus",        "NoSuchTask",  {}),
]
for label, t, p in cases:
    tid = AsstAppendTask(h, t.encode(), json.dumps(p, ensure_ascii=False).encode())
    print("%-20s %-14s -> taskid=%d" % (label, t, tid))
AsstDestroy(h)
print("\n--- generated files under userdir ---")
for root, dirs, files in os.walk(USERDIR):
    for f in files:
        fp = os.path.join(root, f)
        print(os.path.getsize(fp), fp)
