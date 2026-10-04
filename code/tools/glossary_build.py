# -*- coding: utf-8 -*-
"""名词对照「批量表」生成器（数据源 → ak\\glossary\\*.tsv）。

设计约定（见 ak\\glossary\\README.md）：
  * **大表不进知识库核心**（knowledge/ 只留人工精炼的小表 + 指针）；
  * 统一 7 列主 schema：`拼音 | 官方汉语命名 | 代码层ID | 一句话说明 | 知识库地址 | 玩家俗称 | 来源`
    其中 **一句话说明 / 知识库地址 留空**（两列必须成对回填，写不出地址就不写说明）；
  * 额外信息放**附加列**（多语言名、职业、稀有度、描述、备注…），不污染主 schema；
  * **拼音由本脚本生成**（`pypinyin` + 人工兜底表 `PINYIN_OVERRIDE` / `PINYIN_HOLD`）；
  * **玩家俗称只登记"知识库里有出处"的叫法**（`NICKNAMES`），来源不明的标 🟡；
  * **装置/陷阱/召唤物不进 `01_干员.tsv`**（按 `trap_*` / `token_*` / 职业 TRAP·TOKEN 拆到 `01a`）。

用法：
  python glossary_build.py                 # 生成全部表 + 索引 + 抽样自检
  python glossary_build.py --check         # 只对已有表做抽样自检（不重写）
  python glossary_build.py --only 01,03    # 只重写指定编号的表（其余不动）
  python glossary_build.py --audit-pinyin  # 只导出"拼音需人工复核"的候选清单
"""
import argparse
import json
import os
import re
import sys
import time

try:                       # 拼音依赖（python -m pip install pypinyin）
    from pypinyin import lazy_pinyin
except ImportError:        # 没装时**必须拒绝写盘**（见 main 的守卫），否则会静默把整列拼音清空
    lazy_pinyin = None
    print('[!] 未安装 pypinyin —— 拼音列会退化为"只有兜底表"，**不会写盘**。'
          '\n    请用带 pypinyin 的解释器，例如：D:\\__soft\\Anaconda\\python.exe',
          file=sys.stderr)

AK = r'C:\Users\23922\Documents\ds_harness\ak'
OUT = os.path.join(AK, 'glossary')
KB = os.path.join(AK, 'knowledge')

SRC = {
    'maa_battle_data': r'D:\__soft\MAA\resource\battle_data.json',
    'prts_battle_data': r'D:\__soft\ak\prts+\_internal\resource\battle_data.json',
    'operator_mapping': r'D:\__soft\ak\prts+\_internal\resource\operator_mapping.json',
    'level_name_mapping': r'D:\__soft\ak\prts+\_internal\resource\level_name_mapping.json',
    'level_code_mapping': r'D:\__soft\ak\prts+\_internal\resource\level_code_mapping.json',
    'anne_dictionary': r'E:\__file\ak_kb\downloads\量角器\translation\anne_dictionary.json',
    'bena_dictionary': r'E:\__file\ak_kb\downloads\量角器\translation\bena_dictionary.json',
    'enemy_handbook': os.path.join(AK, 'data', 'gamedata_akgd', 'enemy_handbook_table.json'),
}

MAIN_HEADER = ['汉语拼音', '官方汉语命名', '代码层ID', '一句话说明', '知识库地址', '玩家俗称', '来源']
BLANK = ['', '', '', '', '', '', '']

