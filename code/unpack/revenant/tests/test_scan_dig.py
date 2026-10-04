"""Cold start, breadth scan, deep dives.

One seam: the CLI, asserting on the ledger. The corpus warning replaced the
corpus gate (ADR-0002, #28): the scan runs and says what the fingerprint saw.
The scan family is frozen (ADR-0002): frozen is not deleted, so everything here
still has to pass.
"""

from __future__ import annotations

import pytest

from revenant import dig as _dig
from revenant import fingerprint as _fp
from revenant import ledger as _ledger
from revenant import scan as _scan
from revenant.methodology import STATE_MEETS, STATE_OUT_OF_REACH, CellId
from tests import fixtures as fx


@pytest.fixture
def project(tmp_path, monkeypatch):
    from revenant.init import init_project
    root = tmp_path / "proj"
    init_project(str(root), quiet=True)
    text = (root / "revenant.toml").read_text()
    (root / "revenant.toml").write_text(text + '\n[packs]\nenabled = ["example"]\n')
    monkeypatch.setenv("REVENANT_PROJECT", str(root))
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()
    config._IDENTITY_CACHE.clear()
    config.set_platform(None)
    yield root
    config._PROJECT_CONFIG_CACHE.clear()


def _elf(tmp_path):
    return open(fx.write_elf(str(tmp_path / "_e.bin")), "rb").read()


def _pack(project):
    from revenant import config, pack
    return pack.discover(str(project), pack.enabled_packs(config.project_config()))["example"]


def _led(project):
    return _ledger.Ledger.load(_ledger.ledger_path(str(project), "example"), "example")


def _fingerprint(**kw):
    return _fp.Fingerprint(**kw)


# ── the corpus warning ──────────────────────────────────────────────────────

def test_scan_warns_but_runs_when_declared_game_assemblies_are_absent(project):
    """The failure the old gate existed for, now a fact the reader is told.

    Probing the IL2CPP index on a hot-update title returns zero everywhere and
    every cell would land on "checked, genuinely absent". The zero-hit review
    cannot save it: the vocabulary is right, the corpus is wrong. The scan
    still runs -- a wiped marker string once flipped the gate the wrong way --
    but the ledger and the report carry the fact in the fingerprint's words.
    """
    fp = _fingerprint(declared_assemblies=["Game.dll", "UnityEngine.dll"],
                      assemblies_in_metadata=["UnityEngine.dll"],
                      assemblies_absent=["Game.dll"])
    led = _led(project)
    result = _scan.run(_pack(project), fp, led, "1.0", "1.0@android")

    assert result.started
    assert "Game.dll" in result.corpus_warning
    assert "Game.dll" in led.package["corpus_warning"]
    assert "WARNING" in result.as_text()
    assert result.slots_run == ["E01", "E02"]


def test_a_clean_package_carries_no_warning(project):
    """A warning that always fires is as useless as a gate that always refuses."""
    led = _led(project)
    result = _scan.run(_pack(project), _fingerprint(), led, "1.0", "1.0@android")
    assert result.started
    assert not result.corpus_warning
    assert "corpus_warning" not in led.package
    assert result.slots_run == ["E01", "E02"]


def test_the_brief_carries_the_absent_assemblies_not_a_verdict(project):
    fp = _fingerprint(declared_assemblies=["Game.dll"], assemblies_absent=["Game.dll"])
    result = _scan.run(_pack(project), fp, _led(project), "1.0", "1.0@android")
    for brief in result.briefs:
        assert brief["business_assemblies_absent"] == ["Game.dll"]
        assert "corpus" not in brief and "baseline" not in brief and "state_ceiling" not in brief


# ── attention budget and signals ────────────────────────────────────────────

def test_signals_are_batched_not_raised_one_by_one(project):
    """Five batches, not five interruptions -- 24 slots would blow five instantly."""
    led = _led(project)
    for _ in range(3):
        _scan.run(_pack(project), _fingerprint(), led, "1.0", "1.0@android")
    assert int(led.package.get("attention_batches", 0)) <= 3


def test_a_sixth_batch_stops_the_scan(project):
    led = _led(project)
    led.package["attention_batches"] = _scan.MAX_ATTENTION_BATCHES
    pk = _pack(project)
    for cell in pk.slot("E01").cells():
        led.cell(cell)["state"] = STATE_MEETS
    led.cell(CellId("example", "E01", "responsibility"))["state"] = "confirmed_absent"
    led.cell(CellId("example", "E01", "core_mechanism"))["state"] = STATE_MEETS

    result = _scan.run(pk, _fingerprint(), led, "1.0", "1.0@android")
    assert result.signals, "a contradiction must be signalled"
    assert result.stopped_early


