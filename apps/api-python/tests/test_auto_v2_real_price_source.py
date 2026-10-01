"""W4 (``v2.88.17-beta``) — seam de precio con estado «no hay precio» (puro, sin PG).

``W4`` mata el ``100.0`` **silencioso** del simulado. El obstáculo de fondo es que
``PriceScript = Callable[[str, int], float]`` **no puede expresar ausencia**: su único
recurso era mentir con ``100.0`` (``base_mid``) o ``0`` (geometría y el *mark* de equity).
Este módulo prueba el seam nuevo en su plano puro:

1. **``Δ = 0``**: ``ConstantPriceSource`` devuelve EXACTAMENTE lo que devolvía el script,
   para todo ``(símbolo, tick)``, y **nunca** ``None``. Envolver ``flat_price_script``
   reproduce ``100.0`` — el camino hermético (replay y tests) no se mueve.
2. **Ausencia ≠ valor**: ``None`` es el estado «no hay precio», y ninguna fuente de este
   módulo lo degrada a un default (ni ``MappingPriceSource`` ni el adaptador).
3. **Sin default silencioso**: ``as_price_source`` no elige precio por nadie; un objeto no
   invocable revienta en vez de caer a una constante.

La política de turno (``HOLD`` por símbolo, ``BLOCKED`` si no hay ningún precio) NO vive
aquí: vive en el worker y se prueba en su suite (paso 2 del plan ``W4``).
"""

from __future__ import annotations

import pytest

from bolsa_api.background.auto_price_provider import (
    ConstantPriceSource,
    MappingPriceSource,
    PriceSource,
    as_price_source,
)
from bolsa_api.background.auto_simulation_worker import flat_price_script

# ── 1. Δ = 0: el adaptador no mueve un precio del camino hermético ──────────────


def test_constant_source_reproduces_the_script_exactly() -> None:
    """``mid`` y ``execution`` devuelven EXACTAMENTE ``script(símbolo, tick)``."""
    seen: list[tuple[str, int]] = []

    def script(symbol: str, tick: int) -> float:
        seen.append((symbol, tick))
        return 10.0 + tick + len(symbol)

    source = ConstantPriceSource(script)
    for tick in (0, 1, 42, 2099):
        source.refresh(tick=tick, symbols=("AAA", "BBBB"))
        for symbol in ("AAA", "BBBB"):
            expected = 10.0 + tick + len(symbol)
            assert source.mid(symbol) == expected
            assert source.execution(symbol) == expected
    # El contrato temporal se conserva: el script recibe el tick de BARRA que le pasa el motor.
    assert (("AAA", 2099) in seen) and (("BBBB", 0) in seen)


def test_constant_source_over_flat_script_is_the_old_100_0_path() -> None:
    """``flat_price_script`` (100.0) sigue dando ``100.0`` en las DOS fronteras.

    Es el invariante de ``Δ = 0``: adoptar el seam NO cambia el replay ni los tests, sólo
    hace *explícito* el default que antes era invisible en el worker.
    """
    source = ConstantPriceSource(flat_price_script)
    source.refresh(tick=1234, symbols=("AAPL",))
    assert source.mid("AAPL") == 100.0
    assert source.execution("AAPL") == 100.0
    assert source.missing(("AAPL",)) == ()


def test_constant_source_is_deterministic_and_never_none() -> None:
    """Mismo tick ⇒ mismo precio; y ``ConstantPriceSource`` nunca inventa ``None``."""
    source = ConstantPriceSource(flat_price_script)
    source.refresh(tick=7, symbols=("X",))
    assert source.mid("X") == source.mid("X") == 100.0
    # Un símbolo DESCONOCIDO tampoco es ``None``: el camino inyectable es total por contrato.
    assert source.mid("DESCONOCIDO") == 100.0
    assert source.missing(("X", "DESCONOCIDO")) == ()


# ── 2. Ausencia ≠ valor ────────────────────────────────────────────────────────


def test_mapping_source_reports_absence_as_none_not_a_default() -> None:
    """Un símbolo AUSENTE ⇒ ``None``. Nunca ``0``, nunca ``100.0``, nunca el vecino."""
    source = MappingPriceSource({"CON_PRECIO": 57.25})
    source.refresh(tick=3, symbols=("CON_PRECIO", "SIN_PRECIO"))
    assert source.mid("CON_PRECIO") == 57.25
    assert source.mid("SIN_PRECIO") is None
    assert source.execution("SIN_PRECIO") is None
    assert source.missing(("CON_PRECIO", "SIN_PRECIO")) == ("SIN_PRECIO",)


def test_mapping_source_explicit_none_is_absence() -> None:
    """``{símbolo: None}`` es ausencia explícita, no el precio ``0``."""
    source = MappingPriceSource({"A": None, "B": 0.0})
    source.refresh(tick=1, symbols=("A", "B"))
    assert source.mid("A") is None
    assert source.execution("A") is None
    # ``0.0`` SÍ es un valor presente (un precio real no se confunde con ausencia).
    assert source.mid("B") == 0.0
    assert source.execution("B") == 0.0
    assert source.missing(("A", "B")) == ("A",)


def test_mapping_source_empty_means_everything_missing() -> None:
    """Sin mapa ⇒ ningún símbolo tiene precio (la puerta al ``BLOCKED`` del turno)."""
    source = MappingPriceSource()
    source.refresh(tick=0, symbols=("A", "B"))
    assert source.missing(("A", "B")) == ("A", "B")


def test_refresh_is_one_photo_per_tick() -> None:
    """``refresh`` se invoca una vez por tick (observable; el worker lo hace una vez/turno)."""
    source = MappingPriceSource({"A": 5.0})
    source.refresh(tick=1, symbols=("A",))
    source.refresh(tick=2, symbols=("A",))
    assert source.refreshes == 2


# ── 3. Sin default silencioso en el adaptador ──────────────────────────────────


def test_as_price_source_passes_a_source_through_unchanged() -> None:
    """Un ``PriceSource`` ya construido no se re-envuelve (identidad)."""
    source = MappingPriceSource({"A": 1.0})
    assert as_price_source(source) is source


def test_as_price_source_wraps_a_plain_script() -> None:
    """Un ``PriceScript`` suelto se adapta conservando su valor exacto."""
    adapted = as_price_source(flat_price_script)
    assert isinstance(adapted, ConstantPriceSource)
    adapted.refresh(tick=9, symbols=("A",))
    assert adapted.mid("A") == 100.0 and adapted.execution("A") == 100.0


def test_as_price_source_refuses_a_non_callable_instead_of_defaulting() -> None:
    """Sin fuente, REVIENTA: no hay ``100.0`` de consolación."""
    with pytest.raises(TypeError):
        as_price_source(100.0)  # type: ignore[arg-type]


# ── 4. El Protocol distingue «puede expresar ausencia» ────────────────────────


def test_protocol_is_satisfied_by_real_sources_but_not_by_a_bare_script() -> None:
    """``ConstantPriceSource``/``MappingPriceSource`` son ``PriceSource``; un lambda NO.

    La distinción es el punto de ``W4``: un ``PriceScript`` no puede decir «no hay precio».
    """
    assert isinstance(ConstantPriceSource(flat_price_script), PriceSource)
    assert isinstance(MappingPriceSource({"A": 1.0}), PriceSource)
    assert not isinstance(lambda _s, _t: 100.0, PriceSource)


def test_constant_source_rejects_a_non_callable_script() -> None:
    """El adaptador no acepta basura como si fuera una fuente de precio."""
    with pytest.raises(TypeError):
        ConstantPriceSource(42.0)  # type: ignore[arg-type]
