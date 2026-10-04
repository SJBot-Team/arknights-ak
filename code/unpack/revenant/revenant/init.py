"""`revenant init` -- scaffold a new reverse-engineering project directory.

Creates the working tree (data dirs + config + harness files) that the installed
`revenant` package operates on. The package holds the code; the project holds the
data and config. The MCP server entry -- `.mcp.json` for Claude Code,
`.codex/config.toml` for Codex -- is wired to the exact interpreter running this,
so it works under uv tool / venv / pipx installs alike.

Both harnesses are laid down, without a `--harness` switch. The rendered files
are two text files' worth of bytes and identical in content (only their location
and front-matter differ), while a switch is a thing that has to be remembered
every time and remembered *correctly* -- ADR-0001's revision decided that trade
in the files' favour.
"""
from __future__ import annotations

import importlib.resources as resources
import json
import os
import sys

# Empty data/working dirs (a .gitkeep is dropped so they survive in git).
_DIRS = ["_apks", "_binaries", "_refs", "lua", "src", "decompiled", "notes"]

# template resource -> destination path (relative to the project dir)
_FILES = {
    "revenant.toml": "revenant.toml",
    "gitignore": ".gitignore",
    "CLAUDE.md": "CLAUDE.md",
    "claude/settings.json": ".claude/settings.json",
    # NOT the `re` skill: it is generated from the installed Revenant (see
    # `describe.py`) rather than copied, so upgrading the tool updates every
    # project instead of only the ones created afterwards. Copying is exactly
    # what #6 pointed at when it decided domain packs resolve at run time.
    "claude/skills/re-project/SKILL.md": ".claude/skills/re-project/SKILL.md",
    # NOR the four slash commands: rendered with the skill (`describe.py`),
    # under the same guards and the same version stamp (#30).
}

# Codex's equivalent of the `re-project` overlay: always on, concatenated from
# the git root down, which is why it is also registered for `lint` to size-check.
#
# Written once and never again, `--force` included. `_FILES` above is revenant's
# own scaffolding and a forced re-init is allowed to restore it; this is not
# scaffolding. Users often already have an `AGENTS.md` for their own reasons,
# and "revenant does not touch a word of it" has to hold on the run where they
# typed `--force` for something else.
_NEVER_OVERWRITTEN = {"AGENTS.md": "AGENTS.md"}

# Where the repository says which always-on files are under `lint`'s care
# (ADR-0005). At the *repository* root with repository-relative keys, because
# that is the only place `lint.read_memory_registry` looks: an entry written
# beside the project is one `lint --repo` never reads, which is the unenforced
# budget ADR-0005 exists to end. In the nine-titles-one-repository layout (#51)
# one table at the top holds an entry per title, exactly as the ADR's own
# example does.
_MEMORY_REGISTRY = os.path.join(".claude", "agent-memory", "memory.toml")


def _overlay_entry(target: str, repo: str) -> tuple[str, str]:
    """(repository-relative path of this project's AGENTS.md, its registry line).

    `kind = "overlay"`, not a kind of its own: ADR-0005 already has the word for
    a file that is prose about one title rather than a list of claim-and-pointer
    entries, and it is weighed without its entries being read.
    """
    from .describe import AGENTS_MD_BUDGET, CodexRenderer
    rel = os.path.relpath(os.path.join(target, CodexRenderer.OVERLAY), repo)
    rel = rel.replace(os.sep, "/")
    return rel, f'"{rel}" = {{ kind = "overlay", bytes = {AGENTS_MD_BUDGET} }}'


def _register_overlay(target: str, quiet: bool = False) -> None:
    """Put this project's `AGENTS.md` under `lint`'s budget, or say how to.

    Written for the project that finds no table, never rewritten for the one
    that does: the table is the repository's and holds the projects beside this
    one. But not silently skipped either -- a budget nobody was told to add is
    the same unenforced budget as no budget, so the line to paste is printed.
    """
    from . import config
    from .describe import CODEX_PROJECT_DOC_MAX_BYTES
    repo = config.repo_root_of(target)
    rel, entry = _overlay_entry(target, repo)
    path = os.path.join(repo, _MEMORY_REGISTRY)
    shown = os.path.relpath(path, target)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                already = f'"{rel}"' in f.read()
        except OSError:
            already = False
        if not already and not quiet:
            print(f"  registry exists: {shown} -- add this line under `[files]` to")
            print(f"                   have {rel} weighed by `revenant lint --repo`:")
            print(f"                   {entry}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            f"# What `revenant lint --repo` weighs (ADR-0005). A file not listed\n"
            f"# here is not checked, which is how an archive opts out; there is no\n"
            f"# exemption flag. Keys are relative to this repository root.\n"
            f"#\n"
            f"# `AGENTS.md` is read in full on every Codex turn, so its length is\n"
            f"# paid on every turn. The budget is Codex's own\n"
            f"# {CODEX_PROJECT_DOC_MAX_BYTES}-byte `project_doc_max_bytes` cap less a margin, because\n"
            f"# that cap is on the *sum* of every AGENTS.md from here down (#68).\n"
            f"[files]\n"
            f"{entry}\n"
        )
    if not quiet:
        print(f"  wrote: {shown}")


