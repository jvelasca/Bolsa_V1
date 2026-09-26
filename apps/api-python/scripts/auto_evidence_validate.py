#!/usr/bin/env python3
"""AUTO-23 — VALIDACIÓN de la evidencia: un comando, un informe inmutable, o un BLOQUEO.

Qué hace, exactamente: lee el MISMO material PAPER que el RUN (por el **lector único**
``bolsa_application.auto_paper_material.read_paper_material``, o de un JSON de ciclos declarado) y
compone, sin recalcular nada, el informe de validación de la evidencia ``AUTO-22``:

* **Barrido ``P(R>0)`` vs N** — ``P(R>0)`` / OOS / WFE / ``effective_n`` sobre el prefijo cronológico
  para varios tamaños, para observar estabilidad (auditoría ``v2.69``, punto 20). No elige un ``N``.
* **Estabilidad de régimen** — veredicto global vs por régimen de cada estrategia y sus divergencias.
* **Validación de la correlación** — la matriz de ``AUTO-21`` por cubo con los diagnósticos ``P3-2``
  (frecuencia y exposición) declarados, sin tocar la métrica.

Por qué existe: hasta ``v2.69`` la infraestructura de evidencia estaba cerrada pero nadie la había
validado sobre datos reales. Este script deja el andamiaje listo para el primer dataset PAPER; **no
decide** ni mueve el reparto (``auto18-v1`` congelado).

Regla dura: **o se ejecuta completa o se declara BLOQUEADA**. Sin material (sin PG, sin ciclos con R
medible) o con la venue distinta de PAPER, NO se escribe ningún fichero: se declara por stderr y se
sale con ``2``. Nunca un informe parcial.

Uso::

  # Material PAPER real (el paso operativo del propietario)
  uv run --no-sync python apps/api-python/scripts/auto_evidence_validate.py \\
      --account-id <uuid> --strategy-version orb-trend --strategy-version orb-range
  uv run --no-sync python apps/api-python/scripts/auto_evidence_validate.py \\
      --account-id <uuid> --strategy-version orb-trend --sizes 16,32,64 --buckets day,week

  # Material de un JSON de ciclos (fixture declarado, o un volcado previo)
  uv run --no-sync python apps/api-python/scripts/auto_evidence_validate.py --cycles ciclos.json

Códigos de salida:

* ``0`` — informe escrito (el detalle, por stderr; los ficheros, en ``--out-root``).
* ``1`` — uso incorrecto: lo decide ``argparse``.
* ``2`` — **BLOQUEADO**: sin PG, sin material, sin R medible, venue no PAPER, o el directorio de la
  validación ya existe (una validación es inmutable: no se sobrescribe).
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
    CORRELATION_BUCKETS,
)
from bolsa_analytics.cognitive.auto_adaptive_uncertainty import (  # noqa: E402
    ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
)
from bolsa_analytics.cognitive.auto_evidence_report import (  # noqa: E402
    MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
)
from bolsa_analytics.cognitive.auto_evidence_validation import (  # noqa: E402
    CORRELATION_VALIDATION_BUCKETS,
    SAMPLE_SIZE_SWEEP_DEFAULT,
    EvidenceValidationBlockedError,
    build_validation_report,
)
from bolsa_application.auto_paper_material import (  # noqa: E402
    MaterialIncompleteError,
    NonPaperVenueError,
    read_paper_material,
)

#: Directorio raíz por defecto de las validaciones (artefactos generados; no se versionan).
DEFAULT_OUT_ROOT = ROOT / "evidence_validations"


def _json_default(value: Any) -> Any:
    """``Decimal`` → ``str`` y objetos con ``to_dict``: el mismo puente que el exportador."""
    if isinstance(value, Decimal):
        return str(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    raise TypeError(f"no serializable a JSON: {type(value).__name__}")


def _run_id(fingerprint: Any, now: datetime) -> str:
    """Identificador de la validación: ``<UTC>-<huella8>`` (o ``sin-huella`` si no la declara)."""
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    raw = str(fingerprint or "").strip()
    if not raw:
        return f"{stamp}-sin-huella"
    hexish = raw.split(":", 1)[-1]
    safe = "".join(char for char in hexish if char.isalnum())[:8]
    return f"{stamp}-{safe}" if safe else f"{stamp}-sin-huella"


def _int_list(raw: str) -> list[int]:
    """``"16,32,64"`` → ``[16, 32, 64]``; un token no entero es uso incorrecto."""
    values: list[int] = []
    for token in str(raw).split(","):
        token = token.strip()
        if not token:
            continue
        values.append(int(token))
    if not values:
        raise argparse.ArgumentTypeError("se esperaba al menos un tamaño")
    return values


def _bucket_list(raw: str) -> list[str]:
    """``"day,week"`` → ``["day", "week"]``; un cubo desconocido es uso incorrecto."""
    values: list[str] = []
    for token in str(raw).split(","):
        token = token.strip().lower()
        if not token:
            continue
        if token not in CORRELATION_BUCKETS:
            raise argparse.ArgumentTypeError(
                f"cubo desconocido '{token}' (soportados: {', '.join(CORRELATION_BUCKETS)})"
            )
        values.append(token)
    if not values:
        raise argparse.ArgumentTypeError("se esperaba al menos un cubo")
    return values


def _load_cycles(path: Path) -> tuple[list[Any], str, dict[str, Any] | None]:
    """Ciclos, nota y ``material_manifest`` del JSON (mismo contrato que el runner)."""
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


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _dump(path: Path, payload: Any) -> None:
    _write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default) + "\n",
    )


def _persist(target: Path, document: dict[str, Any], report: dict[str, Any]) -> None:
    """Escribe el informe completo. El directorio se crea SOLO al final: sin material no hay carpeta."""
    target.mkdir(parents=True, exist_ok=False)
    _dump(target / "sweep.json", report["sweep"])
    _dump(target / "regime_stability.json", report["regimeStability"])
    _dump(target / "correlation_validation.json", report["correlationValidation"])
    _dump(target / "validation.json", document)


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
        "--sizes",
        type=_int_list,
        default=list(SAMPLE_SIZE_SWEEP_DEFAULT),
        help="tamaños del barrido P(R>0) vs N (por defecto 16,32,64,128)",
    )
    parser.add_argument(
        "--buckets",
        type=_bucket_list,
        default=list(CORRELATION_VALIDATION_BUCKETS),
        help="cubos de la validación de correlación (por defecto day,week,month)",
    )
    parser.add_argument("--folds", type=int, default=3, help="pliegues del walk-forward")
    parser.add_argument("--seed", type=int, default=42, help="semilla del bootstrap declarada")
    parser.add_argument("--level", type=float, default=0.90, help="nivel del intervalo (0.5–0.99)")
    parser.add_argument("--resamples", type=int, default=2000, help="remuestreos del bootstrap")
    parser.add_argument(
        "--min-episodes",
        type=int,
        default=ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
        help="episodios mínimos por celda (no se baja para forzar una corrida)",
    )
    parser.add_argument("--limit", type=int, default=2000, help="tamaño de página de las reservas")
    parser.add_argument(
        "--out-root",
        "--out-dir",
        dest="out_root",
        type=Path,
        default=DEFAULT_OUT_ROOT,
        help="raíz donde se crea <UTC>-<huella8>/ con el informe de esta validación",
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
        # psycopg no corre sobre el ProactorEventLoop por defecto de Windows.
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
        report = build_validation_report(
            cycles,
            material=manifest,
            material_origin=material_origin,
            broker_venue=broker_venue,
            sizes=args.sizes,
            buckets=args.buckets,
            folds=args.folds,
            seed=args.seed,
            level=args.level,
            resamples=args.resamples,
            min_episodes=max(1, int(args.min_episodes)),
        )
    except EvidenceValidationBlockedError as error:
        print(f"# BLOQUEADO: {error}", file=sys.stderr)
        return 2

    now = datetime.now(UTC)
    run_id = _run_id(report.get("fingerprint"), now)
    target = Path(args.out_root) / run_id
    if target.exists():
        # Una validación es INMUTABLE: sobrescribirla borraría lo que se midió.
        print(
            f"# BLOQUEADO: la validación {target} ya existe; no se sobrescribe una medición",
            file=sys.stderr,
        )
        return 2

    document = dict(report)
    document["run"] = {
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "materialOrigin": material_origin,
        "brokerVenue": broker_venue,
        "account": (manifest or {}).get("account"),
        "strategyVersions": list(args.versions or []),
        "sizes": list(args.sizes),
        "buckets": list(args.buckets),
        "folds": args.folds,
        "seed": args.seed,
        "level": args.level,
        "resamples": args.resamples,
        "cyclesClosed": len(cycles),
        "files": {
            "sweep": "sweep.json",
            "regimeStability": "regime_stability.json",
            "correlationValidation": "correlation_validation.json",
        },
    }
    _persist(target, document, report)

    print(
        f"# AUTO-23 EVIDENCE VALIDATION — {report['schema']} · origen={material_origin} · "
        f"huella={report.get('fingerprint')} · ciclos={len(cycles)} · "
        f"medidos={report['measuredCycles']}",
        file=sys.stderr,
    )
    print(f"# informe escrito en {target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
