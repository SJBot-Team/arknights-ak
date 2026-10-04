"""Self-description, and the two guards that make drift impossible to repeat.

The command list and the vocabulary tests are the point of this file. Everything
else guards their edges. They exist because a round added nine commands and
replaced the whole evidence-tier table while the shipped skill kept teaching the
abolished one — and nothing anywhere noticed, until somebody asked.
"""

from __future__ import annotations

import json
import re

import pytest

from revenant import cli, describe as _describe, ledger as _ledger, methodology as _m


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


def _rendered(project=None) -> str:
    return _describe.render_skill(_describe.describe(include_project=project is not None))


def _rendered_files(project=None, target="claude") -> dict:
    """Every file one renderer writes: the skill and the six commands."""
    return _describe.render(_describe.describe(include_project=project is not None), target)


RETIRED = ("T1", "T2", "T3", "T4")
RETIRED_MARKERS = ("(confirmed)", "// Progress:")


def _enable_example_pack(project):
    text = (project / "revenant.toml").read_text()
    (project / "revenant.toml").write_text(text + '\n[packs]\nenabled = ["example"]\n')
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()


# ── the two structural guards ───────────────────────────────────────────────

BACKTICKED = re.compile(r"`revenant ([a-z][a-z-]*)")


def test_every_command_a_document_mentions_actually_exists(project):
    """The generic guard against guidance pointing at a command that is not there.

    One round of this codebase shipped three files telling people to run
    `python -m tools.re ...`, which had not existed since it became an
    installable package. This makes that class of mistake impossible in any
    generated document.
    """
    real = set(cli.command_table())
    for with_pack in (False, True):
        if with_pack:
            _enable_example_pack(project)
        # Every renderer, not only Claude's: a second harness that escaped the
        # guards would be exactly the half-checked state #68 set out to avoid.
        for target in _describe.RENDERERS:
            files = _rendered_files(project, target)
            assert set(files) == set(_describe.rendered_paths(target))
            for rel, text in files.items():
                mentioned = set(BACKTICKED.findall(text))
                unknown = sorted(mentioned - real)
                assert not unknown, f"{rel} documents commands that are not dispatchable: {unknown}"
            skill = _describe.RENDERERS[target].SKILL
            assert set(BACKTICKED.findall(files[skill])), (
                f"{target}: the rendered skill should reference commands at all")


def test_the_document_teaches_exactly_the_vocabulary_the_code_has(project):
    """Directly against this ticket's cause.

    A skill teaching T1-T4 outlived the change that abolished the speculation
    tier, and kept instructing every new project to use a scale the tool would
    reject.
    """
    # Cell states and facets belong to the frozen scan family (ADR-0002) and
    # are taught only once a pack is enabled; tiers apply to every note.
    for tier in _m.TIERS:
        assert f"`{tier}`" in _rendered(project), f"tier {tier} missing from the rendered skill"
    _enable_example_pack(project)
    text = _rendered(project)
    for tier in _m.TIERS:
        assert f"`{tier}`" in text, f"tier {tier} missing from the rendered skill"
    for state in _m.STATES:
        assert f"`{state}`" in text, f"state {state} missing from the rendered skill"
    for facet in _m.FACETS:
        assert f"`{facet}`" in text, f"facet {facet} missing from the rendered skill"

    # And nothing from the retired scheme survives in any rendered file -- the
    # four slash commands taught `T1`/`T3`, `(confirmed)` and `// Progress:`
    # for as long as the skill did (#30).
    for target in _describe.RENDERERS:
        for rel, rendered in _rendered_files(project, target).items():
            for retired in RETIRED:
                assert not re.search(rf"\b{retired}\b", rendered), (
                    f"{rel}: {retired} is from the abolished tier scale and must not be taught"
                )
            for marker in RETIRED_MARKERS:
                assert marker not in rendered, f"{rel} still teaches {marker!r}"


def test_the_document_teaches_how_to_declare_what_a_conclusion_rests_on(project):
    """An agent that has not been taught the marker will not write it, and a
    marker nobody writes checks nothing (#67). It sits with the four states,
    not behind the pack gate: what a conclusion rests on is the same question
    whether the cell came from a pack slot or from a note (ADR-0003)."""
    text = _rendered(project)                       # no pack enabled
    assert "re-rests-on" in text
    assert "expect=" in text, "the count has to be declared, so it has to be taught"
    m = _describe.describe().methodology
    assert "re-rests-on" in m["notes"]["rests_on"]


