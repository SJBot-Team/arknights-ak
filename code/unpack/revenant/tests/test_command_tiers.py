"""The four-tier command table (ADR-0002), and what each surface shows.

The point of these tests is the *default* surface: a newcomer running
`revenant help` sees the fourteen core commands and nothing else, the frozen
scan family appears only once a pack is enabled, and the removed commands say
where they went instead of vanishing.
"""

from __future__ import annotations

import os
import re

import pytest

from revenant import cli, describe as _describe


@pytest.fixture
def project(tmp_path, monkeypatch):
    from revenant.init import init_project
    root = tmp_path / "proj"
    init_project(str(root), quiet=True)
    monkeypatch.setenv("REVENANT_PROJECT", str(root))
    monkeypatch.chdir(root)
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()
    config._IDENTITY_CACHE.clear()
    config.set_platform(None)
    yield root
    config._PROJECT_CONFIG_CACHE.clear()


def _enable_example_pack(project):
    text = (project / "revenant.toml").read_text()
    (project / "revenant.toml").write_text(text + '\n[packs]\nenabled = ["example"]\n')
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()


CORE = {
    "init", "status", "prepare", "find-binary", "find-metadata", "import-metadata",
    "patch-binary", "lua-extract", "seed-src", "fingerprint", "dig", "lint",
    "describe", "help",
}
EXTENSION = {"packs", "probe", "cell", "ledger", "scan", "naming-stats"}
REMOVED = {"workspace", "narrow", "baseline",
           "build-indices", "run-cpp2il", "ls-apk", "extract-apks"}


# ── the table itself ────────────────────────────────────────────────────────

def test_every_dispatchable_command_has_exactly_one_tier():
    for name in cli.command_table():
        assert cli.command_tier(name) in (cli.TIER_CORE, cli.TIER_QUERY, cli.TIER_EXTENSION), name


def test_the_core_tier_is_the_fourteen_from_the_adr():
    assert {n for n in cli.command_table() if cli.command_tier(n) == cli.TIER_CORE} == CORE
    assert len(CORE) == 14


def test_the_extension_tier_is_the_frozen_scan_family():
    assert {n for n in cli.command_table() if cli.command_tier(n) == cli.TIER_EXTENSION} == EXTENSION


def test_removed_commands_are_not_dispatchable_but_say_where_they_went(project, capsys):
    for name in REMOVED:
        assert name not in cli.command_table()
        assert cli.command_tier(name) == cli.TIER_REMOVED
        assert cli.main([name]) == 2
        out = capsys.readouterr()
        assert "ADR-0002" in out.err or "prepare --only" in out.err, name


def test_the_merged_prep_steps_point_at_prepare_only(project, capsys):
    cli.main(["build-indices"])
    assert "prepare --only build-indices" in capsys.readouterr().err


# ── help ────────────────────────────────────────────────────────────────────

_LISTED = re.compile(r"^  ([a-z][a-z-]*)", re.M)


def _listed(text: str) -> set:
    return set(_LISTED.findall(text))


def test_help_lists_exactly_the_core_commands(project, capsys):
    assert cli.main(["help"]) == 0
    listed = _listed(capsys.readouterr().out)
    assert listed == CORE


def test_help_all_adds_the_query_tier(project, capsys):
    cli.main(["help", "--all"])
    listed = _listed(capsys.readouterr().out)
    assert CORE < listed
    assert {"disasm", "evidence", "lua-grep", "cfg"} <= listed
    assert not (listed & EXTENSION), "no pack enabled, so the frozen family stays hidden"


def test_extension_commands_appear_only_when_a_pack_is_enabled(project, capsys):
    cli.main(["help"])
    assert not (_listed(capsys.readouterr().out) & EXTENSION)
    _enable_example_pack(project)
    cli.main(["help"])
    assert EXTENSION <= _listed(capsys.readouterr().out)


def test_a_hidden_command_still_runs(project, capsys):
    """Hidden is not disabled: `help --all` commands and the frozen family stay
    dispatchable -- frozen is not deleted."""
    assert cli.main(["packs"]) == 0
    assert "lua-list" in cli.command_table()


# ── describe and the rendered skill follow the same rule ────────────────────

def test_describe_hides_the_frozen_family_until_a_pack_is_enabled(project):
    names = _describe.describe().command_names()
    assert CORE <= names
    assert not (names & EXTENSION)
    assert not (names & REMOVED)

    _enable_example_pack(project)
    assert EXTENSION <= _describe.describe().command_names()


def test_the_description_json_carries_no_scan_family_without_a_pack(project):
    payload = _describe.as_json(_describe.describe())
    # `cell_states` / `gap_markers` left this list in ADR-0003: they describe
    # what we know about a question, note or slot alike. The pack machinery --
    # the command, the ledger contract, the six facets -- did not.
    for word in ("revenant cell", "fact_fields", "facets"):
        assert word not in payload, word
    _enable_example_pack(project)
    payload = _describe.as_json(_describe.describe())
    assert "cell_states" in payload and "fact_fields" in payload


def test_the_four_states_are_taught_without_any_pack(project):
    """The states answer "what do we know about this question", which is true of
    a note as much as of a pack slot -- Cell is only one carrier (ADR-0003). An
    agent that cannot see the vocabulary cannot write a `re-state` marker."""
    payload = _describe.as_json(_describe.describe())
    for word in ("cell_states", "reach_sources", "gap_markers",
                 "out_of_reach", "input_missing", "server_side"):
        assert word in payload, word


def test_ungating_the_states_does_not_open_the_frozen_family(project):
    """The guard that matters. Facets are pack machinery -- six fixed sections
    per slot -- and stay behind the gate with the rest of the scan family."""
    payload = _describe.as_json(_describe.describe())
    assert "facets" not in payload
    assert "fact_fields" not in payload
    for word in ("revenant cell", "revenant scan", "revenant probe"):
        assert word not in payload, word
    assert not (_describe.describe().command_names() & EXTENSION)


def test_the_rendered_skill_teaches_the_states_but_not_the_facets(project):
    text = _describe.render_skill(_describe.describe())
    assert "out_of_reach" in text
    assert "## Facets" not in text
    assert "## The ledger" not in text


def test_the_rendered_skill_never_mentions_the_frozen_family_without_a_pack(project):
    text = _describe.render_skill(_describe.describe())
    for name in EXTENSION | REMOVED:
        assert not re.search(rf"`revenant {name}\b", text), name
    # and no scan-family section either
    assert "## The ledger" not in text
    assert "## Facets" not in text


def test_the_rendered_skill_teaches_the_family_once_a_pack_is_enabled(project):
    _enable_example_pack(project)
    text = _describe.render_skill(_describe.describe())
    assert "`revenant cell`" in text
    assert "## The ledger" in text
    assert "## Facets" in text


def test_every_command_in_the_description_carries_its_tier(project):
    for cmd in _describe.describe().commands:
        assert cmd["tier"] in (cli.TIER_CORE, cli.TIER_QUERY, cli.TIER_EXTENSION)


# ── prepare --only ──────────────────────────────────────────────────────────

def test_prepare_only_runs_one_named_step(project, capsys, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_step_build_indices", lambda parsed: calls.append("bi") or 0)
    assert cli.main(["prepare", "--only", "build-indices"]) == 0
    assert calls == ["bi"]


def test_prepare_only_rejects_an_unknown_step(project, capsys):
    assert cli.main(["prepare", "--only", "frobnicate"]) == 2
    err = capsys.readouterr().err
    assert "extract-apks" in err and "seed-src" in err


# ── status proxy alarms ─────────────────────────────────────────────────────

def test_status_reports_the_proxy_metrics_without_blocking(project, capsys):
    skill = project / ".claude" / "skills" / "re" / "SKILL.md"
    skill.write_text(skill.read_text() + "\n" * 200)
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"skill .*\d+ lines.*> 80", out)


def test_proxy_alarms_come_from_one_place():
    alarms = cli.proxy_alarms(skill_lines=10, default_commands=14, terms=6)
    assert alarms == []
    alarms = cli.proxy_alarms(skill_lines=81, default_commands=16, terms=7)
    assert len(alarms) == 3
    assert all("ADR-0002" in a for a in alarms)


# ── argument splitting: switches must not eat the next word ─────────────────

def test_a_switch_does_not_swallow_the_positional_after_it():
    """`list-bundles --types MetaScenes` is a switch and a group. Reading the
    group as the switch's value drops it, and the census then runs over every
    bundle in the package instead of one group."""
    positional, opts = cli._split_args(
        ["--types", "MetaScenes", "--root", "assets/aa/android", "--limit=5"],
        boolean=("types",))
    assert positional == ["MetaScenes"]
    assert opts == {"types": "1", "root": "assets/aa/android", "limit": "5"}


def test_a_value_flag_still_takes_its_value():
    positional, opts = cli._split_args(["Env", "one", "--unity-version", "2022.3.62f1"],
                                       boolean=("by-script",))
    assert positional == ["Env", "one"]
    assert opts["unity-version"] == "2022.3.62f1"
    assert cli._split_args(["--by-script"], boolean=("by-script",)) == ([], {"by-script": "1"})


# ── status: project scripts a built-in has replaced ─────────────────────────

def test_superseded_tools_names_the_copy_and_what_replaced_it(tmp_path):
    tools = tmp_path / "res" / "_tools"
    tools.mkdir(parents=True)
    (tools / "dump_strlit.py").write_text("# an old copy")
    (tools / "ab_probe.py").write_text("# another")
    lines = cli.superseded_tools(str(tmp_path))
    assert len(lines) == 2
    joined = "\n".join(lines)
    assert "res/_tools/dump_strlit.py" in joined and "revenant strings" in joined
    assert "list-bundles --types" in joined
    assert "#50" in joined


def test_the_two_kinds_of_replacement_ask_for_different_things(tmp_path):
    """A command replaces the file; an importable construct replaces its body.
    Reading both as "delete it" throws away the game facts the file still holds."""
    tools = tmp_path / "_tools"
    tools.mkdir(parents=True)
    (tools / "dump_strlit.py").write_text("# a copy")
    (tools / "wrap_pe.py").write_text("# a copy")
    by_script = {line.split()[0]: line for line in cli.superseded_tools(str(tmp_path))}
    assert "delete the copy" in by_script["_tools/dump_strlit.py"]
    assert "thin wrapper" in by_script["_tools/wrap_pe.py"]


def test_a_copy_that_already_imports_the_builtin_is_left_alone(tmp_path):
    """A wrapper entry has to be able to go quiet, or the alarm outlives the fix
    it asked for and everyone learns to ignore it."""
    tools = tmp_path / "_tools"
    tools.mkdir(parents=True)
    (tools / "wrap_pe.py").write_text("from revenant.contrib.decrypt import wrap_pe\n")
    assert cli.superseded_tools(str(tmp_path)) == []
    # a command entry is not the same bargain: the file has no reason to survive
    (tools / "dump_strlit.py").write_text("from revenant import strings\n")
    assert len(cli.superseded_tools(str(tmp_path))) == 1


