"""Domain packs, the probe executor, the ledger, and note lint.

Two seams: the probe executor directly (its accounting guarantee is a property
of the module, only indirectly visible from outside), and the CLI, asserting on
what lands in the ledger.
"""

from __future__ import annotations

import json
import os

import pytest

from revenant import cli as _cli
from revenant import ledger as _ledger
from revenant import lint as _lint
from revenant import pack as _pack
from revenant import probes as _probes
from revenant.methodology import (
    FACETS,
    STATE_ABSENT,
    STATE_INSUFFICIENT,
    STATE_MEETS,
    STATE_OUT_OF_REACH,
    CellId,
)


@pytest.fixture
def project(tmp_path, monkeypatch):
    from revenant.init import init_project
    root = tmp_path / "proj"
    init_project(str(root), quiet=True)
    monkeypatch.setenv("REVENANT_PROJECT", str(root))
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()
    config._IDENTITY_CACHE.clear()
    config.set_platform(None)
    yield root
    config._PROJECT_CONFIG_CACHE.clear()


def _enable(project_root, *names):
    text = (project_root / "revenant.toml").read_text()
    listed = ", ".join(f'"{n}"' for n in names)
    (project_root / "revenant.toml").write_text(f"{text}\n[packs]\nenabled = [{listed}]\n")
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()


def _write_overlay_pack(project_root, name, slot_id="X01", pattern=".*(Thing|Widget).*"):
    root = project_root / ".revenant" / "packs" / name
    (root / "slots").mkdir(parents=True, exist_ok=True)
    (root / "pack.yaml").write_text(f'name: {name}\nversion: "1"\n')
    (root / "slots" / f"{slot_id}.md").write_text(
        f"---\nid: {slot_id}\ntitle: overlay slot\n"
        f"probes:\n  - kind: class_regex\n    pattern: \"{pattern}\"\n---\n\nbody\n"
    )
    return root


def _packs(project_root):
    from revenant import config
    return _pack.discover(str(project_root), _pack.enabled_packs(config.project_config()))


# ── packs ───────────────────────────────────────────────────────────────────

def test_builtin_pack_is_resolved_not_copied(project):
    """Built-ins live with the installed package; a project holds only overrides."""
    packs = _pack.discover(str(project))
    assert "example" in packs
    assert not (project / ".revenant" / "packs" / "example").exists()


def test_trimming_removes_cells_but_cannot_add_a_seventh_facet(project):
    pk = _pack.discover(str(project))["example"]
    e01 = pk.slot("E01")
    assert not e01.spec("platform_differences").applicable
    assert len(e01.cells()) == len(FACETS) - 1
    assert {c.facet for c in pk.slot("E02").cells()} == set(FACETS)


def test_a_seventh_facet_is_rejected(project, tmp_path):
    root = tmp_path / "badpack"
    (root / "slots").mkdir(parents=True)
    (root / "pack.yaml").write_text('name: bad\n')
    (root / "slots" / "B1.md").write_text(
        "---\nid: B1\nfacets:\n  vibes:\n    applicable: true\n---\nbody\n")
    with pytest.raises(_pack.PackError, match="not one of the six facets"):
        _pack.load_pack(str(root))


def test_probes_must_be_patterns_not_exact_class_names(project, tmp_path):
    """The rule that keeps a pack reusable on the next game."""
    root = tmp_path / "exactpack"
    (root / "slots").mkdir(parents=True)
    (root / "pack.yaml").write_text('name: exact\n')
    (root / "slots" / "B1.md").write_text(
        '---\nid: B1\nprobes:\n  - kind: class_regex\n    pattern: "MergeBoardManager"\n---\nbody\n')
    with pytest.raises(_pack.PackError, match="exact name"):
        _pack.load_pack(str(root))


def test_unmet_requires_edge_is_reported_not_enforced(project):
    pk = _pack.discover(str(project))["example"]
    unmet = pk.unmet_requires(done=set())
    assert [e.src for e in unmet] == ["E01"]
    assert pk.unmet_requires(done={"E01"}) == []


def test_overlay_replaces_one_slot_not_the_whole_pack(project):
    """Overlay granularity is the slot: adding one must not fork the pack."""
    root = project / ".revenant" / "packs" / "example"
    (root / "slots").mkdir(parents=True)
    (root / "pack.yaml").write_text('name: example\nversion: "1"\n')
    (root / "slots" / "E03.md").write_text(
        '---\nid: E03\ntitle: project-specific slot\n'
        'probes:\n  - kind: class_regex\n    pattern: ".*Local.*"\n---\nbody\n')
    pk = _pack.discover(str(project))["example"]
    assert set(pk.slots) == {"E01", "E02", "E03"}
    assert pk.slot("E01").title == "这个游戏接了哪些第三方组件"   # built-in survives


# ── probe executor (the second seam) ────────────────────────────────────────

def _corpus(classes=(), methods=(), strings=()):
    return _probes.Corpus(
        kind="il2cpp", name="test",
        class_names=tuple(classes), method_names=tuple(methods), strings=tuple(strings),
    )


def test_a_zero_hit_probe_still_produces_a_record(project):
    """The single most droppable line in the whole design.

    "No results, nothing to write" is the natural implementation, and it deletes
    the only checkable way to tell "this game does not have it" from "nobody
    looked" -- 4 places in 110k lines of prior write-ups managed to record it by
    hand.
    """
    probe = _pack.Probe(kind="class_regex", pattern=".*Nothing.*")
    report = _probes.run_slot("S1", [probe], [_corpus(classes=("Foo", "Bar"))])
    assert len(report.runs) == 1
    run = report.runs[0]
    assert run.zero_hit and run.hit_count == 0
    assert run.pattern == ".*Nothing.*"          # what was searched survives
    assert report.zero_hit_runs == [run]


def test_hits_are_recorded_with_what_matched(project):
    probe = _pack.Probe(kind="class_regex", pattern=".*Manager$")
    report = _probes.run_slot("S1", [probe], [_corpus(classes=("AdManager", "Foo", "SdkManager"))])
    assert report.candidates() == ["AdManager", "SdkManager"]


def test_string_probes_match_metadata_literals(project):
    probe = _pack.Probe(kind="string_const", values=("media_source", "nope"))
    report = _probes.run_slot("S1", [probe], [_corpus(strings=("media_source", "other"))])
    assert report.candidates() == ["media_source"]


def test_method_probes_carry_their_owning_class(project):
    probe = _pack.Probe(kind="method_regex", pattern="TrackInstall")
    report = _probes.run_slot(
        "S1", [probe], [_corpus(methods=(("Attrib", "void TrackInstall()"),))])
    assert report.runs[0].hits[0].detail == "Attrib"


def test_adhoc_search_goes_through_the_same_executor_and_is_recorded(project):
    """An agent improvising must not open its own door.

    Ad-hoc retrieval is exactly where the accounting would otherwise develop
    holes, because that is where someone is exploring.
    """
    probe = _pack.Probe(kind="class_regex", pattern=".*Board.*")
    report = _probes.run_adhoc(probe, [_corpus(classes=("MergeBoard",))])
    assert report.runs[0].origin == "adhoc"
    assert report.runs[0].hit_count == 1


def test_probe_runs_are_reproducible(project):
    probe = _pack.Probe(kind="class_regex", pattern=".*Manager$")
    corpus = _corpus(classes=("AdManager", "Foo"))
    first = _probes.run_slot("S1", [probe], [corpus]).runs[0].to_json()
    second = _probes.run_slot("S1", [probe], [corpus]).runs[0].to_json()
    first.pop("ran_at"), second.pop("ran_at")
    assert first == second


def test_naming_statistics_feed_the_zero_hit_review(project):
    corpus = _corpus(classes=("MergeBoard", "MergeItem", "MergeCell", "Foo"))
    stats = dict(_probes.naming_statistics(corpus))
    assert stats["Merge"] == 3


# ── the ledger ──────────────────────────────────────────────────────────────

def _ledger_for(project):
    return _ledger.Ledger(pack="example", path=_ledger.ledger_path(str(project), "example"))


def test_ran_is_a_field_not_a_fifth_state(project):
    """"What we did" and "what we know" must stay separable.

    Fold them and the re-run logic loses the only thing it can key on.
    """
    led = _ledger_for(project)
    cid = CellId("example", "E01", "responsibility")
    led.mark_ran(cid, "hash1", "1.0@android")
    led.set_judgement(cid, state=STATE_ABSENT, tier="structural")
    entry = led.cell(cid)
    assert entry["ran"] is True and entry["state"] == STATE_ABSENT


def test_out_of_reach_must_say_which_side_the_gap_is_on(project):
    led = _ledger_for(project)
    cid = CellId("example", "E01", "data_model")
    with pytest.raises(_ledger.LedgerError, match="opposite remedies"):
        led.set_judgement(cid, state=STATE_OUT_OF_REACH)
    led.set_judgement(cid, state=STATE_OUT_OF_REACH, reach_source="input_missing")
    assert led.cell(cid)["reach_source"] == "input_missing"


def test_illegal_state_is_rejected(project):
    led = _ledger_for(project)
    with pytest.raises(_ledger.LedgerError, match="not a cell state"):
        led.set_judgement(CellId("example", "E01", "responsibility"), state="done")


