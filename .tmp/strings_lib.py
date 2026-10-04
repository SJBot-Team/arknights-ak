# -*- coding: utf-8 -*-
"""Minimal strings extractor: ASCII + UTF-16LE printable runs."""
import re

def strings_from_bytes(data, minlen=5):
    asc = re.findall(rb'[\x20-\x7e]{%d,}' % minlen, data)
    u16 = re.findall((rb'(?:[\x20-\x7e]\x00){%d,}' % minlen), data)
    out = [a.decode('ascii', 'replace') for a in asc]
    out += [a.decode('utf-16-le', 'replace') for a in u16]
    return out

def strings_from_file(path, minlen=5, limit=None):
    with open(path, 'rb') as f:
        data = f.read()
    s = strings_from_bytes(data, minlen)
    return s[:limit] if limit else s

def grep(strings, patterns, ignorecase=True, maxhits=400):
    flags = re.IGNORECASE if ignorecase else 0
    rx = re.compile('|'.join(patterns), flags)
    hits = []
    seen = set()
    for s in strings:
        if rx.search(s):
            k = s.strip()
            if k in seen: continue
            seen.add(k)
            hits.append(k)
            if len(hits) >= maxhits: break
    return hits
