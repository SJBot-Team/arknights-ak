# -*- coding: utf-8 -*-
"""append_round42.py — 第四十二轮：精度验证脚本就位，但导航卡在"点击不生效"。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

DOC_SEC = '''
### 7.70 相位↔墙钟精度验证脚本就位；但导航卡在"点击不生效"（本轮未完成）

#### 已就位
新增 `apps/phase_precision_test.py`：**一条命令跑完**流程——
状态自适应进战斗 → 判定 battle 后**立刻**密集采样 → 逐帧读「费用数字」+ 用 §7.68 实测 ROI
（y∈[805,817]、x∈[1700,1920]）算「条内相位」→ 逐对比较
`推得逻辑帧 = Δ费用×30 + Δ相位` 与 `墙钟Δt×30`，输出误差并统计 |误差| 中位数。
时间戳取**截图前/后的中点**（把 adb 往返抖动砍一半）。

#### 本轮卡住的地方
运行时第 0 步就判定 `squad`，随后**连续 10 次**判定 `squad` 并点击「开始行动」(1659,766)，
但界面始终没变 ⇒ 该 `squad` 判据（右下角 (1540,610,1760,900) 白色占比 > 0.02）
在当前那张画面上**误命中**，或游戏此刻并不在编队界面。

⇒ **根本缺陷是"点击后没有复查"**：状态机只看"点了没"，不看"点完变没变"，
所以一旦判据误命中，就会 10 次空点、并把整轮时间耗光（这在真实打图中同样是致命的）。

#### 下一步（明确的改造清单）
1. 导航加 **"点击生效校验"**：点完 N 百 ms 内复查界面是否变化；未变化则视为失败并**升级策略**
   （换坐标/换判据/报错退出），绝不静默重试同一动作；
2. 状态判据补 **结算/行动结束、关卡地图、编队、准备阶段**等更多分支（当前只有 map/detail/squad/battle 四个）；
3. 判据本身要过 **§7.66 的两条强制自检**（置信度阈值 + "画面在变"），避免再次误命中；
4. 之后再用 `phase_precision_test.py` 跑精度比对（目标 |误差| ≤ 2 帧），
   并接着做**暂停 → 读相位取严格帧号 → 同帧多操作 → 目标相位恢复**的闭环。

#### 连续两轮未完成的诚实记录
- 第四十一轮：`timestamps.csv` 与帧集不同源 ⇒ 精度比对无效；
- 第四十二轮：导航空点 ⇒ 没进到战斗、没有样本。
⇒ 精度验证**仍未成立**；但费用条 ROI 定位（§7.68）、封顶停住（§7.68）、
采集→识别链路（§7.66）三项已确证，且验证脚本已就位，只差"能稳定进战斗"这一步。
'''

REG_ADD = (
    ' **第四十二轮（精度验证脚本就位；导航卡在"点击不生效"）**：'
    '①新增 `apps/phase_precision_test.py`：一条命令完成「状态自适应进战斗 → 立刻密集采样 → 逐帧读费用数字 + '
    '用 §7.68 实测 ROI(y 805-817) 算条内相位 → 逐对比较 推得逻辑帧=Δ费用×30+Δ相位 与 墙钟Δt×30 → 统计 |误差|」，'
    '时间戳取截图前/后**中点**以砍掉一半 adb 往返抖动；'
    '②**本轮卡点**：运行时第 0 步即判 `squad`，随后**连续 10 次**判 squad 并点「开始行动」(1659,766)，界面始终未变 ⇒ '
    'squad 判据（右下角白色占比>0.02）在当前画面**误命中**，或游戏并不在编队界面；'
    '③**根本缺陷**：状态机只看"点了没"，**不看"点完变没变"** ⇒ 判据一旦误命中就会空点 10 次并把整轮时间耗光'
    '（真实打图中同样致命）；④**下一步改造清单**：(a) 导航加"点击生效校验"（点后复查界面，未变则升级策略/报错，'
    '绝不静默重试同一动作）；(b) 状态判据补结算/地图/编队/准备阶段等分支；(c) 判据须过 §7.66 两条强制自检'
    '（置信度阈值 + "画面在变"）；(d) 再用 `phase_precision_test.py` 跑精度（目标 |误差| ≤ 2 帧），'
    '随后做暂停→读相位→同帧多操作→目标相位恢复的闭环；'
    '⑤**连续两轮未完成的诚实记录**：第四十一轮 csv 与帧集不同源、第四十二轮导航空点 ⇒ **精度验证仍未成立**；'
    '已确证的是：费用条 ROI 定位、封顶停住、采集→识别链路；'
    '⑥合规：仅 adb/窗口接口与普通注入，不碰游戏内存；仅演习，未消耗理智。 | 2026-09-14 |'
)

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.69 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, DOC_SEC + '\n### 7.71 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.70')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
if ra not in r:
    raise SystemExit('registry anchor not found')
r = r.replace(ra, REG_ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第四十二轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\code\vision\apps\phase_precision_test.py',
             os.path.join(DST, 'code', 'vision', 'apps', 'phase_precision_test.py'))
print('同步完成')
