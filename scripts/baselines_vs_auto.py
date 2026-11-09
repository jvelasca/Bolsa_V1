#!/usr/bin/env python
"""Líneas base long-only con costes, para compararlas con AUTO sobre TUS datos.

Responde a una pregunta: ¿alguna regla simple supera a comprar y mantener (B&H) en tu
universo y ventana, con las mismas fricciones que mide AUTO (~12,7 bps/lado)?

Uso (Postgres de tu .env, solo lectura):
    python scripts/baselines_vs_auto.py --start 2022-01-03
    python scripts/baselines_vs_auto.py --selftest        # datos sintéticos, sin BD

Reglas (decisión con datos hasta el cierre de t-1, ejecución en la apertura de t; sin
anticipación, igual que el motor AUTO):
  BH          comprar y mantener equiponderado (sin rebalanceo, un solo coste de entrada)
  TREND       cesta equiponderada invertida solo si la cesta > SMA200 (si no, caja)
  MOM         momentum 12-1 meses, quintil superior, rebalanceo mensual, con filtro SMA200
  RANDOM      mismo que MOM pero con puntuaciones aleatorias (N semillas): el control nulo.
              Si MOM no supera al percentil 95 de RANDOM, no hay evidencia de señal.

LIMITACIONES: usa instrumentos ACTIVOS hoy (sesgo de supervivencia, favorece a todas las
reglas por igual y sobre todo a BH). El arnés PIT de tu repo es la referencia fiable.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

AUTO_REFERENCE = {"net_pct": -42.1, "max_dd_pct": 47.5, "bh_pct": 72.9}  # dia-d 2026-11-05


def load_prices(url: str, start: str, timeframe: str = "1d") -> tuple[pd.DataFrame, pd.DataFrame]:
    from sqlalchemy import create_engine, text

    url = url.strip().strip('"').split("?")[0]
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    warmup = (pd.Timestamp(start) - pd.Timedelta(days=420)).strftime("%Y-%m-%d")
    # Clave = yahoo_symbol, NO symbol: hay símbolos repetidos entre plazas (SAN.MC/SAN.PA,
    # BBVA/BBVA.MC) y pivotar por `symbol` mezclaba dos series en una columna. En SAN eso
    # interleava 3 EUR y 88 EUR → retornos de ±3.800 % diarios que el rebalanceo diario
    # convertía en 1e22 % de rentabilidad. yahoo_symbol es único entre los instrumentos activos.
    query = text(
        """
        select coalesce(i.yahoo_symbol, i.symbol) as symbol,
               b.timestamp::date as day, b.open::float8 as open, b.close::float8 as close
        from ohlcv_bars b join instruments i on i.id = b.instrument_id
        where b.timeframe::text = :tf and i.is_active and b.timestamp >= cast(:warmup as timestamptz)
        order by 1, 2
        """
    )
    with create_engine(url).connect() as conn:
        df = pd.read_sql(query, conn, params={"tf": timeframe, "warmup": warmup})
    df["day"] = pd.to_datetime(df["day"])
    df = df.drop_duplicates(["symbol", "day"], keep="last")
    return df.pivot(index="day", columns="symbol", values="open"), df.pivot(
        index="day", columns="symbol", values="close"
    )


def synthetic(n_symbols: int = 40, years: float = 5.5, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2021-01-04", periods=int(252 * years))
    rets = rng.normal(0.0002, 0.016, size=(len(days), n_symbols))
    close = pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=days, columns=[f"S{i}" for i in range(n_symbols)])
    open_ = close.shift(1).fillna(close.iloc[0]) * (1 + rng.normal(0, 0.003, close.shape))
    return open_, close


def metrics(r: pd.Series) -> dict[str, float]:
    eq = (1 + r.fillna(0.0)).cumprod()
    years = max(len(r) / 252.0, 1e-9)
    dd = (eq / eq.cummax() - 1.0).min()
    sd = r.std()
    monthly = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    return {
        "net_pct": 100 * (eq.iloc[-1] - 1),
        "cagr_pct": 100 * (eq.iloc[-1] ** (1 / years) - 1),
        "max_dd_pct": -100 * dd,
        "sharpe": float(r.mean() / sd * np.sqrt(252)) if sd > 0 else float("nan"),
        "pos_months_pct": 100 * float((monthly > 0).mean()),
    }


def run_weights(w_decided: pd.DataFrame, open_: pd.DataFrame, cost_bps: float) -> pd.Series:
    """w_decided[t] se decide con datos hasta el cierre de t y se ejecuta en la apertura de t+1."""
    ret_open = open_.shift(-1) / open_ - 1.0  # mantener de open[t] a open[t+1]
    w = w_decided.shift(1).fillna(0.0)  # decidido en t-1, activo desde open[t]
    gross = (w * ret_open.fillna(0.0)).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(w.abs().sum(axis=1))
    return (gross - turnover * cost_bps / 1e4).iloc[:-1]


def month_end_mask(index: pd.DatetimeIndex) -> pd.Series:
    s = pd.Series(index, index=index)
    return s.groupby([index.year, index.month]).transform("max") == s


def build(open_: pd.DataFrame, close: pd.DataFrame, top_q: float, rng: np.random.Generator | None):
    avail = close.notna() & close.shift(252).notna()
    basket = (1 + close.pct_change().mean(axis=1).fillna(0.0)).cumprod()
    trend_on = (basket > basket.rolling(200).mean()).astype(float)
    ew = avail.div(avail.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    w_trend = ew.mul(trend_on, axis=0)

    score = close.shift(21) / close.shift(252) - 1.0
    if rng is not None:
        score = pd.DataFrame(rng.random(score.shape), index=score.index, columns=score.columns).where(score.notna())
    rank = score.rank(axis=1, pct=True, ascending=True)
    pick = (rank > 1 - top_q).astype(float)
    pick = pick.div(pick.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    reb = month_end_mask(close.index)
    w_mom = pick.where(reb).ffill().fillna(0.0).mul(trend_on, axis=0)
    return w_trend, w_mom


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2022-01-03")
    ap.add_argument("--cost-bps", type=float, default=12.7, help="fricción por lado (AUTO midió 12,71)")
    ap.add_argument("--top-q", type=float, default=0.2)
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        open_, close = synthetic()
        a.start = str(close.index[300].date())
        print("[selftest] datos sintéticos (paseo aleatorio sin edge): MOM no debe batir a RANDOM\n")
    else:
        url = os.environ.get("DATABASE_URL")
        if not url:
            print("Falta DATABASE_URL (exporta el de tu .env).", file=sys.stderr)
            return 2
        open_, close = load_prices(url, a.start)
    close = close.ffill()
    open_ = open_.ffill().combine_first(close)
    start = pd.Timestamp(a.start)

    w_trend, w_mom = build(open_, close, a.top_q, None)
    cut = lambda s: s[s.index >= start]  # noqa: E731
    first = open_.loc[open_.index >= start].iloc[0]
    held = first.dropna().index
    bh_curve = (open_.loc[open_.index >= start, held] / first[held]).mean(axis=1)
    bh = bh_curve.pct_change().fillna(0.0)
    bh.iloc[0] -= a.cost_bps / 1e4

    res = {
        "BH": metrics(bh.iloc[:-1]),
        "TREND": metrics(cut(run_weights(w_trend, open_, a.cost_bps))),
        "MOM": metrics(cut(run_weights(w_mom, open_, a.cost_bps))),
    }
    rng = np.random.default_rng(12345)
    rand = []
    for _ in range(a.seeds):
        _, w_r = build(open_, close, a.top_q, rng)
        rand.append(metrics(cut(run_weights(w_r, open_, a.cost_bps))))
    rdf = pd.DataFrame(rand)

    tbl = pd.DataFrame(res).T
    tbl.loc["RANDOM (mediana)"] = rdf.median()
    tbl.loc["RANDOM (p95)"] = rdf.quantile(0.95)
    tbl.loc["AUTO (dia-d 2026-11-05)"] = [AUTO_REFERENCE["net_pct"], np.nan, AUTO_REFERENCE["max_dd_pct"], np.nan, np.nan]
    print(f"Ventana {a.start} → {close.index[-1].date()} | {close.shape[1]} símbolos | coste {a.cost_bps} bps/lado\n")
    print(tbl.round(2).to_string())
    mom_pct = float((rdf["net_pct"] < res["MOM"]["net_pct"]).mean() * 100)
    print(f"\nMOM supera al {mom_pct:.0f}% de las {a.seeds} carteras aleatorias (>=95% sugiere señal real).")
    print(f"Exceso de MOM vs BH: {res['MOM']['net_pct'] - res['BH']['net_pct']:+.1f} pts | "
          f"TREND vs BH: {res['TREND']['net_pct'] - res['BH']['net_pct']:+.1f} pts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
