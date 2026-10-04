# -*- coding: utf-8 -*-
"""append_round52.py — 第 52 轮：导航可测化重构 + 离线测试 4/4。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.106 导航可测化重构：`plugins/nav/auto_enter.py`

导航逻辑此前写在 `apps/auto_sample_v2.py` 的 `main()` 里，**无法离线测试**，
只能靠实机反复试错（而实机又常被渲染冻结、界面状态漂移打断，前几轮的时间大量耗在这里）。
本轮抽成 `AutoEnter` 类（依赖注入：采集器 / 注入器 / 界面判定器 / 日志），因此可以：

- 用**真实界面帧**当"假采集器"驱动决策链，**离线**验证每一种界面序列；
- 合规约束**写死在逻辑里**：只点「演习」/编队「开始行动」/「继续」/关卡节点，
  **不点关卡详情里那个会消耗理智的「开始行动」**；
- 「开始行动」的位置**由模板给出**（`UiState` 的 `start_point`），不再硬编坐标。

### 7.107 导航离线测试 4/4 PASS（`apps/test_auto_enter.py`）

| 用例 | mock 界面序列 | 断言 | 结果 |
|---|---|---|---|
| A 已在战斗 | `[battle]` | 立即返回 True 且**一次都不点** | PASS |
| B 详情→编队→战斗 | `[detail, squad, squad, battle…]` | 点 `(1441,983)`「演习」+ **点模板给出的 `(1655,759)`「开始行动」** | PASS |
| C 结算→详情→编队→战斗 | `[unknown, unknown, detail, squad, squad, battle…]` | 先点 `(960,988)`"继续"两次，再走 B 的链路 | PASS |
| D 一直 unknown | `[unknown]×8` | 步数用尽返回 False，**且只点"继续"**（不死循环） | PASS |

另：所有用例都断言**从未点击可能消耗理智的位置**（`FORBIDDEN = {(1710,990),(1751,991),(1770,986),(1753,1054)}`）✓
⇒ 这条断言把"必须走演习"从口头约束变成了**可回归的测试**。

### 7.108 全套离线回归（含两项新增）全绿
```
frame_clock 4/4 | ruler_clock 7/7 | costbar_axis 2/2 | skill_ready 3/3 | nav_flow 4/4
暂停协议 5/5 | 自动进关 4/4 | 界面判定 8/8
```

### 7.109 断点（不变）
实机**相位↔墙钟精度验收**仍待跑（渲染冻结，需重启模拟器实例；重启可能触发重新登录，等用户决定）。
验收所用脚本（`instant_sample.py` / `auto_sample_v2.py` / `AutoEnter`）与判定器均已就绪。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.105 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.110 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.106~§7.109')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第五十二轮（导航可测化重构 + 离线测试 4/4）**：渲染仍冻结 ⇒ 继续离线工程化；'
       '①**把导航抽成 `plugins/nav/auto_enter.py`（`AutoEnter` 类，依赖注入采集器/注入器/界面判定器）**——'
       '此前导航写在脚本 main() 里**无法离线测试**，只能靠实机试错（前几轮大量时间耗在此）；'
       '②**导航离线测试 4/4 PASS**（`apps/test_auto_enter.py`，用真实界面帧当假采集器驱动决策链）：'
       '(A) 已在战斗⇒立即返回且**一次都不点**；(B) 详情→演习(1441,983)→**点模板给出的开始行动(1655,759)**→战斗；'
       '(C) 结算⇒先点"继续"(960,988)两次再走 B 链；(D) 一直 unknown⇒步数用尽失败退出且**只点"继续"**（不死循环）；'
       '③**合规约束变成可回归断言**：所有用例断言**从未点击可能消耗理智的位置**'
       '（FORBIDDEN={(1710,990),(1751,991),(1770,986),(1753,1054)}）⇒ 把"必须走演习"从口头约束变成测试；'
       '④**全套离线回归全绿**：frame_clock 4/4、ruler_clock 7/7、costbar_axis 2/2、skill_ready 3/3、nav_flow 4/4、'
       '暂停协议 5/5、自动进关 4/4、界面判定 8/8；'
       '⑤**断点不变**：实机相位↔墙钟精度验收待跑（渲染冻结，需重启实例，可能触发重新登录，等用户决定）；'
       '⑥合规：全程仅演习、理智未消耗；不碰游戏内存。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第五十二轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
for rel in (r'code\vision\plugins\nav\auto_enter.py', r'code\vision\apps\test_auto_enter.py'):
    d = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel), d)
print('同步完成')
