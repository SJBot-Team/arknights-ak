# Two routes to remote content, and how to tell which one a title leaves open

Verified on: Hollywood Merge and Love & Pies (fetch from the CDN), Travel Town
(read what the client already downloaded). Four titles in all, counting Travel
Town's two separate caches.

A title whose package holds almost no content is not a dead end — it is a
question about *where the bytes are reachable from*. Two routes exist, and which
one is open is decided by things you can check statically, before writing any
code.

## Route A — fetch it yourself

Rebuild the request the client makes and issue it.

**Preconditions, all of which are statically checkable:**

1. **The URL is reconstructable from the shipped package.** Either the catalog
   ships whole URLs (Love & Pies: `catalog.json`'s `m_InternalIds`, with three
   placeholders), or the code builds them from a base plus a manifest field
   (Hollywood Merge: `XYDConf.CdnUrl + res + "." + md5`, read out of
   `libil2cpp.so`).
2. **Every placeholder in that URL has a source in the package.** Love & Pies'
   project/environment/bucket ids sit in the metadata string heap as one JSON
   object per environment; `revenant strings` puts them on disk.
3. **The version selector is taken, not guessed.** Love & Pies' release badge
   (`0_81_0_7503`) is baked into the catalog's own URLs. Guessing it wrong does
   not fail loudly — it silently serves another build's content.
4. **No credential is required.** Both CDNs answered a plain GET with a player
   User-Agent. If the endpoint wants a session token, Route A is closed unless
   the token itself is derivable, which in practice it is not.

**What the response has to be checked against.** A body that arrives is not a
body that is right: check the magic (`UnityFS`) or the manifest digest. This is
the same check that decides resume — see below.

`revenant.contrib.fetch` is the loop for this route: concurrency, bounded
retries, resume, and a survey pass. The HTTP call is injected, so the URL rules,
ids and User-Agent stay in the project script where they belong.

## Route B — read what the client already downloaded

Let the game run, then parse its cache off the device or emulator.

**Preconditions:**

1. **The game runs far enough to download.** Travel Town's content arrives
   during first boot; a title gated behind a login you do not have does not get
   there.
2. **You can read the app's private storage.** An emulator with root, or a
   backup extraction. This is the step that actually blocks people.
3. **You know which cache and what wraps it.** Two shapes seen, and
   `revenant.contrib.cache` is the construct for both:
   - **BestHTTP cache** (`files/HTTPCache`): the response body verbatim behind
     HTTP headers. `cache.response_body` cuts at the header terminator -- and
     checks that the prefix really *is* headers first, because a cached body can
     hold a `\r\n\r\n` of its own and splitting at the first one beheads it.
   - **Unity cached bundles** (`cached_bundles/`): plain `UnityFS` with the
     TypeTree intact. `cache.export_bundle_dir` walks the directory and calls the
     same `assets.export_env` a packaged bundle goes through, so an object that
     arrived over the network lands in the same tree as one that shipped.

   What stays in the project: where the cache lives on the device, and any
   grouping of the exported objects by what they mean in that game.

**When Route B is the only one.** A locator registered at runtime — Travel
Town's `RemoteContentLocator` — leaves no URL in the package to rebuild. Nothing
static will produce the address; the client has to make the request for you.

## Choosing

Ask, in this order:

1. Does the package contain the URLs or the rule that builds them? → Route A.
2. Are all the placeholders and the version selector present too? → still A.
3. Otherwise → Route B, and budget for device access rather than code.

Route A scales (Love & Pies: 1,259 bundles, 870 MB, zero failures, unattended)
and is reproducible by anyone with the package. Route B gets you exactly what
that client fetched, on that build, with that account — which is sometimes more
than the CDN would hand out, and sometimes less.

Both routes now have a construct, not just a write-up: `contrib.fetch` for A,
`contrib.cache` for B. Neither opens a socket or knows a path on a device.

## Before downloading anything, survey

Both routes answer "how much is there" before "give me all of it". For Route A
that is a sizing pass: `contrib.fetch.survey`, one entry at a time, writing
nothing.

Use a **one-byte ranged GET**, not a HEAD. A HEAD against a CDN that redirects
to storage answers 200 without `Content-Length`, so every entry surveys as zero
and the total reads as "there is nothing there". The ranged GET carries the real
size in `Content-Range: bytes 0-0/<total>`; `Content-Length` on that same
response is 1, so the range has to win.

## Resume is an integrity question

A truncated download has the right name and a non-zero size. Any resume rule of
the form "the file exists, skip it" makes that file permanent: every later run
skips it, and the corruption surfaces much later, as a parse error in something
downstream.

Skip a file only when its **content** passes a check — the bundle magic, or the
manifest's digest. `contrib.fetch` takes that predicate as an argument and, with
no predicate given, re-fetches rather than trusting what is on disk.
