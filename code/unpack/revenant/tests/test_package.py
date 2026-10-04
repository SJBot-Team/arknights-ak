"""Package smoke tests: import hygiene, the init scaffolder, and the
dependency-free Lua/decode primitives. Run: uv run --extra dev pytest"""
from __future__ import annotations

import json
import os
import re as _stdlib_re


def test_import_does_not_shadow_stdlib_re():
    # `mcp` is an optional extra, so a dev-only environment legitimately lacks
    # it. Importing unconditionally made this fail on any clean checkout that
    # had not installed the harness extra -- an environment gap reported as a
    # code failure.
    import pytest
    pytest.importorskip("mcp")
    import revenant.mcp_server  # noqa: F401
    import re
    assert re.compile(r"\d+").search("a12b").group() == "12"
    assert _stdlib_re.sub("x", "y", "axb") == "ayb"


def test_init_scaffolds_a_project(tmp_path):
    from revenant.init import init_project
    target = tmp_path / "game-x"
    rc = init_project(str(target), quiet=True)
    assert rc == 0
    for rel in [
        "revenant.toml", ".mcp.json", "CLAUDE.md", ".gitignore",
        ".claude/settings.json", ".claude/skills/re/SKILL.md",
        ".claude/commands/re-deep.md",
        "_apks/.gitkeep", "lua/.gitkeep", "src/.gitkeep",
    ]:
        assert (target / rel).exists(), rel
    # The read-only `re` tools are auto-allowed so RE work isn't a prompt storm.
    settings = json.loads((target / ".claude/settings.json").read_text())
    assert "mcp__re" in settings["permissions"]["allow"]
    # .mcp.json launches this interpreter's revenant.mcp_server.
    mcp = json.loads((target / ".mcp.json").read_text())
    assert mcp["mcpServers"]["re"]["args"] == ["-m", "revenant.mcp_server"]


def test_project_root_resolves_from_marker(tmp_path, monkeypatch):
    from revenant.init import init_project
    from revenant import config
    init_project(str(tmp_path / "proj"), quiet=True)
    sub = tmp_path / "proj" / "notes"
    monkeypatch.chdir(sub)
    config._PROJECT_CONFIG_CACHE.clear()
    assert config.workspace_root() == str(tmp_path / "proj")


def test_lua_decode_primitives():
    from revenant import lua
    # XOR is symmetric (explicit key; package has no project-configured key).
    key = b"abc123"
    data = bytes(range(256)) * 2
    assert lua.decrypt(lua.decrypt(data, key), key) == data
    # luafilepack unpack roundtrip.
    import struct
    entries = {"A.B": b"\x1bLuaS_x", "C": b"\x1bLuaS_yy"}
    blob = struct.pack("<i", len(entries))
    for n, d in entries.items():
        nb = n.encode()
        blob += struct.pack("<h", len(nb)) + nb + struct.pack("<i", len(d)) + d
    assert lua.unpack(blob) == entries


def test_lua_normalize_uses_configured_size_t():
    from revenant import lua
    chunk = (b"\x1bLuaS\x01" + b"\x19\x93\r\n\x1a\n" + b"\x04\x04\x08\x08"
             + b"\x78\x56\x00\x00\x00\x00\x00\x00"
             + b"\x00\x00\x00\x00\x00\x28\x77\x40" + b"BODY")
    norm = lua.normalize_luac(chunk)
    assert norm[5] == 0x00
    # No project configured -> stock Lua 5.3 size_t = 8.
    assert norm[12:17] == b"\x04\x08\x04\x08\x08"
    assert norm.endswith(b"BODY")


def test_all_mcp_tools_are_readonly():
    import revenant
    src = open(os.path.join(os.path.dirname(revenant.__file__), "mcp_server.py"),
               encoding="utf-8").read()
    decorators = _stdlib_re.findall(r"@mcp\.tool\([^)]*\)", src)
    assert decorators
    assert not [d for d in decorators if "annotations=RO" not in d]


def test_mcp_server_reexports_the_same_reports_not_its_own_logic():
    """The MCP surface is a thin shell over the same functions the CLI calls.

    Testing it separately would be testing one thing twice; asserting it is
    genuinely the same callable is what keeps that true.
    """
    import pytest
    pytest.importorskip("mcp")
    from revenant import mcp_server, reports, image
    assert mcp_server.image_arch is image.image_arch
    for name in ("find_asm_by_rva", "slice_method"):
        assert hasattr(reports, name)
