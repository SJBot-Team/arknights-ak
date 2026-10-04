---
description: Map a subsystem's structure into a notes/ document
argument-hint: <topic-or-namespace>
---
Map the `$ARGUMENTS` subsystem of this IL2CPP target structurally (no deep decompilation yet). Follow the `re` skill. This is you driving: pick the terms, read the results, decide what is load-bearing.

1. `re_search` for the relevant class/method names around `$ARGUMENTS` (try several terms).
2. For the key types, `re_type_info` to get fields (offsets), base classes, and method lists.
3. Use `re_xrefs` / `re_callgraph` on a few central methods to see how the pieces connect.
4. Synthesize a structural map: class hierarchy, key fields/types, data flow, and which methods look load-bearing (candidates for `/re-deep`).
5. Write to `notes/<arch|core>-NN-<slug>.md` following the doc template (overview, key-files table with Stub/Verified status, numbered sections, a Mermaid diagram, a data-sources section).

Mark each claim's evidence tier in brackets on the same line as its citation; `{{tier:structural}}` is expected here. Do not claim behavior you have not read in assembly.
