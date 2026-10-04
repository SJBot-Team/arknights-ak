"""Control-flow graph analysis for a single method.

Reconstructs basic blocks, edges, loops and dominator / post-dominator
relations from the disassembly listing of one method, so the model does not
have to rebuild control flow (and judge where branches reconverge) by hand.

The headline output is the *always-executed* set: blocks that post-dominate the
entry, i.e. code that runs on every path to exit. That distinguishes a loop's
entry pre-test (which only gates the loop body) from an `if` that guards later
statements -- the structural mistake this module exists to prevent.

Primary input is the same IsilDump assembly listing that `re_find_asm` shows
(`\t0xADDR <mnem> <ops>`, branch targets as `#0x...`), so the CFG annotates
exactly what the model reads. When that listing is unavailable it falls back to
a capstone disassembly of the method's byte range.

Architecture-agnostic: the mnemonic classifier covers both ARM32/Thumb
(`beq`, `bne`, `bx lr`, `pop {..,pc}`) and ARM64 (`b.eq`, `cbz`, `ret`, `br`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .indices import first_index_match, format_rva, normalize_rva, resolve_version
from .reports import _asm_file_path, _extract_method_code

# Condition-code suffixes shared by ARM32 (`blt`) and ARM64 (`b.lt`).
_COND = {
    "eq", "ne", "cs", "hs", "cc", "lo", "mi", "pl",
    "vs", "vc", "hi", "ls", "ge", "lt", "gt", "le",
}

_LINE_RE = re.compile(r"^\s*0x([0-9A-Fa-f]+)\s+([A-Za-z][\w.]*)\s*(.*?)\s*$")
_HEX_RE = re.compile(r"#?0x([0-9A-Fa-f]+)")


@dataclass(frozen=True)
class Insn:
    addr: int
    mnem: str
    ops: str
    kind: str          # call | ret | ubranch | cbranch | ibranch | other
    target: int | None  # resolved branch target for {u,c}branch, else None


@dataclass
class Block:
    idx: int
    start: int
    end: int                       # address of the last instruction
    insns: list[Insn]
    succs: list[int] = field(default_factory=list)   # block ids; EXIT = sentinel
    preds: list[int] = field(default_factory=list)
    is_loop_header: bool = False
    always: bool = False
    cold: bool = False     # not reachable from entry (handler / padding tail)

    @property
    def term(self) -> Insn:
        return self.insns[-1]


# ── Mnemonic classification ──────────────────────────────────────────────────

def _classify(mnem: str, ops: str) -> str:
    m = mnem.lower()
    parts = m.split(".")
    head = parts[0]
    suffix = parts[1] if len(parts) > 1 else ""
    low_ops = ops.lower()

    if head in {"bl", "blx", "blr"}:
        return "call"
    if m == "ret":
        return "ret"
    if head == "bx":
        return "ret" if low_ops.strip() == "lr" else "ibranch"
    if head == "pop" and re.search(r"\bpc\b", low_ops):
        return "ret"
    if head == "mov" and low_ops.startswith("pc,"):
        return "ret" if "lr" in low_ops else "ibranch"
    if head == "ldr" and low_ops.startswith("pc"):
        return "ibranch"
    if head in {"tbb", "tbh", "br"}:
        return "ibranch"
    if head in {"cbz", "cbnz", "tbz", "tbnz"}:
        return "cbranch"
    if head == "b":
        # `b` / `b.w` / `b.n` are unconditional; `b.eq` (ARM64) is conditional.
        if suffix in {"", "w", "n"}:
            return "ubranch"
        if suffix in _COND:
            return "cbranch"
        return "ubranch"
    if head[:1] == "b" and head[1:] in _COND:   # ARM32 beq/bne/blt/...
        return "cbranch"
    return "other"


def _branch_target(ops: str) -> int | None:
    m = _HEX_RE.search(ops)
    return int(m.group(1), 16) if m else None


# ── Listing / fallback parsing ───────────────────────────────────────────────

def _method_block(rva: str, version: str) -> tuple[str | None, str | None]:
    """Return (disassembly_block_text, method_name) for the method at rva."""
    vd = resolve_version(version or None)
    key = normalize_rva(rva)
    asm_key, asm_entry = first_index_match(vd.asm_index, key)
    if not asm_entry:
        return None, None
    file_path = _asm_file_path(asm_entry["file"], vd)
    block = _extract_method_code(file_path, asm_key)
    if not block:
        return None, None
    name = f"{asm_entry['type']}.{asm_entry['method']}"
    return block, name


def _parse_listing(block: str) -> list[Insn]:
    insns: list[Insn] = []
    started = False
    for line in block.splitlines():
        if not started:
            if line.strip().startswith("Disassembly:"):
                started = True
            continue
        m = _LINE_RE.match(line)
        if not m:
            # tolerate blank lines inside the block; stop only at a real
            # non-instruction section (e.g. an "ISIL:" trailer).
            if line.strip() and not line.lstrip().startswith("0x"):
                break
            continue
        addr = int(m.group(1), 16)
        mnem, ops = m.group(2), m.group(3)
        kind = _classify(mnem, ops)
        target = _branch_target(ops) if kind in {"ubranch", "cbranch"} else None
        insns.append(Insn(addr, mnem, ops, kind, target))
    return insns


def _fallback_insns(rva: str, version: str) -> list[Insn]:
    """Disassemble the method's byte range via capstone when no listing exists."""
    try:
        from .binary import find_libil2cpp
        from .disasm import disassemble
        from .image import read_rva_bytes
    except Exception:
        return []
    target = int(normalize_rva(rva), 16)
    try:
        binary = find_libil2cpp().path
    except Exception:
        return []
    end = _next_method_rva(version, target)
    span = min(end - target, 0x2000) if end and end > target else 0x400
    try:
        _, code = read_rva_bytes(binary, target & ~1, span)
        decoded, _arch = disassemble(code, target, binary, None)
    except Exception:
        return []
    insns: list[Insn] = []
    for ins in decoded:
        kind = _classify(ins.mnemonic, ins.op_str)
        tgt = None
        if kind in {"ubranch", "cbranch"} and ins.operands:
            last = ins.operands[-1]
            tgt = last.imm if getattr(last, "kind", "") == "imm" else _branch_target(ins.op_str)
        insns.append(Insn(ins.address, ins.mnemonic, ins.op_str, kind, tgt))
    return insns


