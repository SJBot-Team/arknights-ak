"""How often a config table is named, per corpus. Counts only, never a verdict.

Four of the nine titles have config tables whose columns read perfectly and
whose reference count is zero, so "count the references before you use a table
as evidence" became a rule. There was no way to count it: `xrefs` knows RVAs,
`lua_refs` knows Lua, and the C# side had nothing, so it was done by grepping
`src/`.

The corpora are counted separately and never summed. Which C# roots there are
is `csharp`'s answer -- `[csharp] roots` replaces the built-in pair, and both
built-in roots hold a different kind of C#, so one number over them would
answer a question nobody asked.

**Facts only.** A zero is a zero and never a verdict: one title's `TableParser`
reads override rows before parsing *any* table, so no specific reference does
not mean not loaded. "This table is dead" is a judgement and belongs in a note.
The same rule the ledger keeps -- deterministic code writes facts.

The reverse reading matters as much: an unreferenced table is usually the
residue of offline tuning, and when the live flag state cannot be read, those
names are the only window onto what somebody tried.

Its own module rather than a sixth job for `tables`: nothing here reads a table.
It walks `src/` and `lua/` and the metadata strings counting identifiers, which
is `xrefs`' side of the house -- what it wants from `tables` is two names.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field as _field, replace
from typing import Collection

from .tables import SKIP_DIRS, plural

# A file that names this many distinct tables is a place that handles tables in
# general. A hit there is reported apart from a specific one -- as a fact about
# the site, not a conclusion about the table.
MANY_TABLES = 5

REF_MAX_FILES = 4000        # files read per corpus before the sweep says it stopped
REF_COLUMN = 16             # the corpus-name column, so every line here lines up


@dataclass(frozen=True)
class Refs:
    """One corpus's answer about one table.

    `why` and `caveats` are kept apart because they are opposite facts. `why`
    says the corpus could not be searched at all -- there is no count. A caveat
    qualifies a count that exists: it was taken over the first N files, or the
    project knows too few tables for the general-handler split to fire. Folding
    them into one field is how "we did not look" comes to read like "we looked
    and it was fine".
    """
    corpus: str
    available: bool = True
    why: str = ""            # when the corpus could not be searched
    total: int = 0
    files: int = 0
    unit: str = "file"       # what `files` counts; the metadata blob has sections
    shared: int = 0          # hits in files that name many tables
    by_name: dict = _field(default_factory=dict)
    sites: tuple = ()
    caveats: tuple = ()      # what qualifies a count that was taken

    @property
    def specific(self) -> int:
        return self.total - self.shared


def word_pattern(names) -> "re.Pattern | None":
    """One alternation over `names`, matching whole identifiers only. None if empty.

    Whole-word because `ItemConfExtra` is a different identifier, and counting
    it would turn a zero into a one -- the answer this exists to get right. One
    pattern rather than one per name because every caller runs it over every
    file of a corpus, and a corpus is thousands of files.

    Public, and the one definition of "a whole identifier": `cs-refs` asks the
    same question about C# that this module asks about table names, and two
    spellings of that rule is two places for the substring bug to come back.
    """
    if not names:
        return None
    return re.compile(r"(?<![A-Za-z0-9_])(" +
                      "|".join(re.escape(n) for n in sorted(names)) +
                      r")(?![A-Za-z0-9_])")


def count_names(documents, names, all_names: "Collection[str]" = frozenset()) -> Refs:
    """Count whole-word mentions of `names` across `(label, text)` pairs.

    An iterable of pairs, not a mapping, so a corpus can be counted one file at
    a time and the text dropped: `src/<version>/` is tens of thousands of files
    and holding them all to count identifiers is a cost with nothing bought.
    Order is the caller's -- the sites come back in the order they arrive.

    `all_names` lets a hit be placed: a file naming `MANY_TABLES` distinct other
    tables is a general table-handling site, so its hits are counted apart. When
    the project knows fewer than that many other tables the split cannot fire at
    all, and that is said in a caveat rather than left to look like a specific
    reference.
    """
    names = tuple(names)
    pattern = word_pattern(names)
    if pattern is None:
        return Refs(corpus="", caveats=("no name to search for",))
    others = set(all_names) - set(names)
    many = word_pattern(others) if len(others) >= MANY_TABLES else None
    by_name: dict = {n: 0 for n in names}
    total = shared = files = 0
    sites = []
    for label, text in documents:
        found = pattern.findall(text)
        if not found:
            continue
        files += 1
        total += len(found)
        for hit in found:
            by_name[hit] = by_name.get(hit, 0) + 1
        if many is not None and len(set(many.findall(text))) >= MANY_TABLES:
            shared += len(found)
            sites.append(f"{label} (names many tables)")
        else:
            sites.append(label)
    caveats = ()
    if many is None and total:
        caveats = (f"fewer than {MANY_TABLES} other tables are known here, so a "
                   f"file that handles tables in general cannot be told from one "
                   f"that names this table alone",)
    return Refs(corpus="", total=total, files=files, shared=shared,
                by_name=by_name, sites=tuple(sites), caveats=caveats)


def reference_corpora(names, root: str | None = None, version: str = "",
                      all_names: "Collection[str]" = frozenset()) -> tuple:
    """`Refs` per corpus: each C# source root, the metadata strings, the Lua tree.

    Separate answers, never one total. A corpus that is not there says so --
    "we have not built the index" and "the author never referenced it" are
    different facts, and reporting the first as the second is the mistake `lint`
    calls `no-index`.
    """
    from . import config
    root = os.path.abspath(root or config.workspace_root())
    version = version or config.detect_version()
    return (*_csharp_refs(names, root, version, all_names),
            _metadata_refs(names, all_names),
            _lua_refs(names, root, version, all_names))


def _files_under(directory: str, suffix: str) -> tuple:
    """`(paths, capped)` -- the files of one corpus, in a stable order."""
    paths, capped = [], False
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for filename in sorted(filenames):
            if not filename.endswith(suffix):
                continue
            if len(paths) >= REF_MAX_FILES:
                capped = True
                break
            paths.append(os.path.join(dirpath, filename))
        if capped:
            break
    return tuple(paths), capped


def _texts(paths, base: str):
    """`(relative path, text)` one file at a time; unreadable files are skipped."""
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                yield os.path.relpath(path, base), f.read()
        except OSError:
            continue


def _tree_refs(directory: str, suffix: str, corpus: str, what: str, hint: str,
               names, all_names) -> Refs:
    """A source tree, counted file by file.

    An empty tree is *not* a zero. `lint`'s `no-index` rule keys on whether
    anything actually loaded, not on whether a directory exists -- a `src/`
    holding no `.cs` at all means seeding never ran, and reporting that as "0
    mentions" is our own missing input dressed as the author's answer.
    """
    if not os.path.isdir(directory):
        return Refs(corpus=corpus, available=False, why=f"no {what} ({hint})")
    paths, capped = _files_under(directory, suffix)
    if not paths:
        return Refs(corpus=corpus, available=False,
                    why=f"the {what} holds no {suffix} files ({hint})")
    found = count_names(_texts(paths, directory), names, all_names)
    caveats = found.caveats
    if capped:
        caveats += (f"only the first {REF_MAX_FILES:,} files were read, so this "
                    f"count is of those and not of the whole tree",)
    return replace(found, corpus=corpus, caveats=caveats)


def _csharp_refs(names, root: str, version: str, all_names) -> tuple:
    """One `Refs` per C# source root this project has, never merged.

    The C# side is two roots, not one. `src/<version>/` is the scaffold --
    stubs, with bodies stripped -- and `src-hotupdate/<version>/` is the shipped
    bodies, which is where a title's table loading usually lives. A mention in
    one is not the same finding as a mention in the other, so they are counted
    apart, the way `cs-refs` labels every line it prints.

    Which roots there are is `csharp.declared_roots`' answer, asked rather than
    restated: `[csharp] roots` REPLACES the built-in pair, and a second spelling
    of that list here is a second place for `table refs` to search where
    `cs-refs` does not. That is not hypothetical -- this function replaced one
    that read `src/<version>/` alone, so a project whose recovered source sat
    anywhere else got "cannot check" over a tree that was right there.

    `declared`, not `source_roots`: that one drops the roots that are not there,
    and a root that is not there is precisely what has to be reported as
    "cannot check" rather than as a zero.
    """
    from . import csharp
    out = []
    for directory, label in csharp.declared_roots(root):
        where = os.path.join(directory, version or "<version>")
        out.append(_tree_refs(os.path.join(root, directory, version),
                              csharp.CS_SUFFIX, label, f"{label} at {where}/",
                              csharp.root_hint(directory), names, all_names))
    return tuple(out)


def _lua_refs(names, root: str, version: str, all_names) -> Refs:
    where = os.path.join("lua", version or "<version>")
    return _tree_refs(os.path.join(root, "lua", version), ".lua", "lua",
                      f"extracted Lua tree at {where}/", "revenant lua-extract",
                      names, all_names)


def _metadata_refs(names, all_names) -> Refs:
    """The metadata string literals -- where a name loaded by string shows up.

    One artefact read in two sections, so the count says *sections*: calling
    them files would report one `global-metadata.dat` as two.
    """
    from . import binary, strings
    try:
        location = binary.find_global_metadata()
        with open(location.path, "rb") as f:
            blob = f.read()
        _version, literals, type_names = strings.read_literals(blob)
    except Exception as exc:                  # noqa: BLE001 - report, don't die
        return Refs(corpus="metadata", available=False,
                    why=f"no readable global-metadata.dat ({exc})")
    sections = (("global-metadata.dat (string literals)", "\n".join(literals)),
                ("global-metadata.dat (type names)", "\n".join(type_names)))
    return replace(count_names(sections, names, all_names),
                   corpus="metadata", unit="section")


# The sentence the command exists to keep saying. Here rather than in the CLI so
# there is one wording, and so a caller reusing `refs_report` cannot drop it.
REFS_FOOTER = (
    "Counts, not a verdict: a table loaded by a parser that reads every table\n"
    "shows no specific reference. Whether it is live is a judgement, and goes in\n"
    "a note. Every mention counts -- comments and string literals included.")


def refs_line(found: Refs) -> str:
    """One corpus's answer, phrased once.

    Never a verdict. A zero is reported as a zero, and a corpus that could not
    be searched says so rather than contributing one -- `lint`'s `no-index`
    rule, one layer down: our own missing input is not the author's zero.
    """
    if not found.available:
        return f"{found.corpus:<{REF_COLUMN}} cannot check -- {found.why}"
    if not found.total:
        return f"{found.corpus:<{REF_COLUMN}} 0 mentions"
    head = (f"{found.corpus:<{REF_COLUMN}} {found.total} "
            f"{plural(found.total, 'mention')} in {found.files} "
            f"{plural(found.files, found.unit)}")
    if found.shared:
        return (f"{head}: {found.specific} where the file names this table alone, "
                f"{found.shared} where it names many tables")
    return head


def refs_report(found: Refs, limit: int = 5) -> list:
    """Every line one corpus prints, including what it left out.

    All of it here rather than half in the CLI, for the reason `diff` gives:
    the one sentence a command exists for should have one wording. And nothing
    truncates silently -- the site list says how many it did not show, because a
    query that covered less than it was asked to must not read like one that
    found nothing.
    """
    pad = " " * REF_COLUMN
    out = [refs_line(found)]
    out += [f"{pad} ({note})" for note in found.caveats]
    if found.total and len(found.by_name) > 1:
        # Zeros included. "4 mentions" that are all row class and none of them
        # the table name is a different situation from an even split, and the
        # name that scored nothing is the half that says so.
        by_name = ", ".join(f"{name} {count}"
                            for name, count in sorted(found.by_name.items()))
        out.append(f"{pad}   by name: {by_name}")
    shown = found.sites[:max(0, limit)]
    out += [f"{pad}   {site}" for site in shown]
    left = len(found.sites) - len(shown)
    if left:
        out.append(f"{pad}   ... {left} more {plural(left, 'site')} "
                   f"(--limit shows more)")
    return out
