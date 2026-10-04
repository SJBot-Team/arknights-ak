# 64b · prts+ 轴表与控制面（参考表）
> 主题：**04E 实机 / 打图操作**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）
> 层级：**T2（数据/流程整理类（未含强代码证据））**　建立日期：**—（待补）**　任务：—　｜　**头部为 2026-09-30 自动回填**，推断项已标注

> 子文件，配套 `64_MAA与prts+_GUI操作方案.md`。
> **来源与判据**：`D:\__soft\ak\prts+` 是 **PyInstaller onedir** 打包。
> 本文件内容为**从该二进制内提取的源码字符串/常量 + 解压 xlsm 原文**所得，
> 因此多为 ✅（等价于"已读源码"）；个别取值需要反汇编确认的标 🟡。
> 另参既有剖析：`53_PRTS+部署实现_源码剖析.md`（来自开源仓库）。

---

## 一、命令行参数（`main.py` 的 `argparse`）✅

二进制中提取到的 `add_argument` 原文：

| 参数 | 类型 | 帮助文本（原文） | 说明 |
|---|---|---|---|
| `--xlsm` | `type=<路径>` | `The path to the Excel file.` | **轴表 xlsm 路径**；本机实测**必须纯 ASCII** |
| `--debug` | `store_true` | `Run in debug mode.` | 日志级别 `logging.DEBUG`（默认 `WARNING`） |
| `--autoenter` | `store_true` | `Run in auto enter mode.` | 局外自动进关 |

程序名/描述：`PRTS+`。**只有这三个参数**（无 `--speed` / `--threshold` 等；
阈值与等待时间全部走 xlsm 的「设置」区，见 §三）。

---

## 二、xlsm 轴表结构 ✅（解压 `H12-4` 轴表实物）

### 2.1 工作簿
| Sheet | 内部文件 | 状态 | 作用 |
|---|---|---|---|
| **作战记录** | `sheet1.xml` | 可见 | **轴表主体**（A1:N52） |
| `Sheet1` | `sheet2.xml` | 可见 | 作者的**换算辅助表**（含 `MOD(E,1)*30+1` 等公式，用于推 帧数/绝对时间） |
| `使用须知` | `sheet3.xml` | 可见 | 使用说明 |
| **中转站** | `sheet4.xml` | **hidden** | 隐藏的中转/控制页（对应源码 `Settings` 里的"中转站"列名） |

另有 `xl/vbaProject.bin`（79KB 宏）、`drawing1/2.xml` + `vmlDrawing1.vml` + `ctrlProp1.xml`
⇒ 表内有**表单按钮**。

### 2.1-bis、xlsm 的宏与「控制台」✅（机制确认，格址未定）

从 `vbaProject.bin` 解出的模块名（✅ OLE 流清单）：
```
ThisWorkbook, Sheet1, Sheet2, Sheet3, ControlPanel,
启动控制面板按钮, _VBA_PROJECT, dir, PROJECT, PROJECTwm, CompObj, VBFrame, f, o, __SRP_*
```
- **`ControlPanel`** —— 一个 **VB UserForm**（`Public IgnoreStartCk As Boolean`、`Sub Show()`、
  `vbModeless`「确保只有一个控制台窗口」、`_Initialize`）⇒ xlsm 带一个**控制台面板窗口**。
- **`启动控制面板按钮`** —— 按钮回调 `Sub OpenControlPanel()`。
- VBA 里可读出的**关键片段**（解压后部分残缺，但语义明确）：
  ```
  ' python script 启动参数        WScript.Shell
     --debug'    --autoenter'     " --xlsm "  ...
  ' 1 - 显示窗口; False - 异步执行    ' 0 - 返回错误; False - 异步执行
     Success / 错误，无法运行脚本。
  ' 1. 点击开始按钮后，本工作簿将无法再次点击…
  ' 2. 检查调试模式是否被勾选    ' 2. 检查自动进关是否被勾选
  ' 3. 读取脚本路径   （N5 on 「作战记录」）
  '* 提示：检测到脚本路径为空。默认脚本路径为:  <xlsm 同目录>\prts+.exe
  ' 检查脚本是否存在  ' 您指定的脚本不存在。  ' 4. 调用脚本
  ' 5. 读取运行状态，错误日志
  ' 脚本正在运行。此时无法响应。请确保excel没有单元格处于编辑状态，
    并确保已经进入关卡并暂停游戏。
  ' 1. 修改当前状态标签为「停止中」    停止中
  ```
  ⇒ **官方明确要求：点"开始"前必须已进关并暂停游戏**（与 §四 的运行前提一致）。
  ⇒ 启动命令形如：`<N5 脚本路径 或 同目录 prts+.exe> [--debug] [--autoenter] --xlsm "<本工作簿全路径>"`
  （**xlsm 把"自己"当 `--xlsm` 传进去**）。

  🔴 **控制格精确地址未拿到**：自行实现的 MS-OVBA 解压仍产出重复片段
  （`bitCount` 口径试过 per-chunk 与全局两种）。⇒ 下一步改用 `decompyle3`/`uncompyle6`
  反编译 **`src/excel.pyc`**——因为**控制逻辑在 Python 侧**（见 §2.1-ter），VBA 只是启动器 UI。

