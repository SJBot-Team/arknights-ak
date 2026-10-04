#!/usr/bin/env python3
"""Revenant -- reverse-engineering harness for Unity IL2CPP + xLua games.

Usage:
  revenant <command> [args]        (also: python -m revenant <command>)
  revenant help                    the core commands
  revenant help --all              plus the query tier (agents reach these via MCP)

The command table has four tiers (ADR-0002): core is what a newcomer sees,
query is listed by `help --all`, the extension tier (the frozen breadth-scan
family) appears only once `[packs] enabled` is set, and removed commands say
where they went. The listing itself is generated from `command_table()`.

Based on the RE methodology from the match3-core-sketch project.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass

from .config import (
    DEFAULT_VERSION,
    SHARED_TAG,
    env_key_for_version,
    find_root,
    shared_label,
    version_ref_dir,
    normalize_global_args,
    refs_dir,
    workspace_root,
    xapk_path,
)
from .indices import VERSIONS, load_version, lookup_rva
from .search import search_symbols
from .reports import find_asm_by_rva
from .cfg import build_cfg_report
from .binary import find_libil2cpp, find_global_metadata, extract_all_apks, list_apk_contents
from .assets import (
    MAIN_STORYLINE_GROUP,
    extract_group,
    find_base_apk,
    list_bundles,
)
from .disasm import evidence_report, simple_disasm_report
from .metadata import Il2CppMetadata, decode_metadata_usage
from .image import format_mapping, map_rva_to_file_offset
from .xrefs import find_xrefs, callgraph
from .fields import scan_field_accesses


TIER_CORE = "core"
TIER_QUERY = "query"
TIER_EXTENSION = "extension"
TIER_REMOVED = "removed"

# The four tiers, by name (ADR-0002). `command_table()` is the dispatch table;
# this is the only other place a command's name is written, and it exists to
# say which surface shows it -- not to describe it.
_TIER_OF = {}
for _n in ("init", "status", "prepare", "find-binary", "find-metadata",
           "import-metadata", "patch-binary", "lua-extract", "seed-src",
           "fingerprint", "dig", "lint", "describe", "help"):
    _TIER_OF[_n] = TIER_CORE
for _n in ("disasm", "evidence", "lookup", "search", "xrefs", "callgraph",
           "find-asm", "cfg", "field-scan", "metadata-info", "lua-list",
           "lua-get", "lua-grep", "lua-refs", "lua-bridge",
           "lua-decompile", "cs-list", "cs-get", "cs-grep", "cs-refs",
           "list-bundles",
           "extract-scenes", "strings", "pb-schema", "pb-tags",
           "fb-dump", "fb-schema", "fb-read", "luban-read", "table"):
    _TIER_OF[_n] = TIER_QUERY
for _n in ("packs", "probe", "cell", "ledger", "scan", "naming-stats"):
    _TIER_OF[_n] = TIER_EXTENSION

# Removed commands and where each went. Kept as a table so a stale script or a
# stale note gets an answer instead of "Unknown command".
REMOVED_COMMANDS = {
    "workspace": "removed (ADR-0002): a project is a plain directory; there is no workspace layer",
    "narrow": "removed (ADR-0002): provenance narrowing was a fingerprint judgement; ADR-0002 demotes the fingerprint to observations (#28)",
    "baseline": "removed (ADR-0002): baseline was a scan-family gate; the scan family is frozen",
    "build-indices": "merged into `revenant prepare --only build-indices`",
    "run-cpp2il": "merged into `revenant prepare --only run-cpp2il`",
    "ls-apk": "merged into `revenant prepare --only ls-apk`",
    "extract-apks": "merged into `revenant prepare --only extract-apks`",
}


def command_tier(name: str) -> str:
    """core / query / extension / removed. Unknown names are not a tier."""
    if name in REMOVED_COMMANDS:
        return TIER_REMOVED
    return _TIER_OF.get(name, "")


def command_table() -> dict:
    """Every dispatchable command name mapped to its handler.

    Module-level so `revenant describe` reads the table the CLI actually
    dispatches on. A second, hand-maintained list is exactly how the shipped
    skill ended up missing nine commands.
    """
    table = {
        "init": cmd_init,
        "status": cmd_status,
        "prepare": cmd_prepare,
        "seed-src": cmd_seed_src,
        "list-bundles": cmd_list_bundles,
        "extract-scenes": cmd_extract_scenes,
        "find-binary": cmd_find_binary,
        "find-metadata": cmd_find_metadata,
        "import-metadata": cmd_import_metadata,
        "patch-binary": cmd_patch_binary,
        "disasm": cmd_disasm,
        "evidence": cmd_evidence,
        "lookup": cmd_lookup,
        "search": cmd_search,
        "xrefs": cmd_xrefs,
        "callgraph": cmd_callgraph,
        "find-asm": cmd_find_asm,
        "cfg": cmd_cfg,
        "lua-extract": cmd_lua_extract,
        "lua-list": cmd_lua_list,
        "lua-get": cmd_lua_get,
        "lua-grep": cmd_lua_grep,
        "lua-refs": cmd_lua_refs,
        "lua-bridge": cmd_lua_bridge,
        "lua-decompile": cmd_lua_decompile,
        "cs-list": cmd_cs_list,
        "cs-get": cmd_cs_get,
        "cs-grep": cmd_cs_grep,
        "cs-refs": cmd_cs_refs,
        "field-scan": cmd_field_scan,
        "metadata-info": cmd_metadata_info,
        "strings": cmd_strings,
        "pb-schema": cmd_pb_schema,
        "pb-tags": cmd_pb_tags,
        "fb-dump": cmd_fb_dump,
        "fb-schema": cmd_fb_schema,
        "fb-read": cmd_fb_read,
        "luban-read": cmd_luban_read,
        "table": cmd_table,
        "packs": cmd_packs,
        "probe": cmd_probe,
        "cell": cmd_cell,
        "ledger": cmd_ledger,
        "lint": cmd_lint,
        "fingerprint": cmd_fingerprint,
        "naming-stats": cmd_naming_stats,
        "scan": cmd_scan,
        "dig": cmd_dig,
        "help": cmd_help,
        "describe": cmd_describe,
    }
    untiered = [n for n in table if n not in _TIER_OF]
    assert not untiered, f"commands without a tier: {untiered}"
    return table


def packs_enabled() -> bool:
    """Whether this project has `[packs] enabled` set. False outside a project."""
    try:
        from . import config, pack
        return bool(pack.enabled_packs(config.project_config()))
    except Exception:
        return False


def visible_commands(show_all: bool = False, with_extension: bool | None = None) -> list:
    """The command names a surface shows, in table order.

    Core always; query when `show_all`; extension when a pack is enabled (or
    forced with `with_extension`). `help`, `describe` and the rendered skill
    all go through here so they cannot disagree.
    """
    if with_extension is None:
        with_extension = packs_enabled()
    out = []
    for name in command_table():
        tier = command_tier(name)
        if tier == TIER_CORE:
            out.append(name)
        elif tier == TIER_QUERY and show_all:
            out.append(name)
        elif tier == TIER_EXTENSION and with_extension:
            out.append(name)
    return out


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = normalize_global_args(argv)

    parser = argparse.ArgumentParser(
        description="Gossip Harbor Unity IL2CPP Reverse Engineering Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Game version")
    parser.add_argument("--root", help="Override RE root directory")
    parser.add_argument("--platform", default=None,
                        help="Pin the package platform (android | ios). "
                             "Artifacts live under _refs/<version>[-<platform>]/.")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("command", nargs="?", help="Subcommand")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Subcommand arguments")
    parsed = parser.parse_args(argv)

    cmd = (parsed.command or "help").lower()

    # `init` creates a project; it must run before any project/index machinery.
    from . import config as _config
    _config.set_platform(getattr(parsed, "platform", None))

    if cmd == "init":
        return cmd_init(parsed)
    if cmd == "help":
        return cmd_help(parsed)

    # Auto-load indices from _refs/<version>/
    auto_load_indices(parsed)

    # Dispatch
    dispatch = command_table()

    if cmd in dispatch:
        return dispatch[cmd](parsed)
    if cmd in REMOVED_COMMANDS:
        print(f"revenant {cmd}: {REMOVED_COMMANDS[cmd]}", file=sys.stderr)
        return 2
    print(f"Unknown command: {cmd}", file=sys.stderr)
    print("Available: " + ", ".join(visible_commands(show_all=True)), file=sys.stderr)
    print("(`revenant help --all` lists them with a summary)", file=sys.stderr)
    return 1


def auto_load_indices(parsed: argparse.Namespace) -> None:
    """Auto-load indices from _refs/<version>/cpp2il_out/ or specified root."""
    version = parsed.version
    root = parsed.root or find_root(version)

    # Try _refs/<version>/cpp2il_out/ (new cpp2il output)
    cpp2il_out = os.path.join(version_ref_dir(version), "cpp2il_out")
    if os.path.isdir(cpp2il_out):
        load_version(version, cpp2il_out, parsed.verbose)
        return

    # Try _refs/<version>/index/
    index_dir = os.path.join(root, "index")
    if os.path.isdir(index_dir):
        load_version(version, root, parsed.verbose)
        return

    # Try root directly (if it has index files)
    rva_path = os.path.join(root, "rva_index.json")
    if os.path.exists(rva_path):
        load_version(version, root, parsed.verbose)
        return

    # Try _refs/<version>/
    ref_ver = version_ref_dir(version)
    if os.path.isdir(ref_ver):
        load_version(version, ref_ver, parsed.verbose)
        return


def _arg(parsed: argparse.Namespace, idx: int, default: str = "") -> str:
    """Get a positional argument by index."""
    args = parsed.args
    if idx < len(args):
        return args[idx]
    return default


# ── Project lifecycle ────────────────────────────────────────────────────────

def cmd_init(parsed: argparse.Namespace) -> int:
    """Scaffold a new RE project (config + dirs + the Claude Code and Codex harness files)."""
    from .init import init_project
    target = _arg(parsed, 0) or "."
    force = "--force" in parsed.args
    return init_project(target, force=force)


def cmd_status(parsed: argparse.Namespace) -> int:
    """Show what is set up in the current project, and the ADR-0002 proxy alarms."""
    import os as _os
    from . import config
    from .lua import lua_out_dir
    root = config.workspace_root()
    has_marker = _os.path.exists(_os.path.join(root, config.PROJECT_MARKER))
    pkg = config.detect_package()
    ver = parsed.version
    cpp2il = _os.path.join(config.version_ref_dir(ver), "cpp2il_out")
    has_idx = _os.path.exists(_os.path.join(cpp2il, "rva_index.json"))
    has_lua = _os.path.isdir(lua_out_dir(ver))
    try:
        bin_ok = bool(find_libil2cpp())
    except Exception:
        bin_ok = False
    print(f"Revenant project: {root}")
    print(f"  marker (revenant.toml) : {'yes' if has_marker else 'NO (run: revenant init)'}")
    print(f"  package                : {pkg}")
    print(f"  version                : {ver}")
    print(f"  game package present   : {'yes' if xapk_path() else 'NO (drop an .apk/.xapk here)'}")
    print(f"  IL2CPP binary extracted: {'yes' if bin_ok else 'no (revenant prepare)'}")
    for line in harness_status_lines(root):
        print(line)
    print(f"  indices built          : {'yes' if has_idx else 'no (revenant prepare)'}")
    print(f"  Lua extracted          : {'yes' if has_lua else 'no (xLua: configure [lua]; lua-extract)'}")
    # The table corpus, on the first screen a project ever shows. A noun with no
    # entry point is how `workspace` and `ledger` ended up with no project ever
    # having built one, which is what ADR-0002 removed them for.
    print(f"  config tables          : {_table_summary()}")
    for line in project_proxy_alarms(root):
        print(f"  alarm                  : {line}")
    for line in superseded_tools(root):
        print(f"  alarm                  : {line}")
    return 0


# The value column every `status` line lines up on. One number, because a
# continuation line that does not sit under the value it continues reads as a
# separate finding.
_STATUS_VALUE_COLUMN = len("  agent skill            : ")


def harness_status_lines(root: str) -> list[str]:
    """One labelled line per harness this project has files for, plus its drift.

    Which harnesses appear is decided by what is on disk. A project on Claude
    Code alone is never told anything about Codex, and a project on both is told
    about each separately, because "the generated files are current" is a
    different fact for each of them and one answer covering both would be a
    guess about which one you meant.
    """
    from . import describe as _describe
    installed = _describe.installed_harnesses(root)
    if not installed:
        return [_status_line("agent skill", "no harness files here (run: revenant init)")]
    out = []
    for harness in installed:
        drift = harness_drift_lines(root, harness=harness)
        # Which layer, on the same line as the verdict: "current" about a file
        # whose location is unstated is a judgement with nothing to point at (#51).
        verdict = "current" if not drift else drift[0]
        shared = harness_location(root, harness)
        if shared:
            verdict = f"{verdict} -- generated in {shared}"
        out.append(_status_line(f"agent skill ({harness})", verdict))
        out += [" " * _STATUS_VALUE_COLUMN + line for line in drift[1:]]
    out += [" " * _STATUS_VALUE_COLUMN + line for line in codex_trust_lines(root)]
    return out


def _status_line(label: str, value: str) -> str:
    """One `  label   : value` line, padded so continuations can sit under it."""
    return f"  {label}".ljust(_STATUS_VALUE_COLUMN - 2) + f": {value}"


def _table_summary() -> str:
    """`status`'s table line. A status query never fails over a corpus scan."""
    from . import tables as _tables
    try:
        return _tables.summary(_tables.discover())
    except Exception as exc:                      # noqa: BLE001 - status must not die
        return f"could not be scanned: {exc}"


# ADR-0002's proxy metrics for "a newcomer can use this in a day". Alarms, not
# gates: this map has twice withdrawn a decision to gate on a proxy variable.
PROXY_MAX_SKILL_LINES = 80
PROXY_MAX_DEFAULT_COMMANDS = 15
PROXY_MAX_TERMS = 6


def proxy_alarms(skill_lines: int, default_commands: int, terms: int) -> list:
    """One line per exceeded proxy; empty when all are within bounds."""
    out = []
    if skill_lines > PROXY_MAX_SKILL_LINES:
        out.append(f"skill is {skill_lines} lines > {PROXY_MAX_SKILL_LINES} (ADR-0002 proxy; not a gate)")
    if default_commands > PROXY_MAX_DEFAULT_COMMANDS:
        out.append(f"default command list is {default_commands} > {PROXY_MAX_DEFAULT_COMMANDS} (ADR-0002 proxy; not a gate)")
    if terms > PROXY_MAX_TERMS:
        out.append(f"glossary has {terms} main-line terms > {PROXY_MAX_TERMS} (ADR-0002 proxy; not a gate)")
    return out


