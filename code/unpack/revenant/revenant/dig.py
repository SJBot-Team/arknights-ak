"""Deep dives: a business question, completion criteria, and a convergence.

A direction is a structured brief -- but the person only says one sentence, and
an agent expands it into the brief for them to confirm. That confirmation step
is what settles granularity, so granularity never needs a rule.

The shape is not arbitrary. Five real briefs in the reference corpus all had it
(business question, verified entry addresses, sub-questions, target filename)
and the one run that instead took a bare list of 152 methods produced a table of
"which files were reconstructed" -- the least useful of that project's 27 notes,
because it answered no question.

A dig has two moves (ADR-0002): `open` and `converge`. An earlier shape also
had per-round ticks, a stall detector (progress-based, deliberately not
spend-based) and a handover queue from the scan; all three served an unattended
per-round loop that nobody built. The stall detector's design was right and
comes back with the loop; until then "done" is decided at convergence, by the
criteria.

Human interruptions are *not* limited here, unlike a breadth scan. Someone
pointing the direction is how a deep dive works, not an anomaly, and budgeting
it would be budgeting the method itself.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from . import ledger as _ledger
from .methodology import CellId

STATUS_OPEN = "open"
STATUS_DONE = "done"
STATUS_UNFINISHED = "unfinished"   # converged with criteria still open


@dataclass
class Criterion:
    text: str
    met: bool = False

    def to_json(self) -> dict:
        return {"text": self.text, "met": self.met}


@dataclass
class DigTask:
    id: str
    question: str
    criteria: list = field(default_factory=list)
    entry_hints: list = field(default_factory=list)
    origin_cell: str = ""
    status: str = STATUS_OPEN
    dead_ends: list = field(default_factory=list)
    note_ref: str = ""
    created_at: float = 0.0

    def to_json(self) -> dict:
        return {
            "id": self.id, "question": self.question,
            "criteria": [c.to_json() for c in self.criteria],
            "entry_hints": self.entry_hints, "origin_cell": self.origin_cell,
            "status": self.status, "dead_ends": self.dead_ends,
            "note_ref": self.note_ref, "created_at": self.created_at,
        }

    @classmethod
    def from_json(cls, raw: dict) -> "DigTask":
        task = cls(
            id=raw["id"], question=raw.get("question", ""),
            entry_hints=raw.get("entry_hints") or [],
            origin_cell=raw.get("origin_cell", ""),
            status=raw.get("status", STATUS_OPEN),
            dead_ends=list(raw.get("dead_ends") or []),
            note_ref=raw.get("note_ref", ""), created_at=raw.get("created_at", 0.0),
        )
        task.criteria = [Criterion(c["text"], bool(c.get("met"))) for c in raw.get("criteria") or []]
        return task

    @property
    def unmet(self) -> list:
        return [c for c in self.criteria if not c.met]


class DigError(ValueError):
    pass


def open_task(question: str, criteria: list, entry_hints: list | None = None,
              origin_cell: str = "") -> DigTask:
    """Create a task. A question and criteria are both required.

    Without criteria there is nothing for "done" to mean, and the one historical
    run that skipped them produced a table instead of an answer.
    """
    if not question.strip():
        raise DigError("a dig needs a business question -- a list of targets is not one")
    cleaned = [Criterion(text.strip()) for text in criteria if text.strip()]
    if not cleaned:
        raise DigError(
            "a dig needs completion criteria, tick-by-tick. They are the only "
            "thing 'finished' can be checked against -- self-assessment is a "
            "useful signal but not a verdict."
        )
    return DigTask(
        id=uuid.uuid4().hex[:12], question=question.strip(), criteria=cleaned,
        entry_hints=list(entry_hints or []), origin_cell=origin_cell,
        created_at=time.time(),
    )


def entry_hints_as_probes(hints: list) -> list:
    """Compile the person's entry hints into probes.

    The hard constraint carried over from the direction-selection ticket: a
    direction someone points is retrieval, and it must go through the same
    executor and the same ledger as a pack's probes, or there are two retrieval
    mechanisms that do not know about each other.
    """
    from .pack import Probe
    out = []
    for hint in hints:
        text = str(hint).strip()
        if not text:
            continue
        if text.lower().startswith("0x"):
            continue  # an address, not a retrieval pattern
        pattern = text if any(ch in text for ch in ".*+?[]()|") else f".*{text}.*"
        out.append(Probe(kind="class_regex", pattern=pattern))
    return out


def converge(task: DigTask, led: _ledger.Ledger | None, dead_ends: list,
             retrieved_candidates: list, met: list | None = None,
             used: list | None = None, note_ref: str = "") -> tuple[DigTask, list]:
    """Wrap up a dig. Refuses while any retrieved candidate is unaccounted for.

    Every criterion in `met` is ticked; the dig is `done` if none remain, else
    `unfinished` -- converged, but with the open criteria on record. The
    executor only sees zero hits; a dead end here is the other kind -- a
    candidate that *was* retrieved, was read, and turned out to be irrelevant.
    Left unrecorded, the next dig walks the same path. Making it a condition of
    converging turns it from "remember to do this" into a step, because across
    27 notes exactly one such record was ever written by hand. `used` names the
    candidates that made it into the note; those are accounted for too.

    Dead ends live on the dig; when the dig came from a scan cell, `led` is
    that pack's ledger and they are recorded there as well.
    """
    for index in met or []:
        if index < 0 or index >= len(task.criteria):
            raise DigError(f"no criterion #{index}")
    accounted = {d["candidate"] for d in dead_ends} | set(used or [])
    unaccounted = [c for c in retrieved_candidates if c not in accounted]
    if unaccounted:
        raise DigError(
            f"{len(unaccounted)} retrieved candidates are unaccounted for "
            f"({', '.join(unaccounted[:4])}...). Give each a one-line disposition "
            f"(--dead-end or --used) before converging -- that record is what "
            f"stops the next dig walking the same path."
        )
    for index in met or []:
        task.criteria[index].met = True
    task.dead_ends = list(dead_ends)
    if note_ref:
        task.note_ref = note_ref
    task.status = STATUS_DONE if not task.unmet else STATUS_UNFINISHED
    if led is not None:
        for entry in dead_ends:
            led.record_dead_end(entry.get("slot", ""), entry["candidate"],
                                entry.get("reason", ""), task.id)
    return task, dead_ends


def ledger_for_cell(project_root: str, origin_cell: str):
    """The pack ledger a dig's origin cell lives in, if the dig came from a
    scan; None otherwise (dead ends then stay on the dig itself)."""
    if not origin_cell:
        return None
    try:
        cid = CellId.parse(origin_cell)
    except ValueError:
        return None
    return _ledger.Ledger.load(_ledger.ledger_path(project_root, cid.pack), cid.pack)


def hand_back_cell(led: _ledger.Ledger, cell: CellId | str, note_ref: str,
                   evidence_id: str = "") -> None:
    """Return the originating cell to "not run" once a dig has answered it.

    Not "fill it in": the two answer different questions -- the dig answers a
    business question, the cell asks one of six facets -- so having the dig
    write the cell would be having it write something it was not answering.
    "Not run" already means "redo this next scan", so the existing machinery
    does the work, and the dig's note rides along as better input.
    """
    entry = led.cell(cell)
    entry.update({
        "ran": False, "probe_set_hash": "", "index_version": "", "ran_at": 0.0,
        "state": "", "tier": "", "gap_markers": [], "reach_source": "",
        "summary": "",
    })
    entry["notes_ref"] = note_ref
    if evidence_id:
        led.attach_evidence(cell, evidence_id)


# Review triggers a dig's output must clear before it may overwrite a scan's
# conclusion. Machine-computable, all three.
def review_triggers(defect_marked: bool, self_assessed_high: bool,
                    has_placeholder: bool) -> list:
    out = []
    if defect_marked:
        out.append("input carries lifter defect markers")
    if not self_assessed_high:
        out.append("the agent did not self-assess as high confidence")
    if has_placeholder:
        out.append("the output contains placeholders")
    return out


def may_override_scan(review_needed: list, review_done: bool) -> tuple[bool, str]:
    """Whether a dig conclusion may overwrite a scan conclusion unattended.

    Evidence strength is not symmetric -- a scan stops at structure and clues,
    a dig has read the method body -- so the stronger one wins without a human
    adjudicating. The precondition is that the dig's output cleared the review
    triggers; otherwise something nobody has looked at would be rewriting a
    recorded conclusion.
    """
    if not review_needed or review_done:
        return True, ""
    return False, (
        "conflict recorded, override withheld: " + "; ".join(review_needed) +
        ". Unreviewed output must not rewrite a conclusion already on record."
    )


def record_conflict(led: _ledger.Ledger, cell: CellId | str, probe_key: str,
                    scan_state: str, dig_state: str, overridden: bool) -> None:
    """Log a scan/dig disagreement. Never counts against the attention budget.

    It has to be countable, though: one probe repeatedly disagreeing with dig
    results is a systematic fault in that probe, and that is exactly the input
    the pack-vocabulary reflow wants.
    """
    led.package.setdefault("conflicts", []).append({
        "cell": str(cell), "probe_key": probe_key,
        "scan_state": scan_state, "dig_state": dig_state,
        "overridden": overridden, "at": time.time(),
    })


# ── task storage ────────────────────────────────────────────────────────────

def tasks_path(project_root: str) -> str:
    import os
    return os.path.join(project_root, ".revenant", "digs.json")


def load_tasks(path: str) -> list:
    import json
    import os
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [DigTask.from_json(raw) for raw in json.load(f)]


def save_tasks(path: str, tasks: list) -> str:
    import json
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([t.to_json() for t in tasks], f, indent=1, ensure_ascii=False)
    return path
