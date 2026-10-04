# -*- coding: utf-8 -*-
"""append_round55.py — 第 55 轮：验收达标 + 点击生效判据缺陷修正。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.116 【判据缺陷】"点击生效"不能用帧间差异——关卡地图自身在动

**现象**：正式验收脚本里，点「演习」后连报 4 次"生效"，但界面向来没进编队；截图发现游戏其实停在
**EPISODE 07/08/09 的关卡地图**（R8-1…M8-2）——那位置根本没有「演习」按钮。

**根因**：`AutoEnter` 判断"点击是否生效"用的是**帧间差异 > 3.0**，
而关卡地图本身有**视差/粒子动画**，帧差轻易超过阈值 ⇒ **每次都被误判为"生效"**，
于是状态机以为已经推进、实际上原地踏步。这与 §7.114 里"渲染闸门被静止界面误判"是**同一类错误**：
**用像素差异判断"状态是否改变"不可靠**。

**修正**：改用 **`UiState` 界面类型是否变化**作为生效判据
（点「演习」后若 `state` 仍为 `viewport` ⇒ 判未生效，转去点关卡节点）。
已重跑导航离线测试：**A/B/C/D 仍 4/4 PASS**（无回归）。

**推论（写成规程）**：
1. **"状态是否改变"必须用语义判据（界面类型 / 模板命中 / OCR 文本），不能用像素差异**；
2. 像素差异只适合判断**"画面是否在刷新"**（且要注意静止界面会误报"未刷新"）；
3. 两类判据不可混用——本轮与 §7.114 的两个坑正是一正一反。

### 7.117 本轮实机验收结论回顾（§7.114）
- ✅ **相位↔墙钟 |误差| 中位 0.94 帧**（10 个有效样本，判据 ≤2 帧）——目标 2.1 达成；
- ⚠️ 采样间隔必须 **< 1 秒**（本轮循环约 1.02s，导致 2/10 样本出现约 +29 帧的绕圈歧义）；
- 正式脚本 `apps/verify_phase_precision.py` 已按"不额外 sleep"实现（间隔≈adb 采集耗时 0.6~0.75s）。

### 7.118 当前实机位置与断点
修复判据后，游戏停在 **EPISODE 07/08/09 关卡地图**（不在 H12-4），
自动导航需要先做**章节导航**（此前用 OCR 做过，成本较高）。
⇒ 下一步：把游戏带回 **H12-4 关卡详情**（人工一步最快），再跑
`apps/verify_phase_precision.py` 用**短间隔**复验（预期全部样本达标）。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.115 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.119 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.116~§7.118')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第五十五轮（点击生效判据缺陷修正；验收结论回顾）**：'
       '①**判据缺陷**：正式验收脚本里点「演习」连报 4 次"生效"但界面从未进编队；截图发现游戏其实停在'
       '**EPISODE 07/08/09 关卡地图**（那位置没有演习按钮）⇒ 根因是 `AutoEnter` 用**帧间差异>3.0** 判"点击生效"，'
       '而关卡地图有**视差/粒子动画**，帧差轻易超阈 ⇒ 每次误判为"生效"、状态机原地踏步；'
       '②**修正**：改用 **`UiState` 界面类型是否变化**作生效判据（点演习后仍为 viewport ⇒ 判未生效、转去点节点）；'
       '导航离线测试 **A/B/C/D 仍 4/4 PASS**（无回归）；'
       '③**推论（写成规程）**："状态是否改变"必须用**语义判据**（界面类型/模板命中/OCR 文本），'
       '**不能**用像素差异；像素差异只适合判断"画面是否在刷新"（且静止界面会误报未刷新）；本轮与 §7.114 的两个坑'
       '正是一正一反、不可混用；'
       '④**验收结论回顾**：相位↔墙钟 **|误差| 中位 0.94 帧（达标 ≤2 帧）**，10 个有效样本；'
       '采样间隔须 **<1 秒**（本轮约 1.02s 导致 2/10 样本约 +29 帧绕圈歧义）；'
       '正式脚本 `apps/verify_phase_precision.py` 已按"不额外 sleep"实现；'
       '⑤**断点**：游戏停在 EPISODE 07/08/09 地图，需先带回 **H12-4 详情**（人工一步最快）再跑短间隔复验；'
       '⑥合规：全程仅演习、理智 128/210 未消耗；不碰游戏内存。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第五十五轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
for rel in (r'code\vision\plugins\nav\auto_enter.py', r'code\vision\apps\verify_phase_precision.py'):
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel), os.path.join(DST, rel))
print('同步完成')
