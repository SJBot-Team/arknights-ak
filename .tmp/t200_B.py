# -*- coding: utf-8 -*-
"""B 收尾：把"知识注册表"接进入口与工具索引。"""
import io

# ① 00_Agent入口：§5.3 固定动作 + §6.2 索引页一览
p1 = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\00_Agent入口.md'
s1 = io.open(p1, encoding='utf-8').read()

old1 = '5. **改完跑一次链接检查**（`ak\\code\\tools\\check_kb_links.py`）——保证索引里没有指向已改名/已拆走文件的死链。'
new1 = ('5. **改完跑一次链接检查**（`ak\\code\\tools\\check_kb_links.py`）——保证索引里没有指向已改名/已拆走文件的死链。\n'
        '5b. **改完重跑知识注册表**（`D:\\__soft\\Anaconda\\python.exe ak\\code\\tools\\kb_registry.py --write`）'
        '——刷新 `00_知识注册表.md` 的层级/日期/任务号/置信度标记分布。**新篇请按规范写头部**：'
        '`> 层级：**T1/T2/T3（说明）**　建立日期：YYYY-MM-DD　任务：**T-0xx**`（社区来源另加 `来源：` 与 `URL：`）。')
assert old1 in s1
s1 = s1.replace(old1, new1, 1)

old2 = '| `04_数据对应与核验/45_资产索引_可复用工具与脚本.md` | 可复用脚本与配置 |'
new2 = ('| `04_数据对应与核验/45_资产索引_可复用工具与脚本.md` | 可复用脚本与配置 |\n'
        '| **`00_知识注册表.md`**（**自动生成，勿手改**） | **全库 130 篇的层级 / 日期 / 任务号 / 来源 URL / 置信度标记密度**；'
        '生成器 `ak\\code\\tools\\kb_registry.py`。**要找"哪些篇是 T1、哪些标了 ⚠️拟合、哪些🔴多"，先看这张表** |')
assert old2 in s1
s1 = s1.replace(old2, new2, 1)

# §一 增一行"我要筛可信度"
old3 = '| **判断"某条机制说法"可不可信** |'
new3 = ('| **筛"哪些结论是 T1 / 哪些还标着 ⚠️拟合 / 🔴"** | **`00_知识注册表.md`（自动生成）** | '
        '需要看结论本身则 `04/01_结论索引`；需要看未解决问题则 `04/60` |\n'
        '| **判断"某条机制说法"可不可信** |')
assert old3 in s1
s1 = s1.replace(old3, new3, 1)

io.open(p1, 'w', encoding='utf-8').write(s1)
print('入口已接入注册表')

# ② 04/45：登记生成器
p2 = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\45_资产索引_可复用工具与脚本.md'
s2 = io.open(p2, encoding='utf-8').read()
if 'kb_registry.py' not in s2:
    s2 = s2.rstrip() + ('\n\n### 八·补三、知识注册表生成器（T-200c，2026-09-29）\n\n'
                        '| 工具 | 作用 | 用法 |\n|---|---|---|\n'
                        '| `ak\\code\\tools\\kb_registry.py` | 扫描 `knowledge/**/*.md` 的头部，生成 **`knowledge/00_知识注册表.md`**'
                        '（层级 / 日期 / 任务号 / 来源 URL / 置信度标记密度 / 缺头部清单） | '
                        '`D:\\__soft\\Anaconda\\python.exe ak\\code\\tools\\kb_registry.py --write`（不加 `--write` 为干跑） |\n\n'
                        '> **三件套体检**：结构 `check_kb_links.py`（断链必须 0）｜词典 `glossary_doctor.py`｜**注册表 `kb_registry.py`**。\n'
                        '> **当前基线**：130 篇；层级分布 T1×39 / T2×44 / T3×40 / —×7；**缺规范头部 83 篇**（已在注册表末尾列清单）。\n')
    io.open(p2, 'w', encoding='utf-8').write(s2)
    print('04/45 已登记 kb_registry.py')
else:
    print('04/45 已有登记')
