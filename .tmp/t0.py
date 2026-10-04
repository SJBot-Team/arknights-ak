import ctypes, os, sys
sys.stdout.reconfigure(encoding="utf-8")
MAA = r"D:\__soft\MAA"
try:
    os.add_dll_directory(MAA)
except Exception as e:
    print("add_dll_directory:", e)
dll = ctypes.CDLL(os.path.join(MAA, "MaaCore.dll"))
print("LOADED OK")
dll.AsstGetVersion.restype = ctypes.c_char_p
print("version:", dll.AsstGetVersion())
