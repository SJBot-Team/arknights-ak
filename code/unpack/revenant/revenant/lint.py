"""Note lint: check the three things that are objectively checkable, and stop.

The boundary is the point. A tier says which layer the evidence came from, and
that layer either exists or does not -- an RVA is in the index or it is not, a
class name resolves or it does not. Whether a conclusion was genuinely *read
out of* that assembly is not checkable by anything, and pretending otherwise
would hand out false assurance. So:

checked   -- referenced RVAs exist; referenced class/method names exist; a line
             that carries a bracketed tier also carries *some* source reference
             (an RVA, a symbol, a file, a bare identifier, another note --
             presence only, deliberately loose); a tier spelling is one the
             vocabulary knows
not checked -- "is this conclusion actually what that code does"

Reports, never blocks. Reversing routinely cannot reach complete evidence, and
the previous hard gate in this codebase (a hotspot documentation gate) was never
once satisfied and has been retired.

What counts as a tier marker is decided by `methodology.TIER_ALIASES`, not
here: real notes write `[Lua坐实]`, `[原生T1]`, a bare `T1` in a table cell,
and lint has to read the same vocabulary the skill teaches or it is checking
nothing. Before the alias table existed, 27 real notes produced 23 findings and
every one of them was the lint not recognising the note. Every rule below that
looks like a special case was put there by one of those 27 notes; the shape it
excuses is named next to it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .config import shared_label
from .methodology import (
    KNOWN_GAP_MARKERS, REACH_SOURCES, STATE_MEETS, STATE_OUT_OF_REACH, STATES,
    TIER_ALIASES, TIER_DISASSEMBLY, TIER_LOOKALIKE_HINTS, TIER_MANAGED_CODE, TIER_TITLES,
    TIERS, resolve_tier, tier_spellings,
)

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

# A bracketed tier marker: `[反汇编坐实]`, `[Lua坐实]`, `[原生T1]`, and the
# compound form one corpus writes, `[C#签名 + 待验证]` / `[原生T1/DEX普查]`.
BRACKET = re.compile(r"\[([^\[\]\n]{1,40})\]")
BRACKET_PARTS = re.compile(r"\s*(?:\+|/|、|,|，|;|；|\s)\s*")
# Inside a bracket, a part that is trying to be a tier but is not one we know
# (see methodology.TIER_LOOKALIKE_HINTS); a gap marker is left alone.
TIER_LOOKALIKE = re.compile(
    "|".join(re.escape(h) for h in TIER_LOOKALIKE_HINTS)
    + r"|(?<![A-Za-z0-9])T\d(?:\.\d)?(?![A-Za-z0-9])"
)
# A bare level: `（T1）`, `| T1 |`, `T1/T2`, `**T2**`. Only the retired numbered
# scale is accepted bare; the named tiers always wear brackets. It has to touch
# punctuation on at least one side -- `with ARM32 T1 evidence` in a running
# English sentence is a summary, not a tagged claim.
BARE_TIER = re.compile(r"(?<![\w.])(T\d(?:\.\d)?)(?![\w.])")
BARE_TIER_CONTEXT = set("（()）[]|、/,，:：*")
# The marker as the first thing on a line, followed by a colon or a bracket, is
# a definition-list entry: `- **T1** (ARM32 disassembly): ...`.
_ALIAS_ALT = "|".join(re.escape(k) for k in sorted(TIER_ALIASES, key=len, reverse=True))
DEFINITION = re.compile(r"^\s*(?:[-*]\s*)?\**\[?(?:" + _ALIAS_ALT + r")\]?\**\s*[:：(（]")

RVA_REF = re.compile(r"\b0x[0-9A-Fa-f]{4,}\b")
# `Namespace.Class.Method` or `Class.Method` in backticks -- the shape notes use.
SYMBOL_REF = re.compile(r"`([A-Za-z_][\w.`+<>]*\.[A-Za-z_]\w*)(?:\(\))?`")
# A source file, optionally with lines: `SDKHelper.lua:77,273-275`, `Foo.cs:83`.
# This is what a script-source or managed-code tier cites; it is a source, and
# it is not a symbol to look up in the index.
FILE_EXT = (
    "cs|lua|luac|java|kt|smali|dex|so|dylib|cpp|mm|swift|py|sh|js|ts|"
    "json|xml|plist|toml|yaml|yml|ini|cfg|csv|txt|md|dat|bin|bytes|asset|assets|"
    "bundle|proto|apk|xapk|ipa|aab|jar|aar|dll|pak|zip"
)
FILE_REF = re.compile(
    r"`(?:[\w.\-]+/)*[\w.\-]+\.(?:" + FILE_EXT + r")(?::[\d,\-]+)?`"
)
# A bare identifier in backticks: `AppsFlyerLib`, `BaseBoardModel:_DoMergeItem`,
# `requestTrackingAuthorizationWithCompletionHandler:`. A native / ObjC / Lua
# symbol has no dot, and citing it is citing a source.
IDENT_REF = re.compile(r"`([A-Za-z_][\w:$]{3,})`")
# A domain name (`payapi.cliapi.microfun.cn`) or an app id (`com.mergegame.icookie`)
# in backticks is neither a symbol nor a file: all lowercase, no class in it.
LOWERCASE_DOTTED = re.compile(r"^[a-z0-9_-]+(?:\.[a-z0-9_-]+)+$")
# A CamelCase type name in plain text (`WXInputFieldHelper / NetworkGetIps`):
# a diff note lists the types it counted without backticks. Presence only --
# never looked up in the index. Three capitals and eight characters, so that
# `GitHub` or `Cpp2IL` in prose does not pass for a citation.
CAMEL_IDENT = re.compile(
    r"(?<![\w`.])(?=[A-Za-z0-9]{8,}(?![\w`]))(?=(?:[a-z0-9]*[A-Z]){3})[A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*(?![\w`])"
)
# A reference to another note's conclusion: `arch-09 §3.2` or [see arch-10](...)
NOTE_REF = re.compile(
    r"(?:\b|\()((?:arch|core|econ|elem|rule|diff|cross|schema|plan|ref)-\d+[\w-]*)")

# Pointing back into this document instead of out at a source: `出处见第一节`,
# `同上`, `依据是上表`, `由上两行推得`. Positive detection alone cannot catch
# these -- the claim passes the moment it carries any identifier, and the
# identifier in these lines is the *object* of the back-reference rather than a
# source. See ADR-0006 for why a blacklist is worth the false-positive
# risk here, given this file already retreated from one.
BACKREFERENCE = re.compile(
    r"同上|同前|上表|上图|前文|如前所述"
    r"|(?:见|详见|出处见|依据见|依据是|参见|出处)\s*(?:上|前)"
    r"|(?:见|详见|出处见|依据见|依据是|参见|出处)[^\n，。；]{0,8}"
    r"第\s*[0-9一二三四五六七八九十]+(?:\.[0-9]+)?\s*[节章行条处段]"
    r"|由上[^\n]{0,6}推"
)

# The section the other rules hang on. Real notes title it several ways; all
# of these mean "here is where the evidence came from".
DATA_SOURCES_HEADING = re.compile(
    r"^#{1,6}\s*(数据来源|资料来源|来源|证据索引|技术参考|Data Sources|Sources|References)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
# A reproduce-commands section. Six of eight real projects grew one unprompted,
# so a note that reaches a conclusion is asked (a warning, never a gate) to
# carry one (#32).
#
# The keyword may sit anywhere in the heading, because real notes number their
# sections: `## 七、本轮新增的可复现命令` is the dominant shape (142 of 222
# headings in the corpus carry a numbered prefix). Anchoring the keyword right
# after the `#` made 3 of 13 warnings false (#43) -- the same failure #29 fixed
# for the sources heading. No `\b` either: it does not hold at a CJK boundary,
# which is how `## 复现要点` slipped through.
REPRODUCE_HEADING = re.compile(
    r"^#{1,6}\s.*(复现|重现|Reproduce|Reproduction|Repro)",
    re.MULTILINE | re.IGNORECASE,
)
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s")
FENCE = re.compile(r"^\s{0,3}(```|~~~)")
# A bullet that ends in a colon introduces the indented lines under it; they
# are the same claim, and its sources may live there.
CONTINUES = re.compile(r"[:：]\s*$")
INDENTED = re.compile(r"^\s+\S")
# A note names its own version near the top (`基线版本 **3.92.0**`, `v3.91.0`).
# When that version is indexed, its RVAs are checked against *that* index, not
# the project default -- an address from 3.91.0 is not "missing" in 3.92.0.
NOTE_VERSION = re.compile(r"\bv?(\d+\.\d+\.\d+)\b")
NOTE_VERSION_LINES = 8

# An address that is not a method start is accepted only when the same line
# also cites the start it lies inside (`re_evidence 0x009537DC, eor at
# 0x953890`): that is an instruction in a method the author has named. Without
# the start on the line, any address in the text segment would pass, and rule
# 1 -- the only mechanical catch for an invented address -- would be gone.
INSIDE_METHOD_WINDOW = 0x1000

# Files in notes/ that are not notes: an index has no conclusions to check.
NOT_A_NOTE = {"index.md", "readme.md"}

# What a finding from the repository root's own `notes/` is tagged with. The
# root is not a project, so it cannot wear a project's name -- and this
# repository already has one sentence for "this belongs to no single project"
# (#50), which is reused here rather than invented a second time.
ROOT_LABEL = shared_label("notes/")

# Where the repository keeps what the agent is told every round, and the file
# that says which of those are checked. It sits at the repository root and not
# in a `revenant.toml`, because the memory belongs to no single project -- the
# same fact, and the same answer, as the root's own `notes/` (#67). Giving the
# root a `revenant.toml` to hold this key would make it a project, which it is
# deliberately not.
MEMORY_DIR = os.path.join(".claude", "agent-memory")
MEMORY_REGISTRY = "memory.toml"
MEMORY_LABEL = shared_label(MEMORY_DIR.replace(os.sep, "/") + "/")
# Memory entries carry their evidence by pointer rather than by copy: one
# sentence, then where to go read it. `→` is the whole syntax.
# An entry is a top-level list item, bulleted or numbered. Numbered because the
# 171-entry file this rule was written for numbered every one of them: reading
# only `- ` would have left the pointer rules off on exactly the file that
# motivated them. Indented lines are continuation, and headings are the file
# talking about itself.
MEMORY_ENTRY = re.compile(r"^(?:[-*]|\d+\.)\s+(?P<body>.*)$")
MEMORY_POINTER = re.compile(
    r"→\s*`(?P<path>[^`]+?)`(?:\s*(?:的|,|，)?\s*`(?P<anchor>[^`]+?)`)?\s*$"
)


# What a note declares about itself, in HTML comments the reader never sees.
# Two of them so far, one syntax:
#
#   <!-- re-state: axis=econ slot=05 state=out_of_reach reach=input_missing -->
#   <!-- re-rests-on: axis=econ slot=07 expect=9 -->
#
# The first is this note's own terminal state (#53), the second is which cells a
# cross-game conclusion is built on (#67). `axis` and `slot` are the project's
# own in both -- which questions exist is a fact about the study, not about this
# tool (ADR-0003) -- so they are read and passed through, never validated.
# `state` and `reach` come from the shared vocabulary and are checked, for the
# same reason a tier spelling is: a typo must not silently found a fifth state.
# `expect` is how many games *this round of research* covers, which is again the
# project's fact and not something to count here (see `check_rests_on`).
#
# One pattern builder and one field regex for both, rather than a second pair
# that happens to agree: markers that look alike and are parsed separately agree
# only until one of them is edited.
STATE_FIELD = re.compile(r"(?P<key>[a-z]+)\s*=\s*(?P<value>[^\s>]+)")
RESTS_FIELDS = ("axis", "slot", "expect")


@dataclass(frozen=True)
class Marker:
    """One kind of self-declaration a note can carry, and how to complain about it.

    `hint` is appended to the repeated-key message: `gap=` is the only field
    either marker takes more than one value in, so only `re-state` has advice
    to give there.
    """

    name: str                  # what it is called in a note, and in the message
    rule: str                  # the finding rule its own malformations get
    hint: str = ""

    @property
    def pattern(self) -> re.Pattern:
        # `re` caches compiled patterns by source, so this is a dict lookup
        # after the first note; the marker is spelled once, here.
        return re.compile(rf"<!--\s*{re.escape(self.name)}:(?P<body>.*?)-->", re.S)


STATE_MARKER = Marker("re-state", "malformed-state-marker",
                      ", and separate multiple gap markers with commas")
RESTS_MARKER = Marker("re-rests-on", "malformed-rests-on-marker")


@dataclass
class Finding:
    path: str
    line: int
    severity: str
    rule: str
    message: str
    project: str = ""          # which project it belongs to; "" outside a sweep


@dataclass
class NoteState:
    """What one note declares about itself. Reported as a fact, not a check.

    Present for every note scanned, marker or not: a consumer that only saw the
    marked ones could not tell "wrote no marker" from "file is not there".
    """

    path: str
    project: str = ""
    axis: str = ""
    slot: str = ""
    state: str = ""
    reach: str = ""
    gaps: list = field(default_factory=list)
    # What this note says its conclusion is built on, verbatim: `{}` when it
    # declares nothing. A declaration, like the state above -- the checking of
    # it happens later and elsewhere (`check_rests_on`).
    rests_on: dict = field(default_factory=dict)
    rests_line: int = 0        # where that marker sits, for the findings to point at


@dataclass
class LintReport:
    findings: list = field(default_factory=list)
    files: int = 0
    notes: list = field(default_factory=list)

    @property
    def errors(self) -> list:
        return [f for f in self.findings if f.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list:
        return [f for f in self.findings if f.severity == SEVERITY_WARNING]

    def add(self, *args, **kwargs) -> None:
        self.findings.append(Finding(*args, **kwargs))


@dataclass
class Symbols:
    """What the indices say exists. Empty means "cannot check", not "nothing".

    An empty index must not turn every reference in every note into an error --
    that would be reporting our own missing setup as the author's mistake.
    """

    rvas: set = field(default_factory=set)
    classes: set = field(default_factory=set)
    methods: set = field(default_factory=set)
    loaded: bool = False
    version: str = ""

    def has_rva(self, raw: str) -> bool:
        return _norm_rva(raw) in self.rvas

    def inside_cited_method(self, raw: str, cited: list) -> bool:
        """`raw` lies just after one of the `cited` addresses that is a method start."""
        try:
            value = int(raw, 16)
        except ValueError:
            return False
        for other in cited:
            if other == raw or not self.has_rva(other):
                continue
            start = int(other, 16)
            if 0 < value - start <= INSIDE_METHOD_WINDOW:
                return True
        return False


def _ensure_loaded(version: str) -> bool:
    """Load `_refs/<version>/cpp2il_out` on demand; True if that version is indexed."""
    from .indices import VERSIONS, load_version

    if version in VERSIONS:
        return True
    try:
        from .config import version_ref_dir
        root = os.path.join(version_ref_dir(version), "cpp2il_out")
    except Exception:
        return False
    if not os.path.isfile(os.path.join(root, "rva_index.json")):
        return False
    load_version(version, root)
    return True


def load_symbols(version: str = "") -> Symbols:
    from .indices import resolve_version, VERSIONS

    if version:
        _ensure_loaded(version)
    try:
        vd = resolve_version(version or None)
    except Exception:
        return Symbols()
    rvas: set = set()
    classes: set = set()
    methods: set = set()
    for key, entry in vd.rva_index.items():
        rvas.add(_norm_rva(key))
        cls = entry.get("class") or ""
        sig = entry.get("signature") or ""
        if cls:
            classes.add(cls)
            classes.add(cls.split(".")[-1])
        name = _method_name(sig)
        if cls and name:
            methods.add(f"{cls}.{name}")
            methods.add(f"{cls.split('.')[-1]}.{name}")
    resolved = next((k for k, v in VERSIONS.items() if v is vd), version)
    return Symbols(
        rvas=rvas, classes=classes, methods=methods, loaded=bool(rvas or classes),
        version=resolved,
    )


def _norm_rva(text: str) -> str:
    return text.lower().lstrip("0x").lstrip("0") or "0"


_METHOD_NAME = re.compile(r"([A-Za-z_]\w*)\s*\(")


def _method_name(signature: str) -> str:
    match = _METHOD_NAME.search(signature or "")
    return match.group(1) if match else ""


def note_version(text: str) -> str:
    """The version a note says it is about, if it says so near the top."""
    head = "\n".join(text.splitlines()[:NOTE_VERSION_LINES])
    for candidate in NOTE_VERSION.findall(head):
        if _ensure_loaded(candidate):
            return candidate
    return ""


# ── tier vocabulary on one line ─────────────────────────────────────────────

@dataclass
class TierMarks:
    """The tier vocabulary one line carries.

    `known` are the spellings that resolve to a tier (in the order seen);
    `unknown` are bracketed look-alikes and bare `T4`-style levels that do
    not. `tiers` is the set of distinct tiers. Two or more on one line is a
    legend (every real note opens with one: "标 [C#签名](T2)、[Lua坐实](T2)…"),
    not a claim, and is not asked to cite a source.
    """

    known: list = field(default_factory=list)      # spellings that resolve, in order seen
    unknown: list = field(default_factory=list)    # look-alikes that do not
    bracketed: list = field(default_factory=list)  # the subset of `known` in brackets
    definition: bool = False                       # `- **T1** (...): ...` -- a definition-list entry

    @property
    def tiers(self) -> set:
        return {resolve_tier(k) for k in self.known}

    @property
    def is_legend(self) -> bool:
        return self.definition or len(self.tiers) >= 2


def tier_marks(line: str) -> TierMarks:
    marks = TierMarks()
    for content in BRACKET.findall(line):
        parts = [p for p in BRACKET_PARTS.split(content) if p]
        known = [p for p in parts if resolve_tier(p)]
        marks.known.extend(known)
        marks.bracketed.extend(known)
        # `[C#签名 + 待验证]` is understood through its known half; only a
        # bracket with a tier look-alike and *no* known part is a misspelling.
        if not known:
            for part in parts:
                if TIER_LOOKALIKE.search(part):
                    marks.unknown.append(f"[{content}]")
                    break
    # Bare levels are searched with the bracketed markers blanked out, so the
    # `T1` inside `[原生T1]` is not counted twice.
    rest = BRACKET.sub(lambda m: " " * len(m.group(0)), line)
    for match in BARE_TIER.finditer(rest):
        if not _touches_punctuation(rest, match.start(), match.end()):
            continue
        spelling = match.group(1)
        if resolve_tier(spelling):
            marks.known.append(spelling)
        else:
            marks.unknown.append(spelling)
    if marks.known and DEFINITION.match(line):
        marks.definition = True
    return marks


def _touches_punctuation(text: str, start: int, end: int) -> bool:
    before = text[:start].rstrip()
    after = text[end:].lstrip()
    return (bool(before) and before[-1] in BARE_TIER_CONTEXT) or (
        bool(after) and after[0] in BARE_TIER_CONTEXT
    )


def _known_spellings() -> str:
    return "; ".join(
        f"{TIER_TITLES[t]}: " + ", ".join(tier_spellings(t, include_retired=True)) for t in TIERS
    )


# The index is built from the managed metadata, so it can only vouch for
# symbols a disassembly or managed-code tier cites. A `[Lua坐实]` line cites
# Lua; the index has never heard of it and must not say it is missing.
_INDEXED_TIERS = {TIER_DISASSEMBLY, TIER_MANAGED_CODE}


def _cites_something(text: str) -> bool:
    """Any citation at all, the deliberately loose test rule 3 is built on."""
    return bool(
        _cites_outward(text) or IDENT_REF.search(text) or CAMEL_IDENT.search(text)
    )


def _cites_outward(text: str) -> bool:
    """A citation that names something outside this document.

    The two identifier forms are deliberately excluded. A bare name in
    backticks is a source when it stands on its own (`AppsFlyerLib`), but in
    "出处见第一节，`merge_score_race` 那一列" it is what the back-reference is
    pointing *at*, not where the value was read. Everything else -- an
    address, a dotted symbol, a file, another note -- names a place a reader can
    open.
    """
    return bool(
        RVA_REF.search(text) or SYMBOL_REF.search(text) or FILE_REF.search(text)
        or NOTE_REF.search(text)
    )


def _cited_notes(text: str) -> list:
    """The `.md` paths a line cites, unbackticked.

    Only `.md`. Everything else `FILE_REF` matches -- `res/conf-json/*.json`,
    `src/<ver>/**.cs`, `lua/<ver>/**.lua` -- is extracted material that is
    gitignored and routinely absent on a machine that has not run `prepare`.
    Reporting that as a dangling citation would say the author invented a path
    when the truth is we never unpacked it, which is exactly the wrong answer
    `no-index` exists to avoid giving.
    """
    out = []
    for raw in FILE_REF.findall(text):
        cleaned = raw.strip("`").split(":")[0]
        if cleaned.lower().endswith(".md"):
            out.append(cleaned)
    return out




def _note_bases(path: str) -> list:
    """Where a cited path may be rooted: beside the note, its project, the repo.

    All three are in real use and which one a given citation means is not
    knowable from the string: a bare `econ-01-currency.md` is the sibling in the
    same `notes/`, `notes/econ-10-social.md` is rooted at the project,
    `gossip-harbor/notes/econ-10-social.md` at the repository, and
    `../../notes/ref-02-....md` walks up from the note itself. Trying all of
    them and accepting any is the reading that does not invent a finding out of
    a convention difference -- the sibling form alone accounted for 54 of them
    on the corpus this rule was measured against.
    """
    from .config import repo_root_of
    here = os.path.dirname(os.path.abspath(path))
    project = os.path.dirname(here)
    bases = [here, project]
    repo = repo_root_of(project)
    if os.path.normpath(repo) not in {os.path.normpath(b) for b in bases}:
        bases.append(repo)
    bases.extend(_repo_note_dirs(repo))
    seen, out = set(), []
    for base in bases:
        key = os.path.normpath(base)
        if key not in seen:
            seen.add(key)
            out.append(base)
    return out


def _repo_note_dirs(repo: str) -> list:
    """Every `notes/` in the repository: the root's own, and each project's.

    A bare `econ-05-orders.md` in a cross-game summary means "the note of that
    name in each of the nine", and a same-source pair cites its twin's note the
    same way. Neither is a path, and neither is wrong. Bounded to the root and
    its immediate children on the same grounds as `repo_projects` -- a real
    repository has hundreds of thousands of extracted files below this, and a
    citation check must not pay for a tree walk.

    Membership is "has a `notes/`", not `repo_projects`' "has a `revenant.toml`",
    and the difference is deliberate: the repository root holding the fourteen
    cross-game summaries is exactly the directory that has the first and not the
    second (#67). Asking for the project marker here would put the notes most
    likely to be cited out of reach of the citation check.

    Not cached. `lint_repo` promises the sweep "should leave no trace" and
    restores what it borrows; a process-lifetime dict of which directories
    exist is a trace, and directory existence is not a fact that stays true.
    One `listdir` per note is nothing against reading the note itself.
    """
    out = []
    root_notes = os.path.join(repo, "notes")
    if os.path.isdir(root_notes):
        out.append(root_notes)
    try:
        names = sorted(os.listdir(repo))
    except OSError:
        names = []
    for name in names:
        child = os.path.join(repo, name, "notes")
        if os.path.isdir(child):
            out.append(child)
    return out


def _cited_symbols(line: str) -> list:
    out = []
    for symbol in SYMBOL_REF.findall(line):
        clean = symbol.strip("`")
        if FILE_REF.fullmatch(f"`{clean}`") or LOWERCASE_DOTTED.match(clean):
            continue
        out.append(clean)
    return out


def _one_marker(marker: Marker, path: str, text: str,
                report: LintReport) -> tuple | None:
    """The fields of the one `marker` in `text`, and its line. None if absent.

    Both markers share this because they share a syntax and both ways of losing
    data in silence: a second marker, and a repeated key. Neither is resolved --
    silently keeping the last of `gap=a gap=b` drops `a` with nothing to show
    for it, and there is no reading of a repeated `state=` that is obviously
    right.
    """
    marks = list(marker.pattern.finditer(text))
    if not marks:
        return None
    mark = marks[0]
    number = text[:mark.start()].count("\n") + 1
    if len(marks) > 1:
        report.add(path, text[:marks[1].start()].count("\n") + 1,
                   SEVERITY_ERROR, marker.rule,
                   f"a second {marker.name} marker; a note carries one, and the "
                   f"rest would be read by nobody")
    fields: dict = {}
    for found in STATE_FIELD.finditer(mark["body"]):
        key, value = found["key"], found["value"]
        if key in fields:
            report.add(path, number, SEVERITY_ERROR, marker.rule,
                       f"{key}= given more than once; write one{marker.hint}")
            continue
        fields[key] = value
    return fields, number


def _read_rests_on(path: str, text: str, report: LintReport, entry: NoteState) -> None:
    """Record which cells this note says it rests on, and check it says it fully.

    Only the marker's own spelling is checked here. Whether those cells are
    filled in is a question about *every* project at once, so it is asked after
    the sweep (`check_rests_on`) -- one note on its own cannot answer it.

    All three fields are required, and for the same reason: without them the
    declaration is unfalsifiable. No `axis` or no `slot` and the marker names
    every note that declared no state at all; no `expect` and a note claiming
    nine games passes quietly on finding one, because a walk that finds nothing
    and a lookup that was mistyped return the same empty answer.
    """
    found = _one_marker(RESTS_MARKER, path, text, report)
    if found is None:
        return
    fields, number = found
    entry.rests_on = {key: fields.get(key, "") for key in RESTS_FIELDS}
    entry.rests_line = number
    rule = RESTS_MARKER.rule
    for key in ("axis", "slot"):
        if not entry.rests_on[key]:
            report.add(path, number, SEVERITY_ERROR, rule,
                       f"re-rests-on declares no {key}=; without it the marker "
                       f"names no particular cells and nothing can be checked")
    expect = entry.rests_on["expect"]
    if not expect:
        report.add(path, number, SEVERITY_ERROR, rule,
                   "re-rests-on declares no expect=; how many games this round "
                   "covers is a fact about the research, and without it finding "
                   "one of nine reads the same as finding all nine")
    elif not _positive_int(expect):
        report.add(path, number, SEVERITY_ERROR, rule,
                   f"expect={expect} is not a count; read as 0 it would make "
                   f"every comparison pass forever, so it is reported instead")


def _positive_int(value: str) -> int:
    """`value` as a count, or 0 when it is not one. Never guesses."""
    try:
        number = int(value)
    except ValueError:
        return 0
    return number if number > 0 else 0


def _read_state(path: str, text: str, report: LintReport) -> NoteState:
    """Record the note's declared state, and check the words it used.

    One rule per way of getting it wrong, because each has its own fix and the
    rule name is now part of a machine contract -- a consumer filtering the JSON
    cannot act on a rule that means four different things:

    `unknown-state` / `unknown-reach` are the bargain `unknown-tier` strikes:
    an unrecognised word is reported so a typo cannot quietly found a fifth
    state. `unknown-gap-marker` is the same bargain at warning strength, because
    that vocabulary is open by design -- an unknown marker is allowed, it just
    may not become a new category unnoticed (`ledger` reports it the same way).
    `reach-without-out-of-reach` is structural: `reach` says *why* the evidence
    cannot be reached, so on any other state it is noise that reads like a fact.
    `malformed-state-marker` covers the two shapes that would otherwise lose
    data in silence -- a second marker, and a repeated key -- both of which are
    caught in `_one_marker`, since the other marker loses data the same ways.
    """
    found = _one_marker(STATE_MARKER, path, text, report)
    entry = NoteState(path=path)
    # Recorded whether or not the marker is there, and before any of the checks
    # below can return: a consumer that only saw the marked notes could not tell
    # "wrote no marker" from "file is not there".
    report.notes.append(entry)
    if found is None:
        return entry
    fields, number = found
    entry.axis = fields.get("axis", "")
    entry.slot = fields.get("slot", "")
    entry.state = fields.get("state", "")
    entry.reach = fields.get("reach", "")
    entry.gaps = [g for g in fields.get("gap", "").split(",") if g]

    known = ", ".join(f"`{s}`" for s in STATES)
    if not entry.state:
        report.add(path, number, SEVERITY_ERROR, "unknown-state",
                   f"re-state marker declares no state=; one of {known} is required")
    elif entry.state not in STATES:
        report.add(path, number, SEVERITY_ERROR, "unknown-state",
                   f"unknown state {entry.state!r}; accepted states are {known}")
    if entry.reach and entry.reach not in REACH_SOURCES:
        report.add(path, number, SEVERITY_ERROR, "unknown-reach",
                   f"unknown reach source {entry.reach!r}; accepted sources are "
                   + ", ".join(f"`{r}`" for r in REACH_SOURCES))
    if entry.reach and entry.state and entry.state != STATE_OUT_OF_REACH:
        report.add(path, number, SEVERITY_ERROR, "reach-without-out-of-reach",
                   f"reach={entry.reach} says why the evidence cannot be reached, but "
                   f"the state is {entry.state}; it is only meaningful on "
                   f"`{STATE_OUT_OF_REACH}`")
    for gap in entry.gaps:
        if gap not in KNOWN_GAP_MARKERS:
            report.add(path, number, SEVERITY_WARNING, "unknown-gap-marker",
                       f"gap marker {gap!r} is not one of the known ones ("
                       + ", ".join(f"`{g}`" for g in KNOWN_GAP_MARKERS)
                       + "); allowed, but say so on purpose rather than by typo")
    return entry


def lint_note(path: str, symbols: Symbols, report: LintReport,
              per_version: dict | None = None) -> None:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.splitlines()
    report.files += 1
    bases = _note_bases(path)

    # A note about another indexed version is checked against that version.
    own = note_version(text)
    if own and own != symbols.version and per_version is not None:
        if own not in per_version:
            per_version[own] = load_symbols(own)
        symbols = per_version[own]

    entry = _read_state(path, text, report)
    _read_rests_on(path, text, report, entry)

    # Rule 3 (structure): the data-sources section is where the other rules hang.
    sources_heading = DATA_SOURCES_HEADING.search(text)
    if not sources_heading:
        report.add(
            path, 0, SEVERITY_ERROR, "data-sources",
            "no 「数据来源」 section -- the other checks have nowhere to look, so "
            "every RVA and symbol reference in this note is unverifiable",
        )

    in_sources = False
    sources_level = 0
    in_fence = False
    carried_tier = False
    for number, line in enumerate(lines, start=1):
        # Fenced blocks are code, diagrams and traces, not claims: a mermaid
        # label reading `"(部分客户端坐实)"` is not a tier marker.
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if DATA_SOURCES_HEADING.match(line):
                in_sources, sources_level = True, level
            elif in_sources and level <= sources_level:
                in_sources = False

        marks = tier_marks(line)
        if not marks.known and not marks.unknown:
            continue

        # Rule 4: a tier spelling the vocabulary does not know. A legend line
        # may name the retired T4 while explaining what it maps to; that is a
        # definition, not a claim, and is left alone.
        if marks.unknown and not marks.is_legend:
            report.add(
                path, number, SEVERITY_ERROR, "unknown-tier",
                f"unknown tier spelling {', '.join(marks.unknown)}; accepted spellings are "
                f"{_known_spellings()}",
            )
        if not marks.known:
            continue
        carried_tier = True

        claim = line
        if CONTINUES.search(line):
            for follow in lines[number:]:
                if not INDENTED.match(follow):
                    break
                claim += "\n" + follow
        has_source = _cites_something(claim)

        # Rule 3: a tier without any source reference.
        #
        # A reference to another note counts. Whole documents in the corpus are
        # pure adjudication -- every claim resting on a cited conclusion in a
        # sibling note -- and calling those non-compliant would be wrong. A
        # cited source file (`SDKHelper.lua:77`) or symbol counts: that is
        # exactly what a script-source tier is. Not asked to cite: a heading
        # (its tier scopes the section under it), a legend line (it defines
        # the vocabulary), and any line inside the data-sources section (that
        # section *is* the sources). The only illegal shape is a claim with no
        # source at all.
        #
        # Only a bracketed marker is held to this. A bare `（T1）` is the
        # retired scale annotating the strength of a sentence; that scheme
        # never had a cite-on-the-line convention, and asking for one after
        # the fact flags 114 sentences across eight real projects -- the same
        # worthless-lint failure in the other direction. Bare levels still get
        # their RVAs and symbols checked, and an unknown level is still an
        # error; the skill teaches brackets, so new notes meet the strict rule.
        if not has_source:
            if marks.bracketed and not (marks.is_legend or heading or in_sources):
                report.add(
                    path, number, SEVERITY_ERROR, "tier-without-source",
                    f"carries a tier ({marks.known[0]}) but cites no RVA, no symbol, "
                    f"no source file and no other note",
                )
            continue

        # Rule 3b: the source is a back-reference, and the only thing that made
        # it look like a citation is a bare identifier the back-reference is
        # pointing at. A warning, not an error: a blacklist is the one shape of
        # rule this file has been burned by before (the bare `T1` retreat above),
        # so it earns its severity by being right in the field first.
        if (marks.bracketed and not (marks.is_legend or heading or in_sources)
                and BACKREFERENCE.search(claim) and not _cites_outward(claim)):
            report.add(
                path, number, SEVERITY_WARNING, "backreference-as-source",
                "points back into this document for its source; the identifier on "
                "this line is what the reference points at, not where the value "
                "was read -- cite a file, an RVA, a symbol or another note",
            )

        # Rule 3c: a cited note has to be there. An RVA is looked up and a
        # symbol is looked up; a path was only ever pattern-matched, so a
        # citation could name a note that never existed and still read as
        # evidence.
        #
        # `NOTE_REF`'s bare shorthand (`arch-09 §3.2`) is deliberately *not*
        # looked up, though the asymmetry argument reaches it too. It was tried:
        # three of this file's own tests fail on it -- all three assert that a
        # note citing only its siblings is compliant, which is the shape ADR-0003
        # calls pure adjudication -- and the real corpus produced 50 findings,
        # every one of them `cross-07-progression` matched inside
        # `econ-cross-07-progression`. A prefix without a suffix cannot be told
        # from a suffix, and the doc comment on rule 3 already promises this form
        # is "presence only, deliberately loose".
        for cited in _cited_notes(claim):
            if not any(os.path.exists(os.path.join(base, cited)) for base in bases):
                report.add(
                    path, number, SEVERITY_ERROR, "cited-note-missing",
                    f"cites `{cited}`, which is not there",
                )

        if not symbols.loaded:
            continue
        # Rule 1: referenced RVAs must exist.
        cited_rvas = RVA_REF.findall(line)
        for raw in cited_rvas:
            if not symbols.has_rva(raw) and not symbols.inside_cited_method(raw, cited_rvas):
                report.add(
                    path, number, SEVERITY_ERROR, "rva-not-found",
                    f"{raw} is not in the index for version {symbols.version or '(default)'}",
                )
        # Rule 2: referenced class/method names must exist -- only for tiers the
        # index can vouch for.
        if not marks.tiers <= _INDEXED_TIERS:
            continue
        for clean in _cited_symbols(line):
            if clean in symbols.methods or clean in symbols.classes:
                continue
            head = clean.rsplit(".", 1)[0]
            if head in symbols.classes:
                continue
            report.add(
                path, number, SEVERITY_WARNING, "symbol-not-found",
                f"`{clean}` does not resolve in the index for version "
                f"{symbols.version or '(default)'}",
            )

    # Convention (#32): a note that reaches a tiered conclusion should say how
    # to reproduce it. A warning, never a gate -- six of eight real projects
    # grew this section on their own, so it is a norm being written down, not a
    # new demand.
    if carried_tier and not REPRODUCE_HEADING.search(text):
        report.add(
            path, 0, SEVERITY_WARNING, "no-reproduce",
            "reaches a conclusion but has no 「复现命令」 section -- a reader "
            "cannot re-run what produced it",
        )


def lint_notes(paths: list[str], version: str = "") -> LintReport:
    symbols = load_symbols(version)
    per_version: dict = {}
    report = LintReport()
    for path in paths:
        lint_note(path, symbols, report, per_version)
    if not symbols.loaded:
        report.add(
            "", 0, SEVERITY_WARNING, "no-index",
            "no index loaded, so RVA and symbol existence were not checked "
            "(run `revenant prepare` first)",
        )
    return report


def project_label(project_root: str) -> str:
    """How a project is named across a sweep: its path below the repository root."""
    from .config import repo_root_of
    return os.path.relpath(project_root, repo_root_of(project_root))


def repo_projects(start: str) -> list[str]:
    """Every project under the repository root above `start`, nearest first.

    A project is a directory carrying `revenant.toml` -- the marker `init`
    writes, not a second judgement of what counts. The repository root itself is
    included when it is one, and is *not* required to be: `merge-games-re`'s root
    has no marker, and demanding one is what forced the caller to loop in the
    first place (#53).

    Bounded to the root and its immediate children, on the same grounds as the
    shared `_tools/` scan (#50): a real repository has 655 MB of IsilDump under
    `_refs/` and hundreds of thousands of extracted files under `res/`, and
    `lint` must not pay for a tree walk to find out where the projects are.
    """
    from .config import PROJECT_MARKER, repo_root_of
    repo = repo_root_of(start)
    out = []
    if os.path.exists(os.path.join(repo, PROJECT_MARKER)):
        out.append(repo)
    try:
        names = sorted(os.listdir(repo))
    except OSError:
        return out
    for name in names:
        child = os.path.join(repo, name)
        if os.path.isdir(child) and os.path.exists(os.path.join(child, PROJECT_MARKER)):
            out.append(child)
    return out


def repo_root_display(start: str) -> str:
    """The repository root a sweep from `start` would use, for saying so."""
    from .config import repo_root_of
    return repo_root_of(start)


def repo_root_notes(start: str) -> list[str]:
    """The notes in the repository root's own `notes/`, when it is not a project.

    A root without `revenant.toml` is not a project -- that judgement stays
    exactly where `init` put it (ADR-0003) -- but the `notes/` under it are
    notes. The two facts had been bound into one, and the fourteen cross-game
    summaries in `merge-games-re`'s root, the ones most easily written wrong,
    were the only notes in the repository nothing ever checked (#67).

    Empty when the root *is* a project: `repo_projects` already returns it, and
    collecting the same directory twice would double every finding in it. The
    test is the path, the same way `superseded_tools` decides whether the shared
    `_tools/` is one of this project's own.
    """
    repo = repo_root_display(start)
    if os.path.normpath(repo) in {os.path.normpath(p) for p in repo_projects(start)}:
        return []
    return collect_notes(repo)


def lint_repo(start: str, version: str = "") -> LintReport:
    """Lint every project under the repository root, plus the root's own notes.

    Each project is linted as itself -- `REVENANT_PROJECT` pointed at it and the
    loaded indices dropped first. Both matter: the index lives under the
    project's own `_refs/`, and `indices.VERSIONS` is keyed by version *name*, so
    two projects that happen to share a version string would otherwise have the
    second checked against the first's RVAs and told its addresses do not exist.

    This is also the only place holding every project's terminal states at once,
    so it is where the cross-game check runs (`check_rests_on`) -- `lint_note`
    sees one file and cannot answer a question about nine.
    """
    from . import indices

    merged = LintReport()
    old = os.environ.get("REVENANT_PROJECT")
    # Restored, not just emptied: whatever the caller had loaded is theirs, and
    # the sweep is a read that should leave no trace.
    loaded = dict(indices.VERSIONS)
    repo = repo_root_display(start)
    passes = [(repo, repo_root_notes(start), ROOT_LABEL)]
    passes += [(p, collect_notes(p), project_label(p)) for p in repo_projects(start)]
    try:
        for root, paths, label in passes:
            if not paths:
                # Silence when there is nothing there: a lone project must not
                # grow noise because a second source of notes now exists.
                continue
            indices.VERSIONS.clear()
            os.environ["REVENANT_PROJECT"] = root
            report = lint_notes(paths, version)
            for finding in report.findings:
                finding.project = label
            for note in report.notes:
                note.project = label
            merged.findings.extend(report.findings)
            merged.notes.extend(report.notes)
            merged.files += report.files
    finally:
        indices.VERSIONS.clear()
        indices.VERSIONS.update(loaded)
        if old is None:
            os.environ.pop("REVENANT_PROJECT", None)
        else:
            os.environ["REVENANT_PROJECT"] = old
    check_rests_on(merged)
    check_memory(repo, merged)
    return merged


def read_memory_registry(repo: str, report: LintReport | None = None) -> dict:
    """What the repository has put under lint's care, path -> settings.

    An absent file and an empty table both mean nothing is registered, and that
    is the intended way to opt out: there is no exemption flag, because a flag
    named "exempt" gets reached for and an archive simply not being listed
    cannot be.

    A file that is *there but unreadable* is the third case and is not the same
    one. Answering it with an empty dict turns all six rules off and looks
    exactly like a repository that registered nothing -- which is the exemption
    switch this design refused to build, arriving by way of a typo.
    `config.load_config` settled this same argument the loud way for
    `revenant.toml`; the only difference here is that `lint` has somewhere
    better than stderr to put it.
    """
    path = os.path.join(repo, MEMORY_DIR, MEMORY_REGISTRY)
    if not os.path.exists(path):
        return {}
    import tomllib
    shown = os.path.join(MEMORY_DIR, MEMORY_REGISTRY).replace(os.sep, "/")
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        if report is not None:
            report.add(shown, 0, SEVERITY_ERROR, "memory-registry-unreadable",
                       f"cannot be read, so nothing is being checked: {exc}",
                       project=MEMORY_LABEL)
        return {}
    files = data.get("files")
    return files if isinstance(files, dict) else {}


def check_memory(repo: str, report: LintReport) -> None:
    """Check every registered memory file: size first, then how it carries evidence.

    Size is an `error` and not a `warning` on purpose. The loop this came from
    damps regressions by counting lint errors, and a budget that lands in the
    warning pile is a budget nothing acts on.
    """
    for rel, spec in sorted(read_memory_registry(repo, report).items()):
        if not isinstance(spec, dict):
            continue
        full = os.path.join(repo, rel.replace("/", os.sep))
        shown = rel.replace(os.sep, "/")
        if not os.path.exists(full):
            report.add(shown, 0, SEVERITY_WARNING, "memory-not-found",
                       "registered as memory but not on disk",
                       project=MEMORY_LABEL)
            continue
        budget = spec.get("bytes")
        size = os.path.getsize(full)
        if isinstance(budget, int) and size > budget:
            report.add(
                shown, 0, SEVERITY_ERROR, "memory-over-budget",
                f"{size} bytes, over its {budget}-byte budget -- this file is "
                f"read in full every round, so the overage is paid every round",
                project=MEMORY_LABEL,
            )
        if spec.get("kind") == "memory":
            _check_memory_entries(repo, full, shown, spec, report)


def _check_memory_entries(repo: str, full: str, shown: str,
                          spec: dict, report: LintReport) -> None:
    """Every entry says one thing and points at where to read the rest.

    Only top-level list items are entries; headings, prose and indented
    continuation lines are the file talking about itself. The pointer is checked
    the way an RVA is: the file has to be there, and the anchor has to be in it.
    An anchor is a string, never a line number -- the file this rule came from
    carried `记忆第 435 行`, and by the time anyone read it the line said
    something else entirely.

    An entry runs to the next entry, not to the end of its own line. Reading one
    line was right for the file this was written against (every entry fitted)
    and wrong for prose that wraps: a judgement hard-wrapped at 80 columns, with
    its `→ pointer` landing on the second line, was reported as having none, and
    the loop that counts lint errors damped on a finding that was not real (#69).
    """
    with open(full, encoding="utf-8") as f:
        lines = f.read().splitlines()
    starts = [i for i, line in enumerate(lines) if MEMORY_ENTRY.match(line)]
    for index, start in enumerate(starts):
        number = start + 1
        stop = starts[index + 1] if index + 1 < len(starts) else len(lines)
        # A heading ends an entry too: what follows it is the file talking about
        # itself, and swallowing it would let a later section's backtick satisfy
        # this entry's pointer.
        chunk = []
        for line in lines[start:stop]:
            if chunk and line.lstrip().startswith("#"):
                break
            chunk.append(line)
        found = MEMORY_ENTRY.match(chunk[0])
        body = " ".join([found.group("body").strip()]
                        + [ln.strip() for ln in chunk[1:] if ln.strip()]).strip()
        pointer = MEMORY_POINTER.search(body)
        if not pointer:
            report.add(shown, number, SEVERITY_ERROR, "memory-entry-without-pointer",
                       "an entry with no `→ `pointer`` -- say it in one sentence and "
                       "point at the note that holds the evidence",
                       project=MEMORY_LABEL)
            continue
        target = os.path.join(repo, pointer.group("path").replace("/", os.sep))
        if not os.path.exists(target):
            report.add(shown, number, SEVERITY_ERROR, "memory-pointer-missing",
                       f"points at `{pointer.group('path')}`, which is not there",
                       project=MEMORY_LABEL)
            continue
        anchor = pointer.group("anchor")
        if anchor:
            with open(target, encoding="utf-8", errors="replace") as f:
                if anchor not in f.read():
                    report.add(shown, number, SEVERITY_ERROR, "memory-anchor-missing",
                               f"`{anchor}` is no longer in "
                               f"`{pointer.group('path')}`",
                               project=MEMORY_LABEL)
                    continue
        limit = spec.get("entry_chars")
        if isinstance(limit, int) and len(body[:pointer.start()]) > limit:
            report.add(shown, number, SEVERITY_WARNING, "memory-entry-too-long",
                       f"the claim is {len(body[:pointer.start()])} characters, over "
                       f"{limit} -- what does not fit belongs in the note",
                       project=MEMORY_LABEL)


def check_rests_on(report: LintReport) -> None:
    """Check each declared dependency against the states the sweep collected.

    Of the four ways a cross-game conclusion goes stale, this is the only one
    decidable at the moment it is written: a note claiming to summarise nine
    games, when some of those nine cells are not filled in, is a table lookup.
    (The other three -- one game's finding overturning another's, a later
    dimension overturning an earlier one, a summary that has to be written back
    -- need a graph of which conclusion rests on which evidence, and prose is
    not that graph.)

    Two failures, reported apart, because the remedies are opposite: a cell that
    is *there but not met* means go find better evidence, and a cell that is
    *not there at all* means go write it. Folding them into one finding would
    also be this repository's oldest mistake in a new place -- saying something
    we cannot count as if it were the author's conclusion.

    The unmet cells are reported with their own state names rather than as one
    "not met" bucket, for the same reason `census` reports numbers and not
    verdicts: `confirmed_absent` -- "we looked, this game has no such mechanism"
    -- can be a perfectly good footing for a cross-game claim, and whether it is
    belongs to the reader.

    Only a shortfall is reported, never a surplus. `expect` exists precisely
    because the number of projects in a repository is not the number of games in
    a round of research -- a project of another genre parked beside them makes
    the counted number quietly larger -- and the declaration is what is
    believed. Reporting "found 10, declared 9" would be disbelieving it, on the
    one case the field was invented for.
    """
    cells: dict = {}
    for note in report.notes:
        if note.axis and note.slot:
            cells.setdefault((note.axis, note.slot), []).append(note)
    for note in report.notes:
        if not note.rests_on:
            continue
        axis, slot = note.rests_on["axis"], note.rests_on["slot"]
        expect = _positive_int(note.rests_on["expect"])
        if not axis or not slot or not expect:
            continue          # reported as a malformed marker where it was read
        found = cells.get((axis, slot), [])
        if not found:
            # Not "0 of 9 filled in": nine declared and none found anywhere has
            # only one honest reading, and it is that the marker is wrong.
            report.add(note.path, note.rests_line, SEVERITY_ERROR, "rests-on-nothing",
                       f"rests on axis={axis} slot={slot}, and no note in the "
                       f"repository declares a state for it; {expect} were "
                       f"expected, so this is the marker being wrong rather "
                       f"than the research being unfinished",
                       project=note.project)
            continue
        for cell in found:
            if cell.state == STATE_MEETS:
                continue
            where = f"[{cell.project}] " if cell.project else ""
            report.add(note.path, note.rests_line, SEVERITY_WARNING,
                       "rests-on-unmet-cell",
                       f"rests on axis={axis} slot={slot}, and {where}{cell.path} "
                       f"is {cell.state or 'declared with no state'}, not "
                       f"{STATE_MEETS}",
                       project=note.project)
        # Counted by project, because `expect` is a count of *games* -- one
        # project writing that cell up in two notes would otherwise fill a
        # missing game's place and the shortfall would go unreported. Which unit
        # was counted is said out loud, the same way `table refs` says its Lua
        # rows are counted per file: an unexplained number is read as whatever
        # the reader assumed.
        games = {cell.project for cell in found}
        if len(games) < expect:
            report.add(note.path, note.rests_line, SEVERITY_WARNING,
                       "rests-on-missing-cell",
                       f"rests on axis={axis} slot={slot}: found {len(games)}, "
                       f"declared {expect} (counted by project, since expect "
                       f"is how many games this round covers); the rest have "
                       f"not been written yet",
                       project=note.project)


def as_json(report: LintReport) -> dict:
    """The same report, for a consumer instead of a reader.

    One `LintReport`, two renderers over it -- `format_report` is the other. A
    second formatter fed by its own traversal is how the generated harness files
    drifted in #37. The two do not show the same *amount*: a reader scanning a
    terminal does not want every note's state listed, only the findings. What
    they must never do is disagree about a fact they both show.
    """
    return {
        "files": report.files,
        "errors": len(report.errors),
        "warnings": len(report.warnings),
        "findings": [
            {
                "path": f.path, "line": f.line, "severity": f.severity,
                "rule": f.rule, "message": f.message, "project": f.project,
            }
            for f in report.findings
        ],
        "notes": [
            {
                "path": n.path, "project": n.project, "axis": n.axis,
                "slot": n.slot, "state": n.state, "reach": n.reach, "gaps": n.gaps,
                # Verbatim, values and all: what the note declared is a fact,
                # and the same reading that lets `axis` through untouched
                # applies to a count somebody wrote by hand. The rules it feeds
                # go into `findings` with every other rule -- a consumer should
                # not need a second array to learn about a new check.
                "rests_on": n.rests_on,
            }
            for n in report.notes
        ],
    }


def collect_notes(root: str) -> list[str]:
    out: list[str] = []
    notes_dir = os.path.join(root, "notes")
    for dirpath, _dirs, files in os.walk(notes_dir):
        for name in sorted(files):
            if not name.endswith(".md") or name.startswith("_"):
                continue
            if name.lower() in NOT_A_NOTE:
                continue
            out.append(os.path.join(dirpath, name))
    return out


def format_report(report: LintReport) -> str:
    if not report.findings:
        return f"lint: {report.files} notes, nothing to report."
    lines = []
    for finding in report.findings:
        where = f"{finding.path}:{finding.line}" if finding.path else "(project)"
        # Across a sweep the same relative path exists in every project, so the
        # one thing that tells them apart has to survive into the human report
        # too -- not only into the JSON.
        if finding.project and finding.project != os.curdir:
            where = f"[{finding.project}] {where}"
        lines.append(f"  {finding.severity:7s} {finding.rule:20s} {where}\n           {finding.message}")
    summary = (
        f"lint: {report.files} notes, "
        f"{len(report.errors)} errors, {len(report.warnings)} warnings "
        f"(reported, not enforced)"
    )
    return "\n".join([summary, *lines])
