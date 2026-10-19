#!/usr/bin/env python3
"""V2.100 · OPERATIONAL CERTIFICATION EVIDENCE — bundle diario P1-P4 (read-only).

Qué es
------
El instrumento READ-ONLY que agrega, en **un único paquete por día**, la evidencia de los cuatro
pendientes operativos que la auditoría externa dejó abiertos:

* **P1 — ventana PAPER real** (ADR-046): reutiliza el certificador ``v2_98`` (mismo eje
  ``days``/``episodes``/``measurableCycles`` sobre el material durable de ``v2_80``).
* **P2 — evidencia por valor de ESTUDIO**: reutiliza el lector único de la cadena AUTO
  (``read_estudio_chain_evidence``) y su artefacto canónico (9 etapas, ``FILL``/``CYCLE_CLOSED``,
  ``pnl.reconciled``).
* **P3 — enlace DÍA-D ↔ ciclo AUTOmático**: resume el veredicto por ciclo
  (``executedVsDiaD.matches``) del MISMO material del P2.
* **P4 — aislamiento fail-closed**: estado de las barreras LIVE (envs y venue) y recuento de trazas
  con venue LIVE en ``execution_events`` (invariante ``= 0``).

DECLARACIÓN EXPLÍCITA (leer antes de usar)
------------------------------------------
* **Read-only.** No abre el motor, no escribe en PostgreSQL ni en el journal durable, no cambia el
  gobernador, ``TOP_N`` ni ningún umbral. Solo ``SELECT``.
* **No fabrica.** Un dato ausente se declara hueco (``None``/``null``), **jamás** un ``0`` de
  relleno (``UNKNOWN != 0``). Un paquete con huecos NO cierra ningún pendiente: la evidencia
  medida es la que certifica.
* **No sustituye la operación real.** Este bundle ORDENA y PERSISTE la evidencia; conseguirla
  (≥4 días de mercado operables) sigue siendo OPERACIÓN del propietario.

Sale con ``0`` aunque haya huecos (declararlos no es un fallo); ``2`` significa que el material no
se pudo leer (se declara por stderr) y ``1`` un uso incorrecto.

Uso (desde la raíz del repo)::

    uv run --no-sync python apps/api-python/scripts/v2_100_operational_certification_evidence.py \\
        --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --strategy-version "$VERSION_B" \\
        --engine-id auto-sim --json
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import pathlib
import sys
from datetime import UTC, datetime
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "daily-evidence"

#: Envs humanas de ejecución LIVE: su AUSENCIA es la barrera fail-closed (P4).
_LIVE_ENVS = ("LIVE_EXECUTION_UNLOCKED", "LIVE_EXECUTION_AUTHORIZED")

#: Venues que cuentan como traza LIVE en ``execution_events`` (invariante P4).
_LIVE_VENUES = ("live", "broker_live", "xtb", "real", "live_bridge")

#: Etapas canónicas de la cadena AUTO (para declarar el hueco por instrumento).
_CHAIN_STEPS = (
    "SIGNAL",
    "TOP_N",
    "RISK",
    "RESERVATION",
    "ORDER",
    "FILL",
    "PROTECTION",
    "SETTLEMENT",
    "CYCLE_CLOSED",
)


def _die(message: str, code: int = 2) -> int:
    print(f"# BLOQUEADO: {message}", file=sys.stderr)
    return code


def _use_utf8_console() -> None:
    """Fuerza UTF-8 en stdout/stderr: el resumen lleva ``→``/``≥`` (cp1252 los rompería)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):  # pragma: no cover — consola real de Windows.
            reconfigure(encoding="utf-8", errors="replace")