# ============================================================
# 拼音：人工兜底（**多音字/专名读音**；每条都要写得出理由）
# ============================================================
PINYIN_OVERRIDE = {
    # --- 术语（本身不是表内行，供未来"职业/分支术语表"复用，用户 2026-09-23 点名）---
    '重装': 'zhongzhuang',      # 职业（zhòng zhuāng）
    '行商': 'hangshang',        # 分支（háng shāng，不是 xíng）
    # --- 专名（pypinyin 默认读音与官方英文名/官方读法不符，用英文名交叉校验）---
    '重岳': 'chongyue',         # name_en = Chongyue → 重 = chóng（pypinyin 默认给 zhongyue）
    # --- 官方名确认无误但曾被点名复核的，登记为"已核"（防止后人重新纠结）---
    '巡林者': 'xunlinzhe',
    '浊心斯卡蒂': 'zhuoxinsikadi',
    '黍': 'shu',
    '嵯峨': 'cuoe',
    '澄闪': 'chengshan',
    '涤火杰西卡': 'dihuojiexika',
    '缄默德克萨斯': 'jianmodekesasi',
    '齐尔查克': 'qierchake',
}
# 明确"拿不准"的：留空 + 备注「拼音待核」，**不许瞎填**
PINYIN_HOLD = {
    '薄绿',        # 薄 báo / bó 两读（颜色词多为 bó），无官方读音出处
    '法术：同行',   # 同行 tóngxíng（同伴）/ tóngháng（同业）两读，游戏内无读音出处
    '“越长尘”',    # 运兵车专名，长 cháng / zhǎng 两读，无官方读音出处
    '言省',        # 省 shěng / xǐng 两读（图鉴描述"映照对方心中隐秘"疑取 xǐng），无出处
}
# **词级读音兜底**：pypinyin 的成词判断在这些词上出错（含该词的专名一律受益）
PINYIN_WORD_FIX = {
    '重构': 'chonggou',    # 重构体 = Reconstruction（chóng），pypinyin 给 zhòng
    '重整': 'chongzheng',  # 重整导能组件（chóng）
    '长椅': 'changyi',     # 休闲长椅 / 简约长椅（cháng），pypinyin 给 zhǎng
    '长距': 'changju',     # 长距增运改装（cháng）
    '长臂': 'changbi',     # 长臂投手（cháng）
    '弹跳': 'tantiao',     # “弹跳独轮车”（tán），pypinyin 给 dàn
    '着铠': 'zhuokai',     # 乌萨斯着铠术师（zhuó，着装之"着"）
    '重犯': 'zhongfan',    # 重犯 / 传奇重犯（zhòng，图鉴描述"凶恶囚犯"）
}

# ============================================================
# 玩家俗称（**只登记知识库里确实出现过的叫法**；第三项 False = 目标干员是推断 ⇒ 标 🟡）
# ============================================================
NICKNAMES = {
    'char_1028_texas2': [('翼德', '03_外部学习/22b §4.2（易德/一德 → 翼德（缄默德克萨斯））', True)],
    'char_151_myrtle': [('桃子', '03_外部学习/22b §4.2（陶金娘/桃子 → 桃金娘）', True)],
    'char_102_texas': [('德狗', '03_外部学习/21 §1.7（宿舍换班案例：德克萨斯↔德狗 同指）', True)],
    'char_300_phenxi': [('肥鸭', '03_外部学习/21 §1.7（标题「为何你的肥鸭总是睡错人」＋正文「菲亚梅塔基建技能」）', True)],
    'char_350_surtr': [('42', '03_外部学习/20a §1.8（「42 自动撤回」＝ 史尔特尔 3 技能结束退场）', False)],
    'char_4064_mlynar': [('叔叔', '03_外部学习/22a §1.1（「决战技（切模式）：叔叔 3/水陈 3/EW 3…」）', False)],
    'char_1013_chen2': [('水陈', '03_外部学习/22a §1.1（同上句）', False)],
    'char_1035_wisdel': [('EW', '03_外部学习/22a §1.1、26a N-49（「EW 三段全有」）', False)],
    'char_1021_kroos2': [('寒克', '03_外部学习/21 §A.2（「高攻速连击系（寒克）」）', False)],
    'char_134_ifrit': [('小火龙', '03_外部学习/20a（「放置干员时对前方小火龙范围内所有单位造成法术伤害」）', False)],
    'char_2013_cerber': [('小刻', '03_外部学习/21 §1.7（基建技能「小刻『等不急』」）', False)],
    'char_124_kroos': [('kkdy', '03_外部学习/21 §1.7（基建技能「kkdy『慢性子』」）', False)],
}

CJK = re.compile(r'[\u3400-\u9fff]')
# 多音字/易错字（拼音复核用；只用于"捞出来给人看"，不参与自动改写）
RISK_CHARS = set(
    '重行长者干发分缝供勾骨冠好号和喝横还几给家夹便熟削咽扎占折正钻薄暴背奔辟遍屏泊禁称乘匙臭畜创绰'
    '都省藏曾冲待担单当倒得度恶降教结解角觉空乐了累量落没难宁迫曲散扫舍数说缩弹提调挑吐系相兴血应'
    '与载攒涨着只中转强秘卡摩塞劈喷铺圈雀嚷默没处传更假间任乌丽华查差朝乘澄宿佛否干给还几假间')
