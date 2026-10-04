# PRTS+ 四项确认（控制格 / 常量表 / 列映射 / 坐标换算）

> 对象：`D:\__soft\ak\prts+\prts+.exe`（PyInstaller onedir，Python 3.9）+ 样本 `D:\__soft\ak\prts_plan_h124.xlsm`
> 方法：①公开源码逐字（`main`/`develop`/`release-0.2.0`，经 ghproxy 镜像取 raw）；
> ②**自写 PyInstaller/PYZ 提取器 + Python 3.9 marshal 读取器**（Python 3.13 的 `marshal.loads` 无法读 3.9 code object），解出 `co_code/co_consts/co_names` → 打包版常量与函数结构；
> ③样本 xlsm 用 `zipfile` 直读 OOXML（表头、单元格、dataValidation 提示、隐藏页）；
> ④本机真实运行日志 `.tmp\prts_side_231813.log`（2026-09-14 实跑该 H12-4 计划）。
> 产出脚本与证据：`.tmp\{pyz_scan.py, pyz_toc.py, extract_strings.py, marshal9.py, dump_xlsm.py, val.py}`；
> 证据文件：`.tmp\{str_src_*.txt, const_src_config.txt, h124_dump.txt, validations.txt, pyz/module_list.txt}`。
> ⚠️ 结论 1–4 均已用于核对 `knowledge\64b` 的 §七"未查明项"1、3、4、5、6。

---

## 1. 控制格的确切地址 ✅（源码级 + 磁盘样本互证）

**sheet**：`中转站`（隐藏页，`state="hidden"`）；**写回动作记录用**：`作战记录`。

`src/excel.py`（公开源码逐字；打包版 `str_src_excel.txt` 中同名串完全一致）：

```python
try:
    self.record_sheet  = self.workbook.Sheets("作战记录")
    self.control_sheet = self.workbook.Sheets("中转站")
except com_error: ...
...
# Note: All excel index should be 0-based in the code, adding 1 when interacting with Excel
self.data_loc['cur_status'] = (0, 1)   # B1 cell
self.data_loc['cur_row']    = (1, 1)   # B2 cell
self.data_loc['err_log']    = (2, 1)   # B3 cell

@connection_handler
def set_control_value(self, control_name, value):
    self.control_sheet.Cells(self.data_loc[control_name][0] + 1,
                             self.data_loc[control_name][1] + 1).Value = value

def is_paused(self) -> bool:
    return self.get_control_value('cur_status') == '停止中'
def set_paused(self) -> None:
    self.set_control_value('cur_status', '已停止')
def show_error(self, message) -> None:
    self.set_control_value('err_log', message)
```

| 单元格 | 名称 | 写入者 | 语义 / 取值 |
|---|---|---|---|
| **中转站!B1** | `cur_status` | `_signal_start()` 写 `运行中`；`set_paused()` 写 `已停止`；用户/宏按"停止"写 **`停止中`**；出错后 `finally:` 也会 `set_paused()` | **`is_paused()` ⇔ B1 恰等于字符串 `停止中`**（脚本唯一的外部停止通道） |
| **中转站!B2** | `cur_row` | `_signal_start()` 读它定起始行：`self.current_row = int(get_control_value('cur_row')) - 1`；`next_action()` 每步写 `current_row + 1` | **1 基的"当前操作"行号**（对应 A 列指针 `→`） |
| **中转站!B3** | `err_log` | `_signal_start()` 清空；`show_error(msg)` 写错误文案 | 报错信息 |
| 作战记录!A（`当前执行`） | `cur_exec` | `_reset_cells()` 写 `→`；`next_action()` 逐行搬移 | 当前行指针（`→`） |
| 作战记录!K（`运行结果`） | `result` | `set_result(StatusColor)` 给 `Interior.Color` 上色：SUCCESS=`0x77FF77`(绿)/WARNING=`0x77FFFF`(黄)/FAILURE=`0x7777FF`(红) | 每步成功/延迟/失败 |
| 作战记录!M/N（`设置`/值） | `settings` | 只读：`data_loc[x] = (locate_row(settings_col, x), settings_col + 1)` | M=标签、N=值 |

✅ **磁盘样本独立互证**（`python .tmp\dump_xlsm.py` 读 `xl/worksheets/sheet4.xml`）：
`A1='当前状态' B1='停止中'`、`A2='当前操作' B2='2'`、`A3='报错信息' B3='错误：无法识别当前费用。'`
⇒ 标签在 A 列、值在 **B1/B2/B3**，与源码 `(0,1)/(1,1)/(2,1)` 完全吻合（该文案即 `analyze_time.get_cost` 抛出、被 `main` 捕获后 `show_error` 写入）。
补充：`_signal_start()` 若发现未处于 `停止中`，会先写 `运行中` 并清空 B3；否则直接 `set_paused()`。

---

## 2. `GameRatioConfig` / `ImageProcessingConfig` 常量确切数值

**`MuMuEmulatorConfig`**（打包版反解，数值全部落到整数，无串扰）✅

