"""R6 — el experimento TOP DÍA D (F-D) vive en servidor, append-only.

Fija las tres afirmaciones que la auditoría LAB pidió demostrar:

* guardar un experimento **inserta** una fila de ``research_evidence`` con
  ``source='dia_d_experiment_top'`` y **no** toca el TOP operativo (F-hoy);
* la procedencia la deriva el servidor: un ``runId`` inexistente o de otro
  instrumento se rechaza, y el nivel se publica derivado, nunca declarado;
* el hueco se declara: sin experimento la lectura devuelve ``None`` (que la API
  expone como ``data=null``), y una fecha futura no es un experimento.

@see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §9 (R6)
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from bolsa_application.dia_d_experiment_top import (
    DIA_D_EXPERIMENT_TOP_SOURCE,
    MATH_VERSION_DIA_D_EXPERIMENT_TOP_V0,
    DiaDExperimentTopRejected,
    GetDiaDExperimentTop,
    SaveDiaDExperimentTop,
    TopProvenanceError,
    validate_as_of_dia_d,
)
from bolsa_domain.entities.research_evidence import ResearchEvidence

_PASS_METRICS = {
    "returnBasis": "net",
    "netReturnPct": 4.2,
    "roundTripCostBps": 32.0,
    "netTradeCount": 40,
    "excessReturnPct": 1.1,
    "expectancyCurrency": 12.5,
}

_TODAY = date(2026, 11, 16)


class _Run:
    def __init__(self, instrument_id: str, metrics: dict[str, Any] | None) -> None:
        self.instrument_id = instrument_id
        self.manifest = {"outputs": {"isMetrics": metrics}}


class _Backtests:
    def __init__(self, runs: dict[str, _Run]) -> None:
        self._runs = runs

    async def get_run(self, run_id: str) -> _Run | None:
        return self._runs.get(run_id)


class _EvidenceRepo:
    def __init__(self, rows: list[ResearchEvidence] | None = None) -> None:
        self.rows = list(rows or [])
        self.inserted: list[dict[str, Any]] = []

    async def insert_evidence(self, **kwargs: Any) -> ResearchEvidence:
        self.inserted.append(kwargs)
        row = ResearchEvidence(
            id=f"ev-{len(self.inserted)}",
            instrument_id=kwargs["instrument_id"],
            level=kwargs["level"],
            source=kwargs["source"],
            evidence_weight=kwargs["evidence_weight"],
            summary=kwargs["summary"],
            created_at="2026-11-16T10:00:00+00:00",
            math_version=kwargs.get("math_version"),
        )
        self.rows.insert(0, row)
        return row

    async def list_evidence(
        self,
        *,
        instrument_id: str | None = None,
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        level: str | None = None,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchEvidence], int]:
        rows = [
            row
            for row in self.rows
            if (instrument_id is None or row.instrument_id == instrument_id)
            and (source is None or row.source == source)
            and (level is None or row.level == level)
        ]
        return rows, len(rows)


def _slot(rank: int = 1, **overrides: Any) -> dict[str, Any]:
    slot: dict[str, Any] = {
        "rank": rank,
        "label": f"Estrategia {rank}",
        "stars": 4.0,
        "score": 1.2,
        "source": "optimized",
        "runId": f"run-{rank}",
    }
    slot.update(overrides)
    return slot


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "instrumentId": "inst-1",
        "timeframe": "1d",
        "asOfDiaD": "2026-09-15",
        "slots": [_slot(1), _slot(2)],
        "coachHeadline": "Dos candidatas medidas",
        "productionTop1AtSave": {
            "strategyDefinitionId": "strat-9",
            "label": "F-hoy #1",
            "strategyType": "sma_crossover",
        },
    }
    payload.update(overrides)
    return payload


def _backtests(**overrides: _Run) -> _Backtests:
    runs = {
        "run-1": _Run("inst-1", dict(_PASS_METRICS)),
        "run-2": _Run("inst-1", dict(_PASS_METRICS)),
    }
    runs.update(overrides)
    return _Backtests(runs)


# --- validación de la fecha -------------------------------------------------


def test_as_of_dia_d_must_be_iso_and_past() -> None:
    assert validate_as_of_dia_d("2026-09-15", today=_TODAY) == "2026-09-15"
    with pytest.raises(DiaDExperimentTopRejected):
        validate_as_of_dia_d("2026-09-31", today=_TODAY)
    with pytest.raises(DiaDExperimentTopRejected):
        validate_as_of_dia_d("2026-11-17", today=_TODAY)
    # El propio día D es válido: el experimento mira un cierre ya conocido.
    assert validate_as_of_dia_d("2026-11-16", today=_TODAY) == "2026-11-16"


def test_as_of_dia_d_rejects_free_text() -> None:
    with pytest.raises(DiaDExperimentTopRejected):
        validate_as_of_dia_d("ayer", today=_TODAY)


# --- guardado append-only ---------------------------------------------------


@pytest.mark.asyncio
async def test_save_inserts_evidence_with_experiment_source() -> None:
    repo = _EvidenceRepo()
    use_case = SaveDiaDExperimentTop(repo, backtests=_backtests())

    record = await use_case.execute(_payload(), today=_TODAY)

    assert len(repo.inserted) == 1
    inserted = repo.inserted[0]
    assert inserted["source"] == DIA_D_EXPERIMENT_TOP_SOURCE
    assert inserted["math_version"] == MATH_VERSION_DIA_D_EXPERIMENT_TOP_V0
    assert inserted["instrument_id"] == "inst-1"
    assert inserted["summary"]["kind"] == "dia_d_experiment_top"
    assert inserted["summary"]["sandbox"] is True
    assert inserted["summary"]["asOfDiaD"] == "2026-09-15"
    # El sello temporal lo pone el servidor: el resumen no acepta `savedAt`.
    assert "savedAt" not in inserted["summary"]
    assert record.saved_at == "2026-11-16T10:00:00+00:00"
    assert record.top1 is not None and record.top1["rank"] == 1


@pytest.mark.asyncio
async def test_two_saves_append_two_rows() -> None:
    repo = _EvidenceRepo()
    use_case = SaveDiaDExperimentTop(repo, backtests=_backtests())

    first = await use_case.execute(_payload(), today=_TODAY)
    second = await use_case.execute(_payload(coachHeadline="Segunda pasada"), today=_TODAY)

    assert len(repo.inserted) == 2  # append-only: nunca update
    assert first.id != second.id
    assert repo.rows[0].summary["coachHeadline"] == "Segunda pasada"


@pytest.mark.asyncio
async def test_level_is_c_when_every_slot_cites_a_verified_run() -> None:
    repo = _EvidenceRepo()
    await SaveDiaDExperimentTop(repo, backtests=_backtests()).execute(_payload(), today=_TODAY)

    assert repo.inserted[0]["level"] == "C"
    assert repo.inserted[0]["evidence_weight"] == pytest.approx(0.25)
    assert repo.inserted[0]["summary"]["provenance"]["evidenceLevel"] == "lab_validated"


@pytest.mark.asyncio
async def test_level_is_d_when_a_slot_has_no_run() -> None:
    repo = _EvidenceRepo()
    await SaveDiaDExperimentTop(repo, backtests=_backtests()).execute(
        _payload(slots=[_slot(1), _slot(2, runId=None)]), today=_TODAY
    )

    assert repo.inserted[0]["level"] == "D"
    assert repo.inserted[0]["evidence_weight"] == pytest.approx(0.0)
    provenance = repo.inserted[0]["summary"]["provenance"]
    assert provenance["evidenceLevel"] == "in_sample_only"
    assert provenance["slots"][1]["reason"] == "sin_run_id"


@pytest.mark.asyncio
async def test_gross_run_never_claims_lab_validated() -> None:
    """Un run sin coste medido no aprueba P1: el experimento lo publica tal cual."""
    gross = dict(_PASS_METRICS, returnBasis="gross")
    repo = _EvidenceRepo()
    await SaveDiaDExperimentTop(
        repo, backtests=_backtests(**{"run-1": _Run("inst-1", gross)})
    ).execute(_payload(), today=_TODAY)

    provenance = repo.inserted[0]["summary"]["provenance"]
    assert provenance["evidenceLevel"] == "in_sample_only"
    assert provenance["slots"][0]["p1Status"] != "pass"


@pytest.mark.asyncio
async def test_unknown_run_is_rejected() -> None:
    repo = _EvidenceRepo()
    use_case = SaveDiaDExperimentTop(repo, backtests=_backtests())

    with pytest.raises(TopProvenanceError):
        await use_case.execute(_payload(slots=[_slot(1, runId="run-fantasma")]), today=_TODAY)
    assert repo.inserted == []


@pytest.mark.asyncio
async def test_run_from_another_instrument_is_rejected() -> None:
    repo = _EvidenceRepo()
    use_case = SaveDiaDExperimentTop(
        repo, backtests=_backtests(**{"run-2": _Run("inst-9", dict(_PASS_METRICS))})
    )

    with pytest.raises(TopProvenanceError):
        await use_case.execute(_payload(), today=_TODAY)
    assert repo.inserted == []


@pytest.mark.asyncio
async def test_ranks_must_be_consecutive() -> None:
    repo = _EvidenceRepo()
    use_case = SaveDiaDExperimentTop(repo, backtests=_backtests())

    with pytest.raises(DiaDExperimentTopRejected):
        await use_case.execute(_payload(slots=[_slot(1), _slot(3)]), today=_TODAY)
    assert repo.inserted == []


@pytest.mark.asyncio
async def test_future_day_is_rejected_and_writes_nothing() -> None:
    repo = _EvidenceRepo()
    use_case = SaveDiaDExperimentTop(repo, backtests=_backtests())

    with pytest.raises(DiaDExperimentTopRejected):
        await use_case.execute(_payload(asOfDiaD="2027-01-02"), today=_TODAY)
    assert repo.inserted == []


@pytest.mark.asyncio
async def test_missing_instrument_is_rejected() -> None:
    repo = _EvidenceRepo()
    with pytest.raises(DiaDExperimentTopRejected):
        await SaveDiaDExperimentTop(repo, backtests=_backtests()).execute(
            _payload(instrumentId=""), today=_TODAY
        )


# --- lectura: el experimento vigente ---------------------------------------


@pytest.mark.asyncio
async def test_load_returns_the_latest_experiment_for_the_day() -> None:
    repo = _EvidenceRepo()
    save = SaveDiaDExperimentTop(repo, backtests=_backtests())
    await save.execute(_payload(coachHeadline="primera"), today=_TODAY)
    await save.execute(_payload(coachHeadline="segunda"), today=_TODAY)

    record = await GetDiaDExperimentTop(repo).execute(
        instrument_id="inst-1", timeframe="1d", as_of_dia_d="2026-09-15"
    )

    assert record is not None
    assert record.coach_headline == "segunda"


@pytest.mark.asyncio
async def test_load_does_not_mix_days_or_timeframes() -> None:
    repo = _EvidenceRepo()
    save = SaveDiaDExperimentTop(repo, backtests=_backtests())
    await save.execute(_payload(asOfDiaD="2026-09-15"), today=_TODAY)
    await save.execute(_payload(asOfDiaD="2026-09-10"), today=_TODAY)
    await save.execute(_payload(timeframe="4h"), today=_TODAY)

    loader = GetDiaDExperimentTop(repo)
    day = await loader.execute(instrument_id="inst-1", timeframe="1d", as_of_dia_d="2026-09-10")
    four_hours = await loader.execute(
        instrument_id="inst-1", timeframe="4h", as_of_dia_d="2026-09-15"
    )

    assert day is not None and day.as_of_dia_d == "2026-09-10"
    assert day.timeframe == "1d"
    assert four_hours is not None and four_hours.timeframe == "4h"


@pytest.mark.asyncio
async def test_load_declares_the_gap() -> None:
    repo = _EvidenceRepo()
    loader = GetDiaDExperimentTop(repo)

    missing = await loader.execute(instrument_id="inst-1", timeframe="1d", as_of_dia_d="2026-09-15")

    assert missing is None  # «Sin dato todavía», nunca un experimento vacío
    assert (
        await loader.execute(instrument_id="inst-1", timeframe="1d", as_of_dia_d="no-es-fecha")
        is None
    )
    assert (
        await GetDiaDExperimentTop(None).execute(
            instrument_id="inst-1", timeframe="1d", as_of_dia_d="2026-09-15"
        )
        is None
    )


@pytest.mark.asyncio
async def test_other_instruments_experiments_are_not_returned() -> None:
    repo = _EvidenceRepo()
    await SaveDiaDExperimentTop(repo, backtests=_backtests()).execute(_payload(), today=_TODAY)

    record = await GetDiaDExperimentTop(repo).execute(
        instrument_id="inst-2", timeframe="1d", as_of_dia_d="2026-09-15"
    )
    assert record is None
