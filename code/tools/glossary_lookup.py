# -*- coding: utf-8 -*-
"""名词对照检索器 —— **分层查询**（L0 核心区 → L1 批量表 → L2 PRTS 原文）。

用法：
  python glossary_lookup.py <关键词>      # 三层一起查（拼音/中文/代码名/俗称/任意字段）
  python glossary_lookup.py <关键词> --no-prts   # 跳过 L2，加快
  python glossary_lookup.py <关键词> --prts-limit 10
  python glossary_lookup.py --stats       # 各分节条目数
  python glossary_lookup.py --hotwords    # 导出正词热词表（一行一词）→ 喂给 whisper initial_prompt
  python glossary_lookup.py --fixes       # 导出转写纠错映射
  python glossary_lookup.py --json        # 全量导出 JSON（供程序化使用）

分层口径（**置信度从高到低**）：
  L0 `knowledge/07_名词对照/`  人工精炼词条（每条带**知识库地址**与 T1/T2 标注）
  L1 `ak\\glossary\\*.tsv`        由权威源批量生成（MAA battle_data / gamedata / 量角器枚举 / PRTS 事件表）
  L2 `ak\\_raw\\prts\\**`         **PRTS 原文**（玩家统一口径，**T2、可能出错**）——按行给命中位置，便于回查

设计原则：**只读**。新增/修改词条请编辑 `07_名词对照/*.md`（规则见其 `00_目录与用法.md`）；
批量表人工补注走 `ak\\glossary\\90_人工补注.tsv` → `glossary_backfill.py --apply`。
"""
import argparse
import json
import os
import re
import sys

AK = r'C:\Users\23922\Documents\ds_harness\ak'
GLOSSARY = os.path.join(AK, 'knowledge', '07_名词对照')
BULK = os.path.join(AK, 'glossary')
RAW_PRTS = os.path.join(AK, '_raw', 'prts')          # L2：PRTS 原文（玩家统一口径 T2）
FIELDS = ['pinyin', 'official', 'code', 'meaning', 'address', 'slang', 'note']


def search_prts(kw, limit_per_file=6, max_files=8):
    """L2 层：在 PRTS 原始页（_raw\\prts\\**\\*.txt）里按行搜关键词。
    返回 [(相对页名, [(行号, 原文), ...]), ...]。**只读**；命中行数受控，避免灌爆上下文。"""
    out = []
    if not os.path.isdir(RAW_PRTS):
        return out
    k = kw.lower()
    for root, _dirs, files in os.walk(RAW_PRTS):
        for fn in sorted(files):
            if not fn.endswith(('.txt', '.wikitext')):
                continue
            path = os.path.join(root, fn)
            try:
                lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
            except Exception:
                continue
            hit = [(i, l) for i, l in enumerate(lines, 1) if k in l.lower()]
            if hit:
                rel = os.path.relpath(path, RAW_PRTS)
                out.append((rel, hit[:limit_per_file] + ([('…', f'共 {len(hit)} 行命中')] if len(hit) > limit_per_file else [])))
                if len(out) >= max_files:
                    return out
    return out


def load_bulk():
    """读取 ak\\glossary\\*.tsv（大表区）。返回 [{表, 行号, 各列}]，只保留前 7 列 + 附加列。"""
    out = []
    if not os.path.isdir(BULK):
        return out
    for name in sorted(os.listdir(BULK)):
        if not name.endswith('.tsv'):
            continue
        path = os.path.join(BULK, name)
        with open(path, encoding='utf-8') as f:
            header = None
            for ln, line in enumerate(f, 1):
                cells = line.rstrip('\n').split('\t')
                if header is None:
                    header = cells
                    continue
                if not any(c.strip() for c in cells):
                    continue
                d = {h: (cells[i] if i < len(cells) else '') for i, h in enumerate(header)}
                d['_table'] = name
                d['_line'] = ln - 1
                out.append(d)
    return out


def show_bulk(d):
    name = d.get('官方汉语命名', '')
    cid = d.get('代码层ID', '')
    extra = ' | '.join(f'{k}={v}' for k, v in d.items()
                       if k not in ('汉语拼音', '官方汉语命名', '代码层ID', '一句话说明', '知识库地址', '玩家俗称', '来源')
                       and not k.startswith('_') and v)
    print(f'· {name}  [{cid}]   ({d["_table"]}:{d["_line"]})')
    if d.get('一句话说明') or d.get('知识库地址'):
        print(f'    含义/地址: {d.get("一句话说明","")} {d.get("知识库地址","")}')
    if extra:
        print(f'    {extra[:220]}')


def rows_of(path):
    """抽取 markdown 表格行，返回等长于 FIELDS 的 dict 列表。"""
    out = []
    with open(path, encoding='utf-8-sig') as f:
        for ln, line in enumerate(f, 1):
            s = line.strip()
            if not s.startswith('|') or set(s) <= set('|-: '):
                continue
            cells = [c.strip() for c in s.strip('|').split('|')]
            if len(cells) == len(FIELDS):
                d = dict(zip(FIELDS, cells))
                if d['pinyin'] in ('汉语拼音',) or d['pinyin'].startswith('---'):
                    continue
                d['_file'] = os.path.basename(path)
                d['_line'] = ln
                out.append(d)
    return out


def other_rows(path):
    """非 7 列格式的表格行（如 05 转写纠错表的 5 列）——只用于统计与 --fixes。"""
    out = []
    with open(path, encoding='utf-8-sig') as f:
        header = None
        for ln, line in enumerate(f, 1):
            s = line.strip()
            if not s.startswith('|') or set(s) <= set('|-: '):
                header = None
                continue
            cells = [c.strip() for c in s.strip('|').split('|')]
            if header is None:
                header = cells
                continue
            if len(cells) == len(header):
                out.append((header, cells))
    return out


