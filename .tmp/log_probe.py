# -*- coding: utf-8 -*-
import io, sys, collections, re

p = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 50
f = open(p, 'rb')
head = f.read(400000).decode('utf-8', 'replace')
print("=== FIRST %d LINES of %s ===" % (n, p))
for i, ln in enumerate(head.splitlines()[:n], 1):
    print("%4d| %s" % (i, ln))

# line length / format stats over full file (tail-bounded read)
import os
size = os.path.getsize(p)
f.seek(max(0, size - 8_000_000))
tail = f.read().decode('utf-8', 'replace')
lines = tail.splitlines()
print("\n=== sampled lines: %d (from last 8MB of %d bytes) ===" % (len(lines), size))
pat = collections.Counter()
for ln in lines[:200000]:
    m = re.match(r'^\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\](.*)$', ln)
    if m:
        pat['[ts][level][module]msg'] += 1
    else:
        pat['other'] += 1
print(dict(pat))

# find lines with TaskChain / TaskName keywords
kws = ['TaskChainStart', 'TaskChainCompleted', 'TaskChainError', 'SubTaskExtraInfo',
       'SubTaskStart', 'SubTaskCompleted', 'TaskChainExtraInfo', 'AllTasksCompleted',
       'TaskName', 'recognition', 'coordinates', 'cost']
found = {k: [] for k in kws}
for ln in reversed(lines):
    for k in kws:
        if k in ln and len(found[k]) < 3:
            found[k].append(ln)
print("\n=== KEYWORD SAMPLES (last occurrences, chronological) ===")
for k in kws:
    print("\n--- %s (%d samples) ---" % (k, len(found[k])))
    for ln in reversed(found[k]):
        print(ln[:600])
