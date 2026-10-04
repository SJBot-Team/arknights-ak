# -*- coding: utf-8 -*-
"""append_prtsplus_impl.py — ★★★★★ PRTS+ 部署算法完整实现（从开源仓库取得）。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\53_PRTS+部署实现_源码剖析.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

MD = '''# PRTS+ 部署实现：源码剖析（2026-09-15）

> 来源：开源仓库 **<https://github.com/jue-ce-zhe/prts-plus>**
> 关键文件：`src/mumu/mumu_controller.py`（输入）、`src/logic/perform_action.py`（部署/技能/撤退）、
> `src/logic/game_time.py`（计时器）、`src/logic/analyze_time.py`（时间读取）、
> `src/logic/calc_view.py`（格子→视角坐标）、`src/logic/locate_avatar.py`（定位干员头像）、
> `src/logic/convert_pos.py`（坐标转换）、`src/config.py`（阈值/比例常量）。

---

## 一、输入层（`mumu_controller.py`）—— 「不抢鼠标」的实现

```python
import win32api, win32con, win32gui
# HANDLE = 游戏窗口句柄（src/mumu/mumu_connection.py 取得）

def mouseclick(pos):    # pos 为像素坐标
    win32api.SendMessage(HANDLE, win32con.WM_LBUTTONDOWN, 0, win32api.MAKELONG(*pos))
    win32api.SendMessage(HANDLE, win32con.WM_LBUTTONUP,   0, win32api.MAKELONG(*pos))

def mousedown(pos):
    win32api.SendMessage(HANDLE, win32con.WM_LBUTTONDOWN, 0, win32api.MAKELONG(*pos))

def mouseup(pos):
    win32api.SendMessage(HANDLE, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, win32api.MAKELONG(*pos))

def mousemove(pos):
    win32api.SendMessage(HANDLE, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, win32api.MAKELONG(*pos))

def pause():   # "暂停/恢复"开关 —— 用**鼠标侧键2**
    win32api.SendMessage(HANDLE, config.WM_XBUTTONDOWN, config.XBUTTON2, config.DEFAULT_COORDINATES)
    win32api.SendMessage(HANDLE, config.WM_XBUTTONUP,   config.XBUTTON2, config.DEFAULT_COORDINATES)

def esc():     # "暂停" —— 用**鼠标侧键1**
    win32api.SendMessage(HANDLE, config.WM_XBUTTONDOWN, config.XBUTTON1, config.DEFAULT_COORDINATES)
    win32api.SendMessage(HANDLE, config.WM_XBUTTONUP,   config.XBUTTON1, config.DEFAULT_COORDINATES)

# 坐标装饰器：**比例(0~1) → 像素**，基于 **GetWindowRect 的完整窗口尺寸**
def handle_coordinates(func):
    @functools.wraps(func)
    def wrapper(pos):
        x, y = pos
        if x < 0 or x > 1 or y < 0 or y > 1: raise ValueError(...)
        wr = win32gui.GetWindowRect(HANDLE)
        w, h = wr[2]-wr[0], wr[3]-wr[1]
        return func((int(x*w), int(y*h)))
    return wrapper
```

**三条要点**：
1. **`SendMessage`（同步）而非 `PostMessage`（异步）**；
2. **坐标基准 = `GetWindowRect` 完整窗口尺寸**，用**比例**；
3. **`WM_MOUSEMOVE` 必须带 `MK_LBUTTON`** ⇒ 不移动真实光标 ⇒ **不抢用户鼠标**。

---

## 二、部署主流程（`perform_action.py::perform_deploy`）

### 2.1 两个阈值
```python
BULLET_THRESHOLD = GameTime(0, actionconfig.BULLET_THRESHOLD)   # 进入"子弹时间"的提前量
FRAME_THRESHOLD  = GameTime(0, actionconfig.FRAME_THRESHOLD)    # "帧级"精度阈值
target_time = action.get_game_time()      # 轴表要求的 (秒, 帧)
```

### 2.2 三段式时序逼近（**不变量：进入此段时游戏处于暂停态**）
```python
if get_game_time() + BULLET_THRESHOLD < target_time:
    # ① 时间还早：先恢复 → 等到"子弹阈值"内 → 进子弹时间 → 再暂停
    logger.debug("Too much time, resuming and entering bullet time")
    pause()                                     # 恢复（当前是暂停态）
    wait_until_threshold(target_time, BULLET_THRESHOLD, user_paused)
    mouseclick(ratioconfig.LAST_OPER_RATIO)     # 点"上一次操作的干员"⇒ 进入子弹时间
    time.sleep(GENERAL_WAITTIME)
    wait_until_threshold(target_time, FRAME_THRESHOLD, user_paused)
    esc()                                       # 暂停
elif get_game_time() + FRAME_THRESHOLD < target_time:
    # ② 已在子弹阈值内：直接进子弹时间
    mouseclick(ratioconfig.LAST_OPER_RATIO)
    pause()
    wait_until_threshold(target_time, FRAME_THRESHOLD, user_paused)
    esc()
else:
    # ③ 已在帧阈值内：只进子弹时间，**不恢复**
    mouseclick(ratioconfig.LAST_OPER_RATIO)
```

### 2.3 ★逐帧推进（这就是"过帧"）
```python
while get_game_time() < target_time:
    pause()                     # 恢复
    time.sleep(actionconfig.FRAME_WAITTIME)
    esc()                       # 再暂停
    if user_paused(): raise UserPausedError()
    time.sleep(actionconfig.GENERAL_WAITTIME)
```

### 2.4 ★部署拖拽（关键序列）
```python
locate_avatar(action)                        # 定位干员头像 → action.avatar_pos（比例坐标）
if action.avatar_pos[1] < OPERATOR_SELECTED_RATIO:
    pass                                     # 已经选中
else:
    mouseclick(action.avatar_pos)            # 点选干员
    locate_avatar(action)                    # 重新定位（位置可能变化）

middle_pos = (action.avatar_pos[0], action.avatar_pos[1] - DEPLOY_DRAG_RATIO)

pause()                                      # 恢复
mousedown(action.avatar_pos)                 # ★ 在头像上按下
mousemove(middle_pos)                        # ★ **只移动一次**（向"上"拖一小段）
time.sleep(MINIMUM_WAITTIME)
esc()                                        # ★ 暂停

actual_time = get_game_time()                # 检查是否准时（不变则 warning）

# 完成部署
mousemove((view_pos_side[0], view_pos_side[1] + DEPLOY_DELTA_RATIO))
time.sleep(GENERAL_WAITTIME)
mouseup((view_pos_side[0], view_pos_side[1] + DEPLOY_DELTA_RATIO))
```

### 2.5 定朝向
```python
if direction == LEFT:  dir_pos = (side_x - DIRECTION_RATIO, side_y)
elif RIGHT:            dir_pos = (side_x + DIRECTION_RATIO, side_y)
elif UP:               dir_pos = (side_x, side_y - DIRECTION_RATIO)
elif DOWN:             dir_pos = (side_x, side_y + DIRECTION_RATIO)
mousedown(view_pos_side)
mousemove(dir_pos)
mouseup(dir_pos)
```

### 2.6 技能 / 撤退（`perform_skill_or_retreat`）
同样的三段式逼近 + 逐帧推进；动作本身是 `mouseclick(SKILL_RATIO)` 或 `mouseclick(RETREAT_RATIO)`。

---

## 三、对"划火柴"的解释

- **`pause()` = 鼠标侧键2**：**在暂停态按 ⇒ 恢复；在运行态按 ⇒ 暂停**（切换语义）；
- **`esc()` = 鼠标侧键1**：**暂停**；
- ⇒ 所谓"划火柴"，本质是 **`mousedown` → `mousemove` → `esc`（暂停）→ `mousemove` → `mouseup`**
  这一串**在暂停/恢复之间穿针引线**的操作，使游戏正好停在目标帧，而鼠标（消息）只在窗口内活动；
- **全程用 `SendMessage`** ⇒ **不移动真实光标 ⇒ 不抢用户鼠标**。

## 四、本方需要对齐的点
1. **输入层**：改用 `SendMessage` + `GetWindowRect` 比例坐标 + `WM_MOUSEMOVE(MK_LBUTTON)`（已实现 `sm_mouse/sm_drag`）；
2. **暂停/恢复**：改用**鼠标侧键**（侧键2 切换、侧键1 暂停）—— 比"点暂停按钮"更稳，且不依赖坐标；
3. **部署序列**：**一次 mousemove + 中途 esc 暂停 + 再 mousemove + mouseup**（本方此前用多次 mousemove，应改）；
4. **坐标**：需要 `calc_view` / `locate_avatar` 那类"**格子→屏幕比例坐标**"的映射（可用关卡数据 + 视角变换实现）；
5. **计时**：`game_time.py` / `analyze_time.py` 与我们的**费用尺相位计时**目标一致，可互相印证。
'''

io.open(DOC, 'w', encoding='utf-8').write(MD)
print('已写出 PRTS+ 源码剖析:', DOC)

ADD = (' **★★★★★取得 PRTS+ 部署算法完整实现（开源仓库源码剖析）2026-09-15**：'
       '①**来源**：`github.com/jue-ce-zhe/prts-plus`（含 `src/mumu/`、`src/logic/`、`src/utils/`、'
       '`sample 1-7.xlsm` 示例轴表等），关键文件 **`src/mumu/mumu_controller.py`** 与 '
       '**`src/logic/perform_action.py`**；'
       '②**输入层（"不抢鼠标"的实现）**：用 **`win32api.SendMessage`（同步，非 PostMessage）** 投递 '
       '`WM_LBUTTONDOWN/UP`、**`WM_MOUSEMOVE` 带 `MK_LBUTTON`**；**坐标用 `GetWindowRect` 完整窗口尺寸的"比例"换算**；'
       '**`pause()` = 鼠标侧键2（切换暂停/恢复）、`esc()` = 鼠标侧键1（暂停）**；'
       '③**部署主流程（`perform_deploy`）**：'
       '(a) **两个阈值** `BULLET_THRESHOLD`/`FRAME_THRESHOLD` 做**三段式时序逼近**'
       '（时间还早 ⇒ 恢复+等到子弹阈值+进子弹时间；在子弹阈值内 ⇒ 直接进；已在帧阈值内 ⇒ 只进不恢复）；'
       '(b) **★逐帧推进（即"过帧"）**：`while get_game_time() < target: pause(); sleep(FRAME_WAITTIME); esc()`；'
       '(c) **★部署拖拽序列**：`locate_avatar` 定位头像 → `mouseclick(avatar_pos)` 点选 → '
       '`pause()` 恢复 → **`mousedown(avatar_pos)` → `mousemove(middle_pos)`（只移动一次！）→ `esc()` 暂停** → '
       '`mousemove(view_pos_side+delta)` → `mouseup(...)`；'
       '(d) **定朝向**：`mousedown(view_pos_side)` → `mousemove(dir_pos)` → `mouseup(dir_pos)`（四方向由 DIRECTION_RATIO 决定）；'
       '(e) 技能/撤退同用三段式逼近 + 逐帧推进，动作为 `mouseclick(SKILL_RATIO/RETREAT_RATIO)`；'
       '④**对本方的三条修正**：(a) 输入层改用 SendMessage + GetWindowRect 比例坐标 + MK_LBUTTON；'
       '(b) **暂停/恢复改用鼠标侧键**（侧键2 切换、侧键1 暂停），比点按钮更稳且不依赖坐标；'
       '(c) **部署序列改为"一次 mousemove + 中途 esc 暂停 + 再 mousemove + mouseup"**（本方此前用多次 mousemove，应改）；'
       '⑤**产出 `knowledge/04/53_PRTS+部署实现_源码剖析.md`**（输入层、部署主流程、逐帧推进、划火柴解释、本方待对齐点）；'
       '⑥**下一步**：把 `win_input` 的暂停/恢复切到侧键；按 PRTS+ 序列重写 `deploy`；'
       '实现"格子→屏幕比例坐标"映射（对应它的 `calc_view`/`locate_avatar`）；'
       '⑦**合规**：仅窗口消息层注入（不移动真实光标、不抢用户鼠标）；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
