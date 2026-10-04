"""Domain packs: a reusable investigation outline, on disk as a directory.

A pack is a `pack.yaml` plus one markdown file per slot. The front-matter is for
the harness (probes, facet trimming, thresholds); the body is for the person and
the agent (the question itself, what a good answer looks like, the usual traps).
Two readers, so two halves of one file.

Loaded from three layers that stack, later winning on the same id: the built-in
packs that ship with Revenant, the project's own overlay, and any third-party
packs named in revenant.toml. **Built-in packs are resolved at run time, never
copied into the project** -- the existing counter-example is the `re` skill being
copied into each project, where fixing it benefits only the project you fixed.
Overlay granularity is the slot, so adding one slot does not mean forking a pack.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from hashlib import sha256

from .methodology import FACETS, TIERS, CellId

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is declared, this is a guard
    yaml = None  # type: ignore

FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

EDGE_REQUIRES = "requires"   # not doing it first makes the answer wrong
EDGE_INFORMS = "informs"     # navigation only
EDGE_KINDS = (EDGE_REQUIRES, EDGE_INFORMS)


class PackError(ValueError):
    """A pack on disk is malformed."""


@dataclass(frozen=True)
class Probe:
    """One executable retrieval pattern.

    Patterns, never exact class names. A pack that names concrete classes cannot
    be reused on the next game -- the seeded hotspot config in the corpus is
    entirely `TODO-` placeholders for exactly this reason: the class names are
    only knowable after the first Cpp2IL run, which is the thing the pack is
    supposed to help you get to.
    """

    kind: str                  # class_regex | method_regex | string_const
    pattern: str = ""
    values: tuple[str, ...] = ()

    def key(self) -> str:
        return f"{self.kind}:{self.pattern}:{'|'.join(self.values)}"


PROBE_KINDS = ("class_regex", "method_regex", "string_const")

# Anything without a metacharacter is a literal, i.e. an exact class name.
_REGEX_METACHARS = set(".*+?[]{}()|^$\\")


@dataclass(frozen=True)
class FacetSpec:
    applicable: bool = True
    threshold: str = ""        # minimum tier for this cell to count as met
    ceiling: str = ""          # highest tier this kind of cell can ever reach


@dataclass(frozen=True)
class Slot:
    id: str
    title: str
    pack: str
    probes: tuple[Probe, ...] = ()
    facets: dict = field(default_factory=dict)   # facet -> FacetSpec
    body: str = ""
    source: str = ""

    def spec(self, facet: str) -> FacetSpec:
        return self.facets.get(facet, FacetSpec())

    def cells(self) -> list[CellId]:
        return [
            CellId(self.pack, self.id, facet)
            for facet in FACETS
            if self.spec(facet).applicable
        ]

    def probe_set_hash(self) -> str:
        """Identity of this slot's probes, for the ledger's idempotency key."""
        joined = "\n".join(sorted(p.key() for p in self.probes))
        return sha256(joined.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str


@dataclass
class Pack:
    name: str
    version: str = "0"
    description: str = ""
    root: str = ""
    slots: dict = field(default_factory=dict)     # slot id -> Slot
    edges: tuple[Edge, ...] = ()
    facet_defaults: dict = field(default_factory=dict)

    def slot(self, slot_id: str) -> Slot:
        if slot_id not in self.slots:
            raise PackError(f"pack {self.name!r} has no slot {slot_id!r}")
        return self.slots[slot_id]

    def cells(self) -> list[CellId]:
        out: list[CellId] = []
        for slot_id in sorted(self.slots):
            out.extend(self.slots[slot_id].cells())
        return out

    def unmet_requires(self, done: set[str]) -> list[Edge]:
        """`requires` edges whose source slot has not been answered.

        Reported, never enforced: reversing routinely cannot reach complete
        evidence, and a hard gate would wall people off. A warning that shows up
        in the coverage report is auditable, which blocking is not.
        """
        return [e for e in self.edges if e.kind == EDGE_REQUIRES and e.src not in done]


def _require_yaml():
    if yaml is None:
        raise PackError(
            "Reading domain packs needs PyYAML (pip install 'revenant-re[all]')."
        )


def _parse_probe(raw: dict, where: str) -> Probe:
    kind = str(raw.get("kind", "")).strip()
    if kind not in PROBE_KINDS:
        raise PackError(
            f"{where}: probe kind {kind!r} is not one of {', '.join(PROBE_KINDS)}"
        )
    pattern = str(raw.get("pattern", "") or "")
    values = tuple(str(v) for v in (raw.get("values") or ()))
    if kind in ("class_regex", "method_regex"):
        if not pattern:
            raise PackError(f"{where}: {kind} probe needs a `pattern`")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise PackError(f"{where}: probe pattern is not a valid regex: {exc}") from exc
        if not (_REGEX_METACHARS & set(pattern)):
            # The rule that keeps packs reusable. An exact name is a project
            # fact, and project facts belong in the project's overlay bindings.
            raise PackError(
                f"{where}: probe pattern {pattern!r} has no regex metacharacters, "
                f"so it is an exact name. Probes must be patterns -- exact class "
                f"names are only knowable after the first Cpp2IL run and do not "
                f"carry to the next game."
            )
    if kind == "string_const" and not values:
        raise PackError(f"{where}: string_const probe needs `values`")
    return Probe(kind=kind, pattern=pattern, values=values)


def _parse_facets(raw: dict, where: str) -> dict:
    out: dict = {}
    for facet, spec in (raw or {}).items():
        if facet not in FACETS:
            raise PackError(
                f"{where}: {facet!r} is not one of the six facets ({', '.join(FACETS)}). "
                f"Packs may trim facets; they may not add one."
            )
        spec = spec or {}
        threshold = str(spec.get("threshold", "") or "")
        ceiling = str(spec.get("ceiling", "") or "")
        for label, value in (("threshold", threshold), ("ceiling", ceiling)):
            if value and value not in TIERS:
                raise PackError(
                    f"{where}: {facet}.{label}={value!r} is not an evidence tier "
                    f"({', '.join(TIERS)})"
                )
        out[facet] = FacetSpec(
            applicable=bool(spec.get("applicable", True)),
            threshold=threshold,
            ceiling=ceiling,
        )
    return out


def load_slot(path: str, pack_name: str) -> Slot:
    _require_yaml()
    with open(path, encoding="utf-8") as f:
        text = f.read()
    match = FRONT_MATTER.match(text)
    if not match:
        raise PackError(f"{path}: slot file needs YAML front-matter delimited by ---")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except Exception as exc:
        raise PackError(f"{path}: front-matter is not valid YAML: {exc}") from exc
    slot_id = str(meta.get("id") or "").strip()
    if not slot_id:
        raise PackError(f"{path}: front-matter needs an `id`")
    probes = tuple(
        _parse_probe(p, f"{path} (probe {i})")
        for i, p in enumerate(meta.get("probes") or ())
    )
    return Slot(
        id=slot_id,
        title=str(meta.get("title") or slot_id),
        pack=pack_name,
        probes=probes,
        facets=_parse_facets(meta.get("facets") or {}, path),
        body=text[match.end():].strip(),
        source=path,
    )


def load_pack(root: str) -> Pack:
    """Load one pack directory."""
    _require_yaml()
    manifest_path = os.path.join(root, "pack.yaml")
    if not os.path.exists(manifest_path):
        raise PackError(f"{root} is not a pack directory (no pack.yaml)")
    with open(manifest_path, encoding="utf-8") as f:
        try:
            manifest = yaml.safe_load(f) or {}
        except Exception as exc:
            raise PackError(f"{manifest_path}: not valid YAML: {exc}") from exc

    name = str(manifest.get("name") or os.path.basename(root.rstrip("/")))
    edges: list[Edge] = []
    for raw in manifest.get("edges") or ():
        kind = str(raw.get("kind", EDGE_INFORMS))
        if kind not in EDGE_KINDS:
            raise PackError(f"{manifest_path}: edge kind {kind!r} not in {EDGE_KINDS}")
        src = str(raw.get("from") or "")
        for dst in raw.get("to") or ():
            edges.append(Edge(src=src, dst=str(dst), kind=kind))

    slots: dict = {}
    slots_dir = os.path.join(root, "slots")
    if os.path.isdir(slots_dir):
        for entry in sorted(os.listdir(slots_dir)):
            if not entry.endswith(".md"):
                continue
            slot = load_slot(os.path.join(slots_dir, entry), name)
            slots[slot.id] = slot

    return Pack(
        name=name,
        version=str(manifest.get("version", "0")),
        description=str(manifest.get("description") or ""),
        root=root,
        slots=slots,
        edges=tuple(edges),
        facet_defaults=_parse_facets(manifest.get("facet_defaults") or {}, manifest_path),
    )


def builtin_pack_root() -> str:
    """Where packs shipped with Revenant live, resolved at run time."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "packs")


