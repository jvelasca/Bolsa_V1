"""AUTO-11 — reconstrucción del estado Adaptive desde el journal durable (puro sobre las filas).

Lo que se prueba es la FIDELIDAD de la reconstrucción, no el acceso a datos: que la racha de pausa
se rehaga con la MISMA regla que tenía el proceso vivo (una versión que deja de estar pausada corta
su racha, aparezca o no en el plan), que el valor se sature en el umbral del cooldown declarándolo,
que un reintento del sink no cuente dos veces el mismo turno, y que los tres límites —fuente no
leída, historia insuficiente y filas ilegibles— se declaren en vez de convertirse en un "0" que
permitiría levantar una pausa antes de su ventana mínima.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive import (
    AdaptivePlan,
    AllocationPlan,
    RotationDecision,
    RotationPlan,
)
from bolsa_application.auto_adaptive_journal import build_adaptive_recommendation_entry
from bolsa_application.auto_adaptive_recovery import (
    ADAPTIVE_STATE_WINDOW_DEFAULT,
    adaptive_state_unread,
    read_adaptive_state,
    rebuild_paused_cycles,
)

_ACCOUNT = "acc-1"
_POLICY = "auto9-v1"
#: Umbral real de la política (``ADAPTIVE_MIN_PAUSE_CYCLES_DEFAULT``): la saturación se prueba
#: contra él para que el test siga significando lo mismo si el default cambia.
_MIN_PAUSE = 3


def _row(
    as_of: str,
    *,
    paused: tuple[str, ...] = (),
    versions: tuple[str, ...] = ("v42",),
    policy: str = _POLICY,
) -> Any:
    """Fila durable construida con el CONTRATO real (no un payload a mano)."""
    decisions = tuple(
        RotationDecision(strategy_version=version, active=version not in paused)
        for version in versions
    )
    plan = AdaptivePlan(
        rotation=RotationPlan(decisions),
        allocation=AllocationPlan({}),
        regime="TREND_UP",
        policy_version=policy,
    )
    entry = build_adaptive_recommendation_entry(
        plan=plan, actor="auto-sim", as_of=as_of, account_id=_ACCOUNT
    )
    assert entry is not None
    return entry


def _at(minute: int) -> str:
    return f"2026-09-22T10:{minute:02d}:00Z"


def _read(rows: list[Any], **overrides: Any):
    base: dict[str, Any] = {
        "min_pause_cycles": _MIN_PAUSE,
        "running_policy_version": _POLICY,
        "window": ADAPTIVE_STATE_WINDOW_DEFAULT,
    }
    base.update(overrides)
    return read_adaptive_state(rows, **base)  # type: ignore[arg-type]


# ── La racha trailing, con la regla del proceso vivo ────────────────────────────────


def test_a_trailing_streak_is_rebuilt_from_the_journal() -> None:
    reading = _read(
        [
            _row(_at(4), paused=("v42",)),
            _row(_at(3), paused=("v42",)),
            _row(_at(2), paused=("v42",)),
            _row(_at(1)),
        ],
        window=4,
    )

    assert reading.paused_cycles == {"v42": 3}
    assert reading.evaluated == 4
    assert reading.bounded == (), "la racha se probó entera: encontró su corte"
    assert reading.saturated is False
    assert reading.insufficient_history is False


def test_the_streak_stops_at_the_first_active_evaluation() -> None:
    """El turno que reactivó la versión manda: la historia anterior NO se suma."""
    reading = _read(
        [
            _row(_at(5), paused=("v42",)),
            _row(_at(4)),
            _row(_at(3), paused=("v42",)),
            _row(_at(2), paused=("v42",)),
            _row(_at(1), paused=("v42",)),
        ]
    )

    assert reading.paused_cycles == {"v42": 1}


def test_a_version_that_disappears_from_the_plan_ends_its_streak() -> None:
    """Una versión fuera del plan cuenta a 0 en el mapa vivo: la racha no puede saltarse el hueco."""
    reading = _read(
        [
            _row(_at(3), paused=("v42",)),
            _row(_at(2), versions=("v99",)),  # v42 no está en el plan de ese turno
            _row(_at(1), paused=("v42",)),
        ]
    )

    assert reading.paused_cycles == {"v42": 1}


def test_a_version_never_paused_is_absent_from_the_counter() -> None:
    reading = _read([_row(_at(2), versions=("v42", "v99")), _row(_at(1), versions=("v42", "v99"))])

    assert reading.paused_cycles == {}
    assert reading.paused == ()


def test_a_retry_of_the_same_turn_does_not_double_the_streak() -> None:
    """Mismo ``decision_id`` ⇒ MISMA evaluación: contarla dos veces alargaría el cooldown."""
    reading = _read(
        [
            _row(_at(3), paused=("v42",)),
            _row(_at(3), paused=("v42",)),  # reintento del sink: mismo turno que la anterior
            _row(_at(2), paused=("v42",)),
            _row(_at(1)),
        ]
    )

    assert reading.paused_cycles == {"v42": 2}, "dos evaluaciones, no tres"
    assert reading.evaluated == 3
    assert reading.collapsed == 1
    assert reading.as_dict()["collapsedRows"] == 1


# ── Saturación y ventana: los límites se declaran ───────────────────────────────────


def test_the_counter_is_saturated_at_the_cooldown_threshold() -> None:
    """Por encima del umbral el valor exacto da igual: se publica el techo y se declara el suelo."""
    reading = _read(
        [_row(_at(minute), paused=("v42",)) for minute in range(1, 7)],
        min_pause_cycles=1,
        window=10,
    )

    assert reading.paused_cycles == {"v42": 2}, "techo = min_pause_cycles + 1"
    assert reading.bounded == ("v42",)
    assert reading.saturated is True


def test_insufficient_history_is_declared_when_the_window_is_not_filled() -> None:
    rows = [_row(_at(2), paused=("v42",)), _row(_at(1), paused=("v42",))]

    assert _read(rows, window=5).insufficient_history is True
    assert _read(rows, window=2).insufficient_history is False


def test_an_unreadable_row_cuts_the_streak_and_is_counted() -> None:
    """Fail-closed: no se afirma una pausa que no se puede leer, y el corte se declara."""
    unreadable = replace(_row(_at(3)), payload={"event": "adaptive_recommendation"})
    reading = _read(
        [
            _row(_at(4), paused=("v42",)),
            unreadable,
            _row(_at(2), paused=("v42",)),
            _row(_at(1), paused=("v42",)),
        ]
    )

    assert reading.paused_cycles == {"v42": 1}
    assert reading.unreadable == 1
    assert reading.as_dict()["unreadableRows"] == 1


def test_without_a_durable_source_the_reading_declares_the_gap() -> None:
    """``read_ok = False`` NO es "no había pausas": es "no se miró", y se declara distinto."""
    reading = adaptive_state_unread("reader_failed")

    assert reading.read_ok is False
    assert reading.paused_cycles == {}
    assert reading.evaluated == 0
    summary = reading.as_dict()
    assert summary["readOk"] is False
    assert summary["pausedCycles"] == {}


def test_an_empty_journal_read_ok_is_not_the_same_as_unread() -> None:
    """Cero filas LEÍDAS y cero filas que se pudieron leer son dos hechos: aquí se distinguen."""
    lectura = _read([])

    assert lectura.read_ok is True
    assert lectura.evaluated == 0
    assert lectura.paused_cycles == {}
    assert lectura.insufficient_history is True


# ── Continuidad de política ─────────────────────────────────────────────────────────


def test_a_policy_change_keeps_the_counter_and_declares_the_mismatch() -> None:
    """Resetear el contador al cambiar de política sería exactamente el bug que AUTO-11 cierra."""
    reading = _read(
        [
            _row(_at(4), paused=("v42",), policy="auto9-v1"),
            _row(_at(3), paused=("v42",), policy="auto9-v1"),
            _row(_at(2), paused=("v42",), policy="auto9-v2"),
            _row(_at(1)),
        ],
        running_policy_version="auto9-v2",
    )

    assert reading.paused_cycles == {"v42": 3}, "el contador NO se resetea con la política nueva"
    assert reading.policy_versions == ("auto9-v1", "auto9-v2"), "nuevas → viejas"
    assert reading.policy_version_mismatch is True


def test_a_uniform_history_under_the_running_policy_declares_no_mismatch() -> None:
    reading = _read(
        [_row(_at(2), paused=("v42",)), _row(_at(1), paused=("v42",))],
        running_policy_version=_POLICY,
    )

    assert reading.policy_versions == (_POLICY,)
    assert reading.policy_version_mismatch is False


def test_a_mixed_history_without_a_running_policy_is_declared_as_mixed() -> None:
    """Sin política en curso declarada, lo único afirmable es que la historia mezcla versiones."""
    reading = _read(
        [_row(_at(2), policy="auto9-v2"), _row(_at(1), policy="auto9-v1")],
        running_policy_version="",
    )

    assert reading.policy_versions == ("auto9-v2", "auto9-v1")
    assert reading.policy_version_mismatch is True


# ── Reproducibilidad y contrato del núcleo ──────────────────────────────────────────


def test_the_reading_is_invariant_to_the_order_of_the_rows() -> None:
    """Mismo material ⇒ misma lectura: el orden de entrada no es un dato (se ordena por instante)."""
    rows = [
        _row("2026-09-22T10:04:00+02:00", paused=("v42",)),  # 08:04Z
        _row("2026-09-22T07:00:00Z", paused=("v42",)),
        _row("2026-09-22T06:00:00Z"),
    ]

    forward = _read(list(rows))
    backward = _read(list(reversed(rows)))

    assert forward.paused_cycles == backward.paused_cycles == {"v42": 2}
    assert forward.evaluated == backward.evaluated


def test_the_core_reports_the_streak_and_the_collapsed_rows() -> None:
    rows = [_row(_at(2), paused=("v42",)), _row(_at(1), paused=("v42",))]

    counts, reasons, collapsed = rebuild_paused_cycles(rows, min_pause_cycles=_MIN_PAUSE)

    assert counts == {"v42": 2}
    assert reasons == {"v42": "bounded"}, "la ventana se agotó sin encontrar el corte"
    assert collapsed == 0


def test_the_summary_publishes_every_declared_limit() -> None:
    reading = _read([_row(_at(2), paused=("v42",))], min_pause_cycles=0, window=5)
    summary = reading.as_dict()

    assert summary["paused"] == ["v42"]
    assert summary["requested"] == 5
    assert summary["bounded"] == ["v42"]
    assert summary["insufficientHistory"] is True
    assert summary["policyVersions"] == [_POLICY]
    assert summary["policyVersionMismatch"] is False


# ── El ancla durable del journal (AUTO-13, paso 2) ──────────────────────────────────


def test_the_newest_row_declares_the_durable_anchor() -> None:
    """El ancla es el instante de la evidencia MÁS NUEVA, no el de la primera de la lista."""
    reading = _read([_row(_at(5)), _row(_at(9)), _row(_at(2))])

    assert reading.last_published_at == "2026-09-22T10:09:00+00:00"
    assert reading.as_dict()["lastPublishedAt"] == "2026-09-22T10:09:00+00:00"


def test_an_empty_journal_has_no_anchor() -> None:
    """Leído y vacío no es un ancla: ``None`` (no se supone una publicación que no existe)."""
    assert _read([]).last_published_at is None


def test_a_row_without_a_readable_instant_does_not_become_the_anchor() -> None:
    """Una fila sin instante legible se ordena al final: no puede fechar la evidencia."""
    dated = _row(_at(9))
    undated = replace(
        dated, id="JNL-sin-fecha", decision_id="dec-adap-sin-fecha", created_at=None
    )

    reading = _read([undated, dated])

    assert reading.last_published_at == "2026-09-22T10:09:00+00:00"
    assert reading.evaluated == 2, "las dos filas son de turnos distintos: ninguna se colapsa"


def test_an_unreadable_source_declares_no_anchor() -> None:
    """``read_ok=False`` no puede fingir una antigüedad: el ancla es ``None``, como el contador."""
    reading = adaptive_state_unread("reader_failed", window=ADAPTIVE_STATE_WINDOW_DEFAULT)

    assert reading.last_published_at is None
    assert reading.as_dict()["lastPublishedAt"] is None
    assert reading.as_dict()["reactivatedAt"] == {}


# ── ``reactivated_at``: el corte durable de la rampa (AUTO-13, paso 4) ──────────────


def test_the_journal_declares_when_a_version_left_its_pause() -> None:
    """El corte es el turno MÁS VIEJO de la racha activa actual: ahí empezó la reincorporación."""
    reading = _read(
        [
            _row(_at(5)),
            _row(_at(4)),
            _row(_at(3)),
            _row(_at(2), paused=("v42",)),
            _row(_at(1), paused=("v42",)),
        ],
        window=5,
    )

    assert reading.paused_cycles == {}, "ya no está pausada: la racha es 0"
    assert reading.reactivated_at == {"v42": "2026-09-22T10:03:00+00:00"}


def test_a_version_that_never_paused_declares_no_reactivation() -> None:
    """Una versión que no estuvo pausada dentro de la ventana NO tiene corte: no se inventa."""
    reading = _read([_row(_at(3)), _row(_at(2)), _row(_at(1))], window=3)

    assert reading.reactivated_at == {}


def test_a_version_still_paused_declares_no_reactivation() -> None:
    reading = _read([_row(_at(3), paused=("v42",)), _row(_at(2), paused=("v42",))])

    assert reading.reactivated_at == {}


def test_the_reactivation_does_not_confuse_a_pause_before_it_with_a_later_one() -> None:
    """La reincorporación es el corte MÁS RECIENTE: la racha activa es la de arriba."""
    reading = _read(
        [
            _row(_at(7)),
            _row(_at(6)),
            _row(_at(5), paused=("v42",)),
            _row(_at(4), paused=("v42",)),
            _row(_at(3)),
            _row(_at(2)),
            _row(_at(1)),
        ],
        window=7,
    )

    assert reading.reactivated_at == {"v42": "2026-09-22T10:06:00+00:00"}


def test_an_unreadable_row_cuts_the_reactivation_instead_of_faking_it() -> None:
    """Fail-closed: no se fecha el corte a través de un turno ilegible (sería inventar la fecha)."""
    broken = replace(_row(_at(4)), payload={"event": "adaptive_recommendation"})
    reading = _read([_row(_at(5)), broken, _row(_at(3), paused=("v42",))], window=3)

    assert reading.reactivated_at == {}


def test_a_recovered_version_is_the_one_that_appears_in_the_reactivation_map() -> None:
    reading = _read(
        [
            _row(_at(4), versions=("v42", "v99"), paused=("v99",)),
            _row(_at(3), versions=("v42", "v99"), paused=("v42", "v99")),
            _row(_at(2), versions=("v42", "v99")),
        ],
        window=3,
    )

    assert reading.reactivated_at == {"v42": "2026-09-22T10:04:00+00:00"}
