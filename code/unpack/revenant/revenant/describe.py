"""Self-description: what this build can do, taken from the code that does it.

The agent-facing documents used to be hand-written and copied into each project
at init. They drifted, and drifted in the worst possible place -- one round
added nine commands and replaced the whole evidence-tier table, and the shipped
skill kept teaching the abolished tiers to every new project.

So nothing here is written twice. The command list comes from the CLI's own
dispatch table and docstrings, the vocabulary comes from `methodology`, the
ledger contract comes from `ledger`, and the outline comes from whichever packs
the project has enabled. That is the `Description`, and it is harness-neutral.
A `Renderer` turns it into files for one harness -- `ClaudeRenderer` writes the
skill and the six slash commands, `CodexRenderer` writes the same skill, the
same six commands as on-demand skills, and a project-level MCP declaration --
and contains no methodology of its own, only formatting. The two read one
`Description`, so there is no second copy of the method to drift; what differs
between them is where a file lands and what its front-matter says, never what it
teaches. Every rendered file, on either harness, is under the same two guards
(commands it mentions exist, no retired vocabulary), and drift is decided by
comparing the rendered content with what is on disk (#37).

What is still hand-written is the part no code can produce: judgement about how
to do the work well ("read the control flow before the branches", "a placeholder
is correct behaviour, not a defect"). That lives in a separate file so it is
obvious at a glance which half updates itself.
"""

from __future__ import annotations

import hashlib
import importlib.resources as resources
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Protocol

from . import ledger as _ledger
from . import methodology as _m
from .__init__ import __version__

SCHEMA = 2

# Commands whose audience is the pipeline operator, not an analysing agent.
# Listed in the description, kept out of the agent's working surface.
_PIPELINE = {
    "init", "prepare", "status", "seed-src", "import-metadata", "patch-binary",
    "help", "describe",
}

# The main-line glossary of CONTEXT.md (the reverse-engineering vocabulary, not
# the agent-stack words and not the frozen scan family). `status` counts these
# against ADR-0002's proxy of six; a test keeps the list equal to CONTEXT.md.
CORE_TERMS = (
    "Target", "Project", "Evidence tier", "Scaffold", "Reconstruction",
    "Fingerprint", "Corpus", "Dig", "Table",
)


@dataclass
class Description:
    version: str = ""
    schema: int = SCHEMA
    commands: list = field(default_factory=list)
    mcp_tools: list = field(default_factory=list)
    methodology: dict = field(default_factory=dict)
    ledger: dict = field(default_factory=dict)
    project: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "schema": self.schema,
            "revenant_version": self.version,
            "commands": self.commands,
            "mcp_tools": self.mcp_tools,
            "methodology": self.methodology,
            "ledger": self.ledger,
            "project": self.project,
        }

    def command_names(self) -> set:
        return {c["name"] for c in self.commands}


def _summary(fn) -> str:
    doc = (fn.__doc__ or "").strip()
    return doc.splitlines()[0].strip() if doc else ""


def collect_commands(show_all: bool = False) -> list:
    """The visible CLI commands, straight from the dispatch table.

    Same rule as `revenant help` (ADR-0002): core always, the extension tier
    once a pack is enabled, the query tier with `show_all`.
    """
    from . import cli
    table = cli.command_table()
    out = []
    for name in sorted(cli.visible_commands(show_all=show_all)):
        out.append({
            "name": name,
            "summary": _summary(table[name]),
            "tier": cli.command_tier(name),
            "audience": "pipeline" if name in _PIPELINE else "analysis",
        })
    return out


def collect_mcp_tools() -> list:
    """The read-only MCP surface. Empty when the optional extra is absent."""
    try:
        from . import mcp_server
    except Exception:
        return []
    out = []
    for name in dir(mcp_server):
        if not name.startswith("re_"):
            continue
        fn = getattr(mcp_server, name)
        target = getattr(fn, "fn", fn)   # FastMCP wraps the callable
        if not callable(target):
            continue
        out.append({"name": name, "summary": _summary(target)})
    return sorted(out, key=lambda t: t["name"])


