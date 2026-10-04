# -*- coding: utf-8 -*-
"""t200g_marshal2.py — 手写 Python 3.9 marshal 解析器（只取常量）。

依据 CPython 3.9 `Python/marshal.c` 的 r_object 逻辑：
  '0' NULL 'N' None 'F'/'T' bool 'S' StopIteration 'e' ref
  'i'/'l' int32（'l' 在 3.9 仍是 4 字节）'g' double 'f' 短浮点串 'a'/'A' 旧浮点
  's' bytes(4长度) 'u' unicode(4长度) 'z'/'Z' short ascii(4长度) 't' interned str
  '(' tuple '[' list '{' dict  '<' set '>' frozenset 'r' ref
  'c' code: argcount,i32 / posonlyargcount,i32 / kwonlyargcount,i32 / nlocals,i32 /
      stacksize,i32 / flags,i32 / code,obj / consts,obj / names,obj / varnames,obj /
      freevars,obj / cellvars,obj / filename,obj / name,obj / firstlineno,i32 /
      lnotab,obj
"""
import sys

FLAG_REF = 0x80


class Reader:
    def __init__(self, data):
        self.d = data
        self.i = 0
        self.refs = []
        self.tuples = []

    def u8(self):
        v = self.d[self.i]
        self.i += 1
        return v

    def i32(self):
        v = int.from_bytes(self.d[self.i:self.i + 4], 'little', signed=True)
        self.i += 4
        return v

    def bytes_obj(self):
        ln = self.i32()
        s = self.d[self.i:self.i + ln]
        self.i += ln
        return s

    def obj(self):
        code = self.u8()
        flag = code & FLAG_REF
        t = code & 0x7F
        ch = chr(t)
        if ch == '0':
            return None
        if ch == 'N':
            return None
        if ch == 'F':
            return False
        if ch == 'T':
            return True
        if ch == 'S':
            return 'StopIteration'
        if ch == 'e':
            return None
        if ch == 'i' or ch == 'l':
            v = self.i32()
            if flag:
                self.refs.append(v)
            return v
        if ch == 'g':
            import struct
            v = struct.unpack('<d', self.d[self.i:self.i + 8])[0]
            self.i += 8
            return v
        if ch == 'f':
            ln = self.u8()
            v = float(self.d[self.i:self.i + ln] or b'0')
            self.i += ln
            return v
        if ch == 'a' or ch == 'A':
            ln = self.u8()
            self.i += ln
            return 0.0
        if ch == 's':
            v = self.bytes_obj()
            if flag:
                self.refs.append(v)
            return v
        if ch in 'uzt':
            v = self.bytes_obj()
            try:
                v = v.decode('utf-8')
            except UnicodeDecodeError:
                v = v.decode('latin-1')
            if flag:
                self.refs.append(v)
            return v
        if ch == 'Z':
            # 3.9 没有 TYPE_SHORT_ASCII；稳妥处理成 4 字节长度
            v = self.bytes_obj()
            if flag:
                self.refs.append(v)
            return v
        if ch == 'c':
            for _ in range(6):
                self.i32()
            out = {}
            self.obj()                       # code bytes
            out['consts'] = self.obj()       # tuple
            out['names'] = self.obj()
            self.obj()                       # varnames
            self.obj()                       # freevars
            self.obj()                       # cellvars
            self.obj()                       # filename
            out['name'] = self.obj()
            self.i32()                       # firstlineno
            self.obj()                       # lnotab
            if flag:
                self.refs.append(out)
            return out
        if ch == '(':
            n = self.i32()
            items = [self.obj() for _ in range(n)]
            v = tuple(items)
            if flag:
                self.refs.append(v)
            return v
        if ch == '[':
            n = self.i32()
            items = [self.obj() for _ in range(n)]
            if flag:
                self.refs.append(items)
            return items
        if ch == '{':
            n = self.i32()
            for _ in range(n):
                self.obj()
                self.obj()
            return {}
        if ch == '<' or ch == '>':
            n = self.i32()
            for _ in range(n):
                self.obj()
            return set()
        if ch == 'r':
            self.i32()
            return None
        if ch == 'x':
            # 3.9 起：float 字符串化? 保守跳过
            self.i32()
            return None
        raise ValueError(f'unknown marshal type {ch!r} (0x{t:02x}) at {self.i - 1}')


def walk_consts(node, path='', out=None):
    if out is None:
        out = []
    if isinstance(node, dict) and 'consts' in node:
        name = node.get('name')
        for k, c in enumerate(node['consts'] or []):
            if isinstance(c, dict):
                walk_consts(c, f'{path}.{name}<{k}>', out)
            elif isinstance(c, (str, int, float, bool)) or c is None:
                out.append((f'{path}.{name}', k, c))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for p in sys.argv[1:]:
        print(f'===== {p}')
        d = open(p, 'rb').read()
        # 找到代码对象起点（'c' 0x63）
        start = None
        for off in range(4, 24):
            if off < len(d) and d[off] == 0x63:
                # 试探：argcount / posonly / kwonly / nlocals 都应是小数
                try:
                    a, b, c2, e = (
                        int.from_bytes(d[off + 1 + 4 * k:off + 5 + 4 * k], 'little')
                        for k in range(4))
                except Exception:
                    continue
                if max(a, b, c2, e) < 500:
                    start = off
                    break
        if start is None:
            print('  ! 未找到 code 起点')
            continue
        r = Reader(d)
        r.i = start
        try:
            obj = r.obj()
        except Exception as e:
            print(f'  ! 解析失败: {type(e).__name__}: {e} (停在 {r.i})')
            continue
        print(f'  顶层 code: name={obj.get("name")!r} consts={len(obj.get("consts") or [])}')
        for path, k, c in walk_consts(obj):
            print(f'  {path} consts[{k}] = {c!r}')
