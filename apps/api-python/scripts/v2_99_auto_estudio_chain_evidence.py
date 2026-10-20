#!/usr/bin/env python3
"""V2.99 · AUTO ESTUDIO CHAIN EVIDENCE — evidencia POR VALOR de ESTUDIO de la cadena AUTO.

Qué es
------
El instrumento READ-ONLY que demuestra, **por cada valor del universo ESTUDIO y por ciclo**, la
cadena completa de la operativa AUTO desde HECHOS DURABLES::

    SIGNAL -> TOP_N -> RISK -> RESERVATION -> ORDER -> FILL -> PROTECTION
           -> SETTLEMENT -> CYCLE_CLOSED (P&L conciliado) -> verificación DÍA D

Reutiliza el **lector único** (``read_operational_monitor``) para las nueve etapas —sin un segundo
FIFO de P&L— y la foto durable del selector cross-asset (``top3_opportunities``) para contrastar la
estrategia **EJECUTADA** (identidad que sella el ciclo: ``strategyPresetKey``/``strategyVersion`` y
su ``rank``) con la **MEJOR PUNTUADA** del selector.

DECLARACIÓN EXPLÍCITA (leer antes de usar)
------------------------------------------
* **Read-only.** No abre el motor, no escribe en PostgreSQL ni en el journal durable, no cambia el
  gobernador, ``TOP_N`` ni ningún umbral. Solo ``SELECT``.
* **No fabrica.** Una etapa sin traza durable viaja ``None`` con su medición (hueco); **jamás** un
  ``0`` de relleno (``UNKNOWN != 0``). Un valor sin ciclos declara ``cycles=[]`` y ``complete=False``.
* **No certifica la operación real.** Prueba la CADENA FUNCIONAL sobre el material durable; la
  ventana PAPER real y la rentabilidad siguen NO MEDIDAS (son OPERACIÓN).

Sale con ``0`` aunque no haya ciclos (declarar el hueco no es un fallo); ``2`` significa que el
material no se pudo leer.

Uso (desde la raíz del repo)::

    uv run --no-sync python apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py \\
        --account-id "$ACCOUNT" --engine-id "$ENGINE" --json \\
        --out operability_runs/estudio-chain/estudio-chain.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
from datetime import UTC, datetime
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "estudio-chain"
_DEFAULT_OUT = _OUT_SUBDIR / "estudio-chain.json"


def _die(message: str, code: int = 2) -> int:
    print(f"# BLOQUEADO: {message}", file=sys.stderr)
    return code


def _use_utf8_console() -> None:
    """Fuerza UTF-8 en stdout/stderr: el resumen lleva ``→``/``≠`` (cp1252 los rompería)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):  # pragma: no cover — consola real de Windows.
            reconfigure(encoding="utf-8", errors="replace")


async def _resolve_estudio(factory: Any) -> dict[str, Any]:
    """Resuelve el universo ESTUDIO por el camino canónico (sin reimplementar ESTUDIO)."""
    from bolsa_api.background.estudio_watch import SessionScopedEstudioList
    from bolsa_application.paper_desk_entry import resolve_estudio_universe

    resolution = await resolve_estudio_universe(SessionScopedEstudioList(factory))
    ids = [str(i) for i in (getattr(resolution, "instrument_ids", None) or []) if i]
    return {"status": getattr(resolution, "status", None), "instrumentIds": ids}


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env", override=False)
    from bolsa_application.auto_chain_durable_reader import (
        build_chain_evidence_artifact,
        read_estudio_chain_evidence,
    )
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        estudio = await _resolve_estudio(factory)
        allowlist = tuple(s for s in (args.watch or "").split(",") if s.strip())
        if allowlist:
            wanted = set(allowlist)
            estudio["instrumentIds"] = [i for i in estudio["instrumentIds"] if i in wanted]
            estudio["allowlist"] = list(allowlist)

        async with factory() as session:
            read = await read_estudio_chain_evidence(
                session,
                str(args.account_id),
                engine_id=str(args.engine_id),
                limit=int(args.limit),
                cycle_id=str(args.cycle_id) if args.cycle_id else None,
                instrument_id=str(args.instrument_id) if args.instrument_id else None,
            )

        artifact = build_chain_evidence_artifact(
            account_id=str(args.account_id),
            estudio=estudio,
            cycles=read["cycles"],
            best_scored=read["bestScored"],
            meta={
                "bump": "2.11.155-beta",
                "phase": "V2.99 AUTO ESTUDIO CHAIN EVIDENCE",
                "nature": "INVESTIGACION",
                "account": str(args.account_id),
                "engineId": str(args.engine_id),
                "limit": int(args.limit),
                "cycleId": str(args.cycle_id) if args.cycle_id else None,
                "instrumentId": str(args.instrument_id) if args.instrument_id else None,
                "top3RunId": (read.get("top3") or {}).get("runId"),
                "source": "read_operational_monitor (lector único) + top3_opportunities + dia_d",
            },
            limits=[
                "Read-only: solo SELECT; no escribe en la BD durable ni cambia el motor.",
                "La cadena se LEE de hechos durables; una etapa sin traza declara None, nunca 0.",
                "La foto TOP3 es cross-asset del MOTOR y best-effort: sin foto, la mejor puntuada "
                "es un hueco declarado (no se inventa).",
                "La foto TOP3 no sella identidad de estrategia: 'bestScoredPresetKey' es None y el "
                "emparejamiento por preset es un hueco declarado (solo se compara por activo/rank).",
                "La verificación DÍA-D es opcional por ciclo: sin ella, el ciclo declara diaD=None "
                "y 'executedVsDiaD.matches' queda None (no se fabrica un False con una sola parte).",
                "NO certifica la ventana PAPER real ni la rentabilidad: eso es OPERACIÓN.",
            ],
        )
        artifact["monitor"] = {
            "header": (read["monitor"] or {}).get("header"),
            "notes": (read["monitor"] or {}).get("notes"),
        }
        return artifact
    finally:
        await engine.dispose()


