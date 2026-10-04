# -*- coding: utf-8 -*-
"""临时：完整打印「使用须知」全文（不截断）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import openpyxl

P = r'E:\__file\舟数据\关卡\h12-4\赛博塑料h12-4.xlsm'
wb = openpyxl.load_workbook(P, read_only=True, data_only=True, keep_vba=False)
for name in ('使用须知', 'Sheet1'):
    ws = wb[name]
    print(f'===== {name} =====')
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        cells = [str(x) for x in row if x is not None]
        if cells:
            print(f'{i:>3}', ' || '.join(cells))
