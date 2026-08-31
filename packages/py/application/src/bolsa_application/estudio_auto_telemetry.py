"""V1.33.2 / V1.33.3 — Telemetría A6 (Estudio AUTO funnel).

Responde A6: qué hay que ver en verde antes de ampliar fuentes (Radar/Hoy)
o thaw estricto. Measure ≠ Accept · ≠ flip ``PAPER_D_EXECUTE``.

A0 (precisión dictamen) sigue en ``daily_opinion_telemetry``. OE-1 (P1–P5)
sigue en ``ops_self_eval``. Este módulo añade el embudo A-δ y el veredicto
``expandSourcesReady``.

V1.33.3: ``lastPropose`` / ``recentProposes`` sobreviven restart vía JSONL
(``BOLSA_ESTUDIO_AUTO_PROPOSE_PATH``; default ``logs/estudio_auto_propose.jsonl``).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

from bolsa_application.estudio_auto_hits import resolve_estudio_auto_source
from bolsa_application.paper_d_propose import paper_d_execute_allowed

ESTUDIO_AUTO_TELEMETRY_SCHEMA = "estudio_auto_telemetry_v0"

ALLOWED_AUTO_SOURCES = ("estudio_alarma", "estudio_dictamen")
EXCLUDED_AUTO_SOURCES = ("paper_d", "radar", "hoy")

DEFAULT_PROPOSE_JSONL = Path("logs/estudio_auto_propose.jsonl")
RECENT_PROPOSE_LIMIT = 10

_ENV_PROPOSE_PATH = "BOLSA_ESTUDIO_AUTO_PROPOSE_PATH"

_last_propose_lock = Lock()
_last_propose: dict[str, Any] | None = None


def default_propose_path() -> Path:
    return Path(DEFAULT_PROPOSE_JSONL)


def resolve_propose_path() -> Path | None:
    """Ruta JSONL activa, o None si persistencia desactivada."""
    raw = (os.getenv(_ENV_PROPOSE_PATH) or "").strip()
    if raw.lower() in {"0", "false", "off", "none"}:
        return None
    if raw:
        return Path(raw)
    return default_propose_path()


def propose_durability() -> str:
    return "jsonl" if resolve_propose_path() is not None else "process_memory"


def reset_last_estudio_auto_propose() -> None:
    """Tests: limpia el snapshot in-process (no borra el JSONL)."""
    global _last_propose
    with _last_propose_lock:
        _last_propose = None


def summarize_estudio_auto_propose(result: dict[str, Any]) -> dict[str, Any]:
    """Compacta un POST auto-propose para el snapshot A6 (sin payloads)."""
    skipped_by_reason: dict[str, int] = {}
    for row in result.get("skipped") or []:
        if not isinstance(row, dict):
            continue
        raw = str(row.get("reason") or "unknown")
        key = raw.split(":", 1)[0] if raw.startswith("propose_error:") else raw
        skipped_by_reason[key] = skipped_by_reason.get(key, 0) + 1

    hits_by_source: dict[str, int] = {}
    for hit in result.get("hits") or []:
        if not isinstance(hit, dict):
            continue
        src = str(hit.get("autoSource") or "unknown")
        hits_by_source[src] = hits_by_source.get(src, 0) + 1

    return {
        "generatedAt": result.get("generatedAt"),
        "planId": result.get("planId"),
        "candidateCount": int(result.get("candidateCount") or 0),
        "hitCount": int(result.get("hitCount") or 0),
        "executeStatus": result.get("executeStatus"),
        "skippedByReason": skipped_by_reason,
        "hitsBySource": hits_by_source,
        "durability": propose_durability(),
    }


def _append_propose_jsonl(snap: dict[str, Any]) -> None:
    path = resolve_propose_path()
    if path is None:
        return
    line = json.dumps(snap, ensure_ascii=False, default=str) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _read_propose_jsonl_tail(limit: int) -> list[dict[str, Any]]:
    """Lee hasta ``limit`` snapshots (más reciente primero). Best-effort."""
    path = resolve_propose_path()
    if path is None or not path.is_file() or limit <= 0:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in reversed(text.splitlines()):
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
        if len(out) >= limit:
            break
    return out


def remember_estudio_auto_propose(result: dict[str, Any]) -> dict[str, Any]:
    """Guarda el último auto-propose en memoria (+ JSONL si path activo)."""
    global _last_propose
    snap = summarize_estudio_auto_propose(result)
    with _last_propose_lock:
        _last_propose = snap
    try:
        _append_propose_jsonl(snap)
    except OSError:
        pass
    return snap


def last_estudio_auto_propose() -> dict[str, Any] | None:
    global _last_propose
    with _last_propose_lock:
        if _last_propose is not None:
            return dict(_last_propose)
    recent = _read_propose_jsonl_tail(1)
    if not recent:
        return None
    snap = recent[0]
    with _last_propose_lock:
        if _last_propose is None:
            _last_propose = snap
        return dict(_last_propose) if _last_propose else dict(snap)


def recent_estudio_auto_proposes(limit: int = RECENT_PROPOSE_LIMIT) -> list[dict[str, Any]]:
    """Histórico corto (más reciente primero). JSONL si hay; si no, memoria."""
    global _last_propose
    limit = max(1, min(int(limit), 50))
    from_file = _read_propose_jsonl_tail(limit)
    if from_file:
        with _last_propose_lock:
            if _last_propose is None:
                _last_propose = from_file[0]
        return from_file
    with _last_propose_lock:
        return [dict(_last_propose)] if _last_propose else []


def count_estudio_auto_funnel(rows: list[Any]) -> dict[str, Any]:
    """Cuenta candidatos A-δ (buy aviso|alarma) sin correr propose."""
    days: set[date] = set()
    alarma = 0
    dictamen = 0
    other = 0
    for row in rows:
        as_of = getattr(row, "as_of_bar_date", None)
        if isinstance(as_of, date):
            days.add(as_of)
        src = resolve_estudio_auto_source(
            stance=str(getattr(row, "stance", "") or ""),
            dictamen_stars=int(getattr(row, "dictamen_stars", 0) or 0),
        )
        if src == "estudio_alarma":
            alarma += 1
        elif src == "estudio_dictamen":
            dictamen += 1
        else:
            other += 1
    return {
        "opinionRows": len(rows),
        "daysWithOpinions": len(days),
        "candidatesAlarma": alarma,
        "candidatesDictamen": dictamen,
        "candidatesTotal": alarma + dictamen,
        "notCandidate": other,
        "allowedSources": list(ALLOWED_AUTO_SOURCES),
        "excludedSources": list(EXCLUDED_AUTO_SOURCES),
    }


def derive_a6_gates(
    *,
    auto_mark: str | None,
    strict_accept_ready: bool,
    edge_report_parity: bool,
    paper_d_execute_env: bool,
) -> dict[str, Any]:
    """Veredictos A6. Expandir fuentes exige P1–P5 PASS + EdgeReport paridad SEMI."""
    blockers: list[str] = []
    mark = (auto_mark or "").strip() or "UNAVAILABLE"
    if mark != "PASS":
        blockers.append("p1_p5_not_green")
    if not edge_report_parity:
        blockers.append("edge_report_parity")
    expand = mark == "PASS" and bool(edge_report_parity)
    contract = mark != "PASS" or not edge_report_parity
    return {
        "expandSourcesReady": expand,
        "sourcesShouldContract": contract,
        "thawEstrictoReady": bool(strict_accept_ready),
        "paperDExecuteEnv": bool(paper_d_execute_env),
        "blockers": blockers,
    }


def build_estudio_auto_telemetry(
    *,
    funnel: dict[str, Any],
    auto_lane: dict[str, Any] | None,
    last_propose: dict[str, Any] | None,
    paper_d_execute_env: bool,
    lookback_days: int,
    as_of: date | None = None,
    recent_proposes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Informe JSON-friendly A6 (read-only)."""
    lane = auto_lane or {}
    auto_mark = str(lane.get("mark") or "UNAVAILABLE")
    strict = bool(lane.get("strictAcceptReady"))
    edge_parity = True  # V1.17.1 + V1.33: paper_auto exige EdgeReport = SEMI
    gates = derive_a6_gates(
        auto_mark=auto_mark,
        strict_accept_ready=strict,
        edge_report_parity=edge_parity,
        paper_d_execute_env=paper_d_execute_env,
    )
    end = as_of or datetime.now(UTC).date()
    recent = list(recent_proposes) if recent_proposes is not None else []
    if last_propose is None and recent:
        last_propose = recent[0]
    durability_note = (
        "lastPropose/recentProposes persisten en JSONL "
        f"(BOLSA_ESTUDIO_AUTO_PROPOSE_PATH; default {DEFAULT_PROPOSE_JSONL.as_posix()})."
        if resolve_propose_path() is not None
        else "lastPropose es memoria de proceso: se pierde al reiniciar la API "
        "(BOLSA_ESTUDIO_AUTO_PROPOSE_PATH=off)."
    )
    caveats = [
        "Embudo = dictámenes Estudio en lookback; no corre propose ni Router.",
        "Hits TRIGGERED / skippedByReason solo en lastPropose (dry-run) o POST auto-propose.",
        durability_note,
        "expandSourcesReady exige P1–P5 PASS (OE-1) + EdgeReport paridad SEMI.",
        "≠ flip PAPER_D_EXECUTE · ≠ Radar/Hoy AUTO · ≠ thaw estricto.",
    ]
    return {
        "schemaVersion": ESTUDIO_AUTO_TELEMETRY_SCHEMA,
        "rule": (
            "measure ≠ Accept estricto · ≠ ampliar fuentes · "
            "≠ thaw estricto · ≠ flip PAPER_D_EXECUTE"
        ),
        "asOf": end.isoformat(),
        "lookbackDays": int(lookback_days),
        "funnel": dict(funnel),
        "edgeReport": {
            "paperAutoRequiresEdgeReport": True,
            "parityWithSemi": edge_parity,
            "mark": "PASS",
            "note": (
                "V1.17.1 + V1.33: paper_auto exige EdgeReport (mismo umbral que SEMI). "
                "Conteos DENY viven en el Router, no en este GET."
            ),
        },
        "p1p5": {
            "mark": auto_mark,
            "strictAcceptReady": strict,
            "p1": lane.get("p1"),
            "p2": lane.get("p2"),
            "p3": lane.get("p3"),
            "p4": lane.get("p4"),
            "p5": lane.get("p5"),
            "source": "oe1_auto_lane",
        },
        "lastPropose": last_propose,
        "recentProposes": recent,
        "gates": gates,
        "caveats": caveats,
    }


