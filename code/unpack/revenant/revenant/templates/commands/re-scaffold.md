---
description: Create a src/ scaffold for an IL2CPP class from DiffableCs
argument-hint: <Namespace.Class>
---
Scaffold the class `$1` for this IL2CPP target. Follow the `re` skill scaffold gate. Call `re_status` first for the `<version>`.

1. `re_type_info($1)` → base class, fields (with offsets), method list, and the DiffableCs `.cs` path.
2. Read that `.cs` to get the method stubs and each `[Address(RVA=...)]`.
3. Write to `src/<version>/<Assembly>/<...>/<Class>.cs`: the namespace/class with its fields and all method stubs, plus a header line `// source: <version>`. Keep stub bodies; do not invent implementations. Do not keep a hand-counted progress tally in the file — what is verified is what carries a tier and a citation.

Report: the scaffold path, field count, method count, and the RVAs available for follow-up `/re-deep`.
