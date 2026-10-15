#!/usr/bin/env python3
"""V2.36/A16 — informe determinista del rollout de la gramática de Discovery.

**Solo lectura.** Compara el discovery con la gramática **ON vs OFF** usando los
presupuestos REALES del worker (``_discovery_budget`` / ``_grammar_budget`` /
``_grammar_policy``) y emite la **procedencia catálogo vs gramática** (candidatas y
``presetKey`` gramaticales emitidos). No escribe nada, no abre venues, no toca gates.

Modos:

* **Determinista (siempre, offline)**: corre ``discover_for_instrument_with_summary``
  sobre un universo determinista y comprueba las invariantes de rollout (OFF intacto,
  ON aditivo sobre el catálogo, cuadre ``catálogo + gramática = total``, determinismo).
  Este modo decide el **exit 0/1**.
* **BD (opt-in, ``--db`` + ``DATABASE_URL``)**: agrega la procedencia **real
  persistida** (``strategy_candidates.strategy_family LIKE 'grammar:%'`` unido a
  ``strategy_evaluations``) para contrastar la teoría con lo ejecutado. Es
  **best-effort**: cualquier fallo se reporta y NUNCA cambia el exit code.

Uso (repo root):

  uv run python scripts/verify/report_grammar_rollout.py
  uv run python scripts/verify/report_grammar_rollout.py --db
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (
    ROOT / "packages" / "py" / "application" / "src",
    ROOT / "packages" / "py" / "infrastructure" / "src",
    ROOT / "apps" / "api-python" / "src",
):
    if str(_p) not in sys.path:
        sys.path[:0] = [str(_p)]

GRAMMAR_PREFIX = "grammar:"
DEFAULT_INSTRUMENTS = ("AAA", "BBB", "CCC")


def _universe() -> tuple[str, ...]:
    """Universo determinista: CSV de ``AUTO_ORCHESTRATOR_INSTRUMENTS`` o por defecto."""
    raw = (os.getenv("AUTO_ORCHESTRATOR_INSTRUMENTS") or "").strip()
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    return parts or DEFAULT_INSTRUMENTS


def _run_off(instrument: str) -> tuple[tuple[object, ...], object]:
    from bolsa_api.background import auto_orchestrator_worker as w
    from bolsa_application.strategy_discovery_engine import (
        discover_for_instrument_with_summary,
    )

    return discover_for_instrument_with_summary(
        instrument_id=instrument,
        budget=w._discovery_budget(),
        grammar_budget=None,
        allocator=None,
        policy=None,
        emit_param_region=False,
    )


def _run_on(instrument: str) -> tuple[tuple[object, ...], object]:
    from bolsa_api.background import auto_orchestrator_worker as w
    from bolsa_application.strategy_discovery_engine import (
        discover_for_instrument_with_summary,
    )

    budget = w._discovery_budget()
    grammar_budget = w._grammar_budget(budget)
    return discover_for_instrument_with_summary(
        instrument_id=instrument,
        budget=budget,
        grammar_budget=grammar_budget,
        allocator=w._discovery_allocator(None),
        policy=w._grammar_policy(),
        emit_param_region=False,
    )


def _families(candidates: tuple[object, ...]) -> list[str]:
    return [str(getattr(c, "strategy_family", "")) for c in candidates]


def _preset_keys(candidates: tuple[object, ...], prefix: str = GRAMMAR_PREFIX) -> list[str]:
    keys = []
    for candidate in candidates:
        family = str(getattr(candidate, "strategy_family", ""))
        key = getattr(candidate, "preset_key", None)
        if family.startswith(prefix) and key:
            keys.append(str(key))
    return keys


def run_deterministic() -> int:
    """Compara ON vs OFF y emite el informe de procedencia. Devuelve exit 0/1."""
    from bolsa_api.background import auto_orchestrator_worker as w

    print("=== report_grammar_rollout (determinista, ON vs OFF) ===")
    budget = w._discovery_budget()
    print(
        f"budget: max_trials_total={budget.max_trials_total} "
        f"max_per_family={budget.max_per_family} "
        f"max_candidates={budget.max_candidates}"
    )
    print(f"policy efectiva: {w._grammar_policy_label(w._grammar_policy())}")

    failures: list[str] = []
    universe = _universe()

    header = (
        f"{'instrument':<12} {'cat_off':>8} {'cat_on':>8} {'grammar':>8} "
        f"{'total_on':>9} {'cap_g':>6} {'caps_ok':>8}"
    )
    print(header)
    print("-" * len(header))

    total_off = 0
    total_on = 0
    total_catalog_on = 0
    total_grammar_on = 0
    grammar_preset_counts: dict[str, int] = {}

    for instrument in universe:
        off_candidates, off_summary = _run_off(instrument)
        on_candidates, on_summary = _run_on(instrument)

        cat_off = int(getattr(off_summary, "catalog_candidates", 0))
        cat_on = int(getattr(on_summary, "catalog_candidates", 0))
        grammar_on = int(getattr(on_summary, "grammar_candidates", 0))
        total_on_i = int(getattr(on_summary, "total_candidates", 0))
        cap_g = getattr(on_summary, "grammar_cap", None)

        # Invariante 1: con gramática OFF no hay candidatas gramaticales y el total
        # ES el catálogo.
        if getattr(off_summary, "grammar_enabled", None) is not False:
            failures.append(f"{instrument}: OFF no reporta grammar_enabled=False")
        if int(getattr(off_summary, "grammar_candidates", 0)) != 0:
            failures.append(f"{instrument}: OFF emite candidatas gramaticales")
        if cat_off != len(off_candidates) or cat_off != int(
            getattr(off_summary, "total_candidates", -1)
        ):
            failures.append(f"{instrument}: OFF total != catálogo != len(candidates)")

        # Invariante 2: la gramática es ADITIVA — el catálogo OFF sobrevive como prefijo.
        off_families = _families(off_candidates)
        on_families = _families(on_candidates)
        catalog_on_prefix = [
            f for f in on_families if not f.startswith(GRAMMAR_PREFIX)
        ]
        if catalog_on_prefix != off_families[: len(catalog_on_prefix)]:
            failures.append(f"{instrument}: el catálogo ON no conserva el prefijo OFF")

        # Invariante 3: cuadre de procedencia y techo global.
        if cat_on + grammar_on != total_on_i or total_on_i != len(on_candidates):
            failures.append(
                f"{instrument}: catálogo+gramática != total "
                f"({cat_on}+{grammar_on} != {total_on_i} != {len(on_candidates)})"
            )
        if total_on_i > w._discovery_budget().max_candidates:
            failures.append(f"{instrument}: total ON excede max_candidates")

        # Invariante 4: toda candidata gramatical declara presetKey con prefijo.
        for candidate in on_candidates:
            family = str(getattr(candidate, "strategy_family", ""))
            if family.startswith(GRAMMAR_PREFIX):
                key = getattr(candidate, "preset_key", None)
                if not key or not str(key).startswith("grammar_"):
                    failures.append(f"{instrument}: candidata gramatical sin presetKey")

        # Invariante 5: determinismo (misma llamada ⇒ mismas candidatas).
        on_again, _ = _run_on(instrument)
        if [c.id for c in on_candidates] != [c.id for c in on_again]:
            failures.append(f"{instrument}: emisión ON no determinista")

        for key in _preset_keys(on_candidates):
            grammar_preset_counts[key] = grammar_preset_counts.get(key, 0) + 1
        total_off += cat_off
        total_on += total_on_i
        total_catalog_on += cat_on
        total_grammar_on += grammar_on

        caps_ok = "OK"
        print(
            f"{instrument:<12} {cat_off:>8} {cat_on:>8} {grammar_on:>8} "
            f"{total_on_i:>9} {str(cap_g):>6} {caps_ok:>8}"
        )

    print("-" * len(header))
    print(
        f"TOTAL        {total_off:>8} {total_catalog_on:>8} {total_grammar_on:>8} "
        f"{total_on:>9}"
    )
    print()
    print(f"procedencia: catálogo={total_catalog_on} gramática={total_grammar_on} total={total_on}")
    if total_catalog_on + total_grammar_on != total_on:
        failures.append("TOTAL: catálogo + gramática != total")
    distinct_keys = len(grammar_preset_counts)
    emitted_keys = sum(grammar_preset_counts.values())
    print(f"presetKey gramaticales emitidos (distintos={distinct_keys}, total={emitted_keys}):")
    for key, count in grammar_preset_counts.items():
        print(f"  - {key} x{count}")

    if failures:
        print()
        print(f"FAIL: {len(failures)} incumplimiento(s) de rollout")
        for message in failures:
            print(f"  FAIL {message}")
        return 1
    print()
    print("OK: rollout de la gramática coherente (OFF intacto, ON aditivo, cuadre y determinismo)")
    return 0


def _normalize_db_url(url: str) -> str:
    """Best-effort: convierte el dialecto async del proyecto al síncrono para leer."""
    return url.replace("postgresql+asyncpg", "postgresql+psycopg").replace(
        "postgresql+psycopg_async", "postgresql+psycopg"
    )


def run_db_best_effort() -> None:
    """Agrega la procedencia persistida (best-effort). Nunca cambia el exit code."""
    print()
    print("=== report_grammar_rollout (BD, best-effort) ===")
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        print("DB mode: omitido (DATABASE_URL no definido) — best-effort, no afecta al exit code")
        return
    try:
        from sqlalchemy import create_engine, func, select

        from bolsa_infrastructure.database.models.tables import (
            StrategyCandidateRow,
            StrategyEvaluationRow,
        )

        engine = create_engine(_normalize_db_url(url))
        try:
            with engine.connect() as conn:
                candidates_total = int(
                    conn.execute(
                        select(func.count()).select_from(StrategyCandidateRow)
                    ).scalar_one()
                )
                candidates_grammar = int(
                    conn.execute(
                        select(func.count())
                        .select_from(StrategyCandidateRow)
                        .where(StrategyCandidateRow.strategy_family.like(f"{GRAMMAR_PREFIX}%"))
                    ).scalar_one()
                )
                grammar_evaluated = int(
                    conn.execute(
                        select(func.count(func.distinct(StrategyCandidateRow.id)))
                        .select_from(StrategyCandidateRow)
                        .join(
                            StrategyEvaluationRow,
                            StrategyEvaluationRow.candidate_id == StrategyCandidateRow.id,
                        )
                        .where(StrategyCandidateRow.strategy_family.like(f"{GRAMMAR_PREFIX}%"))
                    ).scalar_one()
                )
        finally:
            engine.dispose()
    except Exception as exc:  # noqa: BLE001 — best-effort: se reporta y se ignora.
        print(f"DB mode: no disponible ({type(exc).__name__}: {exc}) — best-effort, no afecta al exit")
        return

    candidates_catalog = candidates_total - candidates_grammar
    print(f"candidatas persistidas: catálogo={candidates_catalog} gramática={candidates_grammar} "
          f"total={candidates_total}")
    print(f"candidatas gramaticales evaluadas (join strategy_evaluations): {grammar_evaluated}")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    exit_code = run_deterministic()
    if "--db" in args:
        run_db_best_effort()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
