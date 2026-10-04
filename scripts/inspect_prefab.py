# inspect_prefab.py — 解析干员 prefab 的组件树（GameObject + Collider + MonoBehaviour 脚本）
import sys
sys.path.insert(0, r"C:\Users\23922\Documents\ds_harness\ak\scripts")
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper
from ak_lz4ak import decompress_lz4ak
CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak
import UnityPy
import json

env = UnityPy.load(sys.argv[1])

# 收集所有对象
objs = list(env.objects)
print(f"对象总数: {len(objs)}")

# 1) GameObject 树：name -> 组件（Transform 父子关系）
gos = {}   # path_id -> (name, components)
trans = {} # path_id -> parent_path_id
for obj in objs:
    if obj.type.name == "GameObject":
        d = obj.read()
        name = d.m_Name
        comps = []
        for c in (d.m_Components or []):
            try:
                comps.append((c.m_PathID, c.m_FileID))
            except Exception:
                pass
        gos[obj.path_id] = (name, comps)
    elif obj.type.name == "Transform":
        d = obj.read()
        parent = None
        try:
            parent = d.m_Father.m_PathID
        except Exception:
            pass
        trans[obj.path_id] = parent

# 2) 组件详情
print("\n=== 干员根 GameObject ===")
for pid, (name, comps) in gos.items():
    if name and not name.startswith("char_") == False and name:
        pass
# 打印所有 GameObject 名称 + 组件类型
for obj in objs:
    if obj.type.name == "GameObject":
        d = obj.read()
        if d.m_Name:
            print(f"GameObject '{d.m_Name}' path={obj.path_id}")

# 3) Collider（碰撞半径）
print("\n=== Collider 组件 ===")
for obj in objs:
    if "Collider" in obj.type.name:
        d = obj.read()
        r = {}
        for f in ("m_Radius", "m_Size", "m_Offset", "m_Center", "m_Enabled"):
            if hasattr(d, f):
                r[f] = getattr(d, f)
        print(f"  {obj.type.name} path={obj.path_id}: {json.dumps(r, ensure_ascii=False, default=str)}")

# 4) MonoBehaviour -> 脚本名
print("\n=== MonoBehaviour 脚本引用 ===")
for obj in objs:
    if obj.type.name == "MonoBehaviour":
        d = obj.read()
        try:
            script = d.m_Script.read()
            sname = getattr(script, "m_ClassName", None) or getattr(script, "m_Name", None)
            print(f"  MonoBehaviour path={obj.path_id} -> script: {sname}")
        except Exception:
            print(f"  MonoBehaviour path={obj.path_id} -> (script 解析失败)")
