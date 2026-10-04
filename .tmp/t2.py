import ctypes, os, time
MAA = r"D:\__soft\MAA"
os.add_dll_directory(MAA)
dll = ctypes.CDLL(os.path.join(MAA, "MaaCore.dll"))
out=[]
def p(*a): out.append(" ".join(str(x) for x in a))
dll.AsstCreate.restype = ctypes.c_void_p
p("AsstCreate restype set")
h = dll.AsstCreate()
p("AsstCreate() ->", h)
dll.AsstSetUserDir.argtypes=[ctypes.c_char_p]; dll.AsstSetUserDir.restype=ctypes.c_bool
p("AsstSetUserDir ->", dll.AsstSetUserDir(MAA.encode()))
dll.AsstLoadResource.argtypes=[ctypes.c_char_p]; dll.AsstLoadResource.restype=ctypes.c_bool
p("AsstLoadResource ->", dll.AsstLoadResource(os.path.join(MAA,"resource").encode()))
dll.AsstGetVersion.restype=ctypes.c_char_p
p("version:", dll.AsstGetVersion())
dll.AsstConnected.argtypes=[ctypes.c_void_p]; dll.AsstConnected.restype=ctypes.c_bool
p("connected:", dll.AsstConnected(h))
dll.AsstGetUUID.argtypes=[ctypes.c_void_p]; dll.AsstGetUUID.restype=ctypes.c_char_p
p("uuid:", dll.AsstGetUUID(h))
dll.AsstGetNullSize.restype = ctypes.c_ulonglong
p("nullsize:", dll.AsstGetNullSize())
dll.AsstAppendTask.argtypes=[ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]; dll.AsstAppendTask.restype=ctypes.c_int
p("append StartUp ->", dll.AsstAppendTask(h, b"StartUp", b'{"client_type":"Official","start_game_enabled":false}'))
dll.AsstAppendTask.argtypes=[ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
p("append Fight ->", dll.AsstAppendTask(h, b"Fight", b'{"stage":"1-7","medicine":0,"stone":0,"times":1}'))
dll.AsstGetTasksList.argtypes=[ctypes.c_void_p]; dll.AsstGetTasksList.restype=ctypes.c_void_p
p("taskslist ptr:", dll.AsstGetTasksList(h))
dll.AsstDestroy.argtypes=[ctypes.c_void_p]
dll.AsstDestroy(h)
p("destroyed")
open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t2_out.txt","w",encoding="utf-8").write("\n".join(out))
