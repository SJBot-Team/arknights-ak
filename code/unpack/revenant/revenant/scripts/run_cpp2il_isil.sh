#!/usr/bin/env bash
# run_cpp2il_isil.sh — Run Cpp2IL ISIL dump for the extracted IL2CPP binary.
#
# Usage:
#   tools/run_cpp2il_isil.sh [version] [unity_version]
#     version        default: auto-detected from the XAPK manifest
#     unity_version  default: auto-detected from globalgamemanagers
#   (override via args or $REVENANT_VERSION / $UNITY_VERSION). Game-agnostic.
#
# Discovers libil2cpp.so + global-metadata.dat from _binaries/ (populate first
# with `revenant find-binary` / `find-metadata`). Output goes to
# _refs/<version>/cpp2il_out/. Cpp2IL is taken from $CPP2IL, the self-contained
# publish build, then PATH (each validated with --version).
set -euo pipefail

ROOT="$(cd "${REVENANT_PROJECT:-$(pwd)}" && pwd)"
cd "$ROOT"

# Auto-detect identity from the package using the project's own config module.
PY="${REVENANT_PY:-python3}"
_detect() { "$PY" -c "from revenant import config; print(config.$1())" 2>/dev/null || true; }

VERSION="${1:-${REVENANT_VERSION:-$(_detect detect_version)}}"
VERSION="${VERSION:-0.0.0}"
UNITY_VERSION="${2:-${UNITY_VERSION:-$(_detect detect_unity_version)}}"
UNITY_VERSION="${UNITY_VERSION:-2022.3.0f1}"

# ── Locate Cpp2IL ───────────────────────────────────────────────────────────
# Validate each candidate with `--version`: PATH apphosts (/usr/local/bin/Cpp2IL)
# may be dotnet launchers missing Cpp2IL.dll, so a plain existence check is not
# enough. $CPP2IL points straight at a binary and always wins; $CPP2IL_DIR is a
# publish dir to probe (defaults to a local checkout).
#
# Among the probed publish builds, take the NEWEST working one rather than a
# fixed preference order. A publish dir accumulates builds, and an old
# self-contained build sitting next to a fresh one silently wins a static
# ordering -- which is how a months-old Cpp2IL kept crashing on a bug that had
# already been fixed upstream. Report the version so the log says which build
# produced the dump.
CPP2IL_DIR="${CPP2IL_DIR:-$HOME/workspace/playground/Cpp2IL/publish}"
CPP2IL_BIN=""
_cpp2il_works() { [ -x "$1" ] && "$1" --version >/dev/null 2>&1; }

for cand in "${CPP2IL:-}" \
            "$(command -v Cpp2IL 2>/dev/null || true)" \
            "$(command -v cpp2il 2>/dev/null || true)" ; do
  [ -n "$cand" ] || continue
  if _cpp2il_works "$cand"; then CPP2IL_BIN="$cand"; break; fi
done

if [ -z "$CPP2IL_BIN" ] && [ -d "$CPP2IL_DIR" ]; then
  # Newest first (mtime), so a rebuild is picked up without touching this script.
  while IFS= read -r cand; do
    if _cpp2il_works "$cand"; then CPP2IL_BIN="$cand"; break; fi
  done < <(find "$CPP2IL_DIR" -maxdepth 2 -name Cpp2IL -type f -perm -u+x -exec stat -f "%m %N" {} + 2>/dev/null \
             | sort -rn | cut -d' ' -f2-)
fi

if [ -z "$CPP2IL_BIN" ]; then
  echo "Error: no working Cpp2IL found (set \$CPP2IL to a binary whose --version succeeds)." >&2
  exit 1
fi
CPP2IL_VERSION="$("$CPP2IL_BIN" --version 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | grep -i '^Version' | head -1)"

# ── Discover binaries (extracted into _binaries/ by revenant) ────────────────
# An analysis copy (revenant patch-binary) wins outright: it exists precisely
# because the packaged binary defeats Cpp2IL's ELF parsing. Otherwise take the
# newest — find-binary re-extracts the packaged copy on every run, and picking
# alphabetically silently reintroduces the file you just replaced.
BIN="$(ls -1t _binaries/*-libil2cpp.analysis.so 2>/dev/null | head -1 || true)"
[ -n "$BIN" ] || BIN="$(ls -1t _binaries/*-libil2cpp.so 2>/dev/null | head -1 || true)"
META="$(ls -1t _binaries/*-global-metadata.dat 2>/dev/null | head -1 || true)"
if [ -z "$BIN" ] || [ -z "$META" ]; then
  echo "Error: missing _binaries/*-libil2cpp.so or *-global-metadata.dat." >&2
  echo "Run first: revenant find-binary && revenant find-metadata" >&2
  exit 1
