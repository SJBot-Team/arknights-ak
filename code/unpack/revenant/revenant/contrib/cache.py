"""Route B: read what the client already downloaded, off the device.

The other half of `docs/playbooks/remote-content-routes.md`. Route A rebuilds
the request and issues it (`contrib.fetch`); this one lets the game run and
parses its cache. Two shapes have been seen in the wild, and neither is a fact
about any title -- they are the on-disk formats of a widely used Unity HTTP
library and of Unity's own bundle cache:

- **An HTTP response cache** (BestHTTP's `files/HTTPCache`) stores the response
  body verbatim behind its headers. `response_body` cuts at the header
  terminator; `parse_response` hands back both halves.
- **A directory of loose bundles** (`cached_bundles/`) is plain `UnityFS` with
  the TypeTree intact. `export_bundle_dir` walks it and writes the *same*
  per-type tree `extract-scenes` writes for a bundle out of the package, so a
  MonoBehaviour that arrived over the network lands beside one that shipped.

What stays in the project: where the cache lives on the device, which entries
matter, and any grouping of the exported objects by what they mean in that game.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:                       # imported lazily at run time: `contrib`
    from ..assets import BundleReport   # must stay importable without UnityPy

HEADER_END = b"\r\n\r\n"
# A header line is `Name: value`; the first line may be a status line instead.
_HEADER_LINE = re.compile(rb"^[!#$%&'*+.^_`|~0-9A-Za-z-]+:[ \t]*.*$")
_STATUS_LINE = re.compile(rb"^HTTP/\d(?:\.\d)?[ \t]+\d{3}\b")


def split_response(raw: bytes) -> tuple[bytes, bytes]:
    """(header block, body). The header block is `b""` when there is none.

    Deliberately not "cut at the first blank line and hope": a cached body can
    hold `\\r\\n\\r\\n` of its own -- pretty-printed JSON with CRLF endings does,
    and so does anything base64-wrapped -- and cutting there silently beheads
    it. So the prefix has to *read* as headers before it is treated as any.
    """
    at = raw.find(HEADER_END)
    if at < 0:
        return b"", raw
    head = raw[:at]
    lines = head.split(b"\r\n")
    if not lines or not all(_HEADER_LINE.match(line) or _STATUS_LINE.match(line)
                            for line in lines if line):
        return b"", raw
    return head, raw[at + len(HEADER_END):]


def response_body(raw: bytes) -> bytes:
    """The cached response body, with the HTTP headers stripped if present."""
    return split_response(raw)[1]


def parse_response(raw: bytes) -> tuple[dict, bytes]:
    """({lower-cased header name: value}, body). The status line is not a header."""
    head, body = split_response(raw)
    headers: dict = {}
    for line in head.split(b"\r\n"):
        if not line or _STATUS_LINE.match(line):
            continue
        name, _, value = line.partition(b":")
        headers[name.decode("latin-1").strip().lower()] = value.decode("latin-1").strip()
    return headers, body


# ── a directory of loose bundles ────────────────────────────────────────────


def export_bundle_dir(root: str, out_root: str, *, load=None, by_script: bool = False,
                      dump_hierarchy: bool = False,
                      unity_version: str | None = None) -> list["BundleReport"]:
    """Export every bundle under `root` into `out_root/<sub-dir>/<file>/`.

    The same export tree as a bundle taken out of the package: `assets.export_blob`
    is called, not re-implemented, so the two cannot drift apart. Each bundle's
    directory relative to `root` becomes its group -- a cache keyed by content id
    keeps that id in the output path for free.

    A file that is not a bundle, or that will not load, is recorded on that
    entry's report rather than raised; a cache directory routinely holds
    something else as well, and Unity's own `__info` metadata files are in every
    one of them.

    A `root` that is not there raises, because it is a different fact from a
    directory holding no bundles and walking a missing path returns the same
    empty list as an empty one -- reporting the typo as the download's content.
    """
    from .. import assets

    if not os.path.isdir(root):
        raise FileNotFoundError(f"no such directory: {root}")
    load = assets.default_loader(load, unity_version)
    reports = []
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = sorted(dirs)
        rel = os.path.relpath(dirpath, root)
        group = assets.ROOT_GROUP if rel == "." else rel
        for name in sorted(names):
            report = assets.BundleReport(
                group=group, name=name, size=0,
                out_dir=os.path.join(out_root, assets.safe_name(group, "group"),
                                     assets.safe_name(name, "bundle")))
            reports.append(report)
            try:
                with open(os.path.join(dirpath, name), "rb") as handle:
                    data = handle.read()
            except OSError as exc:
                # One unreadable file must not lose the batch: the caller is
                # pointing at 1,259 files pulled off a CDN, and the docstring
                # above promises this is recorded rather than raised.
                report.errors.append(f"{name}: {type(exc).__name__}: {exc}")
                continue
            report.size = len(data)
            if not assets.bundle_payload(data).startswith(assets.UNITYFS):
                report.errors.append(f"{name}: no UnityFS signature")
                continue
            assets.export_blob(data, report, load, dump_hierarchy=dump_hierarchy,
                               by_script=by_script)
    return reports
