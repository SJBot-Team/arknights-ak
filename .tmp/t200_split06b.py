# -*- coding: utf-8 -*-
"""06 拆分的收尾：①改入口指针 ②登记待删除 ③更新入口 §6.1.1 索引页现状"""
import io

# ① 入口：把"开工前先看别人踩过的坑"的指针改到 meta
p1 = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\00_Agent入口.md'
s1 = io.open(p1, encoding='utf-8').read()
old = '| **开工前先看别人踩过的坑** | `06_工作链条/40_错误总结与反思.md` | `meta/流程规范.md`、`meta/解包经验.md` |'
new = '| **开工前先看别人踩过的坑** | **`meta/流程规范.md §8`（错误与方法论教训：E1~E12 / ★M1~M6 / 流程反思）** | `04/45 §十`（核心成果与纠错型成果 R1~R10）、`meta/解包经验.md` |'
assert old in s1, '入口指针未命中'
s1 = s1.replace(old, new, 1)

# ② 入口 §6.1.1：更新各域索引页现状
old2 = """| `01`/`02`/`03`/`05`/`06` | ❌ 无独立索引页 | 文件数少（2–15 篇），**暂不需要**；若某领域超 12 篇再建 |"""
new2 = """| `01`/`02`/`03`/`05` | ✅ **2026-09-29 已补** | `01_基础数据/00_目录.md`、`02_作战机制/00_目录.md`、`03_外部学习/00_目录.md`、`05_舟数据/00_目录.md`（`03` 已有 15 篇，早就该建） |
| `06` | ✅ `06/00_目录.md`（**去向说明页**） | 本域 **2026-09-29 已拆分**：教训→`meta/流程规范 §8`、成果与复现入口→`04/45 §十/§十一`、过程叙述登记删除 |"""
assert old2 in s1, '§6.1.1 未命中'
s1 = s1.replace(old2, new2, 1)

# ③ §二 的 06 行同步
old3 = '| `06_工作链条/` | 两轮大任务的工作链条、核心成果、错误反思（**与机制知识解耦**） | `00_两轮大任务_工作链条.md` |'
new3 = '| `06_工作链条/` | **已于 2026-09-29 拆分**（教训→`meta/流程规范 §8`；成果/命令→`04/45 §十/§十一`；过程叙述登记删除） | `06/00_目录.md`（去向说明） |'
if old3 in s1:
    s1 = s1.replace(old3, new3, 1)
else:
    print('提示：§二 06 行格式不同，未替换')
io.open(p1, 'w', encoding='utf-8').write(s1)
print('入口已更新')

# ④ 登记待删除
p2 = r'C:\Users\23922\Documents\ds_harness\management\trash_registry.md'
s2 = io.open(p2, encoding='utf-8').read()
rows = [
 ('`ak\\knowledge\\06_工作链条\\00_两轮大任务_工作链条.md`',
  '两轮大任务过程叙述（历史）；K 成果与复现入口已迁 `04/45 §十/§十一`，错误反思已迁 `meta/流程规范 §8`'),
 ('`ak\\knowledge\\06_工作链条\\10_封装_轮一_战斗模拟环境.md`',
  '轮一封装（目标/结果/沉淀）；内容已被 `04/41`（模拟器主文档）覆盖'),
 ('`ak\\knowledge\\06_工作链条\\11_封装_轮二_纯AI打图工具流.md`',
  '轮二封装；内容已被 `04/64`（MAA/prts+ GUI 操作方案）覆盖'),
 ('`ak\\knowledge\\06_工作链条\\20_封装_核心成果.md`',
  '核心成果 K1~K11 与纠错 R1~R10 已迁 `04/45 §十`（含落点文档）'),
 ('`ak\\knowledge\\06_工作链条\\40_错误总结与反思.md`',
  'E/M/流程反思已迁 `meta/流程规范.md §8`（该处为流程资产的正确归属）'),
]
add = ''
for path, why in rows:
    line = f'| 2026-09-29 | {path} | {why} | 待确认 | |\n'
    if path not in s2:
        add += line
if add:
    s2 = s2.rstrip('\n') + '\n' + add
    io.open(p2, 'w', encoding='utf-8').write(s2)
    print(f'trash_registry 已登记 {len(rows)} 条')
else:
    print('trash_registry 已登记过，跳过')
