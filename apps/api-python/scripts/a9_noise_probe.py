"""Sonda puntual (no permanente): tasa de rechazo de la cola noisy del venue SIM.

``draw_queue_noise`` decide, de forma determinista a partir de (seed, instrument_id, lado),
si la orden topa con una "costa terminal" que NO llena (reject/timeout/market_closed/
unavailable/unknown) ⇒ ``fills=()``. En el test de restart el instrument_id es ALEATORIO
(``inst-a9restart-<10hex>``) y ``seed = sum(ord(symbol)) % 9999``, así que la probabilidad de
que la entrada se pierda es una lotería por ejecución. Esta sonda la mide.

Uso: ``uv run --no-sync python apps/api-python/scripts/a9_noise_probe.py [n]``
"""

from __future__ import annotations

import random
import sys
from decimal import Decimal

from bolsa_application.simulated_broker import (
    draw_queue_noise,
    simulated_fill_schedule,
)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000


def main() -> None:
    rng = random.Random(20260916)
    empty = 0
    by_event: dict[str, int] = {}
    for _ in range(N):
        instrument_id = f"inst-a9restart-{rng.randrange(16**10):010x}"
        seed = sum(map(ord, instrument_id)) % 9999
        event, _ = draw_queue_noise(seed, "buy", instrument_id)
        by_event[event] = by_event.get(event, 0) + 1
        schedule = simulated_fill_schedule(
            instrument_id=instrument_id,
            side="buy",
            quantity=Decimal("100"),
            venue_order_id=f"sim-x-{instrument_id}",
            seed=seed,
            fill_chunks=4,
            base_mid=100.0,
        )
        if not schedule.fills:
            empty += 1
    print("n =", N)
    print("sin fills:", empty, f"({100.0 * empty / N:.2f}%)")
    for event, n in sorted(by_event.items(), key=lambda kv: -kv[1]):
        print(f"  {event}: {n} ({100.0 * n / N:.2f}%)")


if __name__ == "__main__":
    main()
