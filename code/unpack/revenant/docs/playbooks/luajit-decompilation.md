# Decompiling LuaJIT bytecode

Verified on: Hollywood Merge (3,607 of 3,608 CDN-delivered chunks decompiled).

A ToLua# / LuaJIT title ships its scripts as LuaJIT bytecode, not stock Lua.
The magic is `1B 4C 4A` (`\x1bLJ`); flag `0x08` means FR2/GC64. `unluac` cannot
read it. `luajit-decompiler-v2` can, but upstream
(marsinator358/luajit-decompiler-v2) is Windows-only, so it has to be ported and
built once, then pointed at with `$REVENANT_LJD2`.

`revenant lua-extract` / `revenant.lua.decompile` route any `\x1bLJ` chunk to
that binary automatically; without `$REVENANT_LJD2` set they report the chunk is
LuaJIT and stop, rather than mis-decoding it as stock Lua.

## macOS / POSIX build

From a fresh upstream clone, add a `win_compat.h` shim implementing the handful
of Win32 file/console calls the tool uses (`CreateFileA`, `ReadFile`,
`FindFirstFileA`, `GetStdHandle`, …), then:

- `main.h`: replace `<windows.h>/<conio.h>/<fileapi.h>/<shlwapi.h>` with
  `"win_compat.h"`; drop the `_CHAR_UNSIGNED` `#error` and the MSVC `#pragma`
  lines; fix `\` include separators.
- `ast.h`: make the `Local` / `SlotScope` forward declarations `public`, keep
  `ConditionBuilder` `private` (match their definition sites).
- Strip nested-type extra-qualification (`class Bytecode::X {` → `class X {`).
- `main.cpp`: remove the DPI / console-window / file-dialog GUI blocks
  (command-line only).

Then:

    clang++ -std=c++20 -funsigned-char -fms-extensions -O2 -w \
      main.cpp bytecode/bytecode.cpp bytecode/prototype.cpp \
      ast/ast.cpp lua/lua.cpp -o ljd2

## Use

    export REVENANT_LJD2=/path/to/ljd2
    revenant lua-extract          # \x1bLJ chunks now decompile through ljd2

Directly: `ljd2 <input_file_or_dir> -f -s -o <output_dir>/` (`-f` force
overwrite, `-s` silent — skip chunks that fail an assertion; on Hollywood Merge
that was 1 of 3,608).

## Where the bytecode comes from

Often the CDN, not the package — a title can put the *same* xLua/LuaJIT scheme
either in the package (recoverable statically) or entirely on the CDN
(statically zero). That is a packaging choice, not a technology one; the
download URL template is a per-game fact and stays in that game's notes.
