"""Architecture-adaptive Capstone disassembly and field semantics analysis.

Based on match3-core-sketch's capstone_backend.py methodology.

The instruction architecture comes from the binary image itself (ELF or Mach-O):
- AArch64 (ARM64)  -> CS_ARCH_ARM64
- ARM     (32-bit) -> CS_ARCH_ARM, with ARM/Thumb mode chosen by a best-coverage
                      heuristic (Unity Android ARM32 builds are usually Thumb-2).

Provides:
- Architecture-adaptive instruction disassembly with Capstone
- Field load/store tracking against C# type layouts (ARM64-tuned; ARM32 is
  best-effort -- verify against the ISIL dump)
- Inferred conditions, mutations, and branch gates
- Evidence packets for LLM-based C# reconstruction

NOTE: the structured-operand and field-semantics layer below was tuned for
ARM64 register/encoding conventions. On ARM32/Thumb the raw mnemonics are
correct, but field/condition/mutation inference should be treated as a hint and
cross-checked against the ISIL dump (`find-asm`).
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass

from .binary import find_libil2cpp
from .config import DEFAULT_VERSION
from .image import (
    ARCH_ARM32,
    ARCH_ARM64,
    RegionMapping,
    format_mapping,
    image_arch,
    map_rva_to_file_offset,
    read_rva_bytes,
)

try:
    from capstone import (
        Cs,
        CS_ARCH_ARM,
        CS_ARCH_ARM64,
        CS_MODE_ARM,
        CS_MODE_THUMB,
    )
    from capstone import arm as _cs_arm
    from capstone import arm64 as _cs_arm64
    HAS_CAPSTONE = True
except ImportError:
    HAS_CAPSTONE = False

# Architecture now comes from the image layer, which reads it out of the ELF
# header or the Mach-O cputype -- disasm no longer reaches across that seam to
# parse binary headers itself.


# ── Data types ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Arm64MemOperand:
    base: str
    index: str
    disp: int


@dataclass(frozen=True)
class Arm64Operand:
    kind: str  # reg | imm | mem | other
    reg: str = ""
    imm: int | None = None
    mem: Arm64MemOperand | None = None


@dataclass(frozen=True)
class Arm64Instruction:
    address: int
    data: bytes
    mnemonic: str
    op_str: str
    operands: tuple[Arm64Operand, ...]


@dataclass(frozen=True)
class FieldInfo:
    """A field from C# metadata with its offset."""
    owner: str
    name: str
    type_name: str
    offset: int


@dataclass(frozen=True)
class FieldAccess:
    instruction: Arm64Instruction
    field: FieldInfo
    direction: str  # read | write
    base_reg: str
    value_reg: str


@dataclass(frozen=True)
class InferredCondition:
    instruction: Arm64Instruction
    field: FieldInfo
    relation: str
    rhs: str
    dest_reg: str


@dataclass(frozen=True)
class InferredMutation:
    instruction: Arm64Instruction
    field: FieldInfo
    operator: str
    amount: int


@dataclass(frozen=True)
class InferredBranchGate:
    instruction: Arm64Instruction
    expression: str
    condition: str
    target: int
    effect: str


@dataclass(frozen=True)
class DirectTarget:
    instruction: Arm64Instruction
    mnemonic: str
    target: int
    scope: str  # local | external
    hint: str


@dataclass(frozen=True)
class Arm64MethodAnalysis:
    rva: int
    arch: str  # arm64 | arm32 | thumb
    byte_count: int
    byte_source: str
    binary_path: str
    binary_source: str
    mapping: RegionMapping
    type_name: str
    method_signature: str
    field_map: dict[int, FieldInfo]
    instructions: list[Arm64Instruction]
    accesses: list[FieldAccess]
    conditions: list[InferredCondition]
    mutations: list[InferredMutation]
    branch_gates: list[InferredBranchGate]
    direct_targets: list[DirectTarget]
    notes: dict[int, list[str]]


