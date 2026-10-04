"""Revenant -- a reverse-engineering harness that brings dead binaries back to
source. Unity IL2CPP (ARM64 / ARM32 / Thumb, auto-detected) + xLua game logic,
driven by a coding agent through a read-only MCP server.

`revenant init <dir>` scaffolds a new RE project; the toolkit then operates on
that project (resolved from the cwd / the revenant.toml marker). Submodules are
imported lazily by the CLI and MCP server, so `init` stays light and the
optional `assets`/`harness` extras are only needed for the steps that use them.

Submodules: config, binary, assets, image, disasm, metadata, indices, indexer,
csharp, fields, xrefs, search, reports, cfg, lua, bridge, cli, mcp_server, init.
"""

__version__ = "0.1.0"
