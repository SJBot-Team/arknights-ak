# Revenant

A reverse-engineering harness that brings dead binaries back to source. Unity
**IL2CPP** (ARM64 / ARM32 / Thumb, auto-detected) plus **xLua** game logic,
driven by any MCP-capable coding agent through a read-only MCP server. The
shipped skill and the six commands are rendered for **Claude Code** and
**Codex** from one source; see "Two harnesses" below for what each one gets.

Install once, then `revenant init` a fresh directory per game and start reversing.

## Install

```bash
uv tool install 'revenant-re[all]'      # revenant + revenant-mcp on PATH
# or, into a project venv:  uv pip install 'revenant-re[all]'
```

Extras: `assets` (UnityPy, for AssetBundle/Lua extraction), `harness` (the MCP
server), `all` (both). A JRE is needed for Lua decompilation (the unluac jar is
vendored). Cpp2IL is an external tool — point the `run-cpp2il` step of `revenant prepare`
at it via `$CPP2IL` or `$CPP2IL_DIR`.

## Start a project

```bash
revenant init game-x && cd game-x
# drop the game .apk / .xapk / .apks here, then ONE command for the whole pipeline:
revenant prepare                        # extract → Cpp2IL → indices → seed-src → lua
claude                                  # the `re` MCP server is wired up
# or: codex                             # same, once you have trusted the repo (below)
```

`revenant prepare` runs every prep step end to end (extract-apks → find-binary →
find-metadata → run-cpp2il → build-indices → seed-src → lua-extract), skipping
expensive steps already done. `--force` redoes them, `--keep-going` continues
past a failure, `revenant status` shows what's set up. One step on its own is
`revenant prepare --only <step>` (e.g. `--only run-cpp2il`).

`revenant help` lists the fourteen core commands; `revenant help --all` adds the
query tier (the CLI form of what agents reach through MCP). The breadth-scan
extension (`packs probe cell ledger scan naming-stats`) is frozen and appears
only in projects with `[packs] enabled` set — see `docs/adr/0002-*`.

`init` scaffolds the working tree (`_apks/ _binaries/ _refs/ lua/ src/ notes/
decompiled/`), both harnesses' files (below), and `revenant.toml` (the project
marker + config). The toolkit resolves the project from the cwd, so the same
install drives every project.

Several projects in one repository share one copy of the generated files. Both
harnesses search from the directory they start in up to the repository root, so
the skill and the commands can sit at the top and serve every project below.
`init` and `describe --render <harness>` find that layer and write there rather
than making a second copy; `revenant status` says which layer they are on.
`--here` forces a project its own copy, which is how one is taken back out. The
per-project conventions file stays per project, always — holding "true here,
wrong for the next game" is the whole of what it is for.

## Two harnesses

The method has one source. `revenant describe` builds a harness-neutral
description of this build — commands, MCP tools, evidence rules, this project's
outline — and a renderer per harness turns it into files. What differs between
them is where a file lands and how it is loaded, never what it teaches. `init`
lays down both without a switch to remember; `revenant status` reports each one
separately and says nothing about a harness this project does not have.

| | Claude Code | Codex |
|---|---|---|
| `re` skill | `.claude/skills/re/SKILL.md` | `.codex/skills/re/SKILL.md` |
| the six commands | slash commands in `.claude/commands/` — you type `/re-deep X` | one on-demand skill each under `.codex/skills/` — the model picks one from its description |
| MCP server | `.mcp.json`, works immediately | `.codex/config.toml`, works once you trust the repository |
| permissions | `.claude/settings.json` auto-allows the read-only `re` tools | none — see ADR-0001 |
| your own conventions | `.claude/skills/re-project/SKILL.md`, on demand | `AGENTS.md`, loaded every turn and therefore size-checked by `lint --repo` |

Two costs on the Codex side are deliberate. The commands lose the *entry point*
half of what a slash command is: a person typing `/re-deep X` is certain, a model
choosing a skill from its description is not. And the MCP entry does nothing
until you mark the repository trusted in your own `$CODEX_HOME/config.toml` —
`codex mcp add re -- <python> -m revenant.mcp_server` does it, and `revenant
status` tells you when it is missing. Revenant never writes to your home
directory, so it does not do that step for you.

