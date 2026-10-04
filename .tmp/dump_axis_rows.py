# -*- coding: utf-8 -*-
"""临时：打印赛博塑料 h12-4 轴表原始行（前 20 行、A..K 列）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import openpyxl

P = r'E:\__file\舟数据\关卡\h12-4\赛博塑料h12-4.xlsm'
wb = openpyxl.load_workbook(P, read_only=True, data_only=True, keep_vba=False)
ws = wb['作战记录']
for i, row in enumerate(ws.iter_rows(min_row=1, max_row=20, values_only=True), 1):
    cells = [(str(x)[:16] if x is not None else '') for x in row[:11]]
    print(i, cells)
