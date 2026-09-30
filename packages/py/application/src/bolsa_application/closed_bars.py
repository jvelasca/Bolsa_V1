"""Frontera de barras CERRADAS — primitiva pura de NO lookahead (``W3`` · v2.88.16).

Una sola definición de «¿qué barras puede ver una decisión tomada en el instante ``t``?»:
las barras **cerradas** anteriores al inicio de la barra que contiene ``t``. El motor AUTO
la usa para la señal, el régimen, el ATR y el ancla del precio de ejecución; el replay OOS
(``replay_oos``) la usa para su censo y su walk-forward. Compartirla es lo que garantiza
que la frontera del MOTOR y la del instrumento de investigación son la **misma** (una sola
verdad, no dos parecidas que se separan con el tiempo).

Contrato temporal (``ExecutionModel.timing`` = ``next_bar_open``)
----------------------------------------------------------------
La decisión de la barra ``B`` se toma con las barras ``<= B-1`` y la ejecución se ancla a
la barra corriente ``B``:

* ``last_closed_bar_day(moment, timeframe)`` — día ISO de la última barra **cerrada**
  (``B-1``), que es el ``as_of`` de todo dato que alimente la decisión.
* ``bar_tick(moment, timeframe)`` — índice ENTERO de la barra que contiene ``moment``,
  **estable dentro de la barra**: con él se anclan el ``seed`` del fill y la identidad
  lógica de la orden, de modo que un reintento dentro de la misma barra reusa el MISMO
  ``execution_id`` y la liquidación lo resuelve ``already_applied`` (idempotente) en vez
  de abrir una segunda ejecución.
* ``make_closed_bar_loader`` — ``refresh()`` async con la misma forma que el cargador de
  barras del worker, acotado a ``<= as_of`` (``date_to`` en el repositorio + recorte en
  cliente).

Fail-closed por diseño
----------------------
* Sin ``as_of`` resoluble la ventana es **vacía** (``[]``): sin datos que se puedan fechar
  no hay decisión (el motor queda en HOLD), nunca una decisión a ciegas.
* Una barra sin fecha legible se **descarta** (jamás se asume que es del pasado).
* Con una barra **sub-diaria** la frontera no es expresable a día (el filtro ``date_to`` y
  el recorte por día admitirían la barra **en curso**) ⇒ ``last_closed_bar_day`` devuelve
  ``""`` y la ventana queda vacía: no se fabrica una frontera más fina de la que el filtro
  puede sostener.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from bolsa_analytics.cognitive.signal_identity import bar_window, timeframe_seconds
from bolsa_domain.ohlcv_time import parse_bar_timestamp

logger = logging.getLogger(__name__)

__all__ = [
    "bar_day",
    "bar_tick",
    "clamp_bars_as_of",
    "last_closed_bar_day",
    "make_closed_bar_loader",
    "resolve_as_of",
]

#: Segundos de un día: por debajo de esto la frontera «día de la última barra cerrada» NO
#: es expresable (el filtro del repositorio y el recorte en cliente trabajan a día).
_DAY_SECONDS = 86_400


def bar_day(bar: Any) -> str:
    """Día ISO (``YYYY-MM-DD``) de una barra (``OhlcvBar`` o ``Mapping``); ``""`` si no hay."""
    if isinstance(bar, Mapping):
        raw = bar.get("timestamp") or bar.get("date")
    else:
        raw = getattr(bar, "timestamp", None) or getattr(bar, "date", None)
    text = str(raw or "").strip()
    return text[:10] if text else ""


def resolve_as_of(as_of: str | datetime | Callable[[], Any] | None) -> str:
    """Normaliza ``as_of`` (str/datetime/provider) al día ISO ``YYYY-MM-DD``.

    Acepta un **provider** (``Callable[[], ...]``) para que el llamante pueda mover la
    frontera entre ticks sin recomponer el cargador (misma disciplina que el replay).
    """
    value = as_of() if callable(as_of) else as_of
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value or "").strip()[:10]


def clamp_bars_as_of(bars: Sequence[Any] | None, as_of: Any) -> list[Any]:
    """Devuelve SOLO las barras con día ``<= as_of`` (guardia de NO lookahead).

    Es la guardia en CLIENTE, independiente de que el repositorio soporte ``date_to``: una
    barra sin fecha legible se DESCARTA (fail-closed), nunca se asume que es del pasado.
    Sin ``as_of`` resoluble devuelve ``[]`` (sin fecha límite no hay ventana segura).
    """
    limit = resolve_as_of(as_of)
    if not limit:
        return []
    return [bar for bar in (bars or []) if (day := bar_day(bar)) and day <= limit]


def last_closed_bar_day(moment: datetime, timeframe: Any) -> str:
    """Día ISO de la última barra **CERRADA** antes de la barra que contiene ``moment``.

    Es el ``as_of`` de la decisión: si ``moment`` cae en la barra ``B`` (``bar_window``),
    la última barra cerrada es la inmediatamente anterior, y su día es el instante previo
    al inicio de ``B`` (``inicio(B) - 1s``). Anclaje-agnóstico: vale para cualquier
    timeframe con barra diaria o superior, sea cual sea el día de la semana en que el
    calendario ancle la barra.

    Fail-closed: timeframe ilegible, ``moment`` sin zona o barra **sub-diaria** (frontera no
    expresable a día) ⇒ ``""``. Con ``""`` la ventana de barras queda vacía y el motor no
    decide: no se degrada a «las barras de hoy», que es justo el lookahead que esto cierra.
    """
    window = bar_window(moment, timeframe)
    if window is None:
        return ""
    seconds = timeframe_seconds(timeframe)
    if seconds is None or seconds < _DAY_SECONDS:
        return ""
    start = parse_bar_timestamp(window[0])
    return (start - timedelta(seconds=1)).strftime("%Y-%m-%d")


def bar_tick(moment: datetime, timeframe: Any) -> int:
    """Índice ENTERO de la barra que contiene ``moment`` (``0`` si no es legible).

    Es la **unidad de identidad temporal** del motor: constante dentro de una barra y
    distinta entre barras. Se usa para el ``seed`` del fill y para la identidad lógica de
    la orden, que es lo que hace **idempotente** un reintento intra-barra (mismo
    ``execution_id`` ⇒ ``already_applied``, sin segunda ejecución).

    Sin barra legible devuelve ``0``: un ancla CONSTANTE y determinista. Nunca el minuto
    (que es lo que hoy hace que un reintento en el minuto siguiente sea una orden nueva).
    """
    window = bar_window(moment, timeframe)
    seconds = timeframe_seconds(timeframe)
    if window is None or seconds is None or seconds <= 0:
        return 0
    return int(parse_bar_timestamp(window[0]).timestamp() // seconds)


def make_closed_bar_loader(
    ohlcv: Any,
    symbols: Sequence[str],
    as_of: str | datetime | Callable[[], Any] | None,
    *,
    timeframe: Any = None,
    limit: int | None = 10_000,
) -> Callable[[], Awaitable[dict[str, list[Any]]]]:
    """``refresh()`` async que precarga ``{symbol: [barras <= as_of]}`` (NO lookahead).

    Misma FORMA que el cargador de barras de la señal (``make_bar_snapshot_loader``):
    ``refresh()`` async que el worker invoca una vez por tick. La diferencia es la
    FRONTERA: cada símbolo queda acotado a ``día <= as_of``, así que ninguna barra en
    curso (ni posterior) puede entrar en la decisión.

    ``as_of`` acepta ``str``, ``datetime`` o **provider**: con el provider, el motor mueve
    la frontera en cada tick sin recomponer el cargador (una vez por sesión/tick basta).

    El repositorio real soporta ``date_to`` y se usa (menos filas en vuelo); un port de
    test con firma reducida cae al camino sin filtro y la guardia en cliente hace el
    trabajo. Un fallo por símbolo se ignora (ese símbolo se queda sin barras ⇒ HOLD),
    nunca aborta el refresco.
    """
    from bolsa_domain.value_objects.timeframe import TimeFrame  # noqa: PLC0415

    effective_timeframe = timeframe if timeframe is not None else TimeFrame.D1
    watch = tuple(str(s) for s in symbols)

    async def refresh() -> dict[str, list[Any]]:
        day = resolve_as_of(as_of)
        snapshot: dict[str, list[Any]] = {}
        if not day:
            return snapshot
        for symbol in watch:
            try:
                try:
                    bars = await ohlcv.get_bars(
                        symbol,
                        timeframe=effective_timeframe,
                        limit=limit,
                        date_to=day,
                    )
                except TypeError:
                    # Port sin ``date_to`` (firma reducida): se pide sin filtro y la guardia
                    # en cliente acota. No se degrada el invariante, solo se lee de más.
                    bars = await ohlcv.get_bars(symbol, timeframe=effective_timeframe, limit=limit)
            except Exception:  # noqa: BLE001 — sin barras ⇒ ese símbolo no decide (fail-closed).
                logger.debug("closed bars: no bars for %s", symbol, exc_info=True)
                continue
            clamped = clamp_bars_as_of(bars, day)
            if clamped:
                snapshot[str(symbol)] = clamped
        return snapshot

    return refresh
