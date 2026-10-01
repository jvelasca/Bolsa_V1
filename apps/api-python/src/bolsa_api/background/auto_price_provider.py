"""W4 / v2.88.17-beta — Proveedor de precio REAL del motor AUTO (frontera **MIXTA**).

Motivo (medido en W3.3, `evidence/v2.88.16.3`): el simulado sorteaba el venue sobre un
``base_mid`` **plano de 100.0** (``flat_price_script``), y la banda del instrumento OOS
salía de ``R −37,72`` a ``+0,82`` con ``σ(R) = 10,14``, **cruzando el cero**. Sin precio
real el book es casi todo ruido ⇒ ninguna lectura de mérito es separable del dado.

Este módulo define el **seam** que puede decir «**no hay precio**» — algo que
``PriceScript = Callable[[str, int], float]`` NO puede expresar (su único recurso era
mentir con ``100.0`` o ``0``). Dos fronteras, decididas por el propietario (2026-10-01):

  * ``mid(...)``       — referencia de **DECISIÓN** (señal, geometría, régimen, ATR):
    ``close`` de la última barra **CERRADA** (``<= B-1``). Es la frontera de W3
    (``last_closed_bar_day``), estrictamente **sin lookahead**.
  * ``execution(...)`` — **EJECUCIÓN** (*mid* del fill) y **MARCA** (equity, protección):
    ``open``/último precio de la barra **CORRIENTE**. Es el ancla que W3 ya declaró
    (``OPEN(D+1)``) y **es conocido**: no es lookahead.

**Fail-closed (por símbolo).** ``None`` no es un valor: es el estado «no hay precio». El
motor NO lo degrada a una constante: ese símbolo no puede ejecutar (``HOLD``, declarado y
contado) y si **ningún** símbolo tiene precio el turno se declara ``BLOCKED``. Aquí vive
el contrato; la política de turno vive en el worker.

**``Δ = 0`` por construcción.** ``ConstantPriceSource`` envuelve el ``PriceScript``
inyectable (reloj + script del replay y de los tests) devolviendo **exactamente** lo que
el script devolvía, y **nunca** ``None``. Adoptar este seam no mueve un solo precio del
camino hermético: sólo hace *explícito* el default que antes era silencioso.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol, cast, runtime_checkable

logger = logging.getLogger(__name__)

#: Contrato histórico del precio por ``(símbolo, tick de BARRA)``. Se conserva para el
#: camino inyectable (replay/tests); ``ConstantPriceSource`` lo adapta a ``PriceSource``.
PriceScript = Callable[[str, int], float]


@runtime_checkable
class PriceSource(Protocol):
    """Precio por símbolo en el tick de barra corriente — o ``None`` si **no hay precio**.

    ``refresh`` fija la foto del tick (una vez por tick/barra, **async**: el dato sale de PG
    igual que régimen y ATR, y el worker lo espera en el mismo punto); las consultas son
    puras y deterministas dentro del tick. Implementarla NO obliga a heredar de nada: basta
    con los cuatro métodos (Protocol estructural).
    """

    async def refresh(self) -> None:
        """Precarga la foto del tick/barra corriente (una vez por tick)."""
        ...

    def mid(self, symbol: str) -> float | None:
        """Precio de **DECISIÓN**: ``close`` de la última barra cerrada (``<= B-1``)."""
        ...

    def execution(self, symbol: str) -> float | None:
        """Precio de **EJECUCIÓN/MARCA**: ``open`` de la barra corriente (conocido, no lookahead)."""
        ...

    def missing(self, symbols: Sequence[str]) -> tuple[str, ...]:
        """Símbolos de ``symbols`` SIN precio de ejecución ⇒ no ejecutables (``HOLD``)."""
        ...


class ConstantPriceSource:
    """Adapta un ``PriceScript`` constante/inyectable a ``PriceSource`` **sin cambiar nada**.

    ``mid`` y ``execution`` devuelven EXACTAMENTE ``script(símbolo, tick)`` y **nunca**
    ``None`` (salvo que el propio script devuelva ``None``, que ningún script histórico
    hace). Es la garantía de ``Δ = 0`` para replay y tests: adoptar el seam no mueve un
    precio del camino hermético.
    """

    __slots__ = ("_script", "_tick")

    def __init__(self, script: PriceScript) -> None:
        if not callable(script):
            raise TypeError("ConstantPriceSource exige un PriceScript invocable")
        self._script = script
        self._tick = 0

    async def refresh(self, *, tick: int | None = None) -> None:  # noqa: ARG002 (paridad de firma)
        """Fija el tick del script. El worker la invoca SIN argumentos (una vez por tick),
        así que conserva el último; un test puede fijarlo explícitamente."""
        if tick is not None:
            self._tick = int(tick)

    def _price(self, symbol: str) -> float | None:
        value = self._script(symbol, self._tick)
        return None if value is None else float(value)

    def mid(self, symbol: str) -> float | None:
        return self._price(symbol)

    def execution(self, symbol: str) -> float | None:
        return self._price(symbol)

    def missing(self, symbols: Sequence[str]) -> tuple[str, ...]:
        return tuple(s for s in symbols if self._price(s) is None)


class MappingPriceSource:
    """Fuente de precio desde un ``{símbolo: precio}`` — pura, para tests y *dry-run*.

    Un símbolo **ausente** del mapa ⇒ ``None`` (no hay precio), **nunca** un valor por
    defecto. Es el doble que permite ejercitar el fail-closed sin tocar PG.
    """

    __slots__ = ("_prices", "_tick", "_refreshes")

    def __init__(self, prices: Mapping[str, float | None] | None = None) -> None:
        self._prices: dict[str, float | None] = dict(prices or {})
        self._tick = 0
        self._refreshes = 0

    async def refresh(self, *, tick: int | None = None) -> None:  # noqa: ARG002
        if tick is not None:
            self._tick = int(tick)
        self._refreshes += 1

    def mid(self, symbol: str) -> float | None:
        return self._prices.get(symbol)

    def execution(self, symbol: str) -> float | None:
        return self._prices.get(symbol)

    def missing(self, symbols: Sequence[str]) -> tuple[str, ...]:
        return tuple(s for s in symbols if self._prices.get(s) is None)

    @property
    def refreshes(self) -> int:
        """Nº de ``refresh`` observados (prueba de que la foto es una por tick)."""
        return self._refreshes


class OhlcvPriceSource:
    """Proveedor de precio REAL desde el repositorio de barras (frontera **MIXTA**, §3.1).

    Una sola lectura por tick con ``as_of = día(B)`` (la barra corriente INCLUIDA) que se
    parte en dos fronteras:

    * ``mid`` = ``close`` de la última barra con **día `< B`** (la última CERRADA) — lo usa
      la geometría de la decisión, sin lookahead.
    * ``execution`` = ``open`` de la barra con **día `== B`** (la corriente) — lo usan el
      *fill* y la marca; es un precio **conocido**, no lookahead.

    Si la barra ``B`` no está (vivo/PAPER antes de persistir el día, opción (a) del
    propietario) ⇒ ``execution`` es ``None`` ⇒ fail-closed por símbolo. **Jamás** se cae a
    la barra ``B-1``: un precio rancio es exactamente el fallback que ``W4`` mata.

    ``refresh`` es **async** y sin argumentos (mismo contrato que régimen y ATR): el
    ``symbols``/``as_of``/``timeframe`` se fijan al componer, y el ``as_of`` es un
    **provider** que lee el reloj del worker, así que la frontera se mueve entre ticks sin
    recomponer el objeto.
    """

    def __init__(
        self,
        ohlcv: Any,
        symbols: Sequence[str],
        *,
        as_of: Any,
        timeframe: Any = None,
        limit: int = 120,
    ) -> None:
        self._ohlcv = ohlcv
        self._symbols = tuple(str(s) for s in symbols)
        self._as_of = as_of
        self._timeframe = timeframe
        self._limit = limit
        self._mid: dict[str, float] = {}
        self._exec: dict[str, float] = {}

    async def refresh(self) -> None:
        """Una lectura por símbolo con ``as_of = día(B)``; parte la ventana en las dos fronteras."""
        from bolsa_application.closed_bars import (  # noqa: PLC0415
            bar_day,
            clamp_bars_as_of,
            resolve_as_of,
        )

        day_b = resolve_as_of(self._as_of)
        mid: dict[str, float] = {}
        exec_: dict[str, float] = {}
        if not day_b:
            self._mid, self._exec = mid, exec_
            return
        timeframe = self._timeframe if self._timeframe is not None else _default_timeframe()
        for symbol in self._symbols:
            try:
                try:
                    bars = await self._ohlcv.get_bars(
                        symbol, timeframe=timeframe, limit=self._limit, date_to=day_b
                    )
                except TypeError:
                    # Port sin ``date_to`` (firma reducida): se pide sin filtro y la guardia
                    # en cliente acota (misma disciplina que ``make_closed_bar_loader``).
                    bars = await self._ohlcv.get_bars(
                        symbol, timeframe=timeframe, limit=self._limit
                    )
            except Exception:  # noqa: BLE001 — sin barras ⇒ ese símbolo no tiene precio.
                logger.debug("price source: no bars for %s", symbol, exc_info=True)
                continue
            for bar in reversed(clamp_bars_as_of(bars, day_b)):
                day = bar_day(bar)
                if not day:
                    continue
                if day < day_b:
                    close = _finite_field(bar, "close")
                    if close is not None:
                        mid[symbol] = close
                    break  # la primera barra hacia atrás ya es la última CERRADA (< B).
            for bar in reversed(clamp_bars_as_of(bars, day_b)):
                if bar_day(bar) != day_b:
                    continue
                open_ = _finite_field(bar, "open")
                if open_ is not None:
                    exec_[symbol] = open_
                break  # solo la ÚLTIMA barra del día B (la corriente).
        self._mid, self._exec = mid, exec_

    def mid(self, symbol: str) -> float | None:
        return self._mid.get(symbol)

    def execution(self, symbol: str) -> float | None:
        return self._exec.get(symbol)

    def missing(self, symbols: Sequence[str]) -> tuple[str, ...]:
        return tuple(s for s in symbols if self._exec.get(s) is None)


def _finite_field(bar: Any, name: str) -> float | None:
    """Campo numérico finito de una barra (dataclass/Mapping/atributo); ``None`` si no.

    ``high``/``low``/``close`` de la barra corriente NO se leen nunca: sólo se pide ``open``
    de ``B`` y ``close`` de ``< B`` (leer ``close(B)`` sería lookahead).
    """
    value = bar.get(name) if isinstance(bar, Mapping) else getattr(bar, name, None)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _default_timeframe() -> Any:
    from bolsa_domain.value_objects.timeframe import TimeFrame  # noqa: PLC0415

    return TimeFrame.D1


def as_price_source(provided: PriceSource | PriceScript) -> PriceSource:
    """Normaliza el seam: un ``PriceScript`` se envuelve; un ``PriceSource`` pasa tal cual.

    **Sin default silencioso**: aquí NO se elige ``100.0`` ni ``0``. Quien no tenga fuente
    debe decidirlo explícitamente (el worker conserva ``flat_price_script`` como default
    *declarado* del camino hermético, no como fallback invisible).
    """
    if hasattr(provided, "mid") and hasattr(provided, "execution"):
        return cast("PriceSource", provided)  # ya es un PriceSource (estructural)
    if not callable(provided):
        raise TypeError(
            "as_price_source exige un PriceSource o un PriceScript; "
            f"recibido {type(provided).__name__}",
        )
    return ConstantPriceSource(provided)
