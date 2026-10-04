"""
unpack_ab.py — 明日方舟 AssetBundle 解析（lz4ak 自定义压缩 + UnityPy）
用法: python unpack_ab.py <ab文件> [--list] [--extract-text 输出目录]
说明: 明日方舟 v2.5.04+ 的 AB 使用 LZ4AK（交换 token 高低位）压缩，
      需先注册 decompress_lz4ak 到 UnityPy 的 LZHAM 槽位。
"""
import argparse
import os
import sys

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "Ark-Unpacker")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper
from ak_lz4ak import decompress_lz4ak

# 注册明日方舟自定义压缩（v2.5.04+）
CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak

import UnityPy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ab_file")
    ap.add_argument("--list", action="store_true", help="列出对象")
    ap.add_argument("--extract-text", default=None, help="导出 TextAsset 到目录")
    args = ap.parse_args()

    env = UnityPy.load(args.ab_file)
    text_cnt = 0
    for obj in env.objects:
        t = obj.type.name
        if args.list:
            try:
                data = obj.read()
                n = getattr(data, "m_Name", None) or getattr(data, "name", None)
                print(f"  {t:<18} path={obj.path_id} name={n} size={obj.byte_size}")
            except Exception as e:
                print(f"  {t:<18} path={obj.path_id} read-error: {e}")
        if t == "TextAsset" and args.extract_text:
            data = obj.read()
            name = data.m_Name or f"text_{obj.path_id}"
            out = os.path.join(args.extract_text, f"{name}.bin")
            os.makedirs(args.extract_text, exist_ok=True)
            with open(out, "wb") as f:
                f.write(bytes(data.m_Script))
            text_cnt += 1
    if args.extract_text:
        print(f"TextAsset 导出: {text_cnt} 个 -> {args.extract_text}")


if __name__ == "__main__":
    main()
