"""The A/B experiment roster a CMS ships inside the package.

Everything about an experiment is in the build: which experiments exist, which
items each one touches, which fields it changes, and *both* values. Only "which
variant is this player in" lives on the server. So the roster is readable
without touching a backend, and reading it is worth a construct rather than a
script in each project -- it was one script in one project.

The shape is a CMS middleware's: a list of variants, each naming an item and
carrying a JSON patch in which a changed field is written as a two-element
`[control, test]` pair.

**The three field names are the caller's.** They are concrete names in one
middleware's schema, which `docs/adr/0004-what-qualifies-to-move-into-revenant.md`
counts as a game fact, so they arrive as an argument -- the same way
`contrib.fetch` takes its HTTP call and `[tables] luban_container` takes a
project's own module. `CMS_KEYS` is a default, not knowledge this module claims.

**What else stays in the project**: which guid is which item, which experiment
is which feature, and whether a change is an increase worth acting on. This
module returns guids and field paths and stops -- the same line `table refs`
draws between a count and a verdict.

**Provenance.** The key names and the pair convention were transcribed from the
audit behind #48, which read them off one title's CMS. No sample from a real
package is in this repository and none is checkable outside it, so unlike the
upstream-transcribed format references in `docs/playbooks/` this is not
confirmable anywhere yet: the tests run on synthetic documents and the shape is
**unconfirmed against any package**. A first real roster would settle whether a
patch ever writes more than two values for one field, whether experiment
identity sits anywhere other than the item guid, and whether a patch is ever a
JSON list rather than an object.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# A changed field is written as exactly two values: what it is, and what the
# experiment makes it. A list of any other shape is not a change this parser
# understands, and is reported rather than dropped.
PAIR = 2

# How deep a patch may nest before we stop rather than exhaust the stack. A
# hand-written patch is two or three levels; anything near this is a document
# that is not what we think it is, and it is reported as such.
MAX_DEPTH = 64


@dataclass(frozen=True)
class RosterKeys:
    """What this CMS calls the three things. Concrete names, so: an argument."""
    variants: str = "m_variants"
    item: str = "m_itemGuid"
    patch: str = "m_jsonPatch"


CMS_KEYS = RosterKeys()


@dataclass(frozen=True)
class Change:
    item_guid: str
    field: str          # dotted path inside the patch
    control: object
    test: object
    group: str = ""     # which `m_variants` list it came from


@dataclass(frozen=True)
class Unpaired:
    """A leaf inside a patch that is not a `[control, test]` pair."""
    item_guid: str
    field: str
    value: object
    group: str = ""


@dataclass(frozen=True)
class Roster:
    changes: tuple[Change, ...] = ()
    unpaired: tuple[Unpaired, ...] = ()
    items: tuple[str, ...] = ()      # item guids touched, in the order seen
    groups: tuple[str, ...] = ()     # where each `m_variants` list was found
    notes: tuple[str, ...] = ()      # what could not be read, and why


def _scalar(value) -> bool:
    """Whether a value can be one arm of a change. Containers cannot.

    A pair of objects is not one change with two values -- it is a structure
    this parser does not understand, and calling it a change invents an
    experiment arm nobody wrote.
    """
    return value is None or isinstance(value, (str, int, float, bool))


def read_roster(doc, keys: RosterKeys = CMS_KEYS) -> Roster:
    """Every field an experiment changes, per item. Never says what a guid means.

    `doc` is the decoded CMS document -- a dict or list, whatever `json.load`
    or the FlatBuffers reader handed back. The variants list is looked for
    anywhere inside it, because which wrapper a title puts around it is that
    title's business and hard-coding a path would be a second game fact.

    Each variants list found is a *group*, and every change says which one it
    came from: a document holding two rosters merged into one bucket would read
    as a single roster twice the size.
    """
    found = list(_find_variants(doc, keys.variants))
    if not found:
        return Roster(notes=(f"no {keys.variants} anywhere in this document, so "
                             f"either it holds no experiments or it is not a "
                             f"roster this parser recognises",))
    changes: list[Change] = []
    unpaired: list[Unpaired] = []
    notes: list[str] = []
    items: list[str] = []
    for group, entries in found:
        for entry in entries:
            if not isinstance(entry, dict):
                notes.append(f"{group}: an entry is a {type(entry).__name__}, "
                             f"not an object")
                continue
            guid = str(entry.get(keys.item, "") or "")
            if not guid:
                # Reported, because a change with no item is a change nobody
                # can act on, and a blank column reads as a name we chose not
                # to print rather than one that was not there.
                notes.append(f"{group}: a variant has no {keys.item}; its "
                             f"changes are listed against '(no guid)'")
            elif guid not in items:
                items.append(guid)
            patch, problem = _patch_of(entry, keys)
            if problem:
                notes.append(f"{guid or '(no guid)'}: {problem}")
                continue
            for path, value in _leaves(patch):
                where = guid or "(no guid)"
                if (isinstance(value, list) and len(value) == PAIR
                        and all(_scalar(v) for v in value)):
                    changes.append(Change(item_guid=where, field=path,
                                          control=value[0], test=value[1],
                                          group=group))
                else:
                    unpaired.append(Unpaired(item_guid=where, field=path,
                                             value=value, group=group))
    return Roster(changes=tuple(changes), unpaired=tuple(unpaired),
                  items=tuple(items), groups=tuple(g for g, _e in found),
                  notes=tuple(notes))


def _find_variants(node, key: str, path: str = "", depth: int = 0):
    """`(where, entries)` for every variants list, however deeply it is wrapped."""
    if depth > MAX_DEPTH:
        return
    if isinstance(node, dict):
        for name, value in node.items():
            here = f"{path}.{name}" if path else str(name)
            if name == key and isinstance(value, list):
                yield here, value
            else:
                yield from _find_variants(value, key, here, depth + 1)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _find_variants(item, key, f"{path}[{index}]", depth + 1)


def _patch_of(entry: dict, keys: RosterKeys):
    """`(patch, problem)` -- the patch as an object, however it arrived.

    CMS ships it as a JSON string; an exporter that already parsed the document
    hands back the object. Accepting only one of the two would report a roster
    it could not read as a roster with nothing in it.
    """
    raw = entry.get(keys.patch)
    if raw is None:
        return None, f"no {keys.patch}"
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError as exc:
            return None, f"{keys.patch} is not JSON ({exc})"
    if isinstance(raw, dict):
        return raw, ""
    # Checked after parsing as well as before, because the string form decodes
    # to the same shapes. Every patch seen is an object keyed by field name; a
    # list has no names in it, so its entries could only come back nameless,
    # which is an answer nobody can use.
    return None, (f"{keys.patch} is a {type(raw).__name__}, not an object keyed "
                  f"by field name; this parser has no way to name what it changed")


def _leaves(node, prefix: str = "", depth: int = 0):
    """`(dotted path, value)` for everything that is not a nested object.

    A list is a leaf because that is where the `[control, test]` pair lives;
    whether it *is* a pair is decided by the caller, so a list of objects comes
    back here and is reported as unpaired rather than mistaken for a change.
    """
    if depth > MAX_DEPTH:
        yield prefix, "(nested deeper than this parser follows)"
        return
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield from _leaves(value, path, depth + 1)
        return
    yield prefix, node


def format_roster(roster: Roster) -> str:
    """The roster as text. Guids and field paths, and no reading of them.

    Every bucket is in the header, not just the one that worked: a count of
    changes printed alone reads as the whole roster when half of it was
    something this parser could not name.

    What an experiment *means* -- which item the guid is, whether the test arm
    is an increase -- needs the project's own mapping and the reader's
    judgement, and belongs in a note.
    """
    head = (f"{len(roster.changes)} field change(s) across "
            f"{len(roster.items)} item(s) in {len(roster.groups)} list(s)")
    if roster.unpaired:
        head += f"; {len(roster.unpaired)} leaf/leaves are not control/test pairs"
    if roster.notes:
        head += f"; {len(roster.notes)} thing(s) could not be read"
    lines = [head]
    for change in roster.changes:
        lines.append(f"  {change.item_guid}  {change.field}: "
                     f"{change.control!r} -> {change.test!r}")
    for odd in roster.unpaired:
        lines.append(f"  {odd.item_guid}  {odd.field}: not a control/test pair "
                     f"({type(odd.value).__name__})")
    for note in roster.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)
