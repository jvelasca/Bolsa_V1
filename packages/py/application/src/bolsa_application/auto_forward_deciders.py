"""V2.76 · AUTO-MATERIAL-4 — deciders versionados del PAPER forward (par REAL de estrategias).

Por qué existe: cerrar ``P3-2`` (correlación por cubos temporales) exige **≥2 versiones de
estrategia** operando sobre los MISMOS cubos de tiempo en UNA cuenta. El worker AUTO consulta UN
solo ``DecisionProvider`` por tick (``_v2_collect_packages``), así que la única forma de que dos
versiones convivan es un decider COMPUESTO que enrute por símbolo.

Las dos piezas (puras, sin I/O; el I/O lo compone el runner):

* :class:`VersionedReentryDecider` — versión **A** determinista: propone ``BUY`` mientras el símbolo
  está PLANO y ``HOLD`` con posición. Es el mecanismo probado en ``v2.75`` (``_RoundTrip``): la
  SALIDA no la pide el decider, la dispara el ``ExitPlan`` estructural del motor V2 cuando el precio
  de MERCADO se mueve; y como sólo propone entradas, el ciclo se re-encadena solo (al quedar plano,
  el siguiente tick vuelve a proponer). El ``source`` es ``auto-2.0:<version>``, prefijo que el
  worker ya reconoce (``_strategy_version_from_source``) para atribuir el fill a la versión.
* :class:`SplitWatchDecider` — enrutador: el watch de la versión A va a ``decider_a``; el resto va a
  ``decider_b`` (la estrategia ACTIVE, que internamente hace ``HOLD`` para los símbolos fuera de su
  propio watch). Así las dos versiones operan a la vez sin que el worker sepa que existen dos.

Nota de honestidad sobre "spine": el ``AutoDecisionEngine`` del spine NO sirve para encadenar ciclos
porque entra en ``COOLDOWN`` tras su ``SELL`` y no vuelve a abrir (un solo ciclo por símbolo y
proceso). Por eso la versión A usa un re-entrada determinista equivalente pero SIN cooldown. El
motor sigue siendo el único que decide: aquí sólo se PROPONE.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from bolsa_application.decision_contract import DecisionPackage

#: ``DecisionProvider`` = ``Callable[[str], DecisionPackage]`` (alias local para no acoplar la
#: capa de aplicación al proceso HTTP/worker, igual que ``auto_decision_engine``).
DecisionProvider = Callable[[str], DecisionPackage]

#: Prefijo de ``source`` con que la versión A se declara. Es EL MISMO que reconoce el worker
#: (``_V2_ENTRY_SOURCE_PREFIX``) para atribuir el fill/cierre a la versión de estrategia.
FORWARD_VERSION_SOURCE_PREFIX = "auto-2.0"

__all__ = [
    "FORWARD_VERSION_SOURCE_PREFIX",
    "SplitWatchDecider",
    "VersionedReentryDecider",
    "build_forward_pair_decider",
    "split_watch",
]


def _hold(symbol: str, source: str) -> DecisionPackage:
    return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0, source=source)


def _normalize_watch(watch: Sequence[str]) -> tuple[str, ...]:
    """Watch canónico: sin vacíos, sin duplicados y ordenado (determinismo reproducible)."""
    return tuple(sorted({text for text in (str(s).strip() for s in watch) if text}))


def split_watch(
    watch: Sequence[str],
    *,
    a_share: float = 0.5,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(PURA) Parte el universo del watch en ``(watch_a, watch_b)`` de forma determinista.

    Ordena el universo y asigna a la versión A el primer tramo según ``a_share``; el resto va a B.
    Los dos tramos son **disjuntos y exhaustivos** sobre el watch normalizado. Con un solo símbolo,
    A lo recibe y B queda vacío (se declara: con menos de dos símbolos no hay par posible).
    """
    ordered = _normalize_watch(watch)
    if not ordered:
        return (), ()
    if len(ordered) == 1:
        return ordered, ()
    share = float(a_share)
    share = 0.0 if share != share else min(1.0, max(0.0, share))
    cut = round(len(ordered) * share)
    cut = max(1, min(len(ordered) - 1, cut))
    return ordered[:cut], ordered[cut:]


@dataclass(frozen=True, slots=True)
class VersionedReentryDecider:
    """Versión determinista que re-entra cuando el símbolo está plano (SIN cooldown).

    ``held_quantity`` es la lectura de la posición VIVA (el runner la cablea al libro del worker,
    como ``v2.75``). Una lectura que falla NO se interpreta como "plano": se devuelve ``HOLD``
    (fail-closed), porque proponer una entrada sin saber si hay posición podría apilar.
    """

    watch: tuple[str, ...]
    version: str
    held_quantity: Callable[[str], float]
    lot_qty: float = 100.0
    _watch_set: frozenset[str] = field(default=frozenset(), init=False, repr=False)
    _source: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "watch", _normalize_watch(self.watch))
        object.__setattr__(self, "_watch_set", frozenset(self.watch))
        object.__setattr__(
            self, "_source", f"{FORWARD_VERSION_SOURCE_PREFIX}:{str(self.version).strip()}"
        )

    def __call__(self, symbol: str) -> DecisionPackage:
        key = str(symbol or "").strip()
        if key not in self._watch_set:
            return _hold(key, self._source)
        try:
            held = float(self.held_quantity(key) or 0.0)
        except Exception:  # noqa: BLE001 — sin lectura fiable de posición ⇒ HOLD, nunca apilar.
            return _hold(key, self._source)
        if held > 0:
            return _hold(key, self._source)
        return DecisionPackage(
            action="BUY",
            instrument_id=key,
            quantity=float(self.lot_qty),
            source=self._source,
        )


@dataclass(frozen=True, slots=True)
class SplitWatchDecider:
    """Enruta por símbolo: ``watch_a`` → versión A; el resto → versión B (la ACTIVE)."""

    watch_a: frozenset[str]
    decider_a: DecisionProvider
    decider_b: DecisionProvider

    def __call__(self, symbol: str) -> DecisionPackage:
        key = str(symbol or "").strip()
        if key in self.watch_a:
            return self.decider_a(key)
        return self.decider_b(key)


def build_forward_pair_decider(
    *,
    watch_a: Sequence[str],
    version_a: str,
    decider_b: DecisionProvider,
    held_quantity: Callable[[str], float],
    lot_qty: float = 100.0,
) -> SplitWatchDecider:
    """Compone el par real: versión A determinista + versión B (estrategia ACTIVE) enrutadas.

    ``decider_b`` es el proveedor de la estrategia ACTIVE ya construido (p. ej.
    ``make_active_strategy_decider``); se le entrega TODO símbolo que no esté en ``watch_a`` y él
    hace ``HOLD`` para los que queden fuera de su propio watch (fail-closed ya probado).
    """
    decider_a = VersionedReentryDecider(
        watch=tuple(watch_a),
        version=version_a,
        held_quantity=held_quantity,
        lot_qty=lot_qty,
    )
    return SplitWatchDecider(
        watch_a=frozenset(decider_a.watch),
        decider_a=decider_a,
        decider_b=decider_b,
    )