class EstudioAutoTelemetryService:
    """Lista opiniones → embudo A-δ. P1–P5 se inyectan desde OE-1 (A0 + counts)."""

    def __init__(self, opinions: Any) -> None:
        self._opinions = opinions

    async def compute(
        self,
        *,
        lookback_days: int = 120,
        instrument_ids: list[str] | None = None,
        as_of: date | None = None,
        auto_lane: dict[str, Any] | None = None,
        paper_d_execute_env: bool | None = None,
    ) -> dict[str, Any]:
        lookback_days = max(7, min(int(lookback_days), 366))
        end = as_of or datetime.now(UTC).date()
        start = end - timedelta(days=lookback_days - 1)
        rows: list[Any] = await self._opinions.list_range(
            date_from=start,
            date_to=end,
            instrument_ids=instrument_ids,
            source=None,
            limit=10_000,
        )
        env = (
            bool(paper_d_execute_env)
            if paper_d_execute_env is not None
            else paper_d_execute_allowed()
        )
        recent = recent_estudio_auto_proposes(RECENT_PROPOSE_LIMIT)
        last = recent[0] if recent else last_estudio_auto_propose()
        return build_estudio_auto_telemetry(
            funnel=count_estudio_auto_funnel(rows),
            auto_lane=auto_lane,
            last_propose=last,
            recent_proposes=recent,
            paper_d_execute_env=env,
            lookback_days=lookback_days,
            as_of=end,
        )