# Project scripts a built-in now covers, and what covers them. This table is the
# executable form of the #47 and #50 audits: absorbing a script and leaving its
# copies in place is worse than not absorbing it, because the notes keep pointing
# at a copy nobody maintains any more -- and two copies of `findvm.py` had
# already drifted apart, 78 lines against 84, before anyone noticed.
#
# Only entries where the built-in does the *whole* job belong here. A fetch
# script is not listed: `contrib.fetch` took its loop, but its URL rules and ids
# are facts about that title and stay where they are.
#
# The downstream action differs by what replaced the script, so the table says
# which. A command replaces the file outright -- delete it and cite the command.
# An importable construct replaces its *body* -- the file becomes a thin wrapper
# holding whatever game facts it had, so it is reported only until it actually
# imports the built-in.
BY_COMMAND = "command"      # -> delete the copy, cite the command
BY_IMPORT = "import"        # -> keep the file, make it a wrapper around the import


@dataclass(frozen=True)
class Superseded:
    replacement: str        # a command line, or an importable dotted name
    kind: str               # BY_COMMAND | BY_IMPORT
    note: str = ""          # what stays behind, when something does


SUPERSEDED_TOOLS = {
    "dump_strlit.py": Superseded("revenant strings", BY_COMMAND),
    "pbschema.py": Superseded("revenant pb-schema", BY_COMMAND),
    "recover_tags.py": Superseded("revenant pb-tags", BY_COMMAND),
    "ab_probe.py": Superseded("revenant list-bundles --types", BY_COMMAND),
    "extract_ab.py": Superseded(
        "revenant extract-scenes --by-script [--root PREFIX] [--unity-version V]", BY_COMMAND),
    # #50: `extract-scenes --ggm` produces the same byte set -- 53 TextAssets,
    # names differing only where a space became an underscore.
    "dump_textassets.py": Superseded(
        "revenant extract-scenes --ggm --out <dir>", BY_COMMAND,
        "--out moves the root; what is under it (the per-type tree, `.bytes`, "
        "the sanitised stem) is revenant's layout for every title, so the "
        "scripts reading the old `*.bin` names get repointed once"),
    # The FlatBuffers family, absorbed whole in #50.
    "fbdump.py": Superseded("revenant fb-dump", BY_COMMAND),
    "fbschema.py": Superseded("revenant fb-schema", BY_COMMAND),
    # #62: the shell around the import -- pick a root, pick a path into it, cap
    # the rows -- is what `table` does now, so the file goes rather than getting
    # thinner. What it held that is real stays, as configuration rather than code.
    "fbread.py": Superseded("revenant table list / table census", BY_COMMAND,
                            "the CMS root types and the container convention move to "
                            "[tables] fb_roots / fb_containers in revenant.toml"),
    # Importable constructs: the body moves, the game facts do not.
    "xxtea.py": Superseded("revenant.contrib.decrypt.xxtea", BY_IMPORT,
                           "the key stays in the project"),
    "wrap_pe.py": Superseded("revenant.contrib.decrypt.pe", BY_IMPORT),
    "findvm.py": Superseded("revenant.contrib.decrypt.findvm", BY_IMPORT),
    "parse_patch.py": Superseded("revenant.contrib.decrypt.ifix", BY_IMPORT,
                                 "the per-build opcode map is data and stays"),
    "dump_httpcache.py": Superseded("revenant.contrib.cache", BY_IMPORT,
                                    "the cache path on the device stays in the project"),
    # #48: the roster's shape is a CMS middleware's, so the parsing moves. What
    # the script keeps is the half that is this title's: which guid is which
    # item, and what the experiment means.
    "ab_experiments.py": Superseded("revenant.contrib.experiments", BY_IMPORT,
                                    "the guid-to-item mapping stays in the project"),
    # #48: the walk-find-UnityFS-export shell is `extract-scenes --from-dir`
    # now, so the file goes rather than getting thinner. What stays in the
    # project is where the pull landed and which entries matter.
    "extract_remote.py": Superseded("revenant extract-scenes --from-dir <dir>",
                                    BY_COMMAND),
}

# Where a project keeps its own scripts. Fixed rather than walked: `res/` holds
# hundreds of thousands of extracted files in a real project, and `status` should
# not pay for a full tree walk.
TOOL_DIRS = ("_tools", os.path.join("res", "_tools"), "tools")

# ...and where projects sitting side by side keep the scripts they share. The
# directory above a project is not a Project (there is no `revenant.toml` in it
# and ADR-0002 retired the layer above), so `status` never runs there -- which is
# why this half of the recurrence stayed invisible through the whole #47 audit
# (#50). Note that `config.workspace_root()` means this project's own root, not
# that directory; they are two different places and only one is ours.
#
# The shared directory is one *level* up but the scripts sit one folder inside it
# -- `../_tools/cdph/wrap_pe.py`, `../_tools/ifix/parse_patch.py` -- because each
# is a small project of its own. So the scan reads that directory and each of its
# immediate children, and stops. Bounded on purpose: `status` is a status query
# and must not pay for a tree walk, and the real directory above has nine
# extracted game packages beside it.
SHARED_TOOLS_DIR = "_tools"
# `SHARED_TAG` / `shared_label` -- the one sentence for "this is not any single
# project's" -- moved down into `config` when `lint` needed it too (#67), and
# are imported at the top of this file. Still read as `cli.SHARED_TAG` here,
# which is the point: one phrasing, wherever it is said from.


def superseded_tools(root: str) -> list:
    """One line per script a built-in has replaced; empty when clean.

    Covers this project's own tool directories and the `_tools/` one level up
    that the projects beside it share. Silent when the directory above holds no
    `_tools/`, so a project cloned out on its own sees no noise.
    """
    out = []
    for rel_dir in TOOL_DIRS:
        out.extend(_superseded_in(os.path.join(root, rel_dir), rel_dir))
    shared = os.path.normpath(os.path.join(root, os.pardir, SHARED_TOOLS_DIR))
    if shared in {os.path.normpath(os.path.join(root, d)) for d in TOOL_DIRS}:
        return out
    label = os.path.join(os.pardir, SHARED_TOOLS_DIR)
    out.extend(_superseded_in(shared, label, shared=True))
    for name in _subdirs(shared):
        out.extend(_superseded_in(os.path.join(shared, name),
                                  os.path.join(label, name), shared=True))
    return out


def _subdirs(directory: str) -> list:
    try:
        return sorted(n for n in os.listdir(directory)
                      if os.path.isdir(os.path.join(directory, n)))
    except OSError:
        return []


def _superseded_in(directory: str, label_dir: str, shared: bool = False) -> list:
    """The lines for one directory, non-recursively. Empty if it is not there."""
    if not os.path.isdir(directory):
        return []
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    out = []
    for name in names:
        entry = SUPERSEDED_TOOLS.get(name)
        path = os.path.join(directory, name)
        if entry is None or not os.path.isfile(path):
            continue
        if entry.kind == BY_IMPORT and _imports(path, entry.replacement):
            continue          # already a wrapper: the built-in is the body now
        where = f"{os.path.join(label_dir, name)}"
        if shared:
            where = shared_label(where)
        action = ("delete the copy and cite the command" if entry.kind == BY_COMMAND
                  else "make it a thin wrapper around the import")
        note = f"; {entry.note}" if entry.note else ""
        out.append(f"{where} is superseded by `{entry.replacement}` "
                   f"(#50; {action}{note})")
    return out


def _imports(path: str, module: str) -> bool:
    """Whether the file reaches for the construct that replaced its body.

    Two things this is deliberately not. Not "mentions revenant": a copy that
    only names it in a comment is still a copy. And not "imports revenant at
    all": a script pulling in some unrelated built-in would otherwise silence the
    alarm on a body it never replaced.

    What it accepts is the module itself or its owning package, because that is
    how the wrappers are actually written -- `revenant.contrib.decrypt.findvm`
    re-exports `find_dispatcher`, and the wrapper writes
    `from revenant.contrib.decrypt import find_dispatcher`. Matching only the
    full dotted path would never fire on a single real file.
    """
    package = module.rpartition(".")[0] or module
    pattern = re.compile(
        rf"^\s*(?:import\s+(?:{re.escape(module)}|{re.escape(package)})\b"
        rf"|from\s+(?:{re.escape(module)}|{re.escape(package)})[\w.]*\s+import\b)", re.M)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return bool(pattern.search(f.read()))
    except OSError:
        return False


def project_proxy_alarms(root: str) -> list:
    from . import describe as _describe
    # Wherever the generated skill actually is -- one copy shared by the projects
    # in a repository still gets counted. Reading only the project root made this
    # alarm silently return zero once the copy moved up, which is the failure
    # mode a proxy metric can least afford (#51).
    path = os.path.join(_describe.harness_root(root), _describe.HARNESS_MARKER)
    lines = 0
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                lines = sum(1 for _ in f)
        except OSError:
            lines = 0
    return proxy_alarms(skill_lines=lines,
                        default_commands=len(visible_commands()),
                        terms=len(_describe.CORE_TERMS))


def _step_build_indices(parsed: argparse.Namespace) -> int:
    from .indexer import build_indices
    out = os.path.join(version_ref_dir(parsed.version), "cpp2il_out")
    isil = os.path.join(out, "IsilDump")
    if not os.path.isdir(isil):
        print(f"IsilDump not found at {isil}. Run `revenant prepare --only run-cpp2il` first.", file=sys.stderr)
        return 1
    n = build_indices(isil, out)
    if not n:
        # An empty index means the ISIL dump is empty or truncated (a crashed
        # Cpp2IL run leaves the directory behind), and every downstream tool
        # would then report "not found" instead of "never indexed".
        print(f"No methods indexed — {isil} is empty or truncated. "
              f"Re-run `revenant prepare --only run-cpp2il --force` and check the Cpp2IL log.",
              file=sys.stderr)
        return 1
    print(f"Indices built: {out}/rva_index.json , asm_index.json")
    return 0


def prepare_steps() -> dict:
    """Name -> handler for `prepare --only`. Built per call so the handlers can
    live anywhere in this module (and be patched in tests)."""
    return {
        "extract-apks": _step_extract_apks,
        "find-binary": cmd_find_binary,
        "find-metadata": cmd_find_metadata,
        "run-cpp2il": _step_run_cpp2il,
        "build-indices": _step_build_indices,
        "seed-src": cmd_seed_src,
        "lua-extract": cmd_lua_extract,
        "ls-apk": _step_ls_apk,
    }


def cmd_prepare(parsed: argparse.Namespace) -> int:
    """Run the whole data-prep pipeline end to end (one command).

    extract-apks -> find-binary -> find-metadata -> run-cpp2il (ISIL+DiffableCs)
    -> build-indices -> seed-src -> lua-extract (xLua, if [lua] is configured).
    Expensive steps (Cpp2IL, indices) are skipped when already done; pass
    --force to redo them, --keep-going to continue past a failed step,
    --all to seed engine/3rd-party stubs too, --skip-lua to skip the Lua step.
    `--only <step>` runs one step by itself (extract-apks, find-binary,
    find-metadata, run-cpp2il, build-indices, seed-src, lua-extract; plus
    ls-apk, an inspection step outside the pipeline). Steps used to be their own
    commands; they were folded in here so the command list stays short.
    """
    import copy
    from . import config, lua
    # Line-buffer our own progress so the `==> [N/N]` banners interleave in the
    # right order with subprocess output even when stdout is captured/redirected
    # (block-buffered Python otherwise dumps all banners at exit).
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    flags = set(parsed.args)
    force = "--force" in flags
    keep_going = "--keep-going" in flags
    skip_lua = "--skip-lua" in flags
    seed_all = "--all" in flags
    ver = parsed.version
    out = os.path.join(version_ref_dir(ver), "cpp2il_out")

    def sub(args=()):
        s = copy.copy(parsed)
        s.args = list(args)
        return s

    only = _flag_options(parsed.args).get("only", "")
    if only or "--only" in flags:
        steps = prepare_steps()
        if only not in steps:
            print(f"prepare --only: unknown step {only!r}. Steps: "
                  + ", ".join(steps), file=sys.stderr)
            return 2
        # Pass the remaining flags through (--force, --all, --keep-bytecode).
        rest = [a for a in parsed.args if a not in ("--only", only)]
        return steps[only](sub(rest))

    if not xapk_path():
        print("No .apk/.xapk found in the project root. Drop the game package here, "
              "then re-run `revenant prepare`.", file=sys.stderr)
        return 1

    def _cpp2il_done() -> bool:
        # A crashed Cpp2IL run leaves a partial IsilDump/ behind, so directory
        # existence alone would make prepare skip the very step that needs
        # redoing. Trust the completion marker the runner drops; fall back to
        # the dirs + a non-empty index for projects prepared before the marker.
        if os.path.exists(os.path.join(out, ".cpp2il-complete")):
            return True
        idx = os.path.join(out, "rva_index.json")
        return (os.path.isdir(os.path.join(out, "IsilDump"))
                and os.path.isdir(os.path.join(out, "DiffableCs"))
                and os.path.exists(idx) and os.path.getsize(idx) > 2)

    def _indices_current() -> bool:
        # An index that predates the Cpp2IL output it describes is worse than no
        # index: it maps methods to paths in a dump that has since been
        # regenerated. The completion marker is touched at the end of every
        # successful Cpp2IL run, so comparing against it is an O(1) freshness
        # check — no walking the (huge) IsilDump tree.
        idx = os.path.join(out, "rva_index.json")
        if not os.path.exists(idx):
            return False
        marker = os.path.join(out, ".cpp2il-complete")
        if os.path.exists(marker) and os.path.getmtime(marker) > os.path.getmtime(idx):
            return False
        return True

    def _lua_step() -> int:
        try:
            st = lua.status(ver)
        except Exception:
            st = {"lua_bundles_in_apk": 0}
        if not st.get("lua_bundles_in_apk"):
            print("  not an xLua game (no Lua bundles) — skipping lua-extract")
            return 0
        if not lua.lua_cfg().get("xor_key"):
            print("  Lua bundles present but [lua].xor_key is not set in revenant.toml.\n"
                  "  Reverse the Lua loader, fill [lua], then: revenant lua-extract")
            return 0
        return cmd_lua_extract(sub(["--keep-bytecode"] if "--keep-bytecode" in flags else []))

    steps = [
        ("extract-apks",  lambda: _step_extract_apks(sub()), None),
        ("find-binary",   lambda: cmd_find_binary(sub()), None),
        ("find-metadata", lambda: cmd_find_metadata(sub()), None),
        ("run-cpp2il",    lambda: _step_run_cpp2il(sub()),
                          (lambda: not force and _cpp2il_done())),
        ("build-indices", lambda: _step_build_indices(sub()),
                          (lambda: not force and _indices_current())),
        ("seed-src",      lambda: cmd_seed_src(sub(["--all"] if seed_all else [])), None),
        ("lua-extract",   _lua_step, (lambda: skip_lua)),
    ]

    n = len(steps)
    failed: list[tuple[str, int]] = []
    for i, (label, fn, skip) in enumerate(steps, 1):
        if skip and skip():
            print(f"==> [{i}/{n}] {label}: skip (already done; --force to redo)")
            continue
        print(f"==> [{i}/{n}] {label}", flush=True)
        try:
            rc = fn()
        except Exception as exc:
            rc = 1
            print(f"  {type(exc).__name__}: {exc}", file=sys.stderr)
        if rc != 0:
            if keep_going:
                failed.append((label, rc))
                print(f"  step {label!r} failed (rc={rc}); --keep-going set, continuing.", file=sys.stderr)
                continue
            print(f"\nPrepare stopped at {label!r} (rc={rc}). Fix it and re-run "
                  f"`revenant prepare` (done steps are skipped), or use --keep-going.",
                  file=sys.stderr)
            return rc
    # --keep-going must not launder failures into a green exit: a batch run over
    # many projects only sees the exit code, and a project missing DiffableCs
    # (no src/ scaffold) looks identical to a healthy one until you read the log.
    if failed:
        print("\nPrepare finished with failures (--keep-going):", file=sys.stderr)
        for label, rc in failed:
            print(f"  {label} (rc={rc})", file=sys.stderr)
        print("Fix them and re-run `revenant prepare` (done steps are skipped).", file=sys.stderr)
        return 1
    print("\nPrepare complete. Open the project with your agent (`claude`); the `re` MCP server is wired up.")
    return 0