def _tpl(rel: str) -> str:
    return resources.files("revenant").joinpath("templates", rel).read_text(encoding="utf-8")


def _mcp_json() -> str:
    """.mcp.json wired to this interpreter, so the agent launches the right server."""
    cfg = {"mcpServers": {"re": {"command": sys.executable, "args": ["-m", "revenant.mcp_server"]}}}
    return json.dumps(cfg, indent=2) + "\n"


def _render_agent_files(target: str, quiet: bool = False) -> None:
    """Generate the `re` skill and the six commands, for each harness, from this build.

    Generated, not copied: upgrading Revenant and re-rendering updates every
    project, where a copied template only ever helped the projects created after
    the fix. `revenant status` reports when a rendered file has fallen behind.

    Skipped, per harness, when an ancestor inside the same repository already
    carries that harness's files -- both harnesses search upwards from the
    directory they start in, and writing a second copy would be the tenth
    project re-seeding the sharing its nine neighbours just undid (#51).
    """
    from . import describe as _describe
    from .cli import harness_location, codex_setup_notes
    old = os.environ.get("REVENANT_PROJECT")
    os.environ["REVENANT_PROJECT"] = target
    warned = False
    try:
        for harness in sorted(_describe.RENDERERS):
            shared = harness_location(target, harness)
            if shared:
                if not quiet:
                    print(f"  {harness} skill already generated in {shared}; not copied here")
                    print(f"             (`revenant describe --render {harness} --here` "
                          f"if this project needs its own copy)")
                continue
            written = _describe.write_rendered(target, harness, _describe.describe(),
                                               warn_empty_mcp=not warned)
            warned = True
            if not quiet:
                for path in written:
                    print(f"  generated  {os.path.relpath(path, target)}")
    finally:
        if old is None:
            os.environ.pop("REVENANT_PROJECT", None)
        else:
            os.environ["REVENANT_PROJECT"] = old
    if not quiet:
        for line in codex_setup_notes(target):
            print(line)


def init_project(target: str, force: bool = False, quiet: bool = False) -> int:
    target = os.path.abspath(target or ".")
    os.makedirs(target, exist_ok=True)

    def _emit(path: str, content: str, keep_existing: bool = False) -> None:
        full = os.path.join(target, path)
        if os.path.exists(full) and (keep_existing or not force):
            if not quiet:
                print(f"  skip (exists): {path}")
            return
        os.makedirs(os.path.dirname(full) or full, exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        if not quiet:
            print(f"  wrote: {path}")

    for d in _DIRS:
        os.makedirs(os.path.join(target, d), exist_ok=True)
        keep = os.path.join(target, d, ".gitkeep")
        if not os.path.exists(keep):
            open(keep, "w").close()

    _emit(".mcp.json", _mcp_json())
    for tpl, dest in _FILES.items():
        try:
            _emit(dest, _tpl(tpl))
        except (FileNotFoundError, ModuleNotFoundError) as exc:
            print(f"  WARN: template {tpl!r} missing ({exc})", file=sys.stderr)
    for tpl, dest in _NEVER_OVERWRITTEN.items():
        try:
            _emit(dest, _tpl(tpl), keep_existing=True)
        except (FileNotFoundError, ModuleNotFoundError) as exc:
            print(f"  WARN: template {tpl!r} missing ({exc})", file=sys.stderr)
    _register_overlay(target, quiet=quiet)

    _render_agent_files(target, quiet=quiet)

    if not quiet:
        name = os.path.basename(target)
        print(f"\nInitialized Revenant project at {target}")
        print("Next:")
        print(f"  1. cd {name}")
        print("  2. drop the game .apk / .xapk / .apks here")
        print("  3. revenant prepare              # runs the whole pipeline")
        print("  4. claude                        # the `re` MCP server is wired up")
        print("     codex                         # same, once you have trusted this repo")
        print("\n(xLua games: `prepare` stops to ask you to reverse the Lua loader and set")
        print(" [lua] in revenant.toml; re-run `revenant prepare` to finish with lua-extract.)")
    return 0
