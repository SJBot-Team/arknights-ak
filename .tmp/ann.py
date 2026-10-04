# -*- coding: utf-8 -*-
"""Annotate il2cpp disassembly: for every rip-relative operand, resolve the
metadata-usage slot and (if it is a string literal, usage==5) print the string.

Usage: python ann.py <Class>.<Method> [n]      or   python ann.py --rva 0x288E270 200
"""
import io, json, os, re, struct, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\23922\Documents\ds_harness\ak\code\tools")
import read_cpp

BASE = r"E:\__file\ak_kb\client_res\il2cpp"
SL = os.path.join(BASE, "dump", "stringliteral.json")

_sl = None
def slmap():
    global _sl
    if _sl is None:
        _sl = {}
        for e in json.load(open(SL, encoding="utf-8")):
            _sl[int(e["address"], 16)] = e["value"]
    return _sl

USAGE = {1: "TypeInfo", 2: "Il2CppType", 3: "MethodDef", 4: "FieldInfo",
         5: "StringLiteral", 6: "MethodRef", 0: "Invalid"}

def annotate(d, md, rva, count):
    code = d.read(rva, 16 * count + 64)
    out = []
    for ins in md.disasm(code, d.base + rva):
        extra = []
        for m in re.finditer(r"\[rip \+ (0x[0-9a-f]+)\]", ins.op_str):
            slot = ins.address + ins.size + int(m.group(1), 16) - d.base
            b = d.peek(slot, 4)
            if not b:
                continue
            v = struct.unpack("<I", b)[0]
            usage, idx = v >> 29, v & 0x1FFFFFFF
            s = slmap().get(slot)
            tag = f"slot=0x{slot:X} tok=0x{v:08X} usage={usage}({USAGE.get(usage)})"
            if s is not None:
                tag += f" STR={s!r}"
            elif usage == 1:
                tag += " [type]"
            elif usage == 6:
                tag += " [methodref]"
            extra.append(tag)
        line = (f"0x{ins.address - d.base:08X}  {ins.bytes.hex():<20} "
                f"{ins.mnemonic:<8} {ins.op_str}")
        out.append(line)
        for e in extra:
            out.append("            ; " + e)
        if len([1 for l in out if not l.startswith(' ')]) >= count:
            break
    return out

def main():
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    d = read_cpp.Dll()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    if sys.argv[1] == "--rva":
        rva = int(sys.argv[2], 16)
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 100
        sig = ""
    else:
        cls, _, meth = sys.argv[1].partition(".")
        rva, sig = read_cpp.method_rva(cls, meth)
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        if rva is None:
            print("未定位到", sys.argv[1]); return
    print(f"// RVA: 0x{rva:X}  {sig}")
    print("\n".join(annotate(d, md, rva, n)))

main()