def load_all():
    entries = []
    for name in sorted(os.listdir(GLOSSARY)):
        if name.endswith('.md') and not name.startswith('00_'):
            entries += rows_of(os.path.join(GLOSSARY, name))
    return entries


def is_placeholder(v):
    return ('🔴' in v) or ('待确认' in v) or ('待补' in v) or ('待核' in v)


def search(entries, kw):
    kw = kw.lower()
    hits = []
    for e in entries:
        blob = ' '.join(e[f] for f in FIELDS).lower()
        if kw in blob:
            hits.append(e)
    return hits


def show(e):
    print(f"── {e['official']}  [{e['pinyin']}]   ({e['_file']}:{e['_line']})")
    print(f"   代码名 : {e['code']}")
    print(f"   含义   : {e['meaning']}")
    print(f"   地址   : {e['address']}")
    if e['slang'] and e['slang'] != '—':
        print(f"   俗称   : {e['slang']}")
    if e['note'] and e['note'] != '—':
        print(f"   注意   : {e['note']}")


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('keyword', nargs='?')
    ap.add_argument('--stats', action='store_true')
    ap.add_argument('--hotwords', action='store_true')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--fixes', action='store_true')
    ap.add_argument('--no-prts', action='store_true', help='跳过 L2（PRTS 原文）层，加快查询')
    ap.add_argument('--prts-limit', type=int, default=6, metavar='N', help='L2 每个页面最多显示 N 行命中（默认 6）')
    a = ap.parse_args()

    if not os.path.isdir(GLOSSARY):
        print('未找到名词对照目录：' + GLOSSARY); return 1
    entries = load_all()

    if a.stats:
        from collections import Counter
        c = Counter(e['_file'] for e in entries)
        for k in sorted(c):
            print(f'{c[k]:>4} 条  {k}')
        print(f'{len(entries):>4} 条  合计（7 列词条）')
        fix = os.path.join(GLOSSARY, '05_转写纠错表.md')
        if os.path.exists(fix):
            print(f'{len(other_rows(fix)):>4} 条  05_转写纠错表.md（5 列：误写→正词，另行统计）')
        return 0

    if a.hotwords:
        seen, out = set(), []
        for e in entries:
            # 去掉 markdown 标记：喂给 ASR 的必须是**纯词**（否则模型可能吐出 `**晕眩**`）
            v = e['official'].replace('**', '').replace('`', '').strip()
            if is_placeholder(v) or v in seen or len(v) < 2:
                continue
            # 只导出"像专名"的正词：中文/英文且不含解释性标点
            if any(ch in v for ch in '（）()/、，,：:→'):
                continue
            seen.add(v); out.append(v)
        print('\n'.join(out))
        return 0

    if a.json:
        print(json.dumps(entries, ensure_ascii=False, indent=1))
        return 0

    if a.fixes:
        fix = os.path.join(GLOSSARY, '05_转写纠错表.md')
        clean = lambda s: s.replace('**', '').replace('`', '').strip()
        n = 0
        for header, cells in other_rows(fix):
            if len(cells) >= 2:
                bad, good = clean(cells[0]), clean(cells[1])
                if is_placeholder(good) or bad.startswith('误写') or good == '正词':
                    continue
                print(f'{bad}\t=>\t{good}')
                n += 1
        print(f'# 共 {n} 条已确认映射（存疑项已跳过）', file=sys.stderr)
        return 0

    if not a.keyword:
        ap.print_help()
        return 0

    hits = search(entries, a.keyword)
    bulk = load_bulk()
    bhits = [d for d in bulk if a.keyword.lower() in ' '.join(str(v) for v in d.values()).lower()]
    phits = [] if a.no_prts else search_prts(a.keyword, limit_per_file=a.prts_limit)
    if not hits and not bhits and not phits:
        print(f'未找到「{a.keyword}」。')
        print('提示：可试拼音（zudang）、官方名（阻挡）、代码名（BlockBalancer/char_123_fang）或俗称（挤位）。')
        print('若确认是新词条 → 按 07_名词对照/00_目录与用法.md §二、§四 登记（机制词）或补进 ak\\glossary 批量表。')
        return 1
    print('查询分层：L0 核心区（人工精炼）→ L1 批量表（生成物）→ L2 PRTS 原文（玩家统一口径 T2）\n')
    if hits:
        print(f'【L0 核心区 knowledge/07】命中 {len(hits)} 条：\n')
        for e in hits:
            show(e); print()
    if bhits:
        print(f'【L1 批量表 ak\\glossary】命中 {len(bhits)} 条（只显示前 30）：')
        for d in bhits[:30]:
            show_bulk(d)
        if len(bhits) > 30:
            print(f'  … 另有 {len(bhits) - 30} 条。要精确定位请指定更长的关键词，或直接打开对应 tsv 用 Ctrl+F。')
        print()
    if phits:
        print(f'【L2 PRTS 原文 _raw\\prts】命中 {len(phits)} 个页面（各页最多 {a.prts_limit} 行；原文属 T2、可能出错）：')
        for page, lines in phits:
            print(f'  · {page}  （{len(lines)} 行命中）')
            for ln, txt in lines:
                t = txt.strip()
                if len(t) > 150:
                    t = t[:150] + '…'
                print(f'      L{ln}: {t}')
        print('    ⚠️ 引用 PRTS 原文时须带页名；与代码结论冲突时**两侧都留**（用户规则）。')
    elif not a.no_prts:
        print('【L2 PRTS 原文】无命中（可用 --no-prts 跳过该层以加速）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