### 2.1-ter、★★ xlsm 是**双向**的：prts+ 天生有"外部可干预"的面 ✅

**关键源码**（`src/excel.py`，公开 `main` 分支）：
```python
from win32com import client
class Excel(metaclass=Singleton):
    def _connect(self):
        try:    self.excel = client.GetActiveObject('Excel.Application')  # ★ 优先复用已开的 Excel
        except com_error: self.excel = client.Dispatch('Excel.Application')
        for wb in self.excel.Workbooks:                                   # ★ 按路径找已打开的工作簿
            if os.path.normpath(os.path.abspath(wb.FullName)) == self.file_path:
                self.workbook = wb; break
        if self.workbook is None:
            self.workbook = self.excel.Workbooks.Open(self.file_path)     # 没找到就自己开一份
        self.record_sheet  = self.workbook.Sheets("作战记录")              # ★ 动作表
        self.control_sheet = self.workbook.Sheets("中转站")                # ★ 控制/状态面板
```
⇒ **必须本机装有 Excel**（COM 自动化，工作簿是"活"对象）；**只支持 xlsm**，不支持 json/csv
（`main.py` 只有 `--xlsm`，全仓库无其它读取代码）✅。
这也解释了《使用须知》里"运行期间请勿编辑作战记录，会导致脚本与 Excel 断连"。

**★ 可读可写的格（已查明）** ✅：

| 格 | 含义 | 读写方向 |
|---|---|---|
| **`中转站!B1`** | **状态**：`运行中` / `停止中` / `已停止` | 双向 —— `is_paused()` 的实现就是 **`B1 == '停止中'`**；宏的"停止"按钮就是写这一格 ⇒ **外部写这一格即可暂停 prts+** |
| **`中转站!B2`** | **当前操作行号** | prts+ 写；外部可改（= 官方"使用技巧 6：手动改起始行"） |
| **`中转站!B3`** | **错误日志**（如 `错误：无法识别当前费用。`） | prts+ 写，外部读 |
| `作战记录!K<行>` | 运行结果**单元格底色**（绿=成功 / 黄=延迟 / 红=失败） | prts+ 写，外部读 ⇒ **逐行成败读回** |
| `作战记录!A<行>` | `→` 当前执行指针 | prts+ 写，外部读 |

```python
ACTION_COLUMN_NAME_MAPPING = {          # ★ 字段名即 Excel 表头文字
    '费用': 'cost', '帧数': 'tick', '操作': 'action_type',
    '干员': 'oper', '坐标': 'pos', '朝向': 'direction', '简称': 'alias',
}
# 另有只写不读的：'当前执行'→cur_exec、'运行结果'→result、'设置'→settings
# 设置区按"名字找行、值在右侧一列"定位：data_loc['max_tick'] = (locate_row(settings_col,'每费帧数'), settings_col+1)
```

**★ 一句实跑残留的现场证据**（样本 `prts_plan_h124.xlsm` 的 `中转站`）✅：
`B1=停止中`、`B2=2`、`B3=错误：无法识别当前费用。`、`A2='→'`
⇒ 该次运行**在第 2 行（第一条操作）就因"费用 OCR 失败"停了**，而不是走到封顶段。

**★ `--xlsm` 必须传"规范化后的绝对路径"** 🟡（源码级）：
`_connect()` 用 `normpath(abspath(wb.FullName)) == self.file_path` 做等值比较，而 `main.py`
把命令行参数**原样**传入 ⇒ 传相对路径 / 大小写或斜杠不一致时匹配失败 ⇒ **会再打开一份副本**，
"宏的控制台（中转站页）"与"脚本操作的工作簿"不是同一个 ⇒ **"停止"按钮失效**。
⇒ 原型 `prts_backend.to_ascii_path()` 已一律 `normpath(abspath(...))`。

**★ 官方给的"断点"机制**（《使用须知》使用技巧 5，原文）✅：
> "PRTS+ 将运行到第一个非法后操作停止，因此可以**通过插入空行达到打断点的效果**"

⇒ 想在中途接管，**在轴表插一个空行**即可让它停在那一行；配合改 `中转站!B2`（起始行）就能续跑。