# 真正要紧的一小撮：**同字不同声母/韵母**（拼音无声调 ⇒ 只有这类字会让拼音列写错）
RISK_NARROW = set('重行长着角血薄系说弹调提都省藏乐落卡塞降解折朝佛否查差宿得恶雀没传曾和还给便削称匙畜娜堡壳咖勒笼露络埋脉冒模抹鸟弄奇茄铅朴蜡蔓泊咽')

_trap_ids = ('trap_', 'token_')
_device_prof = ('TRAP', 'TOKEN')


def row(official='', cid='', src='', extras=()):
    """按主 schema 组装一行：拼音/一句话/地址/俗称 先留空，来源进第 7 列，附加信息接在后面。"""
    return ['', clean(official), clean(cid), '', '', '', clean(src)] + [clean(e) for e in extras]


def load(key):
    p = SRC[key]
    if not os.path.exists(p):
        print(f'  [!] 缺源：{p}')
        return None
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def clean(v):
    if v is None:
        return ''
    return str(v).replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').strip()


def write_tsv(name, header, rows):
    path = os.path.join(OUT, name)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(header) + '\n')
        for r in rows:
            f.write('\t'.join(clean(c) for c in r) + '\n')
    print(f'  写出 {name}: {len(rows)} 行')
    return len(rows)


# ---------------- 拼音 ----------------

def _split_by_wordfix(name):
    """按 PINYIN_WORD_FIX 长词优先切分：[(片段, 是否走词级读音)]。"""
    keys = sorted(PINYIN_WORD_FIX, key=len, reverse=True)
    segs, buf, i = [], '', 0
    while i < len(name):
        hit = next((k for k in keys if name.startswith(k, i)), None)
        if hit:
            if buf:
                segs.append((buf, False)); buf = ''
            segs.append((hit, True)); i += len(hit)
        else:
            buf += name[i]; i += 1
    if buf:
        segs.append((buf, False))
    return segs


def _py_segment(text):
    """一段文本 → 拼音；含无法转换的汉字时返回 None。"""
    if not CJK.search(text):
        return re.sub(r'[^0-9a-z]', '', text.lower())
    parts = lazy_pinyin(text)
    if any(CJK.search(p) for p in parts):
        return None
    return ''.join(parts)


def pinyin_of(name):
    """返回 (拼音, 备注)。规则见 glossary/README.md §七。"""
    name = clean(name)
    if not name:
        return '', ''
    if name in PINYIN_OVERRIDE:
        return PINYIN_OVERRIDE[name], ''
    if name in PINYIN_HOLD:
        return '', '拼音待核'
    if not CJK.search(name):
        return re.sub(r'[^0-9a-z]', '', name.lower()), '非中文名（拼音列填小写原名，只为统一检索）'
    if lazy_pinyin is None:
        return '', '拼音待核（未安装 pypinyin：python -m pip install pypinyin）'
    out = []
    for text, fixed in _split_by_wordfix(name):
        if fixed:
            out.append(PINYIN_WORD_FIX[text])
            continue
        seg = _py_segment(text)
        if seg is None:
            miss = ''.join(c for c in text if CJK.search(c))
            return '', f'拼音待核（pypinyin 无「{miss}」读音）'
        out.append(seg)
    return re.sub(r'[^0-9a-z]', '', ''.join(out).lower()), ''


def annotate_pinyin(header, rows, name_idx=1, note_idx=None):
    """给表补第 1 列拼音（以及备注列的「拼音待核」）。返回统计 dict。"""
    stat = {'filled': 0, 'blank': 0, 'hold': 0, 'nonhan': 0}
    for r in rows:
        py, note = pinyin_of(r[name_idx])
        r[0] = py
        if py:
            stat['filled'] += 1
        else:
            stat['blank'] += 1
        if '拼音待核' in note:
            stat['hold'] += 1
        if '非中文名' in note:
            stat['nonhan'] += 1
        if note and note_idx is not None:
            r[note_idx] = (r[note_idx] + '；' + note).strip('；') if r[note_idx] else note
    return stat