def test_the_shipped_practice_text_carries_no_retired_vocabulary(project):
    """The hand-written half is exempt from generation, not from correctness."""
    practice = _describe._practice_text()
    assert practice, "the practice text should ship with the package"
    for retired in ("T1", "T2", "T3", "T4"):
        assert not re.search(rf"\b{retired}\b", practice)
    # The fabricated-completeness markers the ledger replaced.
    assert "// Progress:" not in practice
    assert "(confirmed)" not in practice


# ── the description itself ──────────────────────────────────────────────────

def test_commands_come_from_the_dispatch_table_not_a_second_list(project):
    """Every described command is dispatchable, and the default surface is
    exactly what `help` shows (core; plus the extension tier once a pack is
    enabled). `--all` widens both to the query tier."""
    desc = _describe.describe()
    assert desc.command_names() <= set(cli.command_table())
    assert desc.command_names() == set(cli.visible_commands())
    assert _describe.describe(show_all=True).command_names() == set(cli.visible_commands(show_all=True))
    _enable_example_pack(project)
    assert _describe.describe().command_names() == set(cli.visible_commands())


def test_vocabulary_comes_from_methodology(project):
    _enable_example_pack(project)
    m = _describe.describe().methodology
    assert [t["id"] for t in m["tiers"]] == list(_m.TIERS)
    assert [s["id"] for s in m["cell_states"]] == list(_m.STATES)
    assert [f["id"] for f in m["facets"]] == list(_m.FACETS)
    assert m["gap_markers"] == list(_m.KNOWN_GAP_MARKERS)


def test_ledger_contract_comes_from_the_ledger(project):
    _enable_example_pack(project)
    contract = _describe.describe().ledger
    assert contract["fact_fields"] == list(_ledger.FACT_FIELDS)
    assert contract["judgement_fields"] == list(_ledger.JUDGEMENT_FIELDS)


def test_project_section_lists_the_enabled_packs(project):
    _enable_example_pack(project)

    desc = _describe.describe()
    names = [p["name"] for p in desc.project["packs"]]
    assert names == ["example"]
    assert {s["id"] for s in desc.project["packs"][0]["slots"]} == {"E01", "E02"}


def test_description_is_serialisable(project):
    payload = json.loads(_describe.as_json(_describe.describe()))
    assert payload["schema"] == _describe.SCHEMA
    assert payload["revenant_version"]


# ── generation, not copying ─────────────────────────────────────────────────

def test_init_generates_the_skill_rather_than_copying_a_template(project):
    generated = project / ".claude" / "skills" / "re" / "SKILL.md"
    assert generated.exists()
    assert _describe.stamped_version(generated.read_text())


def test_the_project_overlay_is_separate_and_never_overwritten(project, monkeypatch):
    """Project conventions must survive a re-render; that is the whole point."""
    overlay = project / ".claude" / "skills" / "re-project" / "SKILL.md"
    assert overlay.exists()
    overlay.write_text("---\nname: re-project\ndescription: x\n---\n\nMY NOTES\n")

    monkeypatch.chdir(project)
    assert cli.main(["describe", "--render", "claude"]) == 0
    assert "MY NOTES" in overlay.read_text()


def test_a_stale_render_is_reported(project):
    from revenant import __version__
    generated = project / ".claude" / "skills" / "re" / "SKILL.md"
    generated.write_text(
        generated.read_text().replace(f"version={__version__}", "version=0.0.1"))

    drift = cli.harness_drift(str(project))
    assert "0.0.1" in drift and "re-render" in drift


def test_an_unstamped_document_is_reported_as_hand_written(project):
    generated = project / ".claude" / "skills" / "re" / "SKILL.md"
    generated.write_text("# hand written\n")
    assert "hand-written" in cli.harness_drift(str(project))


def test_a_current_render_reports_nothing(project):
    assert cli.harness_drift(str(project)) == ""


def test_rendering_an_unknown_harness_is_refused_not_guessed(project, monkeypatch, capsys):
    """Adding a harness is a documented decision (ADR-0001), not a flag.

    Codex used to be refused here and is not any more (#68); what the refusal
    was protecting -- "a harness needs a renderer, not a flag" -- is unchanged,
    so the test moved to a target that genuinely has none.
    """
    monkeypatch.chdir(project)
    assert cli.main(["describe", "--render", "reasonix"]) == 2
    out = capsys.readouterr().out
    assert "ADR-0001" in out
    assert "claude" in out and "codex" in out, "it should say which targets exist"