### 2.2 「作战记录」列定义 ✅（来自 `xl/worksheets/sheet1.xml` 的 `dataValidation` 全文）

| 列 | 表头 | 约束 | 官方 prompt（原文） |
|---|---|---|---|
| A | 当前执行 | — | （脚本写入 `→` 标记当前行） |
| B | 费用 | 整数 0–999 | `0-999之间的整数` |
| C | 帧数 | 整数 0–120 | `0至(每费帧数-1)之间的整数` |
| D | 绝对时间 | 整数 0–10000 | `表示费用条一共满过几次的非负整数` |
| E | 操作 | 列表 `部署, 技能, 撤退` | — |
| F | 干员 | 列表 `=F$2:F2` | `干员全名或简称` |
| G | 坐标 | — | `map上的坐标 例如B3` |
| H | 朝向 | 列表 `上, 下, 左, 右, 无` | — |
| I | 简称 | — | `命名当前单位 方便未来引用` |
| J | 备注 | — | `本条操作的备注 不影响操作执行` |
| **K** | **运行结果** | — | `绿色：操作成功_x000a_黄色：操作延迟_x000a_红色：操作失败` |
| L | （题外） | — | `**使用前请务必查看使用须知**` 等作者留言 |
| M | 设置（名） | — | 见 §三 |
| N | 设置（值） | — | 见 §三 |

### 2.3 真实行样本（H12-4，R1 表头 + R2~R40）
```
r2:  A2='→' B2='11' C2='15' D2='1'  E2='部署' F2='令'        G2='C12' H2='上'
r3:           B3='20' C3='0'  D3='20' E3='部署' F3='蕾缪安'   G3='G9'  H3='下'
r4:                   C4='4'  D4='25' E4='技能' F4='蕾缪安'
r7:                   C7='0'  D7='29' E7='部署' F7='弦惊'     G7='D11' H7='左'
r14:                  C14='8' D14='99' E14='撤退' F14='蕾缪安'
r35:                  C35='0' D35='245' E35='部署' F35='雷鸣地雷' G35='F10' H35='无'
```
**语义**：`D`（绝对时间 = 费用条满过几次）× **每费帧数(30)** + `C`（帧数）= 目标帧。
`B`（费用）只在部分行填写，用于脚本的"费用校验"（
源码日志 `Cost mismatch: expected {}, got {} (time matches: {} == {})`）。

### 2.4 编码约定 ✅
- `E` ∈ {`部署`,`技能`,`撤退`} → 源码 `ActionType.DEPLOY/SKILL/RETREAT`
- `H` ∈ {`上`,`下`,`左`,`右`,`无`} → `DirectionType`（`无` = NONE）
- `G` = 棋盘坐标，如 `C12`、`G9`；源码 `convert_pos.py` 原文注释：
  > `Convert chess board representation to numerical representation`
  > `For example, under height 7, width 11: D2 -> (1, 3), C5 -> (4, 4), F7 -> (6, 1)`
  ⇒ 列字母 → 列号（A=0?），行号 → 行号，**且做了行翻转**（`D2 -> (1,3)`：D=3→col 3？(1,3) 是 (row=1, col=3)，
  行 2 → row 1 ⇒ **行号 − 1**，列 D → col 3 ⇒ **列号从 0 起**）。🟡 具体方向需按地图尺寸验证。

---

## 三、xlsm「设置」区（M/N 列）✅ —— ★ 全部阈值都从这里进

| 格子 | 名称 | H12-4 值 | prompt（原文） | 映射到源码常量 |
|---|---|---|---|---|
| N2 | 关卡代号 | `H12-4` | `如果关卡有代号 输入代号即可…例如1-7, H8-4, SN-EX-8` | `Settings.map_code` |
| N3 | 关卡全名 | （空） | `如果没有代号 也可以输入全名 例如：淤浊沼泽` | `Settings.map_name` |
| N4 | **每费帧数** | `30` | `默认为30 可根据减回费修改`（列表 30/40/60/120） | `GameTime.TICK_MAX` |
| N5 | 脚本路径 | `D:\__soft\ak\prts+\prts+.exe` | `务必输入完整路径…若为空 则默认脚本与该文件位于同一文件夹下` | （启动按钮用） |
| N6 | 初始时间 | （空） | `运行前费用条曾满过多少次 默认为0` | `reset_time_counter` 的 `initial_time` |
| N8 | （分区标题） | `高级设置` | | |
| N9 | 等待时间1 | `0.02` | `部署时两次暂停之间的间隔时间 单位：秒 默认：0.02` | `MINIMUM_WAITTIME` |
| N10 | 等待时间2 | `0.1` | `子弹时间下逐帧前进的两次暂停间隔 单位：秒 默认：0.1` | `FRAME_WAITTIME` |
| N11 | 等待时间3 | `0.3` | `等待模拟器反应操作的时间 单位：秒 默认：0.3` | `GENERAL_WAITTIME` |
| N12 | 阈值-子弹时间 | `15` | `尝试进入子弹时间时，距离目标帧的帧数 单位：帧 默认：15` | `BULLET_THRESHOLD` |
| N13 | 阈值-逐帧定位 | `2` | `尝试进入逐帧定位时，距离目标帧的帧数 单位：帧 默认：2` | `FRAME_THRESHOLD` |

