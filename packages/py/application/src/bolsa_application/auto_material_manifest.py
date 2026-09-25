"""AUTO-20B — MANIFEST del material de una exportación PAPER (declaración, no runtime state).

Qué resuelve: cuando el exportador vuelca los ciclos reales al JSON que consume el instrumento
de calibración, hace falta poder AUDITAR que el material que entra es exactamente el que
creemos. Este módulo cuenta y declara ese material —fill leídos, ciclos cerrados, ciclos con y
sin denominador, versiones, regímenes, fricción aplicada, reservas leídas— y le pega la huella
de ``auto_material_manifest`` (``analytics``).

Tres reglas duras, declaradas en vez de asumidas:

* **Los conteos salen del MISMO material que el instrumento.** ``closedCycles`` es el número de
  filas de ``adaptive_instrument_cycles`` (sin un segundo FIFO) y "con riesgo" se lee de la
  propia fila del instrumento (``riskAmount``), no de una reconstrucción paralela. Un conteo
  que pudiera divergir del instrumento sería peor que no tenerlo.
* **El hueco se declara, no se disimula.** ``cyclesWithoutRisk``/``cyclesWithoutVersion``/
  ``cyclesWithoutRegime`` son cuentas explícitas; nunca se colapsan en el total. Un material
  sin reservas no es un fallo del instrumento: es un hecho que el manifest publica.
* **No es estado durable.** Este manifest viaja en el JSON de la exportación (artefacto de
  investigación) y NO se escribe en el journal ni en ninguna tabla: el freeze no se toca.

Read-only: no escribe nada.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from bolsa_analytics.cognitive.auto_evidence_report import (
    EXECUTION_REALITY_VIRTUAL_PAPER,
)
from bolsa_analytics.cognitive.auto_material_manifest import (
    MATERIAL_FINGERPRINT_METHOD,
    material_fingerprint,
)
from bolsa_analytics.cognitive.measurement import MEASUREMENT_COMPLETE

__all__ = [
    "MATERIAL_RISK_BASIS",
    "build_material_manifest",
]

#: De dónde sale el DENOMINADOR de R del material: la reserva de entrada comprometida. Se
#: publica para que un neto ``applied`` y un denominador ``reserved_risk`` no se confundan con
#: otra base en una comparación entre versiones.
MATERIAL_RISK_BASIS = "reservation_reserved_risk"


def _clean(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _number(value: Any) -> Decimal | None:
    """``Decimal``/``str``/``float`` → ``Decimal`` finito, o ``None`` (nunca un cero de relleno)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


def _field(row: Any, *names: str) -> Any:
    if isinstance(row, Mapping):
        for name in names:
            if name in row:
                return row[name]
        return None
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    return None


def _has_risk(row: Any) -> bool:
    """¿La fila del instrumento declara un denominador positivo? (misma regla que el R)."""
    risk = _number(_field(row, "riskAmount", "risk_amount"))
    return risk is not None and risk > 0


def _has_applied_cost(row: Any) -> bool:
    """¿La fila trae fricción aplicada MEDIDA? (el instrumento solo la publica si es ``COMPLETE``)."""
    applied = _field(row, "costApplied", "cost_applied")
    if isinstance(applied, Mapping):
        return _clean(applied.get("measurement")) == MEASUREMENT_COMPLETE
    return applied is not None


def _version_of(row: Any) -> str:
    return _clean(_field(row, "strategyVersion", "strategy_version"))


def _regime_of(row: Any) -> str:
    return _clean(_field(row, "regime", "marketRegime", "market_regime"))


def _perimeter_counts(
    fills_by_version: Mapping[str | None, int] | None,
    requested_versions: Sequence[str],
) -> dict[str, int | None]:
    """(PURA) el contorno del volcado: total de fills de la cuenta y cuántos quedan fuera.

    Se declara, no se incluye: el universo medido NO cambia. Sin el agregado del store los
    conteos quedan ``None`` ("no medido"), nunca un ``0`` que diría "no hay excluidos".
    """
    if fills_by_version is None:
        return {
            "fillsTotalForAccount": None,
            "fillsSelected": None,
            "fillsExcludedNoVersion": None,
            "fillsExcludedOtherVersion": None,
        }
    counts = {key: int(value) for key, value in fills_by_version.items()}
    total = sum(counts.values())
    no_version = counts.get(None, 0)
    # Dedupe: una versión repetida en el CLI no debe contar sus fills dos veces.
    selected = sum(counts.get(str(version), 0) for version in dict.fromkeys(requested_versions))
    return {
        "fillsTotalForAccount": total,
        "fillsSelected": selected,
        "fillsExcludedNoVersion": no_version,
        "fillsExcludedOtherVersion": total - selected - no_version,
    }