# ── Capstone Disassembly ───────────────────────────────────────────────────

def _operand_from_capstone(insn, op, op_reg: int, op_imm: int, op_mem: int) -> Arm64Operand:
    """Decode one Capstone operand using the active arch's operand-type constants."""
    if op.type == op_reg:
        return Arm64Operand(kind="reg", reg=insn.reg_name(op.reg) or "")
    if op.type == op_imm:
        return Arm64Operand(kind="imm", imm=int(op.imm))
    if op.type == op_mem:
        index = insn.reg_name(op.mem.index) if op.mem.index else ""
        base = insn.reg_name(op.mem.base) if op.mem.base else ""
        return Arm64Operand(
            kind="mem",
            mem=Arm64MemOperand(
                base=base or "",
                index=index or "",
                disp=int(op.mem.disp),
            ),
        )
    return Arm64Operand(kind="other")


def _decode(md, code: bytes, rva: int, op_reg: int, op_imm: int, op_mem: int) -> list[Arm64Instruction]:
    md.detail = True
    return [
        Arm64Instruction(
            address=insn.address,
            data=bytes(insn.bytes),
            mnemonic=insn.mnemonic,
            op_str=insn.op_str,
            operands=tuple(_operand_from_capstone(insn, op, op_reg, op_imm, op_mem) for op in insn.operands),
        )
        for insn in md.disasm(code, rva)
    ]


# Common integer/control mnemonics seen in normal compiled ARM/Thumb code.
# Used to score a candidate decode (a wrong mode produces fewer of these and
# more spurious NEON/branch noise).
_COMMON_MNEMONICS = frozenset({
    "push", "pop", "mov", "movs", "movw", "movt", "mvn", "ldr", "ldrb", "ldrh",
    "ldrsb", "ldrsh", "str", "strb", "strh", "ldrd", "strd", "ldm", "stm",
    "add", "adds", "addw", "sub", "subs", "subw", "rsb", "adc", "sbc", "mul",
    "mla", "cmp", "cmn", "tst", "teq", "and", "orr", "orn", "eor", "bic",
    "lsl", "lsr", "asr", "ror", "rrx", "b", "bl", "bx", "blx", "beq", "bne",
    "bgt", "blt", "bge", "ble", "bhi", "bls", "bcc", "bcs", "bmi", "bpl",
    "cbz", "cbnz", "nop", "it", "ite", "itt", "itttt", "uxtb", "uxth", "sxtb",
    "sxth", "uxtab", "adr", "vldr", "vstr", "vmov", "vpush", "vpop", "dmb",
    "ubfx", "sbfx", "bfi", "clz", "rev", "mrc", "mcr",
})


def _coverage(insns: list[Arm64Instruction]) -> int:
    return sum(len(i.data) for i in insns)


def _arm_quality(insns: list[Arm64Instruction], total_bytes: int) -> float:
    """Heuristic quality of an ARM/Thumb decode. Higher is more plausible.

    Combines byte coverage with the share of common integer/control opcodes,
    penalising spurious NEON ops and runs of unconditional branches that a
    wrong-mode decode tends to manufacture. Used only to disambiguate ARM vs
    Thumb at even addresses; an odd RVA is unambiguous (Thumb).
    """
    if not insns or total_bytes <= 0:
        return -1.0
    n = len(insns)
    cov = _coverage(insns) / total_bytes
    base = lambda m: m.split(".")[0]
    common = sum(1 for i in insns if base(i.mnemonic) in _COMMON_MNEMONICS)
    neon = sum(1 for i in insns if i.mnemonic[:1] == "v" and base(i.mnemonic) not in {"vldr", "vstr", "vmov", "vpush", "vpop"})
    uncond_b = sum(1 for i in insns if i.mnemonic == "b")
    return cov * 2.0 + common / n - (neon / n) * 1.5 - max(0.0, uncond_b / n - 0.15)


