"""V2.98 · PAPER WINDOW CERTIFICATION — contratos puros del certificador de la ventana PAPER.

Test hermético (sin red ni PostgreSQL) del certificador tipado: fija que

1. Cada criterio por debajo del umbral deja el veredicto en ``INCONCLUSIVE`` con el criterio
   faltante CORRECTO (``days`` / ``episodes`` / ``measurable_cycles``).
2. ``≥4 días`` / ``≥2 episodios`` / ``≥32 ciclos medibles`` ⇒ ``READY`` sin criterios faltantes.
3. ``UNKNOWN ≠ 0``: un material NO medido declara los tres conteos ``None`` (hueco), mientras que
   un material SÍ medido y vacío declara ceros **medidos**. Nunca se confunden.

Los umbrales NO se re-declaran aquí: se importan de su fuente única (``operability_window``).
"""

from __future__ import annotations

from typing import Any

from bolsa_application.operability_window import (
    MARKET_WINDOW_INCONCLUSIVE,
    MARKET_WINDOW_MIN_CYCLES,
    MARKET_WINDOW_MIN_DAYS,
    MARKET_WINDOW_MIN_EPISODES,
    MARKET_WINDOW_READY,
)
from bolsa_application.paper_window_certification import (
    CERTIFICATION_AXIS,
    CRITERION_CYCLES,
    CRITERION_DAYS,
    CRITERION_EPISODES,
    PAPER_WINDOW_CERTIFICATION_SCHEMA,
    PaperWindowMaterial,
    certify_paper_window,
)


def _row(day: str, regime: str, cycles: int) -> dict[str, Any]:
    """Fila diaria de la MISMA forma que ``window_gate`` consume (día + régimen + ciclos medibles)."""
    return {"day": day, "regime": regime, "regimes": [regime], "measurableCycles": cycles}


def _by_id(certification: Any) -> dict[str, Any]:
    return {criterion.id: criterion for criterion in certification.criteria}


# ── El veredicto y el criterio faltante correcto ──────────────────────────────────────────────


def test_below_min_days_is_inconclusive_flagged_on_days() -> None:
    rows = [
        _row("2026-09-24", "trend_up", 16),
        _row("2026-09-25", "trend_down", 8),
        _row("2026-09-26", "trend_up", 8),
    ]
    cert = certify_paper_window(PaperWindowMaterial(measured=True, rows=rows))
    assert cert.verdict == MARKET_WINDOW_INCONCLUSIVE
    assert cert.ready is False
    assert cert.days == 3
    assert cert.days < MARKET_WINDOW_MIN_DAYS
    assert cert.episodes == 2
    assert cert.measurable_cycles == 32
    assert cert.missing == (CRITERION_DAYS,)
    criteria = _by_id(cert)
    assert criteria[CRITERION_DAYS].met is False
    assert criteria[CRITERION_DAYS].actual == 3
    assert criteria[CRITERION_DAYS].required == MARKET_WINDOW_MIN_DAYS
    assert criteria[CRITERION_EPISODES].met is True
    assert criteria[CRITERION_CYCLES].met is True


def test_below_min_episodes_is_inconclusive_flagged_on_episodes() -> None:
    rows = [_row(f"2026-09-2{day}", "trend_up", 8) for day in range(4, 8)]
    cert = certify_paper_window(PaperWindowMaterial(measured=True, rows=rows))
    assert cert.verdict == MARKET_WINDOW_INCONCLUSIVE
    assert cert.days == MARKET_WINDOW_MIN_DAYS
    assert cert.episodes == 1
    assert cert.measurable_cycles == 32
    assert cert.missing == (CRITERION_EPISODES,)
    assert _by_id(cert)[CRITERION_EPISODES].required == MARKET_WINDOW_MIN_EPISODES


def test_below_min_cycles_is_inconclusive_flagged_on_cycles() -> None:
    rows = [
        _row("2026-09-24", "trend_up", 4),
        _row("2026-09-25", "trend_up", 4),
        _row("2026-09-26", "trend_down", 4),
        _row("2026-09-27", "trend_down", 4),
    ]
    cert = certify_paper_window(PaperWindowMaterial(measured=True, rows=rows))
    assert cert.verdict == MARKET_WINDOW_INCONCLUSIVE
    assert cert.days == 4
    assert cert.episodes == 2
    assert cert.measurable_cycles == 16
    assert cert.missing == (CRITERION_CYCLES,)
    assert _by_id(cert)[CRITERION_CYCLES].required == MARKET_WINDOW_MIN_CYCLES