def annotate_nicknames(rows, id_idx=2, slang_idx=5, note_idx=None):
    """给表补第 6 列玩家俗称 + 出处（进备注列）。返回条数。"""
    n = 0
    for r in rows:
        hits = NICKNAMES.get(r[id_idx])
        if not hits:
            continue
        slang, src, confirmed = hits[0]
        r[slang_idx] = slang if confirmed else slang + ' 🟡'
        if note_idx is not None:
            tag = '' if confirmed else '（🟡 目标干员为按语境推断）'
            note = f'俗称「{slang}」出处：{src}{tag}'
            r[note_idx] = (r[note_idx] + '；' + note) if r[note_idx] else note
        n += 1
    return n


# ---------------- 各表 ----------------

_UNIT_CACHE = {}


def load_units():
    """读 MAA battle_data.json，按"真干员 / 装置·陷阱·召唤物"分流（缓存）。"""
    if 'ops' in _UNIT_CACHE:
        return _UNIT_CACHE['ops'], _UNIT_CACHE['dev']
    m = load('maa_battle_data')
    ops, dev = [], []
    if m:
        src = 'MAA resource/battle_data.json · chars'
        for cid, v in sorted(m['chars'].items()):
            if not isinstance(v, dict):
                continue
            rid = v.get('rangeId')
            rid = '/'.join(rid) if isinstance(rid, list) else rid
            r = row(v.get('name'), cid, src, [
                v.get('name_en'), v.get('name_jp'), v.get('name_kr'), v.get('name_tw'),
                v.get('profession'), v.get('subProfessionId'), v.get('position'),
                v.get('rarity'), rid, v.get('sortIndex'), '',
            ])
            prof = v.get('profession') or ''
            if str(cid).startswith(_trap_ids) or prof in _device_prof:
                dev.append(r)
            else:
                ops.append(r)
    _UNIT_CACHE['ops'], _UNIT_CACHE['dev'] = ops, dev
    return ops, dev


UNIT_EXTRA = ['英文名', '日文名', '韩文名', '繁中名', '职业', '分支', '位置', '星级', '攻击范围ID', '排序号', '备注']
UNIT_HEADER = MAIN_HEADER + UNIT_EXTRA


def build_operators():
    """01：**只留真干员**（`char_*`）；装置/陷阱/召唤物走 01a。"""
    ops, _dev = load_units()
    annotate_pinyin(UNIT_HEADER, ops, name_idx=1, note_idx=len(UNIT_HEADER) - 1)
# NICKNAMES 已迁移到 90_人工补注.tsv（overlay），见 README §十
#     annotate_nicknames(ops, id_idx=2, slang_idx=5, note_idx=len(UNIT_HEADER) - 1)
    return UNIT_HEADER, ops


def build_devices():
    """01a：装置/陷阱/召唤物（职业 TRAP·TOKEN 或 ID `trap_*`/`token_*`），同 schema。"""
    _ops, dev = load_units()
    annotate_pinyin(UNIT_HEADER, dev, name_idx=1, note_idx=len(UNIT_HEADER) - 1)
# NICKNAMES 已迁移到 90_人工补注.tsv（overlay），见 README §十
#     annotate_nicknames(dev, id_idx=2, slang_idx=5, note_idx=len(UNIT_HEADER) - 1)
    return UNIT_HEADER, dev


def build_operator_alias():
    d = load('operator_mapping')
    rows = []
    src = 'prts+ _internal/resource/operator_mapping.json'
    if d:
        for alias, ids in sorted(d.items()):
            rows.append(row(alias, ','.join(ids) if isinstance(ids, list) else ids, src, ['']))
    header = MAIN_HEADER + ['备注']
    annotate_pinyin(header, rows, name_idx=1, note_idx=len(header) - 1)
    return header, rows


def build_enemies():
    d = load('enemy_handbook')
    rows = []
    src = 'gamedata enemy_handbook_table.json · enemyData'
    if d and 'enemyData' in d:
        for eid, v in sorted(d['enemyData'].items()):
            rows.append(row(v.get('name'), eid, src, [
                v.get('enemyIndex'), v.get('enemyLevel'), v.get('attackType'),
                v.get('race'), (v.get('description') or '')[:160], '',
            ]))
    header = MAIN_HEADER + ['图鉴号', '等级', '攻击类型', '种族', '官方描述(截断)', '备注']
    annotate_pinyin(header, rows, name_idx=1, note_idx=len(header) - 1)
# NICKNAMES 已迁移到 90_人工补注.tsv（overlay），见 README §十
#     annotate_nicknames(rows, id_idx=2, slang_idx=5, note_idx=len(header) - 1)
    # 种族列保持留空：本地 gamedata 的 enemyData 没有 race/raceId，无法 join（见 README §六，勿逐行填占位符）
    return header, rows


