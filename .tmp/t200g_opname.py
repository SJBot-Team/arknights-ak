# -*- coding: utf-8 -*-
"""t200g_opname.py — 试探：prts+ 自带的 Python 3.9 运行时里能否直接取到 opcode 表。

思路：`_internal/python39.dll` 是完整 3.9 运行时；若 `_internal` 下还有 `python3.dll` 的
导出函数可用，可尝试 `Py_Initialize` + 导入 `opcode`（3.9 的 stdlib 在 base_library.zip 里，
但该 zip 未含 opcode.pyc）⇒ 本脚本只是**探测**，失败就打印结论。
"""
import ctypes
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

DLL = r'D:\__soft\ak\prts+\_internal\python39.dll'
print('dll exists:', os.path.exists(DLL))
try:
    os.add_dll_directory(r'D:\__soft\ak\prts+\_internal')
except Exception as e:
    print('add_dll_directory:', e)
try:
    py = ctypes.PyDLL(DLL)
    print('loaded:', py)
    py.Py_Initialize()
    py.PyRun_SimpleString(b'import sys; print("py", sys.version)')
except Exception as e:
    print('FAIL:', type(e).__name__, e)
