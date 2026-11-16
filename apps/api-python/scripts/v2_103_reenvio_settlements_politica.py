"""V2.103 · Re-emisión de los settlements con la política de cuantización del dinero (ADR-051).

Qué hace
--------
El P&L publicado de un ciclo pasó a ser el DINERO que sus fills movieron
(``Σ signo · round6(q·p)``, ``applied_per_fill_v1``). Los cierres durables anteriores a ese
contrato conservan la aritmética histórica (``fifo_exact_v0``) y no se pueden comparar con el
ciclo vigente sin tolerar justo el hueco que el contrato eliminó.

Este CLI reconstruye los ciclos cerrados **con la misma función de dominio**
(``cycles_from_fills``, nunca un segundo FIFO), los clasifica y —solo con ``--apply``— **inserta**
un hecho nuevo de settlement con ``pnlPolicy`` y la clave de deduplicación versionada:

    vigente        ya tiene un settlement de la política vigente        ⇒ no-op
    solo_legacy    solo tiene el histórico o ninguno                    ⇒ INSERT del nuevo
    sin_settlement no tiene ningún cierre durable                       ⇒ INSERT del nuevo

Reglas duras
------------
* **Nunca ``UPDATE``, nunca ``DELETE``.** El hecho anterior queda superado, no reescrito. El
  spine es append-only (ADR-029) y la identidad nueva es lo que permite que ``ON CONFLICT DO
  NOTHING`` no descarte la reemisión.
* **``--dry-run`` por defecto.** Sin ``--apply`` no se escribe nada; el artefacto publica la
  clasificación y la cifra nueva frente a la histórica.
* **Reejecutar es un no-op** por la clave policy-aware: la segunda corrida no inserta nada.
* **Sin sello**: no ejecuta ``window:pin``, ``window:freeze`` ni crea tag. ``AUTO`` sigue OFF.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_103_reenvio_settlements_politica.py \\
        --account-id <cuenta> --json

    # apply explícito (solo INSERT):
    uv run --no-sync python apps/api-python/scripts/v2_103_reenvio_settlements_politica.py \\
        --account-id <cuenta> --apply --out docs/engineering/evidence/.../apply.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import pathlib
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

logger = logging.getLogger("v2_103_reenvio_settlements_politica")

_PHASE = "V2.103 CONTRATO DINERO DEL CICLO"
_BUMP = "2.11.194-beta"

CLASS_VIGENTE = "vigente"
CLASS_SOLO_LEGACY = "solo_legacy"
CLASS_SIN_SETTLEMENT = "sin_settlement"

#: Tope de ciclos que el CLI revisa por corrida (la reemisión es una operación, no un export).
_MAX_CYCLES = 5_000


def _dec(value: Any) -> Decimal | None:
    """Decimal exacto o ``None``: un valor ausente no se convierte en ``0``."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _text(value: Any) -> str | None:
    text = str(value).strip() if isinstance(value, str) else ""
    return text or None


def _fmt(value: Decimal | None) -> str | None:
    """Decimal sin notación científica (``0.00000072``, no ``7.2E-7``) y sin perder dígitos.

    El artefacto es evidencia: una cifra en exponente se lee mal y se copia peor. No se
    cuantiza aquí —la escala la fija el ledger— para no esconder decimales del histórico.
    """
    if value is None:
        return None
    return format(value, "f")


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return (value if value.tzinfo is not None else value.replace(tzinfo=UTC)).isoformat()
    return _text(value)