def build_levels():
    nm = load('level_name_mapping') or {}
    cd = load('level_code_mapping') or {}
    by_file = {}
    for name, fn in nm.items():
        by_file.setdefault(fn, {})['name'] = name
    for code, fn in cd.items():
        by_file.setdefault(fn, {})['code'] = code
    rows = []
    src = 'prts+ level_name_mapping.json + level_code_mapping.json'
    for fn, v in sorted(by_file.items()):
        rows.append(row(v.get('name') or v.get('code') or fn, fn, src, [v.get('name'), v.get('code')]))
    return MAIN_HEADER + ['关卡名', '关卡代号'], rows


def build_enums():
    rows = []
    for key, fname, label in [('anne_dictionary', 'anne_dictionary.json', '量角器'),
                              ('bena_dictionary', 'bena_dictionary.json', '量角器')]:
        d = load(key)
        if not d:
            continue
        for cat, mp in sorted(d.items()):
            if not isinstance(mp, dict):
                continue
            for k, v in sorted(mp.items()):
                rows.append(row(v, k, f'{label} translation/{fname}', [cat]))
    return MAIN_HEADER + ['枚举分类'], rows


def build_ranges():
    m = load('maa_battle_data')
    rows = []
    src = 'MAA resource/battle_data.json · ranges'
    if m:
        for rid, cells in sorted(m['ranges'].items()):
            rows.append(row('', rid, src, ['', len(cells) if hasattr(cells, '__len__') else '',
                                           json.dumps(cells, ensure_ascii=False)]))
    return MAIN_HEADER + ['攻击范围名', '格子数', '格子坐标'], rows


TABLES = [
    ('01_干员.tsv', build_operators, '干员（**只含真干员 `char_*`**；多语言名、职业、分支、星级、攻击范围）'),
    ('01a_装置与陷阱.tsv', build_devices, '装置/陷阱/召唤物（职业 TRAP·TOKEN 或 ID `trap_*`/`token_*`；同 schema）'),
    ('02_干员名别名.tsv', build_operator_alias, '中文别名/变体写法 → char id（如「阿米娅-WARRIOR」，含装置类别名）'),
    ('03_敌人.tsv', build_enemies, '敌人（图鉴号、等级、攻击类型、种族、官方描述）'),
    ('04_关卡.tsv', build_levels, '关卡（中文名 ↔ 关卡代号 ↔ 关卡文件名）'),
    ('05_枚举词典.tsv', build_enums, '量角器枚举翻译（compare/target/event/abnormal/attribute…）'),
    ('06_攻击范围.tsv', build_ranges, '攻击范围形状（rangeId → 格子坐标表）'),
]

PINYIN_TABLES = ('01_干员.tsv', '01a_装置与陷阱.tsv', '02_干员名别名.tsv', '03_敌人.tsv', '07_职业与分支.tsv')
# 不由本脚本生成、但属于本目录的表（索引里必须列出，否则"表清单"会骗人）
EXTRA_TABLES = [
    ('07_职业与分支.tsv', '职业/分支：`subProfDict` → 中文（人工/他脚本产出，本脚本**只**能补其拼音）'),
    ('90_人工补注.tsv', '人工补注 overlay（第 4/5/6 列的**持久真源**，由 `glossary_backfill.py --apply` 套用）'),
]