| 常量 | 打包版反解值 | 换算 |
|---|---|---|
| `DEFAULT_COORDINATES` | 6553700 | `0x00640064` = (100, 100) |
| `WINDOW_NAME` | **`'MuMu模拟器12'`** ✅ | 与既有记录一致，**不是** `MuMu`（字符串表里那个 `MuMu` 只是 `MuMuPlayer` 的前缀片段的误读） |
| `SUB_WINDOW_NAME` | `'MuMuPlayer'` ✅ | 子窗口按**标题**取 |
| `WM_XBUTTONDOWN` / `WM_XBUTTONUP` | 523 / 524 | `0x020B` / `0x020C` |
| `XBUTTON1` / `XBUTTON2` | 65536 / 131072 | `0x00010000` / `0x00020000` |

**`GameRatioConfig`** ✅（打包版反解出的元组与公开源码逐项一致；个别二元组的**第二元**受常量表 ref/串扰影响，取值以公开源码为准）

```
COST_AREA_RATIO         = (0.906, 0.685, 1, 0.755)   ← 反解直接命中
COST_NUMBER_AREA_RATIO  = (0.33, 0, 1, 0.9)          ← 反解直接命中
OPERATOR_AREA_RATIO     = (0, 0.8, 1, 1)             ← 反解直接命中
LAST_OPER_RATIO         = (0.95, 0.9)      🟡(第二元)   RETREAT_RATIO = (0.4569, 0.3352) ← 命中
SKILL_RATIO             = (0.6412, 0.5857) ← 命中      START_BUTTON_RATIO = (0.87, 0.74) ← 命中
SPEED_BUTTON_RATIO      = (0.86, 0.07)     ← 命中      PAUSE_BUTTON_RATIO = (0.94, 0.07) 🟡(第二元)
DIRECTION_RATIO = 0.2   DEPLOY_DRAG_RATIO = 0.03   DEPLOY_DELTA_RATIO = 0.02   OPERATOR_SELECTED_RATIO = 0.9
```

**`ImageProcessingConfig`** —— 打包版**新增了 2 个公开版没有的常量**（auto_enter 亮度法用）：

| 常量 | 打包版 | 判据 |
|---|---|---|
| `WHITE_THRESHOLD` | **160** ✅ | 反解直接命中 |
| `SCREEN_STANDARD_SIZE` | **(1280, 720)** ✅ | 反解直接命中 |
| `AVATAR_STANDARD_SIZE` | **(120, 120)** ✅ | 120 命中（元组形态受串扰） |
| `AVATAR_CROP_SIZE` | **(60, 60)** ✅ | 60 命中（同上） |
| `OCR_CONFIDENCE_THRESHOLD` | **60** ✅ | 公开源码 + 反解 |
| `TEMPLATE_MATCH_THRESHOLD` | **0.8** ✅ | 公开源码；反解在 pyc 中定位到该 double（offset 650，`67 9a 99…e9 3f`） |
| **`DARK_THRESHOLD`** | **30** 🟡 | 该 class body 常量表尾部仅余两个整数 `30, 67`，按源码顺序对应 |
| **`BRIGHT_THRESHOLD`** | **67** 🟡 | 同上；**顺序有串扰风险**，建议实机打日志确认 |

**其它类的常量**（打包版反解，公开版无差异）✅
`ViewCalculationConfig`: `FROM_RATIO=0.5625`(9/16)、`TO_RATIO=0.75`、`NEAR=0.3`、`FAR=1000`；
`GameTimeConfig.TICK_MAX_DEFAULT=30`；
`PerformActionConfig`: `BULLET_THRESHOLD=15`、`FRAME_THRESHOLD=2`、`FRAME_WAITTIME=0.1`、**`MINIMUM_WAITTIME=0.03`**（公开版 0.02 ⇒ 打包版改过 🟡，且 xlsm 的 N9=0.02 会在启动时覆盖它）、`GENERAL_WAITTIME=0.3`。

> 附带修正（对 `64b` §5.2 / §5.5）：`get_tick` 的真身是
> `white_ratio = np.mean(cost_bar_area == 255)`，`return round(white_ratio * (GameTime.TICK_MAX - 1))`
> —— 打包版该函数的 `co_names` 含 `mean`、`co_consts` 含常量 `1`，且实机"封顶满格时相位=29"正合 `TICK_MAX-1`；
> 阈值化不在 `get_tick` 内，而在 `get_game_time()` 的 `cv2.threshold(..., WHITE_THRESHOLD, 255, THRESH_BINARY)`。
> 另：资源目录是 `resource/map/`、`resource/avatar/`（单数），模块是 `src/cache.py`（非 `cacher.py`）；`_update_time_counter` **没有** `lru_cache`。

---

## 3. `ACTION_COLUMN_NAME_MAPPING` 完整内容 ✅（源码逐字）