源码对应日志（`main.py` 原文）：
```
Set minimum wait time to / Set frame wait time to / Set general wait time to
Set bullet threshold to  / Set frame threshold to
```
⇒ **这 5 个参数可在 xlsm 里热改**，不必改代码。`每费帧数` 支持 `40/60/120`
⇒ **"减回费"（cost regen 被降低）的关卡也能对轴**——这是官方给的第一个"绕法"入口。

---

## 四、完整执行流程 ✅（`main.py` 反推出）

```
1. argparse: --xlsm / --debug / --autoenter
2. Excel(file_path)                      # win32com 打开工作簿（COM 挂到已开的 Excel 实例）
   ├── _connect()  → GetActiveObject / Dispatch('Excel.Application')
   ├── locate_row()/locate_column() → 找「作战记录」表与各列
   └── get_setting()  → map_code, map_name, max_tick, initial_time,
                        wait_time1/2/3, bullet_threshold, frame_threshold
3. set_tick_max(max_tick); 用设置覆盖 MINIMUM_WAITTIME / FRAME_WAITTIME /
   GENERAL_WAITTIME / BULLET_THRESHOLD / FRAME_THRESHOLD
4. 关卡数据
   ├── get_map_by_code(map_code) 或 get_map_by_name(map_name)   # src/cacher.py，读 resource/maps
   ├── transform_map_to_view(map, side=False) → view_data_front
   └── transform_map_to_view(map, side=True ) → view_data_side  # 3D 投影，见 53 §六
5. 若 --autoenter: auto_enter()
   ├── wait_for_game_start()   # 监视费用区右下角像素亮度：先变暗(加载)→再变亮(开战)
   │     用 ImageProcessingConfig.DARK_THRESHOLD / BRIGHT_THRESHOLD
   │     日志: "Initial pixel brightness: → Brightness changed: a -> b →
   │            Screen darkened, brightness: → Game started, brightness:"
   ├── mouseclick(START_BUTTON_RATIO)              # 点「开始行动」
   ├── "Auto enter started" → "Sent pause signal"  # 发暂停（鼠标侧键/PAUSE_BUTTON_RATIO）
   ├── "Successfully paused at time {}"
   └── mouseclick(SPEED_BUTTON_RATIO) → "Switched game speed to 2x"   # 切 2 倍速
6. reset_time_counter(initial_time)  → "Setting initial time counter to {}"
7. 主循环（逐行）:
   a. action = excel.get_current_action()   # 读 A..K 的当前行 → "Get action: Action(...)"
   b. 校验 action.is_valid()；无效 → set_result(FAILURE) + set_error("Invalid action: ...")
   c. 若是 DEPLOY：
        - 解析 alias（"Memorized {} location at {}" / "Auto set {} location to {} as an alias of {}"
                  / "Detected alias, replace {} with {}"）
        - 取 view_data_front / view_data_side 的对应格坐标
   d. perform_action(action)   # ← 见 §五
   e. excel.set_result(SUCCESS|WARNING|FAILURE, actual_time, scheduled_time)
        → 写 K 列颜色：绿=成功 / 黄=延迟 / 红=失败
   f. excel.next_action()      # 移到下一行（并把 → 标记移过去）
8. 异常收尾（中文文案即"失败分类"）:
     PerformLateError   → "当前操作晚了超过一费"
     UserPausedError    → "用户停止"
     其它               → "疑似发生错误" / "请求人工接管" / "未定义错误"
9. cleanup_vision() / Excel.__exit__（保存并关闭）
```

**★★ 关键推论（对 agent 闭环）**：
`excel.set_result()` / `excel.next_action()` / `excel.get_current_action()` /
`excel.is_paused()` / `excel.set_paused()` / `get_control_value()` / `set_control_value()`
⇒ **xlsm 既是输入也是状态输出，而且存在可读写的中转站/控制格**。
即 **prts+ 天生就有"外部可干预"的面**：agent 可以
①读 K 列知道每步成功/延迟/失败；②通过控制格暂停/恢复；
③改后续行的 C/D（帧/绝对时间）或插删行来**修改操作清单**。
⚠️ 控制格的具体地址未查明（🔴）——下一步读隐藏 `中转站` 页与 `vbaProject.bin`。

