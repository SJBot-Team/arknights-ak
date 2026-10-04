# -*- coding: utf-8 -*-
"""append_r13.py — 记录：绿格可用、nemuwin 层级、F 键的按下/松开语义。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\53_PRTS+部署实现_源码剖析.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

EXTRA = '''

---

## 九、三个实测发现（2026-09-15 续）

### 9.1 ★"绿格"可以直接替代 3D 投影（本方的重要简化）
`calc_view` 存在的意义是"**从轴表的格子号算出屏幕坐标**"。但实测发现：
**点选干员后，游戏会直接把"所有可部署格"高亮成绿色** ⇒
本方可用 `Deployer.find_green_cells()`（HSV 阈值 + 轮廓）直接得到**可部署区域**，
**无需反推 3D 投影参数**。

- 本轮实测：点选卡片后 `find_green_cells()` 稳定返回 2 个绿格（如 (1142,578)、(937,645)）；
- **短期**：用绿格任意一点作为落点即可**验证部署流程**；
- **长期**：若轴表要求**特定格子**，才需要用 `calc_view` 式投影（或"绿格 + 关卡地图布局"反查格子号）。

### 9.2 `nemuwin` 不在主窗口的"直接子窗口"层
实测 `FindWindowExW(main, None, 'nemuwin', None)` **取不到** `nemuwin`（返回的是 `Qt5156QWindowIcon`）；
而枚举子窗口时两者都能看到 ⇒ **`nemuwin` 层级更深**（是 `Qt5156QWindowIcon` 的子窗口）。
⇒ 查找需**递归遍历子窗口**（`EnumChildWindows`）按类名匹配，而不是只看第一层。
**另**：上一轮"向 nemuwin 发消息生效"是通过 UIA 拿到的 hwnd（1247902）直接投递的，
说明**只要句柄对，消息就能生效**；关键是**拿到正确的句柄**。

### 9.3 ★★F 键是"按下=暂停、松开=恢复"（不是切换）
云迹方案的 F 宏定义：
```
press  : ['keyboard_press:158']
release: ['keyboard_release:158']
```
⇒ **按住 F 期间游戏暂停，松开即恢复**。
本方的 `post_key()` 发的是 **down + 30ms + up** ⇒ 表现为"**瞬间暂停后又恢复**"，
在旁观者看来像"切换"——这正是本轮"在暂停态按 F 反而恢复运行"（cost 36→37）的原因。

**⇒ 正确用法（本方应改）**：
- **需要持续暂停**：**只发 `WM_KEYDOWN`（保持按下），操作完成后再发 `WM_KEYUP`**；
- 代码上应新增 `key_down(key)` / `key_up(key)` 两个方法，`post_key` 仅用于"瞬时按键"。

### 9.4 下一步（修正后）
```
1. find_render_hwnd：递归子窗口查找 nemuwin（或直接沿用 UIA 提供的句柄）
2. 新增 WinInput.key_down / key_up；"保持暂停"用 key_down('f') … key_up('f')
3. 部署序列（暂停态）：
     find_cards → 点选卡片 → find_green_cells
     → mousedown(卡片) → 一次 mousemove → (保持暂停即可，无需再按 F)
     → mousemove(绿格) → mouseup(绿格)
     → （定朝向）mousedown(绿格) → mousemove(方向) → mouseup
4. 校验三重判据：卡片消失 / 可放置数 −1 / 费用扣除
```
'''

s = io.open(DOC, encoding='utf-8').read()
if '九、三个实测发现' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新源码剖析文档')

ADD = (' **三个实测发现：绿格可替代 3D 投影 / nemuwin 层级 / F 键按下-松开语义（2026-09-15）**：'
       '①**★绿格可直接替代 3D 投影（本方重要简化）**：`calc_view` 的意义是"从轴表格子号算屏幕坐标"，'
       '但实测**点选干员后游戏直接高亮所有可部署格** ⇒ 用 `find_green_cells()` 即可得到可部署区域，'
       '**无需反推投影参数**（本轮稳定返回 2 个绿格）；短期用绿格任意点即可验证流程，'
       '长期若需精确到特定格子再用投影或反查；'
       '②**`nemuwin` 不在主窗口直接子窗口层**：`FindWindowExW(main, None, "nemuwin", None)` 取不到'
       '（返回 `Qt5156QWindowIcon`）⇒ **需递归遍历子窗口**（EnumChildWindows）按类名匹配；'
       '另：上一轮"向 nemuwin 发消息生效"是**通过 UIA 拿到的句柄(1247902)直接投递**的 ⇒ '
       '**只要句柄正确消息就生效**，关键是拿到正确句柄；'
       '③**★★F 键是"按下=暂停、松开=恢复"，不是切换**：云迹 F 宏为 `press: keyboard_press:158` / '
       '`release: keyboard_release:158` ⇒ **按住期间暂停、松开恢复**；'
       '而本方 `post_key()` 发的是 down+30ms+up ⇒ 表现为"**瞬间暂停又恢复**"，'
       '**这正是本轮"在暂停态按 F 反而恢复运行"（cost 36→37）的原因**；'
       '⇒ **修正：需要持续暂停时应"只发 WM_KEYDOWN（保持），完成后发 WM_KEYUP"**，'
       '故需新增 `WinInput.key_down/key_up`；'
       '④**新增 `plugins/action/calc_view.py`**（PRTS+ `calc_view` 的移植：透视 20°、'
       'rotate_x 30°、side 视图再 rotate_y 10°、格子高度 `heightType*-0.4`、输出 front/side 两套比例坐标），'
       '并实现了 `calibrate_view()`（用实测点反推 view 参数）—— 虽本轮发现绿格可替代，'
       '但该模块在"需精确到指定格子"时仍有用；'
       '⑤**下一步**：递归查找 nemuwin（或沿用 UIA 句柄）→ 新增 key_down/key_up → '
       '按"点选卡片 → 绿格 → mousedown/mousemove/mouseup"跑一次完整部署并三重判据校验；'
       '⑥**合规**：仅窗口消息层注入（不移动真实光标、不抢用户鼠标）；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')

for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\action\win_input.py',
                  r'code\vision\plugins\action'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\action\calc_view.py',
                  r'code\vision\plugins\action')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
