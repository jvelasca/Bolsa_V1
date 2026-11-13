"""Evidencia de adaptación ``AdaptationEvidenceV1`` — pura y determinista (ADR-049).

La IA **no** decide: propone. Antes de proponer necesita hechos medidos, no una corazonada.
Este módulo empaqueta la evidencia que ya existe (atribución, ciclos, gates fallidos) en un
contrato tipado y reproducible:

    AdaptationEvidenceV1: régimen, familia, instrumento, expectativa R, hit, MAE/MFE,
    captura, gates fallidos, top drivers de pérdida y refs de artefacto.

Invariantes:

* **Sin dato no hay número**: con menos de ``min_samples`` ciclos cerrados la evidencia se
  declara ``measured=False`` y sus métricas quedan ``None``. ``NOT_EVALUATED`` nunca se
  convierte en PASS ni en un ``0``.
* **Determinismo**: los drivers se ordenan por (recuento desc, nombre asc) y el hash del
  artefacto se calcula con claves ordenadas.
* **Sin look-ahead**: toda la evidencia se construye con observaciones ya cerradas.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "ADAPTATION_EVIDENCE_VERSION",
    "AdaptationEvidenceV1",
    "AdaptationObservation",
    "build_adaptation_evidence",
    "evidence_hash",
]

ADAPTATION_EVIDENCE_VERSION = "AdaptationEvidenceV1"

#: Muestra mínima por defecto para declarar la evidencia medible (ADR-049 §2.4).
DEFAULT_MIN_SAMPLES = 12


def _round(value: float | None, places: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), places)


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def evidence_hash(payload: dict[str, Any]) -> str:
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AdaptationObservation:
    """Un ciclo CERRADO observado: la única unidad de evidencia que cuenta."""

    realized_r: float | None
    mae_r: float | None = None
    mfe_r: float | None = None
    exit_kind: str | None = None
    loss_driver: str | None = None


@dataclass(frozen=True, slots=True)
class AdaptationEvidenceV1:
    version: str
    regime: str
    family: str
    instrument: str
    cycles: int
    closed_cycles: int
    expectancy_r: float | None
    hit_rate: float | None
    avg_mae_r: float | None
    avg_mfe_r: float | None
    capture: float | None
    failed_gates: tuple[str, ...]
    loss_drivers: tuple[dict[str, Any], ...]
    artifact_refs: tuple[str, ...]
    measured: bool
    gaps: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "version": self.version,
            "regime": self.regime,
            "family": self.family,
            "instrument": self.instrument,
            "cycles": self.cycles,
            "closedCycles": self.closed_cycles,
            "expectancyR": self.expectancy_r,
            "hitRate": self.hit_rate,
            "avgMaeR": self.avg_mae_r,
            "avgMfeR": self.avg_mfe_r,
            "capture": self.capture,
            "failedGates": list(self.failed_gates),
            "lossDrivers": [dict(driver) for driver in self.loss_drivers],
            "artifactRefs": list(self.artifact_refs),
            "measured": self.measured,
            "gaps": list(self.gaps),
        }
        payload["hash"] = evidence_hash(payload)
        return payload


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build_adaptation_evidence(
    observations: Sequence[AdaptationObservation],
    *,
    regime: str,
    family: str,
    instrument: str,
    failed_gates: Sequence[str] = (),
    artifact_refs: Sequence[str] = (),
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> AdaptationEvidenceV1:
    """Construye la evidencia de una (régimen, familia, instrumento) desde ciclos cerrados."""
    closed = [obs for obs in observations if _finite(obs.realized_r) is not None]
    realized: list[float] = []
    for obs in closed:
        realized_value = _finite(obs.realized_r)
        if realized_value is not None:
            realized.append(realized_value)
    gaps: list[str] = []

    required = max(1, int(min_samples))
    measured = len(closed) >= required
    if not measured:
        gaps.append(f"insufficient_sample:{len(closed)}/{required}")
    if not artifact_refs:
        gaps.append("artifacts_not_declared")
    if not failed_gates:
        gaps.append("gates_not_declared")

    if not measured:
        # Un hueco no se rellena: las métricas quedan sin valor, no en 0.
        return AdaptationEvidenceV1(
            version=ADAPTATION_EVIDENCE_VERSION,
            regime=regime,
            family=family,
            instrument=instrument,
            cycles=len(observations),
            closed_cycles=len(closed),
            expectancy_r=None,
            hit_rate=None,
            avg_mae_r=None,
            avg_mfe_r=None,
            capture=None,
            failed_gates=tuple(sorted(str(g) for g in failed_gates if str(g).strip())),
            loss_drivers=(),
            artifact_refs=tuple(str(ref) for ref in artifact_refs if str(ref).strip()),
            measured=False,
            gaps=tuple(gaps),
        )

    mae: list[float] = []
    mfe: list[float] = []
    for obs in closed:
        mae_value = _finite(obs.mae_r)
        if mae_value is not None:
            mae.append(mae_value)
        mfe_value = _finite(obs.mfe_r)
        if mfe_value is not None:
            mfe.append(mfe_value)
    wins = sum(1 for value in realized if value > 0)

    driver_counts: dict[str, int] = {}
    driver_r: dict[str, float] = {}
    for obs in closed:
        driver = str(obs.loss_driver or "").strip()
        if not driver:
            continue
        value = _finite(obs.realized_r) or 0.0
        driver_counts[driver] = driver_counts.get(driver, 0) + 1
        driver_r[driver] = driver_r.get(driver, 0.0) + value
    loss_drivers = tuple(
        {
            "driver": driver,
            "cycles": driver_counts[driver],
            "realizedR": _round(driver_r[driver]),
        }
        for driver in sorted(driver_counts, key=lambda name: (-driver_counts[name], name))
    )

    mfe_total = sum(mfe) if mfe else 0.0
    capture = _round(sum(realized) / mfe_total) if mfe_total > 0 else None

    return AdaptationEvidenceV1(
        version=ADAPTATION_EVIDENCE_VERSION,
        regime=regime,
        family=family,
        instrument=instrument,
        cycles=len(observations),
        closed_cycles=len(closed),
        expectancy_r=_round(_mean(realized)),
        hit_rate=_round(wins / len(realized)),
        avg_mae_r=_round(_mean(mae)),
        avg_mfe_r=_round(_mean(mfe)),
        capture=capture,
        failed_gates=tuple(sorted(str(g) for g in failed_gates if str(g).strip())),
        loss_drivers=loss_drivers,
        artifact_refs=tuple(str(ref) for ref in artifact_refs if str(ref).strip()),
        measured=True,
        gaps=tuple(gaps),
    )
