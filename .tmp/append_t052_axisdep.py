# -*- coding: utf-8 -*-
"""append_t052_axisdep.py — 追加"方向语义固化 + 轴表驱动部署链路"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第86轮】★★★★**格点真源补全"朝向语义"并打通"轴表 → 实机部署"链路**：'
 '①**朝向语义固化（`grid_px.DIR_DELTA` / `dir_to_px` / `deploy_px`）**：'
 '与格轴一致 —— **左 = col−1（x −124.5）**、**右 = col+1**、**上 = row−1（y −138）**、**下 = row+1**；'
 '**验证依据**：芬在 D6(3,5) **朝左**、其攻击范围含 **(3,4)** —— 而 col4 正在 col5 的**屏幕左侧** ✓；'
 '实测输出：**D6 朝左 → 拖向 (1057,502)**（col4）、**D4 朝上 → 拖向 (932,364)**（row2）、'
 'D6 朝右 → (1306,502)（col6）；'
 '**过程中自查并修正一处写反**：首版把"左"写成 Δrow=−1 ⇒ 输出 (1182,364)（应为改 x）；'
 '②**新增 `apps/axis_deploy_live.py`（轴表驱动实机部署）**，链路：'
 '**`ak/axis/1-1.yaml` 的 `deploys[].cell`/`dir` → `grid_px.coord_to_px`/`dir_to_px`（唯一真源）'
 '→ `Deployer.deploy_two_step_px`（两段式）→ 以费用下降量验证提交**；'
 '③**实机运行结果（本次未成功，但原因已定位且非映射问题）**：读取轴表 `deploys[0]` = 芬 @D6 朝左（8 费）；'
 '解得 格像素 **(1182,502)**、朝向点 **(1057,502)**；自动攒费至 8 后暂停，取"费用最低的第 1 张卡" (582,1007) 执行两段式；'
 '**费用 8 → 8 未下降**；查截图确认根因：**这是同一场旧演习**（`剩余可放置角色：6`，'
 '芬(8) 与 月见夜(14) 的卡片**均已用掉**），**当前最便宜的可用卡为 9 费 > 费用 8** ⇒ **游戏因费用不足拒绝部署**；'
 '⇒ **属"队伍/费用状态"问题，映射与两段式链路本身无误**；'
 '④**下一步**：**(a)** 测试前**重开一场演习**（或先确认目标卡仍可用、费用足够）⇒ 再用修正后的 D6(1182,502) 复测；'
 '**(b)** 把 `grid_px` 与两段式接入 `axis_runner`，实现**按共用轴表全自动部署**；'
 '**(c)** 接"过帧（两次暂停）× 费用条帧时钟"实现**目标帧精确部署**；'
 '⑤**合规**：仅界面级拖拽/暂停与截图 + 只读识别；未登录、全程演习未消耗理智、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
