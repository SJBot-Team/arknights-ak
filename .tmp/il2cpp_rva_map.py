"""il2cpp_rva_map.py —— dump.cs 的 RVA / 行号 -> 类名解析器（63b 任务临时脚本）

用法:
  python il2cpp_rva_map.py rva 0x354F880 0x3557AA0 ...   # RVA -> 方法全名 + 行号
  python il2cpp_rva_map.py line 322624 149358 ...        # dump.cs 行号 -> 所在类/命名空间
  python il2cpp_rva_map.py call 0x354F880 [maxinsn]      # 反汇编并按 RVA 解析 call/jmp 目标（单帧骨架）
  python il2cpp_rva_map.py dis 0x3585AB0 [maxinsn]       # 反汇编（call 目标带名字）

只读：dump.cs + GameAssembly.dll（E 盘副本）。
"""
import re
import sys

DUMP = r'E:\__file\ak_kb\client_res\il2cpp\dump\dump.cs'
DLL = r'E:\__file\ak_kb\client_res\il2cpp\GameAssembly.dll'
IMAGE_BASE = 0x180000000

TYPE_RE = re.compile(
    r'^(?:public|private|internal|protected|sealed|abstract|static|\s)*'
    r'(class|struct|interface|enum)\s+([A-Za-z0-9_.<>`\[\], ]+?)\s*(?::|//|$)')
RVA_RE = re.compile(r'^// RVA: (0x[0-9A-Fa-f]+)')
NS_RE = re.compile(r'^// Namespace: (.*)$')


def load():
    rva_map = {}      # rva -> (sig, cls, ns, lineno)
    class_lines = []  # (lineno, kind, name, ns)
    pending_sig = None
    last_cls = ('?', '')
    with open(DUMP, 'r', encoding='utf-8', errors='replace') as f:
        ns = ''
        for i, line in enumerate(f, 1):
            line = line.rstrip('\n')
            s = line.strip()
            m = NS_RE.match(s)
            if m:
                ns = m.group(1).strip()
                continue
            m = TYPE_RE.match(s)
            if m and '(' not in line.split('//')[0]:
                class_lines.append((i, m.group(1), m.group(2).strip(), ns))
                last_cls = (m.group(2).strip(), ns)
                pending_sig = None
                continue
            if s.startswith('// RVA: '):
                pending_sig = (s, i)
                continue
            if pending_sig and s and not s.startswith('//'):
                m2 = RVA_RE.match(pending_sig[0])
                if m2:
                    try:
                        rva = int(m2.group(1), 16)
                    except ValueError:
                        rva = -1
                    if rva > 0 and rva not in rva_map:
                        cls, cns = last_cls
                        rva_map[rva] = (s, cls, cns, pending_sig[1])
                pending_sig = None
    return rva_map, class_lines


def cls_of_line(class_lines, line):
    cur = None
    for (ln, kind, name, ns) in class_lines:
        if ln <= line:
            cur = (kind, name, ns, ln)
        else:
            break
    return cur


def main():
    rva_map, class_lines = load()
    cmd = sys.argv[1]
    if cmd == 'rva':
        for a in sys.argv[2:]:
            rva = int(a, 16)
            if rva in rva_map:
                sig, cls, ns, ln = rva_map[rva]
                print(f'{a}  [{ns}.{cls} @ dump.cs:{ln}]  {sig}')
            else:
                print(f'{a}  <未找到（可能是 icall/thunk）>')
    elif cmd == 'line':
        for a in sys.argv[2:]:
            ln = int(a)
            r = cls_of_line(class_lines, ln)
            print(f'{ln}  ->  {r}')
    elif cmd in ('call', 'dis'):
        import capstone
        import pefile
        maxinsn = int(sys.argv[3]) if len(sys.argv) > 3 else 400
        rva = int(sys.argv[2], 16)
        pe = pefile.PE(DLL, fast_load=True)
        raw = open(DLL, 'rb').read()
        secs = [(s.VirtualAddress, s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData),
                 s.PointerToRawData) for s in pe.sections]

        def rva2off(r):
            for va, end, pr in secs:
                if va <= r < end:
                    return pr + (r - va)
            return None

        off = rva2off(rva)
        code = raw[off:off + 64 * maxinsn]
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        md.detail = False
        n = 0
        for ins in md.disasm(code, rva):
            n += 1
            text = f'0x{ins.address:08X}  {ins.mnemonic:<8} {ins.op_str}'
            mm = re.search(r'rip \+ (0x[0-9a-fA-F]+)', ins.op_str)
            if mm:
                tva = ins.address + ins.size + int(mm.group(1), 16)
                toff = rva2off(tva)
                if toff is not None:
                    b = raw[toff:toff + 8]
                    u32 = int.from_bytes(b[:4], 'little')
                    f32 = __import__('struct').unpack('<f', b[:4])[0]
                    u64 = int.from_bytes(b, 'little')
                    f64 = __import__('struct').unpack('<d', b)[0]
                    text += (f'  ; -> RVA 0x{tva:X} u32={u32} f32={f32:g} u64={u64} f64={f64:g}')
            if cmd == 'call' and ins.mnemonic not in ('call', 'jmp'):
                continue
            tgt = None
            ops = ins.op_str.split(',')
            if ops and ops[0].strip().startswith('0x'):
                try:
                    tgt = int(ops[0].strip(), 16)
                except ValueError:
                    tgt = None
            if tgt is not None:
                tr = tgt
                if tr in rva_map:
                    sig, cls, ns, ln = rva_map[tr]
                    text += f'   -> {ns}.{cls}::{sig[:150]}  (dump.cs:{ln})'
                elif cmd == 'call':
                    continue
            elif ins.mnemonic == 'call' and cmd == 'call':
                continue
            print(text)
            if n >= maxinsn:
                break
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