def test_contradicting_facets_are_a_signal(project):
    led = _led(project)
    led.cell(CellId("example", "E01", "responsibility"))["state"] = STATE_MEETS
    led.cell(CellId("example", "E01", "core_mechanism"))["state"] = "confirmed_absent"
    signals = _scan.facet_contradictions(_pack(project), led)
    assert [s.kind for s in signals] == [_scan.SIGNAL_FACET_CONTRADICTION]


def test_unmet_dependency_and_low_coverage_are_not_signals(project):
    """Both were deliberately excluded.

    An unmet `requires` edge already warns, and calling a human is blocking by
    another name; low coverage is an outcome, not an anomaly.
    """
    result = _scan.run(_pack(project), _fingerprint(), _led(project), "1.0", "1.0@android")
    kinds = {s.kind for s in result.signals}
    assert _scan.SIGNAL_CANDIDATE_EXPLOSION not in kinds
    assert not kinds, "an empty index yields no candidates and no coverage, and neither calls a human"


def test_scan_writes_a_brief_per_slot_and_no_judgements(project):
    result = _scan.run(_pack(project), _fingerprint(), _led(project), "1.0", "1.0@android",
                       brief_dir=str(project / ".revenant" / "briefs"))
    assert len(result.briefs) == 2
    assert _ledger.judgement_fields_written(_led(project)) == []
    for brief in result.briefs:
        assert brief["question"], "the brief carries the question, not an answer"
        assert "naming_statistics_hint" in brief