def test_all_criteria_met_is_ready_without_missing() -> None:
    rows = [
        _row("2026-09-24", "trend_up", 8),
        _row("2026-09-25", "trend_up", 8),
        _row("2026-09-26", "trend_down", 8),
        _row("2026-09-27", "trend_down", 8),
    ]
    cert = certify_paper_window(PaperWindowMaterial(measured=True, rows=rows))
    assert cert.verdict == MARKET_WINDOW_READY
    assert cert.ready is True
    assert cert.days == MARKET_WINDOW_MIN_DAYS
    assert cert.episodes == MARKET_WINDOW_MIN_EPISODES
    assert cert.measurable_cycles == MARKET_WINDOW_MIN_CYCLES
    assert cert.missing == ()
    assert all(criterion.met for criterion in cert.criteria)
    assert cert.schema_version == PAPER_WINDOW_CERTIFICATION_SCHEMA
    assert cert.axis == CERTIFICATION_AXIS


def test_counts_calendar_buckets_not_rows() -> None:
    """Cuatro filas del MISMO día son un solo cubo de calendario: no hay cuatro días."""
    rows = [_row("2026-09-27", "trend_up", 10) for _ in range(4)]
    cert = certify_paper_window(PaperWindowMaterial(measured=True, rows=rows))
    assert cert.days == 1
    assert cert.verdict == MARKET_WINDOW_INCONCLUSIVE


# ── UNKNOWN ≠ 0 ──────────────────────────────────────────────────────────────────────────────


def test_unmeasured_material_declares_none_not_zero() -> None:
    """Fuente NO leída ⇒ hueco: los tres conteos son ``None``, jamás un ``0`` de relleno."""
    cert = certify_paper_window(PaperWindowMaterial(measured=False, rows=[]))
    assert cert.measured is False
    assert cert.days is None
    assert cert.episodes is None
    assert cert.measurable_cycles is None
    assert cert.verdict == MARKET_WINDOW_INCONCLUSIVE
    assert cert.ready is False
    assert cert.missing == (CRITERION_DAYS, CRITERION_EPISODES, CRITERION_CYCLES)
    assert all(criterion.measured is False for criterion in cert.criteria)
    # Un hueco (None) NO es un cero: el tipo y el valor son distintos.
    assert cert.days != 0
    assert cert.as_dict()["days"] is None


def test_measured_but_empty_material_declares_a_measured_zero() -> None:
    """Fuente SÍ leída y vacía ⇒ cero MEDIDO (no un hueco): mismo veredicto, distinto hecho."""
    cert = certify_paper_window(PaperWindowMaterial(measured=True, rows=[]))
    assert cert.measured is True
    assert cert.days == 0
    assert cert.episodes == 0
    assert cert.measurable_cycles == 0
    assert cert.verdict == MARKET_WINDOW_INCONCLUSIVE
    assert cert.missing == (CRITERION_DAYS, CRITERION_EPISODES, CRITERION_CYCLES)
    assert all(criterion.measured is True for criterion in cert.criteria)
    assert all(criterion.met is False for criterion in cert.criteria)


def test_measured_none_and_measured_zero_are_not_confused() -> None:
    """Contraste explícito: un material con un hueco no se lee igual que uno con un cero medido."""
    unmeasured = certify_paper_window(PaperWindowMaterial(measured=False, rows=[]))
    measured_zero = certify_paper_window(PaperWindowMaterial(measured=True, rows=[]))
    assert unmeasured.days is None and measured_zero.days == 0
    assert unmeasured.measured is False and measured_zero.measured is True
    # Un material no medido NUNCA puede promocionar, aunque el conteo se leyera como cero.
    assert unmeasured.ready is False


def test_unmeasured_rows_are_not_counted_even_if_present() -> None:
    """Con ``measured=False`` las filas presentes no se cuentan: el hueco manda sobre el material."""
    rows = [
        _row("2026-09-24", "trend_up", 8),
        _row("2026-09-25", "trend_up", 8),
        _row("2026-09-26", "trend_down", 8),
        _row("2026-09-27", "trend_down", 8),
    ]
    cert = certify_paper_window(PaperWindowMaterial(measured=False, rows=rows))
    assert cert.days is None
    assert cert.episodes is None
    assert cert.measurable_cycles is None
    assert cert.verdict == MARKET_WINDOW_INCONCLUSIVE


def test_as_dict_publishes_thresholds_axis_and_missing() -> None:
    cert = certify_paper_window(PaperWindowMaterial(measured=True, rows=[]))
    payload = cert.as_dict()
    assert payload["thresholds"] == {
        "days": MARKET_WINDOW_MIN_DAYS,
        "episodes": MARKET_WINDOW_MIN_EPISODES,
        "measurableCycles": MARKET_WINDOW_MIN_CYCLES,
    }
    assert payload["axis"] == CERTIFICATION_AXIS
    assert payload["missingCriterionIds"] == [CRITERION_DAYS, CRITERION_EPISODES, CRITERION_CYCLES]
    assert payload["verdict"] == MARKET_WINDOW_INCONCLUSIVE
