"""Breadth scan: deterministic work only, and a warning in front of it.

Revenant never calls a model. `revenant scan` runs the probes, records the
facts, and writes one brief per slot; an external harness drives the agents that
read those briefs. The previous generation of this tooling welded a specific
model vendor into a shell script, and that half never ran once -- the six notes
it was supposed to produce do not exist.

**Corpus warning.** The fingerprint lists which declared game assemblies the
metadata does not contain (ADR-0002: it observes, it does not judge). When that
list is not empty the scan says so, on the ledger and in the report, and runs
anyway: on a title whose business code lives in hot-update assemblies, probing
the IL2CPP index returns zero for everything, and a report that says "this game
has none of it" carries no sign that anything went wrong -- the warning is that
sign. This used to be a hard gate on a marker-string verdict, and one wiped
marker made it fail in the dangerous direction; a fact the reader can check
beats a verdict that can silently flip.

**Attention budget.** At most five interruptions per scan, and those are five
*batches*, not five interruptions. Signals accumulate silently; the whole set is
presented once when the scan finishes. If every signal stopped the scan on the
spot, twenty-four slots would blow through five without trying.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from . import fingerprint as _fp
from . import ledger as _ledger
from . import probes as _probes
from .methodology import STATE_MEETS, STATE_OUT_OF_REACH

# The one hard limit. Tokens and wall-clock are accounted, never gated: the
# right response to overspending tokens is to read the report, while the right
# response to overspending human attention is to stop and rethink the outline.
MAX_ATTENTION_BATCHES = 5

# Candidates past this point are more than an agent can converge on, which is
# one of the three things worth a human for.
CANDIDATE_EXPLOSION = 200

SIGNAL_CANDIDATE_EXPLOSION = "candidate_explosion"
SIGNAL_FACET_CONTRADICTION = "facet_contradiction"
SIGNAL_AGENT_STUCK = "agent_stuck"

# Deliberately NOT signals:
#   unmet `requires` edge  -- already decided to warn, and calling a human is
#                             blocking by another name
#   low coverage           -- an outcome, not an anomaly; it belongs in the
#                             report, not in an interruption


@dataclass
class Signal:
    kind: str
    slot: str
    detail: str


@dataclass
class ScanResult:
    started: bool = False
    corpus_warning: str = ""
    slots_run: list = field(default_factory=list)
    briefs: list = field(default_factory=list)
    signals: list = field(default_factory=list)
    batches_used: int = 0
    stopped_early: bool = False
    zero_hit_runs: int = 0

    def as_text(self) -> str:
        lines = [
            f"scanned {len(self.slots_run)} slots, "
            f"{self.zero_hit_runs} zero-hit probe runs recorded",
        ]
        if self.corpus_warning:
            lines.append(f"WARNING: {self.corpus_warning}")
        if self.stopped_early:
            lines.append(
                f"STOPPED: a sixth batch of signals appeared. The attention budget "
                f"is {MAX_ATTENTION_BATCHES} batches; needing more means the outline "
                f"does not fit this game, and finishing would only spread the same "
                f"doubt over more cells."
            )
        for signal in self.signals:
            lines.append(f"  [{signal.kind}] {signal.slot}: {signal.detail}")
        lines.append(f"briefs: {len(self.briefs)} (one per slot, for the agent side)")
        return "\n".join(lines)


def corpus_warning(fp: _fp.Fingerprint) -> str:
    """The fact the fingerprint offers, in the fingerprint's own words; "" if none.

    Not a gate. The scan runs; the reader is told that the corpus about to be
    searched does not contain the game assemblies the manifest declares -- and
    can check that claim against the observation list.
    """
    note = fp.absent_note()
    if not note:
        return ""
    return (
        f"{note}; if the business code lives in them, every IL2CPP probe below "
        f"returns zero and 'checked, genuinely absent' means nothing"
    )


def _corpora_for(version: str) -> list:
    out = []
    il2cpp = _probes.il2cpp_corpus(version)
    if not il2cpp.is_empty():
        out.append(il2cpp)
    lua = _probes.lua_corpus(version)
    if not lua.is_empty():
        out.append(lua)
    return out


def build_brief(pack, slot, report: _probes.ProbeReport, fp: _fp.Fingerprint) -> dict:
    """One slot's working packet for the agent side.

    Facts only: the question, the six facets to answer, what the probes found
    and what they did not. No ranking, no suggestion of an answer.
    """
    return {
        "pack": pack.name,
        "pack_version": pack.version,
        "slot": slot.id,
        "title": slot.title,
        "question": slot.body,
        "cells": [str(c) for c in slot.cells()],
        "thresholds": {
            c.facet: (slot.spec(c.facet).threshold or pack.facet_defaults.get(c.facet).threshold
                      if pack.facet_defaults.get(c.facet) else slot.spec(c.facet).threshold)
            for c in slot.cells()
        },
        "ceilings": {c.facet: slot.spec(c.facet).ceiling for c in slot.cells()
                     if slot.spec(c.facet).ceiling},
        "probe_runs": [r.to_json() for r in report.runs],
        "candidates": report.candidates()[:CANDIDATE_EXPLOSION],
        "candidate_count": len(report.candidates()),
        "zero_hit_probes": [
            {"kind": r.kind, "pattern": r.pattern, "values": list(r.values)}
            for r in report.zero_hit_runs
        ],
        "business_assemblies_absent": fp.business_assemblies_absent(),
        "naming_statistics_hint": (
            "Before calling any cell 'checked, genuinely absent', hold the probe "
            "vocabulary up against this game's own naming (revenant naming-stats). "
            "A zero hit can mean the word list is wrong, not that the system is."
        ),
    }


def run(
    pack,
    fp: _fp.Fingerprint,
    led: _ledger.Ledger,
    version: str,
    index_version: str,
    only_slots: list | None = None,
    brief_dir: str = "",
) -> ScanResult:
    """Run one pack's probes and produce briefs. Writes facts only.

    The corpus warning (see module docstring) is recorded on the ledger and in
    the result; it never stops the scan.
    """
    result = ScanResult()
    result.corpus_warning = corpus_warning(fp)
    if result.corpus_warning:
        led.package["corpus_warning"] = result.corpus_warning
    else:
        led.package.pop("corpus_warning", None)
    result.started = True
    led.package["fingerprint"] = fp.to_json()

    corpora = _corpora_for(version)
    slot_ids = only_slots or sorted(pack.slots)
    for slot_id in slot_ids:
        slot = pack.slot(slot_id)
        report = _probes.run_slot(slot.id, slot.probes, corpora)
        for probe_run in report.runs:
            led.record_probe_run(probe_run)
        result.zero_hit_runs += len(report.zero_hit_runs)
        for cell in slot.cells():
            led.mark_ran(cell, slot.probe_set_hash(), index_version)

        if len(report.candidates()) > CANDIDATE_EXPLOSION:
            result.signals.append(Signal(
                SIGNAL_CANDIDATE_EXPLOSION, slot.id,
                f"{len(report.candidates())} candidates -- more than an agent can "
                f"converge on; the probe patterns are too broad for this game",
            ))

        brief = build_brief(pack, slot, report, fp)
        result.briefs.append(brief)
        result.slots_run.append(slot.id)
        if brief_dir:
            os.makedirs(brief_dir, exist_ok=True)
            with open(os.path.join(brief_dir, f"{pack.name}-{slot.id}.json"), "w",
                      encoding="utf-8") as f:
                json.dump(brief, f, indent=1, ensure_ascii=False)

    result.signals.extend(facet_contradictions(pack, led))

    # Signals are held, then presented once. Five batches is the budget; the
    # sixth means the outline does not fit this game.
    result.batches_used = 1 if result.signals else 0
    prior = int(led.package.get("attention_batches", 0))
    if result.signals:
        prior += 1
        led.package["attention_batches"] = prior
    if prior > MAX_ATTENTION_BATCHES:
        result.stopped_early = True
    return result


def facet_contradictions(pack, led: _ledger.Ledger) -> list:
    """A slot whose facets disagree in a way that cannot all be true.

    Concretely: some facet met its threshold while another was recorded as
    "checked, genuinely absent". A system cannot both be described and be
    missing.
    """
    signals: list = []
    for slot_id in sorted(pack.slots):
        states = set()
        for cell in pack.slot(slot_id).cells():
            entry = led.cells.get(str(cell)) or {}
            if entry.get("state"):
                states.add(entry["state"])
        if STATE_MEETS in states and "confirmed_absent" in states:
            signals.append(Signal(
                SIGNAL_FACET_CONTRADICTION, slot_id,
                "one facet meets its threshold while another says the system is "
                "genuinely absent -- both cannot hold",
            ))
    return signals


def agent_stuck(slot_id: str, detail: str) -> Signal:
    """Recorded when an agent says so itself, which is the third signal."""
    return Signal(SIGNAL_AGENT_STUCK, slot_id, detail)