# ── description and renderer are two things (#30) ───────────────────────────

def test_the_command_templates_are_rendered_and_stamped_and_speak_the_tier_vocabulary(project):
    files = _rendered_files(project)
    for name in _describe.COMMAND_NAMES:
        text = files[f".claude/commands/{name}.md"]
        assert text.startswith("---\n"), f"{name}: front-matter first, so Claude reads it"
        assert _describe.stamped_version(text) == _describe.__version__
        assert "{{tier:" not in text, "tier tokens must be resolved from methodology"
    assert "`[structural]`" in files[".claude/commands/re-map.md"]
    assert "`[disassembly]`" in files[".claude/commands/re-deep.md"]
    # re-map is human-driven and does not reach for the frozen scan family.
    assert "revenant scan" not in files[".claude/commands/re-map.md"]
    assert "revenant cell" not in files[".claude/commands/re-map.md"]


def test_a_second_renderer_needs_no_change_to_describe(project, monkeypatch, capsys):
    """The interface is real if a renderer that writes only AGENTS.md drops in."""
    class AgentsMdRenderer:
        name = "agents-md"
        paths = ("AGENTS.md",)

        def render(self, desc, practice):
            names = ", ".join(c["name"] for c in desc.commands)
            return {"AGENTS.md": f"{_describe.stamp(desc.version)}\n\n# Agents\n\n{names}\n\n{practice}\n"}

    monkeypatch.setitem(_describe.RENDERERS, "agents-md", AgentsMdRenderer())
    monkeypatch.chdir(project)
    assert cli.main(["describe", "--render", "agents-md"]) == 0
    text = (project / "AGENTS.md").read_text()
    assert "# Agents" in text and "fingerprint" in text
    assert _describe.stamped_version(text) == _describe.__version__
    assert "Practice" in text
    assert _describe.rendered_paths("agents-md") == ("AGENTS.md",)


def test_init_renders_the_slash_commands_rather_than_copying_them(project):
    for name in _describe.COMMAND_NAMES:
        path = project / ".claude" / "commands" / f"{name}.md"
        assert path.exists(), name
        assert _describe.stamped_version(path.read_text()) == _describe.__version__


def test_drift_covers_the_command_templates_too(project):
    from revenant import __version__
    cmd = project / ".claude" / "commands" / "re-deep.md"
    cmd.write_text(cmd.read_text().replace(f"version={__version__}", "version=0.0.1"))
    drift = cli.harness_drift(str(project))
    assert "re-deep.md" in drift and "0.0.1" in drift and "re-render" in drift

    cmd.write_text("# a copied, unstamped command\n")
    assert "hand-written" in cli.harness_drift(str(project)) and "re-deep.md" in cli.harness_drift(str(project))

    cmd.unlink()
    assert "not rendered" in cli.harness_drift(str(project))



def test_render_if_stale_skips_when_current_and_renders_when_behind(project, monkeypatch, capsys):
    from revenant import __version__
    monkeypatch.chdir(project)
    assert cli.main(["describe", "--render", "claude", "--if-stale"]) == 0
    assert "current" in capsys.readouterr().out

    skill = project / ".claude" / "skills" / "re" / "SKILL.md"
    skill.write_text(skill.read_text().replace(f"version={__version__}", "version=0.0.1"))
    assert cli.main(["describe", "--render", "claude", "--if-stale"]) == 0
    out = capsys.readouterr().out
    assert "rendered" in out
    assert _describe.stamped_version(skill.read_text()) == __version__


def test_re_boundary_is_a_six_section_human_driven_outline(project):
    """Channel 3 of #32: the content-boundary outline, rendered and guarded."""
    files = _rendered_files(project)
    text = files[".claude/commands/re-boundary.md"]
    assert _describe.stamped_version(text) == _describe.__version__
    for section in ("代码热更机制", "资源与配置下发机制", "内容边界清单",
                    "缺口评估", "获取路径", "与其他游戏的对照"):
        assert section in text, f"re-boundary missing section {section}"
    # Human-driven: it does not reach for the frozen scan family, and it says so.
    assert "revenant scan" not in text and "revenant cell" not in text
    assert "does not run `scan`" in text
    assert "{{tier:" not in text and "`[structural]`" in text


