"""PortfolioFit v1 — encaje de cesta (concentración por activo y por sector).

Señal del sistema: velas D1. Se evalúa a nivel CESTA, sumando la puesta propuesta
("as-if fill") a las posiciones existentes. Es una función pura de la capa
analytics: sin I/O, sin sesión DB, sin side-effects.

La métrica de encaje usada por el Risk de cesta es la concentración:
  - (a) peso por ACTIVO  (max_asset_weight_pct)
  - (b) peso por SECTOR  (max_sector_weight_pct)

Comportamiento del Risk: VETO (fail-closed). Si la puesta propuesta hace que el
peso del activo o del sector supere el límite de policy, el Risk DENY.
"""

from __future__ import annotations

from dataclasses import dataclass

# Clave sentinel para instrumentos sin sector en ``BasketPosition.sector``:
# se agrupan bajo esta clave para que existan (no se pierden del agregado) y
# se informan con el mismo criterio que un sector real.
UNKNOWN_SECTOR = "<unknown>"

FIT_NOTE_PREFIX = "PortfolioFit v1"


@dataclass(frozen=True, slots=True)
class BasketPosition:
    instrument_id: str
    market_value: float | None
    sector: str | None = None


@dataclass(frozen=True, slots=True)
class PortfolioFitSignal:
    """Resultado del encaje de cesta tras el as-if fill.

    ``max_asset_weight_pct`` y ``max_sector_weight_pct`` son máximos tras
    añadir la puesta propuesta. ``violating_asset`` / ``violating_sector`` se
    llenan solo cuando se pasa el/los límite/s de policy.
    """

    max_asset_weight_pct: float | None
    max_sector_weight_pct: float | None
    violating_asset: str | None
    violating_sector: str | None
    note: str


def _safe_market_value(value: float | None) -> float | None:
    """Normaliza market_value: acepta sólo números positivos finitos."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f <= 0:
        return None
    return f


def _fmt_pct(pct: float) -> str:
    return f"{pct:.2f}%"


def compute_portfolio_fit(
    *,
    proposal: BasketPosition,
    existing: list[BasketPosition],
    equity: float | None,
    max_asset_weight_pct: float | None = None,
    max_sector_weight_pct: float | None = None,
) -> PortfolioFitSignal:
    """Computa la concentración de cesta tras el as-if fill.

    Peso de cada posición = ``market_value / equity``. ``equity`` es la equidad
    total reportada (``total_equity``); si es None o <= 0 se usa la suma de
    los ``market_value`` disponibles como denominador. Si es imposible obtener
    denominador > 0, se devuelve una señal "no_evaluable" sin afirmar violación
    (evitando un falso VETO por falta de datos).

    ``violating_asset`` / ``violating_sector`` se rellenan cuando el peso
    supera el límite correspondiente (solo si se aporta el límite). Instrumentos
    con ``sector is None`` se agrupan bajo ``"<unknown>"``.
    """
    mvs: list[tuple[str, float, str]] = []
    for pos in [proposal, *existing]:
        mv = _safe_market_value(pos.market_value)
        if mv is None:
            continue
        sector = pos.sector if pos.sector and pos.sector.strip() else UNKNOWN_SECTOR
        mvs.append((pos.instrument_id, mv, sector))

    if not mvs:
        return PortfolioFitSignal(
            max_asset_weight_pct=None,
            max_sector_weight_pct=None,
            violating_asset=None,
            violating_sector=None,
            note=f"{FIT_NOTE_PREFIX}: concentración cesta por activo y sector (no_evaluable, sin posiciones valuables)",
        )

    sum_mvs = sum(mv for _, mv, _ in mvs)
    denominator = equity
    if denominator is None or denominator <= 0:
        denominator = sum_mvs
    if denominator <= 0:
        return PortfolioFitSignal(
            max_asset_weight_pct=None,
            max_sector_weight_pct=None,
            violating_asset=None,
            violating_sector=None,
            note=f"{FIT_NOTE_PREFIX}: concentración cesta no_evaluable (denominador <= 0)",
        )

    by_asset: dict[str, float] = {}
    by_sector: dict[str, float] = {}
    for instrument_id, mv, sector in mvs:
        by_asset[instrument_id] = by_asset.get(instrument_id, 0.0) + mv
        by_sector[sector] = by_sector.get(sector, 0.0) + mv

    max_asset = max(by_asset.values())
    largest_asset = max(by_asset, key=lambda k: by_asset[k])
    max_sector = max(by_sector.values())
    largest_sector = max(by_sector, key=lambda k: by_sector[k])

    max_asset_pct = (max_asset / denominator) * 100.0
    max_sector_pct = (max_sector / denominator) * 100.0

    violating_asset: str | None = None
    if max_asset_weight_pct is not None and max_asset_pct > max_asset_weight_pct:
        violating_asset = largest_asset
    violating_sector: str | None = None
    if max_sector_weight_pct is not None and max_sector_pct > max_sector_weight_pct:
        violating_sector = largest_sector

    note = (
        f"{FIT_NOTE_PREFIX}: concentración cesta por activo ({_fmt_pct(max_asset_pct)}) "
        f"y por sector ({_fmt_pct(max_sector_pct)})"
    )
    return PortfolioFitSignal(
        max_asset_weight_pct=round(max_asset_pct, 4),
        max_sector_weight_pct=round(max_sector_pct, 4),
        violating_asset=violating_asset,
        violating_sector=violating_sector,
        note=note,
    )
