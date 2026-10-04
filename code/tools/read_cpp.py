#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""read_cpp.py —— 明日方舟 IL2CPP (cpp 层) 检索与反汇编工具

定位：把 GameAssembly.dll + global-metadata.dat 经 Il2CppDumper 产出的 dump.cs
当作"cpp 层索引"，再用 pefile + capstone 按 RVA 反汇编真实机器码。

数据来源：
  dump.cs         Il2CppDumper 产物，类/字段偏移/方法 RVA
  GameAssembly.dll 本体，x64 PE
  script.json     方法地址表（本次未用，dump.cs 已够）

用法：
  python read_cpp.py find  <正则>            # 在 dump.cs 里搜类/方法/字段
  python read_cpp.py cls   <类名>            # 打印某个类的完整定义（字段偏移+方法RVA）
  python read_cpp.py dis   <RVA十六进制> [n]  # 反汇编该 RVA 起 n 条指令
  python read_cpp.py m     <类名>.<方法名> [n] # 定位方法并反汇编（支持子串匹配）
  python read_cpp.py call  <类名>.<方法名>    # 只看方法体里的 call/jmp 目标（追调用链）
  python read_cpp.py who   <RVA十六进制>      # 按 RVA 反查是哪个方法，并反汇编前几条
  python read_cpp.py xref  <RVA十六进制>      # 反查"谁调用了这个函数"（扫描 .text 的 E8 调用）

示例：
  python read_cpp.py m FP.Abs
  python read_cpp.py m BattleController.Update 40
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DUMP = os.path.join(BASE, "dump", "dump.cs")
DLL = os.path.join(BASE, "GameAssembly.dll")

_dump_lines = None


def dump_lines():
    """惰性读入 dump.cs（约 73MB / 200 万行），按行缓存。"""
    global _dump_lines
    if _dump_lines is None:
        with io.open(DUMP, encoding="utf-8", errors="replace") as f:
            _dump_lines = f.readlines()
    return _dump_lines


def find_class_range(name):
    """返回 (start, end) 行号（0 基），匹配 `public class X` / `struct X` 等。"""
    lines = dump_lines()
    # 不能用 \b：查 "RebornTalent" 会误匹配 "public struct RebornTalent.AdvancedRebornData"
    pat = re.compile(
        r"^public\s+(?:sealed\s+|abstract\s+|static\s+|partial\s+)*"
        r"(?:class|struct|interface|enum)\s+" + re.escape(name) + r"(?![\w.])"
    )
    for i, ln in enumerate(lines):
        if pat.match(ln):
            for j in range(i + 1, len(lines)):
                if lines[j].rstrip("\n") == "}":
                    return i, j
            return i, len(lines) - 1
    return None, None


def cmd_find(pat):
    n = 0
    rx = re.compile(pat)
    for i, ln in enumerate(dump_lines()):
        if rx.search(ln):
            n += 1
            if n <= 120:
                print(f"{i+1}: {ln.rstrip()}")
    print(f"--- 共 {n} 处匹配 ---")


def cmd_cls(name):
    s, e = find_class_range(name)
    if s is None:
        print(f"未找到类 {name}")
        return
    for i in range(s, e + 1):
        print(f"{i+1}: {dump_lines()[i].rstrip()}")


_strlit_cache = None


def _strlit_get(addr):
    """按 metadata usage slot 地址查字符串字面量。

    stringliteral.json 的 `address` 字段就是反汇编里 `lea rcx,[rip+X]` 的目标地址
    （该名单不按 usage index 排序，不能用 (usage<<29)|index 反查）。
    """
    global _strlit_cache
    if _strlit_cache is None:
        _strlit_cache = {}
        try:
            import json

            p = os.path.join(BASE, "dump", "stringliteral.json")
            with io.open(p, encoding="utf-8") as f:
                for item in json.load(f):
                    a = item.get("address")
                    if a is None:
                        continue
                    if isinstance(a, str):
                        a = int(a, 16) if a.lower().startswith("0x") else int(a)
                    _strlit_cache[a] = item.get("value", "")
        except Exception:
            pass
    return _strlit_cache.get(addr)