def write_index(counts, samples, pystat):
    p = os.path.join(OUT, '00_索引.md')
    lines = ['# 名词对照 · 批量表索引（**大表区，不进知识库核心**）', '',
             '> 生成：%s（`ak\\code\\tools\\glossary_build.py`）' % time.strftime('%Y-%m-%d %H:%M'),
             '> 主 schema（7 列）：`汉语拼音 | 官方汉语命名 | 代码层ID | 一句话说明 | 知识库地址 | 玩家俗称 | 来源`',
             '> **「一句话说明 / 知识库地址」两列仍留空**：按回填规则，两列必须成对出现，写不出知识库地址就不写说明。',
             '> **「汉语拼音」已由脚本生成**（`pypinyin` + `PINYIN_OVERRIDE` 人工兜底）；「玩家俗称」只登记知识库里有出处的叫法，推断项标 🟡。',
             '> 阅读规则见 `README.md`；**不要通读本目录**，用 `glossary_lookup.py` 查，或按 §表清单 打开对应 tsv 用查找定位。', '',
             '## 表清单', '', '| 文件 | 行数 | 内容 |', '|---|---|---|']
    for name, _fn, desc in TABLES:
        lines.append(f'| `{name}` | {counts.get(name, 0)} | {desc} |')
    for name, desc in EXTRA_TABLES:
        n = len(load_tsv(name)[1] or []) if os.path.exists(os.path.join(OUT, name)) else '—'
        lines.append(f'| `{name}` | {n} | {desc} |')
    lines += ['', '## 拼音覆盖（只对填了拼音的表统计）', '',
              '| 表 | 已填 | 留空 | 其中「拼音待核」 | 其中「非中文名」 |', '|---|---|---|---|---|']
    for name in PINYIN_TABLES:
        s = pystat.get(name)
        if not s:
            continue
        lines.append(f'| `{name}` | {s["filled"]} | {s["blank"]} | {s["hold"]} | {s["nonhan"]} |')
    lines += ['', '## 抽样自检（生成时自动跑）', '']
    for s in samples:
        lines.append(f'- {s}')
    lines += ['', '## 数据源', '']
    for k, v in SRC.items():
        lines.append(f'- `{k}` → `{v}`' + ('' if os.path.exists(v) else '  ⚠️ **当前不存在**'))
    lines += ['', '## 回填规则（后续轮次）', '',
              '1. 某词条在知识库里有了明确结论 → 回填该行的**「一句话说明」+「知识库地址」**（两列必须同时有）；',
              '2. 玩家俗称 → 只登记**确实见到**的叫法，来源不明的标 🟡；',
              '3. 拼音 → 由脚本生成；多音字走 `PINYIN_OVERRIDE`，拿不准的进 `PINYIN_HOLD`（留空 + 备注「拼音待核」）；',
              '4. **不要**在本目录写长篇说明——说明属于 `knowledge/07_名词对照/`（人工精炼区）。', '']
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'  写出 00_索引.md')


