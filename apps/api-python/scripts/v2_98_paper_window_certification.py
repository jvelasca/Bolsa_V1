#!/usr/bin/env python3
"""V2.98 · PAPER WINDOW CERTIFICATION — certificador EJECUTABLE de la ventana PAPER (P3-2/P3-3).

Qué es
------
El paso **4a** del veredicto (la parte CODIFICABLE): el certificador de la ventana longitudinal
PAPER (``P3-2``/``P3-3``, ADR-046), leído de **HECHOS DURABLES**. Reutiliza el MISMO instrumento de
la ventana (``v2_80_market_window.py`` → ``window_gate``) y traduce su salida al contrato tipado
``paper_window_certification``: ``days``/``episodes``/``measurable_cycles``, los umbrales exigidos y
la lista de criterios faltantes.

DECLARACIÓN EXPLÍCITA (leer antes de usar)
------------------------------------------
* **NO sustituye la ventana real.** El requisito es ``≥4 días`` de **CALENDARIO**, y esos «días»
  salen del reloj de pared (``sim_fill_finance_context.created_at``): una corrida real de ``≥4``
  días **NO es automatizable en CI**. Esta herramienta sólo LEE el material durable que ya existe y
  **DECLARA el hueco honestamente** (``INCONCLUSIVE``); la corrida real queda como **OPERACIÓN** del
  propietario, nunca como un verde de pipeline.
* **No fabrica.** Sin material medido los conteos son ``None`` (hueco), jamás un ``0`` de relleno
  (``UNKNOWN ≠ 0``). Un material leído y vacío sí es un cero MEDIDO, y también es ``INCONCLUSIVE``.
* **Read-only.** No abre el motor, no escribe en PostgreSQL ni en el journal durable, no cambia el
  gobernador, ``TOP_N`` ni ningún umbral. Reutiliza la lectura canónica de ``v2_80``.

Sale con ``0`` aunque el veredicto sea ``INCONCLUSIVE`` (declarar el hueco no es un fallo): sólo un
``2`` significa que el material no se pudo leer (se declara por stderr) y ``1`` un uso incorrecto.

Uso (desde la raíz del repo)::

    uv run --no-sync python apps/api-python/scripts/v2_98_paper_window_certification.py \\
        --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --strategy-version "$VERSION_B" \\
        --json --out operability_runs/paper-window-certification/cert.json
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import pathlib
import sys
from datetime import UTC, datetime
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "paper-window-certification"
_DEFAULT_OUT = _OUT_SUBDIR / "paper-window-certification.json"


def _die(message: str, code: int = 2) -> int:
    print(f"# BLOQUEADO: {message}", file=sys.stderr)
    return code


def _use_utf8_console() -> None:
    """Fuerza UTF-8 en stdout/stderr: la ayuda y el resumen llevan ``→``/``≥`` (cp1252 los rompería)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):  # pragma: no cover — consola real de Windows.
            reconfigure(encoding="utf-8", errors="replace")


def _load_module(filename: str, name: str) -> Any:
    """Carga un runner hermano por ruta (mismo patrón que ``v2_90``)."""
    path = pathlib.Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