class Dll:
    def __init__(self):
        import pefile

        self.pe = pefile.PE(DLL, fast_load=True)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.data = open(DLL, "rb").read()

    def read(self, rva, size):
        off = self.pe.get_offset_from_rva(rva)
        return self.data[off:off + size]

    def peek(self, rva, size=8):
        try:
            return self.read(rva, size)
        except Exception:
            return None

    def annotate(self, ins):
        """解析 rip 相对操作数，读出目标处的常量值，便于读 .cctor 里的 static readonly。"""
        import struct

        m = re.search(r"\[rip \+ (0x[0-9a-f]+)\]", ins.op_str)
        if not m:
            return ""
        target = ins.address + ins.size + int(m.group(1), 16)
        trva = target - self.base
        parts = [f"-> 0x{trva:X}"]
        s = _strlit_get(trva)
        if s is None:
            s = _strlit_get(target)
        if s is not None:
            parts.append("str=" + repr(s)[:90])
        b = self.peek(trva, 8)
        if not b:
            return "  ; " + " ".join(parts)
        if len(b) >= 4:
            f32 = struct.unpack("<f", b[:4])[0]
            u32 = struct.unpack("<I", b[:4])[0]
            parts.append(f"u32={u32}")
            if f32 == f32 and abs(f32) < 1e12 and f32 != 0:
                parts.append(f"f32={f32:g}")
        if len(b) >= 8:
            u64 = struct.unpack("<Q", b)[0]
            parts.append(f"u64={u64}")
            f64 = struct.unpack("<d", b)[0]
            if f64 == f64 and abs(f64) < 1e15 and f64 != 0:
                parts.append(f"f64={f64:g}")
        return "  ; " + " ".join(parts)

    def disasm(self, rva, count=30, show_bytes=True):
        from capstone import Cs, CS_ARCH_X86, CS_MODE_64

        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True
        code = self.read(rva, 16 * count + 64)
        out = []
        for ins in md.disasm(code, self.base + rva):
            raw = ins.bytes.hex() if show_bytes else ""
            line = (f"0x{ins.address - self.base:08X}  {raw:<20} "
                    f"{ins.mnemonic:<8} {ins.op_str}{self.annotate(ins)}")
            out.append((ins, line))
            if len(out) >= count:
                break
        return out


def method_rva(cls, meth):
    """在类范围内找方法声明，取它前一行的 RVA 注释。"""
    s, e = find_class_range(cls)
    if s is None:
        print(f"未找到类 {cls}")
        return None, None
    lines = dump_lines()
    rx = re.compile(r"(?<![\w])" + re.escape(meth) + r"\s*\(")
    last_rva = None
    for i in range(s, e + 1):
        m = re.match(r"\s*//\s*RVA:\s*0x([0-9A-Fa-f]+)", lines[i])
        if m:
            last_rva = int(m.group(1), 16)
            continue
        if rx.search(lines[i]) and "//" not in lines[i].split("(")[0][:0]:
            if last_rva is not None:
                return last_rva, lines[i].strip()
    return None, None


_rva_index = None


def rva_index():
    """扫描 dump.cs 建立 RVA -> (类名, 签名) 索引，用于反查一个调用目标是谁。"""
    global _rva_index
    if _rva_index is not None:
        return _rva_index
    idx = {}
    cls = "?"
    rx_cls = re.compile(r"^public\s+(?:sealed\s+|abstract\s+|static\s+|partial\s+)*"
                        r"(?:class|struct|interface|enum)\s+([\w.<>`]+)")
    rx_rva = re.compile(r"^\s*//\s*RVA:\s*0x([0-9A-Fa-f]+)")
    pending = None
    for ln in dump_lines():
        m = rx_cls.match(ln)
        if m:
            cls = m.group(1)
            continue
        m = rx_rva.match(ln)
        if m:
            pending = int(m.group(1), 16)
            continue
        if pending is not None:
            # ⚠️ **同一 RVA 可能对应多个方法**：同构方法折叠（IL 体逐字节相同的方法/lambda 会被合并到同一地址；
            # 实例：`Scheduler.<_DealFragment>b__108_0` 与无关类 `RoguelikeShopStatusView.<_GenerateDalayTweens>b__23_0`
            # 共用 0x62F8C0）⇒ 必须存**列表**，只保留一个会误导（2026-09-28 实测踩到）。
            idx.setdefault(pending, []).append((cls, ln.strip()))
            pending = None
    _rva_index = idx
    return idx


