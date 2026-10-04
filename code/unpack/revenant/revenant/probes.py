"""The probe executor: every retrieval goes through here, and every one is logged.

Retrieval hints in a pack are not prose for an agent to read -- the harness runs
them, and running them produces the hit/zero-hit record as a by-product.

Two rules that look like details and are not:

**A zero-hit run is still a run, and must leave a record.** The only checkable
way to tell "this game genuinely does not have it" from "nobody looked" is a
record of which terms were searched and what turned up instead. Across 110k
lines of existing write-ups, exactly 4 places managed it -- not because it is
hard, but because nobody remembers to do it by hand. This is the whole reason
the executor exists, and it is the first thing an implementation is tempted to
drop ("no results, nothing to write").

**Ad-hoc searches go through the same door.** An agent that wants to try one
more term mid-session uses `run_adhoc`, not its own regex loop, or the ledger
develops holes exactly where someone was improvising.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Iterable

from .pack import Probe

CORPUS_IL2CPP = "il2cpp"
CORPUS_LUA = "lua"


@dataclass
class Corpus:
    """What probes are matched against.

    Corpus selection is not cosmetic: on a title whose gameplay lives in hot-
    update assemblies or in script source, running probes over the IL2CPP index
    returns zero hits for everything, and the whole scan would conclude "this
    game has none of it". The fingerprint lists which declared assemblies the
    metadata lacks and the scan warns on it (ADR-0002: a fact, not a gate).
    """

    kind: str
    name: str
    class_names: tuple[str, ...] = ()
    method_names: tuple[tuple[str, str], ...] = ()   # (class, signature)
    strings: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not (self.class_names or self.method_names or self.strings)


@dataclass
class ProbeHit:
    probe_key: str
    kind: str
    corpus: str
    what: str          # the class / method / string that matched
    detail: str = ""


@dataclass
class ProbeRun:
    """One probe executed against one corpus. A fact -- never a judgement."""

    probe_key: str
    kind: str
    pattern: str
    values: tuple[str, ...]
    corpus: str
    slot: str
    origin: str                     # "pack" | "adhoc" | "direction"
    hit_count: int
    hits: tuple[ProbeHit, ...] = ()
    ran_at: float = 0.0

    @property
    def zero_hit(self) -> bool:
        return self.hit_count == 0

    def to_json(self) -> dict:
        return {
            "probe_key": self.probe_key,
            "kind": self.kind,
            "pattern": self.pattern,
            "values": list(self.values),
            "corpus": self.corpus,
            "slot": self.slot,
            "origin": self.origin,
            "hit_count": self.hit_count,
            # Hits are capped in the record: the point of the log is what was
            # searched and whether anything answered, not a full result dump.
            "hits": [
                {"what": h.what, "detail": h.detail} for h in self.hits[:MAX_RECORDED_HITS]
            ],
            "hits_truncated": max(0, self.hit_count - MAX_RECORDED_HITS),
            "ran_at": self.ran_at,
        }


MAX_RECORDED_HITS = 25


@dataclass
class ProbeReport:
    runs: list[ProbeRun] = field(default_factory=list)

    @property
    def zero_hit_runs(self) -> list[ProbeRun]:
        return [r for r in self.runs if r.zero_hit]

    def candidates(self) -> list[str]:
        seen: dict[str, None] = {}
        for run in self.runs:
            for hit in run.hits:
                seen.setdefault(hit.what, None)
        return list(seen)


def _now() -> float:
    return time.time()


def _match_regex(pattern: str, items: Iterable[str]) -> list[str]:
    compiled = re.compile(pattern)
    return [item for item in items if compiled.search(item)]


def execute(
    probe: Probe,
    corpus: Corpus,
    slot: str = "",
    origin: str = "pack",
) -> ProbeRun:
    """Run one probe against one corpus. Always returns a record, hits or not."""
    hits: list[ProbeHit] = []

    if probe.kind == "class_regex":
        for name in _match_regex(probe.pattern, corpus.class_names):
            hits.append(ProbeHit(probe.key(), probe.kind, corpus.kind, name))
    elif probe.kind == "method_regex":
        compiled = re.compile(probe.pattern)
        for class_name, signature in corpus.method_names:
            if compiled.search(signature):
                hits.append(
                    ProbeHit(probe.key(), probe.kind, corpus.kind, signature, class_name)
                )
    elif probe.kind == "string_const":
        wanted = {v for v in probe.values}
        for text in corpus.strings:
            if text in wanted:
                hits.append(ProbeHit(probe.key(), probe.kind, corpus.kind, text))

    return ProbeRun(
        probe_key=probe.key(),
        kind=probe.kind,
        pattern=probe.pattern,
        values=probe.values,
        corpus=corpus.kind,
        slot=slot,
        origin=origin,
        hit_count=len(hits),
        hits=tuple(hits),
        ran_at=_now(),
    )


def run_slot(slot_id: str, probes: Iterable[Probe], corpora: Iterable[Corpus]) -> ProbeReport:
    """Run every probe of a slot against every corpus. Zero hits are recorded."""
    report = ProbeReport()
    corpora = list(corpora)
    for probe in probes:
        for corpus in corpora:
            report.runs.append(execute(probe, corpus, slot=slot_id, origin="pack"))
    return report


def run_adhoc(probe: Probe, corpora: Iterable[Corpus], slot: str = "") -> ProbeReport:
    """The one door for improvised retrieval.

    Same executor, same record. An agent reaching for its own regex loop is how
    the accounting develops holes precisely where someone was exploring.
    """
    report = ProbeReport()
    for corpus in corpora:
        report.runs.append(execute(probe, corpus, slot=slot, origin="adhoc"))
    return report


# ── corpus construction ─────────────────────────────────────────────────────

def il2cpp_corpus(version: str = "", limit_strings: int = 0) -> Corpus:
    """Build the IL2CPP corpus from the loaded indices plus metadata strings."""
    from .indices import resolve_version

    class_names: list[str] = []
    methods: list[tuple[str, str]] = []
    try:
        vd = resolve_version(version or None)
    except Exception:
        return Corpus(kind=CORPUS_IL2CPP, name=version or "il2cpp")

    seen_classes: dict[str, None] = {}
    seen_methods: set[tuple[str, str]] = set()
    for entry in vd.rva_index.values():
        cls = entry.get("class") or ""
        sig = entry.get("signature") or ""
        if cls and cls not in seen_classes:
            seen_classes[cls] = None
            class_names.append(cls)
        if sig and (cls, sig) not in seen_methods:
            seen_methods.add((cls, sig))
            methods.append((cls, sig))

    strings = tuple(_metadata_strings(limit_strings))
    return Corpus(
        kind=CORPUS_IL2CPP,
        name=version or "il2cpp",
        class_names=tuple(class_names),
        method_names=tuple(methods),
        strings=strings,
    )


def _metadata_strings(limit: int = 0) -> list[str]:
    """String literals from global-metadata.dat.

    ISIL carries only metadata slot addresses, not string contents, so any probe
    that looks for a literal has to come here -- the index alone cannot answer it.
    """
    try:
        from .binary import find_global_metadata
        from .metadata import Il2CppMetadata
        meta = Il2CppMetadata(find_global_metadata().path)
    except Exception:
        return []
    count = meta.string_literal_count if not limit else min(limit, meta.string_literal_count)
    out: list[str] = []
    for i in range(count):
        value = meta.string_literal(i)
        if value:
            out.append(value)
    return out


def lua_corpus(version: str = "") -> Corpus:
    """Build a corpus from extracted Lua sources, when a title has them."""
    import os
    from .config import workspace_root

    root = os.path.join(workspace_root(), "lua", version) if version else ""
    if not root or not os.path.isdir(root):
        return Corpus(kind=CORPUS_LUA, name=version or "lua")

    names: list[str] = []
    strings: list[str] = []
    string_pat = re.compile(r"""["']([^"'\n]{2,80})["']""")
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if not fn.endswith((".lua", ".txt")):
                continue
            names.append(os.path.splitext(fn)[0])
            try:
                with open(os.path.join(dirpath, fn), encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except OSError:
                continue
            strings.extend(string_pat.findall(text))
    return Corpus(
        kind=CORPUS_LUA,
        name=version or "lua",
        class_names=tuple(dict.fromkeys(names)),
        strings=tuple(dict.fromkeys(strings)),
    )


def naming_statistics(corpus: Corpus, top: int = 40) -> list[tuple[str, int]]:
    """Frequent identifier fragments in a corpus.

    Feeds the zero-hit review: before a cell may be called "checked, genuinely
    absent", the agent has to hold the probe vocabulary up against how this
    particular game actually names things. Same statistic also seeds candidate
    vocabulary for a pack, so it is computed once and used twice.
    """
    from collections import Counter
    counter: Counter = Counter()
    token = re.compile(r"[A-Z][a-z0-9]+|[a-z0-9]{3,}")
    for name in corpus.class_names:
        for part in token.findall(name):
            if len(part) >= 3:
                counter[part] += 1
    return counter.most_common(top)
