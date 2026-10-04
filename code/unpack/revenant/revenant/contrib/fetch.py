"""A skeleton for pulling remote content down: concurrency, retries, resume,
and a survey pass that sizes everything before anything is written.

Nothing in the loop is a fact about any title, which is the bar (#50). Two titles
happened to write it twice -- `fetch_lua.py` (Hollywood Merge, CDN) and
`fetch_ucd.py` (Love & Pies, Unity CCD) -- which is evidence that it is general,
not the reason it is here. They are not byte-identical the way `dump_strlit.py`
was: the URL rules differ, and those differing halves stayed in the projects.

Travel Town's two cache readers are *not* in this count: they are the other
route (below), and this module does not serve them.

**The HTTP action is injected.** Nothing here opens a socket: callers pass a
`get(url) -> bytes` and, for the survey, a `probe(url) -> headers`. That keeps
the title's URL rules, ids, auth and user agent in the project where they
belong, and it makes the loop testable without a network.

Two things this encodes that were learned the hard way, and that a re-write
tends to get wrong:

- **Resume is an integrity question, not an existence question.** A truncated
  download looks finished: right name, non-zero size, and every later run skips
  it. `complete=` therefore takes a predicate over the file's *content*; leave
  it out and existing files are re-fetched rather than trusted.
- **Sizing needs a ranged GET, not a HEAD.** A HEAD against a CDN that
  redirects to storage answers 200 with no `Content-Length`, so every entry
  surveys as 0 bytes. A one-byte ranged GET carries the total in
  `Content-Range`. `RANGE_PROBE_HEADERS` and `size_from_headers` are that
  knowledge; the request itself is still the caller's.

Two routes exist for getting remote content, and only the first is served here:
fetching from the CDN, versus reading what the client already cached. The second
is local parsing and lives in `contrib.cache`; both are written up in
`docs/playbooks/remote-content-routes.md`.
"""

from __future__ import annotations

import concurrent.futures as _cf
import hashlib
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

# A one-byte ranged GET: the only request shape observed to carry a length back
# through a redirect to storage.
RANGE_PROBE_HEADERS = {"Range": "bytes=0-0"}

OK = "ok"
SKIP = "skip"
REJECTED = "rejected"     # downloaded, but failed the caller's integrity check
ERROR = "error"           # retries exhausted
NO_SIZE = "no-size"       # the probe answered, but without a length


class Unretryable(Exception):
    """Raise from an injected `get`/`probe` when retrying cannot help.

    A 404 or a 403 is an answer, not a hiccup; retrying it four times only
    slows a failing run down. `status` is what the tally will count it as.
    """

    def __init__(self, status: str = "unretryable"):
        super().__init__(status)
        self.status = status


@dataclass(frozen=True)
class Entry:
    """One thing to fetch. `meta` carries whatever the title's checks need."""

    name: str                       # path under the output directory
    url: str
    meta: Mapping = field(default_factory=dict)


@dataclass(frozen=True)
class Outcome:
    status: str
    entry: Entry
    size: int = 0
    detail: str = ""


@dataclass
class Result:
    outcomes: list

    @property
    def tally(self) -> Counter:
        return Counter(o.status for o in self.outcomes)

    @property
    def total_bytes(self) -> int:
        return sum(o.size for o in self.outcomes)

    @property
    def failures(self) -> list:
        """Every outcome that is neither a fetch nor a legitimate skip."""
        return [o for o in self.outcomes if o.status not in (OK, SKIP)]

    def ok(self) -> bool:
        return not self.failures


# ── resume and integrity predicates ─────────────────────────────────────────


def magic_check(magic: bytes, window: int = 2048) -> Callable:
    """`(data, entry) -> bool`: the blob announces itself within `window` bytes.

    What Love & Pies used (`UnityFS`), and the cheapest check that a download
    is a whole file of the expected kind rather than an error page.
    """

    def check(data: bytes, _entry: Entry) -> bool:
        return data[:window].find(magic) >= 0

    return check


def digest_check(key: str = "md5", algo: str = "md5") -> Callable:
    """`(data, entry) -> bool`: the body hashes to `entry.meta[key]`.

    What Hollywood Merge used: its manifest's md5 doubles as the integrity
    check, so a half-written file is caught rather than skipped next run. An
    entry without the key is treated as unverifiable, so it is never skipped.
    """

    def check(data: bytes, entry: Entry) -> bool:
        want = entry.meta.get(key)
        return bool(want) and hashlib.new(algo, data).hexdigest() == want

    return check


def file_is_complete(path: str, entry: Entry, check: Callable | None, window: int = 0) -> bool:
    """Whether an existing file may be skipped. False when there is no check.

    `window` reads only the first N bytes, which is what a magic check needs;
    a digest check must see the whole file and passes 0.
    """
    if check is None or not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    with open(path, "rb") as handle:
        data = handle.read(window) if window else handle.read()
    return bool(check(data, entry))


# ── survey: sizes only, nothing written ─────────────────────────────────────


