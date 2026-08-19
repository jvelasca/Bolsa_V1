"""Tests Q2.4 log redact + F-SEG-2 redacción negativa de credenciales en logs."""

import logging

from bolsa_api.logging_redact import RedactFilter, install_log_redact, redact_text


def test_redact_authorization_and_password() -> None:
    s = redact_text("Authorization: Bearer secret-token password=hunter2")
    assert "secret-token" not in s
    assert "hunter2" not in s
    assert "***" in s


# F-SEG-2: los valores reales de credenciales no deben colar en un log aunque
# aparezcan en los pares clave=valor o scheme de auth típicos.

_REAL = ("app_password=ReaL-cRed123", "app_auth_secret=ReAl-sIgN123", "db_password=d-B-Pass99")


def test_redact_credential_pairs_never_echo_values() -> None:
    line = " ".join(_REAL) + " Authorization: Bearer abc-def-123"
    out = redact_text(line)
    for value in ("ReaL-cRed123", "ReAl-sIgN123", "d-B-Pass99", "abc-def-123"):
        assert value not in out
    assert "***" in out


def test_redact_filter_masks_real_values_in_log_records() -> None:
    """Un log emitido con el filtro instalado no debe contener los valores reales."""
    install_log_redact()
    records: list[str] = []
    handler = logging.Handler()
    handler.setLevel(logging.INFO)
    handler.emit = lambda record: records.append(record.getMessage())  # type: ignore[method-assign]
    logger = logging.getLogger("test.fseg2")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    logger.addFilter(RedactFilter())
    try:
        logger.info(
            "login attempt password=suP3r-SeCrEt api_key=api-Live-Key "
            "app_auth_secret=ReAl-sIgN123 Authorization: Bearer live-token-9"
        )
    finally:
        logger.removeHandler(handler)
        logger.removeFilter(RedactFilter())

    assert len(records) == 1
    assert "suP3r-SeCrEt" not in records[0]
    assert "api-Live-Key" not in records[0]
    assert "ReAl-sIgN123" not in records[0]
    assert "live-token-9" not in records[0]