def collect_methodology(with_extension: bool = True) -> dict:
    """The fixed L2 vocabulary. One source, so a document cannot teach another.

    Tiers and the four states apply to every note. A state answers "what do we
    know about this question", which holds whether the question came from a
    pack slot or from a note -- a Cell is only one carrier of it, so gating the
    words on a pack left note authors with no vocabulary to declare a state in
    (ADR-0003). Facets are different: six fixed sections per slot *is* the pack
    machinery, and stays behind the gate with the rest of the frozen family.
    """
    out = {
        "tiers": [
            {
                "id": t, "title": _m.TIER_TITLES[t], "strength": _m.TIER_RANK[t],
                # What a note may write in brackets and have `lint` understand.
                # From the same table lint reads, so the two cannot disagree.
                "spellings": _m.tier_spellings(t),
            }
            for t in _m.TIERS
        ],
        "notes": {
            "tiers": (
                "Tier says which layer the evidence came from -- not how strong "
                "the inference is. Those are different axes; mixing them is how "
                "three projects ended up with three incompatible scales. Mark a "
                "claim with any spelling in the table, in brackets, on the same "
                "line as its source; `revenant lint` reads exactly these."
            ),
        },
    }
    out["cell_states"] = [{"id": s, "title": _m.STATE_TITLES[s]} for s in _m.STATES]
    out["reach_sources"] = list(_m.REACH_SOURCES)
    out["gap_markers"] = list(_m.KNOWN_GAP_MARKERS)
    out["notes"]["three_things"] = (
        "Tier belongs to a conclusion, state belongs to a question, and a gap "
        "marker belongs to a conclusion that holds but has a piece you "
        "cannot obtain. Keep them apart."
    )
    out["notes"]["states"] = (
        "A note declares its state in one HTML comment, which readers never "
        "see: `<!-- re-state: axis=econ slot=01 state=insufficient_evidence -->`. "
        "`axis` and `slot` are yours to define. `reach` says why the evidence "
        "cannot be reached and belongs only on `out_of_reach`; the two sources "
        "have opposite remedies, so an input-side gap re-queues itself once the "
        "input lands and an output-side doubt does not. `revenant lint` reads "
        "exactly these."
    )
    # Beside the states rather than behind the pack gate, and for the same
    # reason (ADR-0003): what a conclusion rests on is the same question whether
    # the cell came from a pack slot or from a note.
    out["notes"]["rests_on"] = (
        "A note that summarises several games declares the cells it is built "
        "on, in a second comment: "
        "`<!-- re-rests-on: axis=econ slot=07 expect=9 -->` -- \"this rests on "
        "axis=econ slot=07, and there should be 9 of them\". `expect` is how "
        "many games this round covers and is required: without it, finding one "
        "cell of nine reads exactly like finding all nine. `revenant lint "
        "--repo` then reports, separately, any of those cells that is not "
        "`meets_threshold` and any that has not been written yet -- the first "
        "means go find evidence, the second means go write the note. Write it "
        "when you claim something across games, not on a single-game note."
    )
    # Taught for the same reason the two markers above are: a rule that fires
    # against a format nobody was told about produces findings nobody can act
    # on. See ADR-0005 for why the memory is checked at all.
    out["notes"]["memory"] = (
        "What a loop tells you every round is a *memory*, and it is checked. "
        "A memory file is registered in `.claude/agent-memory/memory.toml` at "
        "the repository root -- not in a `revenant.toml`, because it belongs to "
        "no single project -- as `\"<path>\" = { kind = \"memory\", bytes = N }`; "
        "a file that is not listed is not checked, which is how an archive opts "
        "out. Every entry is one bullet: one sentence, then `→ `<note>`` and "
        "optionally `` `<anchor>` ``, where the anchor is a string that appears "
        "in that note. Never a line number -- the file this rule came from "
        "pointed at 「记忆第 435 行」 and by the time anyone read it that line "
        "said something else. Evidence lives in the note; the memory holds one "
        "sentence and the way back to it."
    )
    if not with_extension:
        return out
    out["facets"] = [{"id": f, "title": _m.FACET_TITLES[f]} for f in _m.FACETS]
    return out