def disassemble(
    code: bytes,
    rva: int,
    binary_path: str | None = None,
    force_mode: str | None = None,
) -> tuple[list[Arm64Instruction], str]:
    """Disassemble bytes, auto-selecting architecture from the ELF.

    Returns (instructions, arch_label) where arch_label is one of 'arm64',
    'arm32', or 'thumb'.

    ARM32 mode selection:
    - `force_mode` ('arm' | 'thumb') overrides everything.
    - an odd RVA is authoritative Thumb (bit0 is the interworking mode bit);
      the address is masked to even for decoding.
    - otherwise ARM and Thumb are both decoded and the higher-quality decode
      wins (see `_arm_quality`). This is best-effort -- pass force_mode if the
      result looks wrong.
    """
    if not HAS_CAPSTONE:
        raise RuntimeError("Capstone is required for disassembly. Install with: pip install capstone")

    arch = image_arch(binary_path) if binary_path else ARCH_ARM64

    if arch == ARCH_ARM32:
        reg, imm, mem = _cs_arm.ARM_OP_REG, _cs_arm.ARM_OP_IMM, _cs_arm.ARM_OP_MEM

        def decode(mode: int, at: int) -> list[Arm64Instruction]:
            return _decode(Cs(CS_ARCH_ARM, mode), code, at, reg, imm, mem)

        if force_mode == "thumb":
            return decode(CS_MODE_THUMB, rva & ~1), "thumb"
        if force_mode == "arm":
            return decode(CS_MODE_ARM, rva & ~1), "arm32"
        if rva & 1:
            return decode(CS_MODE_THUMB, rva & ~1), "thumb"
        arm_insns = decode(CS_MODE_ARM, rva)
        thumb_insns = decode(CS_MODE_THUMB, rva)
        if _arm_quality(thumb_insns, len(code)) > _arm_quality(arm_insns, len(code)):
            return thumb_insns, "thumb"
        return arm_insns, "arm32"

    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    reg, imm, mem = _cs_arm64.ARM64_OP_REG, _cs_arm64.ARM64_OP_IMM, _cs_arm64.ARM64_OP_MEM
    return _decode(md, code, rva, reg, imm, mem), "arm64"


def disassemble_arm64(code: bytes, rva: int) -> list[Arm64Instruction]:
    """Disassemble ARM64 bytes (back-compat helper; prefer `disassemble`)."""
    if not HAS_CAPSTONE:
        raise RuntimeError("Capstone is required for disassembly. Install with: pip install capstone")
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    return _decode(md, code, rva, _cs_arm64.ARM64_OP_REG, _cs_arm64.ARM64_OP_IMM, _cs_arm64.ARM64_OP_MEM)


# ── Field Semantics Analysis ────────────────────────────────────────────────

def _normalize_reg(reg: str) -> str:
    reg = reg.lower()
    if m := re.match(r"w(\d+)$", reg):
        return "x" + m.group(1)
    if reg == "wzr":
        return "xzr"
    return reg


def _first_reg(insn: Arm64Instruction) -> str:
    if insn.operands and insn.operands[0].kind == "reg":
        return insn.operands[0].reg
    return ""


def _memory_operand(insn: Arm64Instruction) -> Arm64MemOperand | None:
    for op in insn.operands:
        if op.kind == "mem":
            return op.mem
    return None


def _is_store(insn: Arm64Instruction) -> bool:
    return insn.mnemonic.startswith(("str", "stur", "stp"))


def _is_load(insn: Arm64Instruction) -> bool:
    return insn.mnemonic.startswith(("ldr", "ldur", "ldp"))


def _condition_relation(cond: str) -> str:
    return {
        "eq": "==", "ne": "!=", "lt": "<", "le": "<=",
        "gt": ">", "ge": ">=",
        "lo": "< unsigned", "cc": "< unsigned",
        "ls": "<= unsigned", "hi": "> unsigned",
        "hs": ">= unsigned", "cs": ">= unsigned",
    }.get(cond.lower(), cond)


