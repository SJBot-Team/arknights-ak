---
description: Re-verify a reconstructed method against the binary
argument-hint: <Namespace.Class.Method> [rva]
---
Verify the already-reconstructed method `$1` (optional RVA `$2`) against the assembly. Follow the `re` skill. Call `re_status` first for the `<version>`.

1. Read the method's current body in `src/<version>/...`.
2. Resolve the RVA (`$2`, or `re_search` / the class `.cs` `[Address]`).
3. `re_find_asm(rva)` for the ISIL ground truth; for field reads/writes cross-check with `re_field_scan` on the relevant offsets.
4. Compare line by line. A claim keeps `{{tier:disassembly}}` only if you can point at the instruction; a claim you can support from stubs and metadata but not from an instruction drops to `{{tier:managed_code}}`; anything else is `{{tier:structural}}` or comes out.

Report: discrepancies found (if any), corrections applied to `src/`, and which claims changed tier.
