# -*- coding: utf-8 -*-
"""append_t052_schedsurvey.py — 追加"出怪调度先摸底 + 随机出怪组实现"一轮到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第65轮】★★★★**依用户指示"先摸底、避免造轮子"：普查出怪调度字段并补齐加权随机出怪组**：'
 '①**用户指示**：构建模拟工程时**先对已有知识库与已解包代码结构初步掌握，避免重复造轮子**；'
 '敌方单位生成可能涉及**特定出怪列表**（单位/数量/时间/出生间隔），**先从伪代码层找线索**；'
 '②**★摸底结果：知识库里早已有全套沉淀（不应重推）**：'
 '**(a) 伪代码层** `knowledge/02_作战机制/24_常规关卡流程伪代码.md`（§1.3 预载波次、§2 阶段2 波次出生、'
 '§6 波次推进与结算 + 验证状态速查）；'
 '**(b) 时间轴算法** `knowledge/04/27_露托数据源与出怪时序本地化.md` §三.2 —— '
 '`waveStart=wave.preDelay`；`fragments 串行: fragStart=上一frag结束+frag.preDelay`；'
 '`每只怪 c: 时刻=fragStart+action.preDelay+action.interval*c`；`frag 结束=本 frag 动作最大时刻`'
 '（与露托 parseWaves 核验过）⇒ **本库 `build_schedule` 与之逐条一致，属已对齐**；'
 '**(c) cpp 字段表** `knowledge/04/33_cpp层战斗类结构与字段速查.md` §4.4/§五 —— '
 '`WaveData{preDelay/postDelay/maxTimeWaitingForNextWave/fragments/advancedWaveTag}`、'
 '`FragmentData{preDelay/actions}`、'
 '`ActionData{actionType/managedByScheduler/key/count/preDelay/interval/routeIndex/blockFragment/'
 'randomSpawnGroupKey/randomSpawnGroupPackKey/randomType/refreshType/weight}`、'
 '`Scheduler{m_waveStartTime/m_fragmentStartTime/m_actionQueue/m_blockCounter/…}`；'
 '**(d) 反汇编核验** `knowledge/04/36…` K-021（波次超时清空 + 胜负在全波次跑完后判定）；'
 '**(e) 信息完备性** `knowledge/04/31…` 已标出 🟡「`preDelay` float→帧量化时机未验证」；'
 '③**★字段普查（本轮新增，脚本 `probe_schedule_fields.py` + `probe_schedule_detail.py`）**：'
 '范围 = 本地 15 个关卡（主线 1-1~1-12、磨难 h12-4、肉鸽 1-1、act54side 01）⇒ '
 '**`maxTimeWaitingForNextWave` 全部 = −1（未启用超时清场）**；'
 '**`blockFragment=True` 仅 1-11 的 1 条 `TUTORIAL` 动作（非 SPAWN，不影响出怪时刻）**；'
 '**`randomSpawnGroupKey`+`weight` 仅肉鸽 1-1（17 条，组 g1/g2/g3）**；'
 '**`isUnharmfulAndAlwaysCountAsKilled` 见 h12-4（14 条）**；'
 '**★h12-4 不含随机组、不含 blockFragment ⇒ 现有静态时间轴对验证案例够用**；'
 '④**本轮实现（加权随机出怪组）**：语义 = 同 `randomSpawnGroupKey` 内动作**互斥**、'
 '整组按 `weight` **加权抽一条**（`key` 空串 = 抽到不刷怪，肉鸽确有此分支）；'
 '实现在 `engine.py::build_schedule(level, rng=…)`：'
 '**(a)** `Battle.__init__` **先建 RNG 再展开时间轴**（抽签消耗 RNG），'
 '并加断言**禁止之后重建 RNG**（否则抽签与后续随机序列脱节）；'
 '**(b)** 抽签结果写事件 **`spawn_random_pick {group,key,weight,weights,wave,frag}`**，可复现可审计；'
 '**(c)** 抽签用**可控随机数**（.NET System.Random 复刻）⇒ 同 seed 完全可复现；'
 '**(d)** `schedule` 项新增 `harmless_counted` / `blockFragment` 字段供后续使用；'
 '⑤**验证（新增 `test_spawn_random.py`，全通过）**：同 seed 两次运行 37 条出怪**逐条一致**；'
 '抽签事件 5 条（`g1→trap_051_vultres#1`、`g2→trap_051_vultres#2`、`g1→enemy_1007_slime`、'
 '`g3→enemy_1007_slime_2`、`g1→(空=不刷怪)`）；**6/6 个不同 seed 都会改变出怪列表**；'
 '主线 1-1 / h12-4 无随机组（不受影响）；**回归：1-1 仍 16/16、平均 2.19 帧、最大 7 帧**；'
 '⑥**文档**：新增 `knowledge/04/58_出怪调度_知识库摸底与实现边界.md`'
 '（"已有什么"对照表 + 字段普查表 + 实现与验证 + **经验教训** + 待办五项）；'
 '`55_工作前提与五项机制.md` 的**信息查找链条关卡层**补入「**出怪调度必查清单**」'
 '（preDelay/interval/count/routeIndex、managedByScheduler、blockFragment、'
 'randomSpawnGroupKey/weight/randomType/refreshType、maxTimeWaitingForNextWave、'
 'isUnharmfulAndAlwaysCountAsKilled），清单 B 新增 2 条坑（**不先摸底就造轮子**、**把用不到的机制当必须实现**）；'
 '`00_结论索引.md` 新增 **A23/A24、D15/D16/D17** 与检索词；'
 '⑦**待办（按普查排序）**：D15 `isUnharmfulAndAlwaysCountAsKilled`（h12-4 有 14 条，'
 '可与 `ENEMY x/N` 通道互验）；D16 `preDelay` 帧级量化；D17 `randomType`/`refreshType` 刷新语义；'
 '⑧**合规**：仅本地模拟计算、用户提供的数据与知识库既有沉淀；**未触碰游戏文件/内存**。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