def test_gap_marker_is_its_own_dimension(project):
    """A conclusion that holds, missing a number that lives on the server."""
    led = _ledger_for(project)
    cid = CellId("example", "E02", "data_model")
    led.set_judgement(cid, state=STATE_MEETS, tier="managed_code",
                      gap_markers=["server_side"])
    entry = led.cell(cid)
    assert entry["state"] == STATE_MEETS          # not downgraded
    assert entry["gap_markers"] == ["server_side"]


def test_unknown_gap_marker_warns_without_failing(project):
    led = _ledger_for(project)
    warnings = led.set_judgement(
        CellId("example", "E02", "data_model"), state=STATE_MEETS,
        tier="managed_code", gap_markers=["typoed_marker"])
    assert any("not one of the known" in w for w in warnings)


def test_tier_above_the_reachable_ceiling_warns(project):
    led = _ledger_for(project)
    warnings = led.set_judgement(
        CellId("example", "E02", "core_mechanism"), state=STATE_MEETS,
        tier="disassembly", ceiling="managed_code")
    assert any("reachable ceiling" in w for w in warnings)


def test_index_version_change_makes_every_cell_stale(project):
    led = _ledger_for(project)
    cells = [CellId("example", "E01", f) for f in FACETS]
    for cid in cells:
        led.mark_ran(cid, "hash1", "1.0@android")
    same = {str(c): ("hash1", "1.0@android") for c in cells}
    assert led.stale_cells(same) == []
    bumped = {str(c): ("hash1", "2.0@android") for c in cells}
    assert len(led.stale_cells(bumped)) == len(cells)


def test_changing_one_slots_probes_invalidates_only_that_slot(project):
    led = _ledger_for(project)
    for facet in FACETS:
        led.mark_ran(CellId("example", "E01", facet), "hashA", "1.0@android")
        led.mark_ran(CellId("example", "E02", facet), "hashB", "1.0@android")
    expected = {}
    for facet in FACETS:
        expected[str(CellId("example", "E01", facet))] = ("hashA-CHANGED", "1.0@android")
        expected[str(CellId("example", "E02", facet))] = ("hashB", "1.0@android")
    stale = led.stale_cells(expected)
    assert all("E01" in s for s in stale)
    assert len(stale) == len(FACETS)


def test_invalidation_clears_the_judgement_with_the_run(project):
    """A conclusion reached under probes that no longer exist is not an answer."""
    led = _ledger_for(project)
    cid = CellId("example", "E01", "responsibility")
    led.mark_ran(cid, "hashA", "1.0@android")
    led.set_judgement(cid, state=STATE_ABSENT, tier="structural")
    led.invalidate([cid])
    entry = led.cell(cid)
    assert entry["ran"] is False and entry["state"] == ""


def test_dead_ends_are_recorded_in_the_ledger(project):
    led = _ledger_for(project)
    led.record_dead_end("E01", "SomeUnrelatedManager", "handles audio, not ads")
    assert led.dead_ends[0]["candidate"] == "SomeUnrelatedManager"


def test_ledger_round_trips(project):
    led = _ledger_for(project)
    cid = CellId("example", "E01", "responsibility")
    led.mark_ran(cid, "h", "v")
    led.set_judgement(cid, state=STATE_MEETS, tier="structural")
    path = led.save()
    again = _ledger.Ledger.load(path)
    assert again.cell(cid)["state"] == STATE_MEETS
    assert again.cell(cid)["ran"] is True


# ── the guardrail ───────────────────────────────────────────────────────────

def test_deterministic_probe_run_writes_no_judgement_anywhere(project, monkeypatch):
    """The regression guard that matters more than any single case here.

    The previous generation of this tooling had a script write the completeness
    field, and 789 files ended up stamped "complete -- verified" by a regex that
    had never read an instruction. Code writes facts; judgements come through
    one validated door.
    """
    from revenant import cli
    _enable(project, "example")
    monkeypatch.chdir(project)
    assert cli.main(["probe", "example"]) == 0

    led = _ledger.Ledger.load(_ledger.ledger_path(str(project), "example"))
    assert _ledger.judgement_fields_written(led) == []
    assert led.cells, "the run must still have recorded facts"
    assert all(entry["ran"] for entry in led.cells.values())


def test_probe_command_records_zero_hits_on_an_empty_index(project, monkeypatch):
    from revenant import cli
    _enable(project, "example")
    monkeypatch.chdir(project)
    cli.main(["probe", "example"])
    led = _ledger.Ledger.load(_ledger.ledger_path(str(project), "example"))
    assert led.probe_runs, "probe runs must be recorded even with nothing to find"
    assert all(r["hit_count"] == 0 for r in led.probe_runs)


def test_coverage_is_reported_per_pack_never_merged(project, monkeypatch):
    from revenant import cli
    _write_overlay_pack(project, "second")
    _enable(project, "example", "second")
    monkeypatch.chdir(project)
    cli.main(["probe", "example"])
    cli.main(["probe", "second"])

    directory = _ledger.ledger_dir(str(project))
    names = sorted(n for n in os.listdir(directory) if n.endswith(".json"))
    assert names == ["example.json", "second.json"], "one ledger per pack, not one total"


# ── lint ────────────────────────────────────────────────────────────────────

def _note(project, name, text):
    notes = project / "notes"
    notes.mkdir(exist_ok=True)
    path = notes / name
    path.write_text(text, encoding="utf-8")
    return str(path)


DATA_SOURCES = "\n## 数据来源\n\n- IsilDump\n"


def test_a_tier_with_no_source_at_all_is_an_error(project):
    path = _note(project, "arch-01-x.md", "# X\n\n- 这条结论 [反汇编坐实] 没有任何出处\n" + DATA_SOURCES)
    report = _lint.lint_notes([path])
    assert any(f.rule == "tier-without-source" for f in report.errors)


def test_a_tier_citing_an_rva_passes_the_source_rule(project):
    path = _note(project, "arch-02-x.md", "# X\n\n- 结论 [反汇编坐实] 见 0x1234ABCD\n" + DATA_SOURCES)
    report = _lint.lint_notes([path])
    assert not any(f.rule == "tier-without-source" for f in report.findings)


def test_a_pure_adjudication_note_is_compliant(project):
    """Whole documents in the corpus cite sibling notes and nothing else.

    Calling those non-compliant would be wrong; the only illegal shape is a
    claim with no source at all.
    """
    path = _note(
        project, "arch-11-compare.md",
        "# 对比\n\n- 判定 [结构推断] 依据见 arch-09 §3.2\n- 另一条 [托管代码坐实] 见 arch-10 §四\n"
        + DATA_SOURCES)
    report = _lint.lint_notes([path])
    assert not report.errors, [f.message for f in report.errors]


def test_missing_data_sources_section_is_an_error(project):
    path = _note(project, "arch-03-x.md", "# X\n\n- 结论 [结构推断] 见 arch-09\n")
    report = _lint.lint_notes([path])
    assert any(f.rule == "data-sources" for f in report.errors)


def test_shuffled_headings_are_not_an_error(project):
    """Checking section names is checking form; only the anchor is required."""
    path = _note(
        project, "arch-04-x.md",
        "# X\n\n## 数据来源\n- IsilDump\n\n## 概述\n\n## 分析\n- 结论 [结构推断] 见 arch-09\n")
    report = _lint.lint_notes([path])
    assert not report.errors


def test_unknown_rva_is_flagged_when_an_index_is_loaded(project):
    from revenant import indices
    indices.VERSIONS["t"] = indices.VersionData(
        root="", rva_index={"1234abcd": {"class": "Foo", "signature": "void Bar()"}})
    try:
        path = _note(project, "arch-05-x.md", "# X\n\n- 结论 [反汇编坐实] 见 0xDEADBEEF\n" + DATA_SOURCES)
        report = _lint.lint_notes([path], version="t")
        assert any(f.rule == "rva-not-found" for f in report.errors)

        ok = _note(project, "arch-06-x.md", "# X\n\n- 结论 [反汇编坐实] 见 0x1234ABCD\n" + DATA_SOURCES)
        report = _lint.lint_notes([ok], version="t")
        assert not any(f.rule == "rva-not-found" for f in report.errors)
    finally:
        indices.VERSIONS.pop("t", None)


def test_lint_reports_but_does_not_block(project, monkeypatch):
    from revenant import cli
    _note(project, "arch-07-bad.md", "# X\n\n- 结论 [反汇编坐实] 没有出处\n")
    monkeypatch.chdir(project)
    assert cli.main(["lint"]) == 0, "lint reports; it is not a gate"


def test_no_index_is_reported_as_our_gap_not_the_authors(project):
    path = _note(project, "arch-08-x.md", "# X\n\n- 结论 [反汇编坐实] 见 0xDEADBEEF\n" + DATA_SOURCES)
    report = _lint.lint_notes([path], version="nonexistent")
    assert any(f.rule == "no-index" for f in report.warnings)
    assert not any(f.rule == "rva-not-found" for f in report.findings)


def test_rescanning_replaces_probe_records_instead_of_stacking_them(project, monkeypatch):
    """The ledger is state, not an ever-growing log.

    Ad-hoc attempts do append -- those are a record of what somebody tried.
    """
    from revenant import cli
    _enable(project, "example")
    monkeypatch.chdir(project)
    cli.main(["probe", "example"])
    first = len(_ledger.Ledger.load(_ledger.ledger_path(str(project), "example")).probe_runs)
    cli.main(["probe", "example"])
    cli.main(["probe", "example"])
    after = len(_ledger.Ledger.load(_ledger.ledger_path(str(project), "example")).probe_runs)
    assert after == first, "re-scanning must not multiply the record"