Anything else that speaks MCP (Cursor, …) can still consume the `re` tools —
`.mcp.json` is a standard stdio entry — but you bring your own prompting there.

## xLua games

If `re_status` reports Lua bundles, the gameplay is in Lua. Reverse the game's
Lua loader (find its cipher/`Crypt` class and file-pack class with the `re`
tools; the XOR key is usually a `const` that `re_type_info` surfaces), set
`[lua] xor_key/container/size_t` in `revenant.toml`, then:

```bash
revenant lua-extract                    # decrypt → unpack → decompile into lua/
```

Then explore across the boundary: `re_lua_grep` to find logic, `re_lua_bridge`
to resolve `CS.<Type>` calls into the C# side.

## Managed source

For the titles whose logic ships as C# rather than Lua — HybridCLR and IFix
hot-update assemblies — the same four moves, over the source tree instead of
the indices:

```bash
revenant cs-list [query]                # every .cs, across both source roots
revenant cs-get <Type|path> [--from R]  # one file's source
revenant cs-grep <regex>                # root/path:line: text
revenant cs-refs <Symbol>               # where it is declared, where it is mentioned
```

Two roots, and they are never silently merged: `src/<version>/` is the
scaffold `seed-src` lays down — stubs with the bodies stripped —
and `src-hotupdate/<version>/` is source recovered from the hot-update
assemblies, the bodies that actually shipped. Every line of output says which
root it came from, and a name present in both comes back as both rather than as
a pick, because "the stub" and "the shipped body" answer different questions.
`--from scaffold|hotupdate` chooses. Only the first root is revenant's own —
`seed-src` writes it — so where a project lands its *recovered* source is that
project's fact and `[csharp] roots` replaces the pair.

A handle is a path, a `root/path` label, or a type name; a type renamed away
from its file, or the second type in one file, is found by what the file
declares rather than by what it is called.

`cs-refs` matches whole identifiers, so `ItemConfExtra` is not a reference to
`ItemConf`, and it separates declarations from mentions — by whether the symbol
stands in the *name* position, so `private ItemConf _cfg;` declares `_cfg` and
`Reward(1, 2);` is a call. It is text, not a resolved call graph — a comment, a
string literal and a same-named type in another namespace all count, and a
signature split across lines can land in the wrong column — and it says so in
its own output. `xrefs` resolves RVAs; this reads source. Nothing here caps by
depth: you named the tree. What is capped is how many lines are shown, reported
per column as `2 of 15`. All four are on the MCP surface as `re_cs_list /
re_cs_source / re_cs_grep / re_cs_refs`, which print the same answers from the
same code.

## Config tables

Opening the container is where most toolkits stop; the numbers work starts after
it. `revenant table list` prints the config tables a project has — rows, fields,
and **which reader read each one**, because the corpus is found automatically and
a wrong guess has to be visible somewhere:

```bash
revenant table list                     # name, rows, fields, reader, corpus
revenant table census <table>           # per field: fill, distinct, common values
revenant table diff <A> <B>             # rows, fields and values two tables disagree about
revenant table diff <dirA> <dirB>       # two corpora: which tables each side has
revenant table refs <table>             # how often it is named, per corpus
```

`census` is the first move on an unfamiliar table, and the one that keeps a
column from being read as the wrong thing: a `cost` where one value covers 652
rows and the rest are eight-digit numbers is a resource id, not a quantity, and
the distribution shows it where the field name does not. It reports the spread
and stops there — calling the column an id is the reader's conclusion, and
belongs in a note.

`diff` exists because comparing across two titles has produced the wrong answer
twice, in opposite directions, both times looking confident. The same game with
different codegen (`costId` against `CostId`) reported eight core tables as "all
different" — `--normalize-names` aligns them and they match row for row. And a
field whose tag was never recovered rendered its bytes as hex, so `[1]` met
`["01"]` and the report said 929 rows differ, when all 929 were identical. That
second one is a decoding problem and `diff` cannot fix it — but it refuses to
report it as content: a column whose two sides hold different kinds of value is
listed separately, marked, and left out of the difference count — and the rows
it suppressed are reported as *undetermined* rather than as the same, because
"we could not tell" is not "they match". Given two directories instead of two
files it compares corpora, naming which tables each side has. A path may point
into another project, and each side is read with its own project's schema and
keys.

