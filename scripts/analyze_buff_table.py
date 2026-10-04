# analyze_buff_table.py — buff_template_data.json 结构统计（输出 JSON 报告）
import json, re, sys
from collections import Counter

path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata\buff_template_data.json"
out_report = r"C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata\buff_stats.json"
print("加载中...")
data = json.load(open(path, encoding="utf-8"))
report = {}
report["total_templates"] = len(data)

# 1) 前缀
prefix = Counter()
for k in data:
    prefix[re.split(r"[\[\]_]", k)[0]] += 1
report["prefix"] = prefix.most_common(60)

# 2) 字段频率
fields = Counter()
for k, v in data.items():
    for f in v:
        fields[f] += 1
report["fields"] = fields.most_common(30)

# 3) 事件
events = Counter()
for k, v in data.items():
    for e in (v.get("eventToActions") or {}):
        events[e] += 1
report["events"] = events.most_common(200)

# 4) 节点
nodes = Counter()
for k, v in data.items():
    for elist in (v.get("eventToActions") or {}).values():
        for node in elist:
            if not isinstance(node, dict):
                continue
            m = re.search(r"Nodes\+([A-Za-z0-9_]+)", node.get("$type", ""))
            if m:
                nodes[m.group(1)] += 1
report["nodes"] = nodes.most_common(300)

# 5) attributeType / formulaItem（在 CreateBuff 的 _buff.attributes.attributeModifiers 里）
attrs = Counter(); formulas = Counter()
for k, v in data.items():
    for elist in (v.get("eventToActions") or {}).values():
        for node in elist:
            if not isinstance(node, dict):
                continue
            if "CreateBuff" in node.get("$type", ""):
                b = node.get("_buff")
                if isinstance(b, dict):
                    for m in (b.get("attributes", {}).get("attributeModifiers") or []):
                        attrs[m.get("attributeType")] += 1
                        formulas[m.get("formulaItem")] += 1
report["attributeType"] = dict(attrs)
report["formulaItem"] = dict(formulas)

# 6) onEventPriority 取值
op = Counter(v.get("onEventPriority") for v in data.values())
report["onEventPriority"] = dict(op)

with open(out_report, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print("报告已写入:", out_report)
print("模板总数:", report["total_templates"])
print("事件种类:", len(events), "节点种类:", len(nodes))