---

## 五、局内识别与执行 ✅（源码字符串）

### 5.1 截图（`mumu/mumu_vision.py`）
**Windows GDI `BitBlt` 抓游戏窗口**（不是 ADB、不是 WGC）：
```
GetWindowDC(HANDLE) → win32ui.CreateDCFromHandle → CreateCompatibleDC
→ CreateCompatibleBitmap(w,h) → SelectObject → BitBlt(SRCCOPY)
→ GetBitmapBits → np.frombuffer → cv2.cvtColor(COLOR_BGRA2GRAY)
→ ★ cv2.resize(..., ImageProcessingConfig.SCREEN_STANDARD_SIZE)   # = (1280, 720)
```
有 `_dc_cache` / `_bitmap_cache` 复用（`CreateBitmap` 只建一次）+ `cleanup_vision()`。
**⇒ prts+ 与 MAA 一样，把画面归一化到 1280×720 再用比例坐标**
（这也解释了它全部坐标常量都是 `0~1` 的比例）。

### 5.2 计时（`logic/analyze_time.py`）★ 封顶卡死的根因所在
```python
def get_tick(cost_bar_area_bytes) -> int:
    """按费用条中**白色像素占比**算 tick，缩放到 0 ~ GameTime.TICK_MAX-1"""
    white_ratio = (np.frombuffer(cost_bar_area_bytes, np.uint8) > WHITE_THRESHOLD).mean()
    return round(white_ratio * GameTime.TICK_MAX)

@lru_cache
def _update_time_counter(current_tick: int):
    """★ 原文 docstring:
       Update the global time counter based on the current tick.
       If the current tick is less than the last tick,
       it means the cost bar has been filled once."""
    if current_tick < _last_tick:      # 检测"回绕" ⇒ 说明满过一次
        _time_counter += 1
```
```python
def get_game_time(need_cost: bool) -> GameTime:
    # tick = get_tick(费用条区域)              # COST_AREA_RATIO = (0.906, 0.685, 1, 0.755)
    # _update_time_counter(tick)               # 只在 tick 回绕时 time+1
    # cost = OCR(费用数字区)  # COST_NUMBER_AREA_RATIO = (0.33, 0, 1, 0.9)
    #                         # tesserocr + lang='arknights_digit' + PSM.SINGLE_WORD
    #                         # 失败返回 -1；置信度 < OCR_CONFIDENCE_THRESHOLD 判失败
```
`GameTime`（`logic/game_time.py`）dataclass：`cost: Optional[int]`、`time: Optional[int]`
（原文注释：**"the absolute time since game start (how many times the cost bar has been fully filled)"**）、
`tick: int`；`TICK_MAX` 是 **class attribute**（可 `set_tick_max` 全局改）；
`__add__`/`__sub__` 带 carry/borrow；跨类型比较抛 **"Cannot compare time with cost"**。

### 5.3 干员定位（`logic/locate_avatar.py`）
在 `OPERATOR_AREA_RATIO = (0, 0.8, 1, 1)`（底部待部署区）里
对**每个候选干员头像模板**做 `cv2.matchTemplate(TM_CCOEFF_NORMED)`，取 `minMaxLoc` 最大值，
与 `TEMPLATE_MATCH_THRESHOLD` 比较；命中则把比例坐标写回 `action.avatar_pos`。
模板来自 `resource/avatars/`（`AVATAR_STANDARD_SIZE=(120,120)`，`AVATAR_CROP_SIZE=(60,60)`，先 `resize` 再 `crop`）。
失败文案：`Could not find a good matching avatar for {}` / `未在待部署区找到干员`。

### 5.4 动作执行（`logic/perform_action.py`）
沿用 `53` 已剖析的三段式逼近 + 逐帧推进；本机二进制补充确认了**全部日志/异常文案**：
```
"Within frame threshold, entering bullet time"
"Within bullet threshold, entering bullet time"
"Too much time, resuming and entering bullet time"
"Within frame threshold, entering side view"
"Operator {} is already selected"
"Performed action: {} (not on time)" / "(unexpected time)"
"Game time mismatch, performed action at {} instead of {}"
"Cost mismatch: expected {}, got {} (time matches: {} == {})"
"Performing action: {}"
异常类：PerformLateError(actual_time, scheduled_time) / PerformActionError / UserPausedError
函数：wait_until_threshold(target_time, threshold, need_cost, user_paused)
```
部署序列：选中（`OPERATOR_SELECTED_RATIO` 判是否已选中）→ `DEPLOY_DRAG_RATIO` 上拖一次
→ `esc`(暂停) → 移到 `view_pos_side + DEPLOY_DELTA_RATIO` → `mouseup` → 用 `DIRECTION_RATIO` 定朝向。
技能/撤退用 `view_pos_front` + `SKILL_RATIO` / `RETREAT_RATIO`。