def _step_run_cpp2il(parsed: argparse.Namespace) -> int:
    return _run_bundled_script("run_cpp2il_isil.sh", parsed)


def cmd_seed_src(parsed: argparse.Namespace) -> int:
    """CoW-clone the DiffableCs game stubs into src/<version>/ (the scaffold)."""
    return _run_bundled_script("seed-src.sh", parsed)


def _run_bundled_script(name: str, parsed: argparse.Namespace) -> int:
    """Exec a bundled shell script against the project root.

    The script gets the project root (REVENANT_PROJECT + cwd), this interpreter
    (REVENANT_PY, so `from revenant import ...` works), and the resolved
    version/unity (REVENANT_VERSION / UNITY_VERSION) -- so it needs no in-tree
    package on sys.path.
    """
    import subprocess
    import importlib.resources as resources
    from . import config
    root = config.workspace_root()
    env = dict(
        os.environ,
        REVENANT_PROJECT=root,
        REVENANT_PY=sys.executable,
        REVENANT_VERSION=parsed.version,
        REVENANT_PLATFORM=config.detect_platform(),
        REVENANT_REF_DIR=config.version_ref_dir(parsed.version),
    )
    try:
        env["UNITY_VERSION"] = os.environ.get("UNITY_VERSION") or config.detect_unity_version()
    except Exception:
        pass
    sys.stdout.flush()   # emit our own output before the child writes to the fd
    sys.stderr.flush()
    try:
        with resources.as_file(resources.files("revenant").joinpath("scripts", name)) as p:
            return subprocess.run(["bash", str(p), *parsed.args], cwd=root, env=env).returncode
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        print(f"Bundled script {name!r} not found: {exc}", file=sys.stderr)
        return 1


# ── Commands ────────────────────────────────────────────────────────────────

def _step_ls_apk(parsed: argparse.Namespace) -> int:
    """List the package's contents. Inspection only; not part of the pipeline."""
    xapk = xapk_path()
    if not xapk:
        print("No XAPK found in workspace root", file=sys.stderr)
        return 1

    apks = extract_all_apks(xapk)
    for apk in apks:
        print(f"\n=== {os.path.basename(apk)} ===")
        for line in list_apk_contents(apk):
            print(f"  {line}")
    return 0


def _step_extract_apks(parsed: argparse.Namespace) -> int:
    xapk = xapk_path()
    if not xapk:
        print("No XAPK found", file=sys.stderr)
        return 1
    extracted = extract_all_apks(xapk)
    print(f"Extracted {len(extracted)} APK(s):")
    for path in extracted:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  {os.path.basename(path):50s} {size_mb:.1f} MB")
    return 0


def cmd_list_bundles(parsed: argparse.Namespace) -> int:
    """List AssetBundles in the package, optionally by group; --types counts object types instead.

    Usage: list-bundles [group] [--types] [--root PREFIX] [--limit N] [--unity-version V]
    """
    positional, opts = _split_args(parsed.args, boolean=("types",))
    located = find_base_apk(opts.get("root") or None)
    if not located:
        print("Base APK with a known bundle root not found in _apks/. "
              "Run `revenant prepare --only extract-apks` first.", file=sys.stderr)
        return 1
    apk, bundle_root = located
    group = positional[0] if positional else None
    if "types" in opts:
        return _list_bundle_types(apk, bundle_root, group, opts)
    bundles = list_bundles(apk, group, bundle_root)
    if not bundles:
        print(f"No bundles found{f' for group {group}' if group else ''}.")
        return 1
    by_group: dict[str, list[tuple[str, int]]] = {}
    for g, name, size in bundles:
        by_group.setdefault(g, []).append((name, size))
    for g in sorted(by_group):
        items = by_group[g]
        total = sum(s for _, s in items)
        print(f"\n=== {g} ({len(items)} bundles, {total/1024/1024:.1f} MB) ===")
        for name, size in items:
            print(f"  {name:60s} {size/1024:>9.1f} KB")
    print(f"\nTotal: {len(bundles)} bundles")
    return 0


def _no_unitypy() -> int:
    """The one place the asset commands say the optional extra is missing."""
    print("UnityPy is not installed: pip install 'revenant-re[assets]'", file=sys.stderr)
    return 1


def _list_bundle_types(apk: str, bundle_root: str, group: str | None, opts: dict) -> int:
    """The census `list-bundles --types` prints: what is in there, unpacked nothing."""
    from . import assets as _assets
    _assets.set_unity_version(opts.get("unity-version") or None)
    limit = int(opts["limit"]) if opts.get("limit", "").isdigit() else None
    try:
        census = _assets.census_package(apk, bundle_root, group, limit=limit)
    except ImportError:
        return _no_unitypy()
    where = bundle_root if group is None else f"{bundle_root} [{group}]"
    print(f"{where}: {census.parsed} bundle(s) read, {len(census.errors)} unreadable")
    for tname, count in census.type_counts.most_common():
        print(f"  {tname:28s} {count:>8,}")
    # With a handful of bundles the per-bundle split is the interesting half
    # (which bundle holds the MonoBehaviours); with hundreds it is noise.
    if 1 < census.parsed <= 20:
        print("\nper bundle:")
        for name, counts in census.per_member.items():
            top = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:5])
            print(f"  {os.path.basename(name):48s} {top}")
    for name, reason in census.errors[:10]:
        print(f"  ERR {name}: {reason}", file=sys.stderr)
    return 0 if census.parsed else 1


def cmd_extract_scenes(parsed: argparse.Namespace) -> int:
    """Unpack AssetBundles into res/ (--out moves that); --ggm reads the baked-in files, --from-dir a directory of bundles already on disk.

    Usage: extract-scenes [group|--all] [bundles...] [--by-script] [--out DIR] [--root PREFIX] [--unity-version V]
           extract-scenes --ggm [--by-script] [--out DIR] [--unity-version V]   (no group: the layout names the files)
           extract-scenes --from-dir DIR [--by-script] [--out DIR] [--unity-version V]  (bundles already on disk)

    `--out DIR` moves the landing spot, relative to the current directory.
    Every source honours it, because the reason it exists is a project whose
    downstream scripts read the path its own extraction script produced -- and
    teaching revenant that title's directory name would be teaching it a game
    fact (ADR-0004).

    It moves the *root* and nothing else. What is under it -- the per-type
    tree, `.bytes` for a TextAsset, the sanitised stem -- is revenant's own
    layout, the same for every title, and bending it to match one project's
    old script is the thing this flag exists to avoid.
    """
    positional, opts = _split_args(parsed.args, boolean=("by-script", "ggm", "all"))
    by_script = "by-script" in opts
    unity_version = opts.get("unity-version") or None
    res_root, problem = _out_arg(opts)
    if problem:
        return 1
    if "ggm" in opts:
        return _extract_ggm(by_script=by_script, unity_version=unity_version,
                            res_root=res_root)
    if "from-dir" in opts:
        return _extract_from_dir(opts.get("from-dir") or "", by_script=by_script,
                                 unity_version=unity_version, res_root=res_root)
    if "all" in opts:
        # No group is named, so every positional is a bundle filter, not a group.
        group, bundles = None, positional or None
    else:
        group = positional[0] if positional else MAIN_STORYLINE_GROUP
        bundles = positional[1:] or None
    # `parsed.root`, not `opts["root"]`: `--root` is in
    # `GLOBAL_OPTIONS_WITH_VALUES`, so `normalize_global_args` hoists it out of
    # the subcommand's arguments wherever it appears and it never reaches
    # `_split_args`. The flag has therefore never worked -- while
    # `SUPERSEDED_TOOLS` cites it as the reason to delete a project's own
    # script. Outside this ticket's two gaps, but a documented flag that does
    # nothing is worse than one that is missing.
    try:
        reports = extract_group(group, res_root=res_root, bundles=bundles,
                                verbose=True, by_script=by_script,
                                bundle_root=parsed.root or None,
                                unity_version=unity_version)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # The root it wrote into, not `res/` unconditionally and not one report's
    # parent: with `--all` the reports span several groups, so `dirname` of the
    # first names a directory that is one of many. A summary naming the wrong
    # place is a line a note would quote.
    from . import config as _cfg
    landed = res_root or os.path.join(_cfg.workspace_root(), "res")
    where = f"{landed}/{group}/" if group else f"{landed}/ (every group)"
    print(f"\nExtracted {len(reports)} bundle(s) into {where}")
    grand = {}
    for r in reports:
        _report_line(r, where=False, scene=True)
        for k, v in r.exported.items():
            grand[k] = grand.get(k, 0) + v
    print("\n  TOTAL exported: " + ", ".join(f"{k}:{v}" for k, v in sorted(grand.items())))
    return 0


def _out_arg(opts: dict):
    """`(landing root or None, whether to stop)`.

    Present-but-empty is refused rather than treated as absent: `--out` with no
    value silently landing in `res/` drops the caller's landing spot and calls
    the run a success, and the sibling `--from-dir` already refuses the same
    shape. An existing non-directory is refused here too, where it can be said,
    rather than as a `NotADirectoryError` traceback from inside the export.
    """
    if "out" not in opts:
        return None, False
    where = opts.get("out") or ""
    if not where:
        print("--out takes a directory", file=sys.stderr)
        return None, True
    if os.path.exists(where) and not os.path.isdir(where):
        print(f"--out: {where} is not a directory", file=sys.stderr)
        return None, True
    return where, False


def _report_line(report, where: bool = True, scene: bool = False) -> None:
    """One bundle's result, phrased once.

    Three call sites printed this and the third dropped the errors line, which
    is the only place a gzip body that would not inflate is reported -- on the
    source (`--from-dir`) where a truncated download is the likely cause.
    """
    exported = ", ".join(f"{k}:{v}" for k, v in report.exported.most_common())
    head = f"\n  {report.name}"
    if where:
        head += f" ({report.size/1024/1024:.1f} MB) -> {report.out_dir}"
    print(head)
    if scene:
        print(f"    scene: {', '.join(report.scene_paths) or '(no scene container)'}")
    print(f"    exported: {exported or '(none)'}")
    if report.unpacked:
        print("    unpacked: " + ", ".join(f"{k}:{v}"
                                           for k, v in report.unpacked.most_common()))
    if report.errors:
        print(f"    errors: {len(report.errors)} (see _bundle.json)")


def _extract_ggm(by_script: bool = False, unity_version: str | None = None,
                 res_root: str | None = None) -> int:
    """`extract-scenes --ggm`: export what the build baked into the player itself.

    The layout has declared `globalgamemanagers` and `data.unity3d` all along;
    until #47 no command read them, so a title that ships its numeric layer in
    `Resources/` read as "everything is remote".
    """
    from . import assets as _assets
    try:
        reports = _assets.extract_ggm(res_root, by_script=by_script,
                                      unity_version=unity_version)
    except ImportError:
        return _no_unitypy()
    if not reports:
        print(f"No {' / '.join(os.path.basename(p) for p in _assets.GGM_PATHS)} "
              f"found in this project's package.", file=sys.stderr)
        return 1
    for r in reports:
        _report_line(r)
    return 0 if any(r.loaded for r in reports) else 1


def _extract_from_dir(directory: str, by_script: bool = False,
                      unity_version: str | None = None,
                      res_root: str | None = None) -> int:
    """`extract-scenes --from-dir <dir>`: bundles already sitting on disk.

    One title pulled 204 bundles off a device, another fetched 1,259 (872 MB)
    from a CDN, and each wrote its own "walk it, find UnityFS, export by type"
    script -- while `contrib.cache.export_bundle_dir` already did exactly that,
    through the same `assets.export_blob` a packaged bundle goes through. The
    capability was here and the entry point knew one kind of input, which is
    the shape five of #48's nine gaps share.

    Non-bundles are counted, not hidden: every Unity cache holds `__info`
    files, and a run that quietly skipped them would leave the reader unable to
    tell "this directory held no bundles" from "I only looked at some of it".
    """
    from . import config as _config
    from .contrib import cache as _cache
    if not directory:
        print("Usage: extract-scenes --from-dir <directory>", file=sys.stderr)
        return 1
    res_root = res_root or os.path.join(_config.workspace_root(), "res")
    try:
        reports = _cache.export_bundle_dir(directory, res_root, by_script=by_script,
                                           unity_version=unity_version)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ImportError:
        return _no_unitypy()
    # On whether the blob PARSED, not on whether it exported something
    # countable: a bundle holding only AnimationClips writes its names file and
    # increments nothing, and calling that "not a bundle" reports our own gap as
    # the file's content.
    loaded = [r for r in reports if r.loaded]
    skipped = [r for r in reports if not r.loaded]
    for r in loaded:
        _report_line(r)
    if not reports:
        print(f"{directory} holds no files.", file=sys.stderr)
        return 1
    print(f"\n  {len(loaded)} of {len(reports)} file(s) read as bundles"
          + (f"; {len(skipped)} were not (no UnityFS signature, unreadable, or "
             f"would not load)" if skipped else ""))
    problems = sum(len(r.errors) for r in loaded)
    if problems:
        print(f"  {problems} problem(s) inside the bundles that did load "
              f"(each bundle's _bundle.json lists its own)")
    return 0 if loaded else 1