def collect_ledger_contract() -> dict:
    """Which fields code may write, and which are the agent's alone."""
    return {
        "fact_fields": list(_ledger.FACT_FIELDS),
        "judgement_fields": list(_ledger.JUDGEMENT_FIELDS),
        "rule": (
            "Deterministic code writes facts only. Every judgement field is "
            "written through `revenant cell`, which validates it. A previous "
            "generation let a script write the completeness field and produced "
            "789 files stamped 'complete -- verified' by a regex that had never "
            "read an instruction."
        ),
        "run_field": (
            "`ran` is a field, not a fifth state: the four states say what we "
            "know about the game, `ran` says what we did."
        ),
    }


def collect_project() -> dict:
    """What this particular project has enabled. Empty outside a project."""
    try:
        from . import config, pack
        root = config.workspace_root()
        enabled = pack.enabled_packs(config.project_config())
        # ADR-0002: the scan family is visible only when `[packs] enabled` is
        # non-empty. (`pack.discover` itself resolves the built-in packs for an
        # empty list; that is the frozen family's own behaviour, left alone.)
        packs = pack.discover(root, enabled) if enabled else {}
    except Exception:
        return {"packs": []}

    out = []
    for name in sorted(packs):
        pk = packs[name]
        out.append({
            "name": name,
            "version": pk.version,
            "description": pk.description,
            "slots": [
                {
                    "id": slot_id,
                    "title": pk.slots[slot_id].title,
                    "cells": len(pk.slots[slot_id].cells()),
                }
                for slot_id in sorted(pk.slots)
            ],
            "cells": len(pk.cells()),
        })
    return {"packs": out}


def describe(include_project: bool = True, show_all: bool = False) -> Description:
    project = collect_project() if include_project else {"packs": []}
    with_extension = bool(project.get("packs"))
    return Description(
        version=__version__,
        commands=collect_commands(show_all=show_all),
        mcp_tools=collect_mcp_tools(),
        methodology=collect_methodology(with_extension=with_extension),
        # The ledger contract is the scan family's; absent until a pack is enabled.
        ledger=collect_ledger_contract() if with_extension else {},
        project=project,
    )


# ── rendering ───────────────────────────────────────────────────────────────

STAMP_PREFIX = "<!-- generated by revenant describe; version="


def stamp(version: str, digest: str = "") -> str:
    """`<!-- generated by revenant describe; version=X content=Y -->`.

    The version says which build wrote the file; the digest says what it wrote.
    Only the digest can catch a content change that kept the same version --
    and this package's version has never been bumped, so a version-equality
    check reported nothing while the rendered skill changed by 59 lines (#37).
    """
    head = f"{STAMP_PREFIX}{version}"
    if digest:
        head += f" content={digest}"
    return head + " -->"


def _stamp_on(line: str) -> str:
    """The stamp carried by this line, or "".

    A TOML file cannot hold an HTML comment, so `.codex/config.toml` writes the
    same stamp behind a `#`. One stamp shape read through two host languages,
    rather than a second format that would have to be kept in step with this one.
    """
    text = line.strip()
    if text.startswith("#"):
        text = text[1:].lstrip()
    return text if text.startswith(STAMP_PREFIX) else ""


def _stamp_lines(text: str) -> list[str]:
    return [found for line in text.splitlines() if (found := _stamp_on(line))]


def content_digest(text: str) -> str:
    """Digest of a generated document's body, the stamp line excluded.

    Excluded so that stamping cannot change the thing being stamped: the
    digest of a file is the digest of what the renderer produced, whichever
    build stamped it.
    """
    body = "\n".join(line for line in text.splitlines() if not _stamp_on(line))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]


def stamped_version(text: str) -> str:
    """The version a generated document was rendered from. "" if unstamped."""
    for line in _stamp_lines(text):
        return line[len(STAMP_PREFIX):].split()[0].strip()
    return ""


def stamped_digest(text: str) -> str:
    """The content digest a generated document carries. "" if it carries none.

    Empty for anything a pre-#37 build stamped; that is not an error, it just
    means the stamp cannot tell a hand edit from an older build.
    """
    for line in _stamp_lines(text):
        for token in line[len(STAMP_PREFIX):].split():
            if token.startswith("content="):
                return token[len("content="):].strip(" -->")
    return ""


