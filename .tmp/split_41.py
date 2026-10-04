# -*- coding: utf-8 -*-
"""把 04/41（2974 行）按规模红线下沉：§七 工作日志（2745 行）切成 6 篇子文件，母文件保留 §一~§六 + §八 + 日志目录。

正文逐字搬运；母文件的"§七 分期目录"由脚本按各段首尾小标题自动生成，不手抄。
"""
import os

BASE = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验'
SRC = os.path.join(BASE, '41_模拟器与自动打图_首版实现.md')

SEGS = [
    ('41a_日志_时基与轴表语义.md',                    '日志（一）：时基、轴表语义与技能系统',        210, 655),
    ('41b_日志_实机规程与坐标确认.md',                '日志（二）：实机验证规程、导航骨架与坐标确认',  656, 992),
    ('41c_日志_坐标根因与帧级时钟.md',                '日志（三）：坐标根因、费用上限经济学与帧级时钟', 993, 1438),
    ('41d_日志_费用条识别与OCR导航.md',               '日志（四）：费用条识别、OCR 导航与离线回归',   1439, 2022),
    ('41e_日志_案例结论与相位精度.md',                '日志（五）：案例结论、相位精度与公式修正',     2023, 2419),
    ('41f_日志_PRTS+与录像验证.md',                   '日志（六）：PRTS+（赛博塑料）与录像验证、计时定案', 2420, 2951),
]
MOTHER_HEAD = (1, 205)      # 头部 + §一~§六
MOTHER_TAIL = (2952, None)  # §八 合规

PARENT = ('> **本文件是 `41_模拟器与自动打图_首版实现.md` 的子文件**'
          '（母文件：`knowledge/04_数据对应与核验/41_模拟器与自动打图_首版实现.md`）。\n'
          '> 内容为**逐字搬运的工作日志**（原 §七），未改写、未删减；分卷仅为满足"单篇可通读"的规模红线。\n'
          '> 母文件保留：§一~§六（架构/验证/需求对照/结论/缺口/复现命令）、**§七 分期目录**、§八 合规声明。\n')


def load():
    return open(SRC, encoding='utf-8-sig').read().split('\n')


def headings(lines):
    return [l for l in lines if l.startswith('### 7.')]


def main():
    lines = load()
    tail = lines[MOTHER_TAIL[0] - 1:] if MOTHER_TAIL[1] is None else lines[MOTHER_TAIL[0] - 1:MOTHER_TAIL[1]]
    head = lines[MOTHER_HEAD[0] - 1:MOTHER_HEAD[1]]

    rows = []
    for i, (name, title, a, b) in enumerate(SEGS, 1):
        body = lines[a - 1:b]
        assert body[0].startswith('### 7.'), (name, body[0][:40])
        hs = headings(body)
        rng = f"{hs[0].split()[1]} ~ {hs[-1].split()[1]}"
        header = (f'# {name.split("_")[0]} {title}\n\n' + PARENT +
                  f'> 本卷覆盖：**§七 {rng}**（母文件行 {a}~{b}）。\n'
                  f'> 上一卷 / 下一卷见母文件 §七 分期目录。\n\n---\n\n')
        out = os.path.join(BASE, name)
        open(out, 'w', encoding='utf-8', newline='\n').write(header + '\n'.join(body).strip('\n') + '\n')
        n = open(out, encoding='utf-8-sig').read().count('\n') + 1
        rows.append((name, title, rng, n))
        print(f'{name}: {n} 行')

    # 母文件：头 + §七 目录 + 合规
    idx = ['## 七、工作日志（**已按规模红线下沉为 6 卷**，2026-09-23）',
           '',
           '> 本卷为**第二轮起的逐轮工作日志**（原 §七，共 2745 行）。日志是"当时怎么发现、怎么推翻"的过程记录，',
           '> **结论请优先看 §四/§五 与 `01_结论索引.md`、`42_验收对照_模拟与打图.md`**；此处按时间分卷，便于按阶段回查。',
           '',
           '| 卷 | 覆盖 | 行数 | 看什么 |',
           '|---|---|---|---|']
    for name, title, rng, n in rows:
        idx.append(f'| `{name}` | §七 {rng} | {n} | {title.split("：", 1)[-1]} |')
    idx += ['',
            '> **分卷边界**：按日志的自然阶段切（时基 → 实机规程 → 坐标根因 → 费用条/导航 → 案例结论 → PRTS+/录像），',
            '> 每卷 ≤600 行；卷内仍按 §7.x 编号连续，**原编号未改**，跨卷引用（如"见 §7.51"）可直接在母文件本表里定位。',
            '']

    mother = ('\n'.join(head).rstrip('\n') + '\n\n' + '\n'.join(idx) + '\n---\n\n' + '\n'.join(tail).strip('\n') + '\n')
    open(SRC, 'w', encoding='utf-8', newline='\n').write(mother)
    print(f'母文件: {mother.count(chr(10)) + 1} 行')


if __name__ == '__main__':
    main()
