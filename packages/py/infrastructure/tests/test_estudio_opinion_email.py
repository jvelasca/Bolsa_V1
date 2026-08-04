"""Tests: mapa canal Alarmas Estudio (espejo TS §5.2)."""

from bolsa_infrastructure.alerts.estudio_opinion_email import map_opinion_to_channel


def test_buy_stars_to_channel() -> None:
    assert map_opinion_to_channel(stance="buy", dictamen_stars=5) == "alarma"
    assert map_opinion_to_channel(stance="buy", dictamen_stars=4) == "alarma"
    assert map_opinion_to_channel(stance="buy", dictamen_stars=3) == "aviso"
    assert map_opinion_to_channel(stance="buy", dictamen_stars=1) == "silent"


def test_exit_reduce_to_channel() -> None:
    assert map_opinion_to_channel(stance="sell_exit", dictamen_stars=3) == "alarma"
    assert map_opinion_to_channel(stance="reduce", dictamen_stars=2) == "aviso"


def test_hold_silent() -> None:
    assert map_opinion_to_channel(stance="hold_watch", dictamen_stars=5) == "silent"
    assert map_opinion_to_channel(stance="no_trade", dictamen_stars=5) == "silent"