def test_only_reaching_for_the_thing_that_replaced_it_counts(tmp_path):
    """Otherwise any script that reaches for some unrelated built-in silences the
    alarm on a body it never replaced -- and a copy that merely names revenant in
    a comment silences it too."""
    tools = tmp_path / "_tools"
    tools.mkdir(parents=True)
    (tools / "findvm.py").write_text("from revenant import strings   # not the replacement\n")
    assert len(cli.superseded_tools(str(tmp_path))) == 1
    (tools / "findvm.py").write_text("# ported from revenant.contrib.decrypt.findvm\n")
    assert len(cli.superseded_tools(str(tmp_path))) == 1, "a mention is not an import"
    # how the real wrapper is written: the package re-exports the symbol
    (tools / "findvm.py").write_text("from revenant.contrib.decrypt import find_dispatcher\n")
    assert cli.superseded_tools(str(tmp_path)) == []


def test_superseded_tools_stays_quiet_about_game_specific_scripts(tmp_path):
    """The reverse test. A mapping table is easy to write so that it never
    matches; it is equally easy to write one that flags everything, and both
    failures look like silence or noise rather than an error."""
    tools = tmp_path / "res" / "_tools"
    tools.mkdir(parents=True)
    # `ab_experiments.py` used to be one of these. #48 absorbed its parsing
    # half into `contrib.experiments`, so it is a BY_IMPORT entry now and this
    # list needed a script that is still game-specific end to end.
    for name in ("decrypt_conf.py", "fetch_ucd.py", "mergepath_stats.py",
                 "guid_names.py"):
        (tools / name).write_text("# a fact about this title")
    assert cli.superseded_tools(str(tmp_path)) == []
    assert cli.superseded_tools(str(tmp_path / "nowhere")) == []


def test_every_superseded_entry_points_at_something_that_exists():
    """A table that outlives what it points at is worse than no table: it sends
    people to a command that is gone."""
    import importlib
    table = cli.command_table()
    for script, entry in cli.SUPERSEDED_TOOLS.items():
        assert script.endswith(".py"), script
        assert entry.kind in (cli.BY_COMMAND, cli.BY_IMPORT), script
        if entry.kind == cli.BY_COMMAND:
            words = entry.replacement.split()
            assert words[0] == "revenant", entry.replacement
            assert words[1] in table, f"{script} points at a command that does not exist"
        else:
            assert entry.replacement.startswith("revenant."), entry.replacement
            importlib.import_module(entry.replacement)


# ── status: the workspace-shared _tools/ one level up ───────────────────────

def test_the_shared_tools_directory_one_level_up_is_scanned_too(tmp_path):
    """Nine projects share a `_tools/` above them all. The workspace root has no
    `revenant.toml`, so `status` never runs there and this half of the recurrence
    went unseen through a whole audit (#50).

    The scripts sit one folder inside it -- `_tools/cdph-vm/findvm.py` -- because
    each shared tool is a small project of its own. Reading only the top of
    `_tools/` finds nothing but directories, which is silence that looks exactly
    like cleanliness.
    """
    project = tmp_path / "some-title"
    (project / "res").mkdir(parents=True)
    shared = tmp_path / "_tools" / "cdph-vm"
    shared.mkdir(parents=True)
    (shared / "findvm.py").write_text("# the workspace copy, 78 lines to revenant's 84")
    lines = cli.superseded_tools(str(project))
    assert len(lines) == 1
    assert "findvm.py" in lines[0] and "revenant.contrib.decrypt.findvm" in lines[0]
    assert cli.SHARED_TAG in lines[0], "a reader must not go looking in this project for it"


def test_the_shared_directory_does_not_crowd_out_the_projects_own(tmp_path):
    project = tmp_path / "some-title"
    own = project / "_tools"
    own.mkdir(parents=True)
    shared = tmp_path / "_tools"
    shared.mkdir()
    (own / "pbschema.py").write_text("# this project's copy")
    (shared / "wrap_pe.py").write_text("# the shared copy")
    lines = cli.superseded_tools(str(project))
    assert len(lines) == 2
    assert [cli.SHARED_TAG in line for line in lines] == [False, True], "own first, shared after"


def test_no_shared_tools_directory_means_silence(tmp_path):
    """A project cloned out on its own has no workspace above it and must not
    be told about a directory that is not there."""
    project = tmp_path / "lonely"
    (project / "_tools").mkdir(parents=True)
    (project / "_tools" / "pbschema.py").write_text("# only this one")
    lines = cli.superseded_tools(str(project))
    assert len(lines) == 1 and cli.SHARED_TAG not in lines[0]


def test_the_shared_scan_is_bounded_and_never_walks_the_workspace(tmp_path):
    """`status` is a status query. The workspace holds nine extracted game
    packages -- hundreds of thousands of files -- so the scan reads `_tools/` and
    its immediate children and stops."""
    project = tmp_path / "some-title"
    project.mkdir(parents=True)
    deep = tmp_path / "_tools" / "cdph" / "obj" / "Debug"
    deep.mkdir(parents=True)
    (deep / "wrap_pe.py").write_text("# two directories in: build output, not a tool")
    assert cli.superseded_tools(str(project)) == []
    # and the workspace's own game directories are never opened at all
    (tmp_path / "other-title" / "_tools").mkdir(parents=True)
    (tmp_path / "other-title" / "_tools" / "pbschema.py").write_text("# a sibling's copy")
    assert cli.superseded_tools(str(project)) == [], "a sibling project is not ours to report"


def test_status_reports_a_superseded_copy_without_blocking(project, capsys):
    tools = project / "res" / "_tools"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "recover_tags.py").write_text("# the copy #32 left behind")
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "recover_tags.py" in out and "revenant pb-tags" in out


# ── status: the generated harness may live one level up (#51) ───────────────

@pytest.fixture
def shared_repo(tmp_path, monkeypatch):
    """One git repository, one project inside it, generated files at the top.

    Exactly what `merge-games-re` did: nine byte-identical copies of the `re`
    skill deleted, one kept at the repository root, where Claude Code finds it
    for every project below. Built by rendering into the project and moving the
    files up, so the shared copy is a real render rather than a stand-in.
    """
    from revenant.init import init_project
    from revenant import config
    repo = tmp_path / "merge-games-re"
    (repo / ".git").mkdir(parents=True)
    project = repo / "love-and-pies"
    init_project(str(project), quiet=True)
    for rel in _describe.rendered_paths("claude"):
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        (project / rel).rename(dest)
    monkeypatch.setenv("REVENANT_PROJECT", str(project))
    monkeypatch.chdir(project)
    config._PROJECT_CONFIG_CACHE.clear()
    config._IDENTITY_CACHE.clear()
    config.set_platform(None)
    yield repo, project
    config._PROJECT_CONFIG_CACHE.clear()


def test_the_shared_generated_files_are_not_reported_as_missing(shared_repo):
    """The noisy half of #51. `not rendered:` was wrong *and* its remedy would
    have written the nine copies straight back."""
    repo, project = shared_repo
    assert _describe.harness_root(str(project)) == str(repo)
    assert cli.harness_drift_lines(str(project)) == []


def test_the_skill_line_proxy_counts_the_shared_copy(shared_repo):
    """The blind half, and the worse one: the alarm read a file that was no
    longer there, called it zero lines, and went quiet for good."""
    repo, project = shared_repo
    (repo / _describe.HARNESS_MARKER).write_text("x\n" * 200)
    alarms = cli.project_proxy_alarms(str(project))
    assert any("200 lines" in a and "> 80" in a for a in alarms), alarms


def test_a_projects_own_copy_wins_over_the_shared_one(shared_repo):
    repo, project = shared_repo
    (project / _describe.HARNESS_MARKER).parent.mkdir(parents=True, exist_ok=True)
    (project / _describe.HARNESS_MARKER).write_text("x\n" * 300)
    assert _describe.harness_root(str(project)) == str(project)
    assert any("300 lines" in a for a in cli.project_proxy_alarms(str(project)))


def test_a_project_on_its_own_behaves_exactly_as_before(project):
    """A single project cloned out finds nothing above it and gets itself back."""
    assert _describe.harness_root(str(project)) == str(project)
    assert cli.harness_drift_lines(str(project)) == []
    assert cli.harness_location(str(project)) == ""


def test_the_search_never_climbs_out_of_the_repository(shared_repo):
    """Claude Code stops at the repository root, so a copy above it is never
    loaded -- reading one would describe a loading behaviour that never happens.
    """
    repo, project = shared_repo
    outside = repo.parent
    for rel in _describe.rendered_paths("claude"):
        dest = outside / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).rename(dest)
    assert _describe.harness_root(str(project)) == str(project)
    assert "not rendered" in " ".join(cli.harness_drift_lines(str(project)))


def test_without_a_repository_root_the_search_does_not_walk_up(tmp_path):
    """No `.git` anywhere above means no boundary; reading a stranger's
    directory to decide what this project has is worse than missing a copy."""
    project = tmp_path / "loose" / "title"
    project.mkdir(parents=True)
    marker = tmp_path / "loose" / _describe.HARNESS_MARKER
    marker.parent.mkdir(parents=True)
    marker.write_text("# would be shared, if a repository said so\n")
    assert _describe.harness_root(str(project)) == str(project)


def test_one_shared_copy_serves_every_project_on_codex_as_well(shared_repo):
    """#51's arrangement is not Claude Code's alone (#68).

    Codex searches for `.codex/skills/` and concatenates `AGENTS.md` from the
    git root down, so a repository holding nine titles keeps one copy at the top
    there too -- and `init` in the tenth must not write the copy the other nine
    just stopped keeping.
    """
    from revenant.init import init_project
    repo, project = shared_repo
    for rel in _describe.rendered_paths("codex"):
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        (project / rel).rename(dest)
    assert _describe.harness_root(str(project), "codex") == str(repo)
    assert cli.harness_drift_lines(str(project), harness="codex") == []

    sibling = repo / "travel-town"
    init_project(str(sibling), quiet=True)
    assert not (sibling / ".codex").exists(), "the tenth project re-seeded the sharing"
    assert not (sibling / ".claude" / "skills" / "re").exists()
    # The overlay is per title and is not shared: "true here, wrong for the
    # next game" is the whole of what it is for.
    assert (sibling / "AGENTS.md").exists()


def test_status_says_which_layer_the_generated_files_are_on(shared_repo, capsys):
    """"current" with no location is a judgement about an unnamed file."""
    repo, project = shared_repo
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if "agent skill" in l)
    assert "current" in line
    assert ".." in line and cli.SHARED_TAG in line, line