# ── drift is a property of the content, not of a version number (#37) ───────

def test_a_content_change_at_the_same_version_is_reported_as_stale(project):
    """The #37 bug, directly.

    `__version__` has never been bumped, so a version-equality check reported
    nothing while the rendered skill changed by 59 lines. Drift has to be
    decided by comparing content.
    """
    from revenant import __version__
    skill = project / ".claude" / "skills" / "re" / "SKILL.md"
    assert cli.harness_drift(str(project)) == "", "a fresh render is current"

    # What an older build left behind: a body this build would not produce,
    # under a stamp of the shape that build wrote -- version only, no digest,
    # and the *same* version string, because this package has never bumped it.
    older = _describe.render_skill(_describe.describe(include_project=True))
    older = older.replace("## Evidence rules", "## Evidence rules (older wording)")
    older = "\n".join(
        _describe.stamp(__version__) if line.startswith(_describe.STAMP_PREFIX) else line
        for line in older.splitlines()) + "\n"
    skill.write_text(older)
    assert _describe.stamped_version(older) == __version__

    # Red before #37: the version strings are equal, so a version-equality
    # check saw nothing here.
    drift = cli.harness_drift(str(project))
    assert "SKILL.md" in drift and "stale" in drift.lower()
    assert not _describe.stamped_digest(older), "a pre-#37 stamp carries no digest"


def test_a_render_failure_is_reported_not_answered_as_current(project, monkeypatch):
    """A guard that cannot run must say so.

    A renderer raising (a template naming an unknown tier, say) is what the
    guards exist to catch; answering "current" to a check that never ran is the
    blindness #37 is about.
    """
    def boom(*a, **k):
        raise ValueError("re-deep.md names unknown tier 'speculation'")
    monkeypatch.setattr(_describe, "render", boom)
    drift = cli.harness_drift(str(project))
    assert "could not re-render" in drift and "unknown tier" in drift
    assert "REVENANT_PROJECT" not in drift


def test_status_prints_one_line_per_outcome(project, monkeypatch, capsys):
    skill = project / ".claude" / "skills" / "re" / "SKILL.md"
    skill.write_text(skill.read_text() + "\nMY OWN NOTE\n")          # edited by hand
    (project / ".claude" / "commands" / "re-map.md").unlink()         # not rendered
    monkeypatch.chdir(project)
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    reported = [ln for ln in out.splitlines() if "edited by hand" in ln or "not rendered" in ln]
    assert len(reported) == 2, f"one line per outcome, got: {reported}"
    label = next(ln for ln in out.splitlines() if "agent skill" in ln)
    assert all(ln.index("edited by hand" if "edited" in ln else "not rendered")
               == label.index("edited by hand") for ln in reported), "aligned under the value column"


def test_a_hand_edited_file_is_reported_differently_from_an_older_build(project):
    """Both need a re-render, but only one of them loses work by doing it."""
    skill = project / ".claude" / "skills" / "re" / "SKILL.md"
    skill.write_text(skill.read_text() + "\nMY OWN NOTE\n")
    drift = cli.harness_drift(str(project))
    assert "SKILL.md" in drift
    assert "hand" in drift.lower() and "stale" not in drift.lower()


def test_the_stamp_carries_both_the_version_and_a_content_digest(project):
    skill = (project / ".claude" / "skills" / "re" / "SKILL.md").read_text()
    from revenant import __version__
    assert _describe.stamped_version(skill) == __version__
    digest = _describe.stamped_digest(skill)
    assert digest and digest == _describe.content_digest(skill)


def test_an_unstamped_file_is_still_reported(project):
    (project / ".claude" / "skills" / "re" / "SKILL.md").write_text("# mine\n")
    assert "hand-written" in cli.harness_drift(str(project))


