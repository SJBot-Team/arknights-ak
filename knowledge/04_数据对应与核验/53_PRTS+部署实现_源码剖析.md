# PRTS+ 部署实现：源码剖析（2026-09-15）
> 主题：**04E 实机 / 打图操作**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）
> 层级：**T2（数据/流程整理类（未含强代码证据））**　建立日期：2026-09-15（头部 6 行内日期）　任务：—　来源：开源仓库 **<https://github.com/jue-ce-zhe/prts-plus>**　｜　**头部为 2026-09-30 …

> ⚠️ **部分过期（2026-09-23）**：本机 `D:\__soft\ak\prts+` 的 exe **比本文依据的公开分支新**。
> **计时器（`game_time.py`）、费用封顶、控制面（`中转站!B1/B2/B3`）等结论以 `64b_prts+轴表与控制面_参考表.md` 为准**；
> 本文的**部署/技能/撤退动作序列与坐标换算部分**仍然有效（`49`/`59` 的实测可互证）。
> 关键差异：`_update_time_counter` **只在 tick 回绕时 `time+=1`**，而 tick 唯一来源是费用条白像素占比 ⇒ **费用封顶后计时冻结**（`while get_game_time()<target` 永不退出）。
> 另：xlsm 是**双向**的——外部写 `中转站!B1='停止中'` 即可暂停它。详见 `64_MAA与prts+_GUI操作方案.md` §二。

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


---

## 五、常量配置（`src/config.py` 全文摘录）★关键参数

```python
class MuMuEmulatorConfig:
    DEFAULT_COORDINATES = 0x00640064      # (100,100) 默认坐标
    WINDOW_NAME     = "MuMu模拟器12"       # 主窗口
    SUB_WINDOW_NAME = "MuMuPlayer"        # ★ 子窗口（本方此前误用 UIA 的 class 名 nemuwin）
    WM_XBUTTONDOWN, WM_XBUTTONUP = 0x020B, 0x020C
    XBUTTON1, XBUTTON2 = 0x00010000, 0x00020000

class GameRatioConfig:                    # 全部为**比例坐标(0~1)**
    COST_AREA_RATIO        = (0.906, 0.685, 1, 0.755)   # 费用条区域
    COST_NUMBER_AREA_RATIO = (0.33, 0, 1, 0.9)
    OPERATOR_AREA_RATIO    = (0, 0.8, 1, 1)             # 待部署区
    LAST_OPER_RATIO        = (0.95, 0.9)                # 上一次操作的干员（用于进子弹时间）
    RETREAT_RATIO          = (0.4569, 0.3352)
    SKILL_RATIO            = (0.6412, 0.5857)
    START_BUTTON_RATIO     = (0.87, 0.74)
    SPEED_BUTTON_RATIO     = (0.86, 0.07)               # 倍速按钮
    PAUSE_BUTTON_RATIO     = (0.94, 0.07)               # 暂停按钮
    DIRECTION_RATIO        = 0.2                        # 定朝向拖动距离
    DEPLOY_DRAG_RATIO      = 0.03                       # 部署拖拽距离（头像向上拖）
    DEPLOY_DELTA_RATIO     = 0.02                       # 部署落点偏移
    OPERATOR_SELECTED_RATIO= 0.9                        # 判断"已选中"的 y 阈值

class ImageProcessingConfig:
    WHITE_THRESHOLD = 160
    SCREEN_STANDARD_SIZE = (1280, 720)
    AVATAR_STANDARD_SIZE = (120, 120);  AVATAR_CROP_SIZE = (60, 60)
    OCR_CONFIDENCE_THRESHOLD = 60;  TEMPLATE_MATCH_THRESHOLD = 0.8

class ViewCalculationConfig:              # 坐标映射用
    FROM_RATIO = 9/16;  TO_RATIO = 3/4;  NEAR = 0.3;  FAR = 1000

class GameTimeConfig:
    TICK_MAX_DEFAULT = 30                 # ★ 1 秒 = 30 tick（与费用尺口径一致）

class PerformActionConfig:                # ★★ 核心时序参数
    BULLET_THRESHOLD = 15                 # 进入"子弹时间"的提前量（帧）
    FRAME_THRESHOLD  = 2                  # 帧精度阈值（帧）
    MINIMUM_WAITTIME = 0.02
    FRAME_WAITTIME   = 0.1                # ★ 逐帧推进的等待：恢复 → 等 100ms → 暂停
    GENERAL_WAITTIME = 0.3
```

**与己方观测的互证**：
- `PAUSE_BUTTON_RATIO=(0.94,0.07)` ⇒ 帧 (1805,76)，与本方实测的 (1806,80)、MAA 换算的 (1807,79) **三者一致**；
- `BULLET_THRESHOLD=15` / `FRAME_THRESHOLD=2` 与它运行日志中的
  `Set bullet threshold to 15.0` / `Set frame threshold to 2.0` **完全一致**；