def test_rendering_writes_to_the_shared_layer_not_a_second_copy(shared_repo, capsys):
    """User story 3: following what `status` says must not undo the sharing."""
    repo, project = shared_repo
    assert cli.main(["describe", "--render", "claude"]) == 0
    capsys.readouterr()
    for rel in _describe.rendered_paths("claude"):
        assert (repo / rel).exists(), rel
        assert not (project / rel).exists(), rel


def test_render_here_takes_a_project_out_of_the_shared_set(shared_repo):
    """The one deliberate way to get a local copy back."""
    repo, project = shared_repo
    assert cli.main(["describe", "--render", "claude", "--here"]) == 0
    assert (project / _describe.HARNESS_MARKER).exists()
    assert _describe.harness_root(str(project)) == str(project)
    assert cli.harness_drift_lines(str(project)) == []


def test_init_inside_a_shared_repository_makes_no_second_copy(shared_repo, capsys):
    """The tenth project joins the eight; it does not re-seed the ninth copy."""
    from revenant.init import init_project
    repo, _ = shared_repo
    tenth = repo / "tenth-title"
    assert init_project(str(tenth)) == 0
    out = capsys.readouterr().out
    for rel in _describe.rendered_paths("claude"):
        assert not (tenth / rel).exists(), rel
    assert cli.SHARED_TAG in out
    # the per-project overlay is not shared and is still written
    assert (tenth / ".claude" / "skills" / "re-project" / "SKILL.md").exists()
    assert (tenth / ".claude" / "settings.json").exists()


def test_two_projects_that_render_differently_are_not_called_stale(shared_repo):
    """A shared copy only works while every project renders the same skill. Let
    one enable a pack and it stops -- and the old classifier said "stale,
    generated by an earlier build (installed is 0.1.0): ... (0.1.0)", a sentence
    that contradicts itself, above a remedy that ping-pongs: re-rendering from
    this project rewrites the shared copy and breaks it for the one beside it.
    """
    repo, project = shared_repo
    _enable_example_pack(project)
    lines = cli.harness_drift_lines(str(project))
    joined = " ".join(lines)
    assert lines, "the shared copy no longer matches what this project renders"
    # the sentence that contradicted itself, gone
    assert "generated by an earlier build (installed is" not in joined, joined
    assert "not what this project renders" in joined, joined
    # both remedies, each with the condition that makes it the right one --
    # re-rendering alone would rewrite the neighbours' file to suit this project
    assert "--here" in joined, joined
    assert "want the same skill" in joined, joined


def test_a_projects_own_copy_that_lost_step_is_a_plain_re_render(project):
    """The same mismatch on a copy this project owns: nobody else can be hurt by
    a re-render, so that is the whole answer and `--here` would be noise."""
    _enable_example_pack(project)
    joined = " ".join(cli.harness_drift_lines(str(project)))
    assert "not what this project renders" in joined, joined
    assert "re-render with `revenant describe --render claude`" in joined, joined
    assert "--here" not in joined, joined


def test_a_genuinely_older_build_is_still_reported_as_stale(project):
    """The bucket the new one was carved out of has to keep working."""
    from revenant import __version__
    skill = project / _describe.HARNESS_MARKER
    text = skill.read_text().replace(f"version={__version__}", "version=0.0.1")
    skill.write_text(text)
    joined = " ".join(cli.harness_drift_lines(str(project)))
    assert "earlier build" in joined and "0.0.1" in joined, joined


def test_the_project_overlay_never_moves_up(shared_repo):
    """`re-project` holds "this title, not the next one"; sharing it would be
    the one thing it exists to prevent."""
    repo, project = shared_repo
    overlay = project / ".claude" / "skills" / "re-project" / "SKILL.md"
    assert overlay.exists()
    assert not (repo / ".claude" / "skills" / "re-project").exists()
    assert cli.main(["describe", "--render", "claude"]) == 0
    assert overlay.exists()
    assert not (repo / ".claude" / "skills" / "re-project").exists()


# ── table: the config-table corpus (#56) ────────────────────────────────────

def _table_corpus(project, name="Item", payload=None):
    import json
    corpus = project / "res" / "conf-json"
    corpus.mkdir(parents=True, exist_ok=True)
    rows = payload if payload is not None else {
        "items": {"1001": {"id": 1001, "cost": 5}, "1002": {"id": 1002, "tier": 2}}}
    (corpus / f"{name}.json").write_text(json.dumps(rows), encoding="utf-8")
    return corpus


def test_table_sits_in_the_query_tier_beside_the_other_decoders(project, capsys):
    assert cli.command_tier("table") == cli.TIER_QUERY
    cli.main(["help"])
    assert "table" not in _listed(capsys.readouterr().out)
    cli.main(["help", "--all"])
    assert "table" in _listed(capsys.readouterr().out)


def test_table_list_prints_the_rows_fields_and_the_reader_that_read_them(project, capsys):
    _table_corpus(project)
    assert cli.main(["table", "list"]) == 0
    out = capsys.readouterr().out
    assert "Item" in out
    assert "json-idmap" in out, "the reader is the column a wrong guess shows up in"
    assert re.search(r"Item\s+2\s+3\b", out), out


def test_table_list_reports_a_file_it_could_not_read_instead_of_skipping_it(project, capsys):
    corpus = _table_corpus(project)
    (corpus / "_index.json").write_text('{"version": 3, "built": "yes"}', encoding="utf-8")
    assert cli.main(["table", "list"]) == 0
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "_index" in out and "not a table" in out


def test_table_list_prints_a_long_name_whole(project, capsys):
    """The name column is how a table is passed back in. Clipping it to keep
    the columns tidy emits a name that resolves to nothing."""
    name = "AVeryLongTableNameThatGoesOnAndOnForeverAndEver"
    _table_corpus(project, name=name)
    assert cli.main(["table", "list"]) == 0
    assert name in capsys.readouterr().out


def test_table_list_with_nothing_to_list_says_where_to_point_it(project, capsys):
    assert cli.main(["table", "list"]) == 0
    assert "[tables] dirs" in capsys.readouterr().out


def test_configured_dirs_reach_a_corpus_the_sweep_would_not(project, capsys):
    import json
    from revenant import config
    odd = project / "elsewhere" / "cms"
    odd.mkdir(parents=True)
    (odd / "Order.json").write_text(json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8")
    text = (project / "revenant.toml").read_text()
    (project / "revenant.toml").write_text(text + '\n[tables]\ndirs = ["elsewhere/cms"]\n')
    config._PROJECT_CONFIG_CACHE.clear()
    assert cli.main(["table", "list"]) == 0
    out = capsys.readouterr().out
    assert "Order" in out and "json-rows" in out


def test_status_says_how_many_tables_and_corpora_this_project_has(project, capsys):
    _table_corpus(project)
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"config tables\s+: 1 file in 1 corpus", out), out
    assert "revenant table list" in out, "a noun with no entry point does not get used"


def test_status_says_so_when_there_are_no_tables(project, capsys):
    assert cli.main(["status"]) == 0
    assert re.search(r"config tables\s+: none found", capsys.readouterr().out)


# ── luban: the binary table decoder (#59) ───────────────────────────────────

def _uint(x: int) -> bytes:
    if x < 0x80:
        return bytes([x])
    return bytes([(x >> 8) | 0x80, x & 0xFF])


def _luban_blob() -> bytes:
    import struct
    row = _uint(1001) + _uint(6) + b"Energy" + struct.pack("<f", 1.5)
    return _uint(1) + row


def _luban_project(project, tables=None):
    import json
    (project / "luban.json").write_text(json.dumps({
        "beans": {"ItemConf": {"fields": [
            {"name": "id", "type": "int"},
            {"name": "name", "type": "string"},
            {"name": "cost", "type": "float"}]}},
        "tables": tables if tables is not None else {"tbitem": "ItemConf"},
    }))
    corpus = project / "res" / "conf"
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / "Item.json").write_text('{"items": {"1": {"id": 1}}}')
    (corpus / "tbitem.bytes").write_bytes(_luban_blob())
    return corpus


def test_luban_read_sits_in_the_query_tier(project, capsys):
    assert cli.command_tier("luban-read") == cli.TIER_QUERY
    cli.main(["help"])
    assert "luban-read" not in _listed(capsys.readouterr().out)
    cli.main(["help", "--all"])
    assert "luban-read" in _listed(capsys.readouterr().out)


def test_luban_read_decodes_a_blob_against_the_projects_schema(project, capsys):
    corpus = _luban_project(project)
    assert cli.main(["luban-read", str(corpus / "tbitem.bytes"),
                     "--schema", str(project / "luban.json")]) == 0
    captured = capsys.readouterr()
    assert '"name": "Energy"' in captured.out
    assert "1 rows, 3 fields, bean ItemConf" in captured.err


def test_luban_read_without_a_schema_prints_the_shape_of_one(project, capsys):
    corpus = _luban_project(project)
    assert cli.main(["luban-read", str(corpus / "tbitem.bytes")]) == 1
    err = capsys.readouterr().err
    assert "dynamic:Name" in err and "tables" in err


def test_luban_read_on_a_still_wrapped_blob_points_at_the_container(project, capsys):
    """Saying which step failed is the difference between "unwrap it first" and
    "your schema is wrong"."""
    corpus = _luban_project(project)
    (corpus / "tbitem.bytes").write_bytes(b"HEY\x01" + bytes(b ^ 0x5A for b in _luban_blob()))
    assert cli.main(["luban-read", str(corpus / "tbitem.bytes"),
                     "--schema", str(project / "luban.json")]) == 1
    err = capsys.readouterr().err
    assert "header" in err and "--container" in err


def test_luban_read_unwraps_with_the_container_the_project_supplies(project, capsys):
    """Both shipped titles wrap their tables, so a command that could only read
    plaintext could read neither of them."""
    corpus = _luban_project(project)
    (corpus / "tbitem.bytes").write_bytes(b"HEY\x01" + bytes(b ^ 0x5A for b in _luban_blob()))
    (project / "container.py").write_text(
        "def decode(data):\n    return bytes(b ^ 0x5A for b in data[4:])\n")
    assert cli.main(["luban-read", str(corpus / "tbitem.bytes"),
                     "--schema", str(project / "luban.json"),
                     "--container", str(project / "container.py")]) == 0
    assert '"name": "Energy"' in capsys.readouterr().out


def test_luban_read_says_which_beans_the_schema_knows_when_the_name_is_absent(project, capsys):
    corpus = _luban_project(project, tables={"tbother": "ItemConf"})
    assert cli.main(["luban-read", str(corpus / "tbitem.bytes"),
                     "--schema", str(project / "luban.json")]) == 1
    assert "tbother" in capsys.readouterr().err


