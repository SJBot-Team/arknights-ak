# -*- coding: utf-8 -*-
"""append_t052_copilot.py — 记录"MAA copilot 格式摸底 + 卡片识别不必做图像识别的结论"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第93轮】★★★★★**摸清 MAA copilot 作业格式（含 `BulletTime`）；并得出"卡片选人不必做图像识别"的关键结论**：'
 '①**★MAA copilot 作业格式（已拿到动作 schema）**：'
 '顶层 `{type,stage_name,minimum_required,doc,opers,actions,buff,equipment,strategy,groups,…}`；'
 '动作样例：**`{"type":"Deploy","name":"先锋","location":[5,3],"direction":"Right"}`**、'
 '`{"type":"SpeedUp"}`、`{"type":"SkillDaemon"}`；'
 '**★并出现了 `BulletTime` 动作类型** —— 与用户所说的"**子弹时间**"对应 ⇒ '
 '**该工程确实把"暂停/过帧/子弹时间/按表部署"都做进了作业体系**，是我方轴表应对齐的标准；'
 '（本地 `resource/copilot/` 共 74 个作业，多为 SSS 型含 `strategy/tool_men`，含 `actions` 的样例较少）'
 '②**`resource/onnx/operators_det.onnx` 定性**：ONNX 头显示为 **PyTorch(Ultralytics 风格) 目标检测**'
 '（输入 `images`、含 `model.0.conv.*`）⇒ **只给"框"，不给"是哪位干员"** ⇒ **不能用于卡片身份识别**；'
 '③**卡片费用标签识别的最后一次尝试（复用模板 + 放大）**：'
 '假设"卡片小号费用与右下大费用**同字体**、仅字号不同"，故把小裁切放大 1.5/1.8/2.1× 复用既有 `tpl_h124.json`；'
 '在 4 组 y 带 × 3 组缩放的 12 种组合下，**最佳命中仅 1/10**（真值 9,9,9,13,14,15,15,16,16,17）'
 '⇒ **该路亦不可行**；'
 '④**★★关键结论（不绕远路）**：**卡片选人根本不需要图像识别** —— 依据两条已确立的结构性事实：'
 '**(a)** 战斗卡片行**按费用升序**排列（本项目多次实测一致）；'
 '**(b)** **编队构成与每位干员的部署费用都已已知**（编队页可读 / 关卡与干员数据可算，'
 '  且芬=8、月见夜=14 在本编队**唯一**）；'
 '⇒ **卡片序号 = 该干员费用在"编队费用升序"中的位次**，可**直接算出**，无需识别头像或数字；'
 '⑤**下一步**：**(a)** 实现 `card_index_for_operator(squad_costs, target_cost)` 并接入 `axis_deploy_live`；'
 '**(b)** 编队费用表来源：优先"编队页读一次"，退化为"轴表 squad + 干员数据计算"；'
 '**(c)** 对齐 MAA 作业格式（`location/direction/BulletTime/SkillDaemon`）以复用其成熟语义；'
 '⑥**合规**：只读本机 MAA/PRTS+ 资源与已存截图；未登录、未消耗资源、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