def load_tsv(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return None, None
    with open(p, encoding='utf-8') as f:
        lines = [l.rstrip('\n').split('\t') for l in f if l.strip()]
    return lines[0], lines[1:]


def pinyin_stats_from_tables():
    """从已生成的表回收拼音覆盖统计（供 00_索引.md）。"""
    stat = {}
    for name in PINYIN_TABLES:
        h, rows = load_tsv(name)
        if not rows:
            continue
        s = {'filled': 0, 'blank': 0, 'hold': 0, 'nonhan': 0}
        for r in rows:
            if r[0]:
                s['filled'] += 1
            else:
                s['blank'] += 1
            note = r[-1] if len(r) > 7 else ''
            if '拼音待核' in note:
                s['hold'] += 1
            if '非中文名' in note:
                s['nonhan'] += 1
        stat[name] = s
    return stat


def check():
    """抽样自检：用已知事实验证表可用。"""
    res = []
    ok = True

    def bad(msg):
        nonlocal ok
        ok = False
        res.append('❌ ' + msg)

    def good(msg):
        res.append('✅ ' + msg)

    h, rows = load_tsv('01_干员.tsv')
    if rows:
        m = {r[2]: r for r in rows}
        for cid, want in [('char_123_fang', '芬'), ('char_002_amiya', '阿米娅')]:
            r = m.get(cid)
            (good if (r and r[1] == want) else bad)(
                f'干员: `{cid}` → 「{r[1] if r else "?"}」（期望「{want}」）')
        trap = [r for r in rows if r[2].startswith(('trap_', 'token_')) or r[11] in _device_prof]
        (good if not trap else bad)(f'干员表已剔除装置/召唤物：残留 {len(trap)} 行')
        good(f'干员表共 {len(rows)} 行（真干员 `char_*`）')
    h, rows = load_tsv('01a_装置与陷阱.tsv')
    if rows:
        m = {r[2]: r for r in rows}
        r = m.get('trap_001_crate')
        (good if (r and r[1] == '障碍物') else bad)(
            f'装置表: `trap_001_crate` → 「{r[1] if r else "?"}」（期望「障碍物」）')
        only_dev = all(rr[2].startswith(('trap_', 'token_')) or rr[11] in _device_prof for rr in rows)
        (good if only_dev else bad)(f'装置表只含装置/召唤物：共 {len(rows)} 行')
    h, rows = load_tsv('03_敌人.tsv')
    if rows:
        m = {r[2]: r for r in rows}
        r = m.get('enemy_1007_slime')
        name = r[1] if r else '?'
        (good if name == '源石虫' else bad)(f'敌人: `enemy_1007_slime` → 「{name}」（期望「源石虫」）；表内共 {len(rows)} 个敌人')
    h, rows = load_tsv('04_关卡.tsv')
    if rows:
        hit = [r for r in rows if len(r) > 8 and r[8] == 'GT-1']
        if hit:
            good(f'关卡: 代号「GT-1」↔ 关卡名「{hit[0][7]}」；表内共 {len(rows)} 关')
        else:
            bad(f'关卡: 未命中 GT-1；表内共 {len(rows)} 关')
    h, rows = load_tsv('02_干员名别名.tsv')
    if rows:
        good(f'干员别名：{len(rows)} 条（如「阿米娅-WARRIOR」这类变体写法）')
    h, rows = load_tsv('05_枚举词典.tsv')
    if rows:
        good(f'枚举词典：{len(rows)} 条（如 abnormal.STUNNED → 晕眩）')

    # --- 拼音自检：已知读音（含多音字兜底）与官方英文名交叉校验 ---
    h, ops = load_tsv('01_干员.tsv')
    if ops:
        m = {r[2]: r for r in ops}
        py_cases = [('char_123_fang', 'fen', '芬'), ('char_002_amiya', 'amiya', '阿米娅'),
                    ('char_2025_shu', 'shu', '黍'), ('char_2024_chyue', 'chongyue', '重岳'),
                    ('char_362_saga', 'cuoe', '嵯峨'), ('char_377_gdglow', 'chengshan', '澄闪'),
                    ('char_503_rang', 'xunlinzhe', '巡林者'), ('char_1012_skadi2', 'zhuoxinsikadi', '浊心斯卡蒂')]
        for cid, want, nm in py_cases:
            r = m.get(cid)
            got = r[0] if r else '?'
            (good if got == want else bad)(f'拼音: 「{nm}」→ `{got}`（期望 `{want}`）')
        good(f'拼音表内已填 {sum(1 for r in ops if r[0])} / {len(ops)} 行')
        # 官方英文名交叉校验：只对"拼音与英文名逐音节可比"的行做提示（不判错，供人工复核）
        cross = []
        for r in ops:
            en = re.sub(r'[^a-z]', '', (r[7] if len(r) > 7 else '').lower())
            zh = r[1]
            if en and r[0] and CJK.search(zh) and any(c in RISK_CHARS for c in zh):
                cross.append((zh, r[0], en))
        good(f'多音字候选（含英文名可交叉校验）：{len(cross)} 行 → `--audit-pinyin` 导出明细')
    h, ens = load_tsv('03_敌人.tsv')
    if ens:
        m = {r[2]: r for r in ens}
        r = m.get('enemy_1007_slime')
        got = r[0] if r else '?'
        (good if got == 'yuanshichong' else bad)(f'拼音: 敌人「源石虫」→ `{got}`（期望 `yuanshichong`）')

    print('\n'.join('  ' + s for s in res))
    print(f'  自检总体：{"通过" if ok else "有失败项"}')
    return res, ok


def audit_pinyin(outfile):
    """导出"拼音需人工复核"的候选：①含多音字 ②拼音留空（待核）。"""
    lines = []
    for name in ('01_干员.tsv', '01a_装置与陷阱.tsv', '03_敌人.tsv', '07_职业与分支.tsv'):
        h, rows = load_tsv(name)
        if not rows:
            continue
        risk = [r for r in rows if any(c in RISK_CHARS for c in r[1])]
        blank = [r for r in rows if not r[0]]
        lines.append(f'===== {name}：共 {len(rows)} 行；含多音字 {len(risk)} 行；拼音留空 {len(blank)} 行 =====')
        lines.append('--- 多音字候选（官方名 | 实时生成拼音 | 英文名）---')
        for r in risk:
            en = r[7] if len(r) > 7 and name.startswith('01') else ''
            py, _note = pinyin_of(r[1])
            lines.append(f'{r[1]}\t{py}\t{en}')
        lines.append('--- 拼音留空（待核）---')
        for r in blank:
            py, note = pinyin_of(r[1])
            lines.append(f'{r[1]}\t{r[2]}\t{note}')
        narrow = [r for r in rows if any(c in RISK_NARROW for c in r[1])]
        lines.append(f'--- 重点复核（同字异音节，{len(narrow)} 行）：官方名 | 生成拼音 ---')
        for r in narrow:
            py, _note = pinyin_of(r[1])
            lines.append(f'{r[1]}\t{py}')
        lines.append('')
    with open(outfile, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'  审计清单 → {outfile}')
    return 0


def fill_pinyin_in_place(name, apply=False):
    """给**不由本脚本生成**的表（如人工/他脚本产出的 `07_职业与分支.tsv`）补第 1 列拼音。

    **只填空单元格**（幂等，绝不覆盖已有值）；表里若有 `备注` 列就一并写 `拼音待核`，没有就只报告。
    """
    path = os.path.join(OUT, name)
    if not os.path.exists(path):
        print(f'  [!] 找不到 {name}')
        return 1
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n').split('\t') for l in f if l.strip()]
    header, body = lines[0], lines[1:]
    if not header or header[0] != '汉语拼音':
        print(f'  [!] {name} 第 1 列不是「汉语拼音」，跳过')
        return 1
    note_idx = len(header) - 1 if header[-1] == '备注' else None
    filled, blank, notes = 0, 0, []
    for r in body:
        if len(r) < 2 or r[0].strip():
            continue
        py, note = pinyin_of(r[1])
        r[0] = py
        if py:
            filled += 1
        else:
            blank += 1
            if note:
                notes.append(f'{r[1]}: {note}')
        if note and note_idx is not None:
            r[note_idx] = (r[note_idx] + '；' + note).strip('；') if r[note_idx] else note
    print(f'  {name}: 待填 {filled + blank} 行（可填 {filled}、留空 {blank}）'
          + ('' if note_idx is not None else '；本表无「备注」列 ⇒ 留空项只报告不落盘'))
    for n in notes:
        print(f'    · {n}')
    if apply:
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\t'.join(header) + '\n')
            for r in body:
                f.write('\t'.join(r) + '\n')
        print(f'  已写回 {name}（备份请自行保留；本脚本不改其他列）')
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--only', default='')
    ap.add_argument('--fill-pinyin', default='', metavar='表文件名',
                    help='给不由本脚本生成的表补第 1 列拼音（只填空格；配 --apply 才写回）')
    ap.add_argument('--apply', action='store_true', help='配合 --fill-pinyin，实际写回')
    ap.add_argument('--audit-pinyin', nargs='?', const=os.path.join(
        os.path.dirname(AK), '.tmp', 'pinyin_audit.txt'), dest='audit')
    ap.add_argument('--allow-no-pinyin', action='store_true',
                    help='明知没有 pypinyin 仍要写盘（**会清空拼音列**，慎用）')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    # 守卫：没有 pypinyin 时**拒绝全量生成**，避免静默把拼音列清空
    # （2026-09-23 实际踩过：用无 pypinyin 的解释器重跑，460/460 行的拼音被清成 32 行）
    if (lazy_pinyin is None and not a.check and not a.fill_pinyin and not a.audit
            and not a.allow_no_pinyin):
        print('[X] 未安装 pypinyin：全量生成会把拼音列写空，已中止。\n'
              '    改用： D:\\__soft\\Anaconda\\python.exe ak\\code\\tools\\glossary_build.py\n'
              '    或确实要跳过拼音：加 --allow-no-pinyin', file=sys.stderr)
        return 2

    if a.fill_pinyin:
        return fill_pinyin_in_place(a.fill_pinyin, apply=getattr(a, 'apply'))
    if a.audit:
        os.makedirs(os.path.dirname(a.audit), exist_ok=True)
        return audit_pinyin(a.audit)
    if a.check:
        check()
        return 0

    only = [s.strip() for s in a.only.split(',') if s.strip()]
    counts = {}
    for name, fn, _desc in TABLES:
        if only and not any(name.startswith(o) for o in only):
            h, rows = load_tsv(name)
            counts[name] = len(rows or [])
            continue
        out = fn()
        if isinstance(out, tuple):
            header, rows = out
            counts[name] = write_tsv(name, header, rows)
        else:
            counts[name] = 0
    res, _ok = check()
    write_index(counts, res, pinyin_stats_from_tables())
    return 0


if __name__ == '__main__':
    sys.exit(main())