def _load_module(filename: str, name: str) -> Any:
    """Carga un runner hermano por ruta (mismo patrón que ``v2_98``/``v2_99``)."""
    path = pathlib.Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _int_or_none(value: Any) -> int | None:
    """Entero medido o hueco: ``None`` se preserva (nunca se convierte a ``0``)."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _p1_pending(certification: Any) -> dict[str, Any]:
    """Resumen FALSABLE de P1 a partir del certificado ``v2_98`` (hueco = ``None``)."""
    payload = certification.as_dict() if hasattr(certification, "as_dict") else dict(certification)
    days = _int_or_none(payload.get("days"))
    episodes = _int_or_none(payload.get("episodes"))
    cycles = _int_or_none(payload.get("measurableCycles"))
    missing = [str(item) for item in (payload.get("missingCriterionIds") or [])]
    verdict = str(payload.get("verdict") or "")
    return {
        "pendiente": "P1",
        "verdict": verdict,
        "days": days,
        "episodes": episodes,
        "measurableCycles": cycles,
        "thresholds": payload.get("thresholds"),
        "missingCriterionIds": missing,
        # Cierra SOLO con evidencia medida: veredicto READY y sin criterios faltantes.
        "closed": verdict == "READY" and not missing,
    }


def _p2_pending(chain: dict[str, Any]) -> dict[str, Any]:
    """Resumen FALSABLE de P2 a partir del artefacto de cadena (``>0/values`` medidos)."""
    summary = chain.get("summary") or {}
    values = _int_or_none(summary.get("values"))
    measured = _int_or_none(summary.get("measured"))
    complete = _int_or_none(summary.get("complete"))
    return {
        "pendiente": "P2",
        "values": values,
        "measured": measured,
        "completeChains": complete,
        "cycles": _int_or_none(summary.get("cycles")),
        "cyclesComplete": _int_or_none(summary.get("cyclesComplete")),
        "bestScoredPresent": summary.get("bestScoredPresent"),
        # Cierra con al menos un valor medido y una cadena completa (9/9, FILL/CYCLE_CLOSED).
        "closed": bool(measured) and bool(complete),
    }


def _p3_pending(chain: dict[str, Any]) -> dict[str, Any]:
    """Resumen FALSABLE de P3: enlace DÍA-D↔ciclo con ``executedVsDiaD.matches != null``."""
    cycles: list[dict[str, Any]] = []
    for value in chain.get("values") or []:
        cycles.extend(value.get("cycles") or [])
    cycles.extend(chain.get("cyclesOutsideEstudio") or [])

    linked = sum(1 for c in cycles if c.get("diaD") is not None)
    matches_true = 0
    matches_false = 0
    matches_null = 0
    for cycle in cycles:
        block = cycle.get("executedVsDiaD") or {}
        if block.get("matches") is True:
            matches_true += 1
        elif block.get("matches") is False:
            matches_false += 1
        else:
            matches_null += 1
    linked_cycles = [c for c in cycles if c.get("diaD") is not None]
    return {
        "pendiente": "P3",
        "cyclesRead": len(cycles),
        "cyclesWithDiaD": linked,
        "matchesTrue": matches_true,
        "matchesFalse": matches_false,
        "matchesNull": matches_null,
        "linkedCycleIds": [str(c.get("cycleId")) for c in linked_cycles],
        # Cierra cuando existe una fila DÍA-D con identidad declarada por AMBAS partes: matches
        # distinto de None (True o False), nunca fabricado con una sola fuente.
        "closed": (matches_true + matches_false) > 0,
    }


#: Venue EXIGIDO por el contrato de aislamiento P4. Un venue ausente/vacío/desconocido NO cierra.
_REQUIRED_VENUE = "paper"


def _p4_pending(env: dict[str, str | None], live_venue_events: int | None) -> dict[str, Any]:
    """Resumen FALSABLE de P4 a partir del entorno y del invariante de venue LIVE.

    Contrato fail-closed (el MISMO que declaran el README de evidencia y el runbook):
    P4 sólo cierra con ``BROKER_VENUE == "paper"`` **explícito**, las dos envs LIVE ausentes
    y CERO trazas con venue LIVE MEDIDAS. ``venue != "live"`` era más débil que el contrato:
    un venue vacío, ``xtb`` o desconocido podía cerrar P4 si las demás condiciones se cumplían.
    ``UNKNOWN != 0``: con ``live_venue_events is None`` (BD ilegible) el invariante es un hueco
    y P4 queda ABIERTO, nunca un ``0`` de relleno.
    """
    venue = (env.get("BROKER_VENUE") or "").strip().lower()
    live_envs_absent = all(not (env.get(name) or "").strip() for name in _LIVE_ENVS)
    return {
        "pendiente": "P4",
        "brokerVenue": venue or None,
        "liveExecutionEnvsAbsent": live_envs_absent,
        "liveVenueEvents": live_venue_events,
        # Se valida con el contrato EXACTO: venue=paper, sin las dos env LIVE y sin ninguna
        # traza con venue LIVE medida.
        "closed": venue == _REQUIRED_VENUE and live_envs_absent and live_venue_events == 0,
    }


async def _count_live_venue_events(session: Any, account_id: str) -> int | None:
    """Cuenta (read-only) las trazas de ESTA cuenta con venue LIVE. Hueco si no se puede leer."""
    from sqlalchemy import func, select

    from bolsa_infrastructure.database.models.tables import ExecutionEventRow

    try:
        count = (
            await session.execute(
                select(func.count())
                .select_from(ExecutionEventRow)
                .where(
                    ExecutionEventRow.account_id == account_id,
                    func.lower(ExecutionEventRow.venue).in_(_LIVE_VENUES),
                )
            )
        ).scalar()
    except Exception:  # noqa: BLE001 — sin lectura el invariante es un hueco, nunca un 0.
        return None
    return int(count or 0)


async def _resolve_estudio(factory: Any) -> dict[str, Any]:
    """Resuelve el universo ESTUDIO por el camino canónico (reutiliza ``v2_99``)."""
    v99 = _load_module("v2_99_auto_estudio_chain_evidence.py", "v2_99_estudio_chain")
    resolution = await v99._resolve_estudio(factory)  # noqa: SLF001 — se reutiliza el resolver.
    return dict(resolution)


async def _collect(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env", override=False)
    from bolsa_application.auto_chain_durable_reader import (
        build_chain_evidence_artifact,
        read_estudio_chain_evidence,
    )
    from bolsa_application.paper_window_certification import (
        PaperWindowMaterial,
        certify_paper_window,
    )
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    v98 = _load_module("v2_98_paper_window_certification.py", "v2_98_window_cert")

    account_id = str(args.account_id)
    versions = [str(v).strip() for v in (args.strategy_version or []) if str(v).strip()]
    captured_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- P1: certificador de la ventana (lectura canónica v2_80) ---------------------------
    cert_args = argparse.Namespace(
        account_id=account_id,
        strategy_version=versions,
        days=args.days,
        since=args.since,
        limit=int(args.limit),
        forward=args.forward,
    )
    rows, window_meta = await v98.collect_window_rows(cert_args)
    material = PaperWindowMaterial(
        measured=True,
        rows=rows,
        account_id=account_id,
        source="v2_80_market_window._collect (journal durable + fills + reservas + regimen)",
    )
    certification = certify_paper_window(material)

    # --- P2/P3: cadena durable por valor de ESTUDIO ----------------------------------------
    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        estudio = await _resolve_estudio(factory)
        async with factory() as session:
            read = await read_estudio_chain_evidence(
                session,
                account_id,
                engine_id=str(args.engine_id),
                limit=int(args.limit_cycles),
            )
            live_venue_events = await _count_live_venue_events(session, account_id)
    finally:
        await engine.dispose()

    chain = build_chain_evidence_artifact(
        account_id=account_id,
        estudio=estudio,
        cycles=read["cycles"],
        best_scored=read["bestScored"],
        as_of=captured_at,
        meta={
            "bump": "2.11.152-beta",
            "phase": "V2.100 OPERATIONAL CERTIFICATION EVIDENCE",
            "nature": "INVESTIGACION",
            "account": account_id,
            "engineId": str(args.engine_id),
            "source": "read_operational_monitor + v2_98 + top3_opportunities + dia_d",
        },
        limits=[
            "Read-only: solo SELECT; no escribe en la BD durable ni cambia el motor.",
            "Una etapa sin traza durable declara None, nunca 0 (UNKNOWN != 0).",
            "NO sustituye la operación PAPER real: ≥4 días de mercado operables son OPERACIÓN.",
        ],
    )

    # --- P4: aislamiento fail-closed -------------------------------------------------------
    env = {name: os.getenv(name) for name in (*_LIVE_ENVS, "BROKER_VENUE")}

    pendings = {
        "P1": _p1_pending(certification),
        "P2": _p2_pending(chain),
        "P3": _p3_pending(chain),
        "P4": _p4_pending(env, live_venue_events),
    }
    closed = [key for key, value in pendings.items() if value.get("closed")]
    open_pendings = [key for key, value in pendings.items() if not value.get("closed")]

    return {
        "kind": "OPERATIONAL_CERTIFICATION_EVIDENCE",
        "schemaVersion": "operational-certification-v1",
        "readOnly": True,
        "substitutesRealOperation": False,
        "meta": {
            "bump": "2.11.152-beta",
            "phase": "V2.100 OPERATIONAL CERTIFICATION EVIDENCE",
            "nature": "OPERACION",
            "account": account_id,
            "engineId": str(args.engine_id),
            "versions": versions,
            "capturedAt": captured_at,
        },
        "pendings": pendings,
        "closedPendings": closed,
        "openPendings": open_pendings,
        "certification": certification.as_dict(),
        "windowProvenance": window_meta,
        "chainSummary": chain.get("summary"),
        "chainMeta": chain.get("meta"),
        "limits": [
            "El bundle LEE el material durable existente; NO ejecuta la ventana real.",
            "No fabrica: un dato ausente se declara None (hueco), nunca 0 (UNKNOWN != 0).",
            "P1 cierra con verdict=READY y missing vacío; P2 con ≥1 valor medido y cadena completa.",
            "P3 cierra con executedVsDiaD.matches != null; P4 con venue=paper, envs LIVE ausentes "
            "y 0 trazas con venue LIVE.",
            "P4 es un invariante de MANTENIMIENTO: su cierre no acredita la operación PAPER.",
        ],
    }


def _fmt(value: Any) -> str:
    return "hueco" if value is None else str(value)


def _print_summary(bundle: dict[str, Any]) -> None:
    assert isinstance(bundle, dict)
    pend = bundle["pendings"]
    print("OPERATIONAL CERTIFICATION EVIDENCE (V2.100) — read-only; NO sustituye la operación real")
    print("=" * 92)
    print(f"cuenta {bundle['meta']['account']}  ·  capturado {bundle['meta']['capturedAt']}")
    print("")
    p1 = pend["P1"]
    print(
        f"P1 ventana PAPER   {p1['verdict']}  ·  dias {_fmt(p1['days'])}"
        f"  episodios {_fmt(p1['episodes'])}  ciclos {_fmt(p1['measurableCycles'])}"
        f"  =>  {'CERRADO' if p1['closed'] else 'ABIERTO'}"
    )
    p2 = pend["P2"]
    print(
        f"P2 ESTUDIO         valores {_fmt(p2['measured'])}/{_fmt(p2['values'])} medidos"
        f"  cadenas {_fmt(p2['completeChains'])}/{_fmt(p2['values'])}"
        f"  =>  {'CERRADO' if p2['closed'] else 'ABIERTO'}"
    )
    p3 = pend["P3"]
    print(
        f"P3 enlace DIA-D    ciclos {p3['cyclesRead']}  con DIA-D {p3['cyclesWithDiaD']}"
        f"  matches != null {p3['matchesTrue'] + p3['matchesFalse']}"
        f"  =>  {'CERRADO' if p3['closed'] else 'ABIERTO'}"
    )
    p4 = pend["P4"]
    print(
        f"P4 aislamiento     venue {_fmt(p4['brokerVenue'])}"
        f"  envs LIVE ausentes {p4['liveExecutionEnvsAbsent']}"
        f"  trazas LIVE {_fmt(p4['liveVenueEvents'])}"
        f"  =>  {'CERRADO' if p4['closed'] else 'ABIERTO'}"
    )
    print("")
    print(f"cerrados: {', '.join(bundle['closedPendings']) or '(ninguno)'}")
    print(f"abiertos: {', '.join(bundle['openPendings']) or '(ninguno)'}")


def _render_markdown(bundle: dict[str, Any]) -> str:
    pend = bundle["pendings"]
    lines = [
        "# Evidencia de certificación operativa (V2.100) — P1-P4",
        "",
        (
            f"> **Cuenta:** `{bundle['meta']['account']}` · **capturado:** "
            f"{bundle['meta']['capturedAt']} · **read-only** · **NO sustituye la operación PAPER real**."
        ),
        "",
        "## Matriz de pendientes",
        "",
        "| Pendiente | Estado | Evidencia clave |",
        "| --- | --- | --- |",
    ]
    p1 = pend["P1"]
    p2 = pend["P2"]
    p3 = pend["P3"]
    p4 = pend["P4"]
    lines.append(
        f"| P1 ventana PAPER | {'CERRADO' if p1['closed'] else 'ABIERTO'} | verdict={p1['verdict']} · "
        f"días={_fmt(p1['days'])} · episodios={_fmt(p1['episodes'])} · "
        f"ciclos={_fmt(p1['measurableCycles'])} · missing={p1['missingCriterionIds']} |"
    )
    lines.append(
        f"| P2 ESTUDIO | {'CERRADO' if p2['closed'] else 'ABIERTO'} | "
        f"medidos={_fmt(p2['measured'])}/{_fmt(p2['values'])} · "
        f"cadenas={_fmt(p2['completeChains'])} · ciclos={_fmt(p2['cycles'])} |"
    )
    lines.append(
        f"| P3 enlace DÍA-D | {'CERRADO' if p3['closed'] else 'ABIERTO'} | "
        f"ciclos={p3['cyclesRead']} · con DÍA-D={p3['cyclesWithDiaD']} · "
        f"matchesTrue={p3['matchesTrue']} · matchesFalse={p3['matchesFalse']} · "
        f"matchesNull={p3['matchesNull']} |"
    )
    lines.append(
        f"| P4 aislamiento | {'CERRADO' if p4['closed'] else 'ABIERTO'} | "
        f"venue={_fmt(p4['brokerVenue'])} · envs LIVE ausentes={p4['liveExecutionEnvsAbsent']} · "
        f"trazas LIVE={_fmt(p4['liveVenueEvents'])} |"
    )
    lines.extend(
        [
            "",
            f"**Cerrados:** {', '.join(bundle['closedPendings']) or '(ninguno)'} · "
            f"**Abiertos:** {', '.join(bundle['openPendings']) or '(ninguno)'}",
            "",
            "## Límites declarados",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in bundle["limits"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    _use_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, help="cuenta PAPER de la ventana")
    parser.add_argument(
        "--strategy-version",
        action="append",
        default=None,
        metavar="VERSION",
        help="versión de estrategia del material (repetible: una por estrategia del par A/B)",
    )
    parser.add_argument("--engine-id", default="auto-sim", help="motor AUTO (cabecera)")
    parser.add_argument("--days", type=int, default=None, help="ventana de los últimos N días (P1)")
    parser.add_argument("--since", default=None, help="día ISO desde el que leer (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=2000, help="tamaño de página (P1)")
    parser.add_argument(
        "--limit-cycles", type=int, default=100, help="ciclos máximos a leer (P2/P3)"
    )
    parser.add_argument(
        "--forward",
        action="append",
        default=None,
        metavar="PATH|GLOB",
        help="JSON del runner (repetible; admite glob). Opcional y read-only (P1).",
    )
    parser.add_argument("--json", action="store_true", help="emite el bundle como JSON por stdout")
    parser.add_argument(
        "--out",
        default=str(_OUT_SUBDIR),
        help="carpeta del bundle (por defecto operability_runs/daily-evidence/<YYYYMMDD>)",
    )
    args = parser.parse_args(argv)

    if int(args.limit) <= 0:
        return _die("--limit debe ser > 0", code=1)
    if int(args.limit_cycles) <= 0:
        return _die("--limit-cycles debe ser > 0", code=1)

    if sys.platform == "win32":  # pragma: no cover — quirk del loop psycopg en la máquina dev.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        bundle = asyncio.run(_collect(args))
    except Exception as error:  # noqa: BLE001 — sin lectura no hay evidencia: se DECLARA.
        return _die(
            f"no se pudo leer el material de certificación ({type(error).__name__}: {error})"
        )

    day = datetime.now(UTC).strftime("%Y%m%d")
    out_dir = pathlib.Path(args.out)
    if not out_dir.is_absolute():
        out_dir = _REPO_ROOT / out_dir
    out_dir = out_dir / day
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "evidence.json"
    md_path = out_dir / "evidence.md"
    payload = json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    json_path.write_text(payload + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(bundle), encoding="utf-8")

    if args.json:
        print(payload)
    else:
        _print_summary(bundle)
    print("")
    print(f"bundle JSON               {json_path}")
    print(f"bundle MD                 {md_path}")
    print(
        f"# evidencia: cerrados {len(bundle['closedPendings'])}/4 "
        f"({', '.join(bundle['closedPendings']) or 'ninguno'})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