```python
ACTION_COLUMN_NAME_MAPPING = {
    '费用': 'cost',
    '帧数': 'tick',
    '操作': 'action_type',
    '干员': 'oper',
    '坐标': 'pos',
    '朝向': 'direction',
    '简称': 'alias',
}
```
方向 = **表头中文 → `Action` 字段名**。反查（字段 → 表头）：`cost→费用`、`tick→帧数`、`action_type→操作`、`oper→干员`、`pos→坐标`、`direction→朝向`、`alias→简称`。
（打包版该 dict 之外还多一项 **`绝对时间 → time`**：运行日志实证 `Action(cost=20, tick=0, time=20, action_type=DEPLOY, oper='蕾缪安', pos='G9', direction=DOWN, …)`；`time` 的 docstring = "absolute time since game start (how many times the cost bar has been fully filled)"。）

**不在该 dict 里的三列**（单独用 `locate_column` 定位，只写不参与 Action）：`当前执行`→`cur_exec`（A 列）、`运行结果`→`result`（K 列）、`设置`→`settings`（M 列，值在 N 列）。

**设置区行标签**（`data_loc`，用 `locate_row(settings_col, 标签)` 定位、值取 `settings_col+1`）：
`关卡代号 / 关卡全名 / 每费帧数 / 等待时间1 / 等待时间2 / 等待时间3 / 阈值-子弹时间 / 阈值-逐帧定位`，
打包版**另有 `初始时间`**（`.tmp\str_src_excel.txt` 中 `…map_name max_tick initial_time wait_time1…`；样本 `M6='初始时间' N6=空`，其 dataValidation 提示原文"运行前费用条曾满过多少次 默认为0"）。
样本实测：`M2 关卡代号=N2 H12-4`、`M4 每费帧数=N4 30`、`M5 脚本路径=N5 D:\__soft\ak\prts+\prts+.exe`、`M8 高级设置`、`M9..M13` 同源码顺序。

---

## 4. `convert_pos` 的行列换算方向 ✅（公式 + docstring + **实运行日志**三重吻合）

```python
def convert_position(action, height, width):
    """For example, under height 7, width 11: D2 -> (1, 3), C5 -> (4, 4), F7 -> (6, 1)"""
    action.tile_pos = (int(action.pos[1:]) - 1, height - 1 - (ord(action.pos[0]) - ord('A')))
```

**逐例验算（height=7, width=11）**：
`D2` → `(2-1, 7-1-3) = (1, 3)` ✅；`C5` → `(5-1, 7-1-2) = (4, 4)` ✅；`F7` → `(7-1, 7-1-5) = (6, 1)` ✅ —— **与 docstring 三例全部一致**。

**结论**：
- ✅ **返回 `(列, 行)`**，**列号 0 基、自左向右**（`int(pos[1:]) - 1`，列 0 = 数字 1）；
- ✅ **行号 0 基、自下向上翻转**（`height-1-(ord(字母)-ord('A'))`，`'A'` = `height-1` = **地图最下一行**）；
- ✅ 与 `calc_view` 的 `out[i][j]`/`map_point y=(height-1)/2 - i` 及 `main.py` 的 `view_data_*[tile_pos[1]][tile_pos[0]]`（`[行][列]`）自洽；
- ⚠️ `if __name__` 里那三行**注释是旧的/错的**（写着 `D2 -> (5,3)`、`C5 -> (2,4)`、`F7 -> (0,5)`，即把行列反了过来）——**以 docstring/公式为准**。
- ✅ **实运行日志实证**：`.tmp\prts_side_231813.log`（H12-4，地图 9×13）中
  `Action(… pos='G9' …)` → `INFO - Memorized 蕾缪安 location at (8, 2)`
  ⇒ `'G9'` = `(9-1, 9-1-(6)) = (8, 2)`，与公式逐位吻合（`G`-`A`=6，height=9）。

---

## 5. 本轮顺带确证的两点（供 `64b` 收尾）

1. ✅ **不存在其它启动参数**：exe 内入口脚本常量串仅含
   `--xlsm / The path to the Excel file. / --debug / store_true / Run in debug mode. / --autoenter / Run in auto enter mode.`
   ⇒ 无 `--speed`、`--threshold` 等；一切时序参数只能经 xlsm 设置区注入（`main.py` 里 `GameTime.set_tick_max(N4)`、`actionconfig.MINIMUM_WAITTIME/FRAME_WAITTIME/GENERAL_WAITTIME/BULLET_THRESHOLD/FRAME_THRESHOLD` 就地覆盖）。
2. 🟡→✅ **封顶卡死链条**（与 `64b` §6.1 一致，此处只补一条新证据）：
   打包版 `_update_time_counter(current_tick)` 的 docstring 原文 *"If the current tick is less than the last tick, it means the cost bar has been filled once."*（`co_names=['_last_tick','_time_counter']`，常量 1）
   ⇒ 封顶后费用条静止（本工作区实机记录：费用 20 / 相位 29 / 填充 180px 恒定）⇒ tick 不回绕 ⇒ `_time_counter` 停增 ⇒ `while get_game_time() < target_time` 永不退出。
   本机真实日志中该次运行**未走到封顶段**（在第 3 行 `locate_avatar` 处因头像匹配 0.670 < 0.8 报错终止），因此"封顶卡死"的实机现场仍需另取一次带 `--debug` 的运行日志。