def _next_method_rva(version: str, target: int) -> int | None:
    vd = resolve_version(version or None)
    best: int | None = None
    for key in vd.asm_index:
        try:
            val = int(key, 16)
        except ValueError:
            continue
        if val > target and (best is None or val < best):
            best = val
    return best


# ── Block / edge construction ────────────────────────────────────────────────

_TERMINATORS = {"ret", "ubranch", "cbranch", "ibranch"}
EXIT = -1


def _build_blocks(insns: list[Insn]) -> list[Block]:
    if not insns:
        return []
    addrs = [i.addr for i in insns]
    addr_set = set(addrs)
    lo, hi = addrs[0], addrs[-1]

    # Leaders: entry, every branch target inside the method, and the
    # instruction right after any terminator.
    leaders = {insns[0].addr}
    for idx, ins in enumerate(insns):
        if ins.kind in {"ubranch", "cbranch"} and ins.target in addr_set:
            leaders.add(ins.target)
        if ins.kind in _TERMINATORS and idx + 1 < len(insns):
            leaders.add(insns[idx + 1].addr)

    blocks: list[Block] = []
    cur: list[Insn] = []
    for ins in insns:
        if ins.addr in leaders and cur:
            blocks.append(Block(len(blocks), cur[0].addr, cur[-1].addr, cur))
            cur = []
        cur.append(ins)
    if cur:
        blocks.append(Block(len(blocks), cur[0].addr, cur[-1].addr, cur))

    by_start = {b.start: b.idx for b in blocks}
    n = len(blocks)
    for i, b in enumerate(blocks):
        t = b.term
        if t.kind == "ret":
            b.succs = [EXIT]
        elif t.kind == "ibranch":
            b.succs = [EXIT]
        elif t.kind == "ubranch":
            if t.target in by_start:
                b.succs = [by_start[t.target]]
            else:
                b.succs = [EXIT]            # tail call / out-of-method jump
        elif t.kind == "cbranch":
            taken = by_start.get(t.target, EXIT)
            fall = i + 1 if i + 1 < n else EXIT
            b.succs = [taken, fall]
        else:
            b.succs = [i + 1] if i + 1 < n else [EXIT]

    for b in blocks:
        for s in b.succs:
            if 0 <= s < n:
                blocks[s].preds.append(b.idx)
    return blocks


# ── Dominators / post-dominators ─────────────────────────────────────────────