### 5.5 关卡数据（`src/cacher.py`）
`resource/` 下三张映射表：`operator_mapping.json`（`OPERATOR_MAPPING`）、
`level_code_mapping.json`（`LEVEL_CODE_MAPPING`）、`level_name_mapping.json`（`LEVEL_NAME_MAPPING`）；
`resource/maps/` 放关卡数据；`resource/avatars/` 放头像模板。全部 `lru_cache` 懒加载，
日志 `Loaded avatars for {}` / `Loaded map data for {}`。
日志格式：`%(asctime)s - %(levelname)-7s - %(message)s`（带 ANSI 颜色的 `ColoredFormatter`）。

---

## 六、★ 费用封顶卡死的根因与绕法

### 6.1 根因（✅ 源码 docstring 级证据）
链条：
1. `tick = round(费用条白色像素占比 × TICK_MAX)` —— **tick 的唯一来源是费用条的填充长度**；
2. `_update_time_counter` **只在 `current_tick < last_tick`（回绕）时**才 `time_counter += 1`；
3. **费用封顶（H12-4 上限 20）后费用条不再填充** ⇒ tick 冻结在定值 ⇒
   `current_tick < last_tick` **永远为假** ⇒ `_time_counter` **停止递增**；
4. `game_time = GameTime(time=_time_counter, tick=冻结值)` ⇒ **完全静止**；
5. 而"该做下一步了"的判定是 `while get_game_time() < target_time: 恢复 → sleep(FRAME_WAITTIME) → 暂停`
   ⇒ **退出条件永不满足 ⇒ 卡死**（既不推进也不报错，表现为"停在那里"）。
6. 附带损伤：封顶持续 N 秒，`_time_counter` 就**少计 N** ⇒ 即使后来离开封顶，
   **绝对时间轴整体偏移 N 秒**（这就是"计时停住"而不是"只是慢一点"）。

**触发条件**：费用达到上限**且仍有后续操作等待**。H12-4 上限 20、轴表操作密集 ⇒ 必然发生。

### 6.1-bis、★★ 作者自己在《使用须知》里承认了这个限制 ✅

> 原文（`使用须知` 工作表，第三条 1）：**"无法在费用抵达上限……情况下使用"**

⇒ 这不是我们的推测，而是**官方自认的已知限制**。同时官方给了**推荐绕法**（见 §6.2 A）。
**卡死时的判别**：它仍在 `while` 里循环（不是崩溃），所以 `中转站!B1` 仍可被写入 `停止中`
让 `while` 内的 `user_paused()` 命中而退出 ⇒ 可据此区分"死循环"与"进程已崩"。🟡

### 6.2 绕法（按推荐度）

| # | 绕法 | 做法 | 判据/风险 |
|---|---|---|---|
| **A₀** | ★**官方推荐：让费用永不到顶** | 额外带一个高费干员，**在封顶前部署再撤退**故意消耗费用，维持费用条继续填充（=《使用须知》1.1 原文） | ✅ 官方文档；零改码、最稳；缺点是占部署位，且**轴里要预留这次"泄费"操作** |
| **A** | **外部计时，不用 prts+ 的 tick** | 用本工作区 `plugins/clock/frame_clock.py`（官方 `pixel_map` 查表算相位）+ `cost_timeline.py`（**上限锚点，已实现"跨越封顶"**）在**外部**算帧；部署/技能用 `plugins/action/deploy.py` 驱动 | ✅ 既有实现正是为此；视频基准已验证（99.6% ≤2 帧、无漂移） |
| **B** | **封顶处切段 + 官方断点** | 轴表在首个封顶点**插一个空行**（官方"使用技巧 5"：运行到第一个非法处即停）⇒ prts+ 自然停下；封顶段改用 `paused_protocol`（暂停+过帧）由 agent 驱动；之后再改 `中转站!B2`（起始行）续跑 | ✅ 断点机制是官方功能；🟡 切点对齐待实机 |
| **B₂** | **改用绝对时间轴 + `初始时间(N6)`** | 轴写成 `绝对时间`(D) + `帧数`(C)；中途开始就在 `N6` 填"运行前已回满次数" | ✅ 能解决**"部署扣费破坏时间轴"**（H12-4 这种频繁部署撤退的轴必备）；❌ **但不能解决封顶**（`_time_counter` 同样冻结） |
| **C** | **监控→杀→改表续跑** | 外围检测"进程活着但 `Performing action` 停了 > N 秒且费用已达轴表上限" ⇒ 杀进程，按进度改表续跑 | ✅ 已实现（`gui_ops/prts_backend.py::watch()`） |
| **D** | **改 `每费帧数(N4)`** | 该设置本就是给"减回费"关用的；若某关是回费变慢而非封顶，改 40/60/120 即可 | ✅ 设置项存在；对**真封顶无效** |
| **E** | **打补丁改计时** | 改 `analyze_time.get_game_time()`：连续 N 次读到完全相同的 `(tick,cost)` 且 `white_ratio≈1.0`（满格）时，切换为本地自增计数/封顶锚点外推；退出条件由"读数 < 目标"改成"步进 K 次" | 🟡 唯一能"真正自动跑通封顶段"的改法（用户已授权可改 prts+）；改动集中在 `analyze_time` + `perform_action` 两处 `while` |

