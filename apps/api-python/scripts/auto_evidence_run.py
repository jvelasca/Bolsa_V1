#!/usr/bin/env python3
"""AUTO-22 — RUN de evidencia PAPER end-to-end: un comando, un bundle reproducible, un sello.

Qué hace, exactamente: lee el material PAPER (del PostgreSQL durable o de un JSON de ciclos),
compone en UNA llamada el paquete de evidencia ya auditado —walk-forward ``AUTO-19B``, ``P(R>0)``,
correlación entre estrategias por cubo temporal y evidencia del régimen actual (``AUTO-21``)— y
escribe un **bundle autónomo** en ``--out-dir``: el material, el artefacto que importa la UI, el
render legible y un ``run.json`` con los argumentos, la huella y los TRES niveles de evidencia.

Por qué existe: hasta ``v2.68`` la corrida real era una **secuencia de pasos manuales** (exportar,
lanzar el walk-forward, recomponer el artefacto, copiar números). Copiar un número a mano es el
único modo de que la evidencia publicada no sea la que el instrumento midió. Aquí no se copia nada:
el artefacto viaja verbatim desde el instrumento y el bundle se guarda con la huella del material.

Regla dura: **o se ejecuta completa o se declara BLOQUEADA**. Sin material (sin PG, sin ciclos con R
medible, sin completitud probada) o con la venue distinta de PAPER, NO se escribe ningún fichero: se
declara por stderr y se sale con ``2``. Nunca un bundle parcial.

Uso::

  # Material PAPER real (el paso operativo del propietario)
  uv run --no-sync python apps/api-python/scripts/auto_evidence_run.py \\
      --account-id <uuid> --strategy-version orb-trend
  uv run --no-sync python apps/api-python/scripts/auto_evidence_run.py \\
      --account-id <uuid> --strategy-version orb-trend --strategy-version orb-range \\
      --bucket day --folds 3

  # Material de un JSON de ciclos (fixture declarado, o un volcado previo)
  uv run --no-sync python apps/api-python/scripts/auto_evidence_run.py --cycles ciclos.json

Tras correr, importa ``<out-dir>/<run>/artifact.json`` en la sección AUTO EVIDENCE de la cabina.

Códigos de salida:

* ``0`` — bundle escrito (el detalle, por stderr; los ficheros, en ``--out-dir``).
* ``1`` — uso incorrecto: lo decide ``argparse``.
* ``2`` — **BLOQUEADO**: sin PG, sin material, sin R medible, sin completitud probada, venue no
  PAPER, o el directorio de la corrida ya existe (una corrida es inmutable: no se sobrescribe).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

from bolsa_analytics.cognitive.auto_adaptive_correlation import (  # noqa: E402
    CORRELATION_BUCKET_DEFAULT,
    CORRELATION_BUCKETS,
)
from bolsa_analytics.cognitive.auto_evidence_report import (  # noqa: E402
    MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
)
from bolsa_analytics.cognitive.auto_evidence_run import (  # noqa: E402
    EVIDENCE_LEVELS,
    EVIDENCE_RUN_SCHEMA,
    EvidenceRunBlockedError,
    build_evidence_run_bundle,
)
from bolsa_application.auto_paper_material import (  # noqa: E402
    MaterialIncompleteError,
    NonPaperVenueError,
    read_paper_material,
)

#: Directorio raíz por defecto de las corridas (artefactos generados; no se versionan).
DEFAULT_OUT_ROOT = ROOT / "evidence_runs"


def _json_default(value: Any) -> Any:
    """``Decimal`` → ``str`` y objetos con ``to_dict``: el mismo puente que el exportador."""
    if isinstance(value, Decimal):
        return str(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    raise TypeError(f"no serializable a JSON: {type(value).__name__}")


def _run_id(fingerprint: Any, now: datetime) -> str:
    """Identificador de la corrida: ``<UTC>-<huella8>`` (o ``sin-huella`` si no la declara)."""
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    raw = str(fingerprint or "").strip()
    if not raw:
        return f"{stamp}-sin-huella"
    hexish = raw.split(":", 1)[-1]
    safe = "".join(char for char in hexish if char.isalnum())[:8]
    return f"{stamp}-{safe}" if safe else f"{stamp}-sin-huella"


def _load_cycles(path: Path) -> tuple[list[Any], str, dict[str, Any] | None]:
    """Ciclos, nota y ``material_manifest`` del JSON (mismo contrato que el battery)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    manifest: dict[str, Any] | None = None
    if isinstance(raw, dict):
        cycles = raw.get("cycles", [])
        note = str(raw.get("note", "") or "")
        candidate = raw.get("material_manifest")
        manifest = candidate if isinstance(candidate, dict) else None
    else:
        cycles = raw
        note = ""
    if not isinstance(cycles, list):
        raise SystemExit(f"{path}: se esperaba una lista de ciclos o {{'cycles': [...]}}")
    return cycles, note, manifest


