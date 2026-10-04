# -*- coding: utf-8 -*-
"""append_t052_avatar.py — 记录"头像库资产已证实正确；匹配度量仍待解决"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第94轮】★★★★★**按用户指点确认头像库可用：目视对照证明"卡片裁切 == 头像文件"；三种匹配度量仍未过关（已列出真因与下一步）**：'
 '①**用户再次指点**：「`D:\\__soft\\ak\\prts+\\_internal\\resource\\avatar` 为头像地址，'
 '可通过**干员名与代码 id 对照表**找到对应头像。**maa 中也有，应当更新**」；'
 '⇒ 已确认：对照表 = `resource/operator_mapping.json`（927 条，编队 11 人全命中）；'
 '头像 = `resource/avatar/char_<id>.png`；**各干员含基础头像 + 皮肤变体**'
 '（如 `char_123_fang.png` / `char_123_fang_winter#1.png`），无精英阶数变体；'
 'MAA 侧未发现独立头像库（其资源为模板/模型/作业），"应当更新"应指**对照表**需跟上版本；'
 '②**★决定性目视对照（新增 `card_vs_avatar.png`）**：把编队页**实测卡面裁切**与**应有头像**并排为成对图 —— '
 '**卡缇↔char_209_ardign、芬↔char_123_fang、月见夜↔char_283_midn 三对全部一致**（同一张画、同一构图）'
 '⇒ **头像库与卡片裁切坐标均正确**，"头像识别"这条路**资产层面完全可行**；'
 '③**三种匹配度量的实测命中率（真值 = 编队页 11 人顺序）**：'
 '**(a)** 灰度/彩色零均值互相关 + 立绘内多尺度滑窗（含候选集限制）= **2/11**；'
 '**(b)** 修正几何（头像按高度铺满后水平居中裁切）**+ alpha 掩膜**（真因：`imread` 忽略 alpha ⇒ '
 '透明区变黑白噪声）= **2/11**；'
 '**(c)** HSV 三维颜色直方图相关 = **1/11**（但分数普遍 0.79~0.96 ⇒ 直方图对同风格立绘区分度不足）；'
 '④**已定位的真正干扰源**：卡片上叠加了**蓝色对角线横幅、费用数字、职业图标、渐变底色**，'
 '而头像带**透明背景** ⇒ 逐像素相关被这些**非共有区域**淹没；'
 '⑤**下一步（明确）**：**(a)** 用 MAA 的 **`onnx/operators_det.onnx`（YOLO 式检测）先定位"卡面画框"**，'
 '只在**框内的干净区域**（横幅之上的脸部区）做掩膜互相关；'
 '**(b)** 或对卡片与头像**同时只取"脸部方框"**（按固定比例）后比较；'
 '**(c)** 保留**结构性捷径**作为兜底：卡片按费用升序 + 编队费用已知 ⇒ 可直接算出卡片序号，无需识别；'
 '⑥**合规**：只读本机 PRTS+/MAA 资源与已存截图；未登录、未消耗资源、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