def _print_summary(artifact: dict[str, Any]) -> None:
    summary = artifact["summary"]
    estudio = artifact["estudio"]
    print("AUTO ESTUDIO CHAIN EVIDENCE (V2.99) — read-only; NO sustituye la operación PAPER real")
    print("=" * 92)
    print(
        f"cuenta {artifact['accountId']}  ·  ESTUDIO {estudio.get('status')} "
        f"({estudio.get('values')} valores)  ·  asOf {artifact['asOf']}"
    )
    print(
        f"valores medidos {summary['measured']}/{summary['values']}  ·  "
        f"cadenas completas {summary['complete']}/{summary['values']}  ·  "
        f"ciclos {summary['cycles']} (completos {summary['cyclesComplete']})  ·  "
        f"mejor puntuada {'sí' if summary['bestScoredPresent'] else 'NO (hueco)'}"
    )
    print("")
    header = (
        "VALOR                         CICLO            ETAPAS  EJECUTADA            "
        "vs MEJOR        vs DIA D"
    )
    print(header)
    print("-" * len(header))
    for value in artifact["values"]:
        iid = value["instrumentId"]
        if not value["cycles"]:
            print(f"{iid[:28]:<29} {'(sin ciclos)':<16} {'-':<7} {'-':<21} {'-':<15} -")
            continue
        for cycle in value["cycles"]:
            reached = f"{len(cycle['chain']['reached'])}/9"
            executed = cycle["executed"].get("strategyPresetKey") or "(sin dato)"
            vs_best = cycle["executedVsBest"]
            verdict = (
                "mejor puntuada"
                if vs_best.get("executedIsTopRanked") is True
                else "no #1"
                if vs_best.get("executedIsTopRanked") is False
                else "n/d"
            )
            # El eslabón DÍA D se declara por separado: sin verificación es un hueco, no un "OK".
            dia_d = cycle.get("executedVsDiaD") or {}
            if cycle.get("diaD") is None:
                dia_d_verdict = "sin verif."
            elif dia_d.get("matches") is True:
                dia_d_verdict = "identidad ="
            elif dia_d.get("matches") is False:
                dia_d_verdict = "identidad != "
            else:
                dia_d_verdict = "n/d"
            print(
                f"{iid[:28]:<29} {str(cycle['cycleId'])[:15]:<16} "
                f"{reached:<7} {str(executed)[:20]:<21} {verdict:<15} {dia_d_verdict}"
            )


def main(argv: list[str] | None = None) -> int:
    _use_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, help="cuenta de la ventana AUTO")
    parser.add_argument("--engine-id", default="auto-sim", help="motor AUTO (para la cabecera)")
    parser.add_argument("--limit", type=int, default=100, help="ciclos máximos a leer")
    parser.add_argument("--cycle-id", default=None, help="acota a UN ciclo (drill-down)")
    parser.add_argument(
        "--instrument-id", default=None, help="acota a UN valor (si no hay ciclo-id)"
    )
    parser.add_argument(
        "--watch",
        default=None,
        help="allowlist de instrumentos separados por coma que INTERSECTA ESTUDIO (vacío: todo)",
    )
    parser.add_argument(
        "--json", action="store_true", help="emite el artefacto como JSON por stdout"
    )
    parser.add_argument(
        "--out",
        default=str(_DEFAULT_OUT),
        help="ruta del JSON de evidencia (por defecto operability_runs/estudio-chain)",
    )
    args = parser.parse_args(argv)

    if int(args.limit) <= 0:
        return _die("--limit debe ser > 0", code=1)

    if sys.platform == "win32":  # pragma: no cover — quirk del loop psycopg en la máquina dev.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        artifact = asyncio.run(_run(args))
    except Exception as error:  # noqa: BLE001 — sin lectura no hay evidencia: se DECLARA.
        return _die(f"no se pudo leer la cadena durable ({type(error).__name__}: {error})")

    artifact["asOf"] = artifact.get("asOf") or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path = pathlib.Path(args.out)
    if not out_path.is_absolute():
        out_path = _REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    out_path.write_text(payload + "\n", encoding="utf-8")

    if args.json:
        print(payload)
    else:
        _print_summary(artifact)
        print("")
        print(f"evidencia                  {out_path}")
    summary = artifact["summary"]
    print(
        f"# evidencia: valores {summary['measured']}/{summary['values']} medidos · "
        f"cadenas {summary['complete']}/{summary['values']} completas · "
        f"ciclos {summary['cycles']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