def cmd_who(rva):
    idx = rva_index()
    hit = idx.get(rva)
    if hit:
        if len(hit) == 1:
            print(f"RVA 0x{rva:X} = {hit[0][0]}.{hit[0][1]}")
        else:
            print(f"RVA 0x{rva:X} 有 **{len(hit)} 个方法共用**（同构方法折叠；按 dump.cs 出现顺序）：")
            for c, s in hit:
                print(f"    - {c}.{s}")
            print("    ⚠️ 引用该 RVA 时必须说明是哪一个（否则会张冠李戴）")
    else:
        # 落在函数内部时给出最近的前驱
        cands = [k for k in idx if k <= rva]
        if cands:
            near = max(cands)
            first = idx[near][0]
            extra = f"（该地址另有 {len(idx[near])-1} 个同构方法）" if len(idx[near]) > 1 else ""
            print(f"RVA 0x{rva:X} 未被索引命中；最近前驱 0x{near:X} (+0x{rva-near:X}) "
                  f"= {first[0]}.{first[1]}{extra}")
        else:
            print(f"RVA 0x{rva:X} 无命中")
    # 附带调用点
    d = Dll()
    for ins, line in d.disasm(rva, 12):
        print("   " + line)
        if ins.mnemonic == "ret":
            break


def cmd_xref(target_rva):
    """扫描 .text 段中的 E8 相对调用，找出所有调用 target_rva 的位置，并反查调用者。"""
    import struct

    d = Dll()
    # IL2CPP 把托管代码放在名为 "il2cpp" 的段里（不是 .text），两者都要扫
    segs = []
    for s in d.pe.sections:
        if s.Characteristics & 0x20000000:  # IMAGE_SCN_MEM_EXECUTE
            segs.append((s.VirtualAddress, s.get_data()))
    if not segs:
        print("未找到可执行段")
        return
    hits = []
    for base, data in segs:
        off = 0
        while True:
            i = data.find(b"\xe8", off)
            if i < 0 or i + 5 > len(data):
                break
            off = i + 1
            rel = struct.unpack("<i", data[i + 1:i + 5])[0]
            if base + i + 5 + rel == target_rva:
                hits.append(base + i)
    who = rva_index()
    keys = sorted(who)
    print(f"RVA 0x{target_rva:X} 被调用 {len(hits)} 处（E8 直接调用）")
    seen = set()
    for h in hits[:80]:
        cands = [k for k in keys if k <= h]
        near = max(cands) if cands else None
        if near is not None and h - near < 0x4000:
            # ⚠️ `who[near]` 是**列表**（同一 RVA 可能多个同构方法）⇒ 取第一个，并标注还有几个
            group = who[near]
            cls, sig = group[0]
            extra = f" [+{len(group)-1} 个同构方法]" if len(group) > 1 else ""
            label = f"{cls}.{sig} (+0x{h-near:X}){extra}  ⚠️最近前驱，可能是共享桩"
        else:
            label = "未知函数"
        print(f"  call @ 0x{h:X}  ← {label}")
        seen.add(label.split(" (+")[0])
    if len(hits) > 80:
        print(f"  … 其余 {len(hits)-80} 处省略")
    print(f"--- 去重后调用者 {len(seen)} 个 ---")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd, arg = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    if cmd == "find":
        cmd_find(arg)
    elif cmd == "xref":
        cmd_xref(int(arg, 16))
    elif cmd == "who":
        cmd_who(int(arg, 16))
    elif cmd == "cls":
        cmd_cls(arg)
    elif cmd == "dis":
        d = Dll()
        for _, line in d.disasm(int(arg, 16), n):
            print(line)
    elif cmd == "m":
        cls, _, meth = arg.partition(".")
        rva, sig = method_rva(cls, meth)
        if rva is None:
            print(f"未定位到 {arg}")
            return
        print(f"// RVA: 0x{rva:X}  {sig}")
        d = Dll()
        for _, line in d.disasm(rva, n):
            print(line)
    elif cmd == "call":
        d = Dll()
        cls, _, meth = arg.partition(".")
        rva, sig = method_rva(cls, meth)
        if rva is None:
            print(f"未定位到 {arg}")
            return
        print(f"// RVA: 0x{rva:X}  {sig}")
        for ins, line in d.disasm(rva, 400):
            if ins.mnemonic in ("call", "jmp") and ins.op_str.startswith("0x"):
                tgt = int(ins.op_str, 16) - d.base
                print(f"  {line}   -> RVA 0x{tgt:X}")
            if ins.mnemonic == "ret":
                break
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
