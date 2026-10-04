"""The ledger: facts written by code, judgements written by agents through the CLI.

A machine-readable file, kept **physically apart from `notes/`**. The reason is
a specific failure: a previous attempt let both a script and a person write into
the same `.cs` header comments, and ended up with 789 files all stamped
"complete -- verified" by a regex that had never read an instruction. Once the
fact layer and the conclusion layer share a file, nobody can separate them again.

So the fields are split by construction:

- **Fact fields** (`ran`, `probe_set_hash`, `index_version`, probe runs, evidence
  entries) are written by deterministic code.
- **Judgement fields** (`state`, `tier`, `gap_markers`, `reach_source`) are only
  ever written through `set_judgement`, which validates, and which the CLI is the
  only caller of.

`ran` is a separate field rather than a fifth state. The four states say what we
know about the game; `ran` says what we did. Fold them together and the
re-run logic loses the only thing it can key on.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

from .methodology import (
    GAP_SERVER_SIDE,
    KNOWN_GAP_MARKERS,
    REACH_SOURCES,
    STATE_MEETS,
    STATE_OUT_OF_REACH,
    STATES,
    TIERS,
    CellId,
    tier_rank,
)

SCHEMA = 1

# The split that the guardrail test asserts on.
FACT_FIELDS = ("ran", "probe_set_hash", "index_version", "ran_at")
JUDGEMENT_FIELDS = ("state", "tier", "gap_markers", "reach_source", "notes_ref", "summary")


class LedgerError(ValueError):
    """A ledger write was rejected."""


def _blank_cell() -> dict:
    return {
        # facts
        "ran": False,
        "probe_set_hash": "",
        "index_version": "",
        "ran_at": 0.0,
        # judgements -- untouched by any deterministic code path
        "state": "",
        "tier": "",
        "gap_markers": [],
        "reach_source": "",
        "notes_ref": "",
        "summary": "",
        "evidence": [],
    }


@dataclass
class Ledger:
    pack: str
    path: str = ""
    schema: int = SCHEMA
    pack_version: str = "0"
    package: dict = field(default_factory=dict)      # package-level facts
    cells: dict = field(default_factory=dict)
    probe_runs: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    dead_ends: list = field(default_factory=list)

    # ── loading and saving ──────────────────────────────────────────────
    @classmethod
    def load(cls, path: str, pack: str = "") -> "Ledger":
        if not os.path.exists(path):
            return cls(pack=pack or _pack_from_path(path), path=path)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return cls(
            pack=raw.get("pack") or pack or _pack_from_path(path),
            path=path,
            schema=int(raw.get("schema", SCHEMA)),
            pack_version=str(raw.get("pack_version", "0")),
            package=raw.get("package") or {},
            cells=raw.get("cells") or {},
            probe_runs=raw.get("probe_runs") or [],
            evidence=raw.get("evidence") or {},
            dead_ends=raw.get("dead_ends") or [],
        )

    def save(self) -> str:
        if not self.path:
            raise LedgerError("ledger has no path")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {
            "schema": self.schema,
            "pack": self.pack,
            "pack_version": self.pack_version,
            "package": self.package,
            "cells": self.cells,
            "probe_runs": self.probe_runs,
            "evidence": self.evidence,
            "dead_ends": self.dead_ends,
        }
        tmp = f"{self.path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, self.path)
        return self.path

    # ── facts (deterministic code may call these) ───────────────────────
    def cell(self, cell: CellId | str) -> dict:
        key = str(cell)
        if key not in self.cells:
            self.cells[key] = _blank_cell()
        return self.cells[key]

    def ensure_cells(self, cell_ids) -> None:
        for cid in cell_ids:
            self.cell(cid)

    def record_probe_run(self, run) -> None:
        """Record one probe run. Zero-hit runs are recorded like any other.

        A pack probe *replaces* its previous record rather than stacking on it:
        the ledger is the current state of "what was searched and what
        answered", and re-scanning ten times should not make it ten times
        longer. Ad-hoc runs do append -- those are a record of what somebody
        tried, and the attempts are the point.
        """
        payload = run.to_json() if hasattr(run, "to_json") else dict(run)
        if payload.get("origin") == "adhoc":
            self.probe_runs.append(payload)
            return
        key = (payload.get("probe_key"), payload.get("corpus"), payload.get("slot"))
        for index, existing in enumerate(self.probe_runs):
            if existing.get("origin") == "adhoc":
                continue
            if (existing.get("probe_key"), existing.get("corpus"), existing.get("slot")) == key:
                self.probe_runs[index] = payload
                return
        self.probe_runs.append(payload)

    def mark_ran(self, cell: CellId | str, probe_set_hash: str, index_version: str) -> None:
        entry = self.cell(cell)
        entry["ran"] = True
        entry["probe_set_hash"] = probe_set_hash
        entry["index_version"] = index_version
        entry["ran_at"] = time.time()

    def add_evidence(self, evidence_id: str, payload: dict) -> None:
        self.evidence[evidence_id] = payload

    def attach_evidence(self, cell: CellId | str, evidence_id: str) -> None:
        entry = self.cell(cell)
        if evidence_id not in entry["evidence"]:
            entry["evidence"].append(evidence_id)

    def record_dead_end(self, slot: str, candidate: str, reason: str, task: str = "") -> None:
        """A candidate that was retrieved, read, and found irrelevant.

        The executor can only see zero hits; this is the other kind of dead end,
        and without it the next dig walks the same path again. Recorded as one
        line, in the ledger only -- useful to the next investigation, noise to a
        reader of the notes.
        """
        self.dead_ends.append({
            "slot": slot, "candidate": candidate, "reason": reason,
            "task": task, "at": time.time(),
        })

    # ── judgements (CLI-only path, validated) ───────────────────────────
    def set_judgement(
        self,
        cell: CellId | str,
        state: str,
        tier: str = "",
        gap_markers: list | None = None,
        reach_source: str = "",
        notes_ref: str = "",
        summary: str = "",
        ceiling: str = "",
    ) -> list[str]:
        """Write the judgement fields for a cell. Returns non-fatal warnings.

        Validation is the reason this goes through a command rather than the
        MCP surface: state values must be legal, `out_of_reach` must say which
        side the gap is on, and a tier above what this kind of cell can ever
        reach is worth flagging.
        """
        if state not in STATES:
            raise LedgerError(
                f"{state!r} is not a cell state. One of: {', '.join(STATES)}"
            )
        if tier and tier not in TIERS:
            raise LedgerError(f"{tier!r} is not an evidence tier ({', '.join(TIERS)})")
        if state == STATE_OUT_OF_REACH and reach_source not in REACH_SOURCES:
            raise LedgerError(
                "out_of_reach needs reach_source=input_missing|output_doubtful -- "
                "the two have opposite remedies, so the distinction is not optional"
            )
        if reach_source and reach_source not in REACH_SOURCES:
            raise LedgerError(f"{reach_source!r} is not a reach source")

        warnings: list[str] = []
        markers = list(gap_markers or [])
        for marker in markers:
            if marker not in KNOWN_GAP_MARKERS:
                warnings.append(
                    f"gap marker {marker!r} is not one of the known ones "
                    f"({', '.join(KNOWN_GAP_MARKERS)})"
                )
        if state == STATE_MEETS and not tier:
            warnings.append("a cell that meets its threshold should name an evidence tier")
        if ceiling and tier and tier_rank(tier) > tier_rank(ceiling):
            warnings.append(
                f"tier {tier!r} is above this cell's reachable ceiling {ceiling!r} -- "
                f"cells of this kind have not been reachable past that in any target"
            )

        entry = self.cell(cell)
        entry.update({
            "state": state,
            "tier": tier,
            "gap_markers": markers,
            "reach_source": reach_source,
            "notes_ref": notes_ref,
            "summary": summary,
        })
        return warnings

    # ── idempotency ─────────────────────────────────────────────────────
    def stale_cells(self, expected: dict) -> list[str]:
        """Cells whose probe set or index version no longer matches.

        `expected` maps cell id -> (probe_set_hash, index_version). Anything
        that drifted is stale and must be re-run; adding one word to a pack's
        probes therefore invalidates every conclusion that rested on that word
        finding nothing.
        """
        out: list[str] = []
        for key, (probe_hash, index_version) in expected.items():
            entry = self.cells.get(key)
            if not entry or not entry.get("ran"):
                continue
            if entry.get("probe_set_hash") != probe_hash or entry.get("index_version") != index_version:
                out.append(key)
        return out

    def invalidate(self, cell_ids) -> int:
        """Send cells back to "not run" so the next scan redoes them.

        Judgements are cleared with them: they were reached under a probe set
        that no longer exists, and keeping them would be keeping an answer to a
        question that changed.
        """
        count = 0
        for key in cell_ids:
            entry = self.cells.get(str(key))
            if not entry:
                continue
            self.cells[str(key)] = _blank_cell()
            count += 1
        return count

    # ── reporting ───────────────────────────────────────────────────────
    def coverage(self) -> dict:
        total = len(self.cells)
        by_state: dict[str, int] = {}
        ran = 0
        for entry in self.cells.values():
            if entry.get("ran"):
                ran += 1
            state = entry.get("state") or "(unfilled)"
            by_state[state] = by_state.get(state, 0) + 1
        return {
            "pack": self.pack,
            "cells": total,
            "ran": ran,
            "by_state": by_state,
            "probe_runs": len(self.probe_runs),
            "zero_hit_runs": sum(1 for r in self.probe_runs if not r.get("hit_count")),
            "dead_ends": len(self.dead_ends),
        }


def _pack_from_path(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def ledger_dir(project_root: str) -> str:
    return os.path.join(project_root, ".revenant", "scan")


def ledger_path(project_root: str, pack: str) -> str:
    return os.path.join(ledger_dir(project_root), f"{pack}.json")


def judgement_fields_written(led: Ledger) -> list[str]:
    """Cells carrying any judgement. Used by the guardrail test.

    After a purely deterministic command this must be empty. The previous
    generation of this tooling failed exactly here -- a script wrote the
    completeness field, and the number it produced was fiction.
    """
    out: list[str] = []
    for key, entry in led.cells.items():
        if any(entry.get(f) for f in JUDGEMENT_FIELDS):
            out.append(key)
    return out