def _dominators(n: int, succs: list[list[int]], entry: int) -> list[set[int]]:
    preds: list[list[int]] = [[] for _ in range(n)]
    for u in range(n):
        for v in succs[u]:
            if 0 <= v < n:
                preds[v].append(u)
    alln = set(range(n))
    dom = [set(alln) for _ in range(n)]
    dom[entry] = {entry}
    changed = True
    while changed:
        changed = False
        for nd in range(n):
            if nd == entry:
                continue
            inter: set[int] | None = None
            for p in preds[nd]:
                inter = set(dom[p]) if inter is None else (inter & dom[p])
            new = {nd} | (inter or set())
            if new != dom[nd]:
                dom[nd] = new
                changed = True
    return dom


def _post_dominators(blocks: list[Block]) -> list[set[int]]:
    """Post-dominators over blocks; EXIT is a virtual sink node id == n."""
    n = len(blocks)
    exit_id = n
    # Reverse-CFG successors: for edge u->v add v->u; exit-bound edges go via exit_id.
    rsucc: list[list[int]] = [[] for _ in range(n + 1)]
    for b in blocks:
        for s in b.succs:
            v = exit_id if s == EXIT else s
            rsucc[v].append(b.idx)
    dom = _dominators(n + 1, rsucc, exit_id)
    return dom  # dom[b] = set of nodes that post-dominate b (may include exit_id)


def _ipostdom(pdom: list[set[int]], node: int, exit_id: int) -> int | None:
    strict = pdom[node] - {node}
    if not strict:
        return None
    want = strict
    for c in strict:
        if pdom[c] == want:
            return c
    # Fallback: closest = largest post-dom set among strict post-dominators.
    return max(strict, key=lambda c: len(pdom[c]))


# ── Loops ────────────────────────────────────────────────────────────────────

def _natural_loop(header: int, tail: int, blocks: list[Block]) -> set[int]:
    body = {header}
    stack = []
    if tail != header:
        body.add(tail)
        stack.append(tail)
    while stack:
        x = stack.pop()
        for p in blocks[x].preds:
            if p not in body:
                body.add(p)
                stack.append(p)
    return body


def _find_loops(blocks: list[Block], dom: list[set[int]]):
    loops = []
    for b in blocks:
        for s in b.succs:
            if 0 <= s < len(blocks) and s in dom[b.idx]:   # back-edge: s dominates b
                body = _natural_loop(s, b.idx, blocks)
                blocks[s].is_loop_header = True
                loops.append({"header": s, "tail": b.idx, "body": body})
    return loops


# ── Report ───────────────────────────────────────────────────────────────────

def _flags(b: Block) -> str:
    f = []
    if b.idx == 0:
        f.append("ENTRY")
    if b.is_loop_header:
        f.append("LOOP HEADER")
    if b.always:
        f.append("ALWAYS")
    if b.term.kind == "ret":
        f.append("RETURN")
    if b.term.kind == "ibranch":
        f.append("INDIRECT")
    if b.cold:
        f.append("COLD")
    return ("  [" + ", ".join(f) + "]") if f else ""


def _reachable_from_entry(blocks: list[Block]) -> set[int]:
    n = len(blocks)
    seen = {0}
    stack = [0]
    while stack:
        x = stack.pop()
        for s in blocks[x].succs:
            if 0 <= s < n and s not in seen:
                seen.add(s)
                stack.append(s)
    return seen


def _succ_str(b: Block, blocks: list[Block]) -> str:
    n = len(blocks)
    labels = []
    if b.term.kind == "cbranch":
        taken, fall = b.succs[0], b.succs[1]
        labels.append(f"B{taken}(taken)" if 0 <= taken < n else "exit(taken)")
        labels.append(f"B{fall}(fall)" if 0 <= fall < n else "exit(fall)")
    else:
        for s in b.succs:
            labels.append(f"B{s}" if 0 <= s < n else "exit")
    return ", ".join(labels)


def _analyze(rva: str, version: str):
    block_text, name = _method_block(rva, version)
    insns = _parse_listing(block_text) if block_text else []
    source = "IsilDump listing"
    if len(insns) < 2:
        insns = _fallback_insns(rva, version)
        source = "capstone fallback"
    blocks = _build_blocks(insns)
    return blocks, name, source