def cmd_find_binary(parsed: argparse.Namespace) -> int:
    """Locate the IL2CPP binary (libil2cpp.so / UnityFramework)."""
    try:
        loc = find_libil2cpp(parsed.root)
        size = os.path.getsize(loc.path)
        print("IL2CPP binary found:")
        print(f"  path:   {loc.path}")
        print(f"  source: {loc.source}")
        print(f"  size:   {size:,} bytes ({size/1024/1024:.1f} MB)")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_import_metadata(parsed: argparse.Namespace) -> int:
    """Install a metadata image dumped from a running process."""
    from .packed import cache_name, repair_metadata
    if not parsed.args:
        print("usage: revenant import-metadata <dump-file>", file=sys.stderr)
        return 2
    src = parsed.args[0]
    with open(src, "rb") as f:
        data = f.read()
    try:
        repaired, notes = repair_metadata(data)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    dest_dir = os.path.join(workspace_root(), "_binaries")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, cache_name(repaired, "-global-metadata.dat"))
    with open(dest, "wb") as f:
        f.write(repaired)
    for note in notes:
        print(f"  {note}")
    print(f"Imported {len(repaired):,} bytes -> {dest}")
    print("Now run: revenant prepare")
    return 0


def cmd_patch_binary(parsed: argparse.Namespace) -> int:
    """Write an analysis-only copy of libil2cpp.so that Cpp2IL can parse."""
    from .binary import find_libil2cpp
    from .packed import cache_name, repair_elf_for_analysis
    loc = find_libil2cpp(parsed.root)
    with open(loc.path, "rb") as f:
        data = f.read()
    repaired, notes = repair_elf_for_analysis(data)
    dest = os.path.join(os.path.dirname(loc.path),
                        cache_name(repaired, "-libil2cpp.analysis.so"))
    with open(dest, "wb") as f:
        f.write(repaired)
    for note in notes:
        print(f"  {note}")
    print(f"Wrote {len(repaired):,} bytes -> {dest}")
    print("prepare (run-cpp2il) prefers *-libil2cpp.analysis.so when present.")
    return 0


def cmd_find_metadata(parsed: argparse.Namespace) -> int:
    """Locate global-metadata.dat and print its header facts."""
    try:
        loc = find_global_metadata(parsed.root)
        size = os.path.getsize(loc.path)
        meta = Il2CppMetadata(loc.path)
        print(f"global-metadata.dat found:")
        print(f"  path:   {loc.path}")
        print(f"  source: {loc.source}")
        print(f"  size:   {size:,} bytes")
        print(f"  sanity: 0x{meta.sanity:08X}")
        print(f"  version: {meta.version}")
        print(f"  string literals: {meta.string_literal_count}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _mode_arg(value: str) -> str | None:
    """Map a CLI mode token to a force_mode (arm/thumb) or None for auto."""
    v = (value or "").lower()
    if v in {"arm", "arm32"}:
        return "arm"
    if v in {"thumb", "thumb2", "t"}:
        return "thumb"
    return None  # auto / empty / unknown


def cmd_disasm(parsed: argparse.Namespace) -> int:
    """Disassemble at an RVA (arch auto-detected: ARM64 / ARM32 / Thumb)."""
    rva = _arg(parsed, 0)
    if not rva:
        print("Usage: disasm <rva> [byte_count] [arm|thumb]  (ARM32 only; auto by default)",
              file=sys.stderr)
        return 1
    byte_count = int(_arg(parsed, 1, "0x100"), 0)
    force_mode = _mode_arg(_arg(parsed, 2, ""))
    try:
        print(simple_disasm_report(rva, parsed.version, byte_count, force_mode=force_mode))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_evidence(parsed: argparse.Namespace) -> int:
    """Full evidence packet for one RVA, for reconstruction."""
    rva = _arg(parsed, 0)
    if not rva:
        print("Usage: evidence <rva> [byte_count] [arm|thumb]", file=sys.stderr)
        return 1
    byte_count = int(_arg(parsed, 1, "0x100"), 0)
    force_mode = _mode_arg(_arg(parsed, 2, ""))
    try:
        print(evidence_report(rva, parsed.version, byte_count, force_mode=force_mode))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_lookup(parsed: argparse.Namespace) -> int:
    """Look up the method at an RVA."""
    rva = _arg(parsed, 0)
    if not rva:
        print("Usage: lookup <rva>", file=sys.stderr)
        return 1
    if not VERSIONS:
        print("No indices loaded. Run 'find-asm' against raw IsilDump or build indices first.",
              file=sys.stderr)
        return 1
    print(lookup_rva(rva, parsed.version))
    return 0


def cmd_search(parsed: argparse.Namespace) -> int:
    """Search the indices by symbol name."""
    query = " ".join(parsed.args) if parsed.args else ""
    if not query:
        print("Usage: search <query>", file=sys.stderr)
        return 1
    if not VERSIONS:
        print("No indices loaded.", file=sys.stderr)
        return 1
    print(search_symbols(query, parsed.version))
    return 0


def cmd_xrefs(parsed: argparse.Namespace) -> int:
    """Direct cross-references to an RVA (bl/b only; virtual dispatch is invisible)."""
    rva = _arg(parsed, 0)
    if not rva:
        print("Usage: xrefs <rva> [limit]", file=sys.stderr)
        return 1
    limit = int(_arg(parsed, 1, "30"))
    try:
        root = None
        if parsed.root:
            root = os.path.join(parsed.root, "IsilDump", "Assembly-CSharp")
        print(find_xrefs(rva, parsed.version, limit, root=root or ""))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_callgraph(parsed: argparse.Namespace) -> int:
    """Callers and callees of an RVA."""
    rva = _arg(parsed, 0)
    if not rva:
        print("Usage: callgraph <rva> [limit]", file=sys.stderr)
        return 1
    limit = int(_arg(parsed, 1, "20"))
    try:
        root = None
        if parsed.root:
            root = os.path.join(parsed.root, "IsilDump", "Assembly-CSharp")
        print(callgraph(rva, parsed.version, limit, root=root or ""))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_find_asm(parsed: argparse.Namespace) -> int:
    """The IsilDump assembly for an RVA."""
    rva = _arg(parsed, 0)
    if not rva:
        print("Usage: find-asm <rva>", file=sys.stderr)
        return 1
    if not VERSIONS:
        print("No indices loaded. Build indices first.", file=sys.stderr)
        return 1
    print(find_asm_by_rva(rva, parsed.version))
    return 0


def cmd_cfg(parsed: argparse.Namespace) -> int:
    """Control-flow graph: basic blocks, loops, what runs unconditionally."""
    rva = _arg(parsed, 0)
    if not rva:
        print("Usage: cfg <rva>", file=sys.stderr)
        return 1
    if not VERSIONS:
        print("No indices loaded. Build indices first.", file=sys.stderr)
        return 1
    print(build_cfg_report(rva, parsed.version))
    return 0


# ── metadata strings and protobuf schemas (query tier, #32) ─────────────────

def cmd_strings(parsed: argparse.Namespace) -> int:
    """Dump the metadata string literals, bucketed (URLs, events, config keys, format strings, flags, paths)."""
    from . import strings as _strings
    from .binary import find_global_metadata
    opts = _flag_options(parsed.args)
    try:
        loc = find_global_metadata(parsed.root)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    sd = _strings.dump(loc.path)
    from . import config
    out_dir = opts.get("out") or os.path.join(config.workspace_root(), "res", "metadata-strings")
    stats = _strings.write_dump(sd, out_dir)
    print(json.dumps(stats))
    print(f"written to {out_dir}", file=sys.stderr)
    return 0


def cmd_pb_schema(parsed: argparse.Namespace) -> int:
    """Rebuild a protobuf schema (.proto + JSON) from Google.Protobuf codegen stubs: pb-schema <stub-dir> [--out FILE]."""
    from . import protobuf as _pb
    opts = _flag_options(parsed.args)
    stub_dir = _arg(parsed, 0)
    if not stub_dir or not os.path.isdir(stub_dir):
        print("Usage: pb-schema <dir of Cpp2IL .cs stubs> [--out schema.proto]", file=sys.stderr)
        return 1
    schema = _pb.Schema.from_stubs(stub_dir)
    text = schema.to_proto()
    out = opts.get("out")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"messages={len(schema.messages)} enums={len(schema.enums)} -> {out}")
    else:
        print(text)
    return 0


def cmd_pb_tags(parsed: argparse.Namespace) -> int:
    """Recover protobuf field numbers for ProtoBaseProxy messages by disassembling MergeFrom: pb-tags <stub-dir> <libil2cpp.so> [--out FILE]."""
    from . import protobuf as _pb
    opts = _flag_options(parsed.args)
    stub_dir, binary = _arg(parsed, 0), _arg(parsed, 1)
    if not stub_dir or not binary or not os.path.isdir(stub_dir) or not os.path.exists(binary):
        print("Usage: pb-tags <dir of Cpp2IL .cs stubs> <libil2cpp.so> [--out schema.json]", file=sys.stderr)
        return 1
    schema, stats = _pb.recover_schema(stub_dir, binary)
    out = opts.get("out")
    if out:
        _pb.dump_json(schema, out)
    print(json.dumps(stats, indent=1))
    return 0


# ── FlatBuffers, the symmetric half of the protobuf family (query tier, #50) ─

def _fb_load_schema(path: str):
    from . import flatbuffers as _fb
    with open(path, encoding="utf-8") as f:
        return _fb.Schema.from_dict(json.load(f))


def cmd_fb_dump(parsed: argparse.Namespace) -> int:
    """Walk a FlatBuffers buffer with no schema -- shape, present slots, strings: fb-dump <file> [--tree N] [--strings] [--grep TEXT]."""
    from . import flatbuffers as _fb
    positional, opts = _split_args(parsed.args, boolean=("strings",))
    path = positional[0] if positional else ""
    if not path or not os.path.isfile(path):
        print("Usage: fb-dump <buffer.bin> [--tree N] [--strings] [--grep TEXT]", file=sys.stderr)
        return 1
    with open(path, "rb") as f:
        data = f.read()
    print(f"{os.path.basename(path)}  {len(data):,} bytes  root @0x{_fb.Buffer(data).root():x}")
    if "strings" in opts or "grep" in opts:
        needle = (opts.get("grep") or "").lower()
        seen, shown = set(), 0
        for at, s in _fb.strings(data):
            if s in seen:
                continue
            seen.add(s)
            if needle and needle not in s.lower():
                continue
            print(f"  0x{at:08x}  {s}")
            shown += 1
        print(f"\n{shown} strings shown, {len(seen)} distinct in buffer")
        return 0
    shape = _fb.walk(data, max_depth=int(opts.get("tree", 1)))
    _print_shape(shape, "")
    return 0


def _print_shape(shape, indent: str) -> None:
    print(f"{indent}table @0x{shape.offset:x}: {shape.slots} slots")
    for slot in shape.present:
        mark = "  (inferred)" if slot.reading.inferred else ""
        print(f"{indent}  slot {slot.index:2d}  {slot.reading.kind:<7} {slot.reading.value}{mark}")
    for child in shape.children:
        _print_shape(child, indent + "    ")


def cmd_fb_schema(parsed: argparse.Namespace) -> int:
    """Recover a FlatBuffers schema from the IL2CPP stubs (SerializeToBuffer + field offsets): fb-schema <isil-dir> <src-dir> [--out FILE] [--guid-roots A,B] [--unresolved]."""
    from . import flatbuffers as _fb
    positional, opts = _split_args(parsed.args, boolean=("unresolved",))
    isil = positional[0] if positional else ""
    src = positional[1] if len(positional) > 1 else ""
    if not isil or not src or not os.path.isdir(isil) or not os.path.isdir(src):
        print("Usage: fb-schema <cpp2il IsilDump dir> <reconstructed src dir> "
              "[--out schema.json] [--guid-roots Name,Name] [--unresolved]", file=sys.stderr)
        return 1
    roots = tuple(r.strip() for r in (opts.get("guid-roots") or "").split(",") if r.strip())
    recovered = _fb.recover_schema(isil, src, guid_roots=roots)
    out = opts.get("out")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(recovered.to_dict(), f, indent=1, ensure_ascii=False, sort_keys=True)
    if "unresolved" in opts:
        for fqn, slot, kind in recovered.unresolved:
            print(f"  slot {slot:>2} {kind:<8} {fqn}")
    print(json.dumps(recovered.summary(), indent=1))
    if out:
        print(f"-> {out}", file=sys.stderr)
    return 0


def cmd_fb_read(parsed: argparse.Namespace) -> int:
    """Decode a FlatBuffers buffer against a recovered schema: fb-read <file> --schema FILE --type Class [--containers A,B] [--depth N] [--limit N]."""
    from . import flatbuffers as _fb
    positional, opts = _split_args(parsed.args, boolean=("tables",))
    path = positional[0] if positional else ""
    # `--type`, not `--root`: `--root` is a global option naming the project
    # directory and never reaches a subcommand's own argument list.
    schema_path, root = opts.get("schema"), opts.get("type")
    if not path or not os.path.isfile(path) or not schema_path or not root:
        print("Usage: fb-read <buffer.bin> --schema schema.json --type RootClassName "
              "[--containers Name,Name] [--depth N] [--limit N] [--tables]", file=sys.stderr)
        return 1
    with open(path, "rb") as f:
        data = f.read()
    containers = tuple(c.strip() for c in (opts.get("containers") or "").split(",") if c.strip())
    schema = _fb_load_schema(schema_path)
    reader = _fb.Reader(data, schema, containers=containers,
                        max_depth=int(opts.get("depth", 3)), limit=int(opts.get("limit", 5)))
    if "tables" in opts:
        fields, present = schema.fields(root), reader.present()
        unions = schema.unions(root)
        tags = {tag: value for value, tag in unions.items() if tag != value}
        for slot in sorted(fields):
            f = fields[slot]
            # A tag slot is half a field, and the decode reports it with its
            # other half. Listing it as one of its own is how the listing and
            # the decode come to disagree about how many fields there are.
            pair = (f"  (union tag for slot {tags[slot]})" if slot in tags else
                    f"  (union; its tags are in slot {unions[slot]})"
                    if slot in unions else "")
            print(f" {' ' if slot in present else '-'} {slot:>2}  "
                  f"{f['name']:<32} {f.get('cs_type', '')}{pair}")
        return 0
    print(json.dumps(reader.read(root), indent=1, ensure_ascii=False))
    if reader.inferred:
        print(f"{len(reader.inferred)} values were probed, not read from a declared type",
              file=sys.stderr)
    for note in reader.notes:
        print(f"note: {note}", file=sys.stderr)
    return 0


