# AGENTS.md

## Agent skills

The skills these flows rely on are vendored from `mattpocock/skills` into
`.agents/skills/`, with `.claude/skills/` holding symlinks into it. **Both
directories are gitignored; `skills-lock.json` is the tracked artefact** — it
pins all 26 skills by source path and content hash, the same split this repo
already uses for `uv.lock` and `.venv/`.

Worth knowing before a fresh clone: until the vendored copy is restored,
`/wayfinder`, `/to-spec`, `/grilling` and the rest do not exist, and the map's
workflow cannot be followed.

### Restoring the vendored skills

```bash
npx skills experimental_install                     # reads skills-lock.json
mkdir -p .claude/skills                             # then wire the agent dir
for d in .agents/skills/*/; do n=$(basename "$d"); \
  ln -sfn "../../.agents/skills/$n" ".claude/skills/$n"; done
```

Two gaps, both observed by actually running it into an empty directory holding
only the lockfile — not read off the tool's help text:

- **`experimental_install` restores `.agents/skills/` and stops there.** It does
  not create the `.claude/skills/` symlinks, and neither does
  `experimental_sync`. Without the second step Claude Code finds no project
  skills at all, so the restore looks like it worked and nothing is available.
  (`skills add` symlinks by default, which is where the existing links came
  from; the lockfile path skips it.)
- **`writing-great-skills` no longer resolves.** 25 of the 26 locked skills
  restore; that one's upstream path is gone, so the lock pins something that
  cannot be fetched. Nothing here uses it — but a lockfile that cannot be fully
  replayed is worth knowing about before someone reads a partial restore as
  success.

### Issue tracker

Issues live in GitHub Issues on `joycastle/revenant`, operated via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
