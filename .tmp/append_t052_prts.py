# -*- coding: utf-8 -*-
"""append_t052_prts.py — 追加"PRTS+ 方案摸底 + 格子定位三重互证"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第73轮】★★★★★**按用户指示只读摸底 PRTS+ 方案：格子定位三重互证 + 实机战斗操作流程规格**：'
 '①**PRTS+ 是 PyInstaller 包**（`prts+.exe` + `_internal\\`）；exe 引导串中读出模块名 **`src.logic.calc_view`** '
 '⇒ **其格子定位 = 逐关卡相机标定 + 地图数据做投影，而非对格子做模板匹配**；'
 '②**★发现 PRTS+ 内置逐关卡地图数据**：`_internal\\resource\\map\\` 下 **3480 个** `*.json`，'
 '结构 `{code,name,levelId,stageId,width,height, view, tiles}`；**`view` = 两个 3 维相机向量**'
 '（我方 `plugins/action/calc_view.py::CalcView(view=(x,y,z))` 正是消费它，`side` 对应是否叠加 `ROTATE_Y`）；'
 '`tiles` = 每格 `buildableType/heightType/isStart/isEnd`；已把 1-1 两份存为 '
 '`ak/data/derived/prts_map_main_01-01.json`（及 `#f#` 变体）；'
 '③**★1-1 可部署格（由 PRTS+ tiles 读出）**：近战 **11 格** = `(3,1)…(3,7)` 七连排 + `(1,4)(2,4)` + `(4,5)(5,5)`；'
 '高台 14 格；'
 '④**★★三重互证（决定性）**：把实机 7 个绿格与 PRTS+ 可部署集合配对时方向有两解，'
 '**判别性检验**：那"多出来的绿格"(1057,364) 在"x 随 col 递增"假设下是 r2c3/r4c3（**均为高台** ✗），'
 '在"**x 随 col 递减**"假设下是 **r2c4（road）✅** —— 而 PRTS+ 的可部署列表**恰好包含 (2,4)**；'
 '⇒ 唯一确定的映射：**`x(col) = 1556 − 124.5·col`、`y(row) = 502 + 138·(row−3)`**；'
 '⇒ **D6=(3,5) → (934,502)**、**D4=(3,3) → (1182,502)**（均在 PRTS+ 可部署表内、均在实测绿格内）；'
 '**实测绿格 / PRTS+ tile 数据 / 仿射拟合三者互证**；'
 '⑤**（负面结论，避免走弯路）** 直接把 PRTS+ 的 `view` 喂给 `CalcView` 投影，**与实机屏幕对不上**'
 '（4 种 `view×side` 组合下 D6.x 均 > D4.x，与实测相反；格距 162.5px ≠ 实测 124.5px）'
 '⇒ PRTS+ 内部还有一层**视口/分辨率换算**未体现在资源里 ⇒ 本项目**采用"实测绿格+tile 反解"标定**，`view` 仅作交叉参照；'
 '⑥**★记录用户给出的实机战斗操作流程（PRTS+ 方案）= 实现规格**：'
 '**①统计"费用条满"的次数记绝对时间（次数×30+相位=整帧）→ ②操作前≈1s 进入"子弹时间"（选中/拖出干员使游戏减速）'
 '→ ③操作前 5 帧在子弹时间内逐帧过帧 → ④暂停定位到预定帧 → ⑤在该帧部署干员**；'
 '⑦**对 D1 的新解释（可检验）**：此前"抓取成功、释放不提交"可能是因为**提交时游戏并未暂停在目标帧**'
 '⇒ 下一轮须严格按上述 ①→⑤ 顺序（先建立"帧"再释放）；'
 '⑧**新增文档** `knowledge/04_数据对应与核验/59_实机战斗操作_PRTS+方案与格子定位.md`'
 '（含 PRTS+ 方案、三重互证、操作流程规格、下一轮落地清单）；'
 '⑨**合规**：只读本机 PRTS+ 资源与模拟器配置文件；**未读改游戏文件、未访问内存**。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