def cmd_luban_read(parsed: argparse.Namespace) -> int:
    """Decode a Luban binary table against a project schema: luban-read <file> --schema FILE [--type Bean] [--limit N]."""
    from . import luban as _luban
    positional, opts = _split_args(parsed.args, boolean=("fields",))
    path = positional[0] if positional else ""
    schema_path = opts.get("schema")
    if not path or not os.path.isfile(path) or not schema_path:
        print("Usage: luban-read <table.bytes> --schema schema.json [--type Bean] "
              "[--container file.py] [--limit N] [--fields]", file=sys.stderr)
        print("\nThe schema is the project's -- bean names and field types are "
              "facts about\nthe title. Its shape:\n", file=sys.stderr)
        print(_luban.SCHEMA_DOC, file=sys.stderr)
        return 1
    try:
        schema = _luban.load_schema(schema_path)
    except (OSError, ValueError) as exc:
        print(f"Cannot load {schema_path}: {exc}", file=sys.stderr)
        return 1
    stem = os.path.splitext(os.path.basename(path))[0]
    bean = opts.get("type") or schema.tables.get(stem, "")
    if not bean:
        known = ", ".join(sorted(schema.tables)[:8]) or "none"
        print(f"No bean for {stem!r}: pass --type, or add it to the schema's "
              f"`tables` map (it lists {known})", file=sys.stderr)
        return 1
    # The container is the project's code either way; `--container` names the
    # file, and with none the blob has to be plaintext already. Without this the
    # command could not read either shipped title -- both wrap their tables --
    # and `table list` would be the only way in, which is not a CLI, it is a
    # detour.
    from . import config as _config
    try:
        container = _config.load_project_callable(
            opts.get("container"), "decode", "--container")
    except (OSError, RuntimeError) as exc:
        print(f"{exc}", file=sys.stderr)
        return 1
    with open(path, "rb") as f:
        blob = f.read()
    try:
        out = _luban.read_table(blob, schema, bean, container=container)
    except _luban.LubanError as exc:
        print(f"{exc}", file=sys.stderr)
        if exc.stage == _luban.STAGE_HEADER and container is None:
            print("If this title encrypts or wraps its tables, pass --container "
                  "<file.py> exposing `decode(data) -> bytes`: the container and "
                  "its key stay in the project.", file=sys.stderr)
        return 1
    if "fields" in opts:
        for name in out.fields:
            print(name)
        return 0
    limit = int(opts.get("limit", 0) or 0)
    shown = out.rows[:limit] if limit else out.rows
    print(json.dumps(list(shown), indent=1, ensure_ascii=False, default=_json_safe))
    print(f"{len(out.rows)} rows, {len(out.fields)} fields, bean {out.bean}",
          file=sys.stderr)
    if out.trailing:
        from . import tables as _tables
        print(f"WARNING: {_tables.misaligned(out)}", file=sys.stderr)
    return 0


def _json_safe(value):
    """Luban `bytes` fields are not JSON; show their size rather than dying."""
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    raise TypeError(f"cannot serialise {type(value).__name__}")


def _table_refs(parsed: argparse.Namespace) -> int:
    """`table refs <table> [--limit N]` -- how often it is named, per corpus.

    Facts only. A zero is printed as a zero and nothing here calls a table dead:
    one title's parser reads override rows before parsing any table, so no
    specific reference does not mean not loaded. That judgement belongs in a
    note, which is the same line the ledger draws.

    The table is resolved and never read. Counting mentions of a name needs the
    name, not the rows, so a 200k-row blob is not decoded to answer this -- and
    a table whose bytes will not decode at all still gets a straight answer.
    """
    from . import refs as _refs, tables as _tables
    positional, opts = _split_args(parsed.args[1:])
    name = positional[0] if positional else ""
    if not name:
        print("Usage: table refs <table> [--limit N]", file=sys.stderr)
        print("(`revenant table list` names them)", file=sys.stderr)
        return 1
    limit = _limit_arg(opts, default=5)
    if limit is None:
        return 1
    try:
        table = _tables.resolve_any(name)
    except _tables.TableError as exc:
        print(f"{exc}", file=sys.stderr)
        return 1
    owner = _tables.project_root_of(table.path)
    readers = _tables.readers_for(owner)
    found = _tables.discover(claimed=_tables.claimed_names())
    all_names = {t.name for t in found.tables()}
    searched = [table.name]
    row_class = readers.row_class(table)
    if row_class and row_class not in searched:
        searched.append(row_class)

    print(f"{table.name}  ({table.corpus}, {os.path.basename(table.path)})")
    print(f"searching for: {', '.join(searched)}")
    if len(searched) == 1:
        print("(no row class known -- no schema here names one, so a row class "
              "the codegen\n spelled differently would not be found)")
    # The table resolved in its own project -- its readers, its row class -- but
    # the corpora below are this one's: a version and a metadata blob are read
    # from the project you are standing in, and there is no per-root way to ask
    # for either. Counting a sibling title's table name in this title's source
    # is a real question; letting it read as *that* title's count is not.
    # `realpath` on both sides, not `abspath`: on macOS `/tmp` is a symlink to
    # `/private/tmp` and `workspace_root()` comes back resolved, so a path typed
    # through any symlink compared unequal and the project's own table was
    # announced as another project's.
    here = os.path.realpath(workspace_root())
    if os.path.realpath(owner) != here:
        print(f"(this table is in another project; the corpora below are "
              f"{os.path.basename(here)}'s, so this counts how often this "
              f"project names it)")
    print()
    for corpus in _refs.reference_corpora(searched, all_names=all_names):
        for line in _refs.refs_report(corpus, limit):
            print(line)
    print(f"\n{_refs.REFS_FOOTER}")
    return 0


def _table_diff(parsed: argparse.Namespace) -> int:
    """`table diff <A> <B> [--normalize-names] [--key F] [--limit N]`.

    Two files compare their rows; two corpus directories compare which tables
    each holds, which is how a pair of related titles gives up a feature-
    difference list without a line of code being read.
    """
    from . import tables as _tables
    positional, opts = _split_args(parsed.args[1:], boolean=("normalize-names",))
    if len(positional) < 2:
        print("Usage: table diff <table A> <table B> [--normalize-names] "
              "[--key FIELD] [--limit N]", file=sys.stderr)
        print("       table diff <corpus A> <corpus B>   (two directories: "
              "which tables each side has)", file=sys.stderr)
        print("(a path may point into another project; it is read with that "
              "project's own schema and keys)", file=sys.stderr)
        return 1
    limit = _limit_arg(opts)
    if limit is None:
        return 1
    if all(os.path.isdir(p) for p in positional[:2]):
        return _corpus_diff(positional[0], positional[1], limit)

    sides = []
    for name in positional[:2]:
        try:
            data = _tables.read_any(name)
        except _tables.TableError as exc:
            print(f"{exc}", file=sys.stderr)
            return 1
        if data.error:
            print(f"{name}: {data.error}", file=sys.stderr)
            return 1
        sides.append(data)
    a, b = sides
    try:
        out = _tables.diff(a.rows, b.rows, key=opts.get("key", ""),
                           normalize_names="normalize-names" in opts)
    except _tables.TableError as exc:
        print(f"{exc}", file=sys.stderr)
        return 1

    # The path as typed, not the corpus-relative one: two projects with the same
    # layout both say `res/conf/X.json`, and a report that cannot tell its own
    # two sides apart is not a report.
    for side, data, given in (("A", a, positional[0]), ("B", b, positional[1])):
        print(f"{side}  {data.table.name:<24} {len(data.rows):>6} rows  "
              f"{len(data.fields):>3} fields  {data.reader:<12} {given}")
    print(f"\n{_tables.alignment(out)}")
    counts = f"{out.same} the same · {len(out.only_in_a)} only in A · " \
             f"{len(out.only_in_b)} only in B"
    if out.undetermined:
        counts += f" · {out.undetermined} undetermined"
    print(f"rows      {counts}")
    for label, keys in (("A", out.only_in_a), ("B", out.only_in_b)):
        if keys:
            shown = ", ".join(str(k) for k in keys[:limit])
            more = f" ... and {len(keys) - limit} more" if len(keys) > limit else ""
            print(f"          only in {label}: {shown}{more}")
    for label, names in (("A", out.fields_only_in_a), ("B", out.fields_only_in_b)):
        if names:
            print(f"fields    only in {label}: {', '.join(str(n) for n in names)}")
    if (out.fields_only_in_a and out.fields_only_in_b
            and "normalize-names" not in opts):
        print("          (--normalize-names aligns camelCase / PascalCase / "
              "snake_case before comparing)")

    by_row = {}
    for change in out.changed:
        by_row.setdefault(change.key, []).append(change)
    print(f"values    {len(by_row)} rows differ in "
          f"{len({c.field for c in out.changed})} fields")
    for key in list(by_row)[:limit]:
        shown = ", ".join(f"{c.field}: {_tables.show(c.a)} -> {_tables.show(c.b)}"
                          for c in by_row[key][:6])
        print(f"          {key}  {shown}")
    if len(by_row) > limit:
        print(f"          ... {len(by_row) - limit} more rows differ")

    # Kept apart from the count above on purpose, and phrased by `tables` so the
    # one sentence this command exists for has one wording.
    for column in out.incomparable:
        print(f"\nnot comparable  {_tables.decode_warning(column)}")
    for line in out.notes:
        print(f"note      {line}")
    return 0


