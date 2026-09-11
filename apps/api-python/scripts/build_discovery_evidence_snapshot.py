"""V2.36 (incremento 1) — job batch/CLI que materializa el snapshot de evidencia.

Fuera del hot path: el worker AUTO **solo lee** el snapshot vigente; este job es el
único que **escribe**. Cierra la mitad offline del bucle ``evidence → aprender``:

1. Lee la agregación por familia H0 de ``research_trials`` (repo, solo lectura).
2. Construye el snapshot determinista (``bolsa_application.discovery_evidence``).
3. Lo persiste de forma **idempotente por ``snapshot_hash``**: si el hash ya existe,
   no reescribe (los snapshots son inmutables).

No hay LLM, ni red, ni escritura en tablas de dominio: solo la tabla aditiva
``discovery_evidence_snapshots``.

Uso (desde la raíz del repo, con el venv de ``apps/api-python``):

    uv run --project apps/api-python python \
        apps/api-python/scripts/build_discovery_evidence_snapshot.py \
        [--window-from ISO] [--window-to ISO] [--dry-run]

``--dry-run`` calcula e imprime el snapshot sin persistirlo (útil para auditar la
fórmula antes de activar el carril adaptativo).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from bolsa_domain.entities.discovery_evidence_snapshot import (
    MATH_VERSION_DISCOVERY_EVIDENCE_V1,
)

# psycopg async no soporta ProactorEventLoop en Windows: se selecciona el bucle
# Selector igual que hacen los tests de infraestructura, para que el job pueda usar
# el engine async de SQLAlchemy en Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DEFAULT_MAX_ADAPTIVE_WEIGHT = 0.5
DEFAULT_MIN_SAMPLES = 3
DEFAULT_MIN_TOTAL_SAMPLES = 12
DEFAULT_MATH_VERSION = MATH_VERSION_DISCOVERY_EVIDENCE_V1


async def build_and_persist(
    *,
    window_from: str | None,
    window_to: str | None,
    dry_run: bool = False,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    min_total_samples: int = DEFAULT_MIN_TOTAL_SAMPLES,
    max_adaptive_weight: float = DEFAULT_MAX_ADAPTIVE_WEIGHT,
    math_version: str = MATH_VERSION_DISCOVERY_EVIDENCE_V1,
) -> dict[str, object]:
    """Lee evidencia, construye el snapshot y (si no es dry-run) lo persiste.

    Devuelve un resumen serializable para el log del job (incluye ``snapshotHash`` y
    ``persisted`` para que el operador sepa si el hash era nuevo o ya existía).

    ``window_to`` por defecto es el ``created_at`` del trial más reciente (corte
    **dato-dependiente**, no reloj): así dos ejecuciones sobre la misma evidencia
    producen el mismo ``snapshot_hash`` y el job es idempotente de verdad.
    """
    from datetime import UTC, datetime

    from bolsa_application.discovery_evidence import (
        build_discovery_evidence_snapshot,
    )
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.discovery_evidence_snapshot_repository import (  # noqa: E501
        SqlAlchemyDiscoveryEvidenceSnapshotRepository,
    )
    from bolsa_infrastructure.database.repositories.research_trial_repository import (
        SqlAlchemyResearchTrialRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory
    from bolsa_infrastructure.ids import new_id

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            trials = SqlAlchemyResearchTrialRepository(session)
            aggregates = await trials.family_evidence_summary(
                date_from=window_from, date_to=window_to
            )
            # V2.37/P2-01: evidencia posterior (shadow / paper forward) por familia.
            posterior = await trials.posterior_evidence_summary(
                date_from=window_from, date_to=window_to
            )
            merged: list[dict[str, object]] = []
            for row in aggregates:
                family = str(row.get("presetKey") or "")
                extra = posterior.get(family, {})
                merged.append({**row, **extra})
            resolved_to = window_to or await trials.latest_trial_at()
            now = datetime.now(UTC).isoformat()
            snapshot = build_discovery_evidence_snapshot(
                snapshot_id=new_id(),
                created_at=now,
                window_from=window_from or "",
                window_to=resolved_to or "",
                aggregates=merged,
                min_samples=min_samples,
                min_total_samples=min_total_samples,
                max_adaptive_weight=max_adaptive_weight,
                math_version=math_version,
                posterior_cut=resolved_to or "",
            )
            persisted = False
            if not dry_run:
                repo = SqlAlchemyDiscoveryEvidenceSnapshotRepository(session)
                before = await repo.get_by_hash(snapshot.snapshot_hash)
                saved = await repo.save(snapshot)
                await session.commit()
                persisted = before is None
                snapshot = saved
            return {
                "snapshotHash": snapshot.snapshot_hash,
                "mathVersion": snapshot.math_version,
                "evidenceFingerprint": snapshot.evidence_fingerprint,
                "windowFrom": snapshot.window_from,
                "windowTo": snapshot.window_to,
                "laneWeights": snapshot.lane_weights,
                "familyWeights": snapshot.family_weights,
                "sampleSizes": snapshot.sample_sizes,
                "persisted": persisted,
                "dryRun": dry_run,
            }
    finally:
        await engine.dispose()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Construye y persiste el snapshot de evidencia del carril adaptativo "
            "del DiscoveryBudgetAllocator (V2.36, incremento 1)."
        )
    )
    parser.add_argument("--window-from", default=None, help="Corte inferior ISO (opcional).")
    parser.add_argument("--window-to", default=None, help="Corte superior ISO (opcional).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calcula e imprime el snapshot sin persistirlo.",
    )
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument("--min-total-samples", type=int, default=DEFAULT_MIN_TOTAL_SAMPLES)
    parser.add_argument("--max-adaptive-weight", type=float, default=DEFAULT_MAX_ADAPTIVE_WEIGHT)
    parser.add_argument(
        "--math-version",
        default=DEFAULT_MATH_VERSION,
        help="Versión de la fórmula (default: la v1 compuesta; usa discovery_evidence_v0 para audit histórico).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    result = asyncio.run(
        build_and_persist(
            window_from=args.window_from,
            window_to=args.window_to,
            dry_run=bool(args.dry_run),
            min_samples=args.min_samples,
            min_total_samples=args.min_total_samples,
            max_adaptive_weight=args.max_adaptive_weight,
            math_version=args.math_version,
        )
    )
    # ASCII-only: evita UnicodeEncodeError (cp1252) al capturar stdout por pipe.
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
