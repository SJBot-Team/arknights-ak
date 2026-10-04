"""The L2 vocabulary: facets, evidence tiers, cell states, gap markers.

Fixed globally and deliberately not extensible by a pack. Cross-game comparison
is the whole point of writing any of this down, and comparison only works if the
ruler is the same everywhere -- three target projects each grew their own tier
scheme, and the third was not even measuring the same thing as the other two.

Three things live here that get confused with each other constantly, so they are
kept apart by construction:

- **Tier** is a property of one *conclusion*: which layer the evidence came from.
- **State** is a property of one *cell*: how filled in it is.
- **Gap marker** is a property of a conclusion that *holds* but has a piece you
  cannot obtain (a threshold that lives on the server, say).

A corpus measured 78 uses of a "pending server confirmation" marker. There is no
room for that in a tier scale, so when it has nowhere else to go it climbs into
the tier scale and corrupts it -- which is exactly what happened.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── the six facets ──────────────────────────────────────────────────────────
# Every slot is answered in these six sections. Verified isomorphic across 15
# module write-ups in the existing corpus. A pack may declare a facet
# inapplicable to one of its slots; it may not invent a seventh.

FACETS: tuple[str, ...] = (
    "responsibility",          # 职责边界
    "api_contract",            # API 契约
    "data_model",              # 数据模型
    "core_mechanism",          # 核心机制
    "bridge_backend",          # 桥接与后端
    "platform_differences",    # 平台差异
)

FACET_TITLES = {
    "responsibility": "职责边界",
    "api_contract": "API 契约",
    "data_model": "数据模型",
    "core_mechanism": "核心机制",
    "bridge_backend": "桥接与后端",
    "platform_differences": "平台差异",
}


# ── evidence tiers ──────────────────────────────────────────────────────────
# Named after how the evidence was obtained, not by an abstract level number.
#
# Two projects independently abandoned numbered tiers and invented their own
# method-named vocabularies ("[Lua坐实]", "[DEX普查]", ...), which is the
# strongest signal available that method names are what people actually reach
# for. They are also checkable in a way a level number never is: "script source"
# can be verified by looking for the symbol in the script.
#
# The bottom "speculation" tier is gone: it was used exactly 0 times across 22
# write-ups, while an informal "[inferred]" marker was used 416 times. Nobody
# labels their own conclusion a guess.

TIER_DISASSEMBLY = "disassembly"        # 反汇编坐实
TIER_SCRIPT_SOURCE = "script_source"    # 脚本源码坐实
TIER_MANAGED_CODE = "managed_code"      # 托管代码坐实
TIER_STRUCTURAL = "structural"          # 结构推断

TIERS: tuple[str, ...] = (
    TIER_DISASSEMBLY,
    TIER_SCRIPT_SOURCE,
    TIER_MANAGED_CODE,
    TIER_STRUCTURAL,
)

TIER_TITLES = {
    TIER_DISASSEMBLY: "反汇编坐实",
    TIER_SCRIPT_SOURCE: "脚本源码坐实",
    TIER_MANAGED_CODE: "托管代码坐实",
    TIER_STRUCTURAL: "结构推断",
}

# Comparable strength, used only for the reachable-ceiling check. Reading the
# instructions and reading the real script source are both authoritative, for
# different corpora -- a cell is never served by both, so the tie is harmless.
TIER_RANK = {
    TIER_DISASSEMBLY: 3,
    TIER_SCRIPT_SOURCE: 3,
    TIER_MANAGED_CODE: 2,
    TIER_STRUCTURAL: 1,
}


def tier_rank(tier: str) -> int:
    return TIER_RANK.get(tier, 0)


def is_tier(value: str) -> bool:
    return value in TIER_RANK


# ── tier aliases: what real notes actually write ────────────────────────────
# The four tiers above are the ruler. Notes in the wild do not write
# `[script_source]`; they write `[Lua坐实]`, `[原生T1]`, `[C#签名]`, or a bare
# `T1` in a table cell -- 27 real notes carried 23 lint false positives before
# any of these were recognised, which made the lint worthless.
#
# This table maps every observed spelling onto one of the four tiers. It is
# the ONLY place such a mapping lives: `lint` reads it, and the rendered skill
# lists it, so a project cannot learn a spelling the lint does not accept.
# Unknown spellings are reported, not silently ignored -- a typo must not
# become a fifth tier.
#
# Numbered levels are the retired scheme (T1 = raw ARM, T1.5 = interleaved C,
# T2 = verified C#, T3 = structural). They are accepted on the way *in* so old
# notes lint, and the mapping is one-way: `describe` never teaches them. There
# is deliberately no entry for T4 / 推测 / 猜测 -- the speculation tier was
# used 0 times in 22 write-ups and does not exist here (see above), so a note
# that carries it is asked to reclassify.

TIER_ALIASES: dict[str, str] = {
    # canonical spellings
    **{tier: tier for tier in TIERS},
    **{title: tier for tier, title in TIER_TITLES.items()},
    # method-named spellings two projects invented on their own
    "Lua坐实": TIER_SCRIPT_SOURCE,
    "原生T1": TIER_DISASSEMBLY,
    "C#签名": TIER_MANAGED_CODE,
    "DEX普查": TIER_MANAGED_CODE,
    "推断": TIER_STRUCTURAL,
    # the retired numbered scale
    "T1": TIER_DISASSEMBLY,
    "T1.5": TIER_DISASSEMBLY,
    "T2": TIER_MANAGED_CODE,
    "T3": TIER_STRUCTURAL,
}

# What a bracket that is *trying* to be a tier marker looks like when it is not
# one of the spellings above: a morpheme from the accepted spellings, or a bare
# level. `[原生T2]`, `[Smali坐实]`, `[猜测]` are reported by lint as unknown;
# `[服务器侧]` or `[待验证]` are not -- gap markers are a different axis. Kept
# beside the alias table so the vocabulary has one home.
TIER_LOOKALIKE_HINTS: tuple[str, ...] = ("坐实", "签名", "普查", "推断", "推测", "猜测")

# Accepted by lint, never taught by `describe`: listing these in a skill would
# be teaching the abolished scale, which is the drift #25 exists to prevent.
RETIRED_SPELLINGS: frozenset[str] = frozenset({"T1", "T1.5", "T2", "T3"})


def resolve_tier(spelling: str) -> str:
    """Map an observed spelling onto a tier, or '' when it is not one we know."""
    return TIER_ALIASES.get(spelling.strip(), "")


def tier_spellings(tier: str, include_retired: bool = False) -> list[str]:
    """Every accepted spelling of one tier, canonical first.

    `include_retired` adds the numbered levels; lint's error message wants
    them (they are accepted), the rendered skill must not (they are retired).
    """
    out = [tier, TIER_TITLES[tier]]
    for spelling, mapped in TIER_ALIASES.items():
        if mapped != tier or spelling in out:
            continue
        if spelling in RETIRED_SPELLINGS and not include_retired:
            continue
        out.append(spelling)
    return out


# ── cell states ─────────────────────────────────────────────────────────────
# Four, because two would fold "we checked and it genuinely is not there" into
# the same bucket as "nobody looked" -- and a survey of one corpus found that of
# 8 one-sided slots, only 2 were real differences and 6 were coverage holes.

STATE_MEETS = "meets_threshold"              # 已填且达标
STATE_INSUFFICIENT = "insufficient_evidence"  # 已填但证据不够
STATE_ABSENT = "confirmed_absent"            # 查过，确认不存在
STATE_OUT_OF_REACH = "out_of_reach"          # 证据够不到

STATES: tuple[str, ...] = (
    STATE_MEETS, STATE_INSUFFICIENT, STATE_ABSENT, STATE_OUT_OF_REACH,
)

STATE_TITLES = {
    STATE_MEETS: "已填且达标",
    STATE_INSUFFICIENT: "已填但证据不够",
    STATE_ABSENT: "查过，确认不存在",
    STATE_OUT_OF_REACH: "证据够不到",
}

# `out_of_reach` carries one extra dimension, because the two causes have
# opposite remedies: an input-side gap is fixed by supplying better input (and
# should re-queue itself automatically once that lands), while an output-side
# doubt is not.
REACH_INPUT_MISSING = "input_missing"
REACH_OUTPUT_DOUBTFUL = "output_doubtful"
REACH_SOURCES: tuple[str, ...] = (REACH_INPUT_MISSING, REACH_OUTPUT_DOUBTFUL)


# ── gap markers ─────────────────────────────────────────────────────────────
# The conclusion holds; a piece of it is unobtainable. Open vocabulary with
# known values -- an unknown marker is allowed but flagged, so a typo does not
# silently become a new category.

GAP_SERVER_SIDE = "server_side"            # 数值/映射由服务端持有
GAP_NATIVE_BLACKBOX = "native_blackbox"    # 原生层未反汇编
GAP_STRIPPED_SYMBOLS = "stripped_symbols"  # 符号被 strip
GAP_NOT_IN_PACKAGE = "not_in_package"      # 内容不随包发布

KNOWN_GAP_MARKERS: tuple[str, ...] = (
    GAP_SERVER_SIDE, GAP_NATIVE_BLACKBOX, GAP_STRIPPED_SYMBOLS, GAP_NOT_IN_PACKAGE,
)


@dataclass(frozen=True)
class CellId:
    """`<pack>/<slot>#<facet>` -- stable across runs and across projects."""

    pack: str
    slot: str
    facet: str

    def __str__(self) -> str:
        return f"{self.pack}/{self.slot}#{self.facet}"

    @classmethod
    def parse(cls, text: str) -> "CellId":
        try:
            head, facet = text.split("#", 1)
            pack, slot = head.split("/", 1)
        except ValueError as exc:
            raise ValueError(
                f"{text!r} is not a cell id (expected '<pack>/<slot>#<facet>')"
            ) from exc
        if facet not in FACETS:
            raise ValueError(
                f"{facet!r} is not one of the six facets: {', '.join(FACETS)}"
            )
        return cls(pack=pack, slot=slot, facet=facet)
