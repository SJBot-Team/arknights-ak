import ctypes, os
MAA = r"D:\__soft\MAA"
os.add_dll_directory(MAA)
dll = ctypes.CDLL(os.path.join(MAA, "MaaCore.dll"))
dll.AsstLoadResource.argtypes=[ctypes.c_char_p]; dll.AsstLoadResource.restype=ctypes.c_ubyte
dll.AsstSetUserDir.argtypes=[ctypes.c_char_p]; dll.AsstSetUserDir.restype=ctypes.c_ubyte
dll.AsstSetStaticOption.argtypes=[ctypes.c_int32, ctypes.c_char_p]; dll.AsstSetStaticOption.restype=ctypes.c_ubyte
res = []
for cand in [ MAA, MAA+"\\", MAA+"\\resource", MAA+"\\resource\\", os.path.join(MAA,"resource")+"\\.", os.getcwd() ]:
    r = dll.AsstLoadResource(cand.encode())
    res.append(f"LoadResource({cand!r}) = {r}")
for k in range(0, 12):
    v = dll.AsstSetStaticOption(k, MAA.encode())
    res.append(f"SetStaticOption({k}, MAA) = {v}")
open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\loadres.txt","w",encoding="utf-8").write("\n".join(res))
