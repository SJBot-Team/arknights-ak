# Judge same-origin by project fingerprints, not shared keys

Verified on: the Cookie/Cola pair and the eight-title cross-comparison
(build-machine roots, internal domains).

Two packages are from the same codebase when they share *project-instance*
signals — things that a build produced once and that two independent projects
would not collide on:

- **Build-machine absolute paths.** `/Users/<user>/…/workspace/<Codename>/…`
  names the CI host and the internal project codename. Compare the shared
  directory *root*, not whole paths: two titles from one studio sit side by side
  under the same checkout root with different codenames (observed as
  `…/workspace/Cookie…` and `…/workspace/Cola…`).
- **Addressables built-in group GUIDs**, the `boot.config` `memorysetup` lines,
  and **internal domains** (`*.corp.<company>.cn`).

These beat "the two share a decryption key": a key can be a shared library
default, while a build-machine root is specific to one studio's infrastructure.

## Same origin is not same implementation

Treat the verdict as a hint, never as licence to inherit findings. Two branches
of one codebase in the reference corpus had 533 vs 707 config tables and
opposite hot-update settings. `revenant fingerprint` lists the raw signals
(build paths, unity version, declared assemblies, native exports, domains); the
comparison and the verdict are yours to make from them — the tool stopped
scoring it (ADR-0002, #28).