def test_adhoc_attempts_do_accumulate(project):
    led = _ledger_for(project)
    probe = _pack.Probe(kind="class_regex", pattern=".*Board.*")
    for _ in range(3):
        for run in _probes.run_adhoc(probe, [_corpus(classes=("MergeBoard",))]).runs:
            led.record_probe_run(run)
    assert len(led.probe_runs) == 3


# ── lint: the vocabulary real notes actually use (#29) ──────────────────────
#
# 27 real notes produced 23 findings and every one was the lint not recognising
# the note: `## 来源` instead of `## 数据来源`, `[Lua坐实]` instead of
# `[脚本源码坐实]`, a bare `T1` in a table cell. These pin what is accepted.

def _findings(report, rule):
    return [f for f in report.findings if f.rule == rule]


@pytest.mark.parametrize("heading", ["## 来源", "## 数据来源", "## 证据索引", "## 技术参考", "## Sources"])
def test_every_real_spelling_of_the_sources_heading_is_accepted(project, heading):
    path = _note(project, "arch-20-x.md", f"# X\n\n- 结论 [结构推断] 见 arch-09\n\n{heading}\n\n- Lua\n")
    assert not _findings(_lint.lint_notes([path]), "data-sources")


def test_method_named_aliases_resolve_to_the_four_tiers(project):
    """`[Lua坐实]` citing a Lua file is a script-source claim with its source."""
    from revenant.methodology import TIER_ALIASES, resolve_tier, TIER_SCRIPT_SOURCE
    assert resolve_tier("Lua坐实") == TIER_SCRIPT_SOURCE
    assert resolve_tier("原生T1") and resolve_tier("C#签名") and resolve_tier("DEX普查")
    assert set(TIER_ALIASES.values()) <= set(_lint.TIERS)

    path = _note(
        project, "arch-21-x.md",
        "# X\n\n- 渠道标识被解析带入登录。[Lua坐实] `OperManager.lua:56-65`。\n"
        "- 计费客户端 [原生T1] `MFBillingClient` 调用图核实。\n"
        "- ASAA 命名像归因但实际走年龄门。[C#签名 + 待验证] `ASAAManager.cs:16-63`。\n"
        + DATA_SOURCES)
    report = _lint.lint_notes([path])
    assert not report.errors, [f.message for f in report.errors]


def test_an_unknown_spelling_is_reported_with_the_accepted_ones(project):
    path = _note(project, "arch-22-x.md", "# X\n\n- 结论 [原生T2] `Foo.cs:1`\n- 猜的（T4）。\n" + DATA_SOURCES)
    unknown = _findings(_lint.lint_notes([path]), "unknown-tier")
    assert len(unknown) == 2
    assert "[原生T2]" in unknown[0].message and "Lua坐实" in unknown[0].message
    assert "T4" in unknown[1].message


def test_a_bare_numbered_level_is_read_but_not_held_to_the_cite_rule(project):
    """`（T1）` on a sentence is the retired scale; its RVAs are still checked."""
    from revenant import indices
    indices.VERSIONS["t"] = indices.VersionData(
        root="", rva_index={"1234abcd": {"class": "Foo", "signature": "void Bar()"}})
    try:
        path = _note(
            project, "arch-23-x.md",
            "# X\n\n这是同一框架的较早形态（T2）。\n| 明文残留 | 可见 | T1 |\n"
            "解密器在 0xDEADBEEF（T1）。\n" + DATA_SOURCES)
        report = _lint.lint_notes([path], version="t")
        assert not _findings(report, "tier-without-source")
        assert [f.line for f in _findings(report, "rva-not-found")] == [5]
    finally:
        indices.VERSIONS.pop("t", None)


def test_a_legend_a_heading_and_a_fenced_block_are_not_claims(project):
    path = _note(
        project, "arch-24-x.md",
        "# X\n\n逐条标注 **[C#签名]**(T2 级)、**[Lua坐实]**(T2 级)、**[原生黑盒]**(T4)。\n"
        "### 3.1 计费客户端 [原生T1]\n"
        "```mermaid\nsubgraph D[\"差异化 (部分客户端坐实)\"]\n```\n"
        "- **T1** (ARM32 disassembly): inline RVA citations\n"
        + DATA_SOURCES)
    report = _lint.lint_notes([path])
    assert not report.errors, [f.message for f in report.errors]


def test_the_sources_section_and_a_bullets_continuation_lines_are_where_sources_live(project):
    path = _note(
        project, "arch-25-x.md",
        "# X\n\n- **+30 类型**（真实业务新增，[托管代码坐实]）：\n  - 持久化：EncryptedPersistentDict / DictFileStorage\n"
        "\n## 证据索引\n\n- 其余结论均为已核实 [反汇编坐实]。\n")
    report = _lint.lint_notes([path])
    assert not report.errors, [f.message for f in report.errors]


def test_the_index_only_vouches_for_disassembly_and_managed_symbols(project):
    """A `[Lua坐实]` line cites Lua; the C# index has never heard of it."""
    from revenant import indices
    indices.VERSIONS["t"] = indices.VersionData(
        root="", rva_index={"1234abcd": {"class": "Foo", "signature": "void Bar()"}})
    try:
        path = _note(
            project, "arch-26-x.md",
            "# X\n\n- 付费分档 [Lua坐实] `RandomOrderHelper.GetSelectedFilterConfig`\n"
            "- 域名 [托管代码坐实] `payapi.cliapi.microfun.cn` 与 `Foo.Bar`\n"
            "- 缺的 [托管代码坐实] `Nope.Missing`\n" + DATA_SOURCES)
        report = _lint.lint_notes([path], version="t")
        assert [f.line for f in _findings(report, "symbol-not-found")] == [5]
    finally:
        indices.VERSIONS.pop("t", None)


def test_an_address_inside_a_cited_method_is_not_missing_but_a_bare_one_is(project):
    """`eor r1, r4, r6 at 0x953890` is an instruction in the method the line
    names. Without the start on the line the same address is unverifiable, and
    rule 1 -- the only mechanical catch for an invented address -- must fire."""
    from revenant import indices
    indices.VERSIONS["t"] = indices.VersionData(
        root="", rva_index={"009537dc": {"class": "Crypt", "signature": "void CryptStringWithKey()"}})
    try:
        path = _note(project, "arch-27-x.md", "# X\n\n- XOR [反汇编坐实] `re_evidence` 0x009537DC, eor at 0x953890\n" + DATA_SOURCES)
        assert not _findings(_lint.lint_notes([path], version="t"), "rva-not-found")
        bare = _note(project, "arch-27-y.md", "# X\n\n- XOR [反汇编坐实] eor at 0x953890\n" + DATA_SOURCES)
        assert _findings(_lint.lint_notes([bare], version="t"), "rva-not-found")
    finally:
        indices.VERSIONS.pop("t", None)


def test_a_note_about_another_indexed_version_is_checked_against_that_index(project):
    from revenant import indices
    indices.VERSIONS["9.9.1"] = indices.VersionData(root="", rva_index={"00001000": {"class": "A", "signature": "void X()"}})
    indices.VERSIONS["9.9.2"] = indices.VersionData(root="", rva_index={"00002000": {"class": "A", "signature": "void X()"}})
    try:
        path = _note(project, "arch-28-x.md", "# X\n\n**Game**: v9.9.1\n\n- 入口 [反汇编坐实] 0x00001000\n" + DATA_SOURCES)
        report = _lint.lint_notes([path], version="9.9.2")
        assert not _findings(report, "rva-not-found"), [f.message for f in report.errors]
    finally:
        indices.VERSIONS.pop("9.9.1", None)
        indices.VERSIONS.pop("9.9.2", None)


def test_an_index_file_is_not_a_note(project):
    _note(project, "INDEX.md", "# 索引\n")
    _note(project, "arch-29-x.md", "# X\n" + DATA_SOURCES)
    names = [os.path.basename(p) for p in _lint.collect_notes(str(project))]
    assert names == ["arch-29-x.md"]


def test_the_skill_lists_accepted_spellings_but_never_the_retired_scale(project):
    from revenant import describe
    from revenant.methodology import tier_spellings, TIER_SCRIPT_SOURCE
    assert "Lua坐实" in tier_spellings(TIER_SCRIPT_SOURCE)
    assert "T1" not in tier_spellings("disassembly")
    assert "T1" in tier_spellings("disassembly", include_retired=True)
    text = describe.render_skill(describe.describe(include_project=True))
    assert "`[Lua坐实]`" in text and "`[原生T1]`" in text


def test_a_conclusion_without_a_reproduce_section_warns_but_does_not_error(project):
    """Convention (#32): six of eight real projects grew a 复现命令 section on
    their own, so a tiered note without one gets a warning, not an error."""
    bare = _note(project, "arch-40-x.md", "# X\n\n- 结论 [结构推断] 见 arch-09\n" + DATA_SOURCES)
    report = _lint.lint_notes([bare])
    warns = [f for f in report.warnings if f.rule == "no-reproduce"]
    assert len(warns) == 1
    assert not any(f.rule == "no-reproduce" for f in report.errors)

    with_repro = _note(
        project, "arch-41-x.md",
        "# X\n\n- 结论 [结构推断] 见 arch-09\n\n## 复现命令\n\n```\nrevenant search Foo\n```\n" + DATA_SOURCES)
    assert not any(f.rule == "no-reproduce" for f in _lint.lint_notes([with_repro]).findings)


