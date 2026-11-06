#!/usr/bin/env python3
"""Limpia velas «vivas» mal fechadas de ``ohlcv_bars`` (gráfico MERCADO).

Yahoo v8 añade al final de intradía/mensual una vela en curso cuyo timestamp es
``meta.regularMarketTime`` (segundos arbitrarios) en vez del inicio de periodo.
Versiones anteriores la persistían: cada refresco insertaba una fila nueva y el
gráfico dibujaba una vela en una posición temporal imposible. El parser ya la
descarta; este script retira el residuo histórico.

Detección (solo timeframe != 1d):

* segundos/microsegundos distintos de cero (Yahoo siempre entrega :00);
* separación con la vela anterior inferior a medio intervalo nominal.

Por defecto solo LISTA. El borrado exige ``--apply``.

Uso (repo root)::

    uv run python scripts/verify/cleanup_ohlcv_live_bars.py
    uv run python scripts/verify/cleanup_ohlcv_live_bars.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_PATHS = [
    str(path)
    for path in (
        ROOT / "packages" / "py" / "infrastructure" / "src",
        ROOT / "packages" / "py" / "domain" / "src",
        ROOT / "packages" / "py" / "market" / "src",
        ROOT / "packages" / "py" / "application" / "src",
    )
    if str(path) not in sys.path
]
sys.path[:0] = _PATHS

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:  # noqa: BLE001
        pass

# Mínima separación creíble con la vela anterior (la mitad del intervalo).
MIN_GAP: dict[str, timedelta] = {
    "1m": timedelta(seconds=30),
    "5m": timedelta(seconds=150),
    "15m": timedelta(seconds=450),
    "30m": timedelta(seconds=900),
    "1h": timedelta(seconds=1800),
    "4h": timedelta(seconds=7200),
    "1wk": timedelta(days=6),
    "1mo": timedelta(days=27),
}


def is_live_bar_residue(
    timeframe: str,
    timestamp: datetime,
    previous: datetime | None,
) -> tuple[bool, str]:
    """Decide si una fila es una vela viva mal fechada."""
    if timeframe == "1d":
        return False, ""
    if timestamp.second != 0 or timestamp.microsecond != 0:
        return True, "segundos_no_cero"
    min_gap = MIN_GAP.get(timeframe)
    if previous is not None and min_gap is not None and timestamp - previous < min_gap:
        return True, "separacion_menor_que_intervalo"
    return False, ""


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


async def _run(*, apply: bool) -> int:
    _load_env()
    from sqlalchemy import delete, select

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models import OhlcvBarRow
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    print("=== cleanup_ohlcv_live_bars ===")

    findings: list[dict[str, object]] = []
    async with factory() as session:
        rows = (
            await session.execute(
                select(OhlcvBarRow)
                .where(OhlcvBarRow.timeframe != "1d")
                .order_by(
                    OhlcvBarRow.instrument_id,
                    OhlcvBarRow.timeframe,
                    OhlcvBarRow.timestamp,
                )
            )
        ).scalars()
        previous_key: tuple[str, str] | None = None
        previous_ts: datetime | None = None
        for row in rows:
            key = (row.instrument_id, row.timeframe)
            if key != previous_key:
                previous_key = key
                previous_ts = None
            flagged, reason = is_live_bar_residue(row.timeframe, row.timestamp, previous_ts)
            if flagged:
                findings.append(
                    {
                        "id": row.id,
                        "instrument_id": row.instrument_id,
                        "timeframe": row.timeframe,
                        "timestamp": row.timestamp.isoformat(),
                        "reason": reason,
                    }
                )
            previous_ts = row.timestamp

        print(f"residuos detectados: {len(findings)}")
        for item in findings[:20]:
            print(
                f"  - {item['instrument_id']} {item['timeframe']} "
                f"{item['timestamp']} ({item['reason']})"
            )
        if len(findings) > 20:
            print(f"  … y {len(findings) - 20} más")

        if apply and findings:
            ids = [str(item["id"]) for item in findings]
            await session.execute(delete(OhlcvBarRow).where(OhlcvBarRow.id.in_(ids)))
            await session.commit()
            print(f"borrados: {len(ids)}")
        elif findings:
            print("modo lista: usa --apply para borrar")

    report = {
        "mode": "apply" if apply else "dry-run",
        "detected": len(findings),
        "findings": findings,
    }
    print(json.dumps(report, ensure_ascii=False))
    await engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="borra los residuos")
    args = parser.parse_args()
    return asyncio.run(_run(apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
