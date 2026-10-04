# -*- coding: utf-8 -*-
"""append_p1_progress.py — 记录 P1 进展：通用场景加载 + 批量探明 + 抓取第 1 章 + 随机数自检。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **P1 进展：模拟环境通用化（通用场景加载 + 批量探明 + 抓取第 1 章 + 随机数自检）2026-09-15**：'
       '①**新增 `ak_sim/scenario.py`：通用关卡场景加载**（取代专关专用的 `scenario_h124`），'
       '对应"方向性修正 1"（关卡-关联单位-关联机制**一次探明**、变动项做**外部输入**）：'
       '关卡定位**按文件存在性探测**（`1-7`⇒`obt/main/level_main_01-07`、`12-4`⇒`obt/hard/level_hard_12-04`）；'
       '`unit_config`/`enemy_tags` 作为参数注入（练度/模组/敌方 tag 不再写死）；'
       '②**摸清关卡 JSON 的真实字段结构并修正解析**（此前多处按猜测写错）：'
       '生命=`options.maxLifePoint`（非 maxLife）、地图=`mapData.map`（数字编码二维数组）、'
       '**出怪在 `waves[].fragments[].actions[]`**（非 wave.actions）、敌人引用=`enemyDbRefs[].id`、'
       '预置单位=`predefines.{characterInsts,tokenInsts,characterCards,tokenCards}`、'
       '**★关卡自带 `randomSeed`**（对应需求"随机数可控"）；'
       '③**新增 `ak_sim/stage_survey.py`：批量关卡探明台账**（对应需求"预置验证定位"），'
       '产出 `.tmp/stage_survey.json`（结构化）与 `.tmp/stage_survey.md`（可读对照表，含各关机制 blackboard 明细）；'
       '**12-4 探明结果与既有认知完全吻合**：生命 3、地图 9×13、路线 61、敌人引用 15、'
       '机制 `cbuff_max_cost(max_cost=20)`、`enemy_attribute_mul(atk/def×1.2)`、`env_system_new(sightSystem)`；'
       '④**发现本仓仅有 5 个关卡文件**（1-1、1-7、12-4 + 肉鸽/活动各 1）⇒ '
       '**用 `code/unpack/fetch_level.py` 抓取补全第 1 章 12 关全部成功**（1-1~1-12，44KB~130KB 各）；'
       '**第 1 章探明台账**：生命 5~10、地图 7×9~8×11、路线 19~41、敌人 3~8 种、出怪 16~40 条、机制 2~3 个，'
       '**各关 randomSeed 已记录**（如 1-1=978975386、1-7=1924903387、1-12=586487713）；'
       '⑤**新增 `ak_sim/run_stage.py`：通用关卡试跑入口**（空轴基线 + 事件时间线 + 随机数可控性自检）：'
       '**1-1 空轴跑通**（1890 帧=63.0s、生命 10→0、10 次漏怪：10.93/18.13/29.93/33.13/51.53/54.0/56.0/59.63/60.53/63.0s）；'
       '**1-7 空轴跑通**（1800 帧=60.0s、10 次漏怪）；'
       '**★随机数可控性自检通过**：同 seed 多次运行**结果完全一致**（1-1 跑 3 次、1-7 跑 2 次，漏怪时刻与帧数逐位相同）'
       '⇒ 满足需求 1.8"随机数可自由更改、避免凹概率"的基础；'
       '⑥**下一步（断点）**：(a) 补全**逐帧完整切片字段**（操作/血量/坐标/攻速/移速/随机判定，需求 1.6）；'
       '(b) 建**事件帧钩子**（出生/伤害/血条变化/击杀/上限突破，需求 1.5）；'
       '(c) 在**第 1 章**排一个最小轴并用事件帧检验（用户指定的练手路径）；'
       '(d) 打图侧继续找第 1 章进关入口；'
       '⑦合规：仅读取本地数据与公开数据仓库抓取；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录 P1 进展')

for rel in (r'sim\draft\ak_sim\scenario.py', r'sim\draft\ak_sim\stage_survey.py',
            r'sim\draft\ak_sim\run_stage.py'):
    d = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel), d)
shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp', 'stage_survey.md'),
             os.path.join(DST, 'knowledge', '04_数据对应与核验', '关卡探明台账.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
