# -*- coding: utf-8 -*-
"""为 8 月补抓的转写生成「关键词热点索引」——让下一轮不必读 500KB 全文就能跳到讲机制的段落。

输出：ak\\_raw\\bilibili\\transcripts\\_27_关键词热点.md（原始资料区，非核心知识）
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
T = r'C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\transcripts'
BVS = {
    'BV1wPuG6aEyY': '0808 习题课',
    'BV14gby6LEni': '0815 计时器',
    'BV14y8269EbS': '0822 位移能力',
    'BV16xhV6DEF4': '0825 三船入坑',
    'BV1CZ8t6wEyr': '0823 避障力（未转完）',
}
KEYWORDS = ['阻挡偏移', '阻挡', '失衡', '仇恨', '嘲讽', '位移', '穿墙', '进墙', '反射', '传送',
            '索敌', '索迪', '所敌', '避障力', 'b张', '帧', '前摇', '抛光', '阻挡数', '重量',
            '力度', '碰撞', '检查点', '路径', '蓝门', '顺移', '停滞', '技力', '费用']
LINE = re.compile(r'^\[\s*([0-9.]+)-\s*([0-9.]+)\]\s*(.*)$')


def fmt(sec):
    sec = float(sec)
    return f'{int(sec // 60):d}:{int(sec % 60):02d}'


def main():
    out = ['# 8 月补抓转写 · 关键词热点索引（**原始资料，非核心知识**）', '',
           '> 由 `ak\\.tmp\\build_topic_index.py` 生成；用途：**下一轮不必通读 500KB 转写**，按关键词跳到该 BV 的时间点。',
           '> `BV[秒]` 才是结论出处（本索引只做导航）。时间格式 `mm:ss`，括号内为原始秒。', '']
    for bv, label in BVS.items():
        p = os.path.join(T, f'{bv}.txt')
        if not os.path.exists(p):
            out.append(f'## {bv} —— {label}（**尚无转写文件**）\n')
            continue
        hits = {k: [] for k in KEYWORDS}
        n = 0
        for line in open(p, encoding='utf-8'):
            m = LINE.match(line.strip())
            if not m:
                continue
            n += 1
            sec, text = m.group(1), m.group(3)
            for k in KEYWORDS:
                if k in text and len(hits[k]) < 12:
                    hits[k].append((float(sec), text))
        out.append(f'## {bv} —— {label}（{n} 段）\n')
        out.append('| 关键词 | 命中段数上限内的时间点（mm:ss[秒]） |')
        out.append('|---|---|')
        for k in KEYWORDS:
            if hits[k]:
                pts = '、'.join(f'{fmt(s)}[{int(s)}]' for s, _ in hits[k])
                out.append(f'| {k} | {pts} |')
        out.append('')
    dst = os.path.join(T, '_27_关键词热点.md')
    open(dst, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    print('写出', dst, len(out), '行')


if __name__ == '__main__':
    main()
