#!/usr/bin/env python3
"""AUTO-19A/19B — imprime el informe del REPLAY OOS (``statistical_oos_v1``) o de la CALIBRACIÓN
walk-forward (``walk_forward_calibration_v1``).

Qué hace, exactamente: lee un JSON de ciclos (por defecto el fixture determinista de la fase que
toca) y emite por **stdout** el informe completo —las celdas medidas y las respuestas con su
veredicto y su muestra—. Es un instrumento PURO: no toca Postgres, no re-simula órdenes y no mueve
el reparto. Sin ``--cycles`` el fixture es SINTÉTICO: los veredictos que salgan miden el
instrumento, no la estrategia real.

Uso:

  # Replay de una sola partición IS/OOS (AUTO-19A, sin cambios)
  python scripts/research/auto_replay_battery.py
  python scripts/research/auto_replay_battery.py --cycles /ruta/ciclos.json --oos-pct 0.25

  # Calibración walk-forward (AUTO-19B): ventanas crecientes + cobertura del intervalo
  python scripts/research/auto_replay_battery.py --walk-forward
  python scripts/research/auto_replay_battery.py --walk-forward --cycles ciclos.json --folds 4

  # AUTO-20C: además, guardar el artefacto reproducible y el render legible
  python scripts/research/auto_replay_battery.py --walk-forward --cycles ciclos.json \\
      --out AUTO20C_REAL_PAPER_REPORT.json --render AUTO20C_REAL_PAPER_REPORT.txt

El JSON de entrada puede ser una LISTA de ciclos o un OBJETO
``{"cycles": [...], "note": "...", "material_manifest": {...}}``: la nota y la huella del material
(si las trae) se copian a stderr, nunca al JSON de stdout. Cuando el objeto trae
``material_manifest`` (AUTO-20B), se propaga al informe de calibración como bloque ``material``
(metadata de ENTRADA declarada); sin él, el informe queda byte-idéntico.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "py" / "analytics" / "src"))

from bolsa_analytics.cognitive.auto_adaptive_calibration import (  # noqa: E402
    CALIBRATION_FOLDS_DEFAULT,
    build_calibration_report,
)
from bolsa_analytics.cognitive.auto_adaptive_correlation import (  # noqa: E402
    CORRELATION_BUCKET_DEFAULT,
    CORRELATION_BUCKETS,
    build_strategy_correlation_report,
)
from bolsa_analytics.cognitive.auto_adaptive_regime_evidence import (  # noqa: E402
    build_current_regime_evidence,
)
from bolsa_analytics.cognitive.auto_adaptive_replay import (  # noqa: E402
    REPLAY_OOS_PCT_DEFAULT,
    build_replay_report,
)
from bolsa_analytics.cognitive.auto_evidence_report import (  # noqa: E402
    MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
    build_evidence_artifact,
    render_evidence_report,
)

DEFAULT_FIXTURE = (
    ROOT / "packages" / "py" / "analytics" / "tests" / "fixtures" / "auto_replay_cycles.json"
)
CALIBRATION_FIXTURE = (
    ROOT / "packages" / "py" / "analytics" / "tests" / "fixtures" / "auto_calibration_cycles.json"
)


def _load(path: Path) -> tuple[list[Any], str, dict[str, Any] | None]:
    """Ciclos, nota y manifest del JSON, con el contrato declarado.

    Acepta una LISTA de ciclos o un OBJETO ``{"cycles": [...], "note": ..., "material_manifest": ...}``.
    El ``material_manifest`` (AUTO-20B) es OPCIONAL: el fixture sintético no lo trae, y entonces el
    informe de calibración queda byte-idéntico al que ya se auditó. Cuando lo trae, se propaga como
    metadata de ENTRADA (huella + conteos) sin que cambie ninguna medición.
    """
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cycles",
        type=Path,
        default=None,
        help="JSON de ciclos (por defecto: el fixture sintético de la fase)",
    )
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help="emite el informe de CALIBRACIÓN walk-forward (AUTO-19B) en vez del replay",
    )
    parser.add_argument(
        "--folds",
        type=int,
        default=CALIBRATION_FOLDS_DEFAULT,
        help="pliegues del walk-forward (se acotan a 2–5)",
    )
    parser.add_argument(
        "--bucket",
        choices=list(CORRELATION_BUCKETS),
        default=CORRELATION_BUCKET_DEFAULT,
        help="AUTO-21: cubo temporal de la correlación entre estrategias (day/week/month)",
    )
    parser.add_argument(
        "--current-regime",
        default=None,
        help="AUTO-21: régimen actual para la evidencia (por defecto, el del ciclo más reciente)",
    )
    parser.add_argument(
        "--oos-pct", type=float, default=REPLAY_OOS_PCT_DEFAULT, help="fracción OOS (0.1–0.4)"
    )
    parser.add_argument("--seed", type=int, default=42, help="semilla del bootstrap declarada")
    parser.add_argument("--level", type=float, default=0.90, help="nivel del intervalo (0.5–0.99)")
    parser.add_argument("--resamples", type=int, default=2000, help="remuestreos del bootstrap")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="AUTO-20C: escribe el artefacto reproducible (envelope + informe) en esta ruta",
    )
    parser.add_argument(
        "--render",
        type=Path,
        default=None,
        help="AUTO-20C: escribe el render legible AUTO EVIDENCE REPORT en esta ruta",
    )
    args = parser.parse_args(argv)

    # Sin ``--cycles`` el defecto depende del instrumento: el replay sigue byte-idéntico a AUTO-19A
    # (mismo fixture, mismo JSON) y el walk-forward usa el fixture de la calibración.
    default_fixture = CALIBRATION_FIXTURE if args.walk_forward else DEFAULT_FIXTURE
    path = args.cycles if args.cycles is not None else default_fixture
    if not path.exists():
        raise SystemExit(f"no existe el JSON de ciclos: {path}")
    cycles, note, manifest = _load(path)
    if note:
        print(f"# nota del material: {note}", file=sys.stderr)
    if manifest is not None:
        # La huella del material REAL va a stderr (nunca dentro del informe): permite comparar
        # dos corridas y saber si midieron el MISMO universo sin abrir el JSON a mano.
        print(
            f"# material_manifest: huella {manifest.get('fingerprint')} "
            f"({manifest.get('fingerprintMethod')}); ciclos={manifest.get('closedCycles')} "
            f"conR={manifest.get('cyclesWithRisk')} sinR={manifest.get('cyclesWithoutRisk')}",
            file=sys.stderr,
        )
    if path == default_fixture:
        print(
            "# material SINTÉTICO por defecto: mide el instrumento, no la estrategia", file=sys.stderr
        )

    if args.walk_forward:
        report = build_calibration_report(
            cycles,
            folds=args.folds,
            seed=args.seed,
            level=args.level,
            resamples=args.resamples,
            material=manifest,
        )
    else:
        report = build_replay_report(
            cycles,
            oos_pct=args.oos_pct,
            seed=args.seed,
            interval_level=args.level,
            resamples=args.resamples,
        )
    payload = report.as_dict()
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")

    if args.out is not None or args.render is not None:
        # AUTO-20C — artefacto reproducible: envuelve el informe (verbatim) con el manifest del
        # material. El origen se toma del manifest (el exportador lo declara); sin manifest, el
        # material es el fixture sintético y se declara como tal. Nunca se inventa la procedencia.
        material_origin = MATERIAL_ORIGIN_SYNTHETIC_FIXTURE
        broker_venue: str | None = None
        if manifest is not None:
            material_origin = str(
                manifest.get("materialOrigin") or MATERIAL_ORIGIN_SYNTHETIC_FIXTURE
            )
            broker_venue = (
                str(manifest["brokerVenue"]) if manifest.get("brokerVenue") else None
            )
        correlation = build_strategy_correlation_report(cycles, bucket=args.bucket)
        current_evidence = build_current_regime_evidence(
            cycles,
            current_regime=args.current_regime,
            level=args.level,
            resamples=args.resamples,
            seed=args.seed,
        )
        artifact = build_evidence_artifact(
            payload,
            material=manifest,
            broker_venue=broker_venue,
            material_origin=material_origin,
            correlation=correlation.as_dict(),
            current_regime=current_evidence.regime,
            current_evidence=current_evidence.as_dict(),
        )
        if args.out is not None:
            _write(args.out, json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
            print(f"# artefacto AUTO-20C escrito en {args.out}", file=sys.stderr)
        if args.render is not None:
            _write(args.render, render_evidence_report(artifact))
            print(f"# render AUTO EVIDENCE REPORT escrito en {args.render}", file=sys.stderr)
    return 0


def _write(path: Path, text: str) -> None:
    """Escribe ``text`` en ``path`` creando el directorio padre (artefacto de investigación)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
