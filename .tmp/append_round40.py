# -*- coding: utf-8 -*-
"""append_round40.py — 第四十轮：「恒定 8/9」真因（低置信度误判）+ 端到端链路打通。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'

DOC_SEC = '''
### 7.66 【真因】"费用数字恒定 8/9" = 低置信度误判把按钮笔画当成了数字

#### 定案过程
用 §7.64 打通的 adb display 通道（遮挡无关、真画面）进战斗、连拍，仍然"恒定读到 9"。
把那一帧裁出来放大一看：**画面根本还停在编队界面的「开始行动」按钮上**（蓝底白字 + OPERATION START）。

于是整条因果链清楚了：
1. 我的"是否已在战斗"判据是 **`read_cost() is not None`**；
2. 编队界面里，费用数字 ROI 恰好落在「开始行动」按钮上，按钮的白色笔画被字形切分当成数字，
   输出 **`9`，置信度 0.328**（而真战斗帧的置信度是 **0.962**）；
3. ⇒ 状态机误判 `battle`，**提前 break，后续 tap 一次都不执行**；
4. ⇒ 整段采样都在同一个静止画面上读同一个值 ⇒ **"恒定 9"**。

这也回收了前面两轮的同类现象（曾读到"恒定 8"、曾"费用条恒定满格"）：
**根因各不同，但表现都是"恒定值"**——
①桌面坐标系 vs 帧缓冲坐标系（§7.57/§7.58）；②桌面抓屏被别的窗口遮挡（§7.58/§7.60）；
③本条的低置信度误判。

#### 修复
`apps/enter_drill.py` 的 `read_cost()` 增加**置信度阈值 `MIN_CONF = 0.85`**，低置信度一律当作"读不到"。
状态判据因此自洽：编队界面读不到 ⇒ 走 `squad` 分支去点「开始行动」。
（更彻底的做法是给 `CostNumberRecognizer` 本身加阈值参数，本轮先在调用侧加，已足够。）

#### 修复后实测（adb display 2 采集，`enter_drill.py 12 2.0`）
```
[0] squad   [1..5] map   [6] battle
战斗已开始；录制 9 帧；读到费用数字 9 帧，取值范围 11~20
```
⇒ ①状态机 `squad → map → battle` 正确走通（真的点了「开始行动」进战斗）；
②费用读数 **11→20 随时间演化**、落在模型预期区间（初始 10 + t，上限 20）；
③**采集→识别→状态判断 的端到端链路在真机上打通**。

#### 教训（三次"恒定值"现象的统一对策）
任何依赖画面读数的判据，都必须同时满足两条**强制自检**：
1. **置信度阈值**（低置信度不得当作有效读数，宁可当作"读不到"）；
2. **"画面在变"校验**（连拍 2s 要求读数/相位出现 ≥2 个不同值，否则判"抓错画面/画面静止"并报错退出）。
'''

REG_ADD = (
    ' **第四十轮（"恒定 8/9"真因＝低置信度误判；端到端链路打通）**：'
    '①用 §7.64 的 adb display 通道进战斗连拍，仍"恒定读到 9"；把该帧裁出放大后发现**画面还停在编队界面的'
    '「开始行动」按钮上**——我的"是否已在战斗"判据是 `read_cost() is not None`，而该按钮的白色笔画被字形切分当成数字，'
    '输出 `9` 但**置信度只有 0.328**（真战斗帧 0.962）⇒ 状态机误判 `battle`、提前 break、**后续 tap 一次都不执行**，'
    '于是整段采样都在同一静止画面上读同一个值；'
    '②这回收了前两轮同类现象：三次"恒定值"根因各不相同（①桌面 vs 帧缓冲坐标系；②桌面抓屏被其它窗口遮挡；③低置信度误判），'
    '但表现一致 ⇒ **统一对策**：任何画面判据必须同时具备**置信度阈值**与**"画面在变"强制自检**；'
    '③**修复**：`enter_drill.py` 的 `read_cost()` 加 `MIN_CONF=0.85` 置信度阈值，低置信度一律当"读不到"，状态判据随之自洽；'
    '④**修复后实测**（adb display 2）：状态机 `squad→map×5→battle` 正确走通，费用读数 **11~20 随时间演化**、'
    '落在模型预期区间（初始 10+t、上限 20）⇒ **采集→识别→状态判断的端到端链路在真机打通**；'
    '⑤新增/修改：`plugins/capture/emu_window.py`（新增 `AdbDisplayCapture` 与 `make_capture("adb")`）、'
    '`apps/enter_drill.py`（改走 adb 通道 + 置信度阈值）、`apps/locate_cost_bar.py`（帧间差分定位费用条）；'
    '⑥**下一轮**：费用条此刻仍停在上限（两帧差分无变化），需先"故意消耗让费用条保持跳动"再定位 ROI，'
    '随后完成暂停→读相位取严格帧号→同帧多操作→目标相位恢复的闭环；'
    '⑦合规：仅 adb/窗口接口与普通注入，不碰游戏内存；仅演习，未消耗理智。 | 2026-09-14 |'
)

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.65 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, DOC_SEC + '\n### 7.67 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.66')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
if ra not in r:
    raise SystemExit('registry anchor not found')
r = r.replace(ra, REG_ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第四十轮')
