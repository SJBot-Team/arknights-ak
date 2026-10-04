# -*- coding: utf-8 -*-
"""append_p0_1.py — P0 第一块：任务流水线引擎 + 遗留模块复核 + 资源定位。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
PLAN = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\46_执行计划_模拟环境与自动打图.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **P0-1 完成任务流水线引擎（2026-09-15）**：'
       '①**遗留成果复核（用户要求"注意阅读昨天总结与遗留成果"）**：'
       '`plugins/` 下 12 个关键模块**全部在位**（`clock/paused_protocol.py` 7.8KB、`cost_timeline.py` 3.5KB、'
       '`bar_sanity.py` 3.3KB、`frame_clock.py` 19.2KB、`nav/auto_enter.py` 4.5KB、'
       '`recognize/ui_state.py` 5.0KB、`maa_anchor.py` 6.5KB、`cost_number.py` 2.9KB、'
       '`capture/render_guard.py` 3.2KB、`emu_window.py` 16.2KB、`task/axis_runner.py` 24.3KB、`task/nav_flow.py` 7.3KB）'
       '＋ 9 个 app 脚本（`enter_and_pause`/`prts_side_by_side`/`scan_video_events`/`verify_phase_video`/'
       '`analyze_video`/`test_auto_enter`/`test_paused_protocol`/`test_frames_between`/`test_bar_sanity`）'
       '⇒ **昨天的成果完好、可直接复用**（我首次复核时把路径写重了导致误报"缺失"，已纠正）；'
       '②**资源定位**：**弧光 7 人轴表** 3 份（`E:\\__file\\舟数据\\关卡\\弧光\\赛博塑料弧光7.xlsm` 及 `- 酒2`、`- 酒2嵯峨`），'
       '另 discovery 出 **`E:\\QQ\\` 攻略资料区**（多份弧光7轴表、大量帧级命名录像如"艾拉29帧部署吃到劝善"）；'
       '**H12-4 双人解视频**在 `E:\\MUMU共享文件夹\\VideoRecords\\H12-4\\双\\`（4 个以"明日方舟"开头的 mp4，用户确认有参考价值）；'
       '**净罪7 轴表未找到**——目前只有 `净罪作战880.xlsx`（敌人属性表）与 `E:\\QQ\\净罪.xlsx`（**出怪时刻表**，非轴表）'
       '⇒ 待用户确认路径（不阻塞 P0）；'
       '③**P0-1 交付 `plugins/task/pipeline.py`（任务流水线引擎）**，特性对齐用户要求与 MAA/prts+：'
       '(a) **配置驱动**（JSON 描述"识别→动作→下一步"，人可读易改，注释键 `_comment` 可忽略）；'
       '(b) **识别多候选**：`state`（界面语义）/`template`（MAA 模板）/`cost`（费用数字区间）/`always`；'
       '(c) **★步进优先**：`step_pause` 为一等公民动作（= **0 帧暂停/过帧**），'
       '**操作前先暂停定位帧、给识别留缓冲**，与 prts+ 的「子弹时间」同源；'
       '(d) **MAA 的 next 语义**：`next` 为**候选列表**，选"其 recognize 命中"的那个，全不命中则兜底第一个；'
       '(e) **动作后用界面语义判生效**（绝不用像素差异）；'
       '④**离线测试 `apps/test_pipeline.py` 5/5 PASS**：A 配置驱动（JSON+注释键忽略）、B 步进优先（step_pause 正确执行）、'
       'C next 多候选（命中 squad_path 而非 viewport_path）、D 候选全不命中兜底第一个、E `until` 语义（进入 battle 即返回）；'
       '⑤**下一步（P0 剩余）**：把"启动→主界面→终端→选关→编队→选人/技能/模组→出战"写成**一份流水线配置**，'
       '替换现有 `AutoEnter` 的试错式导航，再做实机验证；'
       '⑥合规：仅图形界面级操控；未触碰游戏文件/内存；未消耗理智。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加 P0-1')

for rel, sub in ((r'code\vision\plugins\task\pipeline.py', r'code\vision\plugins\task'),
                 (r'code\vision\apps\test_pipeline.py', r'code\vision\apps'),
                 (r'knowledge\04_数据对应与核验\46_执行计划_模拟环境与自动打图.md',
                  r'knowledge\04_数据对应与核验')):
    src = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel)
    d = os.path.join(DST, sub, os.path.basename(rel))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
