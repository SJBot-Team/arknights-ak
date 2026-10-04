# -*- coding: utf-8 -*-
"""ak_sim — 明日方舟战斗模拟器（draft：搭建中）

分层：
  fp.py         Q32.32 定点（复刻游戏内 FP）
  data.py       标准数据提取（表/关卡/单位/范围/模组/动画索引）
  battlemap.py  地图 / 坐标 / SPFA 寻路 / nextnode 平滑
  units.py      单位模型（干员/敌人/召唤物）
  combat.py     伤害结算（物理/法术/真实/元素）
  engine.py     战斗主循环（费用/波次/移动/阻挡/索敌/攻击/技能/结算/逐帧记录）
  rng.py        局内随机数（.NET System.Random 复刻）
  axis.py       轴表格式（与打图执行器共用）
  cli.py        命令行入口

验证锚点（逐项对照 knowledge）：
  - 伤害公式 → knowledge/01 §3、24 §5（T1）
  - 攻击间隔帧化 → knowledge/23 K-004（🟡）
  - 寻路/避障/惯性 → knowledge/20 cv31743470、23 K-007（🟡）
  - 阻挡半径 0.7071 / 3 帧扫描 → knowledge/02、21（🟡）
  - 仇恨（部署时间 0.1 精度 3 帧分组）→ knowledge/21（✅ 过滤器 + 🟡 行为）
  - 随机数 → knowledge/34（✅ 已逐值验证）
  - 同帧执行顺序 → knowledge/38/39（🟡 部分；本实现按"敌人→干员"顺序，待核）
"""
__all__ = ['fp', 'data', 'battlemap', 'units', 'combat', 'engine', 'rng']
__version__ = '0.1.0-draft'
