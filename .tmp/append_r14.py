# -*- coding: utf-8 -*-
"""append_r14.py — 记录：key_down/key_up 成功、递归窗口查找成功、拖拽待排查。"""
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

## 十、本方实现进展与待排查项（2026-09-15 续）

### 10.1 ✅ 已解决（本轮确定可用）
| 项 | 结果 |
|---|---|
| **递归查找渲染窗口** | ✅ `EnumChildWindows` 按类名取到 **`nemuwin`（hwnd 1247902）**（`FindWindowEx` 只看第一层取不到） |
| **`key_down` / `key_up`** | ✅ **实现并验证**：`key_down('f')` ⇒ 画面稳定停在 **PAUSE/暂停中**（F 是"按下暂停、松开恢复"） |
| **点选干员** | ✅ 向 `nemuwin` 发 `sm_mouse('click', 卡片)` ⇒ **弹出干员详情 + 地图高亮绿色可部署格** |
| **绿格检测** | ✅ `find_green_cells()` 稳定返回 2~3 个绿格（如 (1139,584)、(936,646)） |

### 10.2 ❌ 仍未完成：拖拽/点格均未提交部署
已尝试（均无效果，`cost` 不变、卡片不减）：
1. **选中后直接点绿格**（`sm_mouse('click', 绿格)`）；
2. **按 PRTS+ 序列**：点选（暂停态）→ `key_up('f')` 恢复 → `mousedown(卡片)` → `mousemove(中间位)` →
   `key_down('f')` 暂停 → `mousemove(绿格)` → `mouseup(绿格)`；
3. 全程保持暂停时做同样拖拽。

**参数与 PRTS+ 逐项核对一致**：
- 目标窗口 `nemuwin` ✅；`SendMessage` ✅；`WM_LBUTTONDOWN` wParam=0 ✅；
  `WM_MOUSEMOVE`/`WM_LBUTTONUP` wParam=`MK_LBUTTON` ✅；`MAKELONG(x,y)=(y<<16)|x` ✅；
  坐标 = `GetWindowRect` 尺寸 × 比例 ✅。
⇒ **仍失败，说明差异在别处**。

### 10.3 待排查方向（下一轮）
1. **卡片坐标**：本方 `find_cards()` 只返回 2 个卡片（(709,1002)、(1709,1002)），
   可能与真实 12 张卡片的位置不符 ⇒ **先用截图核对卡片真实坐标**，再用正确的卡片坐标点选/拖拽；
2. **点选是否真的"选中了要部署的干员"**：绿格出现说明"有干员处于选择态"，
   但可能是"点到了详情面板"而非"选中待部署" ⇒ **需对比"选中态"与"仅查看详情"的画面差异**；
3. **拖拽是否需要"真实鼠标"**：PRTS+ 源码用 `SendMessage`，但也许其**键鼠方案/驱动**在其中起作用
   ⇒ 可做对照实验：同一序列改用**真实鼠标**（`SetCursorPos`+`SendInput`）看是否成功；
4. **是否需要"多次 mousemove"**：PRTS+ 只写了一次 `mousemove`，但真实拖拽可能需要
   连续多个坐标点才能让游戏识别为"拖动" ⇒ 试 5~20 个插值点；
5. **确认游戏是否处于"可部署"状态**：费用是否足够该卡（本轮 cost 46，卡片费用可能 7~18）；
   以及"该格子"对该干员类型（近战/远程）是否合法（**绿格已由游戏给出，应合法**）。

### 10.4 建议的下一步实验（成本低、结论明确）
```
① 截图核对 12 张卡片的真实 x 中心（用列方差法或直接目视）
② 用"正确的卡片坐标"点选，截图确认"详情面板 + 绿格"两特征同时出现
③ 拖拽改用 8 个插值点的 mousemove 序列（而非 1 个点）
④ 若仍失败，用真实鼠标做同一序列作为对照（可判定"是否需要真实输入"）
```
'''

s = io.open(DOC, encoding='utf-8').read()
if '十、本方实现进展与待排查项' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新源码剖析文档')

ADD = (' **两项确定进展 + 拖拽待排查（2026-09-15）**：'
       '①**✅ 递归查找渲染窗口成功**：`EnumChildWindows` 按类名取到 **`nemuwin`（hwnd 1247902）**'
       '（`FindWindowEx` 只看第一层取不到）；'
       '②**✅ 实现并验证 `key_down`/`key_up`**：**`key_down("f")` ⇒ 画面稳定停在 PAUSE/暂停中**'
       '（印证"F 是按下暂停、松开恢复"）；'
       '③**✅ 点选干员成功**：向 `nemuwin` 发 `sm_mouse("click", 卡片)` ⇒ **弹出干员详情 + 地图高亮绿色可部署格**；'
       '`find_green_cells()` 稳定返回 2~3 个绿格；'
       '④**❌ 仍未完成：拖拽/点格均未提交部署**（cost 不变、卡片不减）——已试三种方式：'
       '(a) 选中后直接点绿格；(b) **按 PRTS+ 序列**（点选 → 恢复 → mousedown(卡片) → mousemove(中间位) → '
       '暂停 → mousemove(绿格) → mouseup）；(c) 全程保持暂停做同样拖拽；'
       '**参数与 PRTS+ 逐项核对全部一致**（目标窗口 nemuwin、SendMessage、wParam 取值、MAKELONG 顺序、'
       '坐标=GetWindowRect×比例）⇒ **差异在别处**；'
       '⑤**下轮排查方向**：(a) **先用截图核对 12 张卡片的真实坐标**（本方 `find_cards` 只返回 2 个，存疑）；'
       '(b) 确认"点选"是"选中待部署"而非"仅查看详情"（对比两者画面差异）；'
       '(c) 拖拽改用 **8 个插值点**的 mousemove 序列；'
       '(d) **用真实鼠标做同一序列作为对照**，判定"是否需要真实输入"；'
       '(e) 确认费用是否足够该卡片、以及格子类型（近战/远程）是否匹配；'
       '⑥**合规**：仅窗口消息层注入（不移动真实光标）；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
