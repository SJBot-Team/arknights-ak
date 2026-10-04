"""Read a Lua table constructor as data.

Two of the nine titles keep their config as Lua tables rather than JSON or a
binary blob, and `lua-extract` has already decompiled them into readable
source. What was missing was the last step: reading one of those files as rows
and fields, so `table list` and `table census` say the same thing on nine
titles instead of seven.

Not a Lua interpreter and not a Lua parser. It reads one **table constructor**
-- the literal a config file is -- and the values that appear inside one:
tables, strings (both quote forms and the `[[long]]` form), numbers, booleans
and `nil`. Anything else is an error rather than a skip: a module returning
functions is not a config table, and quietly dropping what could not be read
would report it as one with fewer columns.

Nothing here knows a directory, a file name or a field name, so nothing here is
a game fact (`docs/adr/0004-what-qualifies-to-move-into-revenant.md`).
"""

from __future__ import annotations

import re

# A constructor nested this deep is not config. The limit exists so a
# pathological file is an error rather than a blown stack.
MAX_DEPTH = 64

_WS = re.compile(r"[ \t\r\n]+")
_NAME = re.compile(r"[A-Za-z_]\w*")
_NUMBER = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|\d+\.\d*(?:[eE][-+]?\d+)?|"
                     r"\.\d+(?:[eE][-+]?\d+)?|\d+(?:[eE][-+]?\d+)?)")
_LONG_OPEN = re.compile(r"\[(=*)\[")


class LuaError(Exception):
    """A Lua source file is not a table constructor, or holds what we cannot read."""


def parse(text: str):
    """The table this file **returns**, as a dict.

    Lua tables are one type with an array part and a hash part, so both come
    back as a dict: the array part keyed 1..n, exactly as Lua numbers it. A
    caller wanting rows takes the values; keeping the keys is what lets an
    id-keyed config say what its ids were.

    The table is the one the file returns, not the first one it writes. A file
    that defines `Defaults` and then `Config` and returns `Config` used to come
    back as `Defaults` -- one row instead of two hundred, with nothing saying
    so. A confident wrong number is the worst answer available here.
    """
    if _CODE.search(_strip(text)):
        raise LuaError("this file defines functions or requires other modules; "
                       "it is Lua source, not a Lua config table")
    at = _returned_constructor(text)
    value, after = _table(text, at, 0)
    after = _skip(text, after)
    if after < len(text) and not _RETURNS_NAME.match(text, after):
        raise LuaError(f"trailing code after the table at offset {after}: "
                       f"{text[after:after + 30]!r}")
    return value


_RETURN = re.compile(r"\breturn\b")
_RETURNS_NAME = re.compile(r"return\s+[A-Za-z_]\w*\s*;?\s*$")
# `function` or `require` anywhere outside strings and comments means the file
# is code. A config table holds values; a module holds behaviour, and reading
# the first literal in one would report a class's constant as its rows.
_CODE = re.compile(r"\b(?:function|require)\b")


def _strip(text: str) -> str:
    """`text` with strings and comments blanked, so keyword scans cannot lie."""
    out, at = [], 0
    while at < len(text):
        char = text[at]
        if char in "\"'":
            try:
                _, end = _string(text, at)
            except LuaError:
                break
            out.append(" " * (end - at))
            at = end
            continue
        if text.startswith("--", at) or _LONG_OPEN.match(text, at):
            end = _skip(text, at) if text.startswith("--", at) else None
            if end is None:
                try:
                    _, end = _long_string(text, at)
                except LuaError:
                    break
            out.append(" " * (end - at))
            at = end
            continue
        out.append(char)
        at += 1
    return "".join(out)


def _returned_constructor(text: str) -> int:
    """Where the constructor the file returns begins.

    Two shapes come out of the decompilers: `return { ... }` directly, and
    `local X = { ... }` with `return X` at the end. The second is why the first
    `{` in the file is the wrong anchor -- there may be several locals and only
    one of them is returned.
    """
    blanked = _strip(text)
    last = None
    for match in _RETURN.finditer(blanked):
        last = match
    if last is None:
        raise LuaError("this file returns nothing; it is not a Lua config table")
    at = _skip(text, last.end())
    if at < len(text) and text[at] == "{":
        return at
    name = _NAME.match(text, at)
    if not name:
        raise LuaError(f"`return` is followed by {text[at:at + 20]!r}, which is "
                       f"neither a table nor a name")
    wanted = name.group(0)
    assign = re.compile(r"(?:\blocal\s+)?\b" + re.escape(wanted) + r"\s*=\s*\{")
    found = None
    for match in assign.finditer(blanked, 0, last.start()):
        found = match
    if found is None:
        raise LuaError(f"this file returns {wanted!r}, and nothing here assigns "
                       f"a table to it")
    return found.end() - 1


def _skip(text: str, at: int) -> int:
    """Past whitespace and comments, both the line form and the long form."""
    while at < len(text):
        match = _WS.match(text, at)
        if match:
            at = match.end()
            continue
        if text.startswith("--", at):
            long_open = _LONG_OPEN.match(text, at + 2)
            if long_open:
                _, at = _long_string(text, at + 2)
                continue
            end = text.find("\n", at)
            at = len(text) if end < 0 else end + 1
            continue
        return at
    return at


