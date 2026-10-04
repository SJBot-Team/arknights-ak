"""
translate_buff.py — 基于贝娜量角器字典的 buff 模板→中文伪代码翻译器
字典：E:\__file\ak_kb\downloads\量角器\translation\anne_dictionary.json / bena_dictionary.json
用法：python translate_buff.py <模板key> [更多key...]
"""
import json
import re
import sys

DICTS = [
    r"E:\__file\ak_kb\downloads\量角器\translation\anne_dictionary.json",
    r"E:\__file\ak_kb\downloads\量角器\translation\bena_dictionary.json",
]
GD = r"E:\__file\ak_kb\gamedata\buff_template_data.json"

# 载入字典（合并所有组）
groups = {}
for p in DICTS:
    try:
        d = json.load(open(p, encoding="utf-8"))
        for g, m in d.items():
            groups.setdefault(g, {}).update(m)
    except Exception as e:
        print("字典载入失败:", p, e)

# 节点类型 → 说明（补充字典没有的部分，标注源自知识库 notes/12）
NODE_CN = {
    "IfElse": "条件分支", "IfNot": "若非", "AlwaysNext": "无条件继续",
    "CheckContainsBuff": "检查是否持有Buff", "CheckBlocked": "检查是否被阻挡",
    "CheckTargetInRange": "检查目标在范围内", "CheckAbnormalFlag": "检查异常状态",
    "CreateBuff": "创建Buff", "CreateBuffById": "按ID创建Buff", "CreateBuffInRange": "范围内创建Buff",
    "FinishBuff": "结束Buff", "FinishBuffsById": "按ID结束Buff",
    "BlockDamage": "抵挡伤害", "AdvancedApplyDamage": "造成伤害",
    "FixedValueDamage": "固定值伤害", "DamageViaMaxHpRatio": "按最大生命比例伤害",
    "AOEDamage": "范围伤害", "EmitProjectile": "发射弹道",
    "AtkScaleUp": "攻击力放大", "DamageScale": "伤害缩放",
    "ModifySp": "修改技力", "ModifyCost": "修改费用",
    "TriggerAbility": "触发能力", "TriggerEnemySkill": "触发敌方技能",
    "InstantKill": "直接击杀", "SwitchMode": "切换形态",
    "CreateEffect": "创建特效", "PlayAudio": "播放音效",
    "CheckContainsDeckBuff": "检查玩家是否持有Buff(Deck=玩家)",
    "CreateCardBuffFilterByDeckBuff": "给玩家卡牌创建Buff(Deck=玩家)",
    "Dice": "概率判定", "IfConditions": "多条件组合",
    "IsDamage": "伤害判定", "IsHeal": "治疗判定",
    "FilterByBlackboardValue": "按黑板值过滤", "FilterByTargetHpRatio": "按目标血量比例过滤",
    "HealViaMaxHpRatio": "按最大生命比例治疗",
    "FinishDerivedBuff": "结束衍生Buff",
}

# 已知枚举字段 → 字典组
FIELD_GROUP = {
    "_targetType": "target", "_target": "target", "_sourceType": "target",
    "attributeType": "attribute", "formulaItem": "formula",
    "abnormalFlags": "abnormal", "abnormalImmunes": "abnormal", "abnormalAntis": "abnormal",
    "damageType": "damage_type", "damageMask": "damage_type",
    "elementType": "element", "lifeTimeType": None,
    "compareOp": "compare",
}


def tr_enum(group, val):
    m = groups.get(group)
    if m and val in m:
        return m[val]
    return val


def translate(obj, indent=0, depth=0):
    lines = []
    pad = "  " * indent
    if isinstance(obj, dict):
        # 检测 $type 节点
        if "$type" in obj:
            m = re.search(r"Nodes\+([A-Za-z0-9_]+)", obj.get("$type", ""))
            node = m.group(1) if m else obj.get("$type", "")
            cn = NODE_CN.get(node, node)
            lines.append(f"{pad}▶ {cn}")
            for k, v in obj.items():
                if k in ("$type",):
                    continue
                if k == "_buff" and isinstance(v, dict):
                    lines.append(f"{pad}  Buff详情:")
                    lines.append(f"{pad}    key: {v.get('buffKey')} | 模板: {v.get('templateKey')} | 叠加: {v.get('maxStackCnt')} | 类型: {v.get('overrideType')}")
                    attrs = v.get("attributes") or {}
                    abn = attrs.get("abnormalFlags") or []
                    if abn:
                        cn_abn = [tr_enum("abnormal", a) for a in abn]
                        lines.append(f"{pad}    异常状态: {', '.join(cn_abn)}")
                    for m in attrs.get("attributeModifiers") or []:
                        at = tr_enum("attribute", m.get("attributeType"))
                        fm = tr_enum("formula", m.get("formulaItem"))
                        bb = "（黑板值）" if m.get("loadFromBlackboard") else m.get("value")
                        lines.append(f"{pad}    属性修改: {at} {fm} {bb}")
                    continue
                if isinstance(v, (dict, list)):
                    sub = translate(v, indent + 2, depth + 1)
                    if sub.strip():
                        lines.append(f"{pad}  {k}:")
                        lines.append(sub)
                else:
                    g = FIELD_GROUP.get(k)
                    vs = str(v)
                    if g:
                        vs = tr_enum(g, v) if isinstance(v, str) else vs
                    lines.append(f"{pad}  {k}: {vs}")
        else:
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    sub = translate(v, indent + 1, depth + 1)
                    if sub.strip():
                        lines.append(f"{pad}{k}:")
                        lines.append(sub)
                else:
                    lines.append(f"{pad}{k}: {v}")
    elif isinstance(obj, list):
        for item in obj:
            sub = translate(item, indent, depth + 1)
            lines.append(sub)
    return "\n".join(l for l in lines if l)


def main():
    gd = json.load(open(GD, encoding="utf-8"))
    for key in sys.argv[1:]:
        v = gd.get(key)
        if not v:
            print(f"未找到: {key}")
            continue
        print(f"===== {key} =====")
        for ev, nodes in (v.get("eventToActions") or {}).items():
            g = groups.get("event") or {}
            cn_ev = g.get(ev, ev)
            print(f"\n【{cn_ev} ({ev})】")
            for node in nodes:
                print(translate(node))


if __name__ == "__main__":
    main()