- `TICK_MAX_DEFAULT=30`（1 秒 30 tick）与本方"费用条满一次 = 30 帧"的结论**一致**。

---

## 六、坐标映射算法（`src/logic/calc_view.py`）★补全"格子→屏幕坐标"

PRTS+ 用**3D 透视投影**把地图格子映射为**屏幕比例坐标**：

```python
DEGREE = math.pi / 180
height, width = level["height"], level["width"]
x, y, z = level["view"][1 if side else 0]        # ★ 视角参数取自关卡数据

transform_matrix = [[1,0,0,-x],[0,1,0,-y],[0,0,1,-z],[0,0,0,1]]      # 平移
perspective_matrix = [[FROM_RATIO/tan(20°),0,0,0],                   # 20° 视角
                      [0,1/tan(20°),0,0],
                      [0,0,-(FAR+NEAR)/(FAR-NEAR), -(FAR*NEAR*2)/(FAR-NEAR)],
                      [0,0,-1,0]]
rotate_x_matrix = 绕 X 轴 30°（俯视角）
rotate_y_matrix = 绕 Y 轴 10°（仅 side 视图）

final = perspective @ rotate_x @ ([rotate_y] if side else I) @ transform

for i in range(height):
  for j in range(width):
    tile = level["tiles"][i][j]
    map_point = [j-(width-1)/2, (height-1)/2-i, tile["heightType"]*-0.4, 1]   # 格子中心（含高度偏移）
    vp = final @ map_point
    vp = vp / vp[3]                  # 透视除法
    vp = (vp + 1) / 2                # NDC → [0,1]
    out[i][j] = (vp[0], 1 - vp[1])   # ★ y 反转，得到屏幕比例坐标
```

**要点**：
1. **正视(front)与侧视(side)两套矩阵**：部署用 `view_pos_side`、技能/撤退用 `view_pos_front`；
2. **格子高度参与投影**：`heightType * -0.4`（高台格在屏幕上更靠上）；
3. **视角参数 `level["view"]` 来自关卡数据** ⇒ 本方也能取到（`mapData` 同级字段）；
4. 输出即 **`mouseclick(pos)` 需要的比例坐标** ⇒ 与本方的"帧坐标 / 1920×1080"可直接换算
   （比例 = 帧坐标 / 分辨率）。

---

## 七、本方待对齐清单（按 PRTS+ 修正）

| # | 项 | 本方当前 | 应改为（PRTS+） |
|---|---|---|---|
| 1 | 鼠标注入 | `PostMessage` ✗ | **`SendMessage`（同步）** |
| 2 | 移动事件 | `WM_MOUSEMOVE` 无 `MK_LBUTTON` | **带 `MK_LBUTTON`** |
| 3 | 坐标基准 | 客户区 + 标题栏校正 | **`GetWindowRect` 完整窗口 × 比例** |
| 4 | 子窗口 | `nemuwin`（UIA class） | **`MuMuPlayer`** |
| 5 | 暂停/恢复 | 点暂停按钮 | **鼠标侧键2（切换）**；**侧键1 = 暂停** |
| 6 | 部署拖拽 | 多次 mousemove | **一次 mousemove + 中途 `esc()` 暂停 + 再 mousemove + mouseup** |
| 7 | 坐标映射 | 手工估格子坐标 | **用 `calc_view` 式 3D 投影（front/side 两套）** |
| 8 | 逐帧推进 | 无 | **`while time<target: 恢复 → sleep(0.1) → 暂停`**（子弹时间下 1 次 ≈ 1 帧） |
| 9 | 阈值 | 无 | **BULLET_THRESHOLD=15、FRAME_THRESHOLD=2** |


---

## 八、窗口目标与侧键的实测修正（2026-09-15 续）

### 8.1 窗口层级（实测枚举）
```
主窗口   hwnd=4000354  class=ShellWindow  title="MuMu模拟器12"   GetWindowRect=1306×796
 └ Qt5156QWindowIcon   hwnd=3212124      （外层容器）
 └ nemuwin             hwnd=1247902      （渲染/接收输入）
```
- **`MuMuPlayer` 不是"窗口类名"，而是"窗口标题"** —— PRTS+ 的 `SUB_WINDOW_NAME` 是用
  `FindWindow(标题)` 取的（本方先前按 class 找，自然找不到）；
- **★实测：向 `nemuwin`（渲染子窗口）发 `SendMessage` 鼠标消息 ⇒ 生效**
  （成功弹出干员详情面板 + 地图出现绿色可部署高亮格）；
