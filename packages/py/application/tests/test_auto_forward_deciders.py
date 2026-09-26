"""V2.76 · AUTO-MATERIAL-4 — deciders versionados del PAPER forward.

Contratos que se fijan aquí:

* ``split_watch`` parte el universo en dos tramos **disjuntos y exhaustivos**, deterministas.
* La versión A propone ``BUY`` sólo con el símbolo PLANO, con ``source = auto-2.0:<version>``
  (el prefijo que el worker usa para atribuir el fill) y ``HOLD`` con posición.
* Una lectura de posición que FALLA no se lee como "plano": ``HOLD`` (fail-closed, no apila).
* El enrutador entrega cada símbolo a SU versión; el resto a la versión B.
"""

from __future__ import annotations

from collections.abc import Callable

from bolsa_application.auto_forward_deciders import (
    FORWARD_VERSION_SOURCE_PREFIX,
    SplitWatchDecider,
    VersionedReentryDecider,
    build_forward_pair_decider,
    split_watch,
)
from bolsa_application.decision_contract import DecisionPackage

# ── split_watch ────────────────────────────────────────────────────────────────


def test_split_watch_is_disjoint_exhaustive_and_deterministic() -> None:
    """Los dos tramos no se solapan, cubren el universo y no dependen del orden de entrada."""
    first, second = split_watch(["CCC", "AAA", "BBB", "DDD"])
    assert first == ("AAA", "BBB")
    assert second == ("CCC", "DDD")
    assert set(first) & set(second) == set()
    assert set(first) | set(second) == {"AAA", "BBB", "CCC", "DDD"}
    # Mismo resultado con el universo desordenado y con duplicados.
    assert split_watch(["DDD", "AAA", "BBB", "CCC", "AAA"]) == (first, second)


def test_split_watch_normalizes_blank_and_duplicate_symbols() -> None:
    first, second = split_watch([" AAA ", "", "AAA", "BBB"])
    assert first == ("AAA",)
    assert second == ("BBB",)


def test_split_watch_single_symbol_goes_to_a_and_leaves_b_empty() -> None:
    """Con un solo símbolo no hay par posible: A lo recibe y B queda vacío (se declara)."""
    assert split_watch(["AAA"]) == (("AAA",), ())


def test_split_watch_empty_universe_yields_two_empty_tramos() -> None:
    assert split_watch([]) == ((), ())


def test_split_watch_share_is_clamped_so_both_tramos_keep_a_symbol() -> None:
    """Aunque se pida 0 % o 100 %, cada tramo conserva al menos un símbolo (si hay >= 2)."""
    assert split_watch(["AAA", "BBB"], a_share=0.0) == (("AAA",), ("BBB",))
    assert split_watch(["AAA", "BBB"], a_share=1.0) == (("AAA",), ("BBB",))


# ── VersionedReentryDecider ────────────────────────────────────────────────────


def test_versioned_reentry_buys_when_flat_and_stamps_the_version() -> None:
    decider = VersionedReentryDecider(
        watch=("AAA",), version="v76-a", held_quantity=lambda _s: 0.0, lot_qty=100.0
    )

    package = decider("AAA")
    assert package.action == "BUY"
    assert package.instrument_id == "AAA"
    assert package.quantity == 100.0
    assert package.source == f"{FORWARD_VERSION_SOURCE_PREFIX}:v76-a"


def test_versioned_reentry_holds_while_a_position_is_open() -> None:
    """Con posición viva NO se vuelve a proponer: el ciclo se cierra por el ExitPlan, no aquí."""
    decider = VersionedReentryDecider(
        watch=("AAA",), version="v76-a", held_quantity=lambda _s: 100.0
    )

    package = decider("AAA")
    assert package.action == "HOLD"
    assert package.source == f"{FORWARD_VERSION_SOURCE_PREFIX}:v76-a"


def test_versioned_reentry_holds_outside_its_watch() -> None:
    decider = VersionedReentryDecider(watch=("AAA",), version="v76-a", held_quantity=lambda _s: 0.0)

    package = decider("ZZZ")
    assert package.action == "HOLD"
    assert package.instrument_id == "ZZZ"


def test_versioned_reentry_position_read_failure_is_fail_closed() -> None:
    """Sin lectura fiable de posición NO se asume plano: ``HOLD`` (no se apila)."""

    def _boom(_symbol: str) -> float:
        raise RuntimeError("libro ilegible")

    decider = VersionedReentryDecider(watch=("AAA",), version="v76-a", held_quantity=_boom)

    assert decider("AAA").action == "HOLD"


# ── SplitWatchDecider ──────────────────────────────────────────────────────────


def _echo(action: str, source: str) -> Callable[[str], DecisionPackage]:
    def _decide(symbol: str) -> DecisionPackage:
        return DecisionPackage(action=action, instrument_id=symbol, quantity=1.0, source=source)

    return _decide


def test_split_routes_a_symbols_to_a_and_everything_else_to_b() -> None:
    router = SplitWatchDecider(
        watch_a=frozenset({"AAA"}),
        decider_a=_echo("BUY", "auto-2.0:v76-a"),
        decider_b=_echo("SELL", "active-strategy:v76-b"),
    )

    assert router("AAA").source == "auto-2.0:v76-a"
    assert router("BBB").source == "active-strategy:v76-b"


def test_build_forward_pair_decider_wires_both_versions() -> None:
    """El par real: A determinista sobre su watch y B (ACTIVE) para el resto."""
    router = build_forward_pair_decider(
        watch_a=("AAA",),
        version_a="v76-a",
        decider_b=_echo("SELL", "active-strategy:v76-b"),
        held_quantity=lambda _s: 0.0,
    )

    assert router("AAA").action == "BUY"
    assert router("AAA").source == "auto-2.0:v76-a"
    assert router("BBB").action == "SELL"
    assert router("BBB").source == "active-strategy:v76-b"