> **不建议**：只改 `初始时间(N6)`。封顶期间 tick 是**冻结**而非**变慢**，单改原点无法让 `while` 退出。

**给 H12-4 的组合建议**：先按 **B₂** 重写轴（消除部署扣费破坏）；封顶段用 **B**（插空行断点）或 **A**（外部计时接管）；
若要全自动，实施 **E**。

### 6.3 对我们方案的直接影响 ✅
⇒ **agent 闭环里"局内"这一步不能盲目把控制权整段交给 prts+**。
正确分工：
- **无费用封顶的关卡**：`prts` 后端直接跑轴表（我们只做监督，读它写回的 K 列与 `中转站!B1/B2/B3`）。
- **有封顶的关卡（如 H12-4）**：改用工作区自己的 `axis_runner` + `frame_clock`（绕法 A/B），
  prts+ 只作为**参照实现**与"封顶前段"的执行器。

---

## 六-bis、★ 版本差异：**本机 exe 比公开仓库新**（对既有知识库的修正）

> ⚠️ 既有 `53_PRTS+部署实现_源码剖析.md` 是**基于公开仓库 `main`** 写的，
> 而用户手上的 `prts+.exe` **更新** ⇒ `53` 对"输入格式 / 时间语义"的描述是**旧版口径，只对了一半**。
> 下面每项都经 exe 内 PYZ 反解与三份公开分支逐字对比 ✅。

| 项 | 公开 `main`/`develop`/`release-0.2.0` | **本机 `prts+.exe`（新）** |
|---|---|---|
| `GameTime` 字段 | `cost, tick` | **`cost, tick, time`**（+ 报错串 `Cannot compare time with cost`） |
| 绝对时间计数器 | 无 | **`_time_counter` / `_last_tick` / `_update_time_counter()` / `reset_time_counter()`** |
| `get_game_time` | 无参 | **`get_game_time(need_cost=True)`**（可跳过费用 OCR） |
| 设置项 | 无 `初始时间` | **`initial_time`**（xlsm `N6 初始时间`）+ 轴表新增 **`绝对时间`** 列 |
| auto_enter | 点开始 → 等 `tick>0` → 暂停 → 倍速 | 增加 **`wait_for_game_start()`（亮度法）** + `DARK_THRESHOLD=30` / `BRIGHT_THRESHOLD=67`（🟡 顺序存疑） |
| 费用校验 | 无 | 日志 **`Cost mismatch: expected …, got … (time matches: … == …)`** |
| 资源清理 | 无 | `mumu_vision.cleanup` / `cleanup_vision` |
| `MINIMUM_WAITTIME` | 0.02 | **0.03**（✅ 常量反解） |
| 列映射 | 7 项 | 多 **`绝对时间`→`time`**；实跑日志实证 `Action(cost=20, tick=0, time=20, …)` |
| 时间轴口径 | 费用 + 帧数 | **绝对时间 + 帧数**（费用降级为校验） |

**其余已解出的常量**（✅ 自写 Python 3.9 marshal 读取器）：`WINDOW_NAME='MuMu模拟器12'`（**不是** `MuMu`）、
`SUB_WINDOW_NAME='MuMuPlayer'`、`DEFAULT_COORDINATES=0x00640064`、`WM_XBUTTONDOWN/UP=523/524`、
`XBUTTON1/2=0x10000/0x20000`、`WHITE_THRESHOLD=160`、`SCREEN_STANDARD_SIZE=(1280,720)`、
`AVATAR_STANDARD_SIZE=(120,120)`、`AVATAR_CROP_SIZE=(60,60)`、`OCR_CONFIDENCE_THRESHOLD=60`、
`TEMPLATE_MATCH_THRESHOLD=0.8`、视图 `FROM_RATIO=0.5625 / TO_RATIO=0.75 / NEAR=0.3 / FAR=1000`。