def test_re_acquire_encodes_the_method_not_a_site(project):
    """Channel: acquisition (#39). The durable half is identification and
    verification; the mirror's own mechanics are left to the agent, because
    baking one site's private token flow into a shipped template is the same
    over-fitting ADR-0002 called out in the fingerprint weights."""
    text = _rendered_files(project)[".claude/commands/re-acquire.md"]
    assert _describe.stamped_version(text) == _describe.__version__
    # The clone trap and the four checks are the point of the file.
    for must in ("global-metadata.dat", "config.*.apk", r"PK\x03\x04", "revenant fingerprint"):
        assert must in text, f"re-acquire lost its verification step: {must}"
    # A rule, not a blacklist: no URL and no bare host may be written down at
    # all. Mirrors change their pages and their download mechanics constantly;
    # freezing one site's private flow into a shipped template is the
    # over-fitting ADR-0002 called out in the fingerprint weights.
    assert "://" not in text, "re-acquire writes down a URL"
    hosts = re.findall(r"\b[a-z0-9-]+\.(?:com|net|org|io|app|co|cn|io)\b", text.lower())
    assert not hosts, f"re-acquire names a host: {hosts}"


def test_the_document_teaches_the_shape_of_a_memory_entry(project):
    """Same bargain as the markers above: rules that fire against a format
    nobody was taught produce findings nobody can act on. The pointer syntax is
    the whole format, so it is what gets taught."""
    text = _rendered(project)
    assert "→" in text and "memory.toml" in text
    m = _describe.describe().methodology
    assert "memory.toml" in m["notes"]["memory"]


def test_rendering_without_the_mcp_extra_says_the_tool_table_is_empty(project, monkeypatch, capsys):
    """The optional `harness` extra being absent makes `collect_mcp_tools()`
    return [], and the skill renders with the whole read-only tool table gone --
    silently. One repository regenerated its shared skill that way and would
    have dropped 22 rows for nine projects without a word. Same bargain as
    `no-index`: say what we could not see, never let it read as "there is none".
    """
    monkeypatch.setattr(_describe, "collect_mcp_tools", lambda: [])
    _describe.write_rendered(str(project), "claude", _describe.describe())
    assert "mcp" in capsys.readouterr().err.lower()


# ── the second harness (#68) ────────────────────────────────────────────────
#
# Two seams cover all of it, both already here: `describe.render(desc, target)`
# for what gets written, and `cli.main([...])` for what gets said. Nothing below
# reaches inside a renderer, so a renderer may be rewritten without touching a
# line of this.

CODEX = _describe.CodexRenderer


def test_codex_renders_a_skill_a_command_apiece_and_an_mcp_declaration(project):
    """The whole surface, in one place: what an external Codex user ends up with."""
    files = _rendered_files(project, "codex")
    assert set(files) == {
        ".codex/skills/re/SKILL.md",
        *(f".codex/skills/{name}/SKILL.md" for name in _describe.COMMAND_NAMES),
        ".codex/config.toml",
    }
    for rel, text in files.items():
        assert _describe.stamped_version(text) == _describe.__version__, rel
        assert _describe.stamped_digest(text) == _describe.content_digest(text), rel


def test_the_codex_skills_carry_the_front_matter_codex_selects_them_by(project):
    """Name and description are the whole of what reaches the model until it
    picks the file, so a command without them can never be picked."""
    files = _rendered_files(project, "codex")
    for name in ("re", *_describe.COMMAND_NAMES):
        text = files[f".codex/skills/{name}/SKILL.md"]
        head = text.split("---")[1].splitlines()
        assert f"name: {name}" in head, name
        description = next(ln for ln in head if ln.startswith("description: "))
        assert len(description) > len("description: ") + 20, f"{name}: description is a stub"


def test_a_codex_command_says_it_is_not_a_slash_command(project):
    """The cost taken deliberately in ADR-0001's revision: on Codex the model
    chooses the command from its description, so a person asking for one gets a
    request rather than the guarantee `/re-deep` gives on Claude Code. A reader
    who carries that guarantee across harnesses has been misled by silence."""
    files = _rendered_files(project, "codex")
    text = files[".codex/skills/re-deep/SKILL.md"]
    assert "not a slash command" in text
    # The body is the shipped template, unchanged. Asserted against a line only
    # the template has -- the preamble writes `$ARGUMENTS` itself, so looking
    # for that would pass with the whole body dropped.
    body = text.split("read them as what you were asked to work on, in that order.")[1]
    assert "re_find_asm" in body and "re_cfg" in body, "the template body is missing"
    assert "$ARGUMENTS" in text, "the template's placeholders need explaining, not hiding"


