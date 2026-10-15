"""Tests Q2.4 log redact + F-SEG-2 redacción negativa de credenciales en logs."""

import logging

from bolsa_api.logging_redact import install_log_redact, redact_text


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


def test_redact_filter_masks_real_values_in_log_records(
    logging_redact_state: None,
) -> None:
    """Un log emitido por un logger HIJO no debe contener los valores reales.

    Antes esta prueba añadía `RedactFilter` al MISMO logger que emitía — probaba el filtro
    pero no el wiring real. Ahora se instala `install_log_redact()` y se emite desde un
    descendiente (`logging.getLogger(__name__)`), que es el patrón del código de la app:
    el registro propaga al handler de root y allí debe quedar redactado.
    """
    records: list[str] = []
    handler = logging.Handler()
    handler.setLevel(logging.INFO)
    handler.emit = lambda record: records.append(record.getMessage())  # type: ignore[method-assign]
    root = logging.getLogger()
    root.addHandler(handler)
    previous_level = root.level
    root.setLevel(logging.INFO)
    try:
        install_log_redact()
        logging.getLogger("bolsa_api.background.scan_worker").info(
            "login attempt password=suP3r-SeCrEt api_key=api-Live-Key "
            "app_auth_secret=ReAl-sIgN123 Authorization: Bearer live-token-9"
        )
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)

    assert len(records) == 1
    for value in ("suP3r-SeCrEt", "api-Live-Key", "ReAl-sIgN123", "live-token-9"):
        assert value not in records[0]
    assert "***" in records[0]
