# -*- coding: utf-8 -*-
"""fix_windup_table_pos.py — 把"前摇比例表"从 @dataclass 与 class 之间移到模块顶部"""
import io
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

ENGINE = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py'

START = '# ---------------- ★普攻前摇比例表（按职业/模板分组） ----------------'
END_MARK = 'WINDUP_RATIO_DEFAULT_ENEMY = 0.10'


def main():
    s = io.open(ENGINE, encoding='utf-8').read()
    i = s.find(START)
    if i < 0:
        print('★未找到表块起点'); return
    j = s.find(END_MARK, i)
    if j < 0:
        print('★未找到表块终点'); return
    j = s.find('\n', j) + 1
    block = s[i:j]
    # 删除原块（连同其后的空行）
    rest = s[:i] + s[j:]
    rest = re.sub(r'\n{4,}', '\n\n\n', rest)
    # 插到首个 @dataclass 之前（模块级）
    k = rest.find('@dataclass')
    if k < 0:
        print('★未找到 @dataclass'); return
    out = rest[:k] + block.strip('\n') + '\n\n\n' + rest[k:]
    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(out)
    print('已将比例表移到模块顶部（@dataclass 之前）')


if __name__ == '__main__':
    main()
