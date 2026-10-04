# -*- coding: utf-8 -*-
"""t200g_sig.py — 编译一段与 prts+ 同形的源码，打印其 co_code 头部字节。

目的：判定 prts+ 的字节码版本（与本地 code 对象的实际字节逐一对照）。
"""
import sys

SRC = (
    "import numpy as np\n"
    "import math\n"
    "from typing import List, Tuple, Dict, Any\n"
    "from src.logger import logger\n"
    "from src.config import ViewCalculationConfig as viewconfig\n"
    "\n"
    "def transform_map_to_view(level: dict, side: bool) -> List[Tuple[Dict[str, Any], float]]:\n"
    "    DEGREE = 180 / math.pi\n"
    "    height = level['height']\n"
    "    width = level['width']\n"
    "    return []\n"
)

ns = {}
code = compile(SRC, 'logic\\calc_view.py', 'exec')
print('python', sys.version.split()[0])
print('module head :', code.co_code[:24].hex(' '))
sub = [c for c in code.co_consts if hasattr(c, 'co_code')][0]
print('func   head :', sub.co_code[:24].hex(' '))