def _overlay_root(project_root: str) -> str:
    return os.path.join(project_root, ".revenant", "packs")


def _merge(base: Pack, overlay: Pack) -> Pack:
    """Stack an overlay on a pack. Granularity is the slot, not the pack."""
    slots = dict(base.slots)
    slots.update(overlay.slots)
    return Pack(
        name=base.name,
        version=overlay.version if overlay.version != "0" else base.version,
        description=base.description or overlay.description,
        root=base.root,
        slots=slots,
        edges=tuple(list(base.edges) + list(overlay.edges)),
        facet_defaults={**base.facet_defaults, **overlay.facet_defaults},
    )


def discover(project_root: str, enabled: list[str] | None = None) -> dict:
    """Resolve enabled packs across the three layers. `{name: Pack}`.

    Packs are enabled explicitly in revenant.toml, never auto-detected: guessing
    wrong means silently skipping a whole area of the investigation, and for the
    candidate-pool machinery it would mean cross-genre vocabulary bleed.
    """
    if enabled is None:
        enabled = []

    layers: list[str] = [builtin_pack_root(), _overlay_root(project_root)]

    resolved: dict = {}
    for layer in layers:
        if not os.path.isdir(layer):
            continue
        for entry in sorted(os.listdir(layer)):
            root = os.path.join(layer, entry)
            if not os.path.isdir(root) or not os.path.exists(os.path.join(root, "pack.yaml")):
                continue
            pack = load_pack(root)
            if enabled and pack.name not in enabled:
                continue
            resolved[pack.name] = _merge(resolved[pack.name], pack) if pack.name in resolved else pack

    # Third-party packs named by path in revenant.toml.
    for path in enabled or ():
        if os.sep not in path and not path.startswith("."):
            continue
        root = path if os.path.isabs(path) else os.path.join(project_root, path)
        if os.path.isdir(root) and os.path.exists(os.path.join(root, "pack.yaml")):
            pack = load_pack(root)
            resolved[pack.name] = _merge(resolved[pack.name], pack) if pack.name in resolved else pack

    return resolved


def enabled_packs(project_config: dict) -> list[str]:
    """Pack names/paths enabled in revenant.toml (`[packs] enabled = [...]`)."""
    section = project_config.get("packs") or {}
    return [str(x) for x in (section.get("enabled") or [])]
