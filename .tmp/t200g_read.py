# -*- coding: utf-8 -*-
"""t200g_read.py — 修正版 Python 3.9 marshal 读取器 + 反汇编器。

要点（修正 marshal9.py 的缺陷）：
1) `r_object()` 在读到 FLAG_REF 时**先占用 refs 槽**，子解析完成后回填；
   `r_code()` **不得**再 append 一次（marshal9 重复 append ⇒ 之后所有 'r' 引用错位，
   常量表出现 `(0.33, 0, <上一个元组>, 0.9)` 这类串扰）。
2) 提供一个最小 3.9 反汇编器：只需 opcode 名 + 常量/名字索引，用来确认赋值顺序。

用法：
  python t200g_read.py dump <pyc> <out.txt>
  python t200g_read.py dis  <pyc> [函数名]
"""
import dis
import importlib.util
import io
import struct
import sys

FLAG_REF = 0x80


class Code:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return f'<code {self.name} consts={len(self.consts)} names={len(self.names)}>'


class Reader:
    def __init__(self, data, base=0):
        self.d = data
        self.p = 0
        self.base = base
        self.refs = []

    def where(self):
        return self.base + self.p

    def r_byte(self):
        b = self.d[self.p]
        self.p += 1
        return b

    def r_long(self):
        v = struct.unpack('<i', self.d[self.p:self.p + 4])[0]
        self.p += 4
        return v

    def r_double(self):
        v = struct.unpack('<d', self.d[self.p:self.p + 8])[0]
        self.p += 8
        return v

    def r_bytes(self):
        n = self.r_long()
        if n < 0 or self.p + n > len(self.d):
            raise ValueError(f'bytes len {n} 越界 @{self.where()}')
        b = self.d[self.p:self.p + n]
        self.p += n
        return b

    def r_object(self, depth=0):
        code = self.r_byte()
        flag = bool(code & 0x80)
        c = chr(code & 0x7F)
        idx = None
        if flag:
            idx = len(self.refs)
            self.refs.append(None)
        obj = self._impl(c, depth)
        if flag:
            self.refs[idx] = obj
        return obj

    def _impl(self, c, depth):
        if c == 'N':
            return None
        if c == 'T':
            return True
        if c == 'F':
            return False
        if c == 'S':
            return StopIteration
        if c == '.':
            return Ellipsis
        if c in '0123456789':
            return int(c)
        if c == 'i':
            return self.r_long()
        if c == 'I':
            return self.r_long()
        if c == 'l':
            n = self.r_long()
            sign = 1
            if n < 0:
                sign, n = -1, -n
            v = 0
            for k in range(n):
                v |= self.r_byte() << (15 * k)
            return sign * v
        if c == 'g':
            return self.r_double()
        if c == 'y':
            return complex(self.r_double(), self.r_double())
        if c in ('s', 'u', 'a', 'A', 't'):
            raw = self.r_bytes()
            if c == 's':
                return raw
            try:
                return raw.decode('utf-8')
            except UnicodeDecodeError:
                return raw.decode('latin-1')
        if c in ('z', 'Z'):
            n = self.r_byte()
            s = self.d[self.p:self.p + n].decode('latin1')
            self.p += n
            return s
        if c == 'c':
            return self.r_code()
        if c == 'r':
            return self.refs[self.r_long()]
        if c == 'R':
            return self.refs[self.r_long()]
        if c == '(':
            n = self.r_long()
            return tuple(self.r_object(depth + 1) for _ in range(n))
        if c == ')':
            n = self.r_byte()
            return tuple(self.r_object(depth + 1) for _ in range(n))
        if c == '[':
            n = self.r_long()
            return [self.r_object(depth + 1) for _ in range(n)]
        if c == '{':
            n = self.r_long()
            return {self.r_object(depth + 1): self.r_object(depth + 1) for _ in range(n)}
        if c in '<>':
            n = self.r_long()
            return frozenset(self.r_object(depth + 1) for _ in range(n))
        raise ValueError(f'未知类型 {c!r} @{self.where()}')

    def r_code(self):
        a = [self.r_long() for _ in range(6)]
        rec = Code(argcount=a[0], posonly=a[1], kwonly=a[2], nlocals=a[3],
                   stacksize=a[4], flags=a[5])
        rec.co_code = self.r_object(1)
        rec.consts = self.r_object(1)
        rec.names = self.r_object(1)
        rec.varnames = self.r_object(1)
        rec.freevars = self.r_object(1)
        rec.cellvars = self.r_object(1)
        rec.filename = self.r_object(1)
        rec.name = self.r_object(1)
        rec.firstlineno = self.r_long()
        rec.lnotab = self.r_object(1)
        return rec


