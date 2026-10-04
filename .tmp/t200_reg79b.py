# -*- coding: utf-8 -*-
import io

# 1) 索引登记 79
p1 = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\00_目录.md'
s = io.open(p1, encoding='utf-8').read()
if '`79`' not in s:
    row = ('| `79` | **★ prts+ 卡位识别：反汇编复原 + 实机验证** | 70 行 | 主会话 T-200c'
           '（用户 2026-09-29 裁决②「卡位和格子的识别直接用赛博塑料 prts+ 的方案」）：'
           '从 prts+ 冻结包**反汇编复原 `locate_avatar`**——①整条链在 **1280×720 标准尺度**；'
           '②待部署区 `(0,0.8,1,1)`；③`matchTemplate(TM_CCOEFF_NORMED)` 阈值 **0.8**；'
           '④命中后 **`replace_avatar` 抹掉**防重复；⑤输出 **屏幕比例** `avatar_pos`。'
           '**实机（1-1/10 卡）**：位置识别 ✅ 10 个互不重复槽位（pitch≈177px）、已部署的芬以 0.368 被正确排除；'
           '名字识别 🟡 需**脸部裁切+多尺度**（NCC 0.70~0.86，最接近阈值）；'
           '**下一步**：用「按住卡片读面板」建**卡位↔干员真值表**（一次 ~10 手势、整局复用） |\n')
    s = s.replace('| `01` | 结论索引', row + '| `01` | 结论索引', 1)
    io.open(p1, 'w', encoding='utf-8').write(s)
    print('04/00_目录 已登记 79')

# 2) 00_Agent入口
p2 = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\00_Agent入口.md'
s2 = io.open(p2, encoding='utf-8').read()
if '04/79' not in s2:
    s2 = s2.replace(
        '**★`04/73`（模拟环境 × 1-1 标定：逐事件对齐表 + 历史错误清单 + 置信度评估，T-200c）**',
        '**★`04/73`（模拟环境 × 1-1 标定：逐事件对齐表 + 历史错误清单 + 置信度评估，T-200c）**；'
        '**`04/79`（prts+ 卡位识别：反汇编复原 `locate_avatar` + 实机验证）**')
    io.open(p2, 'w', encoding='utf-8').write(s2)
    print('00_Agent入口 已登记 04/79')

# 3) 任务卡
p3 = r'C:\Users\23922\Documents\ds_harness\management\大任务\任务单\帧时间对齐与1-1复刻.md'
s3 = io.open(p3, encoding='utf-8').read()
row3 = (
 '| 23:0x | 11 | **用户裁决②执行：卡位识别直接用 prts+ 的方案**。从 prts+ 冻结包**反汇编复原 `locate_avatar`**'
 '（要点：**1280×720 标准尺度** + 待部署区 `(0,0.8,1,1)` + `TM_CCOEFF_NORMED` 阈值 0.8 + '
 '**`replace_avatar` 去重** + 输出**屏幕比例** `avatar_pos`）。**实机验证（1-1/10 卡）**：'
 '位置 ✅ **10 个互不重复槽位**（pitch≈177px）、已部署的芬以 0.368 被排除；'
 '名字 🟡 需**脸部裁切+多尺度**（NCC 0.70~0.86）。★**本轮实机只做了卡位识别**（按用户要求）。写入 `04/79` | ✅ |\n'
 '| 23:0x | 11 | **用户裁决①**：月见夜费用差 1 = **标定表 14s 后绝对时间标注有误（用户已修正）** '
 '⇒ `04/73 §6-④` 改判为**已解决（表侧）**。**用户裁决③**：动画层**实机 = 猎狗pro 奔跑→攻击切换帧与'
 '芬血量下降帧为 26 帧**、下一费用 15s 间隔 19 ⇒ 记为下一步的**真值锚点**（我此前用标定反推的 19/22 需按此重核） | ✅ |')
anchor = '\n---\n\n## 五、待裁决'
assert anchor in s3
s3 = s3.replace(anchor, '\n' + row3 + anchor, 1)
io.open(p3, 'w', encoding='utf-8').write(s3)
print('任务卡已追加')