def classify_cycle(cycle_id: str, settlements: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """(PURA) clasificación de UN ciclo frente a los cierres durables que declaran su id.

    ``vigente`` si ya existe un hecho de la política actual; ``solo_legacy`` si solo hay hechos
    históricos (o ninguno de la política); ``sin_settlement`` si no hay ninguno. Un hecho sin
    ``pnlPolicy`` es histórico —lo que de verdad hizo—, no un hueco.
    """
    from bolsa_application.cycle_pnl_policy import CYCLE_PNL_POLICY_LEGACY, is_current_policy

    rows = [
        row
        for row in settlements
        if _text(row.get("cycleId")) == cycle_id and isinstance(row, Mapping)
    ]
    current = [row for row in rows if is_current_policy(row.get("pnlPolicy"))]
    legacy = [row for row in rows if not is_current_policy(row.get("pnlPolicy"))]
    if current:
        classification = CLASS_VIGENTE
    elif legacy:
        classification = CLASS_SOLO_LEGACY
    else:
        classification = CLASS_SIN_SETTLEMENT
    return {
        "classification": classification,
        "current": current,
        "legacy": legacy,
        # El histórico es la referencia con la que se compara la reemisión; si no hay histórico
        # (ciclo nunca liquidado), se usa el vigente como referencia y el delta será cero.
        "previous": (legacy[-1] if legacy else (current[-1] if current else None)),
        "previousPolicy": (
            None if not rows else ("applied_per_fill_v1" if current else CYCLE_PNL_POLICY_LEGACY)
        ),
        "duplicateCurrent": len(current) > 1,
        "duplicateLegacy": len(legacy) > 1,
    }


def build_plan(
    *, cycles: Sequence[Mapping[str, Any]], settlements: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """(PURA) plan de reemisión: qué ciclos cambiarían y con qué cifra.

    ``cycles`` son filas de ``cycles_from_fills`` ya cerradas (con ``cycleId`` y ``pnl``). No se
    recalcula nada aquí: el dinero publicado y el exacto vienen del MISMO productor.
    """
    rows: list[dict[str, Any]] = []
    counts = {
        CLASS_VIGENTE: 0,
        CLASS_SOLO_LEGACY: 0,
        CLASS_SIN_SETTLEMENT: 0,
        "duplicateCurrent": 0,
        "unmeasurable": 0,
    }
    for cycle in cycles:
        cycle_id = _text(cycle.get("cycleId"))
        if cycle_id is None:
            counts["unmeasurable"] += 1
            continue
        state = classify_cycle(cycle_id, settlements)
        classification = state["classification"]
        counts[classification] += 1
        if state["duplicateCurrent"]:
            counts["duplicateCurrent"] += 1
        previous = state["previous"]
        previous_pnl = _dec((previous or {}).get("pnl"))
        new_pnl = _dec(cycle.get("pnl"))
        new_exact = _dec(cycle.get("pnlExact"))
        delta = None if previous_pnl is None or new_pnl is None else new_pnl - previous_pnl
        rows.append(
            {
                "cycleId": cycle_id,
                "classification": classification,
                "previousSettlementId": (previous or {}).get("settlementId"),
                "previousPolicy": state["previousPolicy"],
                "previousPnl": _fmt(previous_pnl),
                "newPnl": _fmt(new_pnl),
                "newPnlExact": _fmt(new_exact),
                "delta": _fmt(delta),
                "needsReemission": classification != CLASS_VIGENTE,
                "duplicateCurrent": state["duplicateCurrent"],
            }
        )
    counts["total"] = len(rows)
    counts["toReemit"] = counts[CLASS_SOLO_LEGACY] + counts[CLASS_SIN_SETTLEMENT]
    counts["maxAbsDelta"] = _max_abs_delta(rows)
    return {"counts": counts, "rows": rows}


def _max_abs_delta(rows: Sequence[Mapping[str, Any]]) -> str | None:
    values = [_dec(row.get("delta")) for row in rows]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return _fmt(max(present, key=lambda value: abs(value)))


# ── Lecturas read-only del material durable ─────────────────────────────────────────


async def _load_closed_cycles(session: Any, *, account_id: str | None, limit: int) -> list[str]:
    """Ciclos con fills APLICADOS y ``cycle_id``, más reciente primero (sin depender de reservas)."""
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        SimFillFinanceContextRow,
    )
    from sqlalchemy import desc, func, select

    last_at = func.max(SimFillFinanceContextRow.created_at).label("last_at")
    stmt = (
        select(SimFillFinanceContextRow.cycle_id, last_at)
        .join(
            ExecutionEventRow,
            ExecutionEventRow.execution_id == SimFillFinanceContextRow.execution_id,
        )
        .where(
            SimFillFinanceContextRow.cycle_id.is_not(None),
            ExecutionEventRow.status == "APPLIED",
        )
        .group_by(SimFillFinanceContextRow.cycle_id)
        .order_by(desc(last_at))
        .limit(limit)
    )
    if account_id is not None:
        stmt = stmt.where(SimFillFinanceContextRow.account_id == account_id)
    rows = (await session.execute(stmt)).all()
    return [str(cycle).strip() for cycle, _last_at in rows if _text(cycle)]


async def _load_cycle_fills(session: Any, *, account_id: str | None, cycle_id: str) -> list[Any]:
    """Fills APLICADOS del ciclo, en orden durable, como objetos de dominio."""
    from bolsa_application.sim_durable_store import SimFillFinanceContext
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        SimFillFinanceContextRow,
    )
    from sqlalchemy import select

    stmt = (
        select(SimFillFinanceContextRow)
        .join(
            ExecutionEventRow,
            ExecutionEventRow.execution_id == SimFillFinanceContextRow.execution_id,
        )
        .where(
            SimFillFinanceContextRow.cycle_id == cycle_id,
            ExecutionEventRow.status == "APPLIED",
        )
        .order_by(
            SimFillFinanceContextRow.created_at.asc(),
            SimFillFinanceContextRow.execution_id.asc(),
        )
    )
    if account_id is not None:
        stmt = stmt.where(SimFillFinanceContextRow.account_id == account_id)
    rows = (await session.execute(stmt)).scalars().all()
    fills: list[Any] = []
    for row in rows:
        try:
            fills.append(
                SimFillFinanceContext(
                    execution_id=row.execution_id,
                    instrument_id=row.instrument_id,
                    side=str(row.side).strip().lower(),
                    quantity=Decimal(str(row.quantity)),
                    price=Decimal(str(row.price)),
                    reference_mid=(
                        None if row.reference_mid is None else Decimal(str(row.reference_mid))
                    ),
                    price_source=row.price_source,
                    account_id=row.account_id,
                    venue=row.venue,
                    idempotency_key=row.idempotency_key,
                    strategy_version_id=row.strategy_version_id,
                    cycle_id=row.cycle_id,
                    created_at=row.created_at,
                )
            )
        except ValueError:
            logger.warning("fill inválido en el ciclo %s: %s", cycle_id, row.execution_id)
    return fills