def _limit_arg(opts: dict, default: int = 10):
    """`--limit`, or None once the problem has been reported.

    Clamped rather than trusted, for the reason `census` writes down: a negative
    reaches a slice as `[:-1]`, which prints everything but the last row and
    then claims `... -1 more`. Every command taking `--limit` comes through
    here -- the one that did not went straight back to that bug.
    """
    raw = opts.get("limit", default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        print("--limit takes a number", file=sys.stderr)
        return None
    if value < 0:
        print("--limit takes a count of 0 or more", file=sys.stderr)
        return None
    return value


def _corpus_diff(dir_a: str, dir_b: str, limit: int) -> int:
    """Which tables each side has. The by-product the ticket calls useful.

    A pair of related titles gives up its feature differences this way -- one
    reference pair produced 172 tables new on one side and 56 unique to the
    other -- so the names are printed, not just counted.
    """
    from . import tables as _tables
    sides = []
    for directory in (dir_a, dir_b):
        root = _tables.project_root_of(os.path.join(directory, "x"))
        found = _tables.discover(root, claimed=_tables.claimed_names(root))
        corpus = next((c for c in found.corpora
                       if os.path.abspath(c.path) == os.path.abspath(directory)), None)
        if corpus is None:
            print(f"{directory}: not a table corpus in {root} "
                  f"(`revenant table list` shows the ones that are)", file=sys.stderr)
            return 1
        sides.append({t.name: t for t in corpus.tables})
    a, b = sides
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    both = sorted(set(a) & set(b))
    print(f"A  {dir_a}   {len(a)} tables")
    print(f"B  {dir_b}   {len(b)} tables")
    print(f"\ntables    {len(both)} in both · {len(only_a)} only in A · "
          f"{len(only_b)} only in B")
    for label, names in (("A", only_a), ("B", only_b)):
        for name in names[:limit]:
            print(f"          only in {label}  {name}")
        if len(names) > limit:
            print(f"          ... and {len(names) - limit} more only in {label}")
    print("\n(`table diff <A>/<name> <B>/<name>` compares one table's rows)")
    return 0


def _table_census(parsed: argparse.Namespace) -> int:
    """`table census <table> [--top N]` -- one line per field."""
    from . import tables as _tables
    positional, opts = _split_args(parsed.args[1:])
    name = positional[0] if positional else ""
    if not name:
        print("Usage: table census <table> [--top N]", file=sys.stderr)
        print("(`revenant table list` names them)", file=sys.stderr)
        return 1
    try:
        top = int(opts.get("top", _tables.CENSUS_TOP))
    except ValueError:
        print("--top takes a number", file=sys.stderr)
        return 1
    if top < 0:
        print("--top takes a count of 0 or more", file=sys.stderr)
        return 1
    try:
        # `read_any`, so a path into another project is read with that project's
        # keys rather than this one's.
        data = _tables.read_any(name)
    except _tables.TableError as exc:
        print(f"{exc}", file=sys.stderr)
        return 1
    table = data.table
    # An error with rows behind it is a warning about them, not a refusal: a
    # Luban table whose schema is short still has rows worth looking at, and
    # hiding them would hide the evidence that the schema is short.
    if data.error:
        print(f"{table.name}: {data.error}", file=sys.stderr)
        return 1

    stats = _tables.census(data.rows, top=top)
    print(f"{table.name} -- {len(data.rows)} "
          f"{_tables.plural(len(data.rows), 'row')}, "
          f"{len(stats)} {_tables.plural(len(stats), 'field')}"
          f"  ({data.reader}, {table.corpus})")
    if data.partial:
        print(f"WARNING: {data.partial}", file=sys.stderr)
    if not stats:
        print("\nNo fields to count: " + ("the table is empty."
              if not data.rows else "its rows are values, not objects."))
        return 0
    width = _name_column([s.name for s in stats], "FIELD")
    print()
    print(f"{'FIELD':<{width}}  {'FILLED':>13}  {'DISTINCT':>8}  TOP VALUES")
    for stat in stats:
        print(f"{stat.name:<{width}}  {stat.filled:>13}  "
              f"{stat.distinct:>8}  {stat.values}")
        if stat.null:
            print(f"{'':<{width}}  {'':>13}  {'':>8}  "
                  f"({stat.null} of those are null)")
    return 0


def _name_column(names: list, header: str) -> int:
    """Wide enough for the longest name, and never narrower than it.

    Shared by the two table listings, which both print a name that has to be
    passable back in: a name clipped to fit a column is a name that resolves to
    nothing.
    """
    return max([len(n) for n in names] + [len(header)])


def cmd_table(parsed: argparse.Namespace) -> int:
    """Config tables: `list` what this project has, `census <table>` what is in a field, `diff <A> <B>` what two disagree about, `refs <table>` how often it is named."""
    from . import tables as _tables
    action = _arg(parsed, 0) or "list"
    if action == "census":
        return _table_census(parsed)
    if action == "diff":
        return _table_diff(parsed)
    if action == "refs":
        return _table_refs(parsed)
    if action != "list":
        print(f"table: unknown action {action!r}. "
              f"Actions: list, census, diff, refs", file=sys.stderr)
        return 2

    readers = _tables.readers_for()
    found = _tables.discover(claimed=_tables.claimed_names())
    for line in found.missing:
        print(line)
    if not found.corpora:
        looked = ", ".join(f"{r}/" for r in _tables.CORPUS_ROOTS)
        print(f"No config tables found under {looked} "
              f"({_tables.MAX_DEPTH} levels deep).")
        print("Set [tables] dirs in revenant.toml if this project keeps them elsewhere.")
        for line in found.gaps:
            print(line)
        return 0

    entries = [(t, _tables.read(t, readers))
               for corpus in found.corpora for t in corpus.tables]
    width = _name_column([t.name for t, _ in entries], "TABLE")
    print(f"{'TABLE':<{width}}  {'ROWS':>7}  {'FIELDS':>6}  {'READER':<14}  CORPUS")
    unreadable = []
    for table, data in entries:
        # A shape with no reader gets dashes, not zeroes. Printing 0 rows for a
        # table nobody has decoded is the one wrong answer this command can give
        # (#59): it reads as "this table is empty", which is a finding.
        count = str(len(data.rows)) if data.reader else "-"
        cols = str(len(data.fields)) if data.reader else "-"
        print(f"{table.name:<{width}}  {count:>7}  {cols:>6}  "
              f"{data.label:<14}  {table.corpus}")
        # A shape whose whole story is "nothing reads this yet" already said so
        # in the reader column; repeating it once per file would bury the
        # errors that are actually about this file. Binary is no longer such a
        # shape -- two readers cover it -- so a blob that failed to decode says
        # why instead of hiding behind its label.
        for line in (data.error, data.partial):
            # The Lua count caveat is carried on every Lua read so that
            # `census` and `rows()` see it; here it is the same sentence about
            # every file in the corpus, so it is printed once at the bottom
            # instead of once per file.
            if line and line != _tables.LUA_VARIANT_CAVEAT:
                unreadable.append(
                    f"{os.path.join(table.corpus, os.path.basename(table.path))}: {line}")

    how = ("[tables] dirs in revenant.toml"
           if found.corpora[0].source == _tables.SOURCE_CONFIGURED
           else "the sweep of " + ", ".join(f"{r}/" for r in _tables.CORPUS_ROOTS))
    read_count = sum(1 for _t, data in entries if data.reader)
    tail = f"; {read_count} read as {_tables.plural(read_count, 'a table', 'tables')}"
    print(f"\n{_tables.tally(found)}, from {how}{tail}.")
    for line in unreadable:
        print(f"  not read  {line}")
    for line in found.gaps:
        print(f"  not seen  {line}")
    for line in readers.notes:
        print(f"  config    {line}")
    # Said once, when there is a Lua corpus to say it about: rows there are a
    # count of files, and a title shipping variants of one table as several
    # files loads only some of them.
    if any(t.shape == _tables.SHAPE_LUA and data.reader for t, data in entries):
        print(f"  counted   {_tables.LUA_VARIANT_CAVEAT}")
    blobs = sum(1 for t, data in entries
                if t.shape == _tables.SHAPE_BINARY and not data.reader)
    if blobs and readers.luban_schema is None and not readers.fb_roots:
        print(f"  hint      {blobs} binary {_tables.plural(blobs, 'table')} went unread; "
              f"say what they are in revenant.toml -- [tables] luban_schema for "
              f"Luban (`revenant luban-read` shows the shape), or fb_schema plus "
              f"fb_roots for a FlatBuffers CMS library")
    return 0


def cmd_lua_extract(parsed: argparse.Namespace) -> int:
    """Decrypt, unpack and decompile the game's xLua scripts into lua/<version>/."""
    from .lua import extract_to_tree, have_decompiler
    keep_bc = "--keep-bytecode" in parsed.args
    if not have_decompiler():
        print("Note: unluac.jar/JRE not available; writing string-constant fallback.",
              file=sys.stderr)
    rep = extract_to_tree(parsed.version, keep_bytecode=keep_bc, verbose=parsed.verbose)
    print(f"Lua: {rep.total} scripts -> {rep.out_dir}")
    print(f"  decompiled: {rep.decompiled}   bytecode/strings only: {rep.bytecode_only}")
    return 0


def cmd_lua_list(parsed: argparse.Namespace) -> int:
    """List extracted Lua script module names."""
    from .lua import list_scripts
    query = " ".join(parsed.args) if parsed.args else ""
    names = list_scripts(parsed.version, query, limit=10000)
    if not names:
        print("No extracted Lua. Run: revenant lua-extract", file=sys.stderr)
        return 1
    for n in names:
        print(n)
    print(f"\n{len(names)} script(s).", file=sys.stderr)
    return 0


def cmd_lua_get(parsed: argparse.Namespace) -> int:
    """Print one extracted Lua script's source."""
    from .lua import get_source
    name = _arg(parsed, 0)
    if not name:
        print("Usage: lua-get <Module.Name>", file=sys.stderr)
        return 1
    src = get_source(name, parsed.version)
    if src is None:
        print(f"Not found: {name}. Try lua-list to see available modules.", file=sys.stderr)
        return 1
    print(src)
    return 0


def cmd_lua_grep(parsed: argparse.Namespace) -> int:
    """Regex-search the decompiled Lua tree (module:line: text)."""
    from .lua import lua_grep
    pattern = " ".join(parsed.args) if parsed.args else ""
    if not pattern:
        print("Usage: lua-grep <regex>", file=sys.stderr)
        return 1
    print(lua_grep(pattern, parsed.version, limit=200))
    return 0


def cmd_lua_refs(parsed: argparse.Namespace) -> int:
    """Lua cross-references for a module or function name."""
    from .lua import lua_refs
    name = _arg(parsed, 0)
    if not name:
        print("Usage: lua-refs <Module.Name | functionName>", file=sys.stderr)
        return 1
    print(lua_refs(name, parsed.version))
    return 0


def cmd_lua_decompile(parsed: argparse.Namespace) -> int:
    """Decompile a directory of Lua already on disk (`lua-decompile <dir> [--out DIR]`)."""
    from . import lua as _lua
    positional, opts = _split_args(parsed.args, boolean=("keep-bytecode",))
    src = positional[0] if positional else ""
    if not src:
        print("Usage: lua-decompile <directory> [--out DIR] [--keep-bytecode]",
              file=sys.stderr)
        print("(the package path is `revenant lua-extract`; this is for Lua "
              "already on disk)", file=sys.stderr)
        return 1
    try:
        rep = _lua.decompile_tree(src, out_dir=opts.get("out") or "",
                                  version=parsed.version,
                                  keep_bytecode="keep-bytecode" in opts)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"{rep.decompiled}/{rep.chunks} chunk(s) decompiled into {rep.out_dir}")
    # Counted, never hidden: "this directory holds no Lua" and "I only looked
    # at some of it" have to be different answers. `unreadable` is kept apart
    # from `other` because it is our gap rather than the file's content.
    if rep.bytecode_only:
        print(f"  {rep.bytecode_only} kept as embedded strings only")
    if rep.source_copied:
        print(f"  {rep.source_copied} file(s) were already Lua source, copied through")
    if rep.other:
        print(f"  {rep.other} file(s) were neither Lua bytecode nor .lua source")
    if rep.unreadable:
        print(f"  {rep.unreadable} file(s) could not be read")
    for clash in rep.collisions[:5]:
        print(f"  not written: {clash}")
    if len(rep.collisions) > 5:
        print(f"  ... {len(rep.collisions) - 5} more collision(s)")
    for why in rep.why[:5]:
        print(f"  why: {why}")
    if len(rep.why) > 5:
        print(f"  ... {len(rep.why) - 5} more distinct reason(s)")
    # Anything usable landing in the tree is a success. A directory of nothing
    # but plain source is a legitimate run, and exiting 1 on it called our own
    # bucketing the caller's failure.
    return 0 if (rep.chunks or rep.source_copied) else 1


def cmd_lua_bridge(parsed: argparse.Namespace) -> int:
    """The C#<->Lua bridge: resolve CS.* types, list exposed types."""
    from .bridge import lua_bridge
    query = " ".join(parsed.args) if parsed.args else ""
    print(lua_bridge(query, parsed.version))
    return 0


# ── the managed source tree: the C# side of the `lua-*` group (#48) ─────────
#
# Two roots, `src/<version>/` (the scaffold) and `src-hotupdate/<version>/`
# (source recovered from the hot-update assemblies), the second replaceable via
# `[csharp] roots`. Every line of output names which root, because a stub and a
# shipped body answer different questions.
#
# The wording lives in `csharp`, not here: the MCP tools print the same answers,
# and the one phrase each surface spelled for itself is the one that diverged.
#
# `--root` is not a source-root selector: it is a global flag
# `normalize_global_args` hoists out of the subcommand's arguments wherever it
# appears, and for every other command it means the RE artefacts root. These
# read the project resolved from the cwd, the same as `lua-*` and `table`.

def _cs_which(opts: dict):
    """`--from scaffold|hotupdate`, "" for both, or None once rejected."""
    from . import csharp
    which = str(opts.get("from", "") or "")
    complaint = csharp.check_source(which)
    if complaint:
        print(f"--from: {complaint}", file=sys.stderr)
        return None
    return which


def _cs_has_source(parsed: argparse.Namespace) -> bool:
    """Whether there is a tree at all -- and say what to run when there is not.

    All four commands fail on this rather than answering, because an empty
    answer to "search the C# " reads as "this game has no C#" when what
    happened is that `seed-src` never ran.
    """
    from . import csharp
    if csharp.source_roots(parsed.version):
        return True
    print(csharp.NO_SOURCE, file=sys.stderr)
    return False


def cmd_cs_list(parsed: argparse.Namespace) -> int:
    """List C# source files across the scaffold and the recovered hot-update source."""
    from . import csharp
    positional, opts = _split_args(parsed.args)
    query = " ".join(positional)
    which = _cs_which(opts)
    if which is None or not _cs_has_source(parsed):
        return 1
    limit = _limit_arg(opts, default=0)
    if limit is None:
        return 1
    found = csharp.list_sources(parsed.version, query, which=which)
    print(csharp.list_report(found, query, limit), file=sys.stdout if found
          else sys.stderr)
    return 0 if found else 1


def cmd_cs_get(parsed: argparse.Namespace) -> int:
    """Print one C# source file (`cs-get <Type | path> [--from scaffold|hotupdate]`)."""
    from . import csharp
    positional, opts = _split_args(parsed.args)
    name = positional[0] if positional else ""
    if not name:
        print("Usage: cs-get <TypeName | path> [--from scaffold|hotupdate]",
              file=sys.stderr)
        return 1
    which = _cs_which(opts)
    if which is None or not _cs_has_source(parsed):
        return 1
    hits = csharp.find_source(name, parsed.version, which=which)
    report = csharp.source_report(name, hits)
    print(report, file=sys.stdout if len(hits) == 1 else sys.stderr)
    return 0 if len(hits) == 1 else 1


def cmd_cs_grep(parsed: argparse.Namespace) -> int:
    """Regex-search the C# source roots (root/name:line: text)."""
    from . import csharp
    positional, opts = _split_args(parsed.args)
    pattern = " ".join(positional)
    if not pattern:
        print("Usage: cs-grep <regex> [--limit N] [--from scaffold|hotupdate]",
              file=sys.stderr)
        return 1
    limit, which = _limit_arg(opts, default=200), _cs_which(opts)
    if limit is None or which is None or not _cs_has_source(parsed):
        return 1
    print(csharp.cs_grep(pattern, parsed.version, limit, which=which))
    return 0


def cmd_cs_refs(parsed: argparse.Namespace) -> int:
    """Where a C# name is declared and where it is mentioned, per source root."""
    from . import csharp
    positional, opts = _split_args(parsed.args)
    symbol = positional[0] if positional else ""
    if not symbol:
        print("Usage: cs-refs <TypeName | MemberName> [--limit N] "
              "[--from scaffold|hotupdate]", file=sys.stderr)
        return 1
    limit, which = _limit_arg(opts, default=200), _cs_which(opts)
    if limit is None or which is None or not _cs_has_source(parsed):
        return 1
    print(csharp.cs_refs(symbol, parsed.version, limit, which=which))
    return 0