def test_the_codex_mcp_declaration_binds_to_the_interpreter_running_this(project):
    """Same bargain as `.mcp.json`: a bare `python` finds whichever build is on
    PATH, which is how a project ends up talking to a revenant it did not install."""
    import sys
    import tomllib
    text = _rendered_files(project, "codex")[".codex/config.toml"]
    parsed = tomllib.loads(text)                      # it has to be TOML at all
    assert parsed["mcp_servers"]["re"]["command"] == sys.executable
    assert parsed["mcp_servers"]["re"]["args"] == ["-m", "revenant.mcp_server"]
    # No permissions: a declaration that does nothing until a trust step the
    # user has not taken is more misleading than none (ADR-0001, fourth point).
    assert "sandbox_mode" not in text and "approval_policy" not in text


def test_the_codex_skill_teaches_the_same_methodology_as_the_claude_one(project):
    """One `Description`, two renderers: the vocabulary cannot fork.

    Not "the files are identical" -- they are not, and should not be -- but
    every fact the methodology defines has to reach both.
    """
    text = _rendered_files(project, "codex")[CODEX.SKILL]
    for tier in _m.TIERS:
        assert f"`{tier}`" in text, tier
    for state in _m.STATES:
        assert f"`{state}`" in text, state
    assert "re-state" in text and "re-rests-on" in text and "expect=" in text
    assert "memory.toml" in text and "→" in text
    # And it points at its own overlay, not at Claude Code's.
    assert "AGENTS.md" in text
    assert "re-project" not in text


# Byte-for-byte: what the Claude renderer produced before the second harness
# existed. Recorded, not derived, because the point is to catch a change made
# here -- and a check computed from the same code it is checking cannot.
# Changing one of these is allowed; doing it by accident is what is not.
CLAUDE_DIGESTS = {
    ".claude/commands/re-acquire.md": "60523a2437a7",
    ".claude/commands/re-boundary.md": "89d32eda9f3f",
    ".claude/commands/re-deep.md": "dcf9e90bdb63",
    ".claude/commands/re-map.md": "6fb24b049caa",
    ".claude/commands/re-scaffold.md": "f0b4eb4ebe74",
    ".claude/commands/re-verify.md": "84281646ae78",
    ".claude/skills/re/SKILL.md": "d0222d5c701b",
}


def test_the_claude_render_is_byte_for_byte_what_it_always_was():
    """A second harness must not cost the first one a re-verification.

    Same discipline as the human lint report: adding a renderer may not quietly
    reformat the one that was already there. Every existing project would
    otherwise be told its files had drifted, by a change that meant nothing.
    """
    import hashlib
    desc = _describe.describe(include_project=False)
    if not desc.mcp_tools:
        pytest.skip("the optional `harness` extra is absent, so the tool table is empty")
    got = {rel: hashlib.sha256(text.encode()).hexdigest()[:12]
           for rel, text in _describe.render(desc, "claude").items()}
    assert got == CLAUDE_DIGESTS


def test_describe_render_codex_writes_the_files_and_says_what_you_must_do(project, monkeypatch, capsys):
    monkeypatch.chdir(project)
    assert cli.main(["describe", "--render", "codex"]) == 0
    out = capsys.readouterr().out
    assert (project / CODEX.SKILL).exists()
    assert (project / ".codex" / "config.toml").exists()
    # The two costs that are invisible from the files themselves.
    assert "trust" in out.lower(), "the MCP entry does nothing until the repo is trusted"
    assert "not slash commands" in out
    assert "codex mcp add" in out, "the official route, not only the hand-edit"
    # And the overlay it will never touch.
    assert "AGENTS.md" in out


def test_if_stale_installs_a_harness_the_project_does_not_have_yet(project, monkeypatch, capsys):
    """`--if-stale` is the upgrade-then-re-render loop (#32), meant to be safe to
    run unconditionally. "No drift" and "not installed" are different facts and
    the drift check answers [] to both, so asking it alone reports success while
    installing nothing -- which is exactly what an existing Claude-only project
    upgrading into Codex would hit."""
    import shutil
    shutil.rmtree(project / ".codex")
    monkeypatch.chdir(project)

    assert cli.main(["describe", "--render", "codex", "--if-stale"]) == 0
    assert "rendered" in capsys.readouterr().out
    assert (project / CODEX.SKILL).exists()

    assert cli.main(["describe", "--render", "codex", "--if-stale"]) == 0
    assert "current" in capsys.readouterr().out