⇒ **用户手上的模板（带 `初始时间`、`绝对时间` 列）与本机 exe 配套；公开仓库是旧版。**
**判据优先级：本机 exe > 公开仓库。**

---

## 七、未查明项（下一步）

| # | 项 | 状态 / 卡点 | 下一步 |
|---|---|---|---|
| 1 | **控制格地址** | ✅ **已查明**：`中转站!B1=cur_status`（`停止中`=停止请求）/ `B2=cur_row`（1 基当前行号）/ `B3=err_log`；源码里是 0 基 `(0,1)/(1,1)/(2,1)`，写入时 +1。样本 `sheet4.xml` 互证（A 列标签 / B 列值，`B3` 残留 `错误：无法识别当前费用。`） | 已写入 §2.1-ter |
| 2 | **`GameRatioConfig` / `ImageProcessingConfig` 常量** | ✅ 已解出（自写 Python 3.9 marshal 读取器解 `co_consts`）：<br>`WINDOW_NAME='MuMu模拟器12'`（**不是** `MuMu`）· `DEFAULT_COORDINATES=0x00640064` · 侧键 `WM_XBUTTON*`=523/524 · `XBUTTON1/2`=0x10000/0x20000 · `WHITE_THRESHOLD=160` · `SCREEN_STANDARD_SIZE=(1280,720)` · `AVATAR_STANDARD_SIZE=(120,120)` · `AVATAR_CROP_SIZE=(60,60)` · `OCR_CONFIDENCE_THRESHOLD=60` · `TEMPLATE_MATCH_THRESHOLD=0.8` · 视图 `0.5625/0.75/0.3/1000`（FROM/TO_RATIO、NEAR、FAR）<br>**打包版新增**：`DARK_THRESHOLD=30`、`BRIGHT_THRESHOLD=67`（🟡 顺序存疑）<br>**打包版改动**：`MINIMUM_WAITTIME` 由 `0.02` → **`0.03`** | 已写入 §六-bis |
| 3 | **`ACTION_COLUMN_NAME_MAPPING`** | ✅ 已查明 7 项 + 打包版多 `绝对时间→time`；真实运行日志实证 `Action(cost=20, tick=0, time=20, …)` | 已写入 §2.1-ter |
| 4 | **`convert_pos` 换算** | ✅ **源码级 + 实运行日志双证**。`convert_position` 的通用形式用两个实测样例即可定：<br>`'C12' → (11, 6)`、`'G9' → (8, 2)`（H12-4，**9 列 × 13 行**）<br>两者同时满足 **`(行号-1, (列数-1) - (字母序))`**，即 **行号从上数（0 基）**、**列字母从右数**（`A`=最右）。<br>⚠️ 该仓库 docstring 与文件内 `if __name__` 注释互相矛盾（前者三例自洽、后者错）⇒ 以**实测样例**为准 | 实机再用 1~2 个坐标验证方向 |
| 5 | 封顶时费用条的**具体画面形态**（满格 1.0 还是停在中途） | 🔴 需实机截帧 | 实机在刚封顶时量 `COST_AREA_RATIO` 最后一行的白像素比例；若恒为 1.0 ⇒ 印证 `tick≡29` |
| 6 | 封顶绕法 A₀/A/B/E 的实机效果 | 🔴 模拟器未启动、账号未开放 | 等用户放开实机 |
| 7 | `_VBA_PROJECT`/`dir` 之外的 VBA 控制台细节 | 🟡 部分成功（模块名与命令行已拿到；MS-OVBA 自实现解压仍有重复片段） | 非必需——控制逻辑已由 Python 侧查明（§2.1-ter） |

| 3 | `GameRatioConfig` 各常量的**确切数值** | 字符串表只有 `gffffff` / `333333` 等片段，值需反汇编 | 用 `decompyle3`/`uncompyle6` 反编译 `main.pyc`（已导出到 `.tmp/main_entry.pyc`） |
| 4 | `MuMuEmulatorConfig.WINDOW_NAME` 现值 | 提取到 `MuMu` 与 `MuMuPlayer` 两个串；与既有记录 `"MuMu模拟器12"` 不一致（疑版本差异） | 反编译 `config.pyc` 确认 |
| 5 | `ACTION_COLUMN_NAME_MAPPING` 完整内容 | 只拿到名字 | 反编译 `excel.pyc` |
| 6 | `convert_pos` 的行/列方向细节 | 只有 docstring 的 3 个例子 | 用 `map_height/width` 与已知坐标反推 |
| 7 | 封顶绕法 A/B 的实机效果 | 模拟器未启动、账号未开放 | 等用户放开实机 |
