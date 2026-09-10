"""V2.22 / A9 (M1+M2) — Sell-side simulado + liquidación por ExecutionEvent.

El SimulatedBroker (V2.21/A8·M3) ya modela el *schedule* determinista de fills
para ``side in {"buy","sell"}`` (``simulated_fill_schedule``) y produce
``SimulatedFill`` con identidad financiera ``execution_id =
venue_order_id#fill_seq`` (delta per fill_seq). Lo que faltaba para el bucle
autónomo era:

* un camino **sell-side** de primera clase (simetría real con el buy), y
* la **liquidación** duradera de un ``SimulatedOrderResult`` — sea buy o sell —
  convertido en trazas ``execution_events`` idempotentes por ``execution_id``,
  materializadas con ``apply_execution_financial_once`` + un ``apply_finance``
  (``ExecuteTrade``) y **nunca** con aritmética propia inventada.

Este módulo añade SOLO esa capa faltante, con la misma semántica del recovery
financiero (``recovery_apply.py``): cada fill → un ``execution_id`` → el primer
apply materializa; un crash/reaper/relaunch NO duplica (invariante C3).

Seguridad P0 (AUTO → SIMULATED ONLY): el venue de liquidación lo aporta el
caller y aquí se normaliza contra {paper, simulated}; cualquier alias
live/xtb/real/broker_live => bloqueo (tupla vacía) — nunca se abre una vía REAL.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from bolsa_application.execution_event import (
    ExecutionEvent,
    ExecutionEventStore,
    apply_execution_financial_once,
)
from bolsa_application.simulated_broker import (
    SimulatedOrderResult,
    simulated_fill_schedule,
)

# Venues que el camino AUTO puede liquidar (nunca LIVE). Espeja el contrato del
# decision_contract (ALLOWED_AUTO_VENUES) sin importar aquel módulo de contrato IA,
# para no acoplar la liquidación a los gates de propuesta.
AUTO_SETTLE_VENUES: frozenset[str] = frozenset({"paper", "simulated"})


def _identity_token(value: object, *, fallback: str = "na") -> str:
    """Token estable y seguro para la identidad de orden (sin separadores/espacios)."""
    raw = str(value or "").strip()
    if not raw:
        return fallback
    token = re.sub(r"[^A-Za-z0-9]", "", raw)
    return token[:64] or fallback


def auto_venue_order_id(
    *,
    engine_id: object,
    account_id: object,
    instrument_id: str,
    side: str,
    logical_order_id: object,
) -> str:
    """V2.24 / A9.1 (P1-03) — identidad de orden AUTO con namespace global único.

    Antes: ``sim-{side}-{instrument}-{seed}`` con ``seed`` derivado solo de minuto y
    símbolo ⇒ dos cuentas (o dos engines) podían producir el MISMO ``venue_order_id``
    y, por tanto, el mismo ``execution_id`` (``venue_order_id#fill_seq``). Como la
    idempotencia financiera y la PK de contexto son globales por ``execution_id``,
    una cuenta podía "absorber" la ejecución de otra.

    Ahora la identidad incluye ``engine_id`` + ``account_id`` + un
    ``logical_order_id`` único por INTENCIÓN: una colisión entre cuentas es
    imposible por construcción.
    """
    raw_side = str(side or "").strip().lower()
    return (
        f"sim-{_identity_token(engine_id, fallback='engine')}"
        f"-{_identity_token(account_id, fallback='acct')}"
        f"-{raw_side}"
        f"-{_identity_token(instrument_id, fallback='inst')}"
        f"-{_identity_token(logical_order_id, fallback='ord')}"
    )


def normalized_auto_venue(venue: str) -> str | None:
    """Normaliza un venue de liquidación AUTO.

    ``"paper"``/``"simulated"`` pasan (y sinónimos paper/dry->paper, sim->simulated);
    cualquier venue live/xtb/real/broker_live/otro => ``None`` (bloqueo fail-closed).
    """
    v = str(venue or "").strip().lower()
    if v in {"sim", "simulated"}:
        return "simulated"
    if v in {"paper", "dry", "paper_auto"}:
        return "paper"
    return v if v in AUTO_SETTLE_VENUES else None


def simulated_execution_candidates(
    result: SimulatedOrderResult,
    *,
    instrument_id: str,
    account_id: str | None,
    venue: str,
    order_id: str | None = None,
) -> tuple[ExecutionEvent, ...]:
    """(PURA) convierte un ``SimulatedOrderResult`` en trazas ``ExecutionEvent``.

    Construye UN evento por fill confirmado en el resultado con ``qty`` = delta de
    ESE ``fill_seq`` (P2-03: 40+30+30=100, nunca acumulado) e identidad
    ``execution_id = f"{venue_order_id}#{fill_seq}"``.

    Fail-closed: sin fills (rejected/timeout/unknown) o venue no-AUTO-allowed →
    tupla vacía (cero dinero).
    """
    vid = (result.venue_order_id or "").strip()
    if not vid:
        return ()
    venue_id = normalized_auto_venue(venue)
    if venue_id is None:
        return ()
    oid = (order_id or "").strip() or f"sim-{vid}"
    events: list[ExecutionEvent] = []
    for f in result.fills:
        qty = _to_event_qty(f.qty_delta)
        if qty <= 0:
            continue
        events.append(
            ExecutionEvent(
                execution_id=f.execution_id,
                order_id=oid,
                venue=venue_id.upper(),
                qty=qty,
                account_id=account_id,
                venue_order_id=vid,
                fill_seq=f.fill_seq,
            )
        )
    return tuple(events)


def simulated_idempotency_key(execution_id: str) -> str:
    """Key financiera estable por fill simulado (no-doble M4 por ExecuteTrade).

    Misma regla que ``recovery_idempotency_key`` (rango estable sin whitespace),
    prefijo ``sim-fin-`` para no colisionar con el recovery. Estable por
    ``execution_id`` → un crash/reintento del mismo fill reutiliza la key y
    ``ExecuteTrade`` no duplica.
    """
    slug = re.sub(r"[^A-Za-z0-9_]", "-", (execution_id or "").strip())
    slug = slug.strip("-")
    if not slug:
        slug = "unknown"
    return f"sim-fin-{slug[:120]}"[-128:]


def _to_event_qty(qty: Decimal | None) -> Decimal:
    """Decimal(6dp) >= 0; guarda frente a NaN/negativos/None."""
    from decimal import ROUND_HALF_UP

    if qty is None:
        return Decimal("0")
    raw = Decimal(str(qty))
    if raw.is_nan() or raw <= 0:
        return Decimal("0")
    return raw.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


async def apply_simulated_order_once(
    store: ExecutionEventStore,
    *,
    result: SimulatedOrderResult,
    instrument_id: str,
    account_id: str | None,
    venue: str,
    side: str | None = None,
    context_store: Any | None = None,
    apply_finance: Any | None = None,
    owner: str = "auto-sim",
    retryable_on_ineffective: bool = True,
    strategy_version_id: str | None = None,
) -> dict[str, str]:
    """Liquida un order simulado (buy o sell) en trazas idempotentes una sola vez.

    Para cada ``execution_id`` materializable construye el ``ExecutionEvent`` y lo
    aplica con ``apply_execution_financial_once`` (CAPTURED→APPLYING→APPLIED, con
    fencing). Sin ``apply_finance`` (default) la traza queda capturada pero NO se
    materializa dinero (fail-closed, = a un recovery sin go).

    V2.23/A9 (Bloque 5, P1-05): con ``context_store`` (y ``side``) se persiste, ANTES
    de mover dinero, el contexto financiero durable de cada fill
    (``execution_id → instrument_id/side/qty/price/account/venue``). Así un resolver
    posterior —incluido uno tras crash— reconstruye la finance sin memoria del
    ``SimulatedOrderResult``.

    Devuelve un mapa ``{execution_id: DurableApplyOutcome}`` sobre las trazas.
    """
    events = simulated_execution_candidates(
        result,
        instrument_id=instrument_id,
        account_id=account_id,
        venue=venue,
    )
    # Durable-first: contexto financiero por fill antes de cualquier materialización.
    if context_store is not None and side is not None:
        from bolsa_application.sim_finance_context import persist_fill_finance_context

        await persist_fill_finance_context(
            context_store,
            result,
            instrument_id=instrument_id,
            side=side,
            account_id=account_id,
            venue=venue,
            strategy_version_id=strategy_version_id,
        )
    outcomes: dict[str, str] = {}
    for ev in events:
        outcome = await apply_execution_financial_once(
            store,
            execution=ev,
            apply_finance=apply_finance,  # type: ignore[arg-type]
            owner=owner,
            retryable_on_ineffective=retryable_on_ineffective,
        )
        outcomes[ev.execution_id] = outcome
    return outcomes


async def submit_simulated_order(
    store: ExecutionEventStore,
    *,
    instrument_id: str,
    side: str,
    quantity: Decimal,
    account_id: str | None,
    venue: str,
    seed: int,
    base_mid: float = 100.0,
    fill_chunks: int = 3,
    order_id: str | None = None,
    engine_id: str | None = None,
    logical_order_id: str | None = None,
    venue_order_id: str | None = None,
    apply_finance: Any | None = None,
    context_store: Any | None = None,
    owner: str = "auto-sim",
    strategy_version_id: str | None = None,
) -> tuple[SimulatedOrderResult, dict[str, str]]:
    """Submit determinista simulado (buy/sell) + liquidación idempotente.

    Componibilidad: un único entry point para que cualquier worker/tick AUTO llene
    un order de mercado simulado y lo materialice durablemente.

    1. ``simulated_fill_schedule`` produce el schedule determinista (seed+ctx).
    2. ``apply_simulated_order_once`` captura/materializa por ``execution_id``.

    V2.24 / A9.1 (P1-03): la identidad de orden se namespacea por
    ``engine_id`` + ``account_id`` + ``logical_order_id`` (``auto_venue_order_id``)
    salvo que el caller aporte un ``venue_order_id`` explícito. Así dos cuentas no
    pueden colisionar en el mismo ``execution_id``.

    Raise ``ValueError`` si ``side`` no es buy/sell.
    """
    raw_side = str(side or "").strip().lower()
    if raw_side not in {"buy", "sell"}:
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")

    vid = (
        str(venue_order_id).strip()
        if venue_order_id is not None and str(venue_order_id).strip()
        else auto_venue_order_id(
            engine_id=engine_id or "engine",
            account_id=account_id,
            instrument_id=instrument_id,
            side=raw_side,
            logical_order_id=logical_order_id or f"{seed}-{order_id or ''}",
        )
    )

    venue_id = normalized_auto_venue(venue)
    if venue_id is None:
        # Bloqueo durísimo: venue AUTO no permitido; devolvemos order sin fills ni
        # trazas por si el caller quiere observar. No se fabrica nada.
        blocked = SimulatedOrderResult(
            venue_order_id=vid,
            status="rejected",
            reason="venue_not_auto_allowed",
            scheduled_gap_seconds=0.0,
            fills=(),
            queue_event="noise_unavailable",
            cumulative_filled_quantity=Decimal("0"),
        )
        return blocked, {}

    result = simulated_fill_schedule(
        instrument_id=instrument_id,
        side=raw_side,
        quantity=quantity,
        venue_order_id=vid,
        seed=seed,
        fill_chunks=fill_chunks,
        base_mid=base_mid,
    )
    outcomes = await apply_simulated_order_once(
        store,
        result=result,
        instrument_id=instrument_id,
        account_id=account_id,
        venue=venue_id,
        side=raw_side,
        context_store=context_store,
        apply_finance=apply_finance,
        owner=owner,
        strategy_version_id=strategy_version_id,
    )
    return result, outcomes