def test_a_note_with_no_conclusions_is_not_asked_to_reproduce(project):
    plain = _note(project, "arch-42-x.md", "# X\n\n只是一段说明，没有任何结论。\n" + DATA_SOURCES)
    assert not any(f.rule == "no-reproduce" for f in _lint.lint_notes([plain]).findings)


@pytest.mark.parametrize("heading", [
    "## 复现命令",
    "## 七、本轮新增的可复现命令",   # 编号前缀，语料里 222 个标题有 142 个是这种
    "## 复现要点",                  # `\b` 在中日文边界上不成立，这条曾漏网
    "## Reproduce",
])
def test_every_real_spelling_of_the_reproduce_heading_is_accepted(project, heading):
    """#43: the rule was anchoring the keyword right after the `#`, so 3 of 13
    warnings on the real corpus were false -- #29's failure, repeated."""
    path = _note(project, "arch-50-x.md",
                 f"# X\n\n- 结论 [结构推断] 见 arch-09\n\n{heading}\n\n```\nrevenant search Foo\n```\n"
                 + DATA_SOURCES)
    assert not [f for f in _lint.lint_notes([path]).findings if f.rule == "no-reproduce"]


def test_a_note_with_no_reproduce_section_at_all_still_warns(project):
    """The rule must not become one that never fires."""
    path = _note(project, "arch-51-x.md",
                 "# X\n\n- 结论 [结构推断] 见 arch-09\n\n## 分析\n\n## 结语\n" + DATA_SOURCES)
    assert [f for f in _lint.lint_notes([path]).warnings if f.rule == "no-reproduce"]


# ── lint: the machine-readable form and the repository sweep (#53) ──────────
#
# One seam for both: `cli.main(["lint", ...])` and the JSON that lands on
# stdout. That JSON is the contract `merge-games-re`'s econ-loop consumes; it
# used to scrape the human report with a regex because there was no other form.

def _lint_json(args, capsys):
    assert _cli.main(["lint", "--json", *args]) == 0
    return json.loads(capsys.readouterr().out)


def _repo(tmp_path, *names):
    """A git repository holding one project per name, each with a notes/ dir."""
    from revenant.init import init_project
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    out = []
    for name in names:
        init_project(str(repo / name), quiet=True)
        (repo / name / "notes").mkdir(exist_ok=True)
        out.append(repo / name)
    return repo, out


def test_the_json_and_the_human_report_come_from_one_structure(project, capsys):
    """Two renderers over one `LintReport`. A second formatter would drift from
    the first, which is the failure #37 is about in the generated files."""
    _note(project, "arch-90-x.md", "# X\n\n- 结论 [反汇编坐实] 无出处\n" + DATA_SOURCES)
    payload = _lint_json([], capsys)
    assert _cli.main(["lint"]) == 0
    human = capsys.readouterr().out
    assert len(payload["findings"]) == human.count("  error  ") + human.count("  warning")
    assert any(f["rule"] == "tier-without-source" for f in payload["findings"])


def test_the_human_report_is_byte_for_byte_what_it_always_was(project, capsys):
    """The flag adds a renderer; it must not quietly reformat the old one."""
    path = _note(project, "arch-91-x.md",
                 "# X\n\n- 结论 [反汇编坐实] 无出处\n" + DATA_SOURCES)
    assert _cli.main(["lint"]) == 0
    assert capsys.readouterr().out == _lint.format_report(
        _lint.lint_notes([path])) + "\n"


