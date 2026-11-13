"""Tests: prefs UI override vs flags servidor para email Alarmas."""

import re
from types import SimpleNamespace

import pytest

from bolsa_infrastructure.alerts import estudio_opinion_email as email_mod
from bolsa_infrastructure.alerts.estudio_opinion_email import (
    maybe_notify_estudio_alarmas,
    reason_labels,
    stance_detail,
    stance_label,
)


def _settings(**kwargs):
    base = dict(
        estudio_opinion_email_enabled=False,
        estudio_opinion_email_to=None,
        smtp_host=None,
        smtp_from=None,
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _alarma_row():
    return SimpleNamespace(
        instrument_id="inst-1",
        stance="buy",
        dictamen_stars=5,
        as_of_bar_date="2026-08-04",
        reasons=["test"],
    )


@pytest.mark.asyncio
async def test_client_prefs_disabled_skips() -> None:
    meta = await maybe_notify_estudio_alarmas(
        _settings(smtp_host="smtp.example", smtp_from="a@b.c"),
        [_alarma_row()],
        email_to="user@example.com",
        email_enabled=False,
    )
    assert meta["sent"] is False
    assert meta["skipped_reason"] == "email_disabled"
    assert meta["alarma_count"] == 1


@pytest.mark.asyncio
async def test_client_prefs_empty_email_skips() -> None:
    meta = await maybe_notify_estudio_alarmas(
        _settings(smtp_host="smtp.example", smtp_from="a@b.c"),
        [_alarma_row()],
        email_to="",
        email_enabled=True,
    )
    assert meta["sent"] is False
    assert meta["skipped_reason"] == "email_to vacío"


@pytest.mark.asyncio
async def test_client_prefs_smtp_missing() -> None:
    meta = await maybe_notify_estudio_alarmas(
        _settings(),
        [_alarma_row()],
        email_to="user@example.com",
        email_enabled=True,
    )
    assert meta["sent"] is False
    assert "SMTP" in (meta["skipped_reason"] or "")


# ── Cuerpo del email: lenguaje de producto, nunca claves internas ────────────

_INTERNAL_STANCE_KEYS = (
    "buy",
    "hold_watch",
    "overbought",
    "reduce",
    "sell_exit",
    "no_trade",
    "review_strategy",
)


def _body_row(
    stance: str,
    reasons: list[str],
    *,
    io_score: float | None = 72.0,
    stars: int = 4,
) -> SimpleNamespace:
    return SimpleNamespace(
        instrument_id="inst-1",
        stance=stance,
        dictamen_stars=stars,
        as_of_bar_date="2026-08-04",
        reasons=reasons,
        io_score=io_score,
    )


def test_stance_labels_never_repeat_the_internal_key() -> None:
    for key in _INTERNAL_STANCE_KEYS:
        label = stance_label(key)
        assert label != key, key
        assert not re.search(r"[a-z]+_[a-z]+", label), label
    assert stance_label("buy") == "Comprar"
    assert stance_label("hold_watch") == "Mantener"
    assert stance_label("overbought") == "Sin respaldo"


def test_no_trade_label_depends_on_the_declared_cause() -> None:
    assert stance_label("no_trade", ["position_unmeasured"]) == "No evaluable"
    assert stance_detail("no_trade", ["position_unmeasured"]) == "Cartera sin medir"
    assert stance_label("no_trade", ["eod_data_stale"]) == "No operar"
    assert stance_label("no_trade", ["gate_veto"]) == "Operativa bloqueada"


def test_reason_labels_skip_diagnostics_and_duplicates() -> None:
    labels = reason_labels(["gate_veto", "io_low", "io_low", "top_low"])
    assert labels == ["Calidad de señal baja", "Estrategia del Lab sin respaldo"]
    assert reason_labels(["desconocido"]) == []


def test_email_body_never_prints_internal_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_send(_settings, message) -> None:  # noqa: ANN001
        captured["message"] = message

    monkeypatch.setattr(email_mod, "_send_smtp_message", fake_send)

    email_mod.send_estudio_alarma_email_sync(
        _settings(smtp_host="smtp.example", smtp_from="a@b.c"),
        recipient="user@example.com",
        alarmas=[
            _body_row("buy", ["strong_buy_signal", "top_high", "io_high"], stars=5),
            _body_row("no_trade", ["position_unmeasured"], io_score=None, stars=3),
        ],
        symbol_by_id={"inst-1": "BBVA"},
    )

    message = captured["message"]
    body = message.get_content()  # type: ignore[attr-defined]

    for key in _INTERNAL_STANCE_KEYS + ("position_unmeasured", "strong_buy_signal"):
        assert key not in body, key
    # Ninguna clave snake_case visible.
    assert re.search(r"[a-z]+_[a-z]+", body) is None
    assert "Comprar" in body
    assert "No evaluable" in body
    assert "Cartera sin medir" in body
    # IO sin medir no se pinta como ★3 fabricado.
    assert body.count("Sin medir") == 1