def _long_string(text: str, at: int):
    """`[[ ... ]]` / `[=[ ... ]=]`, returning its body and the position after."""
    open_match = _LONG_OPEN.match(text, at)
    if not open_match:
        raise LuaError(f"expected a long bracket at offset {at}")
    close = "]" + open_match.group(1) + "]"
    start = open_match.end()
    # Lua drops a newline immediately after the opening bracket.
    if text.startswith("\n", start):
        start += 1
    end = text.find(close, start)
    if end < 0:
        raise LuaError("unterminated long bracket")
    return text[start:end], end + len(close)


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b",
            "f": "\f", "v": "\v", "\\": "\\", '"': '"', "'": "'", "\n": "\n"}


def _string(text: str, at: int):
    quote = text[at]
    out, at = [], at + 1
    while at < len(text):
        char = text[at]
        if char == quote:
            return "".join(out), at + 1
        if char == "\\":
            at += 1
            if at >= len(text):
                break
            nxt = text[at]
            if nxt in _ESCAPES:
                out.append(_ESCAPES[nxt])
                at += 1
                continue
            if nxt == "z":                       # \z skips the whitespace after it
                at += 1
                while at < len(text) and text[at] in " \t\r\n":
                    at += 1
                continue
            if nxt.isdigit():                    # \ddd, one byte, so at most 255
                digits = re.match(r"\d{1,3}", text[at:]).group(0)   # type: ignore[union-attr]
                code = int(digits)
                if code > 255:
                    raise LuaError(f"escape \\{digits} is out of range; Lua "
                                   f"decimal escapes are one byte")
                out.append(chr(code))
                at += len(digits)
                continue
            if nxt in "xX":
                hexits = re.match(r"[0-9a-fA-F]{1,2}", text[at + 1:])
                if hexits:
                    out.append(chr(int(hexits.group(0), 16)))
                    at += 1 + len(hexits.group(0))
                    continue
            raise LuaError(f"unknown escape \\{nxt!r} at offset {at}")
        out.append(char)
        at += 1
    raise LuaError("unterminated string")


def _number(token: str):
    if token[:2].lower() == "0x" or token[:3].lower() in ("-0x",):
        return int(token, 16)
    if any(c in token for c in ".eE"):
        return float(token)
    return int(token)


def _value(text: str, at: int, depth: int):
    at = _skip(text, at)
    if at >= len(text):
        raise LuaError("the file ends in the middle of a table")
    char = text[at]
    if char == "{":
        return _table(text, at, depth + 1)
    if char in "\"'":
        return _string(text, at)
    if _LONG_OPEN.match(text, at):
        return _long_string(text, at)
    number = _NUMBER.match(text, at)
    if number:
        return _number(number.group(0)), number.end()
    name = _NAME.match(text, at)
    if name:
        word = name.group(0)
        if word in ("true", "false"):
            return word == "true", name.end()
        if word == "nil":
            return None, name.end()
        # `function`, a call, a concatenation, a reference to another module:
        # all of them mean this is code rather than data, and a parser that
        # skipped them would hand back a table with columns missing and no
        # sign that anything was left out.
        raise LuaError(f"{word!r} at offset {at} is not a value this reads; "
                       f"a table holding {word} is code, not config")
    raise LuaError(f"cannot read a value at offset {at}: {text[at:at + 20]!r}")


def _table(text: str, at: int, depth: int):
    if depth > MAX_DEPTH:
        raise LuaError(f"tables nested deeper than {MAX_DEPTH}")
    if text[at] != "{":
        raise LuaError(f"expected a table at offset {at}")
    at = _skip(text, at + 1)
    out: dict = {}
    index = 0
    while True:
        if at >= len(text):
            raise LuaError("unterminated table constructor")
        if text[at] == "}":
            return out, at + 1
        key = None
        if text[at] == "[":
            key, at = _value(text, at + 1, depth)
            at = _skip(text, at)
            if at >= len(text) or text[at] != "]":
                raise LuaError(f"expected ']' at offset {at}")
            at = _skip(text, at + 1)
            if at >= len(text) or text[at] != "=":
                raise LuaError(f"expected '=' after a key at offset {at}")
            at = _skip(text, at + 1)
        else:
            name = _NAME.match(text, at)
            after = _skip(text, name.end()) if name else at
            if name and after < len(text) and text[after] == "=" and \
                    text[after:after + 2] != "==":
                key = name.group(0)
                at = _skip(text, after + 1)
        value, at = _value(text, at, depth)
        if key is None:
            index += 1
            key = index
        elif isinstance(key, bool):
            # Lua allows it; Python does not keep it separate. `True == 1`, so
            # `{ 5, [true] = 9 }` would silently overwrite the first array
            # element -- a row lost with nothing saying so.
            raise LuaError(f"a boolean key at offset {at} cannot be read: it "
                           f"would collide with the array part")
        # `nil` removes a key in Lua rather than storing one, so an explicit
        # nil is an absent field, not a field whose value is None.
        if value is not None:
            if key in out:
                raise LuaError(f"key {key!r} appears twice; the later one would "
                               f"silently replace the earlier and the row count "
                               f"would be short")
            out[key] = value
        at = _skip(text, at)
        if at < len(text) and text[at] in ",;":
            at = _skip(text, at + 1)
        elif at < len(text) and text[at] != "}":
            raise LuaError(f"expected ',' or '}}' at offset {at}")
