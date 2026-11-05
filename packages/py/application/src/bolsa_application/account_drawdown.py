"""F4 — telemetría de equity para circuit breakers daily/weekly/max."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def _finite(value: Any) -> float | None:
    """``float`` finito, o ``None`` si no es un número medible.

    P3 (auditoría .183): ``bool`` no es un número y ``NaN``/``inf`` no son referencias.
    Tratarlos como cifra envenena el pico y convierte la caída en ``0 %``: el circuit
    breaker dejaría de disparar.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _day_key(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d")


def _week_key(dt: datetime) -> str:
    iso = dt.astimezone(UTC).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


@dataclass(frozen=True, slots=True)
class AccountDrawdowns:
    """Use-case / tipo: Account Drawdowns."""
    daily_pct: float | None
    weekly_pct: float | None
    max_pct: float | None
    day_open_equity: float | None
    week_open_equity: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dailyPct": self.daily_pct,
            "weeklyPct": self.weekly_pct,
            "maxPct": self.max_pct,
            "dayOpenEquity": self.day_open_equity,
            "weekOpenEquity": self.week_open_equity,
        }


def _dd_pct(reference: float, current: float) -> float | None:
    """Caída porcentual desde ``reference``; ``None`` cuando **no es medible**.

    P3 (auditoría .183): ``reference <= 0`` no es "sin caída", es ausencia de marca
    (cuenta sin equity al abrir el día/semana). Devolver ``0.0`` afirmaba un cero
    medido y el circuit breaker no disparaba nunca. Lo mismo con valores no finitos:
    el resultado honesto es "no medido", y quien consume decide (el gate de política
    lo convierte en ``*_unmeasured`` → veto).
    """
    reference_f = _finite(reference)
    current_f = _finite(current)
    if reference_f is None or current_f is None or reference_f <= 0:
        return None
    return max(0.0, (reference_f - current_f) / reference_f * 100.0)


class EquityMarkBook:
    """
    Marcas de apertura día/semana por cuenta (proceso + opcional settings_json).
    Al primer equity del día/semana se fija la referencia; DD = caída desde esa marca.
    max_pct se computa desde el pico de equity (high-water-mark), no desde el depósito inicial.

    P3 (auditoría .183) — contrato de medición:

    * ``daily_pct``/``weekly_pct`` son ``None`` cuando la referencia **no es medible**
      (``<= 0`` o no finita). ``None`` significa "no medido"; nunca se colapsa a ``0 %``.
    * Un equity no finito devuelve todas las métricas en ``None`` y **no** muta el libro:
      la marca buena anterior sigue siendo la referencia del día.
    * La frontera del día es **UTC** (``dayKey``/``weekKey`` viajan dentro de las marcas),
      así que una marca de otro día se descarta, no se reinterpreta en otra zona.
    """

    def __init__(self) -> None:
        self._by_account: dict[str, dict[str, Any]] = {}

    def load_from_settings(self, account_id: str, settings: dict[str, Any] | None) -> None:
        if not settings:
            return
        marks = settings.get("equityMarks")
        if isinstance(marks, dict):
            self._by_account[account_id] = dict(marks)

    def export_settings_fragment(self, account_id: str) -> dict[str, Any]:
        return {"equityMarks": dict(self._by_account.get(account_id) or {})}

    def has_marks(self, account_id: str) -> bool:
        return bool(self._by_account.get(account_id))

    def reset(self) -> None:
        """Olvida todas las marcas (arranque en frío y aislamiento entre tests).

        El libro es estado de PROCESO compartido. Sin este punto de reseteo, el orden de
        los tests (o un reinicio del proceso) cambiaba la referencia de drawdown de una
        cuenta y, desde P2, un drawdown heredado veta aperturas legítimas.
        """
        self._by_account.clear()

    def update(
        self,
        account_id: str,
        equity: float,
        *,
        initial_deposit: float | None = None,
        now: datetime | None = None,
    ) -> AccountDrawdowns:
        now_dt = now or _utc_now()
        # P3: sin equity medible no hay drawdown medible y NO se toca el libro (una marca
        # envenenada con NaN sobreviviría a todos los ticks siguientes).
        equity_f = _finite(equity)
        if equity_f is None:
            return AccountDrawdowns(
                daily_pct=None,
                weekly_pct=None,
                max_pct=None,
                day_open_equity=None,
                week_open_equity=None,
            )
        day = _day_key(now_dt)
        week = _week_key(now_dt)
        state = self._by_account.setdefault(account_id, {})

        # Una marca guardada no finita no es referencia: se reabre el día igual que si no
        # existiera. Una marca a 0 SÍ se conserva: `_dd_pct` la declara "no medible"
        # (`None`) en vez de reabrir el día y fabricar un 0 % que borraría la caída real.
        day_open = _finite(state.get("dayOpen"))
        if state.get("dayKey") != day or day_open is None:
            state["dayKey"] = day
            day_open = equity_f
            state["dayOpen"] = day_open
        week_open = _finite(state.get("weekOpen"))
        if state.get("weekKey") != week or week_open is None:
            state["weekKey"] = week
            week_open = equity_f
            state["weekOpen"] = week_open

        state["lastEquity"] = equity_f
        state["updatedAt"] = now_dt.isoformat().replace("+00:00", "Z")

        peak = _finite(state.get("peakEquity"))
        if peak is None:
            seed = equity_f
            deposit = _finite(initial_deposit)
            if deposit is not None and deposit > 0:
                seed = max(seed, deposit)
            peak = seed
        peak = max(peak, equity_f)
        state["peakEquity"] = peak
        new_high = equity_f >= peak

        max_dd: float | None = None
        deposit = _finite(initial_deposit)
        if deposit is not None and deposit > 0:
            if new_high:
                max_dd = 0.0
            else:
                cur = _dd_pct(peak, equity_f)
                prev = _finite(state.get("maxDrawdownPct"))
                if cur is None:
                    max_dd = None
                else:
                    max_dd = cur if prev is None else max(prev, cur)
            state["maxDrawdownPct"] = max_dd

        daily = _dd_pct(day_open, equity_f)
        weekly = _dd_pct(week_open, equity_f)
        return AccountDrawdowns(
            daily_pct=None if daily is None else round(daily, 4),
            weekly_pct=None if weekly is None else round(weekly, 4),
            max_pct=None if max_dd is None else round(max_dd, 4),
            day_open_equity=day_open,
            week_open_equity=week_open,
        )


# Libro compartido en proceso (paper_auto / tests)
GLOBAL_EQUITY_MARK_BOOK = EquityMarkBook()
