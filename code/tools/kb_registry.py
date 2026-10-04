# -*- coding: utf-8 -*-
r"""kb_registry.py — 扫描知识库每篇头部，生成 **知识注册表**（`knowledge/00_知识注册表.md`）

用途（用户 2026-09-29 裁决 B）：
  · 一眼筛出 **T1 / T2 / T3 / ⚠️拟合 / 🔴待补** 的分布；
  · 让"动态更新"有落点——每次新增/修改后重跑本脚本即可；
  · 与 `check_kb_links.py`（结构体检）、`glossary_doctor.py`（词典体检）并列为**第三个体检工具**。

解析策略（对格式差异容错）：
  · 标题        = 首个 `# ` 行
  · 层级        = 头部 20 行内首个 `层级…T1/T2/T3`，或裸 `T1/T2/T3` 标注
  · 日期        = 头部 20 行内 `建立日期|建立|创建日期|验证日期|拆分日期|更新日期|抓取于` 后的 `YYYY-MM-DD`
  · 任务号      = 头部 20 行内首个 `T-\d{3}[a-z]?`
  · 来源/URL    = 头部 20 行内首个 `来源：`，以及首个 `http(s)://` 链接
  · 置信度计数  = 全文里 🟢 / 🟡 / 🔴 / ⚠️拟合 / ✅ 的出现次数
  · 子文件      = 头部含 "母文件" 即视为子文件

用法：python kb_registry.py [--write]   （不带 --write 只打印摘要，不落盘）
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

KB = r'C:\Users\23922\Documents\ds_harness\ak\knowledge'
OUT = os.path.join(KB, '00_知识注册表.md')

RE_LEVEL = re.compile(r'层级[：:]\s*\**\s*(T[123][^\s，。；、|*]*)')
RE_LEVEL_BARE = re.compile(r'\b(T[123])-?(实测|逆向|代码|推导|社区)?')
RE_DATE = re.compile(r'(建立日期|建立|创建日期|验证日期|拆分日期|更新日期|抓取于|抓取)[：: ]*\**\s*(\d{4}-\d{2}-\d{2})')
RE_TASK = re.compile(r'\bT-\d{3}[a-z]?\b')
RE_URL = re.compile(r'https?://[^\s）)】|，,]+')
RE_SRC = re.compile(r'来源[：:]\s*(.{0,60})')


def parse(path: str) -> dict:
    raw = open(path, encoding='utf-8', errors='replace').read()
    lines = raw.split('\n')
    head = '\n'.join(lines[:20])
    title = next((l.lstrip('# ').strip() for l in lines if l.startswith('# ')), os.path.basename(path))
    m = RE_LEVEL.search(head)
    if m:
        level = re.split(r'[（(]', m.group(1))[0].strip()      # 只留 T1/T2/T3 本体
    else:
        m2 = RE_LEVEL_BARE.search(head)
        level = (m2.group(1) + (m2.group(2) or '')) if m2 else '—'
    dm = RE_DATE.search(head)
    date = dm.group(2) if dm else ''
    tm = RE_TASK.search(head)
    task = tm.group(0) if tm else ''
    um = RE_URL.search(head)
    url = um.group(0) if um else ''
    sm = RE_SRC.search(head)
    src = (sm.group(1).strip().rstrip('。；') if sm else '')
    return {
        'path': path,
        'rel': os.path.relpath(path, KB).replace('\\', '/'),
        'domain': os.path.relpath(path, KB).split(os.sep)[0],
        'title': title[:80],
        'level': level,
        'date': date,
        'task': task,
        'url': url,
        'src': src,
        'lines': len([l for l in lines if l.strip()]),
        'is_sub': '母文件' in head,
        'green': raw.count('🟢'), 'yellow': raw.count('🟡'), 'red': raw.count('🔴'),
        'fit': raw.count('⚠️拟合') + raw.count('⚠️ 拟合'), 'ok': raw.count('✅'),
        'rva': len(re.findall(r'0x[0-9A-Fa-f]{5,}', raw)),
        'codeword': sum(raw.count(k) for k in ('dump.cs', '反汇编', 'IL2CPP', 'RVA', 'GameAssembly')),
        'prts': raw.count('PRTS') + raw.count('prts.wiki'),
        'bili': raw.count('B 站') + raw.count('bilibili') + raw.count('录播') + raw.count('专栏'),
    }


def infer_level(r: dict) -> str:
    """头部没写层级时的启发式推断（结果一律标 `(推)`，不冒充规范标注）。"""
    dom = r['domain']
    if dom.startswith('03'):
        return 'T2(推)'
    if dom.startswith('00') or dom.startswith('02') or dom.startswith('05'):
        return 'T2(推)'
    if dom.startswith('01'):
        return 'T1(推)' if r['rva'] >= 5 else 'T2(推)'
    if dom.startswith('04'):
        if r['rva'] >= 10 or r['codeword'] >= 5:
            return 'T1(推)'
        if r['bili'] >= 3:
            return 'T2(推)'
        return 'T3(推)'
    if dom.startswith('07'):
        return 'T1(推)'
    return '—'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()

    rows = []
    for root, dirs, files in os.walk(KB):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in sorted(files):
            if f.endswith('.md') and f != '00_知识注册表.md':   # 排除自身，避免自指
                rows.append(parse(os.path.join(root, f)))
    rows.sort(key=lambda r: (r['domain'], r['rel']))

    by_domain: dict[str, list] = {}
    for r in rows:
        by_domain.setdefault(r['domain'], []).append(r)

    nohead = []
    for r in rows:
        if r['level'] == '—':
            nohead.append(r)
            r['level'] = infer_level(r)
        else:
            r['level'] += '(标)'
    lv = {}
    for r in rows:
        key = (r['level'] or '—')[:2]
        lv[key] = lv.get(key, 0) + 1

    out = []
    out.append('# 00 知识注册表（自动生成，**勿手改**）\n')
    out.append(f'> 生成时间：**{datetime.now().strftime("%Y-%m-%d %H:%M")}**　生成器：`ak\\code\\tools\\kb_registry.py`')
    out.append('> **用途**：一眼筛出各篇的**层级 / 日期 / 任务号 / 来源地址 / 置信度标记密度**；改完知识库**重跑本脚本**即可刷新。')
    out.append('> **读法**：`T1`＝代码或实测验证；`T2`＝社区口径；`T3`＝推导；**`🔴`/`⚠️拟合` 的计数越高，该篇越需要复核**。')
    out.append('> **配套体检**：结构 `check_kb_links.py`（断链必须 0）｜词典 `glossary_doctor.py`｜**本表（注册表）**。\n')
    out.append(f'**总览**：{len(rows)} 篇 ｜ 层级分布 ' + ' ｜ '.join(f'{k}×{v}' for k, v in sorted(lv.items())) + '\n')
    out.append('---\n')

    for dom in sorted(by_domain):
        rs = by_domain[dom]
        out.append(f'## {dom}（{len(rs)} 篇）\n')
        out.append('| 文件 | 层级 | 日期 | 任务 | 行数 | ✅ | 🟢 | 🟡 | 🔴 | ⚠️拟合 | 来源/URL |')
        out.append('|---|---|---|---|---|---|---|---|---|---|---|')
        for r in rs:
            name = r['rel'].split('/', 1)[1] if '/' in r['rel'] else r['rel']
            name = name.replace('|', '/')
            src = (r['src'] or '')[:36] or (r['url'][:36] if r['url'] else '')
            src = src.replace('|', '/')
            tag = '📄' if r['is_sub'] else ''
            out.append(f"| {tag}`{name}` | {r['level']} | {r['date']} | {r['task']} | {r['lines']} | "
                       f"{r['ok']} | {r['green']} | {r['yellow']} | {r['red']} | {r['fit']} | {src} |")
        out.append('')

    out.append('---\n')
    out.append(f'## 附：缺规范头部的篇目（{len(nohead)} 篇，**建议逐步回填**）\n')
    out.append('> 规范头部格式：`> 层级：**T1/T2/T3（说明）**　建立日期：YYYY-MM-DD　任务：**T-0xx**`。')
    out.append('> 下表各篇的层级是**启发式推断**（标 `(推)`），请以正文实际证据为准。\n')
    for r in nohead:
        out.append(f"- `{r['rel']}`（推断 {r['level']}；RVA 数 {r['rva']}，代码词 {r['codeword']}）")
    out.append('')
    out.append('---\n')
    out.append('## 维护\n')
    out.append('1. **新增/修改知识后重跑**：`D:\\__soft\\Anaconda\\python.exe ak\\code\\tools\\kb_registry.py --write`。')
    out.append('2. **头部规范**（决定本表能不能解析出来）：每篇头部应含')
    out.append('   `> 层级：**T1/T2/T3（说明）**　建立日期：YYYY-MM-DD　任务：**T-0xx**`，社区来源另加 `来源：` 与 `URL：`。')
    out.append('3. 本表是**生成物**：手改会在下次重跑时被覆盖；要改内容请改原篇头部。')
    text = '\n'.join(out) + '\n'

    if a.write:
        open(OUT, 'w', encoding='utf-8').write(text)
        print(f'已写入 {OUT}（{len(rows)} 篇）')
    else:
        print(f'[干跑] 解析到 {len(rows)} 篇；层级分布 ' + ' ｜ '.join(f'{k}×{v}' for k, v in sorted(lv.items())))
        miss = [r['rel'] for r in rows if r['level'] == '—']
        print(f'未解析出层级的 {len(miss)} 篇：')
        for m in miss[:15]:
            print('   ', m)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
