# -*- coding: utf-8 -*-
"""append_t052_round34.py — 写入 T-052 第三十四轮（实机在线标定：快路径可用 + 两个 ROI 待定）。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    ' **第三十四轮（实机在线标定帧级时钟）**：'
    '①新增 `code/vision/apps/calibrate_cost_bar_live.py`（进演习→开打→窗口抓屏连拍→逐帧读费用数字与费用条相位→'
    '对"相位逐帧+1/回绕30""回绕次数=费用增量"做断言）；'
    '②**实机在线验证快路径可用**：在**真实战斗画面**里用 BetterCam 窗口抓屏连拍 **567 帧 / 12s ≈ 47fps**'
    '（远高于 30fps 逻辑帧，说明帧级抓取在实战中成立，不只是静态桌面）；'
    '③费用**数字**识别在战斗中能出值（读到 `8`），但疑似**丢掉首位**（当时应在 18 附近）⇒ '
    '费用数字 ROI/字形分割对两位数不稳，列为待修；'
    '④费用**条** ROI 猜错：`(1795,800,1915,820)` 读到恒定 `fill=1.000`（那是静态 UI）；'
    '逐行亮度扫描（x1780-1920）得到：**数字在 y748–796**、**MAX 标签带 y808–816**、'
    '**疑似空槽轨道在 y≈866–886**（均 grey，max≈120）⇒ 条的真实位置需再标一次；'
    '⑤**标定方法的关键提醒**：费用顶上限时**条是静止的**，无法用帧间差分定位 ⇒ '
    '必须先用用户方法1的"故意消耗让条保持跳动"（部署+撤退便宜干员）制造动画，再做差分定位；'
    '⑥合规：全程仅演习，未消耗理智，未登录、未触碰禁用界面；'
    '⑦断点：先修两位数费用数字识别 → 用"保持跳动"重新标定费用条 ROI → 在线验证相位 30 帧回绕 → '
    '再标定三名计时器干员的待部署十分位 ROI（方法2），最后做两法互校。 | 2026-09-14 |'
)

s = io.open(P, encoding='utf-8').read()
anchor = '\n\n## 冲突记录'
if anchor not in s:
    raise SystemExit('anchor not found')
s = s.replace(anchor, ADD + anchor, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('T-052 已追加第三十四轮；行数 =', len(s.splitlines()))
