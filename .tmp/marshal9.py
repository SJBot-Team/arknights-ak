# -*- coding: utf-8 -*-
"""Minimal marshal reader for Python 3.9 .pyc files (runs on any Python 3).

Does not build real code objects (3.13 refuses 3.9 layout); instead returns
CodeRec placeholders holding argcount/flags/co_code/co_consts/co_names/... so we
can dump constants and names of every function in the packaged bytecode.
"""
import struct, sys, io

class CodeRec:
    def __init__(self, **kw):
        self.__dict__.update(kw)
    def __repr__(self):
        return f"<code {self.name} consts={len(self.consts)} names={len(self.names)}>"

class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0
        self.refs = []

    def r_byte(self):
        b = self.d[self.p]; self.p += 1; return b

    def r_long(self):
        v = struct.unpack('<i', self.d[self.p:self.p + 4])[0]; self.p += 4; return v

    def r_long64(self):
        v = struct.unpack('<q', self.d[self.p:self.p + 8])[0]; self.p += 8; return v

    def r_double(self):
        v = struct.unpack('<d', self.d[self.p:self.p + 8])[0]; self.p += 8; return v

    def r_bytes(self):
        n = self.r_long()
        b = self.d[self.p:self.p + n]; self.p += n; return b

    def r_str(self):
        return self.r_bytes().decode('utf-8', 'replace')

    def r_object(self):
        code = self.r_byte()
        flag = bool(code & 0x80)
        c = chr(code & 0x7f)
        idx = None
        if flag:
            # CPython reserves the ref slot BEFORE parsing contents (supports cycles)
            idx = len(self.refs)
            self.refs.append(None)
        obj = self._r_object_impl(c)
        if flag:
            self.refs[idx] = obj
        return obj

    def _r_object_impl(self, c):
        if c == 'N': return None
        if c == 'T': return True
        if c == 'F': return False
        if c == 'S': return StopIteration
        if c == '.': return Ellipsis
        if c in '0123456789':
            # could be a small int OR a flag byte for refs
            return code - 48
        if c == 'i': return self.r_long()
        if c == 'I': return self.r_long()          # rarely used
        if c == 'l':
            n = self.r_long(); sign = 1
            if n < 0: sign, n = -1, -n
            v = 0
            for i in range(n):
                v |= self.r_byte() << (15 * i)
            return sign * v
        if c == 'g': return self.r_double()
        if c == 'y': return complex(self.r_double(), self.r_double())
        if c in ('s', 'u', 'a', 'A', 'z', 'Z'):
            if c in ('z', 'Z'):  # old short ascii
                n = self.r_byte()
                s = self.d[self.p:self.p + n].decode('latin1')
                self.p += n
                return s
            s = self.r_str()
            if c == 's': return s.encode('utf-8')
            return s
        if c == 'c': return self.r_code()
        if c == 'r':
            idx = self.r_long(); return self.refs[idx]
        if c == 'R':
            idx = self.r_long()
            return self.refs[idx]
        if c == '(':
            n = self.r_long(); return tuple(self.r_object() for _ in range(n))
        if c == ')':
            n = self.r_byte(); return tuple(self.r_object() for _ in range(n))
        if c == '+':
            return self.refs[self.r_long()]
        if c == 't':
            return self.r_str()
        if c == '[':
            n = self.r_long(); return [self.r_object() for _ in range(n)]
        if c == '{':
            n = self.r_long(); return {self.r_object(): self.r_object() for _ in range(n)}
        if c == '<':
            n = self.r_long(); return frozenset(self.r_object() for _ in range(n))
        if c == '>':
            n = self.r_long(); return frozenset(self.r_object() for _ in range(n))
        raise ValueError(f'unknown type code {c!r} at {self.p - 1}')

    def r_code(self):
        argcount = self.r_long()
        posonly = self.r_long()
        kwonly = self.r_long()
        nlocals = self.r_long()
        stacksize = self.r_long()
        flags = self.r_long()
        code = self.r_object()
        consts = self.r_object()
        names = self.r_object()
        varnames = self.r_object()
        freevars = self.r_object()
        cellvars = self.r_object()
        filename = self.r_object()
        name = self.r_object()
        firstlineno = self.r_long()
        lnotab = self.r_object()
        rec = CodeRec(argcount=argcount, posonly=posonly, kwonly=kwonly, nlocals=nlocals,
                      stacksize=stacksize, flags=flags, co_code=code, consts=consts, names=names,
                      varnames=varnames, freevars=freevars, cellvars=cellvars,
                      filename=filename, name=name, firstlineno=firstlineno, lnotab=lnotab)
        self.refs.append(rec)
        return rec

def load_pyc(path):
    data = open(path, 'rb').read()
    magic = data[:4]
    # 3.7+ header: magic(4) + bitfield(4); 3.6-: magic(4)+mtime(4)+size(4)
    return magic, Reader(data[12:]).r_object()

def walk(rec, depth=0, out=None, path='<module>'):
    out.write('  ' * depth + f'CODE {path} argcount={rec.argcount} flags={rec.flags:#x} names={list(rec.names)}\n')
    for c in rec.consts:
        if isinstance(c, CodeRec):
            walk(c, depth + 1, out, f'{path}.{c.name}')
        else:
            out.write('  ' * (depth + 1) + f'const {c!r}\n')

if __name__ == '__main__':
    magic, rec = load_pyc(sys.argv[1])
    dst = sys.argv[2]
    with io.open(dst, 'w', encoding='utf-8') as f:
        f.write(f'magic={magic.hex()} top={rec!r}\n')
        walk(rec, 0, f)
    print('wrote', dst)
