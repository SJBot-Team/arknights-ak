# -*- coding: utf-8 -*-
"""按第一节确认表替换舟数据文件中的干员命名（先备份，替换后输出验证摘要）。
用法: python replace_names.py
"""
import os, re, shutil, datetime

SRC_ROOT = r"E:\__file\舟数据"
BACKUP_ROOT = r"C:\Users\23922\Documents\ds_harness\ak\_raw\zhoudata\backup"
VERIFY = r"C:\Users\23922\Documents\ds_harness\ak\_raw\zhoudata\replace_verify.txt"

# 需处理的文件（第一节简称出现处）
TARGETS = [
    r"通用\干员输出表.xlsx",
    r"关卡\失控.xlsx",
    r"关卡\昔字如烟.xlsx",
    r"关卡\h12-4\h12-4 (version 1).xlsb.xlsx",
    r"关卡\弧光\7r.xlsx",
    r"关卡\水月无藏\寒冷队.xlsx",
]

# 替换规则（顺序敏感：先多字词，后单字边界）
RULES = [
    ("深淀", "深靛"),                      # 深靛（官方名）
    ("异银", "凛御银灰"),                   # 银灰异格
    ("蒂蒂", "斯卡蒂"),
    ("饼干", "乌尔比安"),
    ("新能", "新约能天使"),
    ("浊蒂", "浊心斯卡蒂"),
    ("妮妮宝贝", "妮芙"),
    ("君君", "弑君者"),
    ("隐隐", "隐德来希"),
    ("剑陈", "陈"),
    ("灵芝", "灵知"),
    ("安洁", "安洁莉娜"),
    ("能安", "新约能天使&蕾缪安"),
    ("能艾", "新约能天使&艾拉"),
    # 单字/缩写（带边界，避免误伤中文词语）
    (re.compile(r"(?<![\u4e00-\u9fa5A-Za-z0-9])安(?=[0-9一二三普攻\s:：]|$)"), "蕾缪安"),
    (re.compile(r"(?<![\u4e00-\u9fa5A-Za-z0-9])酒(?=[0-9一二三普攻\s:：]|$)"), "酒神"),
    (re.compile(r"(?<![\u4e00-\u9fa5A-Za-z0-9])温(?=[0-9\s:：]|$)"), "温蒂"),
    (re.compile(r"(?<![\u4e00-\u9fa5A-Za-z0-9])麦(?=[\s:：]|$)"), "麦哲伦"),
    (re.compile(r"(?<![\u4e00-\u9fa5A-Za-z0-9])洁(?=[0-9\s:：]|$)"), "安洁莉娜"),
    (re.compile(r"(?<![A-Za-z])ew(?![A-Za-z])"), "维什戴尔"),
]


def apply_rules(s):
    if not isinstance(s, str):
        return s
    for pat, rep in RULES:
        if isinstance(pat, str):
            s = s.replace(pat, rep)
        else:
            s = pat.sub(rep, s)
    return s


def main():
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    verify = []
    for rel in TARGETS:
        src = os.path.join(SRC_ROOT, rel)
        if not os.path.exists(src):
            verify.append(f"SKIP (不存在): {rel}")
            continue
        # 备份
        bdir = os.path.join(BACKUP_ROOT, stamp)
        os.makedirs(bdir, exist_ok=True)
        bname = rel.replace(os.sep, "__")
        shutil.copy2(src, os.path.join(bdir, bname))
        # 替换
        import openpyxl
        wb = openpyxl.load_workbook(src, data_only=False)
        n_cells = 0
        hits = []
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        new = apply_rules(cell.value)
                        if new != cell.value:
                            hits.append(f"  {ws.title}!{cell.coordinate}: {cell.value[:40]} -> {new[:40]}")
                            cell.value = new
                            n_cells += 1
        wb.save(src)
        verify.append(f"OK {rel}: 替换 {n_cells} 个单元格\n" + "\n".join(hits))
    with open(VERIFY, "w", encoding="utf-8") as f:
        f.write(f"备份目录: {BACKUP_ROOT}\\{stamp}\n\n" + "\n\n".join(verify))
    print(f"完成。备份于 {BACKUP_ROOT}\\{stamp}，验证详情见 {VERIFY}")


if __name__ == "__main__":
    main()