def size_from_headers(headers: Mapping) -> int:
    """Total size from a ranged-GET response.

    `Content-Range: bytes 0-0/12345` names the whole object; `Content-Length`
    on that same response is 1. So the range wins, and Content-Length is only
    the fallback for a server that ignored the range.
    """
    rng = str(headers.get("Content-Range") or "")
    if "/" in rng:
        total = rng.rsplit("/", 1)[-1].strip()
        if total.isdigit():
            return int(total)
    length = str(headers.get("Content-Length") or "").strip()
    return int(length) if length.isdigit() else 0


def survey(entries: Sequence[Entry], probe: Callable, workers: int = 6,
           on_outcome: Callable | None = None) -> Result:
    """Size every entry without writing a byte, so a run can be costed first."""

    def one(entry: Entry) -> Outcome:
        try:
            headers = probe(entry.url)
        except Unretryable as exc:
            return Outcome(exc.status, entry, 0, str(exc))
        except Exception as exc:                      # a survey never retries
            return Outcome(ERROR, entry, 0, f"{type(exc).__name__}: {exc}")
        size = size_from_headers(headers)
        if not size:
            # A HEAD, or a GET the CDN redirected, comes back with no length.
            # Counted as a success it reads as "this file is free", and a whole
            # survey totals to nothing while looking like it worked.
            return Outcome(NO_SIZE, entry, 0, "the probe carried no length back")
        return Outcome(OK, entry, size)

    return Result(_map(one, entries, workers, on_outcome))


# ── fetch ───────────────────────────────────────────────────────────────────


def fetch_all(entries: Sequence[Entry], get: Callable, out_dir: str, *,
              accept: Callable | None = None, complete: Callable | None = None,
              complete_window: int = 0, workers: int = 6, retries: int = 4,
              sleep: Callable = time.sleep, on_outcome: Callable | None = None) -> Result:
    """Fetch every entry into `out_dir/<entry.name>`.

    `accept(data, entry)` decides whether a body is the thing that was asked
    for; a body that fails is not written, and is reported as `rejected` rather
    than counted as success. `complete(data, entry)` decides whether an existing
    file may be skipped -- pass the same predicate to both and resume means
    "already have a good one" instead of "a file with that name exists".

    `on_outcome(index, outcome, running)` is called from the calling thread as
    each entry finishes, with the tally so far. Both project scripts printed a
    progress line every N entries and a line per failure; a run of a thousand
    bundles that says nothing for forty minutes is indistinguishable from a hung
    one, which is why the callback is here rather than left to each caller (#50).
    """
    def one(entry: Entry) -> Outcome:
        dest = os.path.join(out_dir, entry.name)
        if file_is_complete(dest, entry, complete, complete_window):
            return Outcome(SKIP, entry, os.path.getsize(dest))
        last = ""
        for attempt in range(retries):
            try:
                data = get(entry.url)
            except Unretryable as exc:
                return Outcome(exc.status, entry, 0, str(exc))
            except Exception as exc:
                last = f"{type(exc).__name__}: {exc}"
                sleep(0.5 * (attempt + 1))
                continue
            if accept is not None and not accept(data, entry):
                return Outcome(REJECTED, entry, len(data), "failed the integrity check")
            parent = os.path.dirname(dest)
            os.makedirs(parent or out_dir, exist_ok=True)
            # Built beside the destination and moved onto it. A completeness
            # check reads the head, so a pull killed part-way through would
            # otherwise leave a file that still says `UnityFS` and passes for
            # done on the next run -- the very thing resume must not do.
            staging = dest + ".part"
            with open(staging, "wb") as handle:
                handle.write(data)
            os.replace(staging, dest)
            return Outcome(OK, entry, len(data))
        return Outcome(ERROR, entry, 0, last or "retries exhausted")

    os.makedirs(out_dir, exist_ok=True)
    return Result(_map(one, entries, workers, on_outcome))


def _map(work: Callable, entries: Iterable[Entry], workers: int,
         on_outcome: Callable | None = None) -> list:
    """Run `work` over the entries, in order, `workers` at a time.

    Outcomes are handed to `on_outcome` as they arrive, in entry order, on this
    thread -- so a caller can print progress without a lock of its own.
    """
    entries = list(entries)
    out: list = []

    def collect(source):
        for outcome in source:
            out.append(outcome)
            if on_outcome is not None:
                on_outcome(len(out), outcome, Result(out))
        return out

    if workers <= 1 or len(entries) <= 1:
        return collect(work(entry) for entry in entries)
    with _cf.ThreadPoolExecutor(max_workers=workers) as pool:
        return collect(pool.map(work, entries))


def human_bytes(size: float) -> str:
    """A byte count in the largest unit that keeps it under 1024."""
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def report(result: Result) -> str:
    """One line for a run, plus one per failure -- what both copies printed."""
    lines = [f"{dict(sorted(result.tally.items()))}  {human_bytes(result.total_bytes)}"]
    lines.extend(f"  [{o.status}] {o.entry.name} {o.detail}".rstrip() for o in result.failures)
    return "\n".join(lines)
