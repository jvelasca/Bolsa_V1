"""Propuestas de adaptación ``AdaptationProposalV1`` — la IA propone, nadie obedece (ADR-049).

Flujo (siempre determinista y sin efectos de lado):

    AdaptationEvidenceV1 → proxy IA (prompt_adaptation_proposal_v1) → validación estricta
    → AdaptationProposalV1[] → StrategyCandidate (vía discovery, inyectable)

Invariantes:

* **Sin evidencia medida no hay propuestas**: si ``measured=False`` el lote sale vacío y
  declara el motivo; no se adivina.
* **Enum cerrado**: cualquier mutación fuera de :data:`ADAPTATION_MUTATIONS` invalida el
  payload entero del proxy.
* **Fallback honesto**: sin proxy, con error del proxy o con schema inválido se usan reglas
  heurísticas deterministas y se declara ``heuristic_fallback`` con su motivo.
* **Ids estables**: el id de propuesta deriva del hash de la evidencia + mutación + razón, de
  modo que dos ejecuciones idénticas producen el mismo lote y el mismo hash.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bolsa_application.baseline_arms import BASELINE_THRESHOLDS

__all__ = [
    "ADAPTATION_MUTATIONS",
    "ADAPTATION_PROMPT_ID",
    "CandidateRequestV1",
    "AdaptationProposalBatchV1",
    "AdaptationProposalV1",
    "MaterializedCandidateV1",
    "build_candidate_request",
    "materialize_candidates",
    "preregistration_hash",
    "propose_adaptations",
]

ADAPTATION_PROMPT_ID = "prompt_adaptation_proposal_v1"

#: ADR-049 §2.3 — enum **cerrado** de mutaciones. Debe coincidir con
#: ``bolsa_ai.schemas.ADAPTATION_MUTATIONS`` (hay un test de paridad en la API).
ADAPTATION_MUTATIONS: tuple[str, ...] = (
    "tighten_stop_atr",
    "loosen_stop_atr",
    "raise_payoff_target",
    "lower_payoff_target",
    "add_regime_filter",
    "remove_regime_filter",
    "disable_family",
    "enable_family",
    "adjust_entry_confirmation",
    "adjust_position_sizing_cap",
)

ADAPTATION_PROPOSAL_KEYS = frozenset(
    {
        "mutation",
        "rationale",
        "expectedEffect",
        "evidenceRefs",
        "boundsRespected",
        "riskNote",
    }
)

#: Tope de propuestas por lote: el presupuesto de validación es finito y explícito.
DEFAULT_MAX_PROPOSALS = 5

SOURCE_LLM = "llm"
SOURCE_HEURISTIC = "heuristic_fallback"
SOURCE_NO_EVIDENCE = "no_evidence"

Validator = Callable[[Any], list[str]]
ProposalProxy = Callable[[Mapping[str, Any], Mapping[str, float], Mapping[str, Any]], Any]
DiscoverFn = Callable[..., Sequence[Any]]


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _short_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def preregistration_hash(thresholds: Mapping[str, Any] | None = None) -> str:
    """Huella de los umbrales **fijados antes de medir** (ADR-049 §2.4).

    Los umbrales parciales se completan con ``BASELINE_THRESHOLDS``: omitir una clave no
    puede relajar el gate ni cambiar el significado de la huella según quién la calcule.
    """
    limits = {**BASELINE_THRESHOLDS, **dict(thresholds or {})}
    return _short_hash(limits)


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None


def _payload_errors(payload: Any) -> list[str]:
    """Espejo estricto de ``bolsa_ai.schemas.validate_adaptation_proposal_payload``.

    Se duplica a propósito: ``bolsa-application`` no depende de ``bolsa-ai`` y la validación
    no puede quedarse sin puerta. La paridad del enum la cubre un test de la API.
    """
    if not isinstance(payload, Mapping):
        return ["payload debe ser objeto JSON"]
    errors: list[str] = []
    extra = sorted(set(payload) - {"proposals"})
    if extra:
        errors.append(f"claves no permitidas en la raíz: {', '.join(extra)}")
    proposals = payload.get("proposals")
    if not isinstance(proposals, list):
        return [*errors, "proposals debe ser lista"]
    if not proposals:
        return [*errors, "proposals no puede estar vacío"]
    for index, proposal in enumerate(proposals):
        prefix = f"proposals[{index}]"
        if not isinstance(proposal, Mapping):
            errors.append(f"{prefix} debe ser objeto")
            continue
        extra = sorted(set(proposal) - ADAPTATION_PROPOSAL_KEYS)
        if extra:
            errors.append(f"{prefix}: claves no permitidas: {', '.join(extra)}")
        if proposal.get("mutation") not in ADAPTATION_MUTATIONS:
            errors.append(f"{prefix}.mutation inválida: {proposal.get('mutation')!r}")
        for key in ("rationale", "expectedEffect", "riskNote"):
            value = proposal.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{key} debe ser texto no vacío")
        refs = proposal.get("evidenceRefs")
        if not isinstance(refs, list) or not refs or not all(
            isinstance(ref, str) and ref.strip() for ref in refs
        ):
            errors.append(f"{prefix}.evidenceRefs debe ser lista de referencias no vacía")
        if proposal.get("boundsRespected") is not True:
            errors.append(f"{prefix}.boundsRespected debe ser true")
    return errors


@dataclass(frozen=True, slots=True)
class AdaptationProposalV1:
    """Una mutación propuesta, tipada y trazable a la evidencia que la sostiene."""

    id: str
    mutation: str
    rationale: str
    expected_effect: str
    evidence_refs: tuple[str, ...]
    bounds_respected: bool
    risk_note: str
    provider: str | None = None
    model: str | None = None
    prompt_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mutation": self.mutation,
            "rationale": self.rationale,
            "expectedEffect": self.expected_effect,
            "evidenceRefs": list(self.evidence_refs),
            "boundsRespected": self.bounds_respected,
            "riskNote": self.risk_note,
            "provider": self.provider,
            "model": self.model,
            "promptId": self.prompt_id,
        }


@dataclass(frozen=True, slots=True)
class AdaptationProposalBatchV1:
    evidence_version: str
    evidence_hash: str | None
    preregistration_hash: str
    source: str
    reason_codes: tuple[str, ...]
    proposals: tuple[AdaptationProposalV1, ...]
    provider: str | None = None
    model: str | None = None
    prompt_id: str | None = None
    gaps: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "version": "AdaptationProposalBatchV1",
            "evidenceVersion": self.evidence_version,
            "evidenceHash": self.evidence_hash,
            "preregistrationHash": self.preregistration_hash,
            "source": self.source,
            "reasonCodes": list(self.reason_codes),
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "provider": self.provider,
            "model": self.model,
            "promptId": self.prompt_id,
            "gaps": list(self.gaps),
        }
        payload["hash"] = _short_hash(payload)
        return payload


@dataclass(frozen=True, slots=True)
class CandidateRequestV1:
    """Petición de materialización: qué familia se re-descubre con la mutación propuesta."""

    proposal_id: str
    instrument_id: str
    mutation: str
    families: tuple[str, ...] = ()
    parent: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposalId": self.proposal_id,
            "instrumentId": self.instrument_id,
            "mutation": self.mutation,
            "families": list(self.families),
            "parent": self.parent,
            "params": dict(self.params),
        }


@dataclass(frozen=True, slots=True)
class MaterializedCandidateV1:
    proposal_id: str
    instrument_id: str
    candidate_ids: tuple[str, ...]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposalId": self.proposal_id,
            "instrumentId": self.instrument_id,
            "candidateIds": list(self.candidate_ids),
            "error": self.error,
        }


def _refs_for(evidence: Mapping[str, Any], *fields: str) -> tuple[str, ...]:
    base = str(evidence.get("hash") or "unhashed")
    refs = [f"evidence:{base}:{field}" for field in fields]
    for ref in evidence.get("artifactRefs") or ():
        text = str(ref).strip()
        if text:
            refs.append(text)
    return tuple(refs)


def _heuristic_proposals(
    evidence: Mapping[str, Any], thresholds: Mapping[str, float]
) -> list[Mapping[str, Any]]:
    """Reglas deterministas: la misma evidencia produce siempre las mismas propuestas."""
    if evidence.get("measured") is not True:
        return []

    expectancy = _finite(evidence.get("expectancyR"))
    hit_rate = _finite(evidence.get("hitRate"))
    capture = _finite(evidence.get("capture"))
    mae = _finite(evidence.get("avgMaeR"))
    mfe = _finite(evidence.get("avgMfeR"))
    failed = {str(gate) for gate in evidence.get("failedGates") or ()}
    drivers = [d for d in evidence.get("lossDrivers") or () if isinstance(d, Mapping)]

    proposals: list[Mapping[str, Any]] = []

    if expectancy is not None and expectancy < 0:
        proposals.append(
            {
                "mutation": "tighten_stop_atr",
                "rationale": (
                    f"Expectativa medida negativa ({expectancy:.4f} R/ciclo); recortar el "
                    "stop ATR reduce la pérdida media por ciclo fallido."
                ),
                "expectedEffect": "Menor R perdido por ciclo; se medirá expectancyR y avgMaeR.",
                "evidenceRefs": _refs_for(evidence, "expectancyR", "avgMaeR"),
                "boundsRespected": True,
                "riskNote": "Más stops prematuros: puede bajar el hit rate y la captura.",
            }
        )

    if mae is not None and mae <= -0.8:
        proposals.append(
            {
                "mutation": "adjust_position_sizing_cap",
                "rationale": (
                    f"MAE medio profundo ({mae:.4f} R) con expectativa {expectancy!r}: el "
                    "tamaño amplifica pérdidas antes de que el stop actúe."
                ),
                "expectedEffect": "Menor DD aportado por ciclo; se medirá maxDrawdownPct.",
                "evidenceRefs": _refs_for(evidence, "avgMaeR", "expectancyR"),
                "boundsRespected": True,
                "riskNote": "Menos tamaño también reduce el beneficio de los ciclos ganadores.",
            }
        )

    if "maxDrawdownPct" in failed:
        proposals.append(
            {
                "mutation": "adjust_position_sizing_cap",
                "rationale": (
                    "El gate maxDrawdownPct quedó fallido; el tamaño de posición es la "
                    "palanca directa sobre el drawdown sin tocar la señal."
                ),
                "expectedEffect": "DD dentro del umbral pre-registrado; se medirá la curva.",
                "evidenceRefs": _refs_for(evidence, "failedGates"),
                "boundsRespected": True,
                "riskNote": "Puede reducir el exceso vs compra y mantener si el DD baja por tamaño.",
            }
        )

    top_driver = None
    for driver in drivers:
        if int(driver.get("cycles") or 0) >= 2:
            top_driver = str(driver.get("driver") or "").strip() or None
            break
    if top_driver:
        name = top_driver.lower()
        mutation = (
            "disable_family"
            if any(token in name for token in ("family", "familia", "signal", "señal", "entry"))
            else "add_regime_filter"
        )
        proposals.append(
            {
                "mutation": mutation,
                "rationale": (
                    f"Driver de pérdida dominante declarado: '{top_driver}', presente en varios "
                    "ciclos cerrados. Aislar ese origen es la corrección con evidencia directa."
                ),
                "expectedEffect": "Se elimina la pérdida atribuida al driver; se mide por cohorte.",
                "evidenceRefs": _refs_for(evidence, "lossDrivers"),
                "boundsRespected": True,
                "riskNote": "Un filtro de más puede dejar la muestra por debajo del mínimo.",
            }
        )

    if capture is not None and capture < 0.5:
        proposals.append(
            {
                "mutation": "raise_payoff_target",
                "rationale": (
                    f"Captura medida baja ({capture:.4f}): se recorta el recorrido favorable "
                    f"(MFE medio {mfe!r} R). Elevar el objetivo de payoff apunta a capturar más."
                ),
                "expectedEffect": "Mayor captura y expectancyR por ciclo; se medirá capture y MFE.",
                "evidenceRefs": _refs_for(evidence, "capture", "avgMfeR"),
                "boundsRespected": True,
                "riskNote": "Objetivos más altos reducen el hit rate si el MFE no se sostiene.",
            }
        )

    if hit_rate is not None and hit_rate < thresholds.get("minPositiveWindowPct", 60.0) / 100.0:
        proposals.append(
            {
                "mutation": "adjust_entry_confirmation",
                "rationale": (
                    f"Hit rate medido {hit_rate:.4f} por debajo de la línea base; exigir más "
                    "confirmación en la entrada filtra señales débiles."
                ),
                "expectedEffect": "Mejor hit rate; se medirá con la misma muestra mínima.",
                "evidenceRefs": _refs_for(evidence, "hitRate"),
                "boundsRespected": True,
                "riskNote": "Más confirmación llega tarde y puede recortar el MFE disponible.",
            }
        )

    return proposals


def _coerce_proposal(
    raw: Mapping[str, Any],
    *,
    evidence_hash: str | None,
    provider: str | None,
    model: str | None,
    prompt_id: str | None,
) -> AdaptationProposalV1:
    mutation = str(raw["mutation"])
    rationale = str(raw["rationale"]).strip()
    refs = tuple(str(ref).strip() for ref in raw["evidenceRefs"] if str(ref).strip())
    identity = {
        "evidenceHash": evidence_hash,
        "mutation": mutation,
        "rationale": rationale,
        "evidenceRefs": list(refs),
    }
    return AdaptationProposalV1(
        id=f"adp_{_short_hash(identity)[:16]}",
        mutation=mutation,
        rationale=rationale,
        expected_effect=str(raw["expectedEffect"]).strip(),
        evidence_refs=refs,
        bounds_respected=raw.get("boundsRespected") is True,
        risk_note=str(raw["riskNote"]).strip(),
        provider=provider,
        model=model,
        prompt_id=prompt_id,
    )


def _dedupe_cap(
    raws: Sequence[Mapping[str, Any]], max_proposals: int
) -> list[Mapping[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    out: list[Mapping[str, Any]] = []
    for raw in raws:
        key = (str(raw.get("mutation")), " ".join(raw.get("evidenceRefs") or ()))
        if key in seen:
            continue
        seen.add(key)
        out.append(raw)
        if len(out) >= max(1, int(max_proposals)):
            break
    return out


def propose_adaptations(
    evidence: Any,
    *,
    proxy: ProposalProxy | None = None,
    thresholds: Mapping[str, float] | None = None,
    constraints: Mapping[str, Any] | None = None,
    validator: Validator | None = None,
    provider: str | None = None,
    model: str | None = None,
    prompt_id: str | None = ADAPTATION_PROMPT_ID,
    max_proposals: int = DEFAULT_MAX_PROPOSALS,
) -> AdaptationProposalBatchV1:
    """Evidencia → (proxy | heurística) → propuestas validadas y deterministas."""
    evidence_map = (
        dict(evidence.to_dict()) if hasattr(evidence, "to_dict") else dict(evidence or {})
    )
    limits = {**BASELINE_THRESHOLDS, **dict(thresholds or {})}
    prereg = preregistration_hash(limits)
    evidence_version = str(evidence_map.get("version") or "AdaptationEvidenceV1")
    evidence_hash = evidence_map.get("hash")
    evidence_hash = str(evidence_hash) if evidence_hash else None
    gaps = tuple(str(gap) for gap in evidence_map.get("gaps") or ())

    if evidence_map.get("measured") is not True:
        return AdaptationProposalBatchV1(
            evidence_version=evidence_version,
            evidence_hash=evidence_hash,
            preregistration_hash=prereg,
            source=SOURCE_NO_EVIDENCE,
            reason_codes=("evidence_not_measured",),
            proposals=(),
            provider=provider,
            model=model,
            prompt_id=prompt_id,
            gaps=gaps,
        )

    reasons: list[str] = []
    raws: list[Mapping[str, Any]] = []
    source = SOURCE_HEURISTIC

    if proxy is None:
        reasons.append("proxy_not_configured")
    else:
        try:
            payload = proxy(evidence_map, limits, dict(constraints or {}))
        except Exception as exc:  # noqa: BLE001 - fail-closed: cualquier fallo cae a heurística
            reasons.append(f"proxy_error:{type(exc).__name__}")
            payload = None
        if payload is not None:
            errors = (validator or _payload_errors)(payload)
            if errors:
                reasons.append(f"schema_invalid:{len(errors)}")
                reasons.extend(f"schema:{error}" for error in errors[:5])
            else:
                source = SOURCE_LLM
                raws = [item for item in payload["proposals"] if isinstance(item, Mapping)]

    if source != SOURCE_LLM:
        raws = _heuristic_proposals(evidence_map, limits)
        if not raws:
            reasons.append("no_actionable_evidence")
        reasons.append("heuristic_fallback")

    proposals = tuple(
        _coerce_proposal(
            raw,
            evidence_hash=evidence_hash,
            provider=provider,
            model=model,
            prompt_id=prompt_id,
        )
        for raw in _dedupe_cap(raws, max_proposals)
    )

    return AdaptationProposalBatchV1(
        evidence_version=evidence_version,
        evidence_hash=evidence_hash,
        preregistration_hash=prereg,
        source=source,
        reason_codes=tuple(reasons),
        proposals=proposals,
        provider=provider,
        model=model,
        prompt_id=prompt_id,
        gaps=gaps,
    )


def build_candidate_request(
    proposal: AdaptationProposalV1 | Mapping[str, Any],
    *,
    instrument_id: str,
    families: Sequence[str] = (),
    parent: str | None = None,
) -> CandidateRequestV1:
    """Traduce la mutación propuesta a una petición de discovery **explícita**."""
    proposal_id = (
        proposal.id if isinstance(proposal, AdaptationProposalV1) else str(proposal.get("id"))
    )
    mutation = (
        proposal.mutation
        if isinstance(proposal, AdaptationProposalV1)
        else str(proposal.get("mutation") or "")
    )
    if mutation not in ADAPTATION_MUTATIONS:
        raise ValueError(f"mutación fuera del enum cerrado: {mutation!r}")
    return CandidateRequestV1(
        proposal_id=proposal_id,
        instrument_id=instrument_id,
        mutation=mutation,
        families=tuple(str(family) for family in families),
        parent=parent,
        params={"mutation": mutation},
    )


def _default_discover(**kwargs: Any) -> Sequence[Any]:
    from bolsa_application.strategy_discovery_engine import discover_candidates

    return discover_candidates(**kwargs)


def _candidate_id(candidate: Any) -> str | None:
    if isinstance(candidate, Mapping):
        value = candidate.get("id") or candidate.get("candidateId")
    else:
        value = getattr(candidate, "id", None) or getattr(candidate, "candidate_id", None)
    text = str(value).strip() if value is not None else ""
    return text or None


def materialize_candidates(
    requests: Sequence[CandidateRequestV1],
    *,
    discover: DiscoverFn | None = None,
    budget: Any = None,
) -> tuple[MaterializedCandidateV1, ...]:
    """Materializa candidatas versionadas; un fallo de discovery se declara, no se silencia."""
    engine = discover or _default_discover
    results: list[MaterializedCandidateV1] = []
    for request in requests:
        kwargs: dict[str, Any] = {
            "instrument_id": request.instrument_id,
            "parent": request.parent,
        }
        if request.families:
            kwargs["families"] = list(request.families)
        if budget is not None:
            kwargs["budget"] = budget
        try:
            found = engine(**kwargs)
        except Exception as exc:  # noqa: BLE001 - se propaga como error declarado
            results.append(
                MaterializedCandidateV1(
                    proposal_id=request.proposal_id,
                    instrument_id=request.instrument_id,
                    candidate_ids=(),
                    error=f"discovery_error:{type(exc).__name__}",
                )
            )
            continue
        ids = tuple(
            candidate_id for candidate_id in (_candidate_id(c) for c in found or ()) if candidate_id
        )
        results.append(
            MaterializedCandidateV1(
                proposal_id=request.proposal_id,
                instrument_id=request.instrument_id,
                candidate_ids=ids,
                error=None if ids else "no_candidates",
            )
        )
    return tuple(results)
