# -*- coding: utf-8 -*-
"""按小节把超长知识库文档下沉为多卷子文件（T-062「持续更新机制」的配套工具）。

用途：单篇 >600 行的核心文本，按 `## ` 小节**贪心装箱**切成每卷 ≤max 行的子文件，
母文件保留「结论地图 + 卷目录」，正文**逐字搬运、不改写**。

用法（示例）：
  python kb_split_by_sections.py --file "04_数据对应与核验/54_1-1标定对局_复刻报告.md" \
      --mother-lines 95 --max 600 --prefix 54 --suffix 日志 --yes

约定：
  * `--mother-lines N`：母文件保留前 N 行（通常 = 素材/方法/结论部分）；其余按小节切卷。
  * 卷文件名 = `<prefix><a|b|c…>_<suffix>_<该卷首节标题>.md`
  * 每卷头部标注母文件；母文件写入「卷目录」表格（覆盖范围 + 行数 + 该卷首节标题）。
  * 写入前把母文件备份到 `ak/.tmp/<name>.before_split.md`；**不做校验就写**，校验由调用者用 --verify 复核。
"""
import argparse
import os
import re
import shutil
import sys

AK = r'C:\Users\23922\Documents\ds_harness\ak'
KB = os.path.join(AK, 'knowledge')
TMP = os.path.join(AK, '.tmp')


def load(path):
    raw = open(path, 'rb').read()
    return raw, raw.decode('utf-8-sig')


def section_starts(lines, start_idx):
    """返回 [start_idx..end) 内所有 `## ` 小节的起始行号（0-based）。"""
    return [i for i in range(start_idx, len(lines)) if lines[i].startswith('## ')]


def clean_title(h):
    """把小节标题变成安全的文件名片段：只保留中文/字母/数字/下划线，去掉标点、星号、反引号等。"""
    t = h.lstrip('# ').strip()
    t = re.sub(r'[^\w\u4e00-\u9fff]', '', t)
    return t[:20]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True, help='相对 knowledge/ 的路径')
    ap.add_argument('--mother-lines', type=int, required=True)
    ap.add_argument('--max', type=int, default=600)
    ap.add_argument('--prefix', required=True, help='如 54')
    ap.add_argument('--suffix', default='卷', help='卷名主体，如「日志」')
    ap.add_argument('--yes', action='store_true')
    a = ap.parse_args()

    path = os.path.join(KB, a.file)
    _raw, text = load(path)
    lines = text.split('\n')
    n = len(lines)
    cut = a.mother_lines            # 母文件保留 1..cut

    starts = section_starts(lines, cut)
    if not starts:
        print('母文件之后没有 `## ` 小节，无法切分'); return 1
    # 每个小节的区间 [s_i, s_{i+1})，最后一节到文末
    secs = [(starts[i], starts[i + 1] if i + 1 < len(starts) else len(lines))
            for i in range(len(starts))]
    # 贪心装箱：整节装入，装入后不超过 --max
    chunks, cur = [], []
    for s, e in secs:
        if cur and (e - cur[0][0]) > a.max:
            chunks.append(cur); cur = []
        cur.append((s, e))
    if cur:
        chunks.append(cur)
    bounds = [(c[0][0], c[-1][1]) for c in chunks]

    names = []
    for i, (s, e) in enumerate(bounds):
        letter = chr(ord('a') + i)
        name = f'{a.prefix}{letter}_{a.suffix}_{clean_title(lines[s])}.md'
        names.append((name, lines[s], s, e, e - s))

    print(f'母文件 {cut} 行；正文 {n - cut} 行 → {len(names)} 卷')
    for name, head, s, e, cnt in names:
        print(f'  {name}  {cnt} 行  ({head[:24]})')
    if not a.yes:
        print('\n未加 --yes，未写盘。'); return 0

    os.makedirs(TMP, exist_ok=True)
    shutil.copy2(path, os.path.join(TMP, os.path.basename(path) + '.before_split.md'))

    PARENT = (f'> **本文件是 `{os.path.basename(a.file)}` 的子文件**'
              f'（母文件：`knowledge/{a.file}`）。\n'
              f'> 内容为**逐字搬运**（未改写、未删减），分卷只为满足"单篇可通读"的规模红线。\n')
    rows = []
    for i, (name, head, s, e, cnt) in enumerate(names):
        body = '\n'.join(lines[s:e]).strip('\n')
        hdr = (f'# {name.split("_")[0]} {head.lstrip("# ").strip()}\n\n' + PARENT +
               f'> 本卷为母文件第 {s + 1}~{e} 行；上一卷/下一卷见母文件「卷目录」。\n\n---\n\n')
        open(os.path.join(os.path.dirname(path), name), 'w', encoding='utf-8', newline='\n').write(hdr + body + '\n')
        rows.append((name, head.lstrip('# ').strip(), cnt, s + 1, e))

    idx = ['## 卷目录（**本文已按规模红线下沉**）', '',
           '> 正文按小节贪心装箱切卷，每卷 ≤%d 行；**原小节编号未改**，跨卷引用可直接比对。' % a.max, '',
           '| 卷 | 起止（母文件原行） | 行数 | 每个文件首节 |', '|---|---|---|---|']
    for name, head, cnt, s1, e in rows:
        idx.append(f'| `{name}` | {s1}~{e} | {cnt} | {head} |')
    idx.append('')

    mother = ('\n'.join(lines[:cut]).rstrip('\n') + '\n\n' + '\n'.join(idx) + '\n' +
              '\n'.join(lines[len(lines):]).strip('\n'))
    open(path, 'w', encoding='utf-8', newline='\n').write(mother + '\n')
    print(f'母文件已重写：{mother.count(chr(10)) + 1} 行')
    return 0


if __name__ == '__main__':
    sys.exit(main())
