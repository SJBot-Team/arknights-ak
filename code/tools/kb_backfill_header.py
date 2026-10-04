# -*- coding: utf-8 -*-
r"""kb_backfill_header.py — 给缺规范头部的篇目**回填** `> 层级：…　建立日期：…　任务：…`

背景（用户 2026-09-29 裁决）：知识库 130 篇里仅 47 篇有规范头部。
本工具按域分批回填，**推断值一律显式标注**（`｜推断` / `（文件时间）`），不冒充已验证标注。

规范头部格式：
    > 层级：**T2（社区口径｜推断）**　建立日期：2026-08-31（文中抓取日）　任务：—

用法：
    python kb_backfill_header.py --domain 03_外部学习            # 干跑
    python kb_backfill_header.py --domain 03_外部学习 --write    # 落盘
    python kb_backfill_header.py --domain all --write
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

KB = r'C:\Users\23922\Documents\ds_harness\ak\knowledge'
RE_LEVEL = re.compile(r'层级[：:]\s*\**\s*(T[123])')
RE_RVA = re.compile(r'0x[0-9A-Fa-f]{5,}')
CODE_WORDS = ('dump.cs', '反汇编', 'IL2CPP', 'RVA', 'GameAssembly')
RE_TASK = re.compile(r'\bT-\d{3}[a-z]?\b')
RE_DATE_FULL = re.compile(r'(20\d{2})-(\d{1,2})-(\d{1,2})')
RE_DATE_CN = re.compile(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})?\s*日?')
RE_DATE_MONTH = re.compile(r'(20\d{2})-(\d{1,2})(?!\d)')


def domain_level(rel: str, raw: str) -> tuple[str, str]:
    """返回 (层级标注, 依据说明)。证据不足时返回"待定"。"""
    rva = len(RE_RVA.findall(raw))
    cw = sum(raw.count(k) for k in CODE_WORDS)
    bili = raw.count('B 站') + raw.count('bilibili') + raw.count('录播') + raw.count('专栏')
    dom = rel.split(os.sep)[0]
    if dom.startswith('03'):
        return 'T2', '社区口径（B 站/QQ 等）'
    if dom.startswith('07'):
        return 'T1', '词条须有知识库地址（T1 为主）'
    if dom.startswith('05'):
        return 'T2', '用户本地计算文件，非客户端/代码来源'
    if dom.startswith('00_游戏'):
        return 'T2', 'PRTS 新人入门等二手资料'
    if dom.startswith('01'):
        return ('T1', '含代码/RVA 证据') if rva >= 5 else ('T2', '主要来自 PRTS 与数据表')
    if dom.startswith('02'):
        return ('T1', '含代码/RVA 证据') if rva >= 5 else ('T2', 'PRTS 子页面口径')
    base = os.path.basename(rel)
    if dom.startswith('04') and re.search(r'(目录|结论索引|资产索引|问题登记|审核报告|阶段总结|阶段性总结|执行计划|验收对照)', base):
        return 'T3', '索引/总结/审计类（导航性文档，非机制结论）'
    if dom.startswith('04'):
        if rva >= 10 or cw >= 5:
            return 'T1', f'含代码/RVA 证据（RVA {rva}，代码词 {cw}）'
        if bili >= 3:
            return 'T2', '社区资料整理'
        if re.search(r'(索引|目录|导航|资产)', os.path.basename(rel)):
            return 'T3', '索引/导航类'
        return 'T2', '数据/流程整理类（未含强代码证据）'
    return '待定', '无法从域与内容判定'


RE_DATE_LABELED = re.compile(
    r'(建立日期|建立|创建日期|创建|整理日期|整理|抓取于|抓取|更新日期|更新|拆分日期|验证日期|发布|转写|上传)'
    r'[于]?[：: ]*\**\s*(20\d{2})[-年](\d{1,2})[-月](\d{1,2})?')
RE_DATE_HEAD6 = re.compile(r'(20\d{2})-(\d{1,2})-(\d{1,2})')


def find_date(raw: str, path: str) -> tuple[str, str]:
    """优先取**带标签**的日期（建立/整理/抓取…）；否则用文件时间。
    不再"抓到正文第一个日期就用"——那会取到内容里的场次日期（已在 03 域实测踩到）。"""
    head = raw[:4000]
    m = RE_DATE_LABELED.search(head)
    if m:
        lab, y, mo, d = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        return (f'{y:04d}-{mo:02d}-{int(d):02d}' if d else f'{y:04d}-{mo:02d}'), f'文中标注（{lab}）'
    m6 = RE_DATE_HEAD6.search('\n'.join(raw.split('\n')[:6]))     # 头部 6 行内的裸日期
    if m6:
        return f'{int(m6.group(1)):04d}-{int(m6.group(2)):02d}-{int(m6.group(3)):02d}', '头部 6 行内日期'
    # 子文件：尝试继承母文件的标注日期
    mp = re.search(r'母文件[：:]\s*`([^`]+)`', raw[:3000])
    if mp:
        cand = mp.group(1).strip().replace('\\', '/')
        for pref in ('knowledge/', 'ak/knowledge/', './'):
            if cand.startswith(pref):
                cand = cand[len(pref):]
        for base in (KB, os.path.join(KB, '04_数据对应与核验'), os.path.join(KB, '03_外部学习'),
                     os.path.join(KB, '01_基础数据'), os.path.join(KB, '02_作战机制'),
                     os.path.join(KB, '00_游戏总览'), os.path.join(KB, '05_舟数据'),
                     os.path.join(KB, '07_名词对照')):
            fp = os.path.join(base, cand) if not os.path.isabs(cand) else cand
            if os.path.exists(fp):
                pm = RE_DATE_LABELED.search(open(fp, encoding='utf-8', errors='replace').read()[:3000])
                if pm:
                    y, mo, d = int(pm.group(2)), int(pm.group(3)), pm.group(4)
                    return (f'{y:04d}-{mo:02d}-{int(d):02d}' if d else f'{y:04d}-{mo:02d}'), '继承母文件标注日期'
                break
    # ★不用文件 mtime：本工具运行前刚给全库加过主题行，mtime 已被刷新，会误导
    return '—', '待补（文中无标注日期）'


def find_source(raw: str) -> str:
    m = re.search(r'来源[：:]\s*(.{0,70})', raw[:4000])
    if m:
        return m.group(1).strip().rstrip('。；')
    m = re.search(r'(https?://\S{6,60})', raw[:4000])
    return m.group(1) if m else ''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--domain', required=True, help='域目录名，或 all')
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()

    targets = []
    for root, dirs, files in os.walk(KB):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in sorted(files):
            if not f.endswith('.md') or f == '00_知识注册表.md':
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, KB)
            if a.domain != 'all' and not rel.startswith(a.domain):
                continue
            head = '\n'.join(open(p, encoding='utf-8', errors='replace').read().split('\n')[:20])
            if RE_LEVEL.search(head):
                continue
            targets.append(p)

    print(f'{"[干跑]" if not a.write else "[写入]"} 域={a.domain}，待回填 {len(targets)} 篇')
    changed = 0
    for p in targets:
        raw = open(p, encoding='utf-8', errors='replace').read()
        rel = os.path.relpath(p, KB)
        level, why = domain_level(rel, raw)
        date, dwhy = find_date(raw, p)
        tm = RE_TASK.search('\n'.join(raw.split('\n')[:8]))
        task = tm.group(0) if tm else '—'
        src = find_source(raw)
        lv_txt = f'**{level}（{why}）**' if level != '待定' else '**待定（需人工判定）**'
        date_txt = f'{date}（{dwhy}）' if date != '—' else '**—（待补）**'
        line = f'> 层级：{lv_txt}　建立日期：{date_txt}　任务：{task}'
        if src:
            line += f'　来源：{src[:60]}'
        line += '　｜　**头部为 2026-09-30 自动回填**，推断项已标注'

        lines = raw.split('\n')
        idx = next((i for i, l in enumerate(lines) if l.lstrip('\ufeff').startswith('# ')), None)
        if idx is None:
            print('  ★无 H1，跳过:', rel)
            continue
        ins = idx + 1
        if ins < len(lines) and lines[ins].startswith('> 主题：'):
            ins += 1
        lines.insert(ins, line)
        if a.write:
            open(p, 'w', encoding='utf-8').write('\n'.join(lines))
        changed += 1
        print(f'  {rel}  →  {level} / {date} / {task}')
    print(f'共处理 {changed} 篇')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