def test_the_trust_line_carries_the_line_you_have_to_add(project, tmp_path, monkeypatch, capsys):
    """"Not trusted" without the line to paste leaves the reader to derive a
    TOML table name and a quoted absolute path from a sentence."""
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    lines = cli.codex_trust_lines(str(project))
    joined = "\n".join(lines)
    assert 'trust_level = "trusted"' in joined
    assert f'[projects.{json.dumps(str(project))}]' in joined
    assert "codex mcp add" in joined


def test_init_lays_down_both_harnesses(project):
    for rel in _describe.rendered_paths("claude") + _describe.rendered_paths("codex"):
        assert (project / rel).exists(), rel
    assert cli.harness_drift(str(project), "codex") == ""


def test_the_codex_overlay_is_created_once_and_never_written_to_again(project):
    """`AGENTS.md` is the user's, and often already theirs before revenant ran.
    `--force` restores revenant's own scaffolding; it does not reach this."""
    from revenant.init import init_project
    agents = project / "AGENTS.md"
    assert agents.exists()
    agents.write_text("MY OWN CONVENTIONS\n")
    init_project(str(project), force=True, quiet=True)
    assert agents.read_text() == "MY OWN CONVENTIONS\n"


def test_an_existing_agents_md_is_not_touched_by_init(tmp_path):
    """The user who already writes an AGENTS.md loses not one word of it."""
    from revenant.init import init_project
    root = tmp_path / "mine"
    root.mkdir()
    (root / "AGENTS.md").write_text("# mine\n")
    init_project(str(root), quiet=True)
    assert (root / "AGENTS.md").read_text() == "# mine\n"


def test_the_codex_overlay_has_a_budget_and_lint_checks_it(project, monkeypatch, capsys):
    """`AGENTS.md` is read in full on every turn, which is ADR-0005's judgement
    for putting a file under a budget. A budget nothing acts on is not one, so
    the registration is what `init` writes rather than what a doc suggests.

    `kind = "overlay"`, the word ADR-0005 already has for prose about one title:
    weighed, never asked for claim-and-pointer entries.
    """
    import tomllib
    from revenant import describe as d
    registry = project / ".claude" / "agent-memory" / "memory.toml"
    files = tomllib.loads(registry.read_text())["files"]
    assert files["AGENTS.md"] == {"kind": "overlay", "bytes": d.AGENTS_MD_BUDGET}
    assert d.AGENTS_MD_BUDGET < d.CODEX_PROJECT_DOC_MAX_BYTES, "the cap is on the sum"

    (project / "AGENTS.md").write_text("x" * (d.AGENTS_MD_BUDGET + 1))
    monkeypatch.chdir(project)
    assert cli.main(["lint", "--repo"]) == 0
    out = capsys.readouterr().out
    assert "memory-over-budget" in out
    assert "memory-entry-without-pointer" not in out, "an overlay is prose, not entries"


def test_the_budget_is_registered_where_lint_reads_it(tmp_path, monkeypatch, capsys):
    """ADR-0005 puts the table at the *repository* root with repository-relative
    keys, and that is the only place `lint --repo` looks. A table written beside
    the project is one no sweep ever reads -- the unenforced budget again, which
    is the whole thing ADR-0005 exists to end.
    """
    import tomllib
    from revenant import describe as d
    from revenant.init import init_project
    repo = tmp_path / "merge-games-re"
    (repo / ".git").mkdir(parents=True)
    init_project(str(repo / "love-and-pies"), quiet=True)

    registry = repo / ".claude" / "agent-memory" / "memory.toml"
    assert registry.exists(), "written at the repository root, not beside the project"
    assert not (repo / "love-and-pies" / ".claude" / "agent-memory").exists()
    files = tomllib.loads(registry.read_text())["files"]
    assert files["love-and-pies/AGENTS.md"]["bytes"] == d.AGENTS_MD_BUDGET

    (repo / "love-and-pies" / "AGENTS.md").write_text("x" * (d.AGENTS_MD_BUDGET + 1))
    monkeypatch.chdir(repo)
    assert cli.main(["lint", "--repo"]) == 0
    assert "memory-over-budget" in capsys.readouterr().out