def test_scan_calls_no_model(project, monkeypatch):
    """Structural guard: the previous generation welded a vendor into a script.

    That half never ran once. Nothing in the scan path may open a socket.
    """
    import socket

    def _forbidden(*args, **kwargs):
        raise AssertionError("the scan path must not make network calls")

    monkeypatch.setattr(socket.socket, "connect", _forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", _forbidden)
    result = _scan.run(_pack(project), _fingerprint(), _led(project), "1.0", "1.0@android")
    assert result.started


# ── deep dives ──────────────────────────────────────────────────────────────

def test_a_dig_needs_a_question_and_criteria(project):
    with pytest.raises(_dig.DigError, match="business question"):
        _dig.open_task("", ["something"])
    with pytest.raises(_dig.DigError, match="completion criteria"):
        _dig.open_task("why does drop rate feel wrong", [])


def test_entry_hints_become_probes_on_the_same_executor(project):
    """A pointed direction is retrieval, and must not open a second mechanism."""
    probes = _dig.entry_hints_as_probes(["DropTable", ".*Reward.*", "0x1234"])
    patterns = [p.pattern for p in probes]
    assert patterns == [".*DropTable.*", ".*Reward.*"]   # the address is not a pattern


def test_converging_requires_every_retrieved_candidate_to_be_accounted_for(project):
    """Turns "remember to record dead ends" into a step you cannot skip.

    Exactly one such record exists across 27 prior notes, which is what
    voluntary discipline achieves here.
    """
    led = _led(project)
    task = _dig.open_task("q", ["a"])
    with pytest.raises(_dig.DigError, match="unaccounted"):
        _dig.converge(task, led, dead_ends=[], retrieved_candidates=["AudioManager"])

    _dig.converge(task, led,
                  dead_ends=[{"candidate": "AudioManager", "reason": "audio, not drops"}],
                  retrieved_candidates=["AudioManager"])
    assert led.dead_ends[0]["candidate"] == "AudioManager"
    assert task.dead_ends[0]["candidate"] == "AudioManager"


def test_a_dig_is_done_only_when_every_criterion_is_met_at_convergence(project):
    """Open and converge are the only two moves (ADR-0002); "done" is decided
    at convergence by the criteria, not by a tick counter."""
    task = _dig.open_task("q", ["a", "b"])
    _dig.converge(task, None, dead_ends=[], retrieved_candidates=[], met=[0])
    assert task.status == _dig.STATUS_UNFINISHED
    assert [c.text for c in task.unmet] == ["b"]
    _dig.converge(task, None, dead_ends=[], retrieved_candidates=[], met=[0, 1])
    assert task.status == _dig.STATUS_DONE


def test_dig_has_no_tick_round_or_queue(project):
    """The unattended loop those served was never built; they come back with it."""
    for gone in ("tick", "round_finished", "queue_from_ledger", "STALL_ROUNDS"):
        assert not hasattr(_dig, gone), gone


def test_dig_open_and_converge_through_the_cli(project, monkeypatch, capsys):
    from revenant import cli
    monkeypatch.chdir(project)
    assert cli.main(["dig", "open", "--question", "where do drops come from",
                     "--criteria", "table located;weights read"]) == 0
    task_id = capsys.readouterr().out.split()[0]

    # A retrieved candidate with no disposition blocks convergence.
    assert cli.main(["dig", "converge", task_id, "--met", "0",
                     "--retrieved", "AudioManager,DropTable"]) == 2
    assert "unaccounted" in capsys.readouterr().out

    assert cli.main(["dig", "converge", task_id, "--met", "0,1",
                     "--retrieved", "AudioManager,DropTable",
                     "--dead-end", "AudioManager: audio, not drops",
                     "--used", "DropTable",
                     "--note", "notes/core-03-drops.md"]) == 0
    out = capsys.readouterr().out
    assert "done" in out and "AudioManager" in out
    tasks = _dig.load_tasks(_dig.tasks_path(str(project)))
    assert tasks[0].status == _dig.STATUS_DONE
    assert tasks[0].note_ref == "notes/core-03-drops.md"

    for gone in ("tick", "round", "queue"):
        assert cli.main(["dig", gone, task_id]) == 2


def test_a_finished_dig_hands_the_cell_back_as_not_run(project):
    """It does not fill the cell in -- the two answer different questions."""
    led = _led(project)
    cid = CellId("example", "E02", "core_mechanism")
    led.mark_ran(cid, "h", "v")
    led.set_judgement(cid, state=STATE_OUT_OF_REACH, reach_source="input_missing")

    _dig.hand_back_cell(led, cid, note_ref="notes/core-03-drops.md", evidence_id="ev1")
    entry = led.cell(cid)
    assert entry["ran"] is False
    assert entry["state"] == ""
    assert entry["notes_ref"] == "notes/core-03-drops.md"   # the note rides along
    assert "ev1" in entry["evidence"]


# ── dig overriding a scan ───────────────────────────────────────────────────

def test_a_reviewed_dig_conclusion_overrides_the_scan_unattended(project):
    triggers = _dig.review_triggers(defect_marked=False, self_assessed_high=True,
                                    has_placeholder=False)
    allowed, why = _dig.may_override_scan(triggers, review_done=False)
    assert allowed and not why


def test_unreviewed_dig_output_may_not_rewrite_a_recorded_conclusion(project):
    triggers = _dig.review_triggers(defect_marked=True, self_assessed_high=False,
                                    has_placeholder=True)
    allowed, why = _dig.may_override_scan(triggers, review_done=False)
    assert not allowed
    assert "placeholder" in why and "confidence" in why

    allowed, _why = _dig.may_override_scan(triggers, review_done=True)
    assert allowed


def test_conflicts_are_logged_and_countable(project):
    """One probe repeatedly disagreeing is the input reflow wants."""
    led = _led(project)
    for _ in range(3):
        _dig.record_conflict(led, CellId("example", "E02", "core_mechanism"),
                             probe_key="class_regex:.*Attrib.*:", scan_state="meets_threshold",
                             dig_state="confirmed_absent", overridden=True)
    conflicts = led.package["conflicts"]
    assert len(conflicts) == 3
    assert len({c["probe_key"] for c in conflicts}) == 1


# ── cold start, end to end through the CLI ──────────────────────────────────

def test_fingerprint_runs_before_any_index_exists(project, tmp_path, monkeypatch, capsys):
    from revenant import cli
    fx.write_apk(str(project / "game.apk"), _elf(tmp_path), fx.fake_metadata())
    from revenant import config
    config._IDENTITY_CACHE.clear()
    monkeypatch.chdir(project)
    assert cli.main(["fingerprint"]) == 0
    led = _led(project)
    assert led.package["fingerprint"]["kind"] == "apk"
    assert cli.main(["fingerprint", "--json"]) == 0
    out = capsys.readouterr().out
    assert '"markers_seen"' in out


def test_scan_through_the_cli_runs_and_records_the_warning(project, tmp_path, monkeypatch):
    from revenant import cli
    fx.write_apk(str(project / "game.apk"), _elf(tmp_path), fx.fake_metadata())
    monkeypatch.chdir(project)

    real = _fp.collect

    def with_absent(path, lay=None, deep=True):
        fp = real(path, lay, deep)
        fp.assemblies_absent = ["Game.dll"]
        return fp
    monkeypatch.setattr(_fp, "collect", with_absent)
    assert cli.main(["scan", "example"]) == 0
    assert "Game.dll" in _led(project).package["corpus_warning"]