async def _load_settlements(session: Any, *, account_id: str | None) -> list[dict[str, Any]]:
    """Payloads de los cierres durables de la cuenta (históricos incluidos)."""
    from bolsa_application.auto_operational_monitor import AUTO_CYCLE_SETTLEMENT_EVENT
    from bolsa_infrastructure.database.models.tables import DecisionJournalEntryRow
    from sqlalchemy import select

    stmt = select(DecisionJournalEntryRow.payload).where(
        DecisionJournalEntryRow.event_type == AUTO_CYCLE_SETTLEMENT_EVENT
    )
    if account_id is not None:
        stmt = stmt.where(DecisionJournalEntryRow.account_id == account_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [dict(payload) for payload in rows if isinstance(payload, dict)]


# ── Reemisión (solo INSERT) ────────────────────────────────────────────────────────


async def _reemit(
    session: Any,
    *,
    account_id: str,
    engine_id: str,
    actor: str,
    plan: Mapping[str, Any],
    settlements: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    """Inserta el hecho vigente de cada ciclo que solo tiene el histórico.

    Nunca actualiza ni borra. El ``append`` del repositorio es idempotente por ``dedupe_key``,
    así que una segunda corrida no crea un segundo hecho.
    """
    from bolsa_application.auto_operational_audit import (
        build_cycle_settlement_entry,
        durable_fact_dedupe_key,
    )
    from bolsa_application.cycle_pnl_policy import CYCLE_PNL_POLICY

    from bolsa_api.background.auto_worker_shared import settlement_snapshot_from_fills

    inserted = skipped = unmeasurable = 0
    engines: set[str] = set()
    for row in plan.get("rows", ()):
        if not row.get("needsReemission"):
            continue
        cycle_id = str(row["cycleId"])
        fills = await _load_cycle_fills(session, account_id=account_id, cycle_id=cycle_id)
        snapshot = settlement_snapshot_from_fills(fills)
        if snapshot is None:
            unmeasurable += 1
            logger.warning("ciclo %s sin fills reconstruibles: no se reemite", cycle_id)
            continue
        from bolsa_application.auto_self_evaluation_feed import cycles_from_fills

        cycle = next(
            (item for item in cycles_from_fills(fills) if _text(item.get("cycleId")) == cycle_id),
            None,
        )
        if cycle is None:
            unmeasurable += 1
            logger.warning("ciclo %s no cerrado según el FIFO: no se reemite", cycle_id)
            continue
        state = classify_cycle(cycle_id, settlements)
        previous = state["previous"] or {}
        # El MOTOR es parte de la identidad del hecho: se hereda del histórico (es el mismo
        # settlement, bajo otra aritmética). Inventar el default ``auto-sim`` cambiaría la
        # clave y el lector del worker —que filtra por motor— no vería el hecho reemitido.
        row_engine = _text(previous.get("engineId")) or engine_id
        engines.add(row_engine)
        entry = build_cycle_settlement_entry(
            settlement_id=f"settle-{cycle_id}-applied-per-fill-v1",
            instrument_id=snapshot["instrument_id"],
            side="sell",
            closed_qty=snapshot["closed_qty"],
            pnl=cycle.get("pnl"),
            settled_at=_iso(previous.get("settledAt")) or _iso(cycle.get("closedAt")),
            # El motivo de salida NO se inventa: se conserva el que el hecho histórico declaró.
            exit_reason=_text(previous.get("exitReason")),
            price_source=snapshot["price_source"],
            cycle_id=cycle_id,
            actor=actor,
            as_of=_iso(datetime.now(UTC)),
            account_id=account_id,
            structural=bool(previous.get("structural")),
            pnl_policy=CYCLE_PNL_POLICY,
        )
        if entry is None:  # pragma: no cover — sin ciclo el builder ya no llega aquí
            unmeasurable += 1
            continue
        # Misma identidad que sella el sumidero M2: ``engineId`` en el payload y la clave
        # determinista policy-aware. Sin esto la reemisión sería un INSERT plano (duplicado a
        # la segunda corrida) y el ``--apply`` no sería idempotente.
        payload = dict(entry.payload or {})
        if not str(payload.get("engineId") or "").strip():
            payload["engineId"] = row_engine
            entry = replace(entry, payload=payload)
        if not getattr(entry, "dedupe_key", None):
            key = durable_fact_dedupe_key(
                event_type=entry.event_type,
                account_id=entry.account_id,
                engine_id=row_engine,
                cycle_id=payload.get("cycleId"),
                pnl_policy=payload.get("pnlPolicy"),
            )
            if key is not None:
                entry = replace(entry, dedupe_key=key)
        if await _append_once(session, entry):
            inserted += 1
        else:
            skipped += 1
    await session.commit()
    return {
        "inserted": inserted,
        "skipped": skipped,
        "unmeasurable": unmeasurable,
        "engineFallback": engine_id,
        "engines": sorted(engines),
    }


async def _append_once(session: Any, entry: Any) -> bool:
    """``INSERT ... ON CONFLICT DO NOTHING`` y devuelve si la FILA se creó.

    No se usa el repositorio porque su ``append`` devuelve la entrada aunque el conflicto la
    descarte, y la evidencia necesita distinguir "reemitido" de "ya estaba" con el ``rowcount``
    del propio INSERT (si no, una segunda corrida se reportaría como si hubiera escrito).
    """
    from bolsa_infrastructure.database.models.tables import DecisionJournalEntryRow
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    statement = (
        pg_insert(DecisionJournalEntryRow)
        .values(
            id=entry.id,
            decision_id=entry.decision_id,
            session_id=entry.session_id,
            account_id=entry.account_id,
            instrument_id=entry.instrument_id,
            event_type=entry.event_type,
            actor=entry.actor,
            payload=entry.payload,
            created_at=_instant(entry.created_at),
            dedupe_key=entry.dedupe_key,
        )
        .on_conflict_do_nothing(
            index_elements=[DecisionJournalEntryRow.dedupe_key],
            index_where=DecisionJournalEntryRow.dedupe_key.is_not(None),
        )
    )
    result = await session.execute(statement)
    return bool(getattr(result, "rowcount", 0))


def _instant(value: Any) -> datetime:
    """Instante del hecho: el que declara el builder o, si no es parseable, ``now``."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now(UTC)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.auto_self_evaluation_feed import cycles_from_fills
    from bolsa_application.cycle_pnl_policy import CYCLE_PNL_POLICY
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    account_id = _text(args.account_id)
    if account_id is None:
        raise RuntimeError("la reemisión exige --account-id: es una operación por cuenta")
    engine_id = _text(args.engine_id) or "auto-sim"
    actor = _text(args.actor) or engine_id

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    as_of = datetime.now(UTC)

    try:
        async with factory() as session:
            cycle_ids = await _load_closed_cycles(
                session, account_id=account_id, limit=int(args.limit)
            )
            if args.cycle_id:
                wanted = str(args.cycle_id).strip()
                cycle_ids = [cycle for cycle in cycle_ids if cycle == wanted]
            settlements = await _load_settlements(session, account_id=account_id)

            cycles: list[dict[str, Any]] = []
            unmeasurable = 0
            for cycle_id in cycle_ids:
                fills = await _load_cycle_fills(session, account_id=account_id, cycle_id=cycle_id)
                row = next(
                    (
                        item
                        for item in cycles_from_fills(fills)
                        if _text(item.get("cycleId")) == cycle_id
                    ),
                    None,
                )
                if row is None:
                    unmeasurable += 1
                    continue
                cycles.append(row)

            plan = build_plan(cycles=cycles, settlements=settlements)
            plan["counts"]["unmeasurable"] += unmeasurable

            applied: dict[str, Any] | None = None
            if args.apply:
                applied = await _reemit(
                    session,
                    account_id=account_id,
                    engine_id=engine_id,
                    actor=actor,
                    plan=plan,
                    settlements=settlements,
                )
                # Relectura DESPUÉS del apply: cuántos ciclos quedan con la política vigente.
                after = await _load_settlements(session, account_id=account_id)
                after_plan = build_plan(cycles=cycles, settlements=after)
                applied["afterCounts"] = after_plan["counts"]
                applied["currentPolicyTotal"] = _count_current(after, account_id=account_id)
    finally:
        await engine.dispose()

    return {
        "meta": {
            "phase": _PHASE,
            "bump": _BUMP,
            "policy": CYCLE_PNL_POLICY,
            "accountId": account_id,
            "engineFallback": engine_id,
            "engines": (applied or {}).get("engines") or [],
            "asOf": as_of.isoformat(),
            "mode": "apply" if args.apply else "dry-run",
            "readOnly": not bool(args.apply),
            "sealed": False,
        },
        "counts": plan["counts"],
        "rows": _sorted_rows(plan["rows"]),
        "applied": applied,
        "limits": [
            "Solo INSERT: nunca UPDATE, DELETE ni sello.",
            "El PnL sale de cycles_from_fills (un solo FIFO); no hay un segundo cálculo.",
            "Un ciclo sin fills APLICADOS reconstruibles se declara, no se inventa.",
            "El motivo de salida solo se copia del hecho histórico; ausente ⇒ None.",
            "El motor se hereda del hecho histórico (identidad del settlement); 'auto-sim' es solo el respaldo declarado.",
        ],
    }


def _count_current(settlements: Sequence[Mapping[str, Any]], *, account_id: str | None) -> int:
    """Ciclos DISTINTOS con un hecho de la política vigente en la lectura dada."""
    from bolsa_application.cycle_pnl_policy import is_current_policy

    cycles: set[str] = set()
    for payload in settlements:
        if not isinstance(payload, Mapping):
            continue
        if account_id is not None and payload.get("accountId") not in (None, account_id):
            continue
        if not is_current_policy(payload.get("pnlPolicy")):
            continue
        cycle = _text(payload.get("cycleId"))
        if cycle is not None:
            cycles.add(cycle)
    return len(cycles)


def _sorted_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: str(row.get("cycleId") or ""))


def _atomic_write(path: pathlib.Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = pathlib.Path(handle.name)
    temp_path.replace(path)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reemite los settlements con la política de dinero vigente (ADR-051)"
    )
    parser.add_argument("--account-id", default="", help="Cuenta a reemitir (obligatoria)")
    parser.add_argument(
        "--engine-id",
        default="auto-sim",
        help=(
            "Motor de respaldo para un hecho histórico que no lo declare; si lo declara, "
            "manda el del hecho (el motor forma parte de su identidad)."
        ),
    )
    parser.add_argument("--actor", default="", help="Actor del hecho (default: engine-id)")
    parser.add_argument(
        "--cycle-id", default="", help="Limita la corrida a UN ciclo (para verificar)"
    )
    parser.add_argument(
        "--limit", type=int, default=500, help="Máximo de ciclos revisados (default 500)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Escribe el hecho nuevo (solo INSERT). Sin esta bandera es dry-run.",
    )
    parser.add_argument("--out", default="", help="Ruta del artefacto JSON")
    parser.add_argument("--json", action="store_true", help="Imprime el artefacto por stdout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args(argv)
    if args.limit <= 0 or args.limit > _MAX_CYCLES:
        logger.error("--limit debe estar en (0, %s]", _MAX_CYCLES)
        return 2
    if sys.platform == "win32":  # pragma: no cover — quirk del loop psycopg en la máquina dev.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        artifact = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 — CLI de evidencia: fallo explícito
        logger.error("reemisión de settlements falló: %s", exc)
        return 1

    out = (args.out or "").strip()
    if out:
        _atomic_write(pathlib.Path(out), artifact)
    if args.json or not out:
        print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
