# -*- coding: utf-8 -*-
"""append_t052_round60.py — 把第 60 轮的进展追加到 tasks_registry.md 的 T-052 行末尾。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 "【第60轮】★★★★**工作流第3步（视频后半部分）：图像识别建立游戏帧轴 + 发现并实现“先锋技能回费”**："
 "①**新建视觉工具链**（`ak/code/vision/apps/`）：`montage_video.py`、`montage_roi.py`、`locate_costbar_video.py`、"
 "**`video_hud_scan.py`**（逐帧扫 HUD：费用条填充px + 费用数字；字形聚类后“每簇一次”OCR，全片 40s）、"
 "**`video_axis.py`**（两条独立时钟建轴）、`frames_at_game.py`（按游戏帧反查视频帧）、`video_kill_counter.py`、`kc_glyphs.py`；"
 "②**HUD 精确坐标实测**：费用数字 x1830~1894/y753~803、费用条起点 x=1734 且**满条 180px ↔ 30 帧（6px=1帧）**、"
 "击破数「N/33」x830~906/y40~68；"
 "③**★★两条独立时钟互证**：相位累加（费用条）vs 回费计数（费用数字），整片 10579 帧差恒为 +13~15.7、**漂移仅 2.7 帧 / 350 秒** ⇒ 轴精度 ≈±3 帧；"
 "④**★★★三个硬结论**：**(a)** 干净 RUN 段的「游戏帧/视频帧 = **1.000**」（满条取 180px；取 174px 会得到 1.034 的假偏差）"
 "⇒ **1 视频帧 = 1 游戏帧、6px = 1 帧**；**(b)** 两次部署落在游戏帧 **10.0 / 411.3**，与标定表帧 10/411 **完全吻合**（费用 10→2、15→1）"
 "⇒ **“芬 = 8 费”由图像识别独立证实**（= 11 − 潜能2 − 天赋“轻量化”1）；**(c)** 费用 +1 在视频侧落在游戏帧 **29.7±0.5**，与模拟器 `f%30==29` **同相** ⇒ 印证前提 3；"
 "⑤**★★★新发现机制：先锋技能回费——已实现并互检通过**：费用数字在游戏帧 **581/1333** 出现 **+6** 跳变（非逐秒+1）；"
 "数据层：芬 `skcom_charge_cost[1]`「冲锋号令·α型」**等级7** `spCost=25 / initSp=6 / inc=1.0/s / blackboard.cost=+6 / skillType=AUTO / durationType=NONE`"
 " ⇒ 预测第1次 **580**、第2次 **1330**；实测视频 **581/1333**，**模拟器实现后 579/1329**（偏差 −2/−4 帧），"
 "**费用值 7→13、38→44 两侧完全一致**；代码改动：`data.py` 补 `skillType/durationType`（★实测在 **level 字典里**，不在技能表顶层）、"
 "`units.py` 加 `skill_type/skill_cost_gain`、`engine.py::_activate_skill` 按 `blackboard.cost` 回费且**瞬发技能立即结束**"
 "（否则 `skill_active` 永为真 ⇒ SP 不再充能、只发动一次）、`_operator_tick` 实现 **AUTO 自动发动**（`options={'auto_skill': False}` 可关）、"
 "`Battle.__init__` 新增 `options=`；**回归检查**：`replay_verify5.py` 仍为 **16/16、平均 1.81 帧、最大 7 帧**；"
 "⑥**★关卡敌人总数是硬地面真值**：游戏 HUD「ENEMY x/33」的分母 **33** = 关卡 `SPAWN` 展开数 **33**（`probe_waves_raw.py`）"
 " ⇒ 关卡解析链与图像识别链互相印证（注意：`DISPLAY_ENEMY_INFO`/`STORY` 不计入，否则会得到错误的 35）；"
 "⑦**⚠️后半段杀时刻存在未解释差异（已按机制3降级为待办 D9）**：计数器变化帧 vs 模拟器 `kill` 帧 ⇒ 第1/7 条差 −2/0 帧，第2 条 **+28**、第3 条 **−50**、其余 14~21 帧；"
 "已排除“计数器滞后 1 秒”（逐帧放大图显示计数器跳变与**敌人从画面消失**同帧：第2只游戏帧 488 在场、496 已消失），"
 "已确认模拟器**致命一击结算正确**（帧 464 原始切片 `{'kind':'hit','detail':{'src':'芬','tgt':'猎狗','dmg':325.0,'hp_after':0}}` + `{'kind':'kill'}`）；"
 "两种待判假设：**H1 显示延迟（死亡动画约28帧）** vs **H2 模拟器偏早**；决定性实验：读敌人血条/飘字伤害；"
 "⑧**文档与模式固定**：54 号报告新增 **§五十三**（工具链/坐标/双时钟/段表/技能回费/敌人总数/杀时对照/机制3记录）；"
 "55 号文件新增**「标准提取项」13 项表**（并入机制5信息查找链条）、清单 A/B 补 **7 条新坑**；"
 "`00_结论索引.md` 新增 **B17~B22、C4~C9、D6~D10**；"
 "⑨**新增脚本**：`ak/code/vision/apps/` 8 个；`ak/sim/draft/`：`dump_11_full.py`、`probe_schedule.py`、`probe_waves_raw.py`、"
 "`probe_kill_blow.py`、`verify_skill_cost.py`；"
 "⑩**合规**：仅本地模拟计算、视频/图片读取与用户提供的数据；**未触碰游戏文件/内存**，未连接游戏客户端。 |"
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
