"""V1.33.2 / V1.33.3 — Telemetría A6 (embudo Estudio AUTO + persist lastPropose)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from bolsa_application.estudio_auto_telemetry import (
    build_estudio_auto_telemetry,
    count_estudio_auto_funnel,
    derive_a6_gates,
    last_estudio_auto_propose,
    recent_estudio_auto_proposes,
    remember_estudio_auto_propose,
    reset_last_estudio_auto_propose,
    resolve_propose_path,
    summarize_estudio_auto_propose,
)


def _row(*, stance: str, stars: int, day: date = date(2026, 8, 30)) -> SimpleNamespace:
    return SimpleNamespace(
        instrument_id="inst-1",
        stance=stance,
        dictamen_stars=stars,
        as_of_bar_date=day,
    )


def _propose_result(**overrides: object) -> dict:
    base: dict = {
        "generatedAt": "2026-08-30T20:00:00+00:00",
        "planId": "edo_abc",
        "candidateCount": 3,
        "hitCount": 1,
        "executeStatus": "dry_run",
        "hits": [{"autoSource": "estudio_alarma"}],
        "skipped": [
            {"reason": "no_tradeplan"},
            {"reason": "propose_error:boom"},
        ],
    }
    base.update(overrides)
    return base


def test_funnel_counts_alarma_dictamen_and_silent() -> None:
    rows = [
        _row(stance="buy", stars=5),
        _row(stance="buy", stars=3, day=date(2026, 8, 29)),
        _row(stance="buy", stars=1),
        _row(stance="hold_watch", stars=5),
    ]
    funnel = count_estudio_auto_funnel(rows)
    assert funnel["candidatesAlarma"] == 1
    assert funnel["candidatesDictamen"] == 1
    assert funnel["candidatesTotal"] == 2
    assert funnel["notCandidate"] == 2
    assert funnel["daysWithOpinions"] == 2
    assert funnel["allowedSources"] == ["estudio_alarma", "estudio_dictamen"]
    assert "paper_d" in funnel["excludedSources"]
    assert "radar" in funnel["excludedSources"]
    assert "hoy" in funnel["excludedSources"]


def test_gates_blocked_until_p1_p5_pass() -> None:
    blocked = derive_a6_gates(
        auto_mark="FAIL",
        strict_accept_ready=False,
        edge_report_parity=True,
        paper_d_execute_env=False,
    )
    assert blocked["expandSourcesReady"] is False
    assert blocked["thawEstrictoReady"] is False
    assert blocked["paperDExecuteEnv"] is False
    assert "p1_p5_not_green" in blocked["blockers"]


def test_gates_expand_when_p1_p5_and_edge_parity() -> None:
    ready = derive_a6_gates(
        auto_mark="PASS",
        strict_accept_ready=True,
        edge_report_parity=True,
        paper_d_execute_env=False,
    )
    assert ready["expandSourcesReady"] is True
    assert ready["thawEstrictoReady"] is True
    assert ready["paperDExecuteEnv"] is False
    assert ready["blockers"] == []


def test_gates_edge_parity_blocks_expand_even_if_p1_p5_pass() -> None:
    blocked = derive_a6_gates(
        auto_mark="PASS",
        strict_accept_ready=True,
        edge_report_parity=False,
        paper_d_execute_env=False,
    )
    assert blocked["expandSourcesReady"] is False
    assert "edge_report_parity" in blocked["blockers"]


def test_summarize_and_remember_last_propose(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "propose.jsonl"
    monkeypatch.setenv("BOLSA_ESTUDIO_AUTO_PROPOSE_PATH", str(path))
    reset_last_estudio_auto_propose()
    result = _propose_result()
    snap = summarize_estudio_auto_propose(result)
    assert snap["hitCount"] == 1
    assert snap["hitsBySource"] == {"estudio_alarma": 1}
    assert snap["skippedByReason"] == {"no_tradeplan": 1, "propose_error": 1}
    assert snap["durability"] == "jsonl"

    remember_estudio_auto_propose(result)
    stored = last_estudio_auto_propose()
    assert stored is not None
    assert stored["planId"] == "edo_abc"
    assert stored["executeStatus"] == "dry_run"
    assert path.is_file()
    reset_last_estudio_auto_propose()
    # Memoria vacía → hidrata desde JSONL
    hydrated = last_estudio_auto_propose()
    assert hydrated is not None
    assert hydrated["planId"] == "edo_abc"
    reset_last_estudio_auto_propose()


def test_remember_off_is_process_memory_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_ESTUDIO_AUTO_PROPOSE_PATH", "off")
    reset_last_estudio_auto_propose()
    assert resolve_propose_path() is None
    snap = remember_estudio_auto_propose(_propose_result())
    assert snap["durability"] == "process_memory"
    assert last_estudio_auto_propose() is not None
    reset_last_estudio_auto_propose()
    assert last_estudio_auto_propose() is None
    # No escribe bajo tmp (path off)
    assert not (tmp_path / "propose.jsonl").exists()


def test_recent_proposes_order_and_hydrate(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "propose.jsonl"
    monkeypatch.setenv("BOLSA_ESTUDIO_AUTO_PROPOSE_PATH", str(path))
    reset_last_estudio_auto_propose()
    remember_estudio_auto_propose(_propose_result(planId="edo_1", generatedAt="2026-08-30T10:00:00+00:00"))
    remember_estudio_auto_propose(_propose_result(planId="edo_2", generatedAt="2026-08-30T11:00:00+00:00"))
    remember_estudio_auto_propose(_propose_result(planId="edo_3", generatedAt="2026-08-30T12:00:00+00:00"))
    reset_last_estudio_auto_propose()
    recent = recent_estudio_auto_proposes(10)
    assert [r["planId"] for r in recent] == ["edo_3", "edo_2", "edo_1"]
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert json.loads(lines[-1])["planId"] == "edo_3"
    reset_last_estudio_auto_propose()


def test_remember_oserror_does_not_raise(tmp_path: Path, monkeypatch) -> None:
    # Directorio como "fichero" → open append falla
    bad = tmp_path / "not_a_file"
    bad.mkdir()
    monkeypatch.setenv("BOLSA_ESTUDIO_AUTO_PROPOSE_PATH", str(bad))
    reset_last_estudio_auto_propose()
    snap = remember_estudio_auto_propose(_propose_result(planId="edo_ok"))
    assert snap["planId"] == "edo_ok"
    assert last_estudio_auto_propose()["planId"] == "edo_ok"
    reset_last_estudio_auto_propose()


def test_build_report_does_not_flip_env(monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_ESTUDIO_AUTO_PROPOSE_PATH", "off")
    report = build_estudio_auto_telemetry(
        funnel=count_estudio_auto_funnel([_row(stance="buy", stars=4)]),
        auto_lane={
            "mark": "FAIL",
            "strictAcceptReady": False,
            "p1": {"mark": "FAIL", "need": 60},
        },
        last_propose=None,
        recent_proposes=[],
        paper_d_execute_env=False,
        lookback_days=120,
        as_of=date(2026, 8, 30),
    )
    assert report["schemaVersion"] == "estudio_auto_telemetry_v0"
    assert report["funnel"]["candidatesAlarma"] == 1
    assert report["edgeReport"]["parityWithSemi"] is True
    assert report["edgeReport"]["mark"] == "PASS"
    assert report["gates"]["expandSourcesReady"] is False
    assert report["gates"]["paperDExecuteEnv"] is False
    assert report["lastPropose"] is None
    assert report["recentProposes"] == []
    assert "≠ flip PAPER_D_EXECUTE" in report["rule"]
    assert any("memoria de proceso" in c for c in report["caveats"])


def test_build_report_includes_recent(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "propose.jsonl"
    monkeypatch.setenv("BOLSA_ESTUDIO_AUTO_PROPOSE_PATH", str(path))
    reset_last_estudio_auto_propose()
    remember_estudio_auto_propose(_propose_result(planId="edo_r"))
    recent = recent_estudio_auto_proposes()
    report = build_estudio_auto_telemetry(
        funnel=count_estudio_auto_funnel([]),
        auto_lane={"mark": "FAIL", "strictAcceptReady": False},
        last_propose=recent[0],
        recent_proposes=recent,
        paper_d_execute_env=False,
        lookback_days=30,
        as_of=date(2026, 8, 30),
    )
    assert report["lastPropose"]["planId"] == "edo_r"
    assert len(report["recentProposes"]) == 1
    assert any("JSONL" in c for c in report["caveats"])
    reset_last_estudio_auto_propose()
