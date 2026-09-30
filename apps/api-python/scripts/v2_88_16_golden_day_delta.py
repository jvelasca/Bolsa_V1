#!/usr/bin/env python3
"""V2.88.16 (``W3``) — DELTA del GOLDEN DAY: ancla de **MINUTO** vs ancla de **BARRA**.

Qué mide: por qué el día golden hermético tuvo que pasar de ``2026-09-15`` a ``2026-09-17``
al anclar el fill a la BARRA (``fill_seed(bar_tick(moment, timeframe), symbol)``), y que
``2026-09-17`` es el **primer** día posterior que sostiene la premisa del guion.

Premisa del guion del día (``test_auto_v2_golden_day_evidence.py``), tal y como lo ejecuta el
test: en su **barra de entrada** las **tres** compras (``AAA``/``BBB``/``CCC``, 250 uds) se
materializan y las **dos** salidas de esa misma barra (tesis de ``BBB``, stop estructural de
``CCC``) llenan COMPLETAS; la tercera salida (``time_exit`` de ``AAA``) se dispara con un
**salto de reloj** del guion (``2026-11-01``) y por eso se mide como un requisito aparte, en
SU barra (una salida parcial no cerraría la posición y el guion exige libro plano).

Cómo: arnés puro y determinista (sin BD, sin proceso, sin reloj real) que evalúa
``simulated_fill_schedule`` — el MISMO planificador del venue SIM — sobre las órdenes del
guion, con DOS anclas:

* ``nueva`` (``W3``): **un** sorteo por barra — ``seed = fill_seed(bar_tick(día), símbolo)``.
  Es el comportamiento del motor desde ``v2.88.16``: el desenlace de la barra es ÚNICO.
* ``vieja`` (histórica, ``≤ v2.88.15``): el seed colgaba del **minuto** del bucle
  (``seed = self._minute * 100_003 + …``), que es exactamente ``fill_seed(minuto, símbolo)``:
  el mismo ruido re-sorteado cada 60 s ⇒ hasta 1440 oportunidades por día. Por eso el día
  ``2026-09-15`` era válido ANTES aunque su barra no lo sea: el reintento rescataba la orden.

Resultado (verificado): ``2026-09-15`` NO sostiene la premisa con el ancla de barra (una de
las órdenes topa con una cola terminal del 5,6 %) pero SÍ era rescatable con el ancla de
minuto; ``2026-09-17`` es el **primer** día posterior a ``2026-09-15`` que la sostiene ⇒ es el
día elegido, con la razón medida, no narrada.

Dos formas de NO materializar una compra quedan cubiertas, porque las dos existen en el venue:
la cola **terminal** (``rejected``/``unknown``, cero fills) y el **corte de mitad en el primer
chunk** (``submitted`` sin fills, ``queue_event="ok"``). Con el ancla de barra ninguna de las
dos se reintenta dentro del día.

Uso (desde la raíz del repo)::

    uv run --no-sync python apps/api-python/scripts/v2_88_16_golden_day_delta.py
    uv run --no-sync python apps/api-python/scripts/v2_88_16_golden_day_delta.py --json --out delta.json

Códigos de salida: ``0`` si el delta se reproduce tal y como lo declara la evidencia (09-15
inválido con barra y rescatable con minuto · 09-17 válido y primero tras 09-15); ``2`` si no
(el día elegido o la explicación del delta NO se sostienen ⇒ el sello no se puede firmar);
``1`` uso incorrecto.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
for _path in (
    _REPO_ROOT / "packages" / "py" / "application" / "src",
    _REPO_ROOT / "packages" / "py" / "domain" / "src",
    _REPO_ROOT / "packages" / "py" / "analytics" / "src",
    _REPO_ROOT / "apps" / "api-python" / "src",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from bolsa_application.closed_bars import bar_tick  # noqa: E402
from bolsa_application.simulated_broker import fill_seed, simulated_fill_schedule  # noqa: E402

#: Guion del día golden: tres entradas y sus tres salidas.
_SYMBOLS = ("AAA", "BBB", "CCC")
#: Cantidad de la propuesta de entrada del guion (``DecisionPackage(quantity=250.0)``).
_QUANTITY = Decimal("250")
#: Chunks del venue en el motor (``auto_simulation_worker._FILL_CHUNKS``).
_FILL_CHUNKS = 4
#: Barra del golden HISTÓRICO (``≤ v2.88.15``, ancla de minuto).
_OLD_DAY = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)
#: Barra del golden NUEVO (``W3``, ancla de barra) — el que fija el test.
_NEW_DAY = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)
#: Barra del ``time_exit`` de ``AAA``: el guion salta el reloj aquí (techo congelado al nacer).
_TIME_EXIT_DAY = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
#: Salidas que el guion ejecuta en la MISMA barra de la entrada.
_IN_BAR_EXITS = ("BBB", "CCC")
#: Salida que el guion ejecuta tras el salto de reloj.
_LATE_EXIT = "AAA"
#: Minutos que el bucle del motor latía en una barra D1 (60 s ⇒ 1440 vueltas/día).
_MINUTES_PER_DAY = 24 * 60


def _probe(symbol: str, side: str, quantity: Decimal, seed: int) -> dict[str, Any]:
    """Un plan de fill del venue SIM para ``(símbolo, lado, cantidad, seed)``."""
    result = simulated_fill_schedule(
        instrument_id=symbol,
        side=side,
        quantity=quantity,
        venue_order_id=f"delta-{side}-{symbol}-{seed}",
        seed=seed,
        fill_chunks=_FILL_CHUNKS,
        base_mid=100.0,
    )
    return {
        "symbol": symbol,
        "side": side,
        "status": result.status,
        "reason": result.reason,
        "queue_event": result.queue_event,
        "filled": str(result.cumulative_filled_quantity),
        "chunks": len(result.fills),
    }


def _day_orders(moment: datetime, *, anchor: str, minute: int = 0) -> list[dict[str, Any]]:
    """Órdenes del guion en la barra de ``moment`` con el ancla pedida (``bar`` | ``minute``).

    Se modelan las entradas (3 BUY) y las salidas que el guion ejecuta **en esa misma barra**
    (``BBB`` tesis, ``CCC`` stop estructural). La salida tardía de ``AAA`` se mide aparte, en
    su barra (``_TIME_EXIT_DAY``). El BUY va primero; la SALIDA vende EXACTAMENTE lo que el
    BUY materializó (es lo que hace el motor con la posición viva), con el MISMO seed de ancla
    y lado venta.
    """
    tick = bar_tick(moment, "1d") if anchor == "bar" else minute
    orders: list[dict[str, Any]] = []
    for symbol in _SYMBOLS:
        seed = fill_seed(tick, symbol)
        buy = _probe(symbol, "buy", _QUANTITY, seed)
        orders.append(buy)
        if symbol not in _IN_BAR_EXITS:
            continue
        filled = Decimal(buy["filled"])
        if buy["status"] in {"rejected", "unknown"} or filled <= 0:
            orders.append(_probe(symbol, "sell", _QUANTITY, seed))
            continue
        orders.append(_probe(symbol, "sell", filled, seed))
    return orders


def _holds(orders: list[dict[str, Any]]) -> bool:
    """¿La barra sostiene el guion? 3 compras materializadas y las salidas EN BARRA completas."""
    buys = [o for o in orders if o["side"] == "buy"]
    sells = [o for o in orders if o["side"] == "sell"]
    materialized = all(o["status"] in {"filled", "partial"} for o in buys)
    closed = all(o["status"] == "filled" for o in sells)
    return bool(materialized and closed)


def _late_exit_holds() -> dict[str, Any]:
    """La salida ``time_exit`` de ``AAA`` en SU barra (``_TIME_EXIT_DAY``) completa."""
    tick = bar_tick(_TIME_EXIT_DAY, "1d")
    sell = _probe(_LATE_EXIT, "sell", _QUANTITY, fill_seed(tick, _LATE_EXIT))
    return {
        "day": _TIME_EXIT_DAY.strftime("%Y-%m-%d"),
        "tick": tick,
        "holds": sell["status"] == "filled",
        "order": sell,
    }


def _bar_verdict(moment: datetime) -> dict[str, Any]:
    orders = _day_orders(moment, anchor="bar")
    blocking = [o for o in orders if o["side"] == "buy" and o["status"] not in {"filled", "partial"}]
    blocking += [o for o in orders if o["side"] == "sell" and o["status"] != "filled"]
    return {
        "day": moment.strftime("%Y-%m-%d"),
        "tick": bar_tick(moment, "1d"),
        "holds": _holds(orders),
        "orders": orders,
        "blocking": blocking,
    }


def _minute_rescue(moment: datetime) -> dict[str, Any]:
    """¿El día era rescatable con el ancla de MINUTO? (oportunidades por orden).

    Bajo el ancla vieja el seed colgaba del minuto del bucle: una orden rechazada en un
    minuto se re-sorteaba en el siguiente. El día se completaba si CADA orden del guion tenía
    al menos un minuto que llenaba, así que se cuentan los minutos útiles de las 24 h de la
    barra para las órdenes que ese día ejecuta (3 compras + las 2 salidas en barra).
    """
    per_order: dict[str, dict[str, int]] = {}
    plan = [(symbol, "buy") for symbol in _SYMBOLS] + [
        (symbol, "sell") for symbol in _IN_BAR_EXITS
    ]
    for symbol, side in plan:
        ok = 0
        for minute in range(_MINUTES_PER_DAY):
            probe = _probe(symbol, side, _QUANTITY, fill_seed(minute, symbol))
            if side == "buy":
                ok += int(probe["status"] in {"filled", "partial"})
            else:
                ok += int(probe["status"] == "filled")
        per_order[f"{side}:{symbol}"] = {"minutes_ok": ok, "rolls": _MINUTES_PER_DAY}
    return {
        "day": moment.strftime("%Y-%m-%d"),
        "rescuable": all(v["minutes_ok"] > 0 for v in per_order.values()),
        "per_order": per_order,
    }


def measure() -> dict[str, Any]:
    """Veredicto del delta: día viejo (minuto) frente a día nuevo (barra) + primer válido."""
    old_bar = _bar_verdict(_OLD_DAY)
    old_minute = _minute_rescue(_OLD_DAY)
    new_bar = _bar_verdict(_NEW_DAY)
    late_exit = _late_exit_holds()

    # Primer día posterior al viejo que sostiene el guion con el ancla de BARRA (la elección
    # del fixture deja de ser narrada: se RE-DERIVA y se compara con la declarada).
    first_valid: str | None = None
    scan: list[dict[str, Any]] = []
    for offset in range(1, 31):
        candidate = _OLD_DAY + timedelta(days=offset)
        verdict = _bar_verdict(candidate)
        scan.append(
            {
                "day": verdict["day"],
                "tick": verdict["tick"],
                "holds": verdict["holds"],
                "blocking": [
                    {
                        "symbol": o["symbol"],
                        "side": o["side"],
                        "status": o["status"],
                        "queue_event": o["queue_event"],
                    }
                    for o in verdict["blocking"]
                ],
            }
        )
        if verdict["holds"] and first_valid is None:
            first_valid = verdict["day"]
            break

    new_holds = bool(new_bar["holds"] and late_exit["holds"])
    return {
        "old_anchor": {
            "day": old_minute["day"],
            "minute": old_minute,
            "bar": old_bar,
        },
        "new_anchor": {"day": new_bar["day"], "bar": new_bar, "time_exit": late_exit},
        "first_valid_after_old": first_valid,
        "scan": scan,
        "verdict": {
            "old_day_fails_with_bar_anchor": not old_bar["holds"],
            "old_day_was_rescuable_by_minute_retry": bool(old_minute["rescuable"]),
            "new_day_holds_with_bar_anchor": new_holds,
            "new_day_is_first_valid": first_valid == new_bar["day"],
            "reason": (
                "el ancla de barra hace UN sorteo por barra: donde el ancla de minuto "
                "reintentaba hasta 1440 veces en el día, la barra declara un desenlace único; "
                "el día golden se re-elige por MEDICIÓN (primer día que sostiene el guion), "
                "no por conveniencia."
            ),
        },
    }


def _render(payload: dict[str, Any]) -> None:
    old = payload["old_anchor"]
    new = payload["new_anchor"]
    print("GOLDEN DAY — delta ancla MINUTO vs ancla BARRA (W3 / v2.88.16)")
    print("-" * 78)
    print(f"día viejo declarado : {old['day']}")
    print(f"día nuevo declarado : {new['day']}")
    print(f"primer día válido   : {payload['first_valid_after_old']}")
    print("-" * 78)
    for label, day in (("viejo", old), ("nuevo", new)):
        bar = day["bar"]
        print(f"[{label}] {bar['day']} · tick={bar['tick']} · sostiene={bar['holds']}")
        for order in bar["orders"]:
            print(
                f"    {order['side']:<4} {order['symbol']:<4} "
                f"{order['status']:<8} {order['queue_event']:<18} llenado={order['filled']}"
            )
    print("-" * 78)
    minute = old["minute"]
    print(f"rescatable con ancla de MINUTO (día viejo) = {minute['rescuable']} · "
          f"{_MINUTES_PER_DAY} sorteos/orden")
    for key, value in minute["per_order"].items():
        print(f"    {key:<11} minutos útiles = {value['minutes_ok']}/{value['rolls']}")
    late = new["time_exit"]
    print("-" * 78)
    order = late["order"]
    print(
        f"[time_exit] {late['day']} · tick={late['tick']} · sostiene={late['holds']} · "
        f"{order['side']} {order['symbol']} {order['status']} {order['queue_event']} "
        f"llenado={order['filled']}"
    )
    print("-" * 78)
    for row in payload["scan"]:
        flag = "SOSTIENE" if row["holds"] else "no"
        blockers = ", ".join(
            f"{b['side']}:{b['symbol']}={b['status']}/{b['queue_event']}" for b in row["blocking"]
        )
        print(f"    {row['day']} tick={row['tick']:<6} {flag:<9} {blockers}")
    verdict = payload["verdict"]
    print("-" * 78)
    for key in (
        "old_day_fails_with_bar_anchor",
        "old_day_was_rescuable_by_minute_retry",
        "new_day_holds_with_bar_anchor",
        "new_day_is_first_valid",
    ):
        print(f"{key:<38} {verdict[key]}")
    print("-" * 78)
    print("DELTA REPRODUCIDO" if all(verdict[k] for k in (
        "old_day_fails_with_bar_anchor",
        "old_day_was_rescuable_by_minute_retry",
        "new_day_holds_with_bar_anchor",
        "new_day_is_first_valid",
    )) else "DELTA NO REPRODUCIDO")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emite la medición como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de medición")
    args = parser.parse_args(argv)

    payload = measure()
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
    if args.json:
        print(rendered)
    else:
        _render(payload)

    ok = all(
        payload["verdict"][key]
        for key in (
            "old_day_fails_with_bar_anchor",
            "old_day_was_rescuable_by_minute_retry",
            "new_day_holds_with_bar_anchor",
            "new_day_is_first_valid",
        )
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
