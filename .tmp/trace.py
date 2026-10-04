# -*- coding: utf-8 -*-
"""trace.py <Class>.<Method> [n]  — list every call/jmp with resolved callee + string args.
   trace.py --rva 0x... [n]
Also resolves rip-relative string-literal operands inline."""
import re, struct, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\23922\Documents\ds_harness\ak\code\tools")
import read_cpp, json, os

SL = r"E:\__file\ak_kb\client_res\il2cpp\dump\stringliteral.json"
_sl = None
def slmap():
    global _sl
    if _sl is None:
        _sl = {int(e["address"], 16): e["value"] for e in json.load(open(SL, encoding="utf-8"))}
    return _sl

USAGE = {1: "TypeInfo", 2: "Il2CppType", 3: "MethodDef", 4: "FieldInfo",
         5: "StringLiteral", 6: "MethodRef", 0: "Invalid"}

def main():
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    d = read_cpp.Dll()
    idx = read_cpp.rva_index()
    keys = sorted(idx)
    md = Cs(CS_ARCH_X86, CS_MODE_64)

    if sys.argv[1] == "--rva":
        rva = int(sys.argv[2], 16); n = int(sys.argv[3]) if len(sys.argv) > 3 else 300; sig = ""
    else:
        cls, _, meth = sys.argv[1].partition(".")
        rva, sig = read_cpp.method_rva(cls, meth)
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        if rva is None:
            print("未定位到", sys.argv[1]); return
    print(f"// RVA: 0x{rva:X}  {sig}")
    code = d.read(rva, 16 * n + 64)
    pending = []          # string literals seen since last call
    for ins in md.disasm(code, d.base + rva):
        # collect string-literal operands
        for m in re.finditer(r"\[rip \+ (0x[0-9a-f]+)\]", ins.op_str):
            slot = ins.address + ins.size + int(m.group(1), 16) - d.base
            s = slmap().get(slot)
            if s is not None:
                pending.append((ins.mnemonic, s))
        if ins.mnemonic in ("call", "jmp") and re.match(r"^0x[0-9a-f]+$", ins.op_str):
            tgt = int(ins.op_str, 16) - d.base
            if tgt in idx:
                name = f"{idx[tgt][0]}.{idx[tgt][1]}"
            else:
                c = [k for k in keys if k <= tgt]
                name = (f"?<0x{tgt:X}> (prev 0x{max(c):X} +0x{tgt-max(c):X} "
                        f"{idx[max(c)][0]}.{idx[max(c)][1]})") if c else f"?<0x{tgt:X}>"
            note = ""
            if pending:
                note = "   STRARGS=" + repr([s for _, s in pending])
            print(f"0x{ins.address-d.base:08X}  {ins.mnemonic:<5} -> {name}{note}")
            pending = []
        if ins.mnemonic == "ret":
            break
    print("--- end ---")

main()