def build_cfg_report(rva: str, version: str = "") -> str:
    blocks, name, source = _analyze(rva, version)
    if not blocks:
        return (
            f"No disassembly for {format_rva(rva)}. Resolve the method with "
            f"re_search/re_lookup, or view raw bytes with re_disasm."
        )
    n = len(blocks)
    succs = [b.succs for b in blocks]
    dom = _dominators(n, succs, 0)
    pdom = _post_dominators(blocks)
    exit_id = n
    loops = _find_loops(blocks, dom)

    # Always-executed = blocks that post-dominate the entry (on every path).
    always_ids = {b for b in pdom[0] if b != exit_id}
    reachable = _reachable_from_entry(blocks)
    for b in blocks:
        b.always = b.idx in always_ids
        b.cold = b.idx not in reachable

    unresolved = any(b.term.kind == "ibranch" for b in blocks)
    n_cold = sum(1 for b in blocks if b.cold)
    edges = sum(len(b.succs) for b in blocks)

    out = [
        f"CFG: {name or format_rva(rva)} @{format_rva(rva)}",
        f"source: {source}   blocks: {n}   edges: {edges}   loops: {len(loops)}"
        + (f"   cold: {n_cold}" if n_cold else "")
        + ("   (INCOMPLETE: indirect/computed branch present)" if unresolved else ""),
        "",
        "Blocks:",
    ]
    for b in blocks:
        t = b.term
        if t.kind in {"ubranch", "cbranch", "ibranch"}:
            term = f"{t.mnem} {t.ops}".strip()
        elif t.kind == "ret":
            term = f"{t.mnem} {t.ops}".strip() + " (return)"
        else:
            term = "fallthrough"
        out.append(
            f"  B{b.idx}  {format_rva(hex(b.start))}..{format_rva(hex(b.end))}"
            f"  term: {term}  ->  {_succ_str(b, blocks)}{_flags(b)}"
        )

    if loops:
        out += ["", "Loops:"]
        for lp in loops:
            body = sorted(lp["body"])
            hdr = blocks[lp["header"]]
            tail = blocks[lp["tail"]]
            out.append(
                f"  header B{lp['header']} ({format_rva(hex(hdr.start))})"
                f"  body {{{', '.join('B%d' % i for i in body)}}}"
                f"  back-edge from {format_rva(hex(tail.end))}"
            )

    # Always-executed summary -- the key fact against guard over-scoping.
    always_blocks = [b for b in blocks if b.always]
    out += ["", "Always-executed (post-dominate entry -- run on EVERY path):"]
    out.append(
        "  " + ", ".join(
            f"B{b.idx} {format_rva(hex(b.start))}..{format_rva(hex(b.end))}"
            for b in always_blocks
        )
    )
    out.append(
        "  -> code in these blocks is NOT inside any branch's guard; "
        "do not wrap it in an `if`."
    )

    # Per-conditional-branch reconvergence + guarded region (live blocks only).
    cond_blocks = [b for b in blocks if b.term.kind == "cbranch" and not b.cold]
    if cond_blocks:
        ipd = [_ipostdom(pdom, i, exit_id) for i in range(n)]
        out += ["", "Conditional branches (where paths rejoin / what is guarded):"]
        for b in cond_blocks:
            rejoin = ipd[b.idx]
            guarded = _control_dependent(b.idx, blocks, ipd, exit_id)
            rejoin_s = (
                format_rva(hex(blocks[rejoin].start)) if rejoin is not None and rejoin != exit_id
                else "exit"
            )
            back = "  (loop back-edge)" if b.is_loop_header or any(
                0 <= s < n and s in dom[b.idx] for s in b.succs
            ) else ""
            g = ", ".join(f"B{i}" for i in sorted(guarded)) or "(none)"
            out.append(
                f"  branch@{format_rva(hex(b.term.addr))} ({b.term.mnem})"
                f" reconverges at {rejoin_s}; guards only {{{g}}}{back}"
            )

    return "\n".join(out)


def _control_dependent(branch: int, blocks: list[Block], ipd, exit_id: int) -> set[int]:
    """Blocks control-dependent on `branch`: reachable from a successor, walked
    up the post-dom tree until the branch's own reconvergence point."""
    stop = ipd[branch]
    out: set[int] = set()
    n = len(blocks)
    for s in blocks[branch].succs:
        if not (0 <= s < n) or s == stop:
            continue
        x = s
        while x is not None and 0 <= x < n and x != stop and x != branch:
            out.add(x)
            x = ipd[x]
    return out


def branch_summary(rva: str, version: str = "") -> tuple[int, int]:
    """(#branches, #loops) for the method -- cheap footer hint for re_find_asm."""
    blocks, _name, _src = _analyze(rva, version)
    if not blocks:
        return (0, 0)
    n = len(blocks)
    branches = sum(1 for b in blocks if b.term.kind in {"ubranch", "cbranch"})
    dom = _dominators(n, [b.succs for b in blocks], 0)
    loops = sum(
        1 for b in blocks for s in b.succs
        if 0 <= s < n and s in dom[b.idx]
    )
    return (branches, loops)
