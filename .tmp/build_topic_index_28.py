# -*- coding: utf-8 -*-
"""T-067：为 0926/0927 两场新录播生成「关键词热点索引」，便于切片精读（不读全文）。
输出: ak\\_raw\\bilibili\\transcripts\\_28_关键词热点.md
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
T = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\transcripts"
BVS = {
    "BV1xRho6DEAQ": ("0926 属性，伤害等", [
        "属性", "伤害", "攻击力", "防御", "法抗", "抗性", "攻击间隔", "攻速", "帧",
        "乘算", "加算", "终值", "保底", "最小", "固定伤害", "真实伤害", "元素", "灼燃",
        "凋亡", "减伤", "护盾", "屏障", "结算", "顺序", "buff", "状态", "倍率",
        "取整", "向下", "向上", "四舍", "两次", "叠加", "持续时间", "结算顺序"]),
    "BV1cmaa6VEPR": ("0927 出怪帧", [
        "出怪", "帧", "波次", "刷新", "敌人", "检查点", "延迟", "补帧", "索敌", "阻挡",
        "对齐", "生成", "spawn", "出怪帧", "提前", "延后", "卡帧", "部署", "费用",
        "第一波", "间隔", "预兆", "预测", "随机", "种子", "第几帧", "首帧"]),
}
LINE = re.compile(r"^\[\s*([0-9.]+)-\s*([0-9.]+)\]\s*(.*)$")


def fmt(sec):
    sec = float(sec)
    return f"{int(sec // 60):d}:{int(sec % 60):02d}"


def main():
    out = ["# 28 新增录播转写 · 关键词热点索引（**原始资料，非核心知识**）", "",
           "> 由 `ak\\.tmp\\build_topic_index.py` 变体生成；用途：**按关键词跳到时间段切片精读**，"
           "不必通读全文。时间戳 = 整条 BV 全局轴（秒）。", ""]
    for bv, (label, kws) in BVS.items():
        path = os.path.join(T, bv + ".txt")
        if not os.path.exists(path):
            out.append(f"## {bv}（{label}）—— **转写文件不存在**\n")
            continue
        lines = []
        with open(path, encoding="utf-8") as f:
            for ln in f:
                m = LINE.match(ln.strip())
                if m:
                    lines.append((float(m.group(1)), float(m.group(2)), m.group(3)))
        out.append(f"## {bv}（{label}）")
        out.append(f"- 转写段数 {len(lines)}，覆盖至 {fmt(lines[-1][1]) if lines else 'N/A'}"
                   f"（{lines[-1][1]:.0f}s）" if lines else "- 空")
        out.append("")
        out.append("| 关键词 | 命中数 | 前 12 个时间点（mm:ss） |")
        out.append("|---|---|---|")
        for kw in kws:
            hits = [s for s, e, t in lines if kw in t]
            if not hits:
                continue
            pts = "、".join(fmt(x) for x in hits[:12])
            out.append(f"| {kw} | {len(hits)} | {pts} |")
        out.append("")
        # 机制密度：每 300s 窗口命中关键词总数，找"讲课密集段"
        buckets = {}
        for s, e, t in lines:
            if any(k in t for k in kws):
                buckets.setdefault(int(s // 300) * 300, 0)
                buckets[int(s // 300) * 300] += 1
        top = sorted(buckets.items(), key=lambda x: -x[1])[:20]
        out.append("**机制密集窗口（每 5 分钟命中关键词数 top20，先读这些）**")
        out.append("")
        out.append("| 窗口起点 | 命中 |")
        out.append("|---|---|")
        for b, n in sorted(top):
            out.append(f"| {fmt(b)}（{b}s） | {n} |")
        out.append("")
    p = os.path.join(T, "_28_关键词热点.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("saved", p, len(out), "lines")


if __name__ == "__main__":
    main()