def cmd_field_scan(parsed: argparse.Namespace) -> int:
    """Scan IsilDump for accesses to a field offset."""
    offset = _arg(parsed, 0)
    if not offset:
        print("Usage: field-scan <offset> [limit] [path_filter]", file=sys.stderr)
        return 1
    limit = int(_arg(parsed, 1, "50"))
    filter_str = _arg(parsed, 2, "")
    try:
        root = ""
        if parsed.root:
            root = os.path.join(parsed.root, "IsilDump", "Assembly-CSharp")
        elif VERSIONS:
            from .indices import resolve_version
            vd = resolve_version(parsed.version)
            root = os.path.join(vd.root, "IsilDump", "Assembly-CSharp")
        if not root or not os.path.isdir(root):
            print("IsilDump root not found. Specify --root.", file=sys.stderr)
            return 1
        print(scan_field_accesses(root, int(offset, 0), limit, filter_str))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_metadata_info(parsed: argparse.Namespace) -> int:
    """Header facts of global-metadata.dat."""
    try:
        loc = find_global_metadata(parsed.root)
        meta = Il2CppMetadata(loc.path)
        print(f"Metadata: {loc.source}")
        print(f"  sanity: 0x{meta.sanity:08X}")
        print(f"  version: {meta.version}")
        print(f"  string literals: {meta.string_literal_count}")
        print(f"  string data size: {meta.string_literal_data_count}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


_TIER_HEADINGS = {
    TIER_CORE: "Core:",
    TIER_QUERY: "Query (agents reach these through the `re` MCP tools; the CLI form is for people and scripts):",
    TIER_EXTENSION: "Extension (breadth scan; visible because [packs] is enabled):",
}


def cmd_help(parsed: argparse.Namespace) -> int:
    """List the commands. `--all` adds the query tier."""
    from .describe import _summary as _summary_of
    show_all = "--all" in parsed.args
    table = command_table()
    names = visible_commands(show_all=show_all)
    print("revenant <command> [args]")
    for tier in (TIER_CORE, TIER_QUERY, TIER_EXTENSION):
        group = [n for n in names if command_tier(n) == tier]
        if not group:
            continue
        print()
        print(_TIER_HEADINGS[tier])
        for name in group:
            print(f"  {name:18s} {_summary_of(table[name])}")
    if not show_all:
        print()
        print("`revenant help --all` also lists the query tier "
              "(disasm, evidence, search, xrefs, lua-grep, ...).")
    return 0


# ── L2 methodology: packs, probes, the ledger, and note lint ────────────────

def _project_packs():
    from . import config, pack
    return pack.discover(config.workspace_root(), pack.enabled_packs(config.project_config()))


def _corpora(version: str):
    """Corpora probes run against, for this project's technology stack."""
    from . import probes
    out = [probes.il2cpp_corpus(version)]
    lua = probes.lua_corpus(version)
    if not lua.is_empty():
        out.append(lua)
    return [c for c in out if not c.is_empty()] or out[:1]


def cmd_packs(parsed: argparse.Namespace) -> int:
    """List the domain packs resolved for this project."""
    from .methodology import FACET_TITLES
    packs = _project_packs()
    if not packs:
        print("No domain packs enabled.")
        print("Built-in packs are resolved at run time, never copied into the project.")
        print('Enable them in revenant.toml:  [packs]\\n  enabled = ["example"]')
        return 0
    want = _arg(parsed, 0)
    for name, pk in sorted(packs.items()):
        if want and name != want:
            continue
        print(f"{name} v{pk.version}  ({len(pk.slots)} slots, {len(pk.cells())} cells)")
        if pk.description:
            print(f"  {pk.description}")
        for slot_id in sorted(pk.slots):
            slot = pk.slots[slot_id]
            trimmed = [f for f in FACET_TITLES if not slot.spec(f).applicable]
            note = f"  (trimmed: {', '.join(FACET_TITLES[f] for f in trimmed)})" if trimmed else ""
            print(f"  {slot_id}  {slot.title}   {len(slot.probes)} probes{note}")
        for edge in pk.edges:
            print(f"  edge  {edge.src} -> {edge.dst}  [{edge.kind}]")
    return 0


def cmd_probe(parsed: argparse.Namespace) -> int:
    """Run a pack's probes and record the facts. Writes no judgements."""
    from . import config, ledger as _ledger, probes
    pack_name = _arg(parsed, 0)
    only_slot = _arg(parsed, 1)
    packs = _project_packs()
    if pack_name not in packs:
        print(f"No such pack: {pack_name or '(none given)'}. Have: {', '.join(sorted(packs)) or 'none'}")
        return 2
    pk = packs[pack_name]

    root = config.workspace_root()
    path = _ledger.ledger_path(root, pack_name)
    led = _ledger.Ledger.load(path, pack_name)
    led.pack_version = pk.version
    index_version = f"{parsed.version}@{config.detect_platform()}"

    corpora = _corpora(parsed.version)
    slots = [pk.slot(only_slot)] if only_slot else [pk.slots[s] for s in sorted(pk.slots)]
    zero_hits = 0
    for slot in slots:
        report = probes.run_slot(slot.id, slot.probes, corpora)
        for run in report.runs:
            led.record_probe_run(run)
        zero_hits += len(report.zero_hit_runs)
        for cell in slot.cells():
            led.mark_ran(cell, slot.probe_set_hash(), index_version)
        print(f"{slot.id}  {len(report.runs)} probe runs, "
              f"{len(report.zero_hit_runs)} zero-hit, "
              f"{len(report.candidates())} candidates")
    led.save()
    print(f"\nledger: {path}")
    print(f"zero-hit runs recorded: {zero_hits}  "
          f"(a zero hit is a result -- it is what separates 'checked, absent' "
          f"from 'nobody looked')")
    return 0


def cmd_cell(parsed: argparse.Namespace) -> int:
    """Write a judgement for one cell. The only door judgements come through."""
    from . import config, ledger as _ledger
    from .methodology import CellId
    raw = _arg(parsed, 0)
    if not raw:
        print("usage: revenant cell <pack>/<slot>#<facet> --state <state> [--tier <tier>] ...")
        return 2
    try:
        cid = CellId.parse(raw)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2

    opts = _flag_options(parsed.args[1:])
    state = opts.get("state", "")
    if not state:
        from .methodology import STATE_TITLES
        print("--state is required. One of:")
        for key, title in STATE_TITLES.items():
            print(f"  {key:24s} {title}")
        return 2

    packs = _project_packs()
    ceiling = ""
    if cid.pack in packs and cid.slot in packs[cid.pack].slots:
        ceiling = packs[cid.pack].slot(cid.slot).spec(cid.facet).ceiling

    root = config.workspace_root()
    path = _ledger.ledger_path(root, cid.pack)
    led = _ledger.Ledger.load(path, cid.pack)
    try:
        warnings = led.set_judgement(
            cid,
            state=state,
            tier=opts.get("tier", ""),
            gap_markers=[m for m in opts.get("gap", "").split(",") if m],
            reach_source=opts.get("reach", ""),
            notes_ref=opts.get("note", ""),
            summary=opts.get("summary", ""),
            ceiling=ceiling,
        )
    except _ledger.LedgerError as exc:
        print(f"Rejected: {exc}")
        return 2
    led.save()
    print(f"{cid}: {state}" + (f" [{opts['tier']}]" if opts.get("tier") else ""))
    for warning in warnings:
        print(f"  warning: {warning}")
    return 0


def cmd_ledger(parsed: argparse.Namespace) -> int:
    """Coverage for each pack. Never merged into one number."""
    from . import config, ledger as _ledger
    root = config.workspace_root()
    directory = _ledger.ledger_dir(root)
    if not os.path.isdir(directory):
        print("No ledger yet. Run `revenant probe <pack>` first.")
        return 0
    from .methodology import STATE_TITLES
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        led = _ledger.Ledger.load(os.path.join(directory, name))
        cov = led.coverage()
        # Per-pack, deliberately not summed: "growth 78%, core gameplay 12%"
        # says something; weighting them into 45% says nothing.
        print(f"{cov['pack']}: {cov['ran']}/{cov['cells']} cells run, "
              f"{cov['probe_runs']} probe runs ({cov['zero_hit_runs']} zero-hit), "
              f"{cov['dead_ends']} dead ends")
        for state, count in sorted(cov["by_state"].items()):
            print(f"    {STATE_TITLES.get(state, state):24s} {count}")
    return 0


def cmd_lint(parsed: argparse.Namespace) -> int:
    """Check notes for the three objectively checkable things (--repo: every project in the repository; --json: machine-readable)."""
    from . import config, lint as _lint
    root = config.workspace_root()
    paths = [a for a in parsed.args if not a.startswith("-")]

    # `--repo` sweeps the repository rather than this one project, which is what
    # a coverage matrix over several projects needs; without it the caller had to
    # run `lint` once per project and stitch the output back together (#53).
    as_json = "--json" in parsed.args
    repo = "--repo" in parsed.args
    if repo and paths:
        # Named paths win -- `--repo` is about *finding* notes, and you already
        # said which. Said out loud: a flag that does nothing without a word is
        # indistinguishable from one that did not work.
        print("lint: paths were given, so --repo (find every project in the "
              "repository) is ignored.", file=sys.stderr)
    if repo and not paths:
        found = _lint.repo_projects(root)
        # The root's own `notes/` count as something to sweep even when nothing
        # under here is a project (#67), so the empty-handed message waits for
        # both to come back empty.
        if not found and not _lint.repo_root_notes(root):
            print(f"lint: no project (a directory with {config.PROJECT_MARKER}) at or "
                  f"one level under {_lint.repo_root_display(root)}, and no notes/ "
                  f"in the root itself.", file=sys.stderr)
        report = _lint.lint_repo(root, parsed.version)
    else:
        paths = paths or _lint.collect_notes(root)
        if not paths and not as_json:
            # Not said to a consumer: it parses stdout unconditionally, and a
            # sentence where a document belongs is a broken contract, not an
            # edge case. An empty report says the same thing in its own terms.
            print("No notes found under notes/.")
            return 0
        report = _lint.lint_notes(paths, parsed.version) if paths else _lint.LintReport()

    if as_json:
        print(json.dumps(_lint.as_json(report), indent=1, ensure_ascii=False))
        return 0
    print(_lint.format_report(report))
    # Reports, never blocks: reversing routinely cannot reach complete evidence,
    # and the previous hard gate in this codebase was never once satisfied.
    return 0


def _flag_options(args: list[str]) -> dict:
    """Parse `--key value` / `--key=value` pairs out of the remainder."""
    return _split_args(args)[1]


def _split_args(args: list[str], boolean: tuple = ()) -> tuple[list[str], dict]:
    """Positionals and options, with named boolean flags not eating the next word.

    `_flag_options` alone cannot tell `--types MetaScenes` (a flag and a group)
    from `--out dir` (a flag and its value), so a command that has both kinds
    says which of its flags are switches.
    """
    positional: list[str] = []
    opts: dict = {}
    index = 0
    while index < len(args):
        arg = args[index]
        if not arg.startswith("--"):
            positional.append(arg)
            index += 1
            continue
        if "=" in arg:
            key, value = arg[2:].split("=", 1)
            opts[key] = value
            index += 1
            continue
        key = arg[2:]
        if key in boolean:
            opts[key] = "1"
            index += 1
            continue
        value = args[index + 1] if index + 1 < len(args) and not args[index + 1].startswith("--") else ""
        opts[key] = value
        index += 2 if value else 1
    return positional, opts


# ── cold start, breadth scan (frozen extension), deep dives ────────────────

def _fingerprint_for_project(parsed):
    from . import config, fingerprint as _fingerprint
    path = config.package_path()
    if not path:
        return None
    fp = _fingerprint.collect(path)
    fp.platform = config.detect_platform()
    return fp


def cmd_fingerprint(parsed: argparse.Namespace) -> int:
    """Cold start, step one: package-level observations, before Cpp2IL.

    Lists what was looked for and what was found -- markers, declared versus
    present assemblies, `.bytes` literals, build paths, native exports. It does
    not decide the stack or the origin; read the list and decide. `--json` for
    the same as data.
    """
    from . import config, fingerprint as _fingerprint, ledger as _ledger
    fp = _fingerprint_for_project(parsed)
    if fp is None:
        print("No game package in this project.")
        return 2
    if "--json" in parsed.args:
        print(json.dumps(fp.to_json(), indent=2, ensure_ascii=False))
    else:
        print(_fingerprint.format_text(fp))

    root = config.workspace_root()
    # Park the observations on the pack ledgers so a later scan can read them --
    # only when a pack is enabled. Ledgers are the frozen scan family's
    # (ADR-0002); a core command must not create `.revenant/scan/` in a
    # project that never asked for it.
    from . import pack as _pack
    if _pack.enabled_packs(config.project_config()):
        for name in _project_packs() or []:
            led = _ledger.Ledger.load(_ledger.ledger_path(root, name), name)
            led.package["fingerprint"] = fp.to_json()
            led.save()
    return 0


def cmd_naming_stats(parsed: argparse.Namespace) -> int:
    """This game's own naming, for the zero-hit review."""
    from . import probes as _probes
    corpus = _probes.il2cpp_corpus(parsed.version)
    if corpus.is_empty():
        print("No index loaded.")
        return 2
    for token, count in _probes.naming_statistics(corpus):
        print(f"  {count:6d}  {token}")
    return 0


def cmd_scan(parsed: argparse.Namespace) -> int:
    """Run the breadth scan for a pack. Deterministic; calls no model."""
    from . import config, ledger as _ledger, scan as _scan
    pack_name = _arg(parsed, 0)
    packs = _project_packs()
    if pack_name not in packs:
        print(f"No such pack: {pack_name or '(none given)'}. "
              f"Have: {', '.join(sorted(packs)) or 'none'}")
        return 2
    pk = packs[pack_name]
    fp = _fingerprint_for_project(parsed)
    if fp is None:
        print("No game package in this project.")
        return 2

    root = config.workspace_root()
    led = _ledger.Ledger.load(_ledger.ledger_path(root, pack_name), pack_name)
    result = _scan.run(
        pk, fp, led, parsed.version,
        index_version=f"{parsed.version}@{config.detect_platform()}",
        brief_dir=os.path.join(root, ".revenant", "briefs"),
    )
    led.save()
    print(result.as_text())
    return 0


def cmd_dig(parsed: argparse.Namespace) -> int:
    """Deep dives: `open` a question with its criteria, `converge` to close it."""
    from . import config, dig as _dig
    action = _arg(parsed, 0) or "list"
    root = config.workspace_root()
    path = _dig.tasks_path(root)
    tasks = _dig.load_tasks(path)
    opts = _flag_options(parsed.args[1:])

    if action == "open":
        question = opts.get("question", "")
        criteria = [c for c in opts.get("criteria", "").split(";") if c.strip()]
        try:
            task = _dig.open_task(
                question, criteria,
                entry_hints=[h for h in opts.get("entry", "").split(",") if h],
                origin_cell=opts.get("cell", ""),
            )
        except _dig.DigError as exc:
            print(f"Rejected: {exc}")
            return 2
        tasks.append(task)
        _dig.save_tasks(path, tasks)
        print(f"{task.id}  {task.question}")
        for index, criterion in enumerate(task.criteria):
            print(f"  [{index}] {criterion.text}")
        return 0

    if action == "converge":
        task_id = _arg(parsed, 1)
        match = next((t for t in tasks if t.id == task_id), None)
        if match is None:
            print(f"No dig {task_id!r}. Open ones: {', '.join(t.id for t in tasks) or 'none'}")
            return 2
        met_raw = opts.get("met", "")
        try:
            met = (list(range(len(match.criteria))) if met_raw == "all"
                   else [int(x) for x in met_raw.split(",") if x.strip()])
        except ValueError:
            print("--met takes criterion indexes (0,2) or `all`")
            return 2
        dead_ends = _dead_ends_arg(opts.get("dead-end", ""))
        retrieved = [c.strip() for c in opts.get("retrieved", "").split(",") if c.strip()]
        used = [c.strip() for c in opts.get("used", "").split(",") if c.strip()]
        led = _dig.ledger_for_cell(root, match.origin_cell)
        try:
            _dig.converge(match, led, dead_ends=dead_ends, retrieved_candidates=retrieved,
                          met=met, used=used, note_ref=opts.get("note", ""))
        except _dig.DigError as exc:
            print(f"Rejected: {exc}")
            return 2
        if led is not None:
            led.save()
        _dig.save_tasks(path, tasks)
        print(f"{match.id}  {match.status}  "
              f"{sum(1 for c in match.criteria if c.met)}/{len(match.criteria)} criteria")
        for criterion in match.criteria:
            print(f"  [{'x' if criterion.met else ' '}] {criterion.text}")
        for entry in match.dead_ends:
            print(f"  dead end  {entry['candidate']}: {entry.get('reason', '')}")
        for candidate in used:
            print(f"  used      {candidate}")
        if match.note_ref:
            print(f"  note      {match.note_ref}")
        return 0

    if action in ("tick", "round", "queue"):
        print(f"dig {action}: removed (ADR-0002). A dig has two moves: `open` and "
              f"`converge`; the per-round loop these served was never built.")
        return 2

    if action != "list":
        print(f"dig: unknown action {action!r}. Actions: open, converge, list")
        return 2
    for task in tasks:
        met = sum(1 for c in task.criteria if c.met)
        print(f"  {task.id}  {task.status:11s} {met}/{len(task.criteria)}  {task.question[:60]}")
    return 0


def _dead_ends_arg(raw: str) -> list:
    """`--dead-end "Cand: why; Other: why"` -> [{candidate, reason}, ...]."""
    out = []
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        candidate, _sep, reason = item.partition(":")
        out.append({"candidate": candidate.strip(), "reason": reason.strip()})
    return out


def cmd_describe(parsed: argparse.Namespace) -> int:
    """Print what this build can do (JSON; --all adds the query tier), or render the agent files (--render claude|codex; --here writes this project rather than the layer that shares it)."""
    from . import config, describe as _describe
    opts = _flag_options(parsed.args)
    desc = _describe.describe(show_all="--all" in parsed.args)

    target = opts.get("render", "")
    if not target:
        print(_describe.as_json(desc))
        return 0
    if target not in _describe.RENDERERS:
        print(f"Unknown render target {target!r}. Available: {', '.join(sorted(_describe.RENDERERS))}")
        print("A harness is a documented decision (ADR-0001 and its 2026-08-19 "
              "revision), not a flag: it needs a renderer, and both of the "
              "harnesses that have one are listed above.")
        return 2

    root = config.workspace_root()
    # Where the files go: the layer that already carries them, which in a
    # repository holding several projects is one copy above them all. Writing a
    # second copy here is what `status` used to send people to do, and it undid
    # the sharing (#51). `--here` forces this project -- the deliberate way to
    # take one project out of the shared set. Asked per harness, because each
    # one searches for its own files and a repository may share one and not the
    # other.
    dest = root
    if "--here" not in parsed.args:
        dest = _describe.harness_root(root, target)
    # `--if-stale` re-renders only when the rendered files have fallen behind
    # the installed build -- the upgrade-then-re-render loop every project ran
    # by hand (#32), safe to run unconditionally.
    #
    # "Installed" is asked first, and separately. `harness_drift_lines` answers
    # [] both for "current" and for "this harness is not here", and a project
    # that has never had Codex is the second: reading that as "current" is how
    # `--render codex --if-stale` would report success while installing nothing.
    installed = _describe.harness_installed(root, target)
    if "--if-stale" in parsed.args and installed and not harness_drift_lines(
            root, harness_dir=dest, harness=target):
        print("agent skill is current; nothing to re-render.")
        return 0
    for path in _describe.write_rendered(dest, target, desc):
        print(f"rendered {path}  (revenant {desc.version})")
    if os.path.abspath(dest) != os.path.abspath(root):
        print(f"written to {harness_location(root, target)} -- `--here` writes this project its own copy")
    # The overlay is this title's own and is never shared: holding "true here,
    # wrong for the next game" is the whole of what it is for.
    overlay = os.path.join(root, *_describe.overlay_of(target).split("/"))
    if _describe.overlay_of(target) and os.path.exists(overlay):
        print(f"project overlay left untouched: {overlay}")
    if target == _describe.CodexRenderer.name:
        for line in codex_setup_notes(root):
            print(line)
    return 0


def codex_setup_notes(root: str) -> list[str]:
    """What Codex needs a person to do, and what it will not do the same way.

    Two costs of the second harness are taken deliberately and neither is
    visible from the rendered files alone, so they are said here: the MCP entry
    does nothing until the repository is trusted, and the six commands are
    chosen by the model rather than started by a person.
    """
    from . import describe as _describe
    return [
        "",
        f"Codex reads {_describe.CodexRenderer.MCP} only once you have trusted this "
        f"repository. That is your call, so revenant leaves it to you:",
        f"    codex mcp add re -- {sys.executable} -m revenant.mcp_server",
        "  or add to $CODEX_HOME/config.toml (default ~/.codex/config.toml):",
        f'    [projects.{_toml_key(_codex_trust_path(root))}]',
        '    trust_level = "trusted"',
        "",
        "The six commands are skills here, not slash commands: Codex picks one "
        "from its description, so asking for it is a request rather than a "
        "guarantee. `revenant status` reports both of these.",
    ]


def harness_drift_lines(root: str, harness_dir: str | None = None,
                        harness: str = "claude") -> list[str]:
    """One message per kind of drift in one harness's generated files, or [].

    Decided by **content**, not by a version number: this package's version has
    never been bumped, so a version-equality check reported nothing while the
    rendered skill changed by 59 lines (#37). Every file the renderer for
    `harness` writes is re-rendered here and compared with what is on disk.

    Which harness is asked about is decided by what is on disk, never by a
    setting: a project that has no `.codex/` is not asked about Codex and hears
    nothing about it (ADR-0001's revision).

    The five outcomes are reported apart because the remedy differs -- one of
    them loses work if you re-render without reading it first, and one of them
    is made worse by the re-render the others ask for.

    Read from `harness_dir` -- by default the layer that carries the generated
    files, which may be an ancestor shared with the projects beside this one
    (#51). What is *expected* there is still rendered for this project, so a
    shared copy that does not match what this project renders is drift; which
    of the two projects is right is not a question this can answer, so it says
    what it sees and offers the copy-of-its-own way out.
    """
    from . import describe as _describe
    where = harness_dir or _describe.harness_root(root, harness)
    shared = os.path.abspath(where) != os.path.abspath(root)
    if not os.path.exists(os.path.join(where, _describe.dir_of(harness))):
        return []
    old = os.environ.get("REVENANT_PROJECT")
    os.environ["REVENANT_PROJECT"] = root
    try:
        expected = _describe.render(_describe.describe(), harness)
    except Exception as exc:
        # Reported, never swallowed: a renderer that raises (a template naming
        # an unknown tier, say) is exactly what the guards exist to catch, and
        # answering "current" to a check that never ran is the blindness #37
        # is about.
        return [f"could not re-render to check: {type(exc).__name__}: {exc} -- "
                f"the generated files cannot be verified until this is fixed"]
    finally:
        if old is None:
            os.environ.pop("REVENANT_PROJECT", None)
        else:
            os.environ["REVENANT_PROJECT"] = old

    stale, edited, unstamped, missing, mismatched = [], [], [], [], []
    for rel, want in sorted(expected.items()):
        path = os.path.join(where, rel)
        if not os.path.exists(path):
            missing.append(rel)
            continue
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        if text == want:
            continue
        version = _describe.stamped_version(text)
        digest = _describe.stamped_digest(text)
        if not version:
            unstamped.append(rel)
        elif digest and digest != _describe.content_digest(text):
            edited.append(rel)
        elif version != _revenant_version():
            stale.append(f"{rel} ({version})")
        else:
            # Stamped with the version that is installed, and still not what
            # this project renders. Two causes produce exactly this state and
            # nothing on disk tells them apart: an earlier build wrote it and
            # the version never bumped (#37), or a project with a different set
            # of packs rendered it (#51, once one copy is shared). So the line
            # reports what is observed and names both -- the old wording picked
            # the first and asserted it, which read "generated by an earlier
            # build (installed is 0.1.0): ... (0.1.0)".
            mismatched.append(rel)

    fix = f"re-render with `revenant describe --render {harness}`"
    lines = []
    if stale:
        lines.append(
            f"stale, generated by an earlier build (installed is {_revenant_version()}): "
            f"{', '.join(stale)} -- {fix}")
    if mismatched:
        # Which remedy is right depends on the cause, and the cause is not
        # knowable from here. On a copy this project owns, re-rendering is the
        # whole answer either way. On a shared one it is not: if the projects
        # want the same skill, re-render and all of them are fixed at once; if
        # this project's packs differ, re-rendering rewrites the neighbours'
        # file to suit this one and the next `status` next door asks them to
        # rewrite it back. Both are offered, with the condition attached.
        remedy = fix
        if shared:
            remedy = (f"{fix} if the projects beside this one want the same skill; "
                      f"`revenant describe --render {harness} --here` if this project's "
                      f"packs differ and it needs a copy of its own")
        lines.append(
            f"stale against this build: {', '.join(mismatched)} -- stamped with the "
            f"installed version ({_revenant_version()}) yet not what this project "
            f"renders, so either an earlier build wrote it (the version has never "
            f"been bumped, #37) or a project with different packs did (#51) -- {remedy}")
    if edited:
        lines.append(
            f"edited by hand since it was generated: {', '.join(edited)} -- "
            f"re-rendering discards those edits (project conventions belong in "
            f"{_describe.overlay_of(harness)})")
    if unstamped:
        lines.append(f"hand-written (no version stamp): {', '.join(unstamped)} -- {fix}")
    if missing:
        lines.append(f"not rendered: {', '.join(missing)} -- {fix}")
    return lines


def harness_location(project_root: str, harness: str = "claude") -> str:
    """Where one harness's generated files are, or "" when that is this project."""
    from . import describe as _describe
    where = _describe.harness_root(project_root, harness)
    if os.path.abspath(where) == os.path.abspath(project_root):
        return ""
    return shared_label(f"{os.path.relpath(where, project_root)}{os.sep}")


def harness_drift(root: str, harness: str = "claude") -> str:
    """`harness_drift_lines` as one string. "" when every generated file is current."""
    return "; ".join(harness_drift_lines(root, harness=harness))


# ── Codex needs one thing revenant deliberately will not do for you ─────────
#
# `.codex/config.toml` is read only after the repository is listed as trusted in
# the *user's* own `$CODEX_HOME/config.toml`. Trust means "I allow this
# repository to start processes"; a tool granting itself that is pointing the
# wrong way, and revenant's standing promise is that it writes inside the
# project directory and nowhere else. So this reads that file and reports.

def _codex_home() -> str:
    """Where Codex keeps the user's own config. Read from, never written to.

    `$CODEX_HOME` and not just `~/.codex` because that is the variable Codex
    itself honours -- and because it is what made checking this behaviour
    possible at all without touching a real home directory (ADR-0001's revision
    was measured with it pointed at a throwaway).
    """
    return os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")


def _codex_trust_path(root: str) -> str:
    """The directory a person would trust: the repository, not the project.

    Codex keys trust by the directory it was started in, and a repository
    holding nine titles is started at its root as often as inside one of them.
    The outermost bound of the shared-harness walk is the same answer (#51),
    which is why it is taken from there rather than decided again here.
    """
    from . import config
    return config.up_to_repo_root(os.path.abspath(root))[-1]


def _toml_key(path: str) -> str:
    """A path as a TOML quoted key, e.g. `[projects."/home/me/repo"]`.

    `json.dumps` and not an f-string with quotes round it: a TOML basic string
    escapes exactly the way a JSON one does, and a Windows path is full of the
    backslashes that difference would eat.
    """
    return json.dumps(path)


def codex_trust_lines(root: str) -> list[str]:
    """One line when the MCP entry is on disk and Codex will not be reading it.

    A report, not an offer to fix: the remedy is the user's own command, printed
    with the path already filled in. Silent when there is no `.codex/config.toml`
    to be ignored -- a project not on Codex hears nothing about Codex.
    """
    from . import describe as _describe
    where = _describe.harness_root(root, _describe.CodexRenderer.name)
    declared = os.path.join(where, *_describe.CodexRenderer.MCP.split("/"))
    if not os.path.exists(declared):
        return []
    trusted, why = _codex_trusted(root)
    if trusted:
        return []
    # Both ways out, in full. The line to paste is the point: "this repository
    # is not trusted" without it leaves the reader to work out a TOML table name
    # and a quoted absolute path from a sentence.
    return [
        f"MCP declared in {_describe.CodexRenderer.MCP} but {why}, so Codex "
        f"ignores it -- `codex mcp add re -- {sys.executable} -m "
        f"revenant.mcp_server`,",
        f"or put this in {os.path.join(_codex_home(), 'config.toml')} yourself: "
        f"[projects.{_toml_key(_codex_trust_path(root))}] trust_level = \"trusted\"",
    ]


def _codex_trusted(root: str) -> tuple[bool, str]:
    """(is this repository trusted, why not). Never raises: `status` must not die."""
    from . import config
    path = os.path.join(_codex_home(), "config.toml")
    if not os.path.exists(path):
        return False, f"{path} does not exist"
    try:
        import tomllib
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:                       # noqa: BLE001 - status must not die
        return False, f"{path} could not be read ({exc})"
    projects = data.get("projects")
    if not isinstance(projects, dict):
        return False, f"{path} lists no trusted repository"
    for directory in config.up_to_repo_root(os.path.abspath(root)):
        entry = projects.get(directory)
        if isinstance(entry, dict) and entry.get("trust_level") == "trusted":
            return True, ""
    return False, f'{path} has no `trust_level = "trusted"` for it'


def _revenant_version() -> str:
    from . import __version__
    return __version__


# At the very end, and not one line earlier: `command_table()` names every
# handler in this file, so a guard placed mid-module runs `main()` while the
# handlers below it are still unbound. It sat 500 lines up and took `packs`,
# `probe`, `cell`, `ledger`, `lint`, `scan` and `dig` down with it.
if __name__ == "__main__":
    sys.exit(main())
