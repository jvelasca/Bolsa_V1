"""Certificación del **método** DÍA-D as-run — independiente del resultado (ADR-049).

Qué certifica
-------------
No certifica que la operativa gane dinero: certifica que el replay es **válido** como
reconstrucción histórica. Un DÍA-D certificado con resultado negativo es un resultado útil;
un DÍA-D sin certificar no puede sostener ninguna decisión aunque su número sea bonito.

Las ocho condiciones (ADR-049 §3 y dictamen de producto):

0. ``artifact_integrity`` — el ``hash`` declarado se recalcula del artefacto completo: cualquier
   edición de brazos, decisiones, versiones o certificación lo invalida.
1. ``temporal_freeze`` — el día D, la fuente del estado y la huella de barras están declarados.
2. ``initial_state`` — las patas reales de D están en el sobre de auditoría, no reconstruidas,
   y el universo de D está **declarado** (no derivado de lo que se cargó después).
3. ``sequential_replay`` — cada brazo medido conserva sus decisiones, ordenadas y posteriores a D.
4. ``real_market_data`` — las barras posteriores son de mercado real y su manifest por vela es
   recomputable: cambiar una vela rompe el ``barsHash``.
5. ``realistic_execution`` — coste > 0, deslizamiento declarado, cota de liquidez, política de
   gaps y base de coste de los fills reales (``quoted``/``effective``).
6. ``benchmarks`` — ``as_run``, ``cash`` y ``market_bh`` medidos, con universo, capital,
   periodo y coste del benchmark declarados.
7. ``audit`` — motor, esquema, bump, parámetros (recomputables) y límites declarados.

Invariantes:

* ``NOT_EVALUATED`` **nunca** cuenta como ``PASS``: fail-closed.
* Un dato ausente es ``NOT_EVALUATED``; un dato presente e incoherente es ``FAIL``.
* La certificación es pura y determinista (mismo artefacto ⇒ mismo hash).
* No lee configuración, no escribe nada, no autoriza operaciones.
* Lo que no puede detectar, lo declara: un productor que reescriba artefacto y hashes de forma
  coherente no es distinguible sin una firma o un sello externo al propio artefacto.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bolsa_application.dia_d_as_run import (
    ARM_AS_RUN,
    ARM_CASH,
    ARM_MARKET_BH,
    BENCHMARK_CAPITAL_INITIAL,
    BENCHMARK_CAPITAL_UNIT,
    DEFAULT_MIN_COHORT_SAMPLES,
    GAP_POLICY_OPEN,
    GAP_POLICY_THEORETICAL,
    REAL_FILLS_COST_EFFECTIVE,
    REAL_FILLS_COST_QUOTED,
    UNIVERSE_SOURCE_DECLARED,
    artifact_hash,
)

__all__ = [
    "CHECK_FAIL",
    "CHECK_NOT_EVALUATED",
    "CHECK_PASS",
    "CERTIFICATION_CHECKS",
    "CERTIFICATION_VERSION",
    "CertificationCheck",
    "DiaDCertificationV1",
    "DiaDCohortCertificationV1",
    "certify_artifact",
    "certify_cohort",
]

CERTIFICATION_VERSION = "DiaDCertificationV1"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_NOT_EVALUATED = "NOT_EVALUATED"

VERDICT_CERTIFIED = "certified"
VERDICT_NOT_CERTIFIED = "not_certified"
VERDICT_INSUFFICIENT = "insufficient_sample"

#: Las ocho condiciones, en orden canónico.
CERTIFICATION_CHECKS: tuple[str, ...] = (
    "artifact_integrity",
    "temporal_freeze",
    "initial_state",
    "sequential_replay",
    "real_market_data",
    "realistic_execution",
    "benchmarks",
    "audit",
)

_GAP_POLICIES = (GAP_POLICY_OPEN, GAP_POLICY_THEORETICAL)
_REAL_FILLS_COST_BASES = (REAL_FILLS_COST_QUOTED, REAL_FILLS_COST_EFFECTIVE)
_BENCHMARK_CAPITAL_BASES = (BENCHMARK_CAPITAL_INITIAL, BENCHMARK_CAPITAL_UNIT)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _non_empty_str(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


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


@dataclass(frozen=True, slots=True)
class CertificationCheck:
    name: str
    status: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class DiaDCertificationV1:
    day: str | None
    verdict: str
    checks: tuple[CertificationCheck, ...]
    failures: tuple[str, ...]
    not_evaluated: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def certified(self) -> bool:
        return self.verdict == VERDICT_CERTIFIED

    @property
    def status(self) -> str:
        return self.verdict

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": CERTIFICATION_VERSION,
            "day": self.day,
            "verdict": self.verdict,
            "certified": self.certified,
            "checks": [check.to_dict() for check in self.checks],
            "failures": list(self.failures),
            "notEvaluated": list(self.not_evaluated),
            "reasons": list(self.reasons),
        }
        payload["hash"] = _payload_hash(payload)
        return payload


@dataclass(frozen=True, slots=True)
class DiaDCohortCertificationV1:
    """Certificación de una cohorte: sin muestra suficiente no hay certificado."""

    verdict: str
    samples: int
    required: int
    certified_days: tuple[str, ...]
    failed: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]

    @property
    def certified(self) -> bool:
        return self.verdict == VERDICT_CERTIFIED

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": CERTIFICATION_VERSION,
            "verdict": self.verdict,
            "certified": self.certified,
            "samples": self.samples,
            "required": self.required,
            "certifiedDays": list(self.certified_days),
            "failed": [dict(item) for item in self.failed],
            "reasons": list(self.reasons),
        }
        payload["hash"] = _payload_hash(payload)
        return payload


def _payload_hash(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "hash"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _passes(name: str) -> CertificationCheck:
    return CertificationCheck(name=name, status=CHECK_PASS)


def _missing(name: str, reason: str) -> CertificationCheck:
    return CertificationCheck(name=name, status=CHECK_NOT_EVALUATED, reason=reason)


def _failed(name: str, reason: str) -> CertificationCheck:
    return CertificationCheck(name=name, status=CHECK_FAIL, reason=reason)


def _arms_by_name(artifact: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = artifact.get("arms")
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("arm")): row
        for row in rows
        if isinstance(row, Mapping) and row.get("arm")
    }


def _dates_ordered(decisions: Any, *, day: str) -> bool:
    """Decisiones presentes, con fechas no decrecientes y nunca anteriores a D."""
    if not isinstance(decisions, list) or not decisions:
        return False
    previous: str | None = None
    for decision in decisions:
        if not isinstance(decision, Mapping):
            return False
        date = _non_empty_str(decision.get("date"))
        if date is None:
            continue
        key = date[:10]
        if key < day:
            return False
        if previous is not None and key < previous:
            return False
        previous = key
    return True


def _check_artifact_integrity(artifact: Mapping[str, Any]) -> CertificationCheck:
    """El hash declarado debe ser el del artefacto tal y como está ahora.

    Sin esto, cambiar un ``realizedR``, un ``bump`` o una decisión dejaba la certificación
    intacta: el certificado describía un artefacto que ya no existía.
    """
    name = "artifact_integrity"
    declared = artifact.get("hash")
    if not _is_sha256(declared):
        return _missing(name, "artifact_hash_missing")
    body = {key: value for key, value in artifact.items() if key != "hash"}
    if artifact_hash(body) != str(declared):
        return _failed(name, "artifact_hash_mismatch")
    return _passes(name)


def _check_temporal_freeze(
    day: str, pit: Mapping[str, Any]
) -> CertificationCheck:
    name = "temporal_freeze"
    pit_day = _non_empty_str(pit.get("day"))
    if not day:
        return _missing(name, "day_not_declared")
    if pit_day is None:
        return _missing(name, "point_in_time_not_declared")
    if pit_day != day:
        return _failed(name, "point_in_time_day_mismatch")
    if _non_empty_str(pit.get("stateSource")) is None:
        return _missing(name, "state_source_not_declared")
    if not _is_sha256(pit.get("legsHash")):
        return _missing(name, "legs_hash_missing")
    if pit.get("sourceIsReconstructed") is not False:
        return _failed(name, "state_is_reconstructed")
    return _passes(name)


def _check_initial_state(
    pit: Mapping[str, Any], starting_state: Mapping[str, Any]
) -> CertificationCheck:
    name = "initial_state"
    legs = pit.get("legs")
    if not isinstance(legs, list):
        return _missing(name, "initial_state_not_declared")
    if not all(isinstance(row, Mapping) for row in legs):
        return _failed(name, "initial_state_malformed")
    if legs and not all(
        _non_empty_str(row.get("instrumentId")) is not None
        and _finite(row.get("entry")) is not None
        and _finite(row.get("quantity")) is not None
        for row in legs
    ):
        return _failed(name, "initial_state_incomplete")
    if pit.get("sourceIsReconstructed") is not False:
        return _failed(name, "state_is_reconstructed")
    declared_legs = _finite(starting_state.get("legs"))
    if declared_legs is not None and int(declared_legs) != len(legs):
        return _failed(name, "starting_state_legs_mismatch")
    if bool(starting_state.get("cashOnly")) and legs:
        return _failed(name, "cash_only_with_legs")
    legs_hash = pit.get("legsHash")
    if not _is_sha256(legs_hash):
        return _missing(name, "legs_hash_missing")
    recomputed = artifact_hash({"legs": sorted(legs, key=lambda r: str(r.get("instrumentId")))})
    if recomputed != str(legs_hash):
        return _failed(name, "legs_hash_mismatch")
    universe = pit.get("universe")
    if not isinstance(universe, list) or not universe:
        return _missing(name, "universe_not_declared")
    if not all(_non_empty_str(item) is not None for item in universe):
        return _failed(name, "universe_malformed")
    if str(pit.get("universeSource") or "") != UNIVERSE_SOURCE_DECLARED:
        # Derivar el universo de las patas y las barras cargadas no prueba qué se sabía en D.
        return _missing(name, "universe_not_declared")
    return _passes(name)


def _check_sequential_replay(
    audit: Mapping[str, Any],
    arms: Mapping[str, Mapping[str, Any]],
    *,
    day: str,
) -> CertificationCheck:
    name = "sequential_replay"
    decisions = audit.get("decisions")
    if not isinstance(decisions, Mapping):
        return _missing(name, "decisions_not_declared")
    if not day:
        return _missing(name, "day_not_declared")
    measured = [arm for arm, row in arms.items() if row.get("measured") is True]
    if not measured:
        return _missing(name, "no_measured_arm")
    for arm in measured:
        if not _dates_ordered(decisions.get(arm), day=day):
            return _failed(name, f"decisions_missing_or_unordered:{arm}")
    return _passes(name)


def _check_real_market_data(data: Mapping[str, Any]) -> CertificationCheck:
    name = "real_market_data"
    if _non_empty_str(data.get("barsSource")) is None:
        return _missing(name, "bars_source_not_declared")
    if _non_empty_str(data.get("timeframe")) is None:
        return _missing(name, "bars_timeframe_not_declared")
    bars_hash = data.get("barsHash")
    if not _is_sha256(bars_hash):
        return _missing(name, "bars_hash_missing")
    instruments = data.get("instruments")
    if not isinstance(instruments, list) or not instruments:
        return _missing(name, "bars_not_declared")
    for row in instruments:
        if not isinstance(row, Mapping):
            return _failed(name, "bars_summary_malformed")
        if _non_empty_str(row.get("instrument")) is None:
            return _failed(name, "bars_summary_malformed")
        bars = _finite(row.get("bars"))
        if bars is None or bars < 1:
            return _failed(name, "bars_summary_malformed")
    manifest = data.get("barsManifest")
    if not isinstance(manifest, Mapping) or not manifest:
        return _missing(name, "bars_manifest_missing")
    # El manifest es la huella real: si el resumen de barras no cuadra con él, miente.
    for row in instruments:
        instrument = str(row.get("instrument"))
        rows = manifest.get(instrument) if isinstance(row, Mapping) else None
        if not isinstance(rows, list) or not rows:
            return _failed(name, f"bars_manifest_missing:{instrument}")
        declared = _finite(row.get("bars"))
        if declared is not None and int(declared) != len(rows):
            return _failed(name, f"bars_manifest_count_mismatch:{instrument}")
        days: list[str] = []
        for entry in rows:
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                return _failed(name, f"bars_manifest_malformed:{instrument}")
            day_key, digest = entry
            day_text = _non_empty_str(day_key)
            if day_text is None or not _is_sha256(digest):
                return _failed(name, f"bars_manifest_malformed:{instrument}")
            days.append(day_text[:10])
        if days != sorted(days) or len(set(days)) != len(days):
            return _failed(name, f"bars_manifest_unordered:{instrument}")
    if artifact_hash(manifest) != str(bars_hash):
        return _failed(name, "bars_hash_mismatch")
    return _passes(name)


def _check_realistic_execution(
    audit: Mapping[str, Any], artifact: Mapping[str, Any]
) -> CertificationCheck:
    name = "realistic_execution"
    execution = audit.get("execution")
    if not isinstance(execution, Mapping):
        return _missing(name, "execution_model_not_declared")
    round_trip = _finite(execution.get("roundTripBps"))
    if round_trip is None:
        return _missing(name, "round_trip_cost_not_declared")
    if round_trip <= 0:
        return _failed(name, "round_trip_cost_not_positive")
    cost_bps = _finite(artifact.get("costBps"))
    if cost_bps is None:
        return _missing(name, "cost_bps_not_declared")
    if abs(round_trip - cost_bps) > 0.01:
        return _failed(name, "cost_bps_mismatch")
    slippage = _finite(execution.get("slippageBps"))
    if slippage is None:
        return _missing(name, "slippage_not_declared")
    participation = execution.get("maxParticipationPct")
    if participation is None:
        # Liquidez ilimitada declarada explícitamente es válida; la ausencia no lo es.
        return _missing(name, "liquidity_cap_not_declared")
    if isinstance(participation, bool) or not isinstance(participation, (int, float)):
        return _failed(name, "liquidity_cap_invalid")
    if not 0 < float(participation) <= 1:
        return _failed(name, "liquidity_cap_invalid")
    if str(execution.get("gapPolicy") or "") not in _GAP_POLICIES:
        return _missing(name, "gap_policy_not_declared")
    basis = _non_empty_str(execution.get("realFillsCostBasis"))
    if basis is None:
        return _missing(name, "real_fills_cost_basis_not_declared")
    if basis not in _REAL_FILLS_COST_BASES:
        return _failed(name, "real_fills_cost_basis_invalid")
    execution_cost = _finite(execution.get("executionCostBps"))
    if execution_cost is None:
        return _missing(name, "execution_cost_not_declared")
    if basis == REAL_FILLS_COST_EFFECTIVE and execution_cost > 1e-9:
        # Si el fill ya es neto, cobrar otra vez duplica el coste del brazo real.
        return _failed(name, "effective_fills_with_cash_cost")
    return _passes(name)


def _check_benchmarks(
    arms: Mapping[str, Mapping[str, Any]],
    audit: Mapping[str, Any],
    artifact: Mapping[str, Any],
) -> CertificationCheck:
    name = "benchmarks"
    for arm in (ARM_AS_RUN, ARM_CASH, ARM_MARKET_BH):
        row = arms.get(arm)
        if row is None:
            return _missing(name, f"benchmark_not_declared:{arm}")
        if row.get("measured") is not True:
            return _failed(name, f"benchmark_not_measured:{arm}")
    market = arms.get(ARM_MARKET_BH, {})
    if _finite(market.get("pnlCurrency")) is None:
        return _failed(name, "benchmark_pnl_not_declared")
    benchmark = _mapping(audit.get("benchmark"))
    universe = benchmark.get("universe")
    if not isinstance(universe, list) or not universe:
        return _missing(name, "benchmark_universe_not_declared")
    if str(benchmark.get("capitalBasis") or "") not in _BENCHMARK_CAPITAL_BASES:
        return _missing(name, "benchmark_capital_basis_not_declared")
    benchmark_cost = _finite(benchmark.get("costBps"))
    if benchmark_cost is None:
        return _missing(name, "benchmark_cost_not_declared")
    cost_bps = _finite(artifact.get("costBps"))
    if cost_bps is None:
        return _missing(name, "cost_bps_not_declared")
    if abs(benchmark_cost - cost_bps) > 0.01:
        return _failed(name, "benchmark_cost_mismatch")
    declared_universe = _mapping(audit.get("pointInTime")).get("universe", [])
    if sorted(str(item) for item in universe) != sorted(
        str(item) for item in (declared_universe if isinstance(declared_universe, list) else [])
    ):
        return _failed(name, "benchmark_universe_mismatch")
    return _passes(name)


def _check_audit(
    audit: Mapping[str, Any], artifact: Mapping[str, Any]
) -> CertificationCheck:
    name = "audit"
    versions = audit.get("versions")
    if not isinstance(versions, Mapping):
        return _missing(name, "versions_not_declared")
    for key in ("engine", "schema", "bump", "paramsHash"):
        if _non_empty_str(versions.get(key)) is None:
            return _missing(name, f"versions_missing:{key}")
    if _non_empty_str(artifact.get("engine")) is None:
        return _missing(name, "engine_not_declared")
    if str(versions.get("engine")) != str(artifact.get("engine")):
        return _failed(name, "engine_mismatch")
    if str(versions.get("schema")) != str(artifact.get("schemaVersion")):
        return _failed(name, "schema_mismatch")
    params = audit.get("params")
    if params is None:
        # Sin los parámetros no se puede recomputar su hash: presencia no es verificación.
        return _missing(name, "params_not_declared")
    if not isinstance(params, Mapping):
        return _failed(name, "params_malformed")
    if artifact_hash(params) != str(versions.get("paramsHash")):
        return _failed(name, "params_hash_mismatch")
    if not isinstance(audit.get("limits"), list):
        return _missing(name, "limits_not_declared")
    return _passes(name)


def certify_artifact(artifact: Mapping[str, Any]) -> DiaDCertificationV1:
    """Aplica las ocho condiciones a un artefacto as-run. Fail-closed por diseño."""
    if not isinstance(artifact, Mapping):
        check = _failed("audit", "artifact_not_mapping")
        return DiaDCertificationV1(
            day=None,
            verdict=VERDICT_NOT_CERTIFIED,
            checks=(check,),
            failures=("audit",),
            not_evaluated=(),
            reasons=("audit:artifact_not_mapping",),
        )

    day = _non_empty_str(artifact.get("day")) or ""
    audit = _mapping(artifact.get("audit"))
    pit = _mapping(audit.get("pointInTime"))
    data = _mapping(audit.get("data"))
    starting_state = _mapping(artifact.get("startingState"))
    arms = _arms_by_name(artifact)

    checks = (
        _check_artifact_integrity(artifact),
        _check_temporal_freeze(day, pit),
        _check_initial_state(pit, starting_state),
        _check_sequential_replay(audit, arms, day=day),
        _check_real_market_data(data),
        _check_realistic_execution(audit, artifact),
        _check_benchmarks(arms, audit, artifact),
        _check_audit(audit, artifact),
    )

    failures = tuple(check.name for check in checks if check.status == CHECK_FAIL)
    not_evaluated = tuple(check.name for check in checks if check.status == CHECK_NOT_EVALUATED)
    reasons = tuple(
        f"{check.name}:{check.reason}"
        for check in checks
        if check.status != CHECK_PASS and check.reason
    )
    verdict = VERDICT_NOT_CERTIFIED if (failures or not_evaluated) else VERDICT_CERTIFIED
    return DiaDCertificationV1(
        day=day or None,
        verdict=verdict,
        checks=checks,
        failures=failures,
        not_evaluated=not_evaluated,
        reasons=reasons,
    )


def certify_cohort(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    min_samples: int = DEFAULT_MIN_COHORT_SAMPLES,
) -> DiaDCohortCertificationV1:
    """Certifica la cohorte completa: sin muestra mínima no hay certificado de conjunto."""
    required = max(1, int(min_samples))
    rows = [artifact for artifact in artifacts or () if isinstance(artifact, Mapping)]
    certifications = [certify_artifact(artifact) for artifact in rows]
    certified_days = tuple(
        sorted(
            str(certification.day)
            for certification in certifications
            if certification.certified and certification.day
        )
    )
    failed = tuple(
        {
            "day": certification.day,
            "verdict": certification.verdict,
            "reasons": list(certification.reasons),
        }
        for certification in certifications
        if not certification.certified
    )
    reasons: list[str] = []
    if len(rows) < required:
        reasons.append(f"insufficient_sample:{len(rows)}/{required}")
        verdict = VERDICT_INSUFFICIENT
    elif failed:
        reasons.append(f"days_not_certified:{len(failed)}")
        verdict = VERDICT_NOT_CERTIFIED
    else:
        verdict = VERDICT_CERTIFIED

    return DiaDCohortCertificationV1(
        verdict=verdict,
        samples=len(rows),
        required=required,
        certified_days=certified_days,
        failed=failed,
        reasons=tuple(reasons),
    )