def analyze_field_accesses(
    instructions: list[Arm64Instruction],
    field_map: dict[int, FieldInfo],
) -> tuple[list[FieldAccess], list[InferredCondition], list[InferredMutation]]:
    """Analyze instructions for field loads/stores, conditions, and mutations.

    Uses the field offset map from C# metadata to identify struct field accesses.
    """
    accesses: list[FieldAccess] = []
    conditions: list[InferredCondition] = []
    mutations: list[InferredMutation] = []

    # Track which registers currently hold a this pointer (x0 or mov'd from x0)
    this_regs: set[str] = set()

    for insn in instructions:
        # Track this-pointer propagation
        mnemonic = insn.mnemonic
        if mnemonic in {"bl", "blr"}:
            this_regs.difference_update(f"x{idx}" for idx in range(0, 19))

        if mnemonic == "mov" and len(insn.operands) >= 2:
            dest = _normalize_reg(insn.operands[0].reg) if insn.operands[0].kind == "reg" else ""
            src = _normalize_reg(insn.operands[1].reg) if insn.operands[1].kind == "reg" else ""
            if dest:
                if src in this_regs:
                    this_regs.add(dest)
                else:
                    this_regs.discard(dest)
            continue

        if mnemonic in {"cmp", "cmn", "tst"} or mnemonic.startswith(("b", "cb", "tb")) or _is_store(insn):
            pass  # don't clobber this_regs for these
        else:
            dest = _normalize_reg(_first_reg(insn))
            if dest:
                this_regs.discard(dest)

        # Check memory operand for field offset match
        mem = _memory_operand(insn)
        if not mem:
            continue

        base = _normalize_reg(mem.base)
        if base not in this_regs and base not in {"x0", "x1", "x2", "x3", "x4"}:
            # Allow x0-x4 as potential this/candidate pointers
            pass

        offset = mem.disp
        if offset >= 0 and offset in field_map:
            field = field_map[offset]
            direction = "write" if _is_store(insn) else "read"
            value_reg = _first_reg(insn) if direction == "write" else ""
            access = FieldAccess(
                instruction=insn,
                field=field,
                direction=direction,
                base_reg=base,
                value_reg=value_reg,
            )
            accesses.append(access)

            # Detect simple mutation patterns: add/sub on loaded value
            if direction == "read":
                next_idx = instructions.index(insn) + 1
                if next_idx < len(instructions):
                    nxt = instructions[next_idx]
                    if nxt.mnemonic in {"add", "sub", "adc", "sbc"} and len(nxt.operands) >= 3:
                        src_reg = _normalize_reg(nxt.operands[1].reg) if nxt.operands[1].kind == "reg" else ""
                        if src_reg == _normalize_reg(value_reg):
                            imm = nxt.operands[2].imm if nxt.operands[2].kind == "imm" else None
                            if imm is not None and imm > 0 and imm <= 0x1000:
                                op = "+=" if nxt.mnemonic == "add" else "-="
                                mutations.append(InferredMutation(
                                    instruction=nxt,
                                    field=field,
                                    operator=op,
                                    amount=imm,
                                ))

        # Detect compare-and-branch gating on fields
        if mnemonic in {"cmp", "cmn"} and len(insn.operands) >= 2:
            rhs_op = insn.operands[1]
            rhs_str = rhs_op.reg if rhs_op.kind == "reg" else (f"#{rhs_op.imm}" if rhs_op.kind == "imm" else "")
            first_op = insn.operands[0]
            if first_op.kind == "reg":
                # Check if this is a loaded field value
                for access in accesses:
                    if _normalize_reg(first_op.reg) == _normalize_reg(access.value_reg):
                        conditions.append(InferredCondition(
                            instruction=insn,
                            field=access.field,
                            relation="cmp",
                            rhs=rhs_str,
                            dest_reg=first_op.reg,
                        ))

    return accesses, conditions, mutations


# ── Reports ─────────────────────────────────────────────────────────────────

