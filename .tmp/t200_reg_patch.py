# -*- coding: utf-8 -*-
"""给 kb_registry.py 打补丁：①加 RVA/代码特征计数 ②层级启发式兜底 ③输出"缺头部"清单。"""
import io

p = r'C:\Users\23922\Documents\ds_harness\ak\code\tools\kb_registry.py'
s = io.open(p, encoding='utf-8').read()

# ① parse() 里加 rva 计数与 raw 摘要
s = s.replace("""        'fit': raw.count('⚠️拟合') + raw.count('⚠️ 拟合'), 'ok': raw.count('✅'),
    }""",
"""        'fit': raw.count('⚠️拟合') + raw.count('⚠️ 拟合'), 'ok': raw.count('✅'),
        'rva': len(re.findall(r'0x[0-9A-Fa-f]{5,}', raw)),
        'codeword': sum(raw.count(k) for k in ('dump.cs', '反汇编', 'IL2CPP', 'RVA', 'GameAssembly')),
        'prts': raw.count('PRTS') + raw.count('prts.wiki'),
        'bili': raw.count('B 站') + raw.count('bilibili') + raw.count('录播') + raw.count('专栏'),
    }""")

# ② 兜底函数 + 在 main 里应用
s = s.replace("""def main() -> int:""",
'''def infer_level(r: dict) -> str:
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


def main() -> int:''')
s = s.replace("""    lv = {}
    for r in rows:
        key = (r['level'] or '—')[:2]
        lv[key] = lv.get(key, 0) + 1""",
"""    nohead = []
    for r in rows:
        if r['level'] == '—':
            nohead.append(r)
            r['level'] = infer_level(r)
        else:
            r['level'] += '(标)'
    lv = {}
    for r in rows:
        key = (r['level'] or '—')[:2]
        lv[key] = lv.get(key, 0) + 1""")

# ③ 结尾输出"缺规范头部"清单
s = s.replace("""    out.append('---\\n')
    out.append('## 维护\\n')""",
"""    out.append('---\\n')
    out.append(f'## 附：缺规范头部的篇目（{len(nohead)} 篇，**建议逐步回填**）\\n')
    out.append('> 规范头部格式：`> 层级：**T1/T2/T3（说明）**　建立日期：YYYY-MM-DD　任务：**T-0xx**`。')
    out.append('> 下表各篇的层级是**启发式推断**（标 `(推)`），请以正文实际证据为准。\\n')
    for r in nohead:
        out.append(f"- `{r['rel']}`（推断 {r['level']}；RVA 数 {r['rva']}，代码词 {r['codeword']}）")
    out.append('')
    out.append('---\\n')
    out.append('## 维护\\n')""")
io.open(p, 'w', encoding='utf-8').write(s)
print('kb_registry.py 已打补丁')