def load(path):
    d = open(path, 'rb').read()
    for off in range(0, 40):
        r = Reader(d[off:], off)
        try:
            o = r.r_object()
        except Exception:
            continue
        if isinstance(o, Code):
            return o, off, len(d)
    raise SystemExit('解析失败')


def walk(rec, f, depth=0, path='<module>'):
    pad = '  ' * depth
    f.write(f'{pad}CODE {path} argcount={rec.argcount} nlocals={rec.nlocals} '
            f'flags={rec.flags:#x} co_code={len(rec.co_code)}\n')
    f.write(f'{pad}  names={list(rec.names)}\n')
    f.write(f'{pad}  varnames={list(rec.varnames)}\n')
    for i, c in enumerate(rec.consts):
        if isinstance(c, Code):
            walk(c, f, depth + 1, f'{path}.{c.name}')
        else:
            f.write(f'{pad}  consts[{i}] = {c!r}\n')


def dis9(rec, f, depth=0, path='<module>'):
    pad = '  ' * depth
    f.write(f'{pad}=== {path} (argcount={rec.argcount}, co_code={len(rec.co_code)}B)\n')
    co = rec.co_code
    i = 0
    while i < len(co):
        op = co[i]
        name = dis.opname[op]
        if op >= dis.HAVE_ARGUMENT:
            arg = co[i + 1] | (co[i + 2] << 8)
            extra = ''
            if op in dis.hasconst and arg < len(rec.consts):
                c = rec.consts[arg]
                extra = f'  # const[{arg}]={c!r}' if not isinstance(c, Code) else f'  # const[{arg}]={c!r}'
            elif op in dis.hasname and arg < len(rec.names):
                extra = f'  # name[{arg}]={rec.names[arg]!r}'
            elif op in dis.haslocal and arg < len(rec.varnames):
                extra = f'  # var[{arg}]={rec.varnames[arg]!r}'
            elif op in dis.hasfree:
                extra = f'  # free/cell[{arg}]'
            f.write(f'{pad}{i:4d} {name:<24} {arg:5d}{extra}\n')
            i += 2
        else:
            f.write(f'{pad}{i:4d} {name}\n')
            i += 1
    for c in rec.consts:
        if isinstance(c, Code):
            dis9(c, f, depth + 1, f'{path}.{c.name}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    mode = sys.argv[1]
    if mode == 'dump':
        rec, off, ln = load(sys.argv[2])
        with io.open(sys.argv[3], 'w', encoding='utf-8') as f:
            f.write(f'src={sys.argv[2]} len={ln} code_off={off}\n')
            walk(rec, f)
        print('wrote', sys.argv[3])
    else:
        rec, off, ln = load(sys.argv[2])
        want = sys.argv[3] if len(sys.argv) > 3 else None
        with io.open(sys.argv[2] + '.dis.txt', 'w', encoding='utf-8') as f:
            if want:
                found = []

                def find(r):
                    if r.name == want:
                        found.append(r)
                    for c in r.consts:
                        if isinstance(c, Code):
                            find(c)
                find(rec)
                for r in found:
                    dis9(r, f)
            else:
                dis9(rec, f)
        print('wrote', sys.argv[2] + '.dis.txt')