def test_a_second_project_is_told_the_line_to_add_rather_than_having_it_written(
        tmp_path, capsys):
    """The table is the repository's and holds the projects beside this one, so
    revenant does not rewrite it. Saying nothing would be the same unenforced
    budget arriving quietly, so the line to paste is printed instead."""
    from revenant.init import init_project
    repo = tmp_path / "merge-games-re"
    (repo / ".git").mkdir(parents=True)
    init_project(str(repo / "love-and-pies"), quiet=True)
    capsys.readouterr()

    init_project(str(repo / "travel-town"), quiet=False)
    out = capsys.readouterr().out
    assert 'travel-town/AGENTS.md" = { kind = "overlay"' in out
    assert "lint --repo" in out
    # And the first project's entry is still the only one on disk.
    registry = repo / ".claude" / "agent-memory" / "memory.toml"
    assert "travel-town" not in registry.read_text()


def test_drift_covers_the_codex_files_too(project):
    from revenant import __version__
    skill = project / ".codex" / "skills" / "re-deep" / "SKILL.md"
    skill.write_text(skill.read_text().replace(f"version={__version__}", "version=0.0.1"))
    drift = cli.harness_drift(str(project), "codex")
    assert "re-deep" in drift and "0.0.1" in drift and "--render codex" in drift
    assert cli.harness_drift(str(project)) == "", "and says nothing about the other harness"

    (project / ".codex" / "config.toml").unlink()
    assert "not rendered" in cli.harness_drift(str(project), "codex")


def test_a_hand_edited_codex_file_is_pointed_at_the_codex_overlay(project):
    """Re-rendering discards the edit, so the line has to name the file that
    survives -- and on Codex that is AGENTS.md, not the Claude overlay."""
    toml = project / ".codex" / "config.toml"
    toml.write_text(toml.read_text() + '\nmodel = "mine"\n')
    drift = cli.harness_drift(str(project), "codex")
    assert "edited by hand" in drift and "AGENTS.md" in drift


def test_status_reports_each_installed_harness_and_stays_quiet_about_the_others(project, monkeypatch, capsys):
    import shutil
    monkeypatch.chdir(project)
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "agent skill (claude)" in out and "agent skill (codex)" in out

    shutil.rmtree(project / ".codex")
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "agent skill (claude)" in out
    assert "codex" not in out.lower(), "a project not on Codex hears nothing about Codex"


def test_status_says_when_the_mcp_declaration_is_there_but_the_repo_is_untrusted(
        project, tmp_path, monkeypatch, capsys):
    """The one thing revenant will not do for you, reported rather than done.

    Trust means "I allow this repository to start processes"; a tool granting
    itself that points the wrong way, and revenant writes inside the project
    directory and nowhere else.
    """
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.chdir(project)

    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    line = next(ln for ln in out.splitlines() if ".codex/config.toml" in ln)
    assert "ignores it" in line, "say what the consequence is, not only that a file is missing"
    assert str(codex_home) in line, "and which file would have to say so"
    assert "codex mcp add" in line, "the remedy, with the paths already filled in"

    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(project.resolve()))}]\ntrust_level = "trusted"\n')
    assert cli.main(["status"]) == 0
    assert "codex mcp add" not in capsys.readouterr().out


def test_rendering_codex_without_the_mcp_extra_says_the_tool_table_is_empty(
        project, monkeypatch, capsys):
    """The same warning on both harnesses. A Codex user regenerating from a venv
    without the extra would otherwise get a skill silently missing 22 rows."""
    monkeypatch.setattr(_describe, "collect_mcp_tools", lambda: [])
    _describe.write_rendered(str(project), "codex", _describe.describe())
    assert "mcp" in capsys.readouterr().err.lower()


def test_init_writes_nothing_into_your_home_directory(tmp_path, monkeypatch):
    """Uninstalling revenant has to be clean, and the trust step is the user's.

    Both promises rest on the same fact -- nothing revenant writes is outside
    the repository it was pointed at -- so it is checked rather than remembered.
    `$CODEX_HOME` in particular is read and never written: granting a repository
    the right to start processes is the user's call to make.
    """
    from revenant.init import init_project
    home = tmp_path / "home"
    codex_home = tmp_path / "home" / ".codex"
    codex_home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    before = {p for p in home.rglob("*")}

    init_project(str(tmp_path / "proj-elsewhere"), quiet=True)

    assert {p for p in home.rglob("*")} == before