def test_a_sweep_says_which_project_in_the_human_report_too(tmp_path, monkeypatch, capsys):
    """The project is the only thing telling nine identical relative paths
    apart, so it cannot exist only in the JSON."""
    repo, (a, _b) = _repo(tmp_path, "love-and-pies", "travel-town")
    _note(a, "econ-01-currency.md", "# A\n\n- 结论 [反汇编坐实] 无出处\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "[love-and-pies]" in capsys.readouterr().out


def test_repo_with_paths_says_the_flag_was_ignored(project, capsys):
    """A flag that does nothing without a word is indistinguishable from one
    that did not work."""
    path = _note(project, "arch-94-x.md", "# X\n\n- 见 arch-09\n" + DATA_SOURCES)
    assert _cli.main(["lint", "--repo", path]) == 0
    assert "--repo" in capsys.readouterr().err


def test_json_reports_and_does_not_block(project, capsys):
    """`lint` returns 0 whatever it finds. Machine-readable output is not a
    reason to reopen a gate the previous one was never once satisfied by."""
    _note(project, "arch-92-x.md", "# X\n\n- 结论 [反汇编坐实] 无出处\n" + DATA_SOURCES)
    assert _cli.main(["lint", "--json"]) == 0
    capsys.readouterr()


# ── the terminal-state marker ───────────────────────────────────────────────

MARK = "<!-- re-state: axis=econ slot=01 state=insufficient_evidence -->"


def test_a_notes_declared_state_reaches_the_json(project, capsys):
    _note(project, "econ-01-currency.md", f"{MARK}\n# X\n\n- 见 arch-09\n" + DATA_SOURCES)
    notes = {n["path"]: n for n in _lint_json([], capsys)["notes"]}
    entry = next(n for p, n in notes.items() if p.endswith("econ-01-currency.md"))
    assert entry["state"] == "insufficient_evidence"
    assert entry["axis"] == "econ" and entry["slot"] == "01"


def test_a_note_without_a_marker_is_still_listed_with_an_empty_state(project, capsys):
    """Otherwise a consumer cannot tell "wrote no marker" from "file absent"."""
    _note(project, "arch-93-x.md", "# X\n\n- 见 arch-09\n" + DATA_SOURCES)
    entry = next(n for n in _lint_json([], capsys)["notes"]
                 if n["path"].endswith("arch-93-x.md"))
    assert entry["state"] == ""


def test_the_marker_may_span_lines_and_carry_reach_and_gaps(project, capsys):
    _note(project, "econ-05-orders.md",
          "<!-- re-state: axis=econ slot=05 state=out_of_reach\n"
          "               reach=input_missing gap=server_side,not_in_package -->\n"
          "# X\n\n- 见 arch-09\n" + DATA_SOURCES)
    entry = next(n for n in _lint_json([], capsys)["notes"]
                 if n["path"].endswith("econ-05-orders.md"))
    assert entry["state"] == "out_of_reach"
    assert entry["reach"] == "input_missing"
    assert entry["gaps"] == ["server_side", "not_in_package"]


def test_an_unknown_state_is_reported_rather_than_becoming_a_new_category(project):
    """Same bargain as `unknown-tier`: a typo must not silently found a fifth
    state. `partial` is econ-loop's word, and exactly the kind of near-miss."""
    path = _note(project, "econ-02-energy.md",
                 "<!-- re-state: axis=econ slot=02 state=partial -->\n# X\n" + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "unknown-state")


def test_a_marker_with_no_state_at_all_is_reported(project):
    path = _note(project, "econ-03-x.md",
                 "<!-- re-state: axis=econ slot=03 -->\n# X\n" + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "unknown-state")


def test_reach_only_means_something_when_the_evidence_is_out_of_reach(project):
    """`reach` says *why* it cannot be reached. On any other state it is noise
    that reads like a fact."""
    path = _note(project, "econ-04-x.md",
                 "<!-- re-state: axis=econ slot=04 state=meets_threshold "
                 "reach=input_missing -->\n# X\n" + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "reach-without-out-of-reach")
    ok = _note(project, "econ-04-y.md",
               "<!-- re-state: axis=econ slot=04 state=out_of_reach "
               "reach=output_doubtful -->\n# X\n" + DATA_SOURCES)
    assert not _findings(_lint.lint_notes([ok]), "reach-without-out-of-reach")


def test_an_unknown_reach_source_has_its_own_rule(project):
    """Its own name, not `unknown-state`: the rule is a machine contract now,
    and a consumer cannot act on one that means four different things."""
    path = _note(project, "econ-04-z.md",
                 "<!-- re-state: axis=econ slot=04 state=out_of_reach "
                 "reach=someday -->\n# X\n" + DATA_SOURCES)
    report = _lint.lint_notes([path])
    assert _findings(report, "unknown-reach")
    assert not _findings(report, "unknown-state")


def test_a_gap_marker_is_never_tied_to_the_state(project):
    """A gap marker hangs on a conclusion that *holds* but is missing a piece.
    That is a different axis from how far the question got, so it is legal on
    any state -- including the one that met the threshold."""
    path = _note(project, "econ-06-x.md",
                 "<!-- re-state: axis=econ slot=06 state=meets_threshold "
                 "gap=server_side,not_in_package -->\n# X\n" + DATA_SOURCES)
    report = _lint.lint_notes([path])
    assert not report.findings or all(
        f.rule not in ("unknown-gap-marker", "reach-without-out-of-reach")
        for f in report.findings)


def test_an_unknown_gap_marker_is_allowed_but_said_out_loud(project):
    """Open vocabulary, so a warning and not an error -- but a typo must not
    found a new category in silence. Same bargain `ledger` strikes."""
    path = _note(project, "econ-06-y.md",
                 "<!-- re-state: axis=econ slot=06 state=meets_threshold "
                 "gap=serverside -->\n# X\n" + DATA_SOURCES)
    found = _findings(_lint.lint_notes([path]), "unknown-gap-marker")
    assert found and found[0].severity == "warning"


def test_a_repeated_key_is_reported_rather_than_silently_dropped(project):
    """`gap=a gap=b` used to keep `b` and lose `a` with nothing to show."""
    path = _note(project, "econ-07-x.md",
                 "<!-- re-state: axis=econ slot=07 state=meets_threshold "
                 "gap=server_side gap=not_in_package -->\n# X\n" + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "malformed-state-marker")


def test_a_second_marker_is_reported_rather_than_ignored(project):
    path = _note(project, "econ-07-y.md",
                 "<!-- re-state: axis=econ slot=07 state=meets_threshold -->\n"
                 "# X\n\n"
                 "<!-- re-state: axis=econ slot=07 state=confirmed_absent -->\n"
                 + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "malformed-state-marker")


def test_axis_and_slot_are_the_projects_business_and_are_not_validated(project):
    """Which dimensions exist is a fact about the study, not about revenant --
    the reason `matrix.yaml` stays in the project (ADR-0003)."""
    path = _note(project, "anti-cheat-77-x.md",
                 "<!-- re-state: axis=anti-cheat slot=77 state=confirmed_absent -->\n"
                 "# X\n" + DATA_SOURCES)
    report = _lint.lint_notes([path])
    assert not _findings(report, "unknown-state")


# ── the repository sweep ────────────────────────────────────────────────────

def test_repo_sweeps_every_project_under_the_repository_root(tmp_path, monkeypatch, capsys):
    """One invocation instead of one `subprocess` per project. The sensor looped
    because `lint` only ever knew the project it was standing in."""
    repo, (a, b) = _repo(tmp_path, "love-and-pies", "travel-town")
    _note(a, "econ-01-currency.md", f"{MARK}\n# A\n" + DATA_SOURCES)
    _note(b, "econ-01-currency.md", f"{MARK}\n# B\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    assert {n["project"] for n in payload["notes"]} == {"love-and-pies", "travel-town"}


def test_repo_runs_from_the_repository_root_which_is_not_itself_a_project(
        tmp_path, monkeypatch, capsys):
    """`merge-games-re`'s root has no `revenant.toml`. Requiring one is exactly
    what forced the per-project loop."""
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    _note(a, "econ-01-currency.md", f"{MARK}\n# A\n" + DATA_SOURCES)
    assert not (repo / "revenant.toml").exists()
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    assert [n["project"] for n in payload["notes"]] == ["love-and-pies"]


def test_a_finding_says_which_project_it_belongs_to(tmp_path, monkeypatch, capsys):
    """`notes/econ-01-currency.md` is the same relative path in all nine."""
    repo, (a, b) = _repo(tmp_path, "love-and-pies", "travel-town")
    _note(a, "econ-01-currency.md", "# A\n\n- 结论 [反汇编坐实] 无出处\n" + DATA_SOURCES)
    _note(b, "econ-01-currency.md", f"{MARK}\n# B\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    offenders = {f["project"] for f in payload["findings"]
                 if f["rule"] == "tier-without-source"}
    assert offenders == {"love-and-pies"}


def test_repo_does_not_climb_out_of_the_repository(tmp_path, monkeypatch, capsys):
    """Same bound as the harness search (#51): a project above the repository
    root is somebody else's."""
    from revenant.init import init_project
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    _note(a, "econ-01-currency.md", f"{MARK}\n# A\n" + DATA_SOURCES)
    outside = tmp_path / "not-ours"
    init_project(str(outside), quiet=True)
    _note(outside, "econ-01-currency.md", f"{MARK}\n# outside\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    assert [n["project"] for n in payload["notes"]] == ["love-and-pies"]


def test_without_a_git_root_repo_is_just_this_project(tmp_path, monkeypatch, capsys):
    """No `.git` means no boundary, so there is nothing to sweep but here."""
    from revenant.init import init_project
    loose = tmp_path / "loose"
    init_project(str(loose), quiet=True)
    _note(loose, "econ-01-currency.md", f"{MARK}\n# A\n" + DATA_SOURCES)
    sibling = tmp_path / "sibling"
    init_project(str(sibling), quiet=True)
    _note(sibling, "econ-01-currency.md", f"{MARK}\n# S\n" + DATA_SOURCES)
    monkeypatch.chdir(loose)
    monkeypatch.delenv("REVENANT_PROJECT", raising=False)
    payload = _lint_json(["--repo"], capsys)
    assert len(payload["notes"]) == 1


def test_each_project_is_checked_against_its_own_index(tmp_path, monkeypatch, capsys):
    """Two projects can carry the same version string. Sharing one loaded index
    across the sweep would check B's notes against A's RVAs and invent errors."""
    from revenant import indices
    repo, (a, b) = _repo(tmp_path, "one", "two")
    _note(a, "arch-01-x.md", "# A\n\n- 见 arch-09\n" + DATA_SOURCES)
    _note(b, "arch-01-x.md", "# B\n\n- 见 arch-09\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    _lint_json(["--repo"], capsys)
    assert not indices.VERSIONS, "the sweep must not leave one project's index loaded"


def test_json_stays_json_when_there_are_no_notes(project, capsys):
    """A consumer parses stdout unconditionally. Answering a machine with the
    sentence "No notes found under notes/." is a broken contract, not an edge."""
    assert not _lint.collect_notes(str(project))
    payload = _lint_json([], capsys)
    assert payload["files"] == 0 and payload["notes"] == []


# ── the repository root's own notes (#67) ───────────────────────────────────
#
# A root without `revenant.toml` is not a project, but the `notes/` under it are
# notes -- and they are the cross-game summaries, the ones most easily written
# wrong. Fourteen of them sat outside `lint --repo`'s view because those two
# facts had been bound into one.

def test_the_repository_roots_own_notes_are_linted_too(tmp_path, monkeypatch, capsys):
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    _note(a, "econ-01-currency.md", f"{MARK}\n# A\n" + DATA_SOURCES)
    _note(repo, "cross-01-summary.md", "# 跨款\n\n- 结论 [反汇编坐实] 无出处\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    assert any(n["path"].endswith("cross-01-summary.md") for n in payload["notes"])
    assert any(f["rule"] == "tier-without-source" and f["path"].endswith("cross-01-summary.md")
               for f in payload["findings"])


def test_a_root_finding_says_it_belongs_to_no_project(tmp_path, monkeypatch, capsys):
    """The root is not a project, so its findings must not wear a project's name
    -- and this repository already has one sentence for "not yours" (#50)."""
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    _note(a, "econ-01-currency.md", f"{MARK}\n# A\n" + DATA_SOURCES)
    _note(repo, "cross-01-summary.md", "# 跨款\n\n- 结论 [反汇编坐实] 无出处\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    entry = next(n for n in payload["notes"] if n["path"].endswith("cross-01-summary.md"))
    assert entry["project"] == _lint.ROOT_LABEL
    assert "love-and-pies" not in entry["project"]
    # And in the human report too: nine projects carry the same relative paths,
    # so where a finding came from cannot live only in the JSON.
    assert _cli.main(["lint", "--repo"]) == 0
    assert _lint.ROOT_LABEL in capsys.readouterr().out


def test_a_repository_root_without_notes_stays_quiet(tmp_path, monkeypatch, capsys):
    """One isolated project must not grow noise because a second source exists."""
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    _note(a, "econ-01-currency.md", f"{MARK}\n# A\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    assert [n["project"] for n in payload["notes"]] == ["love-and-pies"]


def test_a_repository_with_notes_only_at_the_root_is_not_called_empty_handed(
        tmp_path, monkeypatch, capsys):
    """"No project here" was the whole message, and it was said while fourteen
    notes sat in the root waiting to be checked."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    _note(repo, "cross-01-summary.md", "# 跨款\n\n- 见 arch-09\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    monkeypatch.delenv("REVENANT_PROJECT", raising=False)
    payload = _lint_json(["--repo"], capsys)
    assert [n["project"] for n in payload["notes"]] == [_lint.ROOT_LABEL]
    assert "no project" not in capsys.readouterr().err

    # ...and with the note gone there really is nothing here, which is said.
    os.remove(str(repo / "notes" / "cross-01-summary.md"))
    assert _cli.main(["lint", "--repo"]) == 0
    assert "no project" in capsys.readouterr().err


def test_a_root_that_is_itself_a_project_is_not_linted_twice(tmp_path, monkeypatch, capsys):
    """`repo_projects` already includes a marked root. Collecting its notes a
    second time would double every finding in them."""
    from revenant.init import init_project
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    init_project(str(repo), quiet=True)
    _note(a, "econ-01-currency.md", f"{MARK}\n# A\n" + DATA_SOURCES)
    _note(repo, "cross-01-summary.md", "# 跨款\n\n- 结论 [反汇编坐实] 无出处\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    hits = [n for n in payload["notes"] if n["path"].endswith("cross-01-summary.md")]
    assert len(hits) == 1
    # The finding is the half that matters: a doubled note is a doubled report.
    doubled = [f for f in payload["findings"]
               if f["path"].endswith("cross-01-summary.md")
               and f["rule"] == "tier-without-source"]
    assert len(doubled) == 1


# ── what a cross-game conclusion rests on (#67) ─────────────────────────────
#
# The one failure of the four that is decidable the moment it is written: a note
# claiming to summarise nine games, while some of those nine cells are not
# filled. Everything else about invalidation needs a dependency graph nobody
# maintains; this needs a table lookup.

def _cell_mark(state):
    return f"<!-- re-state: axis=econ slot=07 state={state} -->"


def _study(tmp_path, states, marker):
    """One project per state, plus a cross-game note in the repository root."""
    repo, projects = _repo(tmp_path, *[f"game-{n}" for n in range(1, len(states) + 1)])
    for proj, state in zip(projects, states):
        _note(proj, "econ-07-x.md", f"{_cell_mark(state)}\n# X\n" + DATA_SOURCES)
    _note(repo, "econ-cross-07-summary.md", f"{marker}\n# 跨款\n" + DATA_SOURCES)
    return repo


def _rests(payload):
    return [f for f in payload["findings"] if f["rule"].startswith("rests-on")]


REST_ON_THREE = "<!-- re-rests-on: axis=econ slot=07 expect=3 -->"


def test_the_declared_dependency_reaches_the_json_as_a_fact(tmp_path, monkeypatch, capsys):
    """Same standing as `re-state`: what the note declares is a fact, reported
    beside the checks rather than instead of them."""
    repo = _study(tmp_path, [STATE_MEETS] * 3, REST_ON_THREE)
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    entry = next(n for n in payload["notes"] if n["path"].endswith("econ-cross-07-summary.md"))
    assert entry["rests_on"] == {"axis": "econ", "slot": "07", "expect": "3"}


def test_a_note_without_the_dependency_marker_carries_none(tmp_path, monkeypatch, capsys):
    repo = _study(tmp_path, [STATE_MEETS] * 3, REST_ON_THREE)
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    entry = next(n for n in payload["notes"] if n["path"].endswith("econ-07-x.md"))
    assert entry["rests_on"] == {}


def test_a_conclusion_resting_on_an_unmet_cell_names_the_project_and_the_state(
        tmp_path, monkeypatch, capsys):
    repo = _study(tmp_path, [STATE_MEETS, STATE_MEETS, STATE_INSUFFICIENT], REST_ON_THREE)
    monkeypatch.chdir(repo)
    payload = _lint_json(["--repo"], capsys)
    found = [f for f in _rests(payload) if f["rule"] == "rests-on-unmet-cell"]
    assert len(found) == 1, [f["message"] for f in found]
    assert "game-3" in found[0]["message"], found[0]["message"]
    assert STATE_INSUFFICIENT in found[0]["message"]
    assert found[0]["severity"] == "warning"


def test_a_conclusion_resting_on_cells_that_all_met_the_threshold_is_silent(
        tmp_path, monkeypatch, capsys):
    repo = _study(tmp_path, [STATE_MEETS] * 3, REST_ON_THREE)
    monkeypatch.chdir(repo)
    assert _rests(_lint_json(["--repo"], capsys)) == []


def test_fewer_cells_than_declared_says_both_numbers(tmp_path, monkeypatch, capsys):
    """Two numbers, in that order: an implementation that maps them the wrong
    way round would otherwise pass every test that only checks a rule fired."""
    repo = _study(tmp_path, [STATE_MEETS, STATE_MEETS],
                  "<!-- re-rests-on: axis=econ slot=07 expect=9 -->")
    monkeypatch.chdir(repo)
    found = [f for f in _rests(_lint_json(["--repo"], capsys))
             if f["rule"] == "rests-on-missing-cell"]
    assert len(found) == 1
    assert "found 2" in found[0]["message"] and "declared 9" in found[0]["message"]
    assert found[0]["severity"] == "warning"


def test_two_notes_from_one_game_are_one_game(tmp_path, monkeypatch, capsys):
    """`expect` counts games, so the found side has to as well. Counting notes
    lets one project that wrote the cell up twice stand in for a game nobody
    has looked at, and the shortfall goes unreported."""
    repo = _study(tmp_path, [STATE_MEETS, STATE_MEETS], REST_ON_THREE)
    second = repo / "game-2" / "notes" / "econ-07-again.md"
    second.write_text(f"{_cell_mark(STATE_MEETS)}\n# X\n" + DATA_SOURCES, encoding="utf-8")
    monkeypatch.chdir(repo)
    found = [f for f in _rests(_lint_json(["--repo"], capsys))
             if f["rule"] == "rests-on-missing-cell"]
    assert len(found) == 1
    assert "found 2" in found[0]["message"], found[0]["message"]


def test_more_cells_than_declared_is_not_reported(tmp_path, monkeypatch, capsys):
    """The declaration is believed, and this is the case it was invented for: a
    project of another genre parked beside the study makes the counted number
    quietly larger, and "found 4, declared 3" would be us disbelieving the
    author about what their own round covers."""
    repo = _study(tmp_path, [STATE_MEETS] * 4, REST_ON_THREE)
    monkeypatch.chdir(repo)
    assert _rests(_lint_json(["--repo"], capsys)) == []


def test_as_many_cells_as_declared_is_silent_about_the_count(tmp_path, monkeypatch, capsys):
    repo = _study(tmp_path, [STATE_MEETS] * 3, REST_ON_THREE)
    monkeypatch.chdir(repo)
    assert not [f for f in _rests(_lint_json(["--repo"], capsys))
                if f["rule"] == "rests-on-missing-cell"]


def test_the_state_check_fires_even_when_the_count_is_right(tmp_path, monkeypatch, capsys):
    """The trap: judge the count first and return when it is satisfied, and half
    the rule never runs. Three cells, three declared, one of them not met."""
    repo = _study(tmp_path, [STATE_MEETS, STATE_MEETS, STATE_OUT_OF_REACH], REST_ON_THREE)
    monkeypatch.chdir(repo)
    rules = {f["rule"] for f in _rests(_lint_json(["--repo"], capsys))}
    assert rules == {"rests-on-unmet-cell"}


def test_both_kinds_of_failure_are_reported_separately(tmp_path, monkeypatch, capsys):
    """The remedies are different -- go find evidence, versus go write the note
    -- so folding them into one finding would tell the author the wrong thing."""
    repo = _study(tmp_path, [STATE_MEETS, STATE_INSUFFICIENT],
                  "<!-- re-rests-on: axis=econ slot=07 expect=9 -->")
    monkeypatch.chdir(repo)
    rules = {f["rule"] for f in _rests(_lint_json(["--repo"], capsys))}
    assert rules == {"rests-on-unmet-cell", "rests-on-missing-cell"}


def test_confirmed_absent_is_reported_under_its_own_name(tmp_path, monkeypatch, capsys):
    """It is the one unmet state that can be a legitimate footing -- "this game
    has no such mechanism" is itself a finding. So it is reported *with its own
    state name* and the judgement left to the reader, never merged into a
    blanket "not met"."""
    repo = _study(tmp_path, [STATE_MEETS, STATE_MEETS, STATE_ABSENT], REST_ON_THREE)
    monkeypatch.chdir(repo)
    found = [f for f in _rests(_lint_json(["--repo"], capsys))
             if f["rule"] == "rests-on-unmet-cell"]
    assert len(found) == 1
    assert STATE_ABSENT in found[0]["message"]


def test_notes_without_the_marker_are_never_asked_about_cells(tmp_path, monkeypatch, capsys):
    """Nine per-game notes must not turn noisy because a thirteenth rule exists."""
    repo, projects = _repo(tmp_path, "game-1", "game-2", "game-3")
    for proj in projects:
        _note(proj, "econ-07-x.md", f"{_cell_mark(STATE_INSUFFICIENT)}\n# X\n" + DATA_SOURCES)
    monkeypatch.chdir(repo)
    assert _rests(_lint_json(["--repo"], capsys)) == []


def test_a_dependency_on_cells_that_exist_nowhere_is_a_marker_error(
        tmp_path, monkeypatch, capsys):
    """Nine declared and none found has only one honest reading: the marker is
    wrong. Reporting it as "0 of 9 filled in" would blame the research."""
    repo = _study(tmp_path, [STATE_MEETS] * 3,
                  "<!-- re-rests-on: axis=econ slot=99 expect=3 -->")
    monkeypatch.chdir(repo)
    found = _rests(_lint_json(["--repo"], capsys))
    assert [f["rule"] for f in found] == ["rests-on-nothing"]
    assert found[0]["severity"] == "error"


def test_the_dependency_check_reports_and_does_not_block(tmp_path, monkeypatch, capsys):
    repo = _study(tmp_path, [STATE_INSUFFICIENT], "<!-- re-rests-on: axis=econ slot=07 expect=9 -->")
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    capsys.readouterr()


# The marker's own spelling is checked where every note is read, so these need
# no sweep -- and a broken marker must be reported even to somebody linting one
# project on its own.

def test_a_non_numeric_expect_is_an_error_not_a_silent_zero(project):
    """`expect=nine` read as 0 makes every count comparison pass forever."""
    path = _note(project, "econ-cross-01-x.md",
                 "<!-- re-rests-on: axis=econ slot=07 expect=nine -->\n# X\n" + DATA_SOURCES)
    found = _findings(_lint.lint_notes([path]), "malformed-rests-on-marker")
    assert found and found[0].severity == "error"


def test_a_dependency_marker_with_no_expect_is_an_error(project):
    """"Found 7" and "should be 9" are two facts, and a walk that finds nothing
    returns the same empty answer as a path that was mistyped."""
    path = _note(project, "econ-cross-02-x.md",
                 "<!-- re-rests-on: axis=econ slot=07 -->\n# X\n" + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "malformed-rests-on-marker")


def test_a_dependency_marker_must_say_which_axis_and_slot(project):
    """Without them the marker points at every unmarked note in the repository."""
    path = _note(project, "econ-cross-03-x.md",
                 "<!-- re-rests-on: expect=9 -->\n# X\n" + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "malformed-rests-on-marker")


def test_a_second_dependency_marker_is_reported(project):
    path = _note(project, "econ-cross-04-x.md",
                 "<!-- re-rests-on: axis=econ slot=07 expect=9 -->\n# X\n\n"
                 "<!-- re-rests-on: axis=econ slot=08 expect=9 -->\n" + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "malformed-rests-on-marker")


def test_a_repeated_key_in_the_dependency_marker_is_reported(project):
    path = _note(project, "econ-cross-05-x.md",
                 "<!-- re-rests-on: axis=econ slot=07 slot=08 expect=9 -->\n# X\n"
                 + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "malformed-rests-on-marker")


def test_a_well_formed_dependency_marker_is_not_a_marker_error(project):
    """The reverse of the five above: a correct marker in a project linted on
    its own reports nothing, because the cells it names live elsewhere."""
    path = _note(project, "econ-cross-06-x.md",
                 f"{REST_ON_THREE}\n# X\n" + DATA_SOURCES)
    report = _lint.lint_notes([path])
    assert not [f for f in report.findings if f.rule.startswith("rests-on")
                or f.rule == "malformed-rests-on-marker"]


# ── lint: a back-reference is not a source (ADR-0006) ───────────────────────
#
# `_cites_something` is positive-only, so a claim that points back into the
# document passes the moment it happens to carry any identifier. That is the
# highest-frequency failure in the econ corpus, and the project it came from had
# been patching it with a hand-written grep and a prose table in its skill.

def test_a_backreference_carrying_only_a_bare_identifier_is_reported(project):
    """"出处见第一节，`merge_score_race` 那一列" -- the shape that slips through.
    The identifier is the object of the back-reference, not a source."""
    path = _note(project, "arch-70-x.md",
                 "# X\n\n- 竞速分是普通分的 47% [脚本源码坐实]：出处见第一节，"
                 "`merge_score_race` 那一列\n" + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "backreference-as-source")


def test_a_backreference_that_also_names_a_file_is_left_alone(project):
    """The guard on the blacklist. Pointing back *and* out is how a real note
    says "same source as above, here it is again" -- that is not the failure."""
    path = _note(project, "arch-71-x.md",
                 "# X\n\n- 竞速分是普通分的 47% [脚本源码坐实]：见第一节；另见 "
                 "`Data/Config/MergeItemScoreConfig.lua:47`\n" + DATA_SOURCES)
    assert not _findings(_lint.lint_notes([path]), "backreference-as-source")


def test_a_backreference_carrying_only_a_camelcase_name_is_reported(project):
    """`由上两行推得，见 \\`RewardEconomyValueConf\\`` -- the second real shape.
    `CAMEL_IDENT` is what let this one through."""
    path = _note(project, "arch-72-x.md",
                 "# X\n\n- 该值由上两行推得 [结构推断]，见 `RewardEconomyValueConf`\n"
                 + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "backreference-as-source")


def test_a_claim_with_no_source_at_all_is_not_also_called_a_backreference(project):
    """One line, one complaint. `依据是第 1.4 节那五处各自的判据行` carries no
    citation at all, so it is `tier-without-source`; saying both would make the
    reader fix it twice."""
    path = _note(project, "arch-73-x.md",
                 "# X\n\n- 九款都没有工会 [结构推断]：依据是第 1.4 节那五处各自的判据行\n"
                 + DATA_SOURCES)
    report = _lint.lint_notes([path])
    assert _findings(report, "tier-without-source")
    assert not _findings(report, "backreference-as-source")


def test_an_econ_note_reference_counts_as_a_source(project):
    """The prefix table predates the econ corpus, so 53 notes' cross-references
    only passed because they happened to be written as full paths."""
    path = _note(project, "arch-74-x.md",
                 "# X\n\n- 结论 [结构推断] 依据见 econ-10-social §3\n" + DATA_SOURCES)
    assert not _findings(_lint.lint_notes([path]), "tier-without-source")


# ── lint: a cited note has to exist (ADR-0005) ──────────────────────────────
#
# RVAs are looked up and symbols are looked up; a cited path was only ever
# pattern-matched. Narrowed to `.md` on purpose: `res/` and `src/` are extracted
# material that is gitignored and often absent, and reporting *our* missing
# corpus as *the author's* dangling citation is the `no-index` mistake.

def test_a_cited_note_that_does_not_exist_is_reported(project):
    path = _note(project, "arch-75-x.md",
                 "# X\n\n- 结论 [结构推断] 见 `notes/arch-99-nope.md`\n" + DATA_SOURCES)
    assert _findings(_lint.lint_notes([path]), "cited-note-missing")


def test_a_cited_note_that_exists_is_not_reported(project):
    _note(project, "arch-76-target.md", "# T\n\n- 见 arch-09\n" + DATA_SOURCES)
    path = _note(project, "arch-77-x.md",
                 "# X\n\n- 结论 [结构推断] 见 `notes/arch-76-target.md`\n" + DATA_SOURCES)
    assert not _findings(_lint.lint_notes([path]), "cited-note-missing")


def test_a_cited_extracted_file_is_never_reported_as_missing(project):
    """`res/` is gitignored raw material. Absent means we did not prepare it,
    not that the author invented the path -- the same line `no-index` draws."""
    path = _note(project, "arch-78-x.md",
                 "# X\n\n- 结论 [结构推断] 见 `res/conf-json/_index.json`\n" + DATA_SOURCES)
    assert not _findings(_lint.lint_notes([path]), "cited-note-missing")


# ── lint: the agent's memory is a checked artifact (ADR-0005) ───────────────
#
# One repository grew a 314 KB memory file that was `cat`-ed into every round's
# context and never once got smaller across 81 commits. Registered files are
# checked; unregistered ones are not -- "not listed" is the whole opt-out, so
# there is no exemption flag to be abused.

MEMORY_DIR = os.path.join(".claude", "agent-memory")


def _memory(repo, name, text, **fields):
    """A memory file plus its line in the registry. Returns the file path."""
    import tomllib  # noqa: F401  (asserts the stdlib parser is the one in play)
    d = repo / MEMORY_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")
    rel = f"{MEMORY_DIR}/{name}".replace(os.sep, "/")
    body = ", ".join(f'{k} = {v!r}' if isinstance(v, str) else f"{k} = {v}"
                     for k, v in fields.items())
    reg = d / "memory.toml"
    head = reg.read_text(encoding="utf-8") if reg.exists() else "[files]\n"
    reg.write_text(f'{head}"{rel}" = {{ {body} }}\n', encoding="utf-8")
    return str(d / name)


def test_a_registered_memory_over_its_budget_is_an_error(tmp_path, monkeypatch, capsys):
    repo, _ = _repo(tmp_path, "love-and-pies")
    _memory(repo, "gap-loop.md", "x" * 500, kind="memory", bytes=100)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-over-budget" in capsys.readouterr().out


def test_an_unregistered_memory_file_is_not_checked_at_all(tmp_path, monkeypatch, capsys):
    """"Not listed" is the opt-out. The 314 KB archive stays on disk beside the
    live memory and must not be reported for being what it is."""
    repo, _ = _repo(tmp_path, "love-and-pies")
    d = repo / MEMORY_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "archive.md").write_text("x" * 500_000, encoding="utf-8")
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-over-budget" not in capsys.readouterr().out


MEMORY_HEAD = "# 记忆\n\n"


def test_a_memory_entry_without_a_pointer_is_an_error(tmp_path, monkeypatch, capsys):
    """An entry that carries its own evidence is how the fact layer and the
    conclusion layer end up in one file, which is the state they never come
    back out of. One sentence, then where to read it."""
    repo, _ = _repo(tmp_path, "love-and-pies")
    _memory(repo, "gap-loop.md", MEMORY_HEAD + "- 服务端下发的缺口先去远端素材里重验\n",
            kind="memory", bytes=40960)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-entry-without-pointer" in capsys.readouterr().out


def test_a_memory_entry_with_a_live_pointer_is_clean(tmp_path, monkeypatch, capsys):
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    (a / "notes" / "econ-10-social.md").write_text(
        "# S\n\n- 竞速口径的分在 `merge_score_race` 那一列\n", encoding="utf-8")
    _memory(repo, "gap-loop.md",
            MEMORY_HEAD + "- 竞速玩法另有一套计分口径 → "
            "`love-and-pies/notes/econ-10-social.md` 的 `merge_score_race`\n",
            kind="memory", bytes=40960)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-" not in capsys.readouterr().out


def test_a_memory_pointer_at_a_file_that_is_gone_is_an_error(tmp_path, monkeypatch, capsys):
    repo, _ = _repo(tmp_path, "love-and-pies")
    _memory(repo, "gap-loop.md",
            MEMORY_HEAD + "- 某条判据 → `love-and-pies/notes/econ-99-gone.md`\n",
            kind="memory", bytes=40960)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-pointer-missing" in capsys.readouterr().out


def test_a_memory_anchor_that_drifted_out_of_the_note_is_an_error(tmp_path, monkeypatch, capsys):
    """The anchor is a string and not a line number precisely so that this is
    detectable: the note was edited, the thing it pointed at is gone, say so."""
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    (a / "notes" / "econ-10-social.md").write_text("# S\n\n- 改写过了\n", encoding="utf-8")
    _memory(repo, "gap-loop.md",
            MEMORY_HEAD + "- 某条判据 → `love-and-pies/notes/econ-10-social.md` "
            "的 `merge_score_race`\n", kind="memory", bytes=40960)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-anchor-missing" in capsys.readouterr().out


def test_an_overlay_is_weighed_but_not_asked_for_pointers(tmp_path, monkeypatch, capsys):
    """A project's `re-project` overlay is prose about one game, not a list of
    claims-with-pointers. It gets the budget and nothing else."""
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    overlay = a / ".claude" / "skills" / "re-project"
    overlay.mkdir(parents=True, exist_ok=True)
    (overlay / "SKILL.md").write_text("# 本款约定\n\n- 热更程序集在 AOT 索引之外\n",
                                      encoding="utf-8")
    d = repo / MEMORY_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "memory.toml").write_text(
        '[files]\n"love-and-pies/.claude/skills/re-project/SKILL.md" = '
        '{ kind = "overlay", bytes = 61440 }\n', encoding="utf-8")
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    out = capsys.readouterr().out
    assert "memory-entry-without-pointer" not in out
    assert "memory-over-budget" not in out


def test_a_registered_memory_that_is_not_on_disk_is_reported(tmp_path, monkeypatch, capsys):
    """Registered-and-absent is not the same as unregistered. Silence here
    would let a rename quietly turn the checks off."""
    repo, _ = _repo(tmp_path, "love-and-pies")
    d = repo / MEMORY_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "memory.toml").write_text(
        '[files]\n".claude/agent-memory/gone.md" = { kind = "memory", bytes = 100 }\n',
        encoding="utf-8")
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-not-found" in capsys.readouterr().out


def test_a_memory_claim_longer_than_its_limit_is_a_warning(tmp_path, monkeypatch, capsys):
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    (a / "notes" / "econ-10-social.md").write_text("# S\n\n- 锚 `merge_score_race`\n",
                                                   encoding="utf-8")
    _memory(repo, "gap-loop.md",
            MEMORY_HEAD + "- " + "很长的一句话" * 30 + " → "
            "`love-and-pies/notes/econ-10-social.md` 的 `merge_score_race`\n",
            kind="memory", bytes=40960, entry_chars=120)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-entry-too-long" in capsys.readouterr().out


def test_a_sibling_note_cited_by_bare_name_resolves(project):
    """Notes cite each other by bare filename far more often than by path --
    54 findings on the real corpus, every one of them a note sitting right
    beside the one citing it."""
    _note(project, "arch-79-target.md", "# T\n\n- 见 arch-09\n" + DATA_SOURCES)
    path = _note(project, "arch-80-x.md",
                 "# X\n\n- 结论 [结构推断] 见 `arch-79-target.md`\n" + DATA_SOURCES)
    assert not _findings(_lint.lint_notes([path]), "cited-note-missing")


def test_a_note_cited_by_a_path_relative_to_itself_resolves(project):
    """`../../notes/ref-02-....md` is how a project note reaches the repository
    root's own notes."""
    root_notes = project.parent / "notes"
    root_notes.mkdir(exist_ok=True)
    (root_notes / "ref-02-x.md").write_text("# R\n", encoding="utf-8")
    path = _note(project, "arch-81-x.md",
                 "# X\n\n- 结论 [结构推断] 见 `../../notes/ref-02-x.md`\n" + DATA_SOURCES)
    assert not _findings(_lint.lint_notes([path]), "cited-note-missing")


def test_a_bare_note_name_resolves_against_any_project_in_the_repository(
        tmp_path, monkeypatch, capsys):
    """A cross-game summary writes 「九款的 `econ-03-merge-chain.md`」 and a
    same-source pair cites its twin's note by bare name. Both are correct prose;
    every one of the seven findings left on the real corpus was one of them."""
    repo, (a, b) = _repo(tmp_path, "hotel-legacy", "tasty-travels")
    (a / "notes" / "core-03-ifix-hotfix.md").write_text("# H\n", encoding="utf-8")
    path = b / "notes" / "core-02-ifix-hotfix.md"
    path.write_text("# T\n\n- 同一套构建配置 [结构推断]，见 `core-03-ifix-hotfix.md`\n"
                    + DATA_SOURCES, encoding="utf-8")
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "cited-note-missing" not in capsys.readouterr().out


def test_a_note_name_that_exists_nowhere_is_still_reported(tmp_path, monkeypatch, capsys):
    """The reverse of the above: widening the search must not turn the rule off."""
    repo, (a,) = _repo(tmp_path, "hotel-legacy")
    (a / "notes" / "core-01-x.md").write_text(
        "# H\n\n- 结论 [结构推断] 见 `core-77-invented.md`\n" + DATA_SOURCES,
        encoding="utf-8")
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "cited-note-missing" in capsys.readouterr().out


def test_an_unreadable_memory_registry_is_reported_not_swallowed(tmp_path, monkeypatch, capsys):
    """A typo in the registry must not read as "nothing is registered". That is
    the exemption switch this design refused to build, delivered by accident --
    and `config.load_config` already decided this argument the loud way."""
    repo, _ = _repo(tmp_path, "love-and-pies")
    d = repo / MEMORY_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "memory.toml").write_text('[files\n"x.md" = 1\n', encoding="utf-8")
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-registry-unreadable" in capsys.readouterr().out


def test_a_numbered_memory_entry_is_an_entry_too(tmp_path, monkeypatch, capsys):
    """The 171-entry file this rule was written about numbered its entries.
    Reading only `- ` would have left every pointer rule off on exactly the
    file that motivated them."""
    repo, _ = _repo(tmp_path, "love-and-pies")
    _memory(repo, "gap-loop.md", MEMORY_HEAD + "1. 服务端下发的缺口先去远端素材里重验\n",
            kind="memory", bytes=40960)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-entry-without-pointer" in capsys.readouterr().out


def test_the_bare_note_shorthand_is_deliberately_not_looked_up(tmp_path, monkeypatch, capsys):
    """The asymmetry argument behind `cited-note-missing` reaches `arch-88 §3.2`
    too, and stopping short of it is a decision, not an oversight.

    It was implemented and withdrawn. Three of this file's own tests fail under
    it -- each asserts that a note citing only its siblings is compliant, the
    pure-adjudication shape -- and the real corpus produced 50 findings, every
    one of them a stem matched inside a longer name (`cross-07-progression`
    inside `econ-cross-07-progression`). A prefix cannot be told from a suffix.
    """
    repo, (a,) = _repo(tmp_path, "hotel-legacy")
    (a / "notes" / "core-01-x.md").write_text(
        "# H\n\n- 结论 [结构推断] 依据见 arch-88 §3.2\n" + DATA_SOURCES, encoding="utf-8")
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "cited-note-missing" not in capsys.readouterr().out


def test_a_wrapped_memory_entry_keeps_its_pointer(tmp_path, monkeypatch, capsys):
    """An entry runs to the next entry, not to the end of its own line (#69).

    Reading one line was right for the file this rule was written against --
    every entry fitted on one -- and wrong for prose that wraps. A judgement
    hard-wrapped at 80 columns, with its `→ pointer` on the second line, was
    reported as having none; the loop that damps on lint errors then damped on
    a finding that was not real.
    """
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    (a / "notes" / "econ-10-social.md").write_text("# S\n\n- 锚 `merge_score_race`\n",
                                                   encoding="utf-8")
    _memory(repo, "gap-loop.md",
            MEMORY_HEAD
            + "- 判据的第一行在八十列上写不下，于是折了行，这在中文里是常态\n"
            + "  它的第二行仍然属于同一条\n"
            + "→ `love-and-pies/notes/econ-10-social.md` 的 `merge_score_race`\n",
            kind="memory", bytes=40960)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-entry-without-pointer" not in capsys.readouterr().out


def test_an_entry_with_no_pointer_anywhere_in_it_is_still_reported(tmp_path, monkeypatch, capsys):
    """The relaxation must not become the exemption. Widening what counts as
    the entry's body is only safe while a body with no pointer still fails."""
    repo, _ = _repo(tmp_path, "love-and-pies")
    _memory(repo, "gap-loop.md",
            MEMORY_HEAD + "- 一条判据\n  它的续行\n  还是没有指针\n",
            kind="memory", bytes=40960)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-entry-without-pointer" in capsys.readouterr().out


def test_an_entry_cannot_borrow_a_pointer_from_the_next_section(tmp_path, monkeypatch, capsys):
    """A heading ends an entry. Without that, the first pointer anywhere below
    would satisfy every pointer-less entry above it."""
    repo, (a,) = _repo(tmp_path, "love-and-pies")
    (a / "notes" / "econ-10-social.md").write_text("# S\n\n- 锚 `x`\n", encoding="utf-8")
    _memory(repo, "gap-loop.md",
            MEMORY_HEAD + "- 一条没有指针的判据\n\n## 别的小节\n\n"
            "见 → `love-and-pies/notes/econ-10-social.md`\n",
            kind="memory", bytes=40960)
    monkeypatch.chdir(repo)
    assert _cli.main(["lint", "--repo"]) == 0
    assert "memory-entry-without-pointer" in capsys.readouterr().out