def restamp(text: str, version: str) -> str:
    """Rewrite the document's stamp so its digest matches its body.

    Applied centrally to every renderer's output, so a renderer only has to
    place a stamp line -- it does not have to know how the digest is made.
    """
    digest = content_digest(text)
    out = []
    for line in text.splitlines():
        if not _stamp_on(line):
            out.append(line)
            continue
        # The comment marker belongs to the host language, not to the stamp:
        # rewriting it away leaves a TOML file with a line it cannot parse.
        marker = "# " if line.strip().startswith("#") else ""
        out.append(marker + stamp(version, digest))
    return "\n".join(out) + "\n"


_EXT_BEGIN = "<!-- extension:packs -->"
_EXT_END = "<!-- /extension:packs -->"


def _practice_text(with_extension: bool = False) -> str:
    """The hand-written half, shipped with the package.

    Folded in at render time rather than copied into a project, so an upgrade
    carries it everywhere. Splitting it out keeps it obvious which half of the
    rendered file updates itself. Blocks fenced by the extension markers belong
    to the frozen scan family and are dropped unless a pack is enabled.
    """
    try:
        text = resources.files("revenant").joinpath(
            "templates", "skill-practice.md").read_text(encoding="utf-8")
    except Exception:
        return ""
    out = []
    keep = True
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == _EXT_BEGIN:
            keep = with_extension
            continue
        if stripped == _EXT_END:
            keep = True
            continue
        if keep:
            out.append(line)
    return "\n".join(out).strip()


@dataclass(frozen=True)
class _HarnessText:
    """Everything in the skill that names a harness rather than a method.

    Two strings, and that is the whole of it: the rest of `_skill_markdown` is
    the same text on both harnesses, which is the point. The methodology has one
    source, and what differs between Claude Code and Codex is where files live,
    not what they say.
    """

    target: str          # what `revenant describe --render <target>` takes
    conventions: str     # the file revenant writes once and never overwrites


_CLAUDE_TEXT = _HarnessText("claude", ".claude/skills/re-project/SKILL.md")
_CODEX_TEXT = _HarnessText("codex", "AGENTS.md")