def build_method_analysis(
    address: str,
    version: str = DEFAULT_VERSION,
    byte_count: int | None = None,
    field_map: dict[int, FieldInfo] | None = None,
    force_mode: str | None = None,
) -> Arm64MethodAnalysis:
    """Build a full method analysis for a given RVA."""
    target = int(address.strip().lstrip("0x"), 16) if "x" in address.lower() else int(address, 16)
    binary = find_libil2cpp()
    mapping = map_rva_to_file_offset(binary.path, target & ~1)

    # Determine byte count
    if byte_count is None:
        byte_count = 0x100  # default preview size
    byte_source = f"user-specified 0x{byte_count:X}"

    # Read and disassemble (architecture auto-detected from the ELF)
    _, code = read_rva_bytes(binary.path, target & ~1, byte_count)
    instructions, arch = disassemble(code, target, binary.path, force_mode=force_mode)

    # Field analysis
    field_map = field_map or {}
    accesses, conditions, mutations = analyze_field_accesses(instructions, field_map)

    # Branch gates
    branch_gates: list[InferredBranchGate] = []
    for i, insn in enumerate(instructions):
        if insn.mnemonic in {"cbz", "cbnz", "tbz", "tbnz"}:
            target_reg = insn.operands[0].reg if insn.operands[0].kind == "reg" else ""
            branch_target = insn.operands[-1].imm if insn.operands[-1].kind == "imm" else 0
            if branch_target and branch_target is not None:
                condition = "== 0" if insn.mnemonic in {"cbz", "tbz"} else "!= 0"
                # Check preceding cmp for field-based gates
                expr = target_reg
                effect = "branch (unknown)"
                if i > 0:
                    prev = instructions[i - 1]
                    if prev.mnemonic == "cmp":
                        for cond in conditions:
                            if _normalize_reg(cond.dest_reg) == _normalize_reg(target_reg):
                                expr = f"{cond.field.name} {cond.relation} {cond.rhs}"
                                effect = "conditional branch based on field"
                branch_gates.append(InferredBranchGate(
                    instruction=insn,
                    expression=expr,
                    condition=condition,
                    target=branch_target if branch_target else 0,
                    effect=effect,
                ))

    # Direct targets (BL/B to external addresses)
    direct_targets: list[DirectTarget] = []
    method_start = target
    method_end = target + byte_count
    for insn in instructions:
        if insn.mnemonic in {"bl", "b"} and insn.operands and insn.operands[0].kind == "imm":
            tgt = insn.operands[0].imm
            if tgt is not None:
                scope = "local" if method_start <= tgt < method_end else "external"
                direct_targets.append(DirectTarget(
                    instruction=insn,
                    mnemonic=insn.mnemonic,
                    target=tgt,
                    scope=scope,
                    hint="",
                ))

    notes: dict[int, list[str]] = {}
    for access in accesses:
        addr = access.instruction.address
        notes.setdefault(addr, []).append(
            f"{access.direction} {access.field.owner}.{access.field.name}"
        )

    return Arm64MethodAnalysis(
        rva=target,
        arch=arch,
        byte_count=byte_count,
        byte_source=byte_source,
        binary_path=binary.path,
        binary_source=binary.source,
        mapping=mapping,
        type_name="",
        method_signature="",
        field_map=field_map,
        instructions=instructions,
        accesses=accesses,
        conditions=conditions,
        mutations=mutations,
        branch_gates=branch_gates,
        direct_targets=direct_targets,
        notes=notes,
    )


def format_instruction_line(insn: Arm64Instruction, notes: str = "") -> str:
    """Format a single instruction line for display."""
    line = f"  {insn.address:08x}: {insn.data.hex(' '):<14} {insn.mnemonic:<8} {insn.op_str}"
    if notes:
        line += f"  // {notes}"
    return line


