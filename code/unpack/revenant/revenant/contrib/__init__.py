"""Importable building blocks with no game facts in them.

Not commands and not on the 14-command surface (ADR-0002): these are modules you
import from a project's own `_tools/` script when a title needs them. The
game-specific facts -- addresses, keys, jump tables, opcode maps, URL rules --
stay in the project; only the shape-based machinery lives here.

**The bar for moving something in**: a piece of code belongs here when it holds
**no game fact**. Recurrence is evidence of generality, not a precondition for
it -- the toolbox is meant to grow.

The bar, the enumerated list of what counts as a game fact, why the rule changed
twice, and the separate bar playbooks are held to all live in
`docs/adr/0004-what-qualifies-to-move-into-revenant.md`. They are not restated
here: three copies of one rule is three chances for it to drift, and this one
already had three.

- `decrypt/` -- decryptor machinery for packed titles, plus the CenturyGame
  XXTEA transform and its `$CGF$` container.
- `fetch` -- route A: the remote-acquisition loop (concurrency, retries, resume
  by integrity, survey-before-download), with the HTTP call injected.
- `cache` -- route B: reading what the client already downloaded, whether that
  is an HTTP response cache or a directory of loose bundles.
- `experiments` -- the A/B roster a CMS ships in the package: which items each
  experiment touches and both values of every field it changes.
"""
