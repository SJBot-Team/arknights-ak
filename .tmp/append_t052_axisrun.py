# -*- coding: utf-8 -*-
"""append_t052_axisrun.py — 追加"轴表两端闭环验证"一轮到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第68轮】★★★★**共用轴表"两端闭环"验证：打图端执行器干跑同一份轴，帧号与模拟器完全一致**：'
 '①**新建 `code/vision/configs/axis_1-1.json`**（打图端执行配置）：指向共用轴表派生的 `ak/data/derived/axis_1-1.json`，'
 '含合规段、`unit_costs`、`grid(7×9)`、`coord_transform=rc_normal`、`max_seconds=60` 等；**默认 dry-run**；'
 '②**★发现并修正一处语义错配（重要）**：打图端 `run_axis.py` 的 `ops[].cost` 是**费用锚点（该时刻 HUD 显示费用）**，'
 '不是单位部署费用；而共用轴表里的 `cost` 是**单位部署费用**（芬 8）。'
 '首轮干跑即暴露：把 8/14 当锚点会反推出帧 0/360（错），'
 '⇒ 轴表新增 **`cost_anchor`**（1-1：帧 10 → **10**、帧 411 → **15**，取自标定表"该秒初始费用"），'
 '桥接脚本 `axis_to_runner_ops` 改为把 `cost_anchor` 写成打图端 `cost`、`frame % 30` 写成 `foff`（费用内帧相位），'
 '单位费用另存 `unit_cost`；'
 '③**闭环验证（`code/vision/apps/test_axis_runner.py`，dry-run + 虚拟时钟，不注入任何输入）**：'
 '**2/2 执行成功**、**目标帧 = [10, 411] 与轴表逐帧一致**、费用锚 10/15 正确、'
 '**迟到 >0.5 帧 0 条**（最大 0.018 帧）、`same_frame_groups` 字段在位（为"同帧多操作"留位）；'
 '④**★由此得到一条可复用的帧换算关系**（打图端原生口径）：'
 '`绝对帧 = (显示费用 − 初始费用 + 净累计消耗) × 30 + foff`；'
 '1-1 实测反推：芬 `(10−10+0)×30+10 = 10`、月见夜 `(15−10+8)×30+21 = 411` ⇒ **与轴表逐帧一致**；'
 '⑤**两端一致性**：同一份 `ak/axis/1-1.yaml` —— 模拟器/校验器 `replay_axis.py` 得 **18/18 可对齐**'
 '（16 条伤害/出生/击杀平均 2.19、最大 7）；打图端执行器得 **目标帧 [10,411]、0 迟到**；'
 '⑥**文档**：`ak/axis/README.md` 增补「**两套费用语义**」表与"跑一遍"（模拟侧 + 打图侧两条命令）与两端结果表；'
 '`55_工作前提与五项机制.md` 清单 A 增补"共用轴表（三方）"与"两套费用语义（勿混）"两行；'
 '`00_结论索引.md` 更新 **B30**（含费用锚点语义与干跑结果）；'
 '⑦**回归**：`replay_axis` 18/18、`replay_verify5` 16/16（平均 2.19）、`verify_semantics` A1~A9、'
 '`test_axis_io` 全通过；`test_axis_runner` 全通过；'
 '⑧**合规**：打图端全程 **dry-run + 虚拟时钟**，**未加载输入后端、未截图、未注入、未登录**；'
 '未触碰游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