def evidence_report(
    address: str,
    version: str = DEFAULT_VERSION,
    byte_count: int | None = None,
    field_map: dict[int, FieldInfo] | None = None,
    force_mode: str | None = None,
) -> str:
    """Build a self-contained evidence packet for LLM reconstruction."""
    analysis = build_method_analysis(address, version, byte_count, field_map, force_mode=force_mode)
    target = f"0x{analysis.rva:08X}"
    arch_label = analysis.arch.upper()

    lines = [
        f"{arch_label} Evidence Packet for RVA {target}",
        f"binary: {analysis.binary_path}",
        f"source: {analysis.binary_source}",
        f"arch: {analysis.arch}",
        f"mapping: {format_mapping(analysis.mapping)}",
        f"method bytes: 0x{analysis.byte_count:X} ({analysis.byte_source})",
    ]
    if analysis.arch != "arm64":
        lines.append(
            "NOTE: field/condition/mutation inference is ARM64-tuned; on "
            f"{analysis.arch} treat it as best-effort and verify against the ISIL dump."
        )
    lines.extend(["", "--- Field Accesses ---"])

    if analysis.accesses:
        for idx, acc in enumerate(analysis.accesses, 1):
            arrow = "->" if acc.direction == "read" else "<-"
            lines.append(
                f"  {idx:02d}. 0x{acc.instruction.address:08X} {acc.direction:<5} "
                f"{acc.field.owner}.{acc.field.name} (+0x{acc.field.offset:X}) "
                f"via {acc.base_reg} {arrow} {acc.value_reg}"
            )
    else:
        lines.append("  none")

    lines.extend(["", "--- Inferred Conditions ---"])
    if analysis.conditions:
        for cond in analysis.conditions:
            lines.append(
                f"  0x{cond.instruction.address:08X}: "
                f"{cond.field.name} {cond.relation} {cond.rhs} -> {cond.dest_reg}"
            )
    else:
        lines.append("  none")

    lines.extend(["", "--- Inferred Mutations ---"])
    if analysis.mutations:
        for mut in analysis.mutations:
            lines.append(
                f"  0x{mut.instruction.address:08X}: "
                f"{mut.field.name} {mut.operator} {mut.amount}"
            )
    else:
        lines.append("  none")

    lines.extend(["", "--- Branch Gates ---"])
    if analysis.branch_gates:
        for gate in analysis.branch_gates:
            lines.append(
                f"  0x{gate.instruction.address:08X}: if {gate.expression} {gate.condition} -> {gate.effect}"
            )
    else:
        lines.append("  none")

    lines.extend(["", "--- Direct Targets ---"])
    for dt in analysis.direct_targets:
        lines.append(
            f"  0x{dt.instruction.address:08X}: {dt.scope} {dt.mnemonic} -> 0x{dt.target:X}  {dt.hint}"
        )

    lines.extend(["", f"--- Annotated {arch_label} Disassembly ---"])
    for insn in analysis.instructions:
        note = "; ".join(analysis.notes.get(insn.address, []))
        lines.append(format_instruction_line(insn, note))

    return "\n".join(lines)


def simple_disasm_report(
    address: str,
    version: str = DEFAULT_VERSION,
    byte_count: int = 0x100,
    force_mode: str | None = None,
) -> str:
    """Quick disassembly dump for an RVA (architecture auto-detected)."""
    target = int(address.strip().lstrip("0x"), 16) if "x" in address.lower() else int(address, 16)
    binary = find_libil2cpp()
    mapping, code = read_rva_bytes(binary.path, target & ~1, byte_count)
    insns, arch = disassemble(code, target, binary.path, force_mode=force_mode)

    lines = [
        f"Disassembly at 0x{target:X} ({byte_count} bytes, arch={arch})",
        f"binary: {binary.path}",
        f"source: {binary.source}",
        f"mapping: {format_mapping(mapping)}",
        "",
    ]
    for insn in insns:
        lines.append(f"  {insn.address:08x}: {insn.data.hex(' '):<14} {insn.mnemonic:<8} {insn.op_str}")
    return "\n".join(lines)