def _skill_markdown(desc: Description, practice: str,
                    harness: _HarnessText = _CLAUDE_TEXT) -> str:
    """The `re` skill, rendered from the description.

    Formatting only. Every fact below comes from `desc`, so this function cannot
    be the place where a stale tier table survives an upgrade.
    """
    lines: list[str] = []
    packs = desc.project.get("packs") or []
    with_extension = bool(packs)
    # The skill lists the core tier and, once a pack is enabled, the extension
    # tier -- the same rule as `revenant help` (ADR-0002). The query tier is
    # reached through the MCP tools listed above it.
    shown = [c for c in desc.commands if c.get("tier") in ("core", "extension")]
    analysis = [c for c in shown if c["audience"] == "analysis"]
    pipeline = [c for c in shown if c["audience"] == "pipeline"]

    lines.append("---")
    lines.append("name: re")
    lines.append(
        "description: Reverse-engineer a Unity IL2CPP / xLua game — reconstruct C# "
        "from assembly, "
        + ("run a schema-driven breadth scan, " if with_extension else "")
        + "drive a deep dive, and record findings under this project's evidence "
        "rules. Generated from the installed Revenant; do not hand-edit."
    )
    lines.append("---")
    lines.append("")
    lines.append(stamp(desc.version))
    lines.append("")
    lines.append("# Revenant")
    lines.append("")
    lines.append(
        "This file is generated. Re-render it after upgrading Revenant with "
        f"`revenant describe --render {harness.target}`; `revenant status` reports when it "
        "has fallen behind. Project-specific conventions belong in "
        f"`{harness.conventions}`, which is never overwritten."
    )
    lines.append("")
    lines.append("Call `re_status` first — the target, its architecture, and what "
                 "is built are all auto-detected.")

    if desc.mcp_tools:
        lines.append("")
        lines.append("## Read-only tools (MCP)")
        lines.append("")
        lines.append("| Tool | What it gives you |")
        lines.append("|------|-------------------|")
        for tool in desc.mcp_tools:
            lines.append(f"| `{tool['name']}` | {tool['summary']} |")

    lines.append("")
    lines.append("## Commands")
    lines.append("")
    lines.append("| Command | What it does |")
    lines.append("|---------|--------------|")
    for cmd in analysis:
        lines.append(f"| `revenant {cmd['name']}` | {cmd['summary']} |")
    lines.append("")
    lines.append("Pipeline commands (data prep, not analysis): "
                 + ", ".join(f"`{c['name']}`" for c in pipeline))

    m = desc.methodology
    lines.append("")
    lines.append("## Evidence rules")
    lines.append("")
    if with_extension:
        lines.append(m["notes"]["three_things"])
        lines.append("")
    lines.append("**Evidence tiers** — " + m["notes"]["tiers"])
    lines.append("")
    lines.append("| Tier | 中文 | Strength | Accepted spellings |")
    lines.append("|------|------|----------|--------------------|")
    for tier in m["tiers"]:
        spellings = " ".join(f"`[{s}]`" for s in tier["spellings"])
        lines.append(f"| `{tier['id']}` | {tier['title']} | {tier['strength']} | {spellings} |")

    # States are not pack vocabulary (ADR-0003): they say what we know about a
    # question, and a note asks questions as much as a pack slot does.
    lines.append("")
    lines.append("**States** — " + m["notes"]["states"])
    lines.append("")
    lines.append("| State | 中文 |")
    lines.append("|-------|------|")
    for state in m["cell_states"]:
        lines.append(f"| `{state['id']}` | {state['title']} |")
    lines.append("")
    lines.append(
        f"`out_of_reach` must say which side the gap is on: "
        + ", ".join(f"`{r}`" for r in m["reach_sources"])
        + ". The two have opposite remedies."
    )
    lines.append("")
    lines.append("**Gap markers** (a conclusion that holds, missing a piece you "
                 "cannot obtain): " + ", ".join(f"`{g}`" for g in m["gap_markers"]))
    lines.append("")
    lines.append("**What a cross-game conclusion rests on** — " + m["notes"]["rests_on"])
    lines.append("")
    lines.append("**What a loop remembers between rounds** — " + m["notes"]["memory"])

    if not with_extension:
        if practice:
            lines.append("")
            lines.append(practice)
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    # ── the frozen scan family, rendered only for projects that enabled a pack
    lines.append("")
    lines.append("## The ledger")
    lines.append("")
    lines.append(desc.ledger["rule"])
    lines.append("")
    lines.append(desc.ledger["run_field"])
    lines.append("")
    lines.append("- Facts (written by code): "
                 + ", ".join(f"`{f}`" for f in desc.ledger["fact_fields"]))
    lines.append("- Judgements (yours, via `revenant cell`): "
                 + ", ".join(f"`{f}`" for f in desc.ledger["judgement_fields"]))

    lines.append("")
    lines.append("## Facets")
    lines.append("")
    lines.append("Every slot is answered in these six sections. A pack may declare "
                 "one inapplicable; none may add a seventh.")
    lines.append("")
    for facet in m["facets"]:
        lines.append(f"- `{facet['id']}` — {facet['title']}")

    lines.append("")
    lines.append("## This project's outline")
    lines.append("")
    for pk in packs:
        lines.append(f"**{pk['name']}** v{pk['version']} — {pk['cells']} cells"
                     + (f". {pk['description']}" if pk['description'] else ""))
        lines.append("")
        for slot in pk["slots"]:
            lines.append(f"- `{slot['id']}` {slot['title']} ({slot['cells']} cells)")
        lines.append("")

    if practice:
        lines.append("")
        lines.append(practice)
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ── renderers ───────────────────────────────────────────────────────────────
#
# A renderer turns one Description (plus the hand-written practice text) into a
# set of files for one agent harness: {relative path: content}. The description
# is harness-neutral; everything harness-specific -- front-matter, file
# locations, the slash-command shape -- lives in the renderer. Adding a
# harness is a documented decision (ADR-0001), so the registry below is short
# on purpose -- two entries, one per harness the project actually maintains.

class Renderer(Protocol):
    name: str
    paths: tuple[str, ...]          # every file this renderer writes, project-relative

    def render(self, desc: Description, practice: str) -> dict[str, str]: ...


# Three further things a renderer may declare. The protocol above stays what it
# always was -- a name, the paths, and `render` -- because a test says so out
# loud: `test_a_second_renderer_needs_no_change_to_describe` drops in a renderer
# declaring exactly those three and nothing else, and it has to keep passing.
# So each of these answers from `paths` when the renderer is silent. The two
# shipped renderers state all three anyway: a file whose presence means "this
# harness is installed here" is worth saying rather than inferring from an
# ordering that could be reshuffled without anyone noticing.