def build_material_manifest(
    *,
    account_id: str | None,
    requested_versions: Sequence[str],
    fills: Iterable[Any],
    cycles: Sequence[Any],
    reservations_read: int,
    risk_read_saturated: bool,
    export_timestamp: str,
    material_origin: str,
    fills_by_version: Mapping[str | None, int] | None = None,
    execution_reality: str = EXECUTION_REALITY_VIRTUAL_PAPER,
    broker_venue: str | None = None,
    regime_confirmed: int = 0,
    regime_absent: int = 0,
    regime_unconfirmed: int = 0,
    regime_not_derivable: int = 0,
) -> dict[str, Any]:
    """(PURA) declaración auditable del material exportado + su huella.

    ``cycles`` son las filas de ``adaptive_instrument_cycles`` (el MISMO material que mide el
    instrumento): de ahí salen ``closedCycles`` y las cuentas de riesgo, versión y régimen. La
    huella se calcula sobre esas filas con ``material_fingerprint`` (analytics).

    ``material_origin`` es obligatorio: separar el material PAPER REAL del fixture sintético no
    puede depender de un valor por defecto que mienta. ``fills_by_version`` (AUTO-20C) es el
    agregado del store con el que se DECLARA el perímetro (fills sin versión / de otra versión);
    no altera el universo ni la huella. ``execution_reality``/``broker_venue`` declaran que el
    material es PAPER **virtual** (``EXECUTION_REALITY_VIRTUAL_PAPER`` por defecto).
    """
    rows = list(cycles)
    total = len(rows)
    with_risk = sum(1 for row in rows if _has_risk(row))
    with_version = sum(1 for row in rows if _version_of(row))
    without_identity = sum(
        1 for row in rows if not _clean(_field(row, "cycleId", "cycle_id"))
    )
    applied = sum(1 for row in rows if _has_applied_cost(row))

    per_version: dict[str, dict[str, int]] = {}
    observed_versions: set[str] = set()
    observed_regimes: set[str] = set()
    for row in rows:
        version = _version_of(row)
        if version:
            observed_versions.add(version)
            cell = per_version.setdefault(version, {"cycles": 0, "withRisk": 0, "withoutRisk": 0})
            cell["cycles"] += 1
            if _has_risk(row):
                cell["withRisk"] += 1
            else:
                cell["withoutRisk"] += 1
        regime = _regime_of(row)
        if regime:
            observed_regimes.add(regime)
    per_version = {version: per_version[version] for version in sorted(per_version)}

    requested = [str(v) for v in requested_versions]
    requested_set = {version for version in requested if version}
    observed = sorted(observed_versions)

    return {
        "account": _clean(account_id) or None,
        "requestedStrategyVersions": requested,
        "observedStrategyVersions": observed,
        "versionsRequestedWithoutMaterial": sorted(requested_set - observed_versions),
        "versionsObservedNotRequested": sorted(observed_versions - requested_set),
        "materialOrigin": material_origin,
        "executionReality": execution_reality,
        "brokerVenue": broker_venue,
        "fillsRead": len(list(fills)),
        **_perimeter_counts(fills_by_version, requested),
        "closedCycles": total,
        "cyclesWithRisk": with_risk,
        "cyclesWithoutRisk": total - with_risk,
        "cyclesWithVersion": with_version,
        "cyclesWithoutVersion": total - with_version,
        "cyclesWithoutIdentity": without_identity,
        "costAppliedCycles": applied,
        "regimesPresent": sorted(observed_regimes),
        "cyclesWithoutRegime": regime_absent + regime_unconfirmed + regime_not_derivable,
        "perVersion": per_version,
        "regimeRead": {
            "confirmed": regime_confirmed,
            "absent": regime_absent,
            "unconfirmed": regime_unconfirmed,
            "notDerivable": regime_not_derivable,
        },
        "reservationsRead": int(reservations_read),
        # ``True`` ⇒ la lectura de reservas pudo agotar una página sin garantizar completitud:
        # el exportador NO declara el material completo (fail-closed) y lo dice aquí también.
        # ``False`` NO significa "todas las reservas existen": significa que la lectura paginada
        # TERMINÓ de forma considerada completa. Lo que de verdad hay se lee en ``reservationsRead``
        # y en ``cyclesWithRisk``/``cyclesWithoutRisk``, no en este booleano.
        "riskReadSaturated": bool(risk_read_saturated),
        "riskBasis": MATERIAL_RISK_BASIS,
        "fingerprint": material_fingerprint(rows),
        "fingerprintMethod": MATERIAL_FINGERPRINT_METHOD,
        "exportTimestamp": export_timestamp,
    }
