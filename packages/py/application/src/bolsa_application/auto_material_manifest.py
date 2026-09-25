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


def build_material_manifest(
    *,
    account_id: str | None,
    requested_versions: Sequence[str],
    fills: Iterable[Any],
    cycles: Sequence[Any],
    reservations_read: int,
    risk_read_saturated: bool,
    export_timestamp: str,
    regime_confirmed: int = 0,
    regime_absent: int = 0,
    regime_unconfirmed: int = 0,
    regime_not_derivable: int = 0,
) -> dict[str, Any]:
    """(PURA) declaración auditable del material exportado + su huella.

    ``cycles`` son las filas de ``adaptive_instrument_cycles`` (el MISMO material que mide el
    instrumento): de ahí salen ``closedCycles`` y las cuentas de riesgo, versión y régimen. La
    huella se calcula sobre esas filas con ``material_fingerprint`` (analytics).
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
    for row in rows:
        version = _version_of(row)
        if not version:
            continue
        cell = per_version.setdefault(version, {"cycles": 0, "withRisk": 0, "withoutRisk": 0})
        cell["cycles"] += 1
        if _has_risk(row):
            cell["withRisk"] += 1
        else:
            cell["withoutRisk"] += 1
    per_version = {version: per_version[version] for version in sorted(per_version)}

    return {
        "account": _clean(account_id) or None,
        "requestedStrategyVersions": [str(v) for v in requested_versions],
        "fillsRead": len(list(fills)),
        "closedCycles": total,
        "cyclesWithRisk": with_risk,
        "cyclesWithoutRisk": total - with_risk,
        "cyclesWithVersion": with_version,
        "cyclesWithoutVersion": total - with_version,
        "cyclesWithoutIdentity": without_identity,
        "costAppliedCycles": applied,
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
        "riskReadSaturated": bool(risk_read_saturated),
        "riskBasis": MATERIAL_RISK_BASIS,
        "fingerprint": material_fingerprint(rows),
        "fingerprintMethod": MATERIAL_FINGERPRINT_METHOD,
        "exportTimestamp": export_timestamp,
    }
