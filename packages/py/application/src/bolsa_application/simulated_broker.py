"""V2.21 / A8 (M3) — SimulatedBroker virtual, determinista (sin broker externo).

Cero sell-side sim hoy: este módulo reproduce, EN SIMULACIÓN, el ciclo de truth de
una ORDER del venue (``LiveOrder`` FSM) sin depender de ningún bridge:

    submit → SUBMITTED → MARKET_SIMULATION (latencia) → PARTIAL_FILL(s) → FILL

Contrato de cantidad (V2.20 P2-03, `recovery_apply`): cada llenado parcial de una
misma orden produce su propio ``execution_id = f"{venue_order_id}#{fill_seq}"`` y su
``qty`` es el **DELTA de ESE fill_seq** — no un acumulado. Un parcial se reconstruye
sumando los deltas: ``40 + 30 + 30 = 100``. Expresamos el ``fill_schedule`` con esos
deltas, de modo que un consumidor (AUTO engine M4, recover, test) puede materializar
cada traza idempotente por fill_seq exactamente como si viniera del venue.

Determinismo: todo ruido (slippage, spread, latencias, colas noisy de
reject/timeout/unavailable/reconnect/duplicate/UNKNOWN) deriva de ``hashlib.sha256``
acoplado a un ``seed`` entero + contexto — NUNCA del RNG global. El mismo orden con
el mismo seed devuelve SIEMPRE el mismo resultado (tests de inmutabilidad).

Este componente es de lectura/planeo + un adapter de submit para la simulación; NO
abre ninguna vía real (M0 la mantiene doblemente bloqueada) ni escribe ledger por sí
solo (eso queda a capas idempotentes existentes por execution_id).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_DOWN, ROUND_HALF_UP, Decimal
from hashlib import sha256
from typing import Any, Literal

_QTY_SCALE = Decimal("0.000001")
_PRICE_SCALE = Decimal("0.0001")


def _qty(value: Any) -> Decimal:
    d = Decimal(str(value)) if not isinstance(value, Decimal) else value
    if d.is_nan() or d < 0:
        return Decimal("0")
    return d.quantize(_QTY_SCALE, rounding=ROUND_HALF_UP)


def _price(value: Any) -> Decimal:
    d = Decimal(str(value)) if not isinstance(value, Decimal) else value
    if d.is_nan() or d < 0:
        return Decimal("0")
    return d.quantize(_PRICE_SCALE, rounding=ROUND_HALF_UP)


def sim_hash_int(*parts: object) -> int:
    """Entero determinista ∈ [0, 1) derivado de seed+contexto (sha256, no RNG)."""
    blob = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(sha256(blob).digest()[:8], "big")


def sim_rand(seed: int, *context: object) -> float:
    """U(0,1) determinista para un (seed, contexto). Libre de estado global."""
    return sim_hash_int(seed, *context) / (2**64)


# Fases ruidosas de cola simuladas (close-loop de mercado) del audit §13.
SimQueueEvent = Literal[
    "ok",  # camino normal.
    "noise_latency",  # latencia extra de red/matching.
    "noise_reject",  # orden rechazada (sin fill).
    "noise_timeout",  # puente sin respuesta; fill queda UNKNOWN/no confirmado.
    "noise_market_closed",  # fuera de horario → reject/quedada abierta sin fill.
    "noise_unavailable",  # canal inaccesible de forma transitoria.
    "noise_reconnect",  # reconexión; la orden sigue activa.
    "noise_duplicate",  # confirmación duplicada del bridge (idempotencia despierta).
    "noise_unknown",  # clase desconocida → honest 'UNKNOWN' durable (na H4).
]

_QUEUE_CHANNEL: dict[str, tuple[float, SimQueueEvent]] = {
    # Umbral acumulado de ruido market microstructure determinista.
    "reject": (0.010, "noise_reject"),
    "timeout": (0.025, "noise_timeout"),
    "market_closed": (0.005, "noise_market_closed"),
    "unavailable": (0.012, "noise_unavailable"),
    "reconnect": (0.020, "noise_reconnect"),
    "duplicate": (0.015, "noise_duplicate"),
    "unknown": (0.004, "noise_unknown"),
}


def draw_queue_noise(seed: int, side: str, instrument_id: str) -> tuple[SimQueueEvent, float]:
    """Determina si esta orden topa con una cola noisy (y con qué latencia).

    Acumula umbrales de forma ordenada y determinista: si la U(0,1) cae en el canal
    correspondiente → evento noisy; si no, camino ``ok`` con su latencia base.
    """
    u = sim_rand(seed, instrument_id, side, "queue")
    acc = 0.0
    chosen: SimQueueEvent = "ok"
    for _key, (w, ev) in _QUEUE_CHANNEL.items():
        acc += w
        if u < acc:
            chosen = ev
            break
    if chosen == "ok":
        latency = 0.02 + 0.08 * u  # 20-100 ms base.
    elif chosen == "noise_latency":
        latency = 0.2 + 0.8 * u
    else:
        latency = 0.3 + 2.0 * u
    return chosen, round(latency, 4)


# Decisión de cuanto se llena en cada parcial (deltas que suman <= quantity).
@dataclass(frozen=True, slots=True)
class SimulatedFill:
    fill_seq: int
    qty_delta: Decimal  # delta DE ESTE fill_seq (P2-03): 40+30+30=100.
    price: Decimal
    occurred_after_seconds: float
    venue_order_id: str

    @property
    def execution_id(self) -> str:
        """Identidad financiera idempotente por fill (venue_order_id#fill_seq)."""
        return f"{self.venue_order_id}#{self.fill_seq}"


@dataclass(frozen=True, slots=True)
class SimulatedOrderResult:
    venue_order_id: str
    status: Literal["submitted", "partial", "filled", "rejected", "unknown"]
    reason: str | None
    scheduled_gap_seconds: float
    fills: tuple[SimulatedFill, ...]  # ordenados por fill_seq (deltas).
    queue_event: SimQueueEvent
    cumulative_filled_quantity: Decimal


# ── Vista por trades/fills que el venue confirmaría a lo largo del time-lapse ──

def simulated_fill_schedule(
    *,
    instrument_id: str,
    side: str,  # "buy" | "sell"
    quantity: Decimal,
    venue_order_id: str,
    seed: int,
    fill_chunks: int = 3,
    adverse_slippage_bps: int = 4,
    spread_bps: int = 6,
    base_mid: float = 100.0,
) -> SimulatedOrderResult:
    """Plan determinista de estado final que un broker REAL devolvería por consulta.

    * Si la cola noisy fuerza reject/timeout/market_closed → la orden NO se llena
      (0 delta), ``status`` refleja esa terminal y ``fills=()``.
    * Si hay camino ok/parciales: parte la cantidad en ``fill_chunks`` deltas
      (diminuiéndose lentamente bajo noise), suma = quantity (full fill) salvo un
      residual que TOPA en una cola noisy a mitad — simulando un llenado no total.
    * Precio por parcial: deriva del mid con slippage adverso + spread, oscilando
      deterministamente en ±X bps; crece levemente con el ordinal.
    * ``cumulative_filled_quantity`` = suma de deltas == quantity (estado FILL) o
      < quantity cuando la orden quedó en parcial no-completa (market out).

    La semántica documentada es la del contrato P2-03: cada llenado luce como un
    ``execution_id = f"{venue_order_id}#{fill_seq}"`` independiente e idempotente.
    """
    total = _qty(quantity)
    if total <= 0:
        return SimulatedOrderResult(
            venue_order_id=venue_order_id,
            status="submitted",
            reason="no_quantity",
            scheduled_gap_seconds=0.0,
            fills=(),
            queue_event="ok",
            cumulative_filled_quantity=Decimal("0"),
        )
    q_noise, gap = draw_queue_noise(seed, side, instrument_id)
    if q_noise in {
        "noise_reject",
        "noise_market_closed",
        "noise_unavailable",
        "noise_timeout",
        "noise_unknown",
    }:
        # Costas terminales que NO llenan (fail-closed: cero delta, cero ledger).
        status_map = {
            "noise_reject": "rejected",
            "noise_market_closed": "rejected",
            "noise_unavailable": "unknown",
            "noise_timeout": "unknown",
            "noise_unknown": "unknown",
        }
        return SimulatedOrderResult(
            venue_order_id=venue_order_id,
            status=status_map[q_noise],  # type: ignore[arg-type]
            reason=f"sim_{q_noise}",
            scheduled_gap_seconds=gap,
            fills=(),
            queue_event=q_noise,
            cumulative_filled_quantity=Decimal("0"),
        )

    # Camino de llenado: vamos consumiendo el total en deltas que se adelgazan.
    scale = Decimal("0.000001")
    # Fracciones decrecientes deterministas: p.ej. 0.5/0.3/0.2 para 3 chunks.
    weights = [max(0.5 - 0.03 * i, 0.15) for i in range(fill_chunks)]
    deltas: list[Decimal] = []
    pending = total
    base_mid_dec = Decimal(base_mid)
    for i in range(fill_chunks):
        if pending < scale:
            break
        is_last = i == fill_chunks - 1
        # Mercado noisy a mitad: una parcial se queda corta (no consumimos el resto)
        # solo si aún no es el chunk final. (Caso de libro: partial-mided.)
        if not is_last:
            # V2.24/A9.1 (P1-03): la aleatoriedad del book depende SOLO del contexto
            # de mercado (seed/side/instrument), nunca de la identidad del order
            # (``venue_order_id``). Así namespacear la identidad no altera el fill.
            mid_cut = sim_rand(seed, side, instrument_id, "partialcut", i)
            if mid_cut < 0.07:
                break  # la cola no mete el resto → esta orden queda en parcial.
        frac = Decimal(str(weights[i]))
        delta = (pending * frac).quantize(scale, rounding=ROUND_HALF_DOWN)
        if is_last or delta <= 0 or delta > pending:
            delta = pending  # el último chunk consume el resto → sum = quantity.
        deltas.append(delta)
        pending -= delta

    # Precio adverso determinista por parcial (slippage crece con ordinal).
    fills: list[SimulatedFill] = []
    cum = Decimal("0")
    elapsed = 0.0
    for i, d in enumerate(deltas, start=1):
        slip = adverse_slippage_bps * i - (sim_rand(seed, side, instrument_id, "slip", i) * 2 - 1) * 2
        spr = spread_bps / 2.0
        bps_total = Decimal(str(slip + spr)) / Decimal("10000")
        delta_price = base_mid_dec * bps_total
        # buy: compra al ask (= mid + slippageAdverso). sell: al bid (simétrico).
        sign = Decimal("-1") if str(side).strip().lower() in {"sell", "short"} else Decimal("1")
        px = base_mid_dec + sign * abs(delta_price)
        delay_extra = 0.08 * (1 + sim_rand(seed, side, instrument_id, "delay", i))
        elapsed += gap + delay_extra
        cum += d
        fills.append(
            SimulatedFill(
                fill_seq=i,
                qty_delta=d,
                price=_price(px),
                occurred_after_seconds=round(elapsed, 4),
                venue_order_id=venue_order_id,
            )
        )
    # Invariante garantizada por construcción: la suma de deltas nunca supera el
    # total pedido (cada delta acota a pending restante).
    if not fills:
        status: Any = "submitted"
        reason: str | None = "sim_submitted_no_fill"
    else:
        full = cum == total
        status = "filled" if full else "partial"
        reason = "sim_full_fill" if full else "sim_partial"
        if q_noise not in {"ok", "noise_duplicate", "noise_reconnect"}:
            reason = f"sim_{q_noise}"
    return SimulatedOrderResult(
        venue_order_id=venue_order_id,
        status=status,
        reason=reason,
        scheduled_gap_seconds=gap,
        fills=tuple(fills),
        queue_event=q_noise,
        cumulative_filled_quantity=cum,
    )
