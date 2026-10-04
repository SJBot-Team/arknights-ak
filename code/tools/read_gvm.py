#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""read_gvm.py —— 读取 Unity 序列化文件里的全局管理器设置（cpp 层的运行期参数）

明日方舟逻辑步长 = UnityEngine.Time.fixedDeltaTime（见 GlobalConsts..cctor 反汇编）。
该值的真源是 Unity 打包时写入 globalgamemanagers 的 TimeManager 对象。

用法：
  python read_gvm.py <文件路径> [对象类型名过滤]
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else \
        r"E:\__file\ak_kb\client_res\unity_player\globalgamemanagers"
    want = sys.argv[2] if len(sys.argv) > 2 else None

    import UnityPy

    env = UnityPy.load(path)
    print(f"== {os.path.basename(path)} ==")
    n = 0
    for obj in env.objects:
        tname = obj.type.name if hasattr(obj.type, "name") else str(obj.type)
        if want and want.lower() not in tname.lower():
            continue
        n += 1
        try:
            data = obj.read()
        except Exception as e:
            print(f"[{obj.path_id}] {tname}  读取失败: {e}")
            continue
        print(f"\n--- [{obj.path_id}] {tname} ---")
        if hasattr(data, "__dict__"):
            for k, v in vars(data).items():
                if k.startswith("_"):
                    continue
                print(f"    {k} = {v!r}")
        else:
            print(f"    {data!r}")
    print(f"\n== 共 {n} 个对象 ==")


if __name__ == "__main__":
    main()