- **★实测：向"主窗口"发同样的消息 ⇒ 无效**（侧键、鼠标均无反应）
  ⇒ **目标窗口应为渲染子窗口 `nemuwin`**。

### 8.2 鼠标侧键依赖键鼠方案
- PRTS+ 用**鼠标侧键**做 `pause()`（侧键2）/`esc()`（侧键1），但那是它**自己的键鼠方案**
  （`PRTS+键鼠方案示例.json`）里绑定的；
- **本机当前启用的是"云迹方案"，其中并没有侧键绑定** ⇒
  **向窗口投递 `WM_XBUTTONDOWN/UP` 无任何效果**（已实测）；
- ⇒ **本方暂用"键盘宏"替代**：**F = 时停（切换）**、**R/T/Y = 过帧**（均已实测生效），
  这与云迹方案匹配；若将来切换到 PRTS+ 方案，则可改用侧键。

### 8.3 PRTS+ 部署序列的要点（再强调，便于本方实现）
```python
mouseclick(action.avatar_pos)          # ① 点选干员（avatar_pos 是"卡片头像"的比例坐标）
pause()                                # ② 恢复（切换）
mousedown(action.avatar_pos)           # ③ 在头像上按下
mousemove(middle_pos)                  # ④ 只移动一次：middle_pos = (x, y - DEPLOY_DRAG_RATIO)
esc()                                  # ⑤ 暂停
mousemove(view_pos_side + DELTA)       # ⑥ 移到目标格（3D 投影算出的 side 视图坐标）
mouseup(view_pos_side + DELTA)         # ⑦ 抬起 ⇒ 完成部署
# ⑧ 定朝向：mousedown(view_pos_side) → mousemove(dir_pos) → mouseup(dir_pos)
```
**关键差异点（本方此前缺失）**：
- **④ 只移动一次**（不是多次）；
- **⑤ 中途 `esc()` 暂停**（这是"划火柴"的核心节奏）；
- **⑥⑦ 的落点是 `view_pos_side`（3D 投影坐标）**，不是"看起来像格子的像素位置"。

### 8.4 下一步
1. `find_render_hwnd` 回退到 **`nemuwin`**（本方实测有效）；
2. **实现 3D 投影坐标映射**（`calc_view` 式，front/side 两套），用关卡数据的 `view` 参数；
3. 按 8.3 序列跑一次完整部署，并用"卡片消失 / 可放置数 −1 / 费用扣除"三重判据校验；
4. 逐帧推进用 **`F` 时停 + `T/R/Y` 过帧**（云迹方案），并在每步读相位闭环校验。


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


---

## 十一、三项修正与当前状态（2026-09-15 续）

### 11.1 ✅ 卡片检测改进（根因之一）
旧 `find_cards()` 只用"列标准差"分段 ⇒ **把相邻卡片合并**，实测只返回 **2 段**
（(709,1002)、(1709,1002)）—— **而 (709,…) 正落在第 5~6 张卡片之间的间隙**，
所以"点选"根本没点到卡片上。

**改进版**（列梯度能量 `Sobel_x` + 列亮度均值 双通道，取分段较多者）：
实测 12 张卡片 ⇒ 返回 **10 段**，中心 **`[100, 275, 458, 627, 801, 980, 1136, 1352, 1644, 1858]`**，
可视化（`apps/card_probe.py` 画出红框+中线）**与画面吻合**。
⇒ **点选随即生效**（弹出干员详情 + 绿色可部署格稳定出现）。

### 11.2 ✅ 窗口查找的关键修正（根因之二）
PRTS+ 的 `src/mumu/mumu_connection.py` 全文要点：
```python
PARENT_HANDLE = win32gui.FindWindow(None, "MuMu模拟器12")               # 主窗口（按标题）
HANDLE = win32gui.FindWindowEx(PARENT_HANDLE, 0, None, "MuMuPlayer")    # ★ 子窗口：**按标题**找
# 其日志：Found the game window with handle 7801904, parent handle 983350
```
**两个要点**：
1. **`MuMuPlayer` 是"窗口标题"**（class 参数传 `None`）—— 本方此前按 class 找，自然失败；
2. **它拿到的 `HANDLE` = 7801904**，正是本方此前独立发现的 **`render_wnd`**
   ⇒ **目标窗口就是 render_wnd**。

### 11.3 ✅ DPI 感知（根因之三，PRTS+ 也做了）
```python
ctypes.windll.shcore.SetProcessDpiAwareness(2)     # PROCESS_PER_MONITOR_DPI_AWARE
```
**为什么关键**：若进程**不是** DPI-aware，`GetWindowRect` 返回的是**被 DPI 缩放后**的坐标
⇒ "帧坐标 → 窗口像素"的换算会整体偏移。本机屏幕 2560×1600 而窗口 1306×796，**存在缩放**
⇒ 本方已在 `WinInput.__init__` 中加入该调用。