def marker_of(harness: str) -> str:
    """The file whose presence says this harness is installed in a directory."""
    renderer = RENDERERS[harness]
    return getattr(renderer, "MARKER", renderer.paths[0])


def dir_of(harness: str) -> str:
    """The harness's own directory, project-relative. "" when it writes at the root."""
    marker = marker_of(harness)
    fallback = marker.split("/")[0] if "/" in marker else ""
    return getattr(RENDERERS[harness], "DIR", fallback)


def overlay_of(harness: str) -> str:
    """The conventions file revenant writes once and never again. "" when none."""
    return getattr(RENDERERS[harness], "OVERLAY", "")


COMMAND_NAMES = ("re-acquire", "re-scaffold", "re-deep", "re-verify", "re-map", "re-boundary")


class ClaudeRenderer:
    """Claude Code: the `re` skill and every slash-command template.

    The command templates used to be copied by `init` and never looked at
    again; they taught `T1`/`T3`, `(confirmed)` and `// Progress:` for as long
    as the skill did (#25). Rendering them all here puts them under the same two
    guards as the skill -- every command they mention exists, no retired
    vocabulary -- and the same content check `status` runs.
    """

    name = "claude"
    DIR = ".claude"
    SKILL = ".claude/skills/re/SKILL.md"
    COMMANDS = {c: f".claude/commands/{c}.md" for c in COMMAND_NAMES}
    MARKER = SKILL
    OVERLAY = _CLAUDE_TEXT.conventions
    paths = (SKILL, *COMMANDS.values())

    def render(self, desc: Description, practice: str) -> dict[str, str]:
        out = {self.SKILL: _skill_markdown(desc, practice)}
        for name, rel in self.COMMANDS.items():
            out[rel] = _command_markdown(name, desc)
        return out


class CodexRenderer:
    """Codex: the same `re` skill, plus one on-demand skill per command.

    Codex has no project-level prompt channel, so the six commands cannot be
    slash commands here -- each becomes a skill of its own and is chosen by the
    model from its description rather than started by a person. That is a real
    loss of the "entry point" half of what a Command is, taken deliberately
    (ADR-0001's 2026-08-19 revision) and said out loud in each rendered file.

    The MCP declaration is project-level and lands in `.codex/config.toml`. It
    holds nothing but the server entry: no `sandbox_mode`, no `approval_policy`.
    A permission file that only takes effect after a trust step the user has not
    taken yet is more misleading than no permission file at all -- and revenant
    does not do that trust step for them.
    """

    name = "codex"
    DIR = ".codex"
    SKILL = ".codex/skills/re/SKILL.md"
    COMMANDS = {c: f".codex/skills/{c}/SKILL.md" for c in COMMAND_NAMES}
    MCP = ".codex/config.toml"
    MARKER = SKILL
    OVERLAY = _CODEX_TEXT.conventions
    paths = (SKILL, *COMMANDS.values(), MCP)

    def render(self, desc: Description, practice: str) -> dict[str, str]:
        out = {self.SKILL: _skill_markdown(desc, practice, _CODEX_TEXT)}
        for name, rel in self.COMMANDS.items():
            out[rel] = _codex_command_skill(name, desc)
        out[self.MCP] = _codex_mcp_toml(desc)
        return out


RENDERERS: dict = {r.name: r for r in (ClaudeRenderer(), CodexRenderer())}

# `AGENTS.md` is loaded on every turn, from the git root down, and Codex caps
# the concatenation at `project_doc_max_bytes` (32 KiB by default). That makes
# it the third instance of ADR-0005's judgement -- a file whose capacity is
# itself the design constraint -- so `init` registers it for `lint` to check.
# The budget is the cap less a margin, because the cap is on the *sum* of every
# `AGENTS.md` from the repository root down to here.
CODEX_PROJECT_DOC_MAX_BYTES = 32 * 1024
AGENTS_MD_BUDGET = 24 * 1024

# Tokens a command template may use so its vocabulary comes from `methodology`
# rather than being typed in: `{{tier:disassembly}}` -> `[disassembly]`.
_TIER_TOKEN = re.compile(r"\{\{tier:([a-z_]+)\}\}")