async def collect_window_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Lee la serie diaria durable por el camino CANÓNICO (``v2_80._collect``): una sola lectura.

    No se reimplementa la lectura: se reutiliza el instrumento de la ventana para que el material
    certificado sea EXACTAMENTE el que publica ``v2_80`` (mismos días, mismos ciclos, mismo gate).
    Es ``async`` para poder reutilizarse desde un test PG dentro de un bucle ya en marcha.
    """
    v80 = _load_module("v2_80_market_window.py", "v2_80_market_window")
    window_args = argparse.Namespace(
        account_id=str(args.account_id),
        strategy_version=[str(v) for v in (args.strategy_version or []) if str(v).strip()],
        days=args.days,
        since=args.since,
        limit=int(args.limit),
        forward=args.forward,
    )
    return await v80._collect(window_args)  # noqa: SLF001 — se reutiliza el instrumento.


def _read_material(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if sys.platform == "win32":  # pragma: no cover — quirk del loop psycopg en la máquina dev.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(collect_window_rows(args))


def _build_artifact(
    *,
    certification: dict[str, Any],
    provenance: dict[str, Any],
    account_id: str,
    versions: list[str],
    captured_at: str,
) -> dict[str, Any]:
    """Artefacto JSON con el veredicto, el eje, su procedencia y los límites declarados."""
    return {
        "kind": "PAPER_WINDOW_CERTIFICATION",
        "schemaVersion": certification["schemaVersion"],
        "readOnly": True,
        # El certificador NO promociona la ventana: la corrida real ≥4 días es OPERACIÓN.
        "substitutesRealWindow": False,
        "meta": {
            "bump": "2.11.125-beta",
            "phase": "V2.98 PAPER WINDOW CERTIFICATION",
            "nature": "OPERACION",
            "account": account_id,
            "versions": versions,
            "capturedAt": captured_at,
        },
        "certification": certification,
        "provenance": provenance,
        "limits": [
            "El certificado LEE el material durable existente; NO ejecuta la ventana real.",
            "≥4 días de CALENDARIO salen del reloj de pared (sim_fill_finance_context.created_at): "
            "la corrida real queda como OPERACIÓN, no como CI.",
            "Un material no medido declara None (hueco), nunca 0 (UNKNOWN != 0).",
            "Eje: días de calendario / regímenes distintos / ciclos medibles (window_gate).",
        ],
    }


def _print_summary(artifact: dict[str, Any]) -> None:
    cert = artifact["certification"]
    header = artifact.get("provenance") or {}
    print("PAPER WINDOW CERTIFICATION (V2.98) — read-only; NO sustituye la ventana real")
    print("=" * 92)
    print(
        f"cuenta {artifact['meta']['account']}  ·  "
        f"versiones {', '.join(artifact['meta']['versions']) or '(ninguna)'}  ·  "
        f"capturado {artifact['meta']['capturedAt']}"
    )
    header_view = header.get("header") if isinstance(header, dict) else None
    if isinstance(header_view, dict):
        print(
            f"fills leidos {header_view.get('fillsRead')}  ·  "
            f"ciclos {header_view.get('cyclesRead')}  ·  "
            f"entradas de journal {header_view.get('journalEntriesRead')}"
        )
    print("")
    print(f"EJE: {cert['axis']}")
    print(
        f"  dias={cert['days']}/{cert['thresholds']['days']}"
        f"  episodios={cert['episodes']}/{cert['thresholds']['episodes']}"
        f"  ciclos={cert['measurableCycles']}/{cert['thresholds']['measurableCycles']}"
        f"  =>  {cert['verdict']}"
    )
    if cert["missingCriterionIds"]:
        print(f"  criterios faltantes: {', '.join(cert['missingCriterionIds'])}")
    if cert["verdict"] != "READY":
        print("  (INCONCLUSIVE honesto: la ventana real ≥4 días aún no se acredita; es OPERACIÓN)")


def main(argv: list[str] | None = None) -> int:
    _use_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, help="cuenta PAPER de la ventana")
    parser.add_argument(
        "--strategy-version",
        action="append",
        default=None,
        required=True,
        metavar="VERSION",
        help="versión de estrategia del material (repetible: una por estrategia del par A/B)",
    )
    parser.add_argument("--days", type=int, default=None, help="ventana de los últimos N días")
    parser.add_argument("--since", default=None, help="día ISO desde el que leer (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=2000, help="tamaño de página de las lecturas")
    parser.add_argument(
        "--forward",
        action="append",
        default=None,
        metavar="PATH|GLOB",
        help="JSON de evidencia del runner (repetible; admite glob). OPCIONAL y read-only: enriquece "
        "SOLO los huecos declarados del funnel/par A/B, nunca sobrescribe lo medido.",
    )
    parser.add_argument("--json", action="store_true", help="emite el artefacto como JSON por stdout")
    parser.add_argument(
        "--out",
        default=str(_DEFAULT_OUT),
        help="ruta del JSON del certificado (por defecto operability_runs/paper-window-certification)",
    )
    args = parser.parse_args(argv)

    from bolsa_application.paper_window_certification import (
        PaperWindowMaterial,
        certify_paper_window,
    )

    try:
        rows, meta = _read_material(args)
    except Exception as error:  # noqa: BLE001 — sin lectura no hay material: se DECLARA.
        return _die(f"no se pudo leer el material PAPER durable ({type(error).__name__}: {error})")

    captured_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    versions = [str(v).strip() for v in (args.strategy_version or []) if str(v).strip()]
    material = PaperWindowMaterial(
        # La lectura canónica de ``v2_80`` completó: con días presentes o vacíos, se MIDIÓ.
        measured=True,
        rows=rows,
        account_id=str(args.account_id),
        source="v2_80_market_window._collect (journal durable + fills + reservas + regimen)",
    )
    certification = certify_paper_window(material)
    artifact = _build_artifact(
        certification=certification.as_dict(),
        provenance=meta,
        account_id=str(args.account_id),
        versions=versions,
        captured_at=captured_at,
    )

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
        print(f"certificado                {out_path}")
    print(
        f"# certificado: {certification.verdict} · dias {certification.days} · "
        f"episodios {certification.episodes} · ciclos {certification.measurable_cycles}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
