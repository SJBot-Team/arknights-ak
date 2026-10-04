---
description: Acquire a game package and prove it is the one you meant
argument-hint: <game name or package id>
---
Get the package for `$ARGUMENTS` into this project and establish that it is genuinely that publisher's build. Follow the `re` skill. This is you driving: mirror sites change their pages and their download mechanics constantly, so work out the current interaction yourself rather than following a recipe — what is written here is the part that does not change.

## 1. Resolve the package id, then confirm the publisher

Never take a title match as identification. The merge/puzzle category is saturated with name-squatting clones: a search for one well-known title returned a package literally titled the same by an unrelated studio. Analysing a clone as the benchmark silently poisons every cross-game comparison built on top of it.

Fix the identity on evidence before downloading:

- the developer name on the store listing, against the studio you actually mean
- the reverse-DNS package id — a studio's own domain is hard to fake and easy to check
- if two candidates remain, download the smaller one first and settle it with step 3

State which candidate you picked and on what evidence.

## 2. Acquire

Prefer the official store when you can reach it. Otherwise a mirror. Record **which source and which version string** in your report below — mirrors sometimes carry builds the store no longer serves, and the note written later needs to say where the artefact came from.

Practical notes, not instructions — verify each still holds:

- Mirrors commonly gate the real file behind a session token and inject the link with JavaScript, so the download URL is usually not in the first HTML you fetch. Look for a token/check-in endpoint, keep the same session (cookies + referer) for the file request, and expect the link to be percent-encoded inside the page.
- Some mirrors sit behind a JS challenge that a plain HTTP client cannot pass at all. That is a signal to use a browser, not to try harder with the client.
- A file arriving as `.apks` is fine — that is Google's split format and this harness reads it like an `.xapk`.

## 3. Prove what you got, before anything else touches it

Do all of these and report them:

- **It is a zip and it is whole.** First bytes `PK\x03\x04`, and the archive opens and lists its members without error.
- **The package id is self-consistent.** Open the base apk's manifest: the providers, permissions and authorities should all carry the package id you expect as a prefix. A repackaged build often leaves the original id in some of these and not others.
- **The splits are present.** A split package should carry `config.*.apk` alongside the base; a base-only download will be missing the native libraries.
- **It is a Unity IL2CPP build** if that is what you expect: `assets/bin/Data/Managed/Metadata/global-metadata.dat` exists.

Then drop it in the project root and run `revenant fingerprint`. Read the observations for anything that contradicts the identity you settled in step 1 — `dex_packages` four segments deep name the SDKs and often the publisher, `build_paths` name the build machine, `native_exports` name the vendors. A mirror can serve a repackaged or resigned build; the fingerprint is where that shows up, and it observes rather than judges, so the reading is yours. `signing_certs` is the sharpest of these: repackaging requires resigning, so a digest that differs from another copy of the same version means the artefact was rebuilt, and two packages sharing a digest were signed by the same key.

If anything here fails, say so and stop. An analysis built on the wrong package is worse than no analysis, because it looks like a result.

## 4. Hand off

Report: the package id and version, the source and why you trust it, the four checks in step 3, and the fingerprint's first read. Then `revenant prepare`.