def _print_levels(levels: dict[str, list[dict[str, Any]]]) -> None:
    """Publica los TRES niveles por stderr (lo medido, y lo no medido declarado como tal)."""
    for index, name in enumerate(EVIDENCE_LEVELS, start=1):
        print(f"# NIVEL {index} — {name.upper()}", file=sys.stderr)
        for row in levels.get(name, ()):
            suffix = "  [no medido]" if row.get("inconclusive") else ""
            print(f"#   {row.get('label')}: {row.get('value')}{suffix}", file=sys.stderr)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _persist(target: Path, bundle: dict[str, Any], run: dict[str, Any], cycles: list[Any]) -> None:
    """Escribe el bundle completo. El directorio se crea SOLO al final: sin material no hay carpeta."""
    target.mkdir(parents=True, exist_ok=False)
    _write_text(
        target / "cycles.json",
        json.dumps(cycles, indent=2, ensure_ascii=False, default=_json_default) + "\n",
    )
    _write_text(
        target / "artifact.json",
        json.dumps(bundle["artifact"], indent=2, ensure_ascii=False, default=_json_default) + "\n",
    )
    _write_text(target / "render.txt", str(bundle["render"]))
    _write_text(
        target / "run.json",
        json.dumps(run, indent=2, ensure_ascii=False, default=_json_default) + "\n",
    )


