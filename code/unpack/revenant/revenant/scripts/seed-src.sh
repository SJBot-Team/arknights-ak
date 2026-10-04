#!/usr/bin/env bash
# seed-src.sh — Seed src/<version>/ with the game stub set as copy-on-write
# (APFS clonefile, `cp -c`) clones of the Cpp2IL DiffableCs output, as the
# reverse-engineering base. The originals under
# _refs/<version>/cpp2il_out/DiffableCs/ stay pristine as the reference.
#
# Third-party / engine assemblies (UnityEngine, System, Facebook, AppsFlyer,
# DOTween, ...) are excluded by default -- only game code is seeded. Pass --all
# to clone every assembly.
#
# Re-runnable: only files missing from src/ are cloned, so reconstructions you
# have already written are never overwritten.
#
# Usage: tools/seed-src.sh [version] [--all]
#   version  default: auto-detected from the package
#   --all    seed every assembly, including engine/third-party (default: game code only)
set -euo pipefail
cd "${REVENANT_PROJECT:-$(pwd)}"

PY="${REVENANT_PY:-python3}"

INCLUDE_ALL=0; VERSION=""
for a in "$@"; do
  case "$a" in
    --all) INCLUDE_ALL=1 ;;
    *) VERSION="$a" ;;
  esac
done
[ -n "$VERSION" ] || VERSION="${REVENANT_VERSION:-$("$PY" -c "from revenant import config;print(config.detect_version())" 2>/dev/null || true)}"
VERSION="${VERSION:-0.0.0}"

REF="${REVENANT_REF_DIR:-_refs/$VERSION}/cpp2il_out/DiffableCs"
SRC="src/$VERSION"
if [ ! -d "$REF" ]; then
  echo "Error: DiffableCs not found at $REF." >&2
  echo "Run the Cpp2IL diffable-cs pass first (revenant prepare --only run-cpp2il; see CLAUDE.md)." >&2
  exit 1
fi

# Game-assembly filter (skip engine/third-party) unless --all. One python call
# returns the assembly names to seed.
if [ "$INCLUDE_ALL" = "1" ]; then
  mapfile -t ASMS < <(cd "$REF" && for d in */; do echo "${d%/}"; done)
else
  mapfile -t ASMS < <("$PY" - "$REF" <<'PY'
import os, sys
sys.path.insert(0, ".")
from revenant import config
ref = sys.argv[1]
for name in sorted(os.listdir(ref)):
    if os.path.isdir(os.path.join(ref, name)) and config.is_game_assembly(name):
        print(name)
PY
)
fi

# clonefile (cp -c) if the volume supports it, else a plain copy (independent
# files, just not block-shared).
CLONE="-c"
_probe="$(find "$REF" -name '*.cs' 2>/dev/null | head -1 || true)"
if [ -n "$_probe" ] && ! cp -c "$_probe" "/tmp/.seedsrc_probe.$$" 2>/dev/null; then
  CLONE=""
  echo "Note: clonefile (cp -c) unsupported here; using a plain copy." >&2
fi
rm -f "/tmp/.seedsrc_probe.$$" 2>/dev/null || true

mkdir -p "$SRC"
for asm in "${ASMS[@]}"; do
  [ -d "$REF/$asm" ] || continue
  if [ ! -e "$SRC/$asm" ]; then
    cp $CLONE -R "$REF/$asm" "$SRC/$asm"          # whole-assembly recursive clone (fast)
  else
    while IFS= read -r -d '' f; do                # fill only missing files; keep edits
      rel="${f#"$REF"/}"; dst="$SRC/$rel"
      [ -e "$dst" ] && continue
      mkdir -p "$(dirname "$dst")"
      cp $CLONE "$f" "$dst"
    done < <(find "$REF/$asm" -name '*.cs' -print0)
  fi
done

total=$(find "$SRC" -name '*.cs' 2>/dev/null | wc -l | tr -d ' ')
echo "Seeded src/$VERSION/ : $total .cs across ${#ASMS[@]} assemblies (CoW clones; _refs left pristine)."
[ "$INCLUDE_ALL" = "1" ] || echo "Third-party/engine assemblies skipped (pass --all to include them)."
echo "Reconstruct in place; originals stay at $REF for reference."
