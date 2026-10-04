# Project conventions

This file is yours. Revenant creates it once and never writes to it again — put
here only what is true of *this game* and would be wrong for the next one.

Methodology is not here. The `re` skill (`.codex/skills/re/SKILL.md`, generated
from the installed Revenant) carries the commands, the read-only tools, the
evidence rules and this project's outline; six more skills carry the commands
(acquire, scaffold, deep dive, verify, map, boundary). Read this file every
turn, reach for those when you need them.

Things that belong here:

- Naming quirks of this title, once you have found them.
- Which classes turned out to be the real entry points for a subsystem — exact
  names, which is precisely what a reusable pattern cannot carry.
- Traps this specific target has already sprung on you.

Things that do **not** belong here: evidence tiers, the command list, anything
the generated skill already teaches. Those are generated, and a second copy here
would drift out of date exactly the way the old hand-written skill did.

This file is read in full on every turn, so its length is paid on every turn.
`revenant lint --repo` reports it once it goes over the budget recorded in
`.claude/agent-memory/memory.toml`. What does not fit belongs in `notes/`, with
one line here pointing at it.

_(Nothing recorded yet.)_
