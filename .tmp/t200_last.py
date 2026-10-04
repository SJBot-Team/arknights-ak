# -*- coding: utf-8 -*-
import io, glob, os

edits = {
 r'C:\Users\23922\Documents\ds_harness\ak\knowledge\00_Agent入口.md':
   ('> 层级：**待定（需人工判定）**　建立日期：**—（待补）**　任务：—　｜　**头部为 2026-09-30 自动回填**，推断项已标注',
    '> 层级：**T3（全库索引/导航，非机制结论）**　建立日期：2026-09-23　任务：T-062　｜　维护：改结构后同步本页并重跑三件套体检'),
}
for p, (old, new) in edits.items():
    s = io.open(p, encoding='utf-8').read()
    if old in s:
        io.open(p, 'w', encoding='utf-8').write(s.replace(old, new, 1))
        print('已改:', os.path.basename(p))
    else:
        print('未命中:', os.path.basename(p))

# README.md：补一行头部
p = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\README.md'
s = io.open(p, encoding='utf-8').read()
if '层级：' not in s.split('\n\n')[0]:
    lines = s.split('\n')
    idx = next(i for i, l in enumerate(lines) if l.startswith('# '))
    lines.insert(idx + 1, '> 层级：**T3（领域与条目格式约定，非机制结论）**　建立日期：2026-09-23　任务：T-062')
    io.open(p, 'w', encoding='utf-8').write('\n'.join(lines))
    print('已补 README.md 头部')

# 06 域：去向页 + 待删的 5 篇，各补一行状态头（便于注册表识别）
p = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\06_工作链条\00_目录.md'
s = io.open(p, encoding='utf-8').read()
if '层级：' not in s:
    lines = s.split('\n')
    idx = next(i for i, l in enumerate(lines) if l.startswith('# '))
    lines.insert(idx + 1, '> 层级：**T3（域去向说明页，非机制结论）**　建立日期：2026-09-29　任务：T-200c　｜　本域已拆分，内容去向见下')
    io.open(p, 'w', encoding='utf-8').write('\n'.join(lines))
    print('已补 06 去向页头部')

for f in ('00_两轮大任务_工作链条.md', '10_封装_轮一_战斗模拟环境.md', '11_封装_轮二_纯AI打图工具流.md',
          '20_封装_核心成果.md', '40_错误总结与反思.md'):
    p = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\knowledge\06_工作链条', f)
    s = io.open(p, encoding='utf-8').read()
    if '层级：' in s:
        continue
    lines = s.split('\n')
    idx = next(i for i, l in enumerate(lines) if l.startswith('# '))
    lines.insert(idx + 1, '> 层级：**T3（历史工作记录）**　建立日期：—　任务：—　｜　**⚠️ 已于 2026-09-29 拆分，本文件待删除**（去向见 `06/00_目录.md`）')
    io.open(p, 'w', encoding='utf-8').write('\n'.join(lines))
    print('已标待删:', f)