def _command_template(name: str) -> str:
    """One shipped command template with its tier tokens resolved.

    One template per command, read by both renderers. The six say the same thing
    on either harness; only the file they land in and the front-matter above them
    differ, and a second copy of the text is exactly the drift this module exists
    to prevent. It sits under `templates/commands/` and no longer under
    `templates/claude/`, because it stopped being one harness's (#68).
    """
    text = resources.files("revenant").joinpath(
        "templates", "commands", f"{name}.md").read_text(encoding="utf-8")

    def _tier(match) -> str:
        tier = match.group(1)
        if tier not in _m.TIERS:
            raise ValueError(f"{name}.md names unknown tier {tier!r}")
        return f"[{tier}]"

    return _TIER_TOKEN.sub(_tier, text)


def _split_front_matter(name: str, lines: list[str]) -> tuple[list[str], list[str]]:
    """(front-matter lines including both fences, body lines). ([], lines) if none."""
    if not (lines and lines[0].strip() == "---"):
        return [], lines
    closes = [i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"]
    if not closes:
        raise ValueError(f"{name}.md opens front-matter and never closes it")
    return lines[:closes[0] + 1], lines[closes[0] + 1:]


def _front_matter_field(head: list[str], key: str) -> str:
    """One `key: value` out of a template's front-matter, or "".

    Deliberately not a YAML parse: the shipped templates are ours, three keys
    wide, and a dependency for reading `description:` out of six files we wrote
    is not a trade worth making.
    """
    for line in head:
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return ""


def _command_markdown(name: str, desc: Description) -> str:
    """One slash-command template: front-matter, then the stamp, then the body."""
    head, body = _split_front_matter(name, _command_template(name).splitlines())
    # Front-matter first (Claude reads it), then the stamp, then the body.
    lines = head + [stamp(desc.version), ""] + body
    return "\n".join(lines).rstrip() + "\n"


def _codex_command_skill(name: str, desc: Description) -> str:
    """One command as a Codex skill: its own front-matter, then the same body.

    A Command is an entry point a person starts, and that half of it does not
    survive the crossing: Codex has no project-level prompt channel, so the
    model picks this file from its description instead (CONTEXT.md's Command
    entry says so, ADR-0001's revision decided it). The file says so too, rather
    than letting a reader carry a guarantee across from the other harness that
    does not hold on this one.
    """
    head, body = _split_front_matter(name, _command_template(name).splitlines())
    what = _front_matter_field(head, "description")
    hint = _front_matter_field(head, "argument-hint")
    lines = ["---", f"name: {name}"]
    if what and not what.endswith("."):
        what += "."           # the templates write a title, and this is a sentence
    lines.append("description: " + what + (f" Say what to work on ({hint})." if hint else "")
                 + " Generated from the installed Revenant; do not hand-edit.")
    lines.append("---")
    lines.append("")
    lines.append(stamp(desc.version))
    lines.append("")
    lines.append(
        f"On Codex this command is a skill, not a slash command: nobody types "
        f"`/{name}`, the model reaches for this file from the description above. "
        f"Where the steps below write `$ARGUMENTS`, `$1` or `$2`, read them as "
        f"what you were asked to work on, in that order."
    )
    lines.append("")
    lines += body
    return "\n".join(lines).rstrip() + "\n"


def _codex_mcp_toml(desc: Description) -> str:
    """`.codex/config.toml`: the `re` server entry, wired to this interpreter.

    Project-level, so two reversing projects in different directories do not
    share one server. Only the server entry: the trust step that makes Codex
    read this file at all is the user's to take, and a permission block that
    silently does nothing until they take it is worse than none.
    """
    command = json.dumps(sys.executable)
    return "\n".join([
        f"# {stamp(desc.version)}",
        "# Generated by revenant; do not hand-edit -- `revenant status` reports",
        "# when it has fallen behind, and re-rendering discards edits made here.",
        "#",
        "# Codex reads this file only once you have trusted this repository in",
        "# your own $CODEX_HOME/config.toml. That is your call to make, so",
        "# revenant does not make it -- `revenant status` says when it is missing.",
        "",
        "[mcp_servers.re]",
        f"command = {command}",
        'args = ["-m", "revenant.mcp_server"]',
        "",
    ])


# `target` below is the *render* target, meaning the harness. CONTEXT.md reserves
# **Target** for the game being reversed, so everything that is not this
# long-standing pair of signatures says `harness` instead (#68).

def render(desc: Description, target: str) -> dict[str, str]:
    """{project-relative path: content} for one harness. KeyError on an unknown one."""
    renderer = RENDERERS[target]
    practice = _practice_text(with_extension=bool(desc.project.get("packs")))
    return {rel: restamp(text, desc.version)
            for rel, text in renderer.render(desc, practice).items()}


def rendered_paths(target: str) -> tuple[str, ...]:
    return tuple(RENDERERS[target].paths)


def write_rendered(root: str, target: str, desc: Description,
                   warn_empty_mcp: bool = True) -> list[str]:
    """Render and write every file for one harness; returns the paths written.

    An empty MCP surface is called out rather than rendered in silence. The
    tool table comes from importing `revenant.mcp_server`, which needs the
    optional `harness` extra; without it `collect_mcp_tools()` answers `[]`,
    which renders exactly like "this build has no read-only tools". One
    repository regenerated its shared skill from a venv missing the extra and
    would have dropped 22 rows for nine projects without a word. Same bargain
    as `lint`'s `no-index`: say what we could not see. Said once per run rather
    than once per harness (`warn_empty_mcp`): one missing extra is one fact, and
    repeating it per renderer reads like two problems.
    """
    if not desc.mcp_tools and warn_empty_mcp:
        print("revenant: the MCP tool table is empty, so the rendered skill "
              "teaches no read-only tools.\n"
              "          That is usually the optional extra missing rather than "
              "a build without them:\n"
              "          install it with `uv pip install 'revenant-re[harness]'` "
              "and render again.", file=sys.stderr)
    written = []
    for rel, content in render(desc, target).items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        written.append(path)
    return written


# Both harnesses look for their project files in the directory they start in
# *and in every parent up to the repository root*, so one copy at the top of a
# repository serves every project under it. `merge-games-re` keeps its nine
# titles in one repository and did exactly that: nine byte-identical copies
# deleted, one kept at the root. Revenant used to assume the generated files were
# always under the project root, which made that arrangement read as missing (#51).
HARNESS_MARKER = ClaudeRenderer.MARKER


def harness_root(project_root: str, harness: str = ClaudeRenderer.name) -> str:
    """The directory that carries this project's generated files for one harness.

    The project itself when it has its own copy, otherwise the nearest ancestor
    up to and including the git repository root that has one. Nearest wins, so a
    project cloned out on its own -- nothing above it -- gets its own root back
    and behaves exactly as it did before this existed.

    The only signal is whether that layer holds the rendered skill. No config
    option, and in particular no "which harness is this project on": #50's
    lesson is that a setting somebody has to remember does not get remembered,
    and here the thing to look for *is* the thing being looked for. Each harness
    is asked about separately, so a repository running both gets two answers and
    a repository running one is not asked about the other.
    """
    from . import config
    root = os.path.abspath(project_root)
    marker = marker_of(harness)
    # Bounded by the repository because both harnesses' own search is: a skill
    # above the repository root is never loaded, so pointing at one would
    # describe a loading behaviour that does not happen. The walk itself lives
    # in `config`, shared with the note sweep (#53) -- one boundary, one owner.
    for directory in config.up_to_repo_root(root):
        if os.path.exists(os.path.join(directory, marker)):
            return directory
    return root


def harness_installed(project_root: str, harness: str) -> bool:
    """Whether this project has one harness's files at all, here or above it.

    The harness's own directory, not the skill inside it: a project whose skill
    was deleted still has the harness installed and should be told the skill is
    missing, which is exactly the case a marker-only test would answer "not
    using Codex" to.
    """
    where = harness_root(project_root, harness)
    return os.path.exists(os.path.join(where, dir_of(harness)))


def installed_harnesses(project_root: str) -> list[str]:
    """Which harnesses this project has files for, named alphabetically."""
    return [name for name in sorted(RENDERERS)
            if harness_installed(project_root, name)]


def render_skill(desc: Description) -> str:
    """The Claude skill alone -- the renderer's first file."""
    return render(desc, ClaudeRenderer.name)[ClaudeRenderer.SKILL]


def as_json(desc: Description) -> str:
    return json.dumps(desc.to_json(), indent=1, ensure_ascii=False, sort_keys=True)
