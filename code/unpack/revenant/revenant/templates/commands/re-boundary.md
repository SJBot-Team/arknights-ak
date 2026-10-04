---
description: Map a game's content boundary into a notes/ document (six sections)
argument-hint: <optional focus>
---
Map this title's **content boundary** — what ships in the package versus what the server delivers at runtime — into one note. Follow the `re` skill. This is you driving: read the package, decide what is bundled and what is remote. It does not run `scan` and does not build a ledger; it is a six-section outline, human-filled.

Write `notes/core-NN-content-delivery.md` with these six sections, in order:

1. **代码热更机制** — none / HybridCLR / IFix / xLua / ToLua# / other. Give the evidence (a marker string or a file path, not just the verdict). Where does the code come from: bundled (package path + size) / server-delivered (URL or domain) / both. If server-delivered, at what granularity (whole assembly / single patch / single script). `revenant fingerprint` lists the markers and the `*.bytes` literals to start from.
2. **资源与配置下发机制** — Addressables / YooAsset / custom / none. Catalog/manifest filename, format, in-package path. CDN domain and path template (read from the string table or config — do **not** make network requests). How the version is chosen. Any A/B or grayscale override packs.
3. **内容边界清单** — the core table: for 玩法代码 / 数值配置表 / 合成链掉率 / 活动配置 / 本地化 / UI 预制体 / 美术资源, mark each 随包 / 下发 / 混合 with evidence, quantified where possible.
4. **缺口评估** — how much of the game static reversing covers, and whether each gap is a *numbers* gap (values you cannot read) or a *structure* gap (you do not even know what content exists).
5. **获取路径** — feasibility only, do not execute: what it would take to close a gap (packet capture / process memory / device cache / CDN), and each path's preconditions. **No network requests, no capture in this pass.**
6. **与其他游戏的对照** — how this title's mechanism resembles or differs from others already mapped, especially same-origin pairs.

Every claim carries a bracketed tier on the same line as its evidence — `{{tier:disassembly}}`, `{{tier:managed_code}}`, `{{tier:structural}}`. Include a `## 数据来源` section and a `## 复现命令` section, then run `revenant lint`.