Discovery is by shape, not by name (directory and file-naming conventions are
facts about one title, so revenant knows none of them) and it is bounded — it
sweeps `res/`, `decompiled/` and `lua/` three levels deep under caps it reports
rather than walking the tree. `[tables] dirs` in `revenant.toml` points it
elsewhere and replaces the sweep. Read today: the id-to-row map and the row
array that JSON dumps produce; binary blobs — Luban or a FlatBuffers CMS
library — once the project says which they are (below); and Lua table
constructors, which two titles keep their config in and `lua-extract` has
already decompiled.

A directory of `.lua` qualifies as a corpus by *shape* — a table whose entries
are tables — because `lua/<version>/` is the whole decompiled game and matching
on names would report thousands of gameplay modules as unreadable tables. Lua
rows are counted per file and the listing says so: one title ships variants of
one table as 62 files and the game loads 47, so summing them overstates the
rows by a third, and which ones load is a fact about that title's loader.

`refs` counts mentions of a table — and of its row class, which codegen usually
names differently — across every C# source root, the metadata strings and the
Lua tree, reporting each corpus on its own and never summing them. The C# roots
are the ones `cs-refs` searches, asked of the same code: both built-in roots get
a line, `[csharp] roots` replaces the pair, and a title whose table loading
lives in the hot-update bodies is counted there rather than reported as
unsearchable. It never calls a table dead: one title's parser reads override
rows before parsing any table, so a zero specific reference does not mean
unloaded, and that judgement belongs in a note. A corpus that is not there says
"cannot check" rather than contributing a zero — and so does one that is there
and empty, because a `src/` holding no `.cs` at all means seeding never ran. The
row class comes from the schema's declaration, so nothing is decoded to answer
this and a table whose bytes will not parse still gets a straight answer. A path
into a sibling title resolves with *that* project's schema, but the corpora
searched are the one you are standing in, and the output says so.

For the analysis a command cannot do — joins, graph walks, custom aggregates —
`revenant.tables.rows(table)` hands back the rows with the wrapper key already
off, which is the two lines every analysis note used to open with.

**Luban titles.** `revenant luban-read <blob> --schema schema.json` decodes a
Luban binary table, and setting `[tables] luban_schema` lets `table list` read
them in place. The format is built in (a big-endian prefix varint for integers,
little-endian IEEE for floats — see `docs/playbooks/luban-table-format.md`); the
schema and the container stay in the project, because bean names and a
decryption key are facts about one title. A schema that is short a field still
produces rows, all of them shifted, so the leftover bytes are reported as an
error on that table rather than a footnote.

**FlatBuffers titles.** `[tables] fb_schema` plus `[tables.fb_roots]` name the
recovered schema and which root class each `.bin` holds, and `table list` reads
the CMS library like any other corpus — `Root#Field` picks the vector when a
root holds several. A directory of nothing but `.bin` counts as a corpus as soon
as the project names one of its files, which is the shape a CMS library has.
Values the decoder had to probe rather than read off a declared type keep their
`?` marker through `census`, so a reader can see which columns to drop a tier.

A FlatBuffers **union** is two slots — a member tag and a value — and they come
back as the one field they are: `{"type": [...], "value": ...}`. The tag is not
a label printed beside the value, it *selects* the class the value is decoded
as, per element for a repeated union — so the member list is what turns a union
from a probe into a concrete type. `fb-schema` records the pairing; the member
list is a list of concrete class names that is not in the buffer, so it goes in
the schema's `union_members` alongside `guid_types`. Without it the tags are
still reported as numbers and `fb-read` says on stderr that a member list is
what is missing.

## Tools surfaced to the agent (`mcp__re__*`)

`re_status`, `re_search`, `re_type_info`, `re_find_asm`, `re_cfg`, `re_lookup`,
`re_xrefs`, `re_callgraph`, `re_field_scan`, `re_disasm`, `re_evidence`,
`re_find_binary`, `re_find_metadata`, and the Lua set `re_lua_list /
re_lua_source / re_lua_grep / re_lua_refs / re_lua_bridge`. All read-only.

Bundled `unluac` is MIT-licensed (see `revenant/vendor/`).