fi

REF_DIR="${REVENANT_REF_DIR:-_refs/$VERSION}"
OUT="$REF_DIR/cpp2il_out"
mkdir -p "$OUT"
LOG="$REF_DIR/cpp2il.log"

echo "Cpp2IL:   $CPP2IL_BIN  ${CPP2IL_VERSION:-(version unknown)}"
echo "binary:   $BIN"
echo "metadata: $META"
echo "unity:    $UNITY_VERSION"
echo "output:   $OUT  (log: $LOG)"

export DOTNET_BUNDLE_EXTRACT_BASE_DIR=/tmp/dotnet-extract
: > "$LOG"

# RESOURCE FLOOR: the ISIL pass peaks around 15.7 GB RSS on a ~100 MB binary
# (#10, measured on both an ELF and a Mach-O -- it is a function of binary size,
# not of format). A machine with less RAM will thrash or be OOM-killed here.
#
# Two passes into the same output dir: ISIL (-> IsilDump/, the asm ground truth)
# and DiffableCs (-> DiffableCs/, the C# stubs seed-src and re_type_info read).
# $SERIAL_ENV forces single-threaded analysis: Cpp2IL fans method analysis out
# through PLINQ (MiscUtils.ExecuteParallel -> .AsParallel()), which on some
# binaries dies with a native AccessViolationException inside
# ISILControlFlowGraph's constructor -- a data race, not bad input. PLINQ takes
# its degree of parallelism from Environment.ProcessorCount, so pinning
# DOTNET_PROCESSOR_COUNT=1 serialises it without patching Cpp2IL. Slower, but a
# slow dump beats no dump.
SERIAL_ENV=""
_pass() {  # _pass <label> <cpp2il-args...>
  echo "  [$1] running${SERIAL_ENV:+ (single-threaded)}... (log: $LOG)"
  env $SERIAL_ENV "$CPP2IL_BIN" \
      --force-binary-path "$BIN" \
      --force-metadata-path "$META" \
      --force-unity-version "$UNITY_VERSION" \
      --output-to "$OUT" \
      "${@:2}" >> "$LOG" 2>&1 \
    || { echo "  [$1] FAILED -- see $LOG" >&2; return 1; }
}

rm -f "$OUT/.cpp2il-complete"   # a stale marker must not let prepare skip a redo
if ! _pass isil --output-as isil; then
  echo "  [isil] retrying single-threaded (Cpp2IL's parallel path crashed; see $LOG)" >&2
  SERIAL_ENV="DOTNET_PROCESSOR_COUNT=1"
  _pass isil --output-as isil || exit 1
fi
if [ "${REVENANT_SKIP_DIFFABLE:-0}" = "1" ]; then
  touch "$OUT/.cpp2il-complete"
  echo "Done: $OUT/IsilDump  (DiffableCs skipped)"
else
  # nativemethoddetector is OFF by default, on both platforms.
  #
  # It resolves raw bytes per native method and dies on addresses its own
  # mapping cannot reach. On a Mach-O that failure is expensive and late: #10
  # measured 2,530 s / 26.1 GB and then zero output, versus 39 s / 2.4 GB with
  # the layer dropped. Retrying after the throw means paying that first. And the
  # layer's benefit has never been measured -- it only annotates native methods,
  # and it has misbehaved on arm64 too. A layer with unknown benefit and a
  # 42-minute failure cost belongs off by default; ask for it explicitly.
  _diffable() { _pass diffable-cs --output-as diffable-cs "$@"; }
  LAYERS="attributeinjector,stablenamer"
  if [ "${CPP2IL_NATIVE_METHOD_DETECTOR:-0}" = "1" ]; then
    LAYERS="attributeinjector,nativemethoddetector,stablenamer"
    echo "  [diffable-cs] nativemethoddetector enabled by request" >&2
  fi
  if ! _diffable --use-processor "$LAYERS"; then
    echo "  [diffable-cs] retrying with no processing layers (a layer threw; see $LOG)" >&2
    _diffable || exit 1
  fi
  touch "$OUT/.cpp2il-complete"
  echo "Done: $OUT/IsilDump + $OUT/DiffableCs"
fi