### 11.4 当前状态
| 环节 | 状态 |
|---|---|
| 卡片检测 | ✅ 10 段，中心正确 |
| 目标窗口 | ✅ 按标题 `MuMuPlayer` 找到（3212124，与 PRTS+ 的 HANDLE 同类） |
| DPI 感知 | ✅ 已设置 |
| 暂停（点按钮） | ✅ |
| **F 键保持暂停** | ⚠️ **时好时坏**：上一轮 `key_down('f')` 稳定保持；本轮"先 `key_up` 再 `key_down`"后**未保持**（cost 46→47）⇒ 需排查"快速 up/down 配对"的时序 |
| **点选干员** | ✅ 稳定生效（详情 + 绿格） |
| **拖拽提交部署** | ❌ **仍未成功**（cost 不变、卡片不减） |

### 11.5 下一步
1. **暂停用"点按钮"而非 F**：F 的 up/down 语义容易出错；`ensure_paused()`（点暂停按钮 + 两次读数确认）
   已被证明可靠 ⇒ **部署全程用 `ensure_paused` 保证暂停，不依赖 F**；
2. **在"确认暂停"之后**再执行 PRTS+ 拖拽序列（mousedown → 一次 mousemove → 暂停保持 → mousemove → mouseup），
   去掉序列中的 `key_up/key_down('f')`；
3. 若仍失败，做**对照实验**：同一序列改用**真实鼠标**（`SetCursorPos`+`SendInput`）执行，
   以判定"本机是否必须使用真实输入"；
4. 另可尝试 `SendMessage` 的**超时变体** `SendMessageTimeout`，或改用 `PostMessage` 到该窗口配合更长间隔。


---

## 十二、A/B 对照实验与三条机制发现（2026-09-15 续）

### 12.1 A/B 对照：**两种输入通道都失败**（重要结论）
在同一状态下分别执行"点选卡片 → 拖到绿格"：

| 通道 | 结果 |
|---|---|
| **A：`SendMessage`（后台、不抢鼠标）** | 卡片 (100,1007)、绿格 (1142,578)、**cost 57→57（Δ=0）** |
| **B：真实鼠标（`SetCursorPos`+`SendInput`，右键拖拽）** | 卡片 (100,1007)、绿格 (1273,553)、**cost 57→57（Δ=0）** |

**⇒ 两种通道都失败 ⇒ 排除"输入通道"这一假设**（此前怀疑的 PostMessage/SendMessage/真实鼠标差异
并非主因）。问题在**操作语义或坐标**。

### 12.2 ★"绿色可部署格"只在**暂停态**出现
| 状态 | 点卡片后 |
|---|---|
| **暂停态** | ✅ **出现绿色高亮格**（可部署范围） |
| **运行态** | ❌ **不出现绿格** |

⇒ 绿格是"**暂停态下的选择态提示**"；这也解释了"运行态点卡片→点格子"为什么无效。

### 12.3 ★卡片上的"可点区域"有讲究
在同一张卡片上按不同 y 点击（x=99，卡片区 y≈940~1075）：

| 点击 y | 绿格数 |
|---|---|
| 965 | 0 |
| **980** | **3** ✅ |
| 1000 | 0 |
| **1030** | **3** ✅ |

⇒ **y≈980（头像上部）与 y≈1030（卡片下部）可触发"选中"**，而 y≈965/1000 落在"空隙/不可点区"。
**此前一直用 y=1007（卡片中心）**，恰好处在"可点区之外"或其语义不是"选中"。

### 12.4 当前卡点
**"选中"已能稳定触发（绿格出现），但"点绿格"或"拖到绿格"都不提交部署**（cost 不变、卡片不减）。
且已确认：费用充足（cost 57，卡片费用 ≤22）、格子由游戏自身高亮（必然合法）。

### 12.5 下一轮（按优先级）
1. **拖动起点改用 y≈980 或 1030**（此前用的 1007 在可点区外）
   ⇒ 完整序列：暂停 → 点卡片(y=980) → 确认绿格 → **mousedown(卡片, y=980)** →
   mousemove(中间点) → mousemove(绿格) → mouseup(绿格)；
2. **点绿格时改用"格子的中心"而非"绿块质心"**：绿块可能是**多个格子的联合区域**，
   其质心可能落在"格子边界/不可部署处" ⇒ 应先按格子尺寸（约 130×130 帧像素）切分绿块再取格心；
3. 若仍失败，**请用户手动操作一次**（暂停 → 点干员 → 放格子），我截取"操作前后"的画面差异，
   据此反推正确语义；
4. 亦可读 PRTS+ 的 `locate_avatar.py` 与 `src/utils/`（本轮网络两次失败，可稍后重试）。