async def _read_pg(account_id: str, versions: list[str], *, limit: int) -> dict[str, Any]:
    """(I/O) lee el material PAPER real por el lector ÚNICO de la aplicación."""
    material = await read_paper_material(account_id, list(versions), limit=limit)
    return material.as_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", default=None, help="cuenta PAPER cuyos fills durables se leen")
    parser.add_argument(
        "--strategy-version",
        action="append",
        dest="versions",
        default=None,
        help="versión de estrategia a medir (repetible)",
    )
    parser.add_argument(
        "--cycles",
        type=Path,
        default=None,
        help="JSON de ciclos en vez de PostgreSQL (fixture declarado o volcado previo)",
    )
    parser.add_argument(
        "--bucket",
        choices=list(CORRELATION_BUCKETS),
        default=CORRELATION_BUCKET_DEFAULT,
        help="cubo temporal de la correlación entre estrategias (day/week/month)",
    )
    parser.add_argument(
        "--current-regime",
        default=None,
        help="régimen actual para la evidencia (por defecto, el del ciclo más reciente)",
    )
    parser.add_argument("--folds", type=int, default=3, help="pliegues del walk-forward")
    parser.add_argument("--seed", type=int, default=42, help="semilla del bootstrap declarada")
    parser.add_argument("--level", type=float, default=0.90, help="nivel del intervalo (0.5–0.99)")
    parser.add_argument("--resamples", type=int, default=2000, help="remuestreos del bootstrap")
    parser.add_argument("--limit", type=int, default=2000, help="tamaño de página de las reservas")
    parser.add_argument(
        "--out-root",
        "--out-dir",
        dest="out_root",
        type=Path,
        default=DEFAULT_OUT_ROOT,
        help="raíz donde se crea <UTC>-<huella8>/ con el bundle de esta corrida",
    )
    args = parser.parse_args(argv)

    if args.cycles is None and not (args.account_id and args.versions):
        print(
            "# uso incorrecto: sin --cycles hacen falta --account-id y --strategy-version",
            file=sys.stderr,
        )
        return 1
    if args.cycles is not None and not args.cycles.exists():
        print(f"# BLOQUEADO: no existe el JSON de ciclos: {args.cycles}", file=sys.stderr)
        return 2

    if sys.platform == "win32":  # pragma: no cover — quirks del loop en la máquina de desarrollo.
        # psycopg no corre sobre el ProactorEventLoop por defecto de Windows. Sin esto, el run
        # fallaría por el loop, no por la base de datos — y un fallo de infraestructura no debe
        # leerse como "sin material".
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    source = "fixture"
    manifest: dict[str, Any] | None = None
    if args.cycles is not None:
        try:
            cycles, note, manifest = _load_cycles(args.cycles)
        except (OSError, ValueError) as error:
            print(f"# BLOQUEADO: no se pudo leer {args.cycles} ({error})", file=sys.stderr)
            return 2
        if note:
            print(f"# nota del material: {note}", file=sys.stderr)
        # El origen lo declara el material, nunca el script: sin manifest, es el fixture declarado.
        material_origin = MATERIAL_ORIGIN_SYNTHETIC_FIXTURE
        if manifest is not None:
            material_origin = str(
                manifest.get("materialOrigin") or MATERIAL_ORIGIN_SYNTHETIC_FIXTURE
            )
        print(
            "# material de un JSON de ciclos (SIN lectura de PostgreSQL): la procedencia la declara "
            f"su manifest ({material_origin})",
            file=sys.stderr,
        )
    else:
        source = "paper_real"
        try:
            payload = asyncio.run(
                _read_pg(args.account_id, list(args.versions or []), limit=max(1, int(args.limit)))
            )
        except MaterialIncompleteError as error:
            print(f"# BLOQUEADO: {error}", file=sys.stderr)
            return 2
        except NonPaperVenueError as error:
            print(f"# BLOQUEADO: {error}", file=sys.stderr)
            return 2
        except Exception as error:  # noqa: BLE001 — sin lectura no hay material: se DECLARA.
            print(
                f"# BLOQUEADO: no se pudo leer el material durable "
                f"({type(error).__name__}: {error})",
                file=sys.stderr,
            )
            return 2
        cycles = list(payload["cycles"])
        manifest = payload["material_manifest"]
        material_origin = str(manifest.get("materialOrigin") or source)
        print(f"# nota del material: {payload['note']}", file=sys.stderr)

    broker_venue = None
    if manifest is not None and manifest.get("brokerVenue"):
        broker_venue = str(manifest["brokerVenue"])

    try:
        bundle = build_evidence_run_bundle(
            cycles,
            material=manifest,
            material_origin=material_origin,
            broker_venue=broker_venue,
            bucket=args.bucket,
            current_regime=args.current_regime,
            folds=args.folds,
            seed=args.seed,
            level=args.level,
            resamples=args.resamples,
        )
    except EvidenceRunBlockedError as error:
        print(f"# BLOQUEADO: {error}", file=sys.stderr)
        return 2

    now = datetime.now(UTC)
    run_id = _run_id(bundle.get("fingerprint"), now)
    target = Path(args.out_root) / run_id
    if target.exists():
        # Una corrida de evidencia es INMUTABLE: sobrescribirla borraría lo que se midió.
        print(
            f"# BLOQUEADO: la corrida {target} ya existe; no se sobrescribe una medición",
            file=sys.stderr,
        )
        return 2

    run = {
        "schema": EVIDENCE_RUN_SCHEMA,
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "materialOrigin": material_origin,
        "brokerVenue": broker_venue,
        "fingerprint": bundle.get("fingerprint"),
        "account": (manifest or {}).get("account"),
        "strategyVersions": list(args.versions or []),
        "bucket": args.bucket,
        "currentRegime": bundle["artifact"].get("currentRegime"),
        "folds": args.folds,
        "seed": args.seed,
        "level": args.level,
        "resamples": args.resamples,
        "cyclesClosed": len(cycles),
        "levels": bundle["levels"],
        "files": {
            "cycles": "cycles.json",
            "artifact": "artifact.json",
            "render": "render.txt",
            "run": "run.json",
        },
    }
    _persist(target, bundle, run, list(cycles))

    print(
        f"# AUTO-22 EVIDENCE RUN — {EVIDENCE_RUN_SCHEMA} · origen={material_origin} · "
        f"huella={bundle.get('fingerprint')} · ciclos={len(cycles)}",
        file=sys.stderr,
    )
    _print_levels(bundle["levels"])
    print(f"# bundle escrito en {target}", file=sys.stderr)
    print(f"# importa {target / 'artifact.json'} en la sección AUTO EVIDENCE", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