def test_table_list_names_luban_as_the_reader_once_a_schema_is_configured(project, capsys):
    from revenant import config
    _luban_project(project)
    text = (project / "revenant.toml").read_text()
    (project / "revenant.toml").write_text(
        text + '\n[tables]\nluban_schema = "luban.json"\n')
    config._PROJECT_CONFIG_CACHE.clear()
    assert cli.main(["table", "list"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"tbitem\s+1\s+3\s+luban", out), out
    assert "with no reader yet" not in out, "both tables were read; the tally counts outcomes"


def test_table_list_offers_the_luban_route_when_blobs_go_unread(project, capsys):
    from revenant import tables
    _luban_project(project)
    assert cli.main(["table", "list"]) == 0
    out = capsys.readouterr().out
    assert f"binary ({tables.UNCLAIMED})" in out
    assert "luban_schema" in out, "the hint is the whole point of listing them"


# ── table census (#57) ──────────────────────────────────────────────────────

def test_table_census_prints_a_line_per_field(project, capsys):
    import json
    corpus = project / "res" / "conf-json"
    corpus.mkdir(parents=True)
    rows = {str(i): {"id": i, "cost": 31 if i < 8 else 10000001} for i in range(10)}
    (corpus / "MergeTapCost.json").write_text(json.dumps({"items": rows}))
    assert cli.main(["table", "census", "MergeTapCost"]) == 0
    out = capsys.readouterr().out
    assert "MergeTapCost -- 10 rows, 2 fields" in out
    assert re.search(r"cost\s+10/10\s+100%\s+2\s+31 ×8", out), out


def test_table_census_truncates_the_value_list_and_says_it_did(project, capsys):
    import json
    corpus = project / "res" / "conf-json"
    corpus.mkdir(parents=True)
    (corpus / "Big.json").write_text(json.dumps(
        {"rows": {str(i): {"v": i} for i in range(1200)}}))
    assert cli.main(["table", "census", "Big", "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "(+1197 more)" in out
    body = [line for line in out.splitlines() if line.startswith("v ")]
    assert len(body) == 1, "a thousand rows still print one line per field"


def test_table_census_works_on_a_luban_table_not_only_json(project, capsys):
    """Every reader `table list` knows, not just the JSON pair."""
    from revenant import config
    _luban_project(project)
    text = (project / "revenant.toml").read_text()
    (project / "revenant.toml").write_text(
        text + '\n[tables]\nluban_schema = "luban.json"\n')
    config._PROJECT_CONFIG_CACHE.clear()
    assert cli.main(["table", "census", "tbitem"]) == 0
    out = capsys.readouterr().out
    assert "(luban," in out
    assert re.search(r'name\s+1/1\s+100%\s+1\s+"Energy" ×1', out), out


def test_table_census_on_a_table_with_no_rows_says_so_rather_than_printing_nothing(
        project, capsys):
    import json
    corpus = project / "res" / "conf-json"
    corpus.mkdir(parents=True)
    (corpus / "Empty.json").write_text(json.dumps({"rows": []}))
    assert cli.main(["table", "census", "Empty"]) == 0
    assert "the table is empty" in capsys.readouterr().out


def test_table_census_on_rows_that_are_not_objects_says_that_instead(project, capsys):
    import json
    corpus = project / "res" / "conf-json"
    corpus.mkdir(parents=True)
    (corpus / "Scalars.json").write_text(json.dumps({"ids": [1, 2, 3]}))
    assert cli.main(["table", "census", "Scalars"]) == 0
    assert "values, not objects" in capsys.readouterr().out


def test_table_census_on_an_unknown_name_points_at_the_listing(project, capsys):
    assert cli.main(["table", "census", "NoSuch"]) == 1
    assert "table list" in capsys.readouterr().err


def test_table_census_with_no_argument_says_how_to_use_it(project, capsys):
    assert cli.main(["table", "census"]) == 1
    assert "Usage: table census" in capsys.readouterr().err


def test_an_unknown_table_action_lists_the_ones_there_are(project, capsys):
    assert cli.main(["table", "wat"]) == 2
    assert "list, census" in capsys.readouterr().err


# ── the FlatBuffers corpus end to end (#62) ─────────────────────────────────

def _fb_cms_project(project):
    """A project whose corpus holds a CMS `.bin` and the two keys to read it."""
    import json
    from tests.fixtures import flatbuffers_rows
    corpus = project / "res" / "cms-embedded"
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / "currencies.bin").write_bytes(
        flatbuffers_rows(2, names=["coin_0", "coin_1"]))
    (corpus / "Other.json").write_text('{"rows": {"1": {"id": 1}}}')
    (project / "cms.json").write_text(json.dumps({"classes": {
        "Game.CMS.Db": {"slots": 1, "fields": {
            "0": {"name": "Items", "fb_type": "offset", "cs_type": "Game.CMS.Item[]"}}},
        "Game.CMS.Item": {"slots": 2, "fields": {
            "0": {"name": "Id", "fb_type": "int32", "cs_type": "int"},
            "1": {"name": "Name", "fb_type": "offset", "cs_type": "string"}}}}}))
    text = (project / "revenant.toml").read_text()
    (project / "revenant.toml").write_text(
        text + '\n[tables]\nfb_schema = "cms.json"\n'
               '[tables.fb_roots]\ncurrencies = "Game.CMS.Db"\n')
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()
    return corpus


def test_table_list_names_flatbuffers_as_the_reader_and_counts_the_rows(project, capsys):
    _fb_cms_project(project)
    assert cli.main(["table", "list"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"currencies\s+2\s+2\s+flatbuffers", out), out


def test_table_census_works_on_a_flatbuffers_table(project, capsys):
    _fb_cms_project(project)
    assert cli.main(["table", "census", "currencies"]) == 0
    out = capsys.readouterr().out
    assert "(flatbuffers," in out
    assert re.search(r'Name\s+2/2\s+100%\s+2\s+"coin_0" ×1', out), out


def test_an_unread_blob_offers_both_routes_not_just_luban(project, capsys):
    corpus = project / "res" / "conf"
    corpus.mkdir(parents=True)
    (corpus / "Item.json").write_text('{"rows": {"1": {"id": 1}}}')
    (corpus / "mystery.bin").write_bytes(b"\x01\x02\x03\x04")
    assert cli.main(["table", "list"]) == 0
    out = capsys.readouterr().out
    assert "luban_schema" in out and "fb_roots" in out


def test_fbread_is_superseded_by_the_table_command_now(project, capsys):
    """#62 folds the script's whole job into `table`; what it really held --
    the CMS roots and the container convention -- becomes configuration."""
    tools = project / "_tools"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "fbread.py").write_text("# the shell #50 left behind\n")
    lines = cli.superseded_tools(str(project))
    assert len(lines) == 1
    assert "revenant table list" in lines[0]
    assert "delete the copy" in lines[0]
    assert "fb_roots" in lines[0]


# ── table diff (#63) ────────────────────────────────────────────────────────

def _diff_projects(tmp_path):
    """Two projects, same game, different codegen -- and one unrecovered tag."""
    import json
    from revenant.init import init_project
    out = []
    for name, style in (("hotel", "camel"), ("tasty", "pascal")):
        root = tmp_path / name
        init_project(str(root), quiet=True)
        corpus = root / "res" / "conf"
        corpus.mkdir(parents=True)
        rows = {}
        for i in range(4):
            rows[str(i)] = ({"id": i, "costId": [1], "gold": 100 + i}
                            if style == "camel" else
                            {"Id": i, "Cost_Id": ["01"], "Gold": 100 + i})
        if style == "pascal":
            rows["3"]["Gold"] = 999
            rows["9"] = {"Id": 9, "Cost_Id": ["01"], "Gold": 1}
        (corpus / "Currency.json").write_text(json.dumps({"rows": rows}))
        out.append(corpus / "Currency.json")
    return out


def test_table_diff_aligns_names_and_keeps_a_decode_mismatch_out_of_the_count(
        project, tmp_path, capsys):
    a, b = _diff_projects(tmp_path)
    assert cli.main(["table", "diff", str(a), str(b), "--normalize-names"]) == 0
    out = capsys.readouterr().out
    assert "keyed on 'id'" in out
    # not "3 the same": every row has a column nothing can compare, so none of
    # them is *known* to match -- claiming otherwise is the trap inverted
    assert re.search(r"rows\s+0 the same · 0 only in A · 1 only in B · 3 undetermined",
                     out), out
    assert "only in B: 9" in out, "which row, not just how many"
    assert "values    1 rows differ" in out
    assert "not comparable  costid" in out
    assert "NOT counted as content" in out, "the 929-row trap, said out loud"


def test_table_diff_without_normalising_offers_the_flag(project, tmp_path, capsys):
    a, b = _diff_projects(tmp_path)
    assert cli.main(["table", "diff", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "only in A: id" in out and "only in B: Id" in out
    assert "--normalize-names" in out


def test_table_diff_reads_each_side_with_its_own_projects_config(project, tmp_path):
    """A path into another title is read with that title's keys. Decoding one
    game's bytes against another game's schema produces rows, not an error."""
    from revenant import tables
    a, b = _diff_projects(tmp_path)
    assert tables.project_root_of(str(a)) == str(tmp_path / "hotel")
    assert tables.project_root_of(str(b)) == str(tmp_path / "tasty")


def test_table_diff_of_two_corpora_names_the_tables_each_side_has(project, tmp_path, capsys):
    """The by-product the ticket calls useful: one reference pair gave up 172
    new tables and 56 unique ones this way, with no code read."""
    import json
    a, b = _diff_projects(tmp_path)
    (a.parent / "OnlyHotel.json").write_text(json.dumps({"rows": {"1": {"id": 1}}}))
    (b.parent / "OnlyTasty.json").write_text(json.dumps({"rows": {"1": {"id": 1}}}))
    assert cli.main(["table", "diff", str(a.parent), str(b.parent)]) == 0
    out = capsys.readouterr().out
    assert "1 in both · 1 only in A · 1 only in B" in out
    assert "only in A  OnlyHotel" in out and "only in B  OnlyTasty" in out


def test_table_diff_refuses_a_negative_limit(project, tmp_path, capsys):
    """The bug `census` already wrote down: a negative reaches the slice as
    `[:-1]`, printing all but the last row and claiming `... -1 more`."""
    a, b = _diff_projects(tmp_path)
    assert cli.main(["table", "diff", str(a), str(b), "--limit", "-1"]) == 1
    assert "0 or more" in capsys.readouterr().err


def test_table_diff_says_so_when_the_limit_is_not_a_number(project, tmp_path, capsys):
    a, b = _diff_projects(tmp_path)
    assert cli.main(["table", "diff", str(a), str(b), "--limit", "lots"]) == 1
    assert "takes a number" in capsys.readouterr().err


def test_table_diff_needs_two_tables(project, capsys):
    assert cli.main(["table", "diff", "OnlyOne"]) == 1
    assert "Usage: table diff" in capsys.readouterr().err


def test_the_table_actions_are_listed_when_one_is_misspelled(project, capsys):
    assert cli.main(["table", "wat"]) == 2
    assert "list, census, diff, refs" in capsys.readouterr().err


# ── table refs (#64) ────────────────────────────────────────────────────────

def _refs_project(project, referenced=True, many=False):
    import json
    corpus = project / "res" / "conf"
    corpus.mkdir(parents=True, exist_ok=True)
    for name in ("MergeTapCost", "OrderA", "OrderB", "OrderC", "OrderD", "OrderE"):
        (corpus / f"{name}.json").write_text(json.dumps({"rows": {"1": {"id": 1}}}))
    src = project / "src" / "0.0.0" / "Game"
    src.mkdir(parents=True)
    if referenced:
        (src / "Shop.cs").write_text("var cost = MergeTapCost.Rows();\n")
    if many:
        names = ", ".join(f'"{n}"' for n in
                          ("MergeTapCost", "OrderA", "OrderB", "OrderC", "OrderD", "OrderE"))
        (src / "TableParser.cs").write_text(f"foreach (var n in new[]{{{names}}})\n")
    (src / "Other.cs").write_text("// nothing\n")
    return corpus


def test_table_refs_counts_each_corpus_separately(project, capsys):
    _refs_project(project)
    assert cli.main(["table", "refs", "MergeTapCost"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"scaffold\s+1 mention in 1 file", out), out
    assert "lua              cannot check" in out, "not a zero we did not earn"
    assert "metadata         cannot check" in out


def test_table_refs_reports_a_real_zero_without_calling_it_dead(project, capsys):
    _refs_project(project, referenced=False)
    assert cli.main(["table", "refs", "MergeTapCost"]) == 0
    out = capsys.readouterr().out
    assert "scaffold         0 mentions" in out
    for verdict in ("dead", "unused", "orphan", "abandoned"):
        assert verdict not in out.lower(), verdict
    assert "judgement" in out and "note" in out


def test_table_refs_separates_a_general_table_handler_from_a_specific_use(project, capsys):
    """One title's parser reads override rows before parsing any table, so a hit
    there is not a reference to this table."""
    _refs_project(project, many=True)
    assert cli.main(["table", "refs", "MergeTapCost"]) == 0
    out = capsys.readouterr().out
    assert "names this table alone" in out and "names many tables" in out


def test_table_refs_says_when_every_mention_is_a_general_handler(project, capsys):
    """The case the split exists for: the only file naming the table is the one
    that names all of them. It must not print like a specific reference."""
    _refs_project(project, referenced=False, many=True)
    assert cli.main(["table", "refs", "MergeTapCost"]) == 0
    out = capsys.readouterr().out
    assert "0 where the file names this table alone" in out
    for verdict in ("dead", "unused", "orphan", "abandoned"):
        assert verdict not in out.lower(), verdict


def test_table_refs_searches_the_row_class_too(project, capsys):
    """Codegen names the file and the row class differently, so searching one
    finds nothing and nothing reads as zero."""
    import json
    corpus = project / "res" / "conf"
    corpus.mkdir(parents=True)
    (corpus / "tbitem.bytes").write_bytes(b"\x00")
    (project / "luban.json").write_text(json.dumps(
        {"beans": {"ItemConf": {"fields": []}}, "tables": {"tbitem": "ItemConf"}}))
    text = (project / "revenant.toml").read_text()
    (project / "revenant.toml").write_text(
        text + '\n[tables]\nluban_schema = "luban.json"\n')
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()
    assert cli.main(["table", "refs", "tbitem"]) == 0
    out = capsys.readouterr().out
    assert "searching for: tbitem, ItemConf" in out
    assert "no row class known" not in out


def test_table_refs_says_when_no_schema_names_a_row_class(project, capsys):
    """A plain JSON corpus has no class names in it. Searching one name and
    saying nothing lets a zero look like an answer about both."""
    _refs_project(project)
    assert cli.main(["table", "refs", "MergeTapCost"]) == 0
    out = capsys.readouterr().out
    assert "searching for: MergeTapCost" in out
    assert "no row class known" in out


def test_table_refs_answers_about_a_table_whose_bytes_will_not_decode(project, capsys):
    """Counting mentions of a name needs the name, not the rows. Refusing here
    would withhold a straight answer over something the question never used --
    and reading a 200k-row blob to get a file stem is work nobody asked for."""
    corpus = project / "res" / "conf"
    corpus.mkdir(parents=True)
    (corpus / "Broken.json").write_text("{ not json at all")
    src = project / "src" / "0.0.0"
    src.mkdir(parents=True)
    (src / "A.cs").write_text("Broken.Rows();\n")
    assert cli.main(["table", "refs", "Broken"]) == 0
    assert re.search(r"scaffold\s+1 mention", capsys.readouterr().out)


def test_table_refs_rejects_a_limit_it_cannot_use(project, capsys):
    """The `[:-1]` bug `_limit_arg` exists to stop. `refs` had its own parse and
    went straight back to it."""
    _refs_project(project)
    assert cli.main(["table", "refs", "MergeTapCost", "--limit", "-1"]) == 1
    assert "0 or more" in capsys.readouterr().err
    assert cli.main(["table", "refs", "MergeTapCost", "--limit", "abc"]) == 1
    assert "takes a number" in capsys.readouterr().err


def test_table_refs_needs_a_table(project, capsys):
    assert cli.main(["table", "refs"]) == 1
    assert "Usage: table refs" in capsys.readouterr().err


def test_table_refs_counts_the_hot_update_root_too(project, capsys):
    """The C# side is two roots (#48), and the loading code is usually in the
    hot-update one. Counting only `src/` reported "cannot check" over a tree
    that was there, which is this command's own no-index rule broken by us."""
    import json
    corpus = project / "res" / "conf"
    corpus.mkdir(parents=True)
    (corpus / "MergeTapCost.json").write_text(json.dumps({"rows": {"1": {"id": 1}}}))
    hot = project / "src-hotupdate" / "0.0.0" / "Game"
    hot.mkdir(parents=True)
    (hot / "Shop.cs").write_text("var cost = MergeTapCost.Rows();\n")
    assert cli.main(["table", "refs", "MergeTapCost"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"hotupdate\s+1 mention in 1 file", out), out
    assert "scaffold         cannot check" in out, "and the absent one still says so"


def test_table_refs_never_merges_the_scaffold_and_the_hot_update_counts(project, capsys):
    """A stub mentioning the table and a shipped body mentioning it are
    different findings. One number over both is the merge this command's first
    criterion forbids."""
    import json
    corpus = project / "res" / "conf"
    corpus.mkdir(parents=True)
    (corpus / "MergeTapCost.json").write_text(json.dumps({"rows": {"1": {"id": 1}}}))
    _cs_project(project, scaffold=[("A.cs", "class MergeTapCost {}\n")],
                hotupdate=[("B.cs", "var x = MergeTapCost.Rows();\n")])
    assert cli.main(["table", "refs", "MergeTapCost"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"scaffold\s+1 mention in 1 file", out), out
    assert re.search(r"hotupdate\s+1 mention in 1 file", out), out
    assert "2 mentions" not in out, "the two roots are never summed"


def test_table_refs_reads_the_roots_this_project_named(project, capsys):
    """`[csharp] roots` REPLACES the built-in pair. Reading `src/` anyway sends
    `table refs` somewhere `cs-refs` does not go, and the zero it brings back
    is about a directory the project already said is not its source."""
    import json
    corpus = project / "res" / "conf"
    corpus.mkdir(parents=True)
    (corpus / "MergeTapCost.json").write_text(json.dumps({"rows": {"1": {"id": 1}}}))
    named = project / "decomp" / "0.0.0"
    named.mkdir(parents=True)
    (named / "Shop.cs").write_text("var cost = MergeTapCost.Rows();\n")
    text = (project / "revenant.toml").read_text()
    (project / "revenant.toml").write_text(text + '\n[csharp]\nroots = ["decomp"]\n')
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()
    assert cli.main(["table", "refs", "MergeTapCost"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"decomp\s+1 mention in 1 file", out), out
    assert "scaffold" not in out, "the built-in pair was replaced, not added to"


def test_table_refs_says_when_the_corpora_are_not_the_table_s_own_project(
        project, tmp_path, capsys):
    """A path into a sibling title resolves there -- its readers, its row class
    -- but the version and the metadata blob are read from the project you are
    standing in, so the corpora searched are this one's. That is a usable
    question (does the other game's table name appear in my source?) and a
    different one from the count the reader asked for, so it is said."""
    other = _diff_projects(tmp_path)[0]
    src = project / "src" / "0.0.0"
    src.mkdir(parents=True)
    (src / "A.cs").write_text("Currency.Rows();\n")
    assert cli.main(["table", "refs", str(other)]) == 0
    out = capsys.readouterr().out
    assert "another project" in out, out
    assert re.search(r"scaffold\s+1 mention", out), "and the count is still given"


def test_table_refs_does_not_call_its_own_table_another_project_s(project, tmp_path,
                                                                  capsys):
    """A path through a symlink is the same project. `workspace_root()` comes
    back resolved and `abspath` does not resolve, so comparing the two announced
    this project's own table as a sibling's -- on macOS, where `/tmp` is a
    symlink, that was every table under a temp directory."""
    import json
    corpus = project / "res" / "conf"
    corpus.mkdir(parents=True)
    (corpus / "MergeTapCost.json").write_text(json.dumps({"rows": {"1": {"id": 1}}}))
    link = tmp_path / "seen-through-a-link"
    os.symlink(str(project), str(link))
    assert cli.main(["table", "refs",
                     str(link / "res" / "conf" / "MergeTapCost.json")]) == 0
    assert "another project" not in capsys.readouterr().out


def test_the_term_list_mirrors_the_context_glossary():
    """`status` counts the main-line glossary terms; keep the code's list equal
    to CONTEXT.md's, minus the frozen scan section."""
    import pathlib
    ctx = pathlib.Path(__file__).resolve().parents[1] / "CONTEXT.md"
    if not ctx.exists():
        pytest.skip("CONTEXT.md only exists in the source checkout")
    text = ctx.read_text(encoding="utf-8")
    main_line = text.split("### 广度扫描", 1)[0]
    def _terms(section: str) -> list:
        found = re.findall(r"^\*\*([^*]+?)\*\*:\s*$", section, re.M)
        return [t.split("（")[0].strip() for t in found]

    terms = _terms(main_line)
    # Agent-stack terms (Harness/Model/Skill/Command/Memory) describe the
    # runner, not the work; ADR-0002's proxy counts the reverse-engineering
    # vocabulary. Read out of the section rather than listed here: the list had
    # to be edited by hand every time the stack grew a word, which is the same
    # drift the mirror exists to catch.
    stack = set(_terms(main_line.split("### Agent 栈", 1)[-1].split("###", 1)[0]))
    work_terms = [t for t in terms if t not in stack]
    assert list(_describe.CORE_TERMS) == work_terms


# ── the managed-source query surface (#48) ──────────────────────────────────

CS_COMMANDS = ("cs-list", "cs-get", "cs-grep", "cs-refs")


def _cs_project(project, scaffold=(), hotupdate=()):
    for where, files in (("src", scaffold), ("src-hotupdate", hotupdate)):
        for rel, text in files:
            path = project / where / "0.0.0" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    return project


def test_the_cs_commands_are_on_the_query_tier_like_the_lua_ones():
    """ADR-0002: new capability lands on the query tier, the core table stays
    at fourteen. These mirror `lua-*`, which is where they belong."""
    for name in CS_COMMANDS:
        assert cli.command_tier(name) == cli.TIER_QUERY, name
        assert name in cli.command_table(), name
    core = [n for n in cli.command_table() if cli.command_tier(n) == cli.TIER_CORE]
    assert len(core) == 14


def test_the_default_help_does_not_grow_and_help_all_lists_them(capsys):
    cli.main(["help"])
    default = capsys.readouterr().out
    for name in CS_COMMANDS:
        assert name not in default, name
    cli.main(["help", "--all"])
    everything = capsys.readouterr().out
    for name in CS_COMMANDS:
        assert name in everything, name


def test_cs_list_names_both_roots_and_says_which(project, capsys):
    _cs_project(project, scaffold=[("Game/Shop.cs", "class Shop {}\n")],
                hotupdate=[("Game/Deal.cs", "class Deal {}\n")])
    assert cli.main(["cs-list"]) == 0
    out = capsys.readouterr().out
    assert "scaffold/Game/Shop" in out and "hotupdate/Game/Deal" in out


def test_cs_get_refuses_to_pick_between_the_stub_and_the_shipped_body(project, capsys):
    """The scaffold's stub and the hot-update body are different answers.
    Printing either one silently is the failure this command must not have."""
    _cs_project(project, scaffold=[("Game/Shop.cs", "class Shop {}  // stub\n")],
                hotupdate=[("Game/Shop.cs", "class Shop { Buy(); }\n")])
    assert cli.main(["cs-get", "Game/Shop"]) == 1
    err = capsys.readouterr().err
    assert "scaffold/Game/Shop" in err and "hotupdate/Game/Shop" in err
    assert cli.main(["cs-get", "Game/Shop", "--from", "hotupdate"]) == 0
    assert "Buy()" in capsys.readouterr().out


def test_cs_grep_and_cs_refs_reach_both_roots(project, capsys):
    _cs_project(project, scaffold=[("A.cs", "public class ItemConf {}\n")],
                hotupdate=[("B.cs", "var x = ItemConf.Rows();\n")])
    assert cli.main(["cs-grep", "ItemConf"]) == 0
    out = capsys.readouterr().out
    assert "scaffold/A:1:" in out and "hotupdate/B:1:" in out
    assert cli.main(["cs-refs", "ItemConf"]) == 0
    out = capsys.readouterr().out
    assert "declared (1)" in out and "mentioned (1)" in out


def test_a_misspelt_source_root_is_rejected_rather_than_filtered_on(project, capsys):
    """`--from scafold` matches no root. Answering "nothing found" would report
    our own mistake as the tree's content -- the reverse test for the filter."""
    _cs_project(project, scaffold=[("A.cs", "class A {}\n")])
    assert cli.main(["cs-list", "--from", "scafold"]) == 1
    err = capsys.readouterr().err
    assert "no source root named 'scafold'" in err and "scaffold" in err
    assert cli.main(["cs-list", "--from", "scaffold"]) == 0
    assert "scaffold/A" in capsys.readouterr().out


def test_the_cs_commands_say_what_to_run_when_there_is_no_source_tree(project, capsys):
    """All four fail the same way. An empty answer to "search the C#" reads as
    "this game has no C#" when what happened is that `seed-src` never ran, and
    a command that exits 0 on that has called our missing input a result."""
    for argv in (["cs-list"], ["cs-get", "Shop"], ["cs-grep", "x"],
                 ["cs-refs", "X"]):
        assert cli.main(argv) == 1, argv
        assert "seed-src" in capsys.readouterr().err, argv


def test_the_cs_commands_need_an_argument(project, capsys):
    for name in ("cs-get", "cs-grep", "cs-refs"):
        assert cli.main([name]) == 1
        assert f"Usage: {name}" in capsys.readouterr().err, name


def test_cs_grep_rejects_a_limit_it_cannot_use(project, capsys):
    _cs_project(project, scaffold=[("A.cs", "class A {}\n")])
    assert cli.main(["cs-grep", "class", "--limit", "-1"]) == 1
    assert "0 or more" in capsys.readouterr().err


def test_the_cs_tools_are_on_the_mcp_surface(project):
    """User story 11: an agent reading C# should not have to shell out."""
    import asyncio
    from revenant import mcp_server
    names = {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert {"re_cs_list", "re_cs_source", "re_cs_grep", "re_cs_refs"} <= names


def test_a_project_can_replace_the_source_roots(project, capsys):
    """`src/` is revenant's own -- `seed-src` writes it. Where a project lands
    its *recovered* source is a fact about that project, which CONTEXT.md's bar
    keeps out of revenant, so `[csharp] roots` replaces the built-in pair the
    way `[tables] dirs` replaces discovery."""
    path = project / "recovered" / "0.0.0" / "A.cs"
    path.parent.mkdir(parents=True)
    path.write_text("class A {}\n")
    text = (project / "revenant.toml").read_text()
    (project / "revenant.toml").write_text(
        text + '\n[csharp]\nroots = ["recovered"]\n')
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()
    assert cli.main(["cs-list"]) == 0
    assert "recovered/A" in capsys.readouterr().out
    assert cli.main(["cs-list", "--from", "scaffold"]) == 1
    assert "this project has: recovered" in capsys.readouterr().err


def test_cs_list_says_when_it_showed_less_than_it_found(project, capsys):
    _cs_project(project, scaffold=[(f"F{i}.cs", "class A {}\n") for i in range(5)])
    assert cli.main(["cs-list", "--limit", "2"]) == 0
    out = capsys.readouterr().out
    assert "2 of 5 C# file(s)" in out
    assert out.count("scaffold/F") == 2


def test_the_mcp_side_validates_and_reports_its_cap_like_the_cli(project):
    """The two surfaces had already diverged: the MCP tools took `source`
    unchecked and printed a capped listing as the whole tree."""
    from revenant import mcp_server
    _cs_project(project, scaffold=[(f"F{i}.cs", "class A {}\n") for i in range(5)])
    mcp_server.VERSION = "0.0.0"
    assert "no source root named 'scafold'" in mcp_server.re_cs_list(source="scafold")
    assert "no source root named 'scafold'" in mcp_server.re_cs_source("F1", source="scafold")
    assert "no source root named 'scafold'" in mcp_server.re_cs_grep("class", source="scafold")
    assert "no source root named 'scafold'" in mcp_server.re_cs_refs("A", source="scafold")
    assert "2 of 5 C# file(s)" in mcp_server.re_cs_list(limit=2)


# ── extract-scenes takes a directory as a source (#48 gap one) ──────────────

def test_extract_scenes_from_a_directory_of_bundles(project, capsys, monkeypatch):
    """872 MB of fetched bundles were on disk with no built-in way to export
    them, while `contrib.cache.export_bundle_dir` already did it. The gap was
    the entry point, which is the shape five of this ticket's nine gaps share."""
    from revenant import assets
    from revenant.contrib import cache
    pulled = project / "pulled"
    pulled.mkdir()
    (pulled / "a.bundle").write_bytes(b"UnityFS-a")
    (pulled / "__info").write_bytes(b"not a bundle")

    class _Obj:
        type = type("T", (), {"name": "TextAsset"})()
        path_id = 1

        def read(self):
            return type("R", (), {"m_Name": "Level", "m_Script": b"rows"})()

    monkeypatch.setattr(assets, "default_loader",
                        lambda load=None, unity_version=None:
                        lambda stream: type("E", (), {"objects": [_Obj()], "cabs": {}})())
    assert cli.main(["extract-scenes", "--from-dir", str(pulled)]) == 0
    out = capsys.readouterr().out
    assert "1 of 2 file(s) read as bundles" in out
    assert "1 were not" in out, "a non-bundle is counted, not hidden"
    assert (project / "res" / "root" / "a.bundle" / "TextAsset" / "Level.bytes").exists()
    assert cache.export_bundle_dir  # the shared implementation, not a second one


def test_extract_scenes_from_dir_needs_a_directory_that_exists(project, capsys):
    assert cli.main(["extract-scenes", "--from-dir", str(project / "nope")]) == 1
    assert "no such directory" in capsys.readouterr().err
    assert cli.main(["extract-scenes", "--from-dir"]) == 1
    assert "Usage: extract-scenes --from-dir" in capsys.readouterr().err


def test_extract_scenes_from_dir_prints_the_problems_inside_the_bundles(project, capsys, monkeypatch):
    """A gzip body that will not inflate is the only signal a file is not what
    its header claims, and `--from-dir` is the source where a truncated
    download is the likely cause. The count line alone hid it."""
    import gzip
    from revenant import assets
    pulled = project / "pulled"
    pulled.mkdir()
    (pulled / "a.bundle").write_bytes(b"UnityFS-a")

    class _Obj:
        type = type("T", (), {"name": "TextAsset"})()
        path_id = 1

        def read(self):
            return type("R", (), {"m_Name": "Cut",
                                  "m_Script": gzip.compress(b"payload")[:12]})()

    monkeypatch.setattr(assets, "default_loader",
                        lambda load=None, unity_version=None:
                        lambda stream: type("E", (), {"objects": [_Obj()], "cabs": {}})())
    assert cli.main(["extract-scenes", "--from-dir", str(pulled)]) == 0
    out = capsys.readouterr().out
    assert "errors: 1" in out
    assert "1 problem(s) inside the bundles that did load" in out


def test_the_extract_scenes_summary_line_names_every_source(capsys):
    """`help --all` renders the first docstring line. A flag documented only in
    the multi-line usage is a flag nobody finds."""
    cli.main(["help", "--all"])
    line = next(row for row in capsys.readouterr().out.splitlines()
                if row.strip().startswith("extract-scenes"))
    assert "--ggm" in line and "--from-dir" in line, line


def test_the_superseded_script_for_a_pulled_directory_cites_the_command():
    """CONTEXT.md's rule: once a command exists, the mapping cites it and the
    copy goes, rather than staying as a thin wrapper around the import."""
    entry = cli.SUPERSEDED_TOOLS["extract_remote.py"]
    assert entry.kind == cli.BY_COMMAND
    assert "--from-dir" in entry.replacement


def test_the_extract_scenes_bundle_root_flag_actually_arrives(project, monkeypatch):
    """`--root` is a global option `normalize_global_args` hoists out of the
    subcommand's arguments, so reading it back out of `_split_args` got nothing
    and the flag silently did nothing -- while `SUPERSEDED_TOOLS` cites it as
    the reason to delete a project's own extraction script."""
    from revenant import cli as _cli
    seen = {}

    def fake(group, **kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(_cli, "extract_group", fake)
    _cli.main(["extract-scenes", "--all", "--root", "assets/custom/path"])
    assert seen.get("bundle_root") == "assets/custom/path"


# ── lua-decompile <dir> (#48 gap nine) ──────────────────────────────────────

def test_lua_decompile_is_on_the_query_tier_and_only_in_help_all(capsys):
    assert cli.command_tier("lua-decompile") == cli.TIER_QUERY
    cli.main(["help"])
    assert "lua-decompile" not in capsys.readouterr().out
    cli.main(["help", "--all"])
    assert "lua-decompile" in capsys.readouterr().out
    core = [n for n in cli.command_table() if cli.command_tier(n) == cli.TIER_CORE]
    assert len(core) == 14


def test_lua_decompile_reports_what_it_did_not_touch(project, capsys, monkeypatch):
    """A pulled tree holds catalogues and sometimes plain source. Both are
    counted, because "no Lua here" and "I only looked at some" differ."""
    from revenant import lua
    pulled = project / "pulled"
    pulled.mkdir()
    (pulled / "a.lua").write_bytes(b"\x1bLua53-a")
    (pulled / "already.lua").write_text("local x = 1\n")
    (pulled / "catalog.json").write_text('{"x":1}')
    monkeypatch.setattr(lua, "decompile", lambda chunk, timeout=60: (True, "return 1\n"))
    assert cli.main(["lua-decompile", str(pulled)]) == 0
    out = capsys.readouterr().out
    assert "1/1 chunk(s) decompiled" in out
    assert "1 file(s) were already Lua source, copied through" in out
    assert "1 file(s) were neither Lua bytecode nor .lua source" in out


def test_lua_decompile_succeeds_on_a_tree_that_is_all_plain_source(project, capsys):
    """A CDN tree can be plain Lua end to end. Exiting 1 on it reported our own
    bucketing as the caller's failure."""
    pulled = project / "pulled"
    pulled.mkdir()
    (pulled / "a.lua").write_text("Config = {}\n")
    assert cli.main(["lua-decompile", str(pulled)]) == 0
    assert "1 file(s) were already Lua source, copied through" in capsys.readouterr().out


def test_lua_decompile_says_why_nothing_came_out(project, capsys, monkeypatch):
    """Story 22 the other way: `$REVENANT_LJD2` missing must be reported, not
    silently downgraded -- which is the behaviour lua-extract already has."""
    from revenant import lua
    pulled = project / "pulled"
    pulled.mkdir()
    (pulled / "a.lua").write_bytes(b"\x1bLJ\x02SomeName\x00")
    monkeypatch.setattr(lua, "decompile",
                        lambda chunk, timeout=60: (False, "set $REVENANT_LJD2"))
    monkeypatch.setattr(lua, "have_decompiler", lambda: True)
    assert cli.main(["lua-decompile", str(pulled)]) == 0
    out = capsys.readouterr().out
    assert "0/1 chunk(s) decompiled" in out
    assert "1 kept as embedded strings only" in out
    assert "why: set $REVENANT_LJD2" in out


def test_lua_decompile_needs_a_directory_that_exists(project, capsys):
    assert cli.main(["lua-decompile"]) == 1
    assert "Usage: lua-decompile" in capsys.readouterr().err
    assert cli.main(["lua-decompile", str(project / "nope")]) == 1
    assert "no such directory" in capsys.readouterr().err


# ── the bar for moving something in lives in one place (#48) ────────────────

def _repo_file(*parts):
    import pathlib
    path = pathlib.Path(__file__).resolve().parents[1].joinpath(*parts)
    if not path.exists():
        pytest.skip(f"{path.name} only exists in the source checkout")
    return path.read_text(encoding="utf-8")


GAME_FACT_LEAD = "游戏事实指这些东西："


def _game_facts(text: str) -> list:
    """The enumerated kinds of game fact, from whichever document states them."""
    after = text.split(GAME_FACT_LEAD, 1)[1]
    sentence = after.split("。", 1)[0]
    return [part.strip() for part in sentence.split("；") if part.strip()]


def test_the_two_copies_of_the_game_fact_list_agree():
    """CONTEXT.md keeps the list because it is read at the start of every
    session; ADR-0004 keeps it because that is where the decision lives. Two
    readable copies pinned equal beats one copy behind a link -- the same trade
    `describe.CORE_TERMS` makes against CONTEXT.md's glossary."""
    adr = _game_facts(_repo_file("docs", "adr",
                                 "0004-what-qualifies-to-move-into-revenant.md"))
    context = _game_facts(_repo_file("CONTEXT.md"))
    assert adr == context, "the enumerated game facts drifted"
    assert len(adr) >= 5, adr


# What the seven kinds of game fact are called in English, one marker each. A
# docstring naming several of them is enumerating the list again, whatever
# punctuation it uses -- which is the drift this test exists to catch, and the
# first version of it could not: it pinned a Chinese lead that can never appear
# in an English docstring and one exact substring.
_GAME_FACT_MARKERS = ("key", "URL", "bucket id", "namespace",
                      "directory convention", "file-naming", "reads meaning")


def test_the_criterion_is_not_restated_a_third_time_in_the_code():
    """It had three copies -- CONTEXT.md, `contrib/__init__.py`, and the
    playbooks README -- saying not quite the same thing. The module cites the
    ADR now; a fresh copy here is how they drift apart again."""
    from revenant import contrib
    doc = contrib.__doc__ or ""
    assert GAME_FACT_LEAD not in doc
    named = [m for m in _GAME_FACT_MARKERS if m.lower() in doc.lower()]
    assert len(named) < 3, f"the enumerated list came back: {named}"
    assert "0004-what-qualifies-to-move-into-revenant" in doc


def test_the_drift_detector_notices_the_list_coming_back():
    """The reverse test, because this one is a detector and a detector that
    cannot fire is worse than none. The first version passed with the whole
    list reinserted in different punctuation."""
    doc = ("The bar: no game fact. A game fact is any of: a key, a URL or the "
           "rule that builds one, a project, environment or bucket id, a list "
           "of concrete class names or namespaces, a directory convention, a "
           "file-naming convention, a rule that reads meaning out of a name.")
    named = [m for m in _GAME_FACT_MARKERS if m.lower() in doc.lower()]
    assert len(named) >= 3, named


def test_the_placement_list_is_not_copied_into_the_adr():
    """ADR-0004's own 后果 says three copies is three chances to drift, and the
    first draft of it copied CONTEXT.md's 「各部分放哪」 list -- which had
    already diverged in the same commit that wrote it."""
    adr = _repo_file("docs", "adr", "0004-what-qualifies-to-move-into-revenant.md")
    assert "各部分放哪" not in adr or "CONTEXT.md" in adr
    assert "tests/test_backflow.py" not in adr, "the placement list came back"


def test_the_playbook_bar_points_at_the_adr_and_stays_its_own_rule():
    """Two bars, deliberately different: a construct is judged by whether it
    holds a game fact, a playbook by whether two titles used the method. The
    README may not quietly adopt the construct rule."""
    readme = _repo_file("docs", "playbooks", "README.md")
    assert "0004-what-qualifies-to-move-into-revenant" in readme
    assert "two data points" in readme, "the two-title rule for methods stands"


def test_the_adr_records_why_the_narrower_version_was_declined():
    """#48 proposed reinstating "copied into two projects" as one branch of a
    two-branch rule. Declining it is the substance of this ADR; an ADR that
    only states the outcome cannot stop the same proposal returning."""
    adr = _repo_file("docs", "adr", "0004-what-qualifies-to-move-into-revenant.md")
    assert "#32" in adr and "#50" in adr and "#48" in adr
    assert "不采纳" in adr


def test_every_playbook_declares_what_it_was_verified_on():
    """The README's bar for a method is two real titles, and the "Verified on"
    line is where that claim is made. A playbook without one is a method
    asserting it generalises with nothing behind the assertion."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "docs" / "playbooks"
    if not root.is_dir():
        pytest.skip("playbooks only exist in the source checkout")
    for path in sorted(root.glob("*.md")):
        if path.name == "README.md":
            continue
        head = path.read_text(encoding="utf-8")[:600]
        # The marker has to be *inside* the Verified-on line, which is what the
        # README asks for: a 【源码确认】 elsewhere in the file is not the claim.
        line = next((row for row in head.splitlines()
                     if row.startswith("Verified on:")), "")
        assert line, f"{path.name} makes no Verified-on claim"
        assert len(line) > len("Verified on:") + 4, f"{path.name}: {line!r}"


def test_every_playbook_is_listed_in_the_readme():
    """An unlisted playbook is one nobody finds, which is the same as one that
    was never written."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "docs" / "playbooks"
    if not root.is_dir():
        pytest.skip("playbooks only exist in the source checkout")
    readme = (root / "README.md").read_text(encoding="utf-8")
    for path in sorted(root.glob("*.md")):
        if path.name != "README.md":
            assert f"({path.name})" in readme, path.name


# ── extract-scenes --out: the landing spot is the caller's (#48 tail) ───────

def _fake_textasset_loader(monkeypatch, name="Level", body=b"rows"):
    from revenant import assets

    class _Obj:
        type = type("T", (), {"name": "TextAsset"})()
        path_id = 1

        def read(self):
            return type("R", (), {"m_Name": name, "m_Script": body})()

    monkeypatch.setattr(assets, "default_loader",
                        lambda load=None, unity_version=None:
                        lambda stream: type("E", (), {"objects": [_Obj()], "cabs": {}})())


def test_extract_scenes_ggm_lands_where_it_is_told(project, capsys, monkeypatch):
    """One title's downstream scripts read the path its own script produced.
    The fix is a settable landing spot, not revenant learning that title's
    directory name -- a directory convention is a game fact (ADR-0004)."""
    from revenant import assets
    _fake_textasset_loader(monkeypatch)
    monkeypatch.setattr(assets, "iter_ggm_sources",
                        lambda root=None: [("base.apk!data.unity3d", b"UnityFS-g")])
    out = project / "res" / "cms-embedded"
    assert cli.main(["extract-scenes", "--ggm", "--out", str(out)]) == 0
    assert (out / assets.GGM_GROUP / "data.unity3d" / "TextAsset" / "Level.bytes").exists()
    assert not (project / "res" / assets.GGM_GROUP).exists(), "not also in the default"


def test_extract_scenes_from_dir_lands_where_it_is_told(project, capsys, monkeypatch):
    """The same flag for the source added by this ticket; one landing spot
    flag that only half the sources honoured would be a new asymmetry."""
    _fake_textasset_loader(monkeypatch)
    pulled = project / "pulled"
    pulled.mkdir()
    (pulled / "a.bundle").write_bytes(b"UnityFS-a")
    out = project / "elsewhere"
    assert cli.main(["extract-scenes", "--from-dir", str(pulled),
                     "--out", str(out)]) == 0
    assert (out / "root" / "a.bundle" / "TextAsset" / "Level.bytes").exists()


def test_extract_scenes_defaults_to_res_when_no_out_is_given(project, capsys, monkeypatch):
    from revenant import assets
    _fake_textasset_loader(monkeypatch)
    monkeypatch.setattr(assets, "iter_ggm_sources",
                        lambda root=None: [("base.apk!data.unity3d", b"UnityFS-g")])
    assert cli.main(["extract-scenes", "--ggm"]) == 0
    assert (project / "res" / assets.GGM_GROUP / "data.unity3d").is_dir()


def test_the_superseded_entry_for_the_textasset_dump_cites_the_flag():
    """The mapping said `extract-scenes --ggm` while the paths still differed,
    which is why the copy was neither deleted nor listed. It can be deleted
    once the command can produce the same directory."""
    entry = cli.SUPERSEDED_TOOLS["dump_textassets.py"]
    assert entry.kind == cli.BY_COMMAND
    assert "--out" in entry.replacement


def _stub_extract_group(monkeypatch, reports):
    """Capture what the CLI passed, which is the half the summary cannot show."""
    from revenant import cli as _cli
    seen = {}

    def fake(group, **kwargs):
        seen["group"] = group
        seen.update(kwargs)
        return reports

    monkeypatch.setattr(_cli, "extract_group", fake)
    return seen


def test_the_package_source_forwards_out_as_well(project, monkeypatch):
    """The mutation this test exists for: dropping `res_root=` from the
    `extract_group` call left the whole suite green, because the only test
    touching this path stubbed the function and never looked at its arguments.
    CONTEXT.md says all three sources honour `--out`; two of them were pinned."""
    seen = _stub_extract_group(monkeypatch, [])
    cli.main(["extract-scenes", "G", "--out", str(project / "elsewhere")])
    assert seen["res_root"] == str(project / "elsewhere")


def test_the_extract_scenes_summary_names_where_it_actually_wrote(project, capsys, monkeypatch):
    """It printed `res/<group>/` unconditionally. With `--out` that is a
    sentence a note would quote about a directory nothing was written to."""
    from revenant import assets
    out = project / "elsewhere"
    reports = [assets.BundleReport(group="G", name="b", size=1,
                                   out_dir=str(out / "G" / "b"), loaded=True)]
    _stub_extract_group(monkeypatch, reports)
    assert cli.main(["extract-scenes", "G", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert str(out / "G") in printed
    assert "res/G/" not in printed


def test_the_summary_does_not_name_one_group_when_every_group_ran(project, capsys, monkeypatch):
    """`--all` spans several groups, so `dirname` of the first report named a
    directory that was one of many -- the exact failure the summary fix claimed
    to have removed."""
    from revenant import assets
    out = project / "elsewhere"
    reports = [assets.BundleReport(group=g, name="b", size=1,
                                   out_dir=str(out / g / "b"), loaded=True)
               for g in ("A", "B", "C")]
    _stub_extract_group(monkeypatch, reports)
    assert cli.main(["extract-scenes", "--all", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert str(out / "A") not in printed, "one group is not the landing spot"
    assert "every group" in printed


def test_out_with_no_value_is_refused_rather_than_ignored(project, capsys):
    """It fell back to `res/` and exited 0, dropping the caller's landing spot
    and calling the run a success. `--from-dir` already refuses the same shape,
    so the two flags on one command behaved oppositely."""
    assert cli.main(["extract-scenes", "--ggm", "--out"]) == 1
    assert "--out takes a directory" in capsys.readouterr().err


def test_out_pointing_at_a_file_is_refused_where_it_can_be_said(project, capsys):
    """It escaped as a NotADirectoryError traceback from inside the export."""
    afile = project / "afile"
    afile.write_text("not a directory\n")
    assert cli.main(["extract-scenes", "--ggm", "--out", str(afile)]) == 1
    assert "is not a directory" in capsys.readouterr().err


# ── Lua config tables in the corpus (#58) ──────────────────────────────────

def test_table_list_reads_lua_config_and_says_what_it_counted(project, capsys):
    """Two titles keep config as Lua tables. Listing them without saying the
    rows are per file would hand back a confident number that one of those
    titles makes 34% too large."""
    conf = project / "lua" / "0.0.0" / "Data" / "Config"
    conf.mkdir(parents=True)
    (conf / "Order.lua").write_text(
        "return {\n [1] = { id = 1, cost = 3 },\n [2] = { id = 2, cost = 4 },\n}\n")
    (conf / "Item.lua").write_text("return { [9] = { id = 9 } }\n")
    assert cli.main(["table", "list"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"Order\s+2\s+2\s+lua-table", out), out
    assert re.search(r"Item\s+1\s+1\s+lua-table", out), out
    assert "count of files read, not of loadable tables" in out


def test_table_list_says_nothing_about_variants_when_there_is_no_lua(project, capsys):
    """The reverse test: a caveat printed on every listing is one nobody
    reads."""
    import json
    corpus = project / "res" / "conf"
    corpus.mkdir(parents=True)
    (corpus / "A.json").write_text(json.dumps({"rows": {"1": {"id": 1}}}))
    assert cli.main(["table", "list"]) == 0
    assert "loadable tables" not in capsys.readouterr().out


def test_table_census_works_on_a_lua_table(project, capsys):
    conf = project / "lua" / "0.0.0" / "Config"
    conf.mkdir(parents=True)
    (conf / "Order.lua").write_text(
        "return {\n" + "".join(f" [{i}] = {{ id = {i}, cost = 5 }},\n"
                               for i in range(1, 6)) + "}\n")
    assert cli.main(["table", "census", "Order"]) == 0
    out = capsys.readouterr().out
    assert "cost" in out and "id" in out
    assert re.search(r"cost\s+5/5", out), out


def test_the_lua_caveat_reaches_census_and_is_not_repeated_per_file(project, capsys):
    """It has to reach `census`, where the count is consumed -- but as a
    per-file note in the listing it printed the same sentence for every file in
    the corpus, which is how a caveat becomes noise nobody reads."""
    conf = project / "lua" / "0.0.0" / "Config"
    conf.mkdir(parents=True)
    for name in ("A", "B", "C"):
        (conf / f"{name}.lua").write_text("return { [1] = { id = 1 } }\n")
    assert cli.main(["table", "list"]) == 0
    out = capsys.readouterr().out
    assert out.count("count of files read") == 1
    assert "not read" not in out
    assert cli.main(["table", "census", "A"]) == 0
    printed = capsys.readouterr()
    assert "count of files read" in printed.out + printed.err


def test_running_the_cli_module_directly_reaches_the_whole_command_table():
    """`python -m revenant.cli` ran `main()` from a guard sitting 500 lines
    before the end of the file, so every handler defined below it -- `packs`,
    `probe`, `cell`, `ledger`, `lint`, `scan`, `dig` -- was still unbound when
    `command_table()` built its dict. The guard belongs at the end.
    """
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-m", "revenant.cli", "help"],
                         capture_output=True, text=True)
    assert "NameError" not in out.stderr, out.stderr[-400:]
    assert out.returncode == 0, out.stderr[-400:]


# ── a tool that cannot tell "no data" from "wrong directory" (#69) ──────────

def _mcp_tool_functions():
    """Every `re_*` tool on the MCP surface, as plain callables."""
    from revenant import mcp_server
    out = {}
    for name in dir(mcp_server):
        if not name.startswith("re_"):
            continue
        fn = getattr(mcp_server, name)
        out[name] = getattr(fn, "fn", fn)
    return out


def test_every_mcp_tool_says_wrong_directory_rather_than_no_data(project, monkeypatch):
    """The day this came from: nine prepared projects, the server started at the
    repository root above them, and every index-backed tool answering "indices
    not built -- run `revenant prepare`". That is false about all nine, and the
    rounds that believed it wrote down "this game does not have that".

    Enumerated rather than spot-checked, because the failure mode is a tool that
    forgot to have the guard -- eleven of twenty-two had no guard at all, and
    the Lua and C# ones answered "0 scripts" from outside a project.
    """
    from revenant import mcp_server
    monkeypatch.setattr(mcp_server, "_PROJECT_ROOT", "")
    monkeypatch.setattr(mcp_server, "_INDICES_OK", False)

    sample = {"query": "X", "type_name": "X", "rva": "0x1000", "address": "0x1000",
              "name": "X", "pattern": "x", "offset": "0x10", "symbol": "X",
              "limit": 2, "source": "", "filter": ""}
    checked = []
    for name, fn in sorted(_mcp_tool_functions().items()):
        import inspect
        kwargs = {p: sample[p] for p in inspect.signature(fn).parameters
                  if p in sample}
        answer = fn(**kwargs)
        assert "No Revenant project here" in answer, (
            f"{name} answered something other than 'wrong directory': {answer[:120]!r}")
        assert "revenant prepare" not in answer, (
            f"{name} still blames missing data for a location problem")
        checked.append(name)
    assert len(checked) >= 20, f"only {len(checked)} tools reached"


def test_the_no_project_message_names_the_projects_beside_it(tmp_path, monkeypatch):
    """"You are not in a project" is half an answer when the other half -- which
    ones, by name -- is one listdir away."""
    from revenant import config, mcp_server
    repo = tmp_path / "merge-games-re"
    for game in ("flambe", "travel-town"):
        (repo / game).mkdir(parents=True)
        (repo / game / config.PROJECT_MARKER).write_text("")
    monkeypatch.chdir(repo)
    monkeypatch.delenv("REVENANT_PROJECT", raising=False)
    monkeypatch.setattr(mcp_server, "_PROJECT_ROOT", "")

    answer = mcp_server.re_status.fn() if hasattr(mcp_server.re_status, "fn") else mcp_server.re_status()
    assert "flambe" in answer and "travel-town" in answer
    assert "cd flambe" in answer


def test_re_status_does_not_invent_a_target_when_there_is_no_project(tmp_path, monkeypatch):
    """The one tool whose whole job is to say what is set up was the one that
    most convincingly lied: `com.unknown.il2cppgame v0.0.0, architecture
    unknown` is the generic fallback rendered as a real target."""
    from revenant import mcp_server
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("REVENANT_PROJECT", raising=False)
    monkeypatch.setattr(mcp_server, "_PROJECT_ROOT", "")
    fn = getattr(mcp_server.re_status, "fn", mcp_server.re_status)
    answer = fn()
    assert "com.unknown.il2cppgame" not in answer
    assert "No Revenant project here" in answer
