import json, sys, re, os

SL = r'E:\__file\ak_kb\client_res\il2cpp\dump\stringliteral.json'
_data = None

def load():
    global _data
    if _data is None:
        _data = json.load(open(SL, encoding='utf-8'))
    return _data

def by_index(i):
    d = load()
    if 0 <= i < len(d):
        return d[i]
    return None

def decode(v):
    """v = encoded metadata usage token value (from DLL static bytes)"""
    usage = v >> 29
    idx = v & 0x1FFFFFFF
    return usage, idx

def slot(addr):
    """look up by usage slot address e.g. 0x755D628"""
    d = load()
    key = int(addr) if not isinstance(addr, str) else int(addr, 16)
    for i, e in enumerate(d):
        if int(e['address'], 16) == key:
            return i, e['value']
    return None, None

USAGE = {1: 'TypeInfo', 2: 'Il2CppType', 3: 'MethodDef', 4: 'FieldInfo',
         5: 'StringLiteral', 6: 'MethodRef', 0: 'Invalid'}

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'idx':
        for a in sys.argv[2:]:
            v = int(a, 0)
            u, i = decode(v)
            e = by_index(i)
            print(f'{v} (0x{v:08X}) usage={u}({USAGE.get(u)}) index={i} -> addr={e["address"] if e else None} value={e["value"][:200] if e else None!r}')
    elif mode == 'addr':
        for a in sys.argv[2:]:
            i, val = slot(a)
            print(f'{a} -> index={i} value={val!r}')
    elif mode == 'search':
        pat = re.compile(sys.argv[2], re.I)
        d = load()
        for i, e in enumerate(d):
            if pat.search(e['value']):
                print(f'[{i}] {e["address"]} {e["value"]!r}')
