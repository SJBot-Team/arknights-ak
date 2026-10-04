# -*- coding: utf-8 -*-
"""t200g_m2.py — marshal 解析器 v2（带 REF 支持与失败点报告）。

关键修正：3.9 的 co_code 是 `bytes`，其 4 字节长度在**紧邻长度前**存在；
此前把 `f3 ce 00 00 00` 误读为 4 字节长度 + 首字节。这里按 marshalled 流顺序解析，
并在异常时报告偏移与已解析到的字段，便于人工校正。
"""
import struct
import sys

FLAG_REF = 0x80


class R:
    def __init__(self, d, i0):
        self.d = d
        self.i = i0
        self.refs = []

    def u8(self):
        v = self.d[self.i]
        self.i += 1
        return v

    def i32(self):
        v = int.from_bytes(self.d[self.i:self.i + 4], 'little', signed=True)
        self.i += 4
        return v

    def blen_bytes(self):
        ln = self.i32()
        if ln < 0 or self.i + ln > len(self.d):
            raise ValueError(f'bytes len {ln} 越界 @{self.i}')
        v = self.d[self.i:self.i + ln]
        self.i += ln
        return v

    def obj(self, depth=0):
        at = self.i
        c = self.u8()
        t = c & 0x7F
        flag = bool(c & FLAG_REF)
        ch = chr(t)
        v = self._obj(ch, depth)
        if flag:
            self.refs.append(v)
        return v

    def _obj(self, ch, depth):
        if ch == '0' or ch == 'N':
            return None
        if ch == 'F':
            return False
        if ch == 'T':
            return True
        if ch == 'S':
            return 'StopIteration'
        if ch == 'e':
            self.i32()
            return None
        if ch in 'il':
            return self.i32()
        if ch == 'g':
            v = struct.unpack('<d', self.d[self.i:self.i + 8])[0]
            self.i += 8
            return v
        if ch == 'f':
            ln = self.u8()
            v = float(self.d[self.i:self.i + ln] or b'0')
            self.i += ln
            return v
        if ch in 'aA':
            ln = self.u8()
            self.i += ln
            return 0.0
        if ch == 's':
            return self.blen_bytes()
        if ch in 'uzt':
            b = self.blen_bytes()
            try:
                return b.decode('utf-8')
            except UnicodeDecodeError:
                return b.decode('latin-1')
        if ch == 'Z':
            return self.blen_bytes()
        if ch == 'c':
            args = [self.i32() for _ in range(6)]
            out = {'argcount': args[0], 'posonly': args[1], 'kwonly': args[2],
                   'nlocals': args[3], 'stacksize': args[4], 'flags': args[5]}
            out['code'] = self.obj(depth + 1)
            out['consts'] = self.obj(depth + 1)
            out['names'] = self.obj(depth + 1)
            out['varnames'] = self.obj(depth + 1)
            out['freevars'] = self.obj(depth + 1)
            out['cellvars'] = self.obj(depth + 1)
            out['filename'] = self.obj(depth + 1)
            out['name'] = self.obj(depth + 1)
            out['firstlineno'] = self.i32()
            out['lnotab'] = self.obj(depth + 1)
            return out
        if ch == '(':
            n = self.i32()
            return tuple(self.obj(depth + 1) for _ in range(n))
        if ch == '[':
            n = self.i32()
            return [self.obj(depth + 1) for _ in range(n)]
        if ch == '{':
            n = self.i32()
            return {self.obj(depth + 1): self.obj(depth + 1) for _ in range(n)}
        if ch in '<>':
            n = self.i32()
            return {self.obj(depth + 1) for _ in range(n)}
        if ch == 'r':
            self.i32()
            return None
        raise ValueError(f'未知 marshal 类型 {ch!r} @{self.i - 1}')


def walk(node, path, out):
    if isinstance(node, dict) and 'consts' in node:
        nm = node.get('name')
        for k, c in enumerate(node['consts'] or []):
            p = f'{path}/{nm}[{k}]'
            if isinstance(c, dict):
                walk(c, p, out)
            else:
                out.append((p, c))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for p in sys.argv[1:]:
        print(f'===== {p}')
        d = open(p, 'rb').read()
        ok = False
        for off in range(4, 24):
            if d[off] != 0x63:
                continue
            r = R(d, off)
            try:
                top = r.obj()
            except Exception as e:
                print(f'  off={off} 失败: {type(e).__name__}: {e}')
                continue
            if not isinstance(top, dict) or not isinstance(top.get('consts'), tuple):
                continue
            print(f'  ✅ code 起点 @{off}  name={top.get("name")!r} file={top.get("filename")!r} '
                  f'argcount={top["argcount"]} nlocals={top["nlocals"]}')
            for path, c in walk(top, '', []):
                print(f'  {path} = {c!r}')
            ok = True
            break
        if not ok:
            print('  ! 所有候选起点都解析失败')
