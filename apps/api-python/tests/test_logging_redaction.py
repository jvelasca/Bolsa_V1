"""Fija la redacción de credenciales en logs / representación (auditoría `G6`, P3).

Hermético: sin PG, sin red, sin `get_settings` real (se instancia `Settings` con
`_env_file=None` y entorno por `monkeypatch`). Ejercita las FUNCIONES/CLASES REALES
(`redact_text`, `RedactFilter`, `Settings.__repr__`, `_redact_dsn_credentials`) en lugar
de copiar la lógica.

Ancla en el código real:
* `apps/api-python/src/bolsa_api/logging_redact.py` — `authorization`/`api-key`/
  `password` y las credenciales de la app (`app_password`/`app_auth_secret`/
  `db_password`/`xtb_user`/`xtb_pass`/`xtb_token`).
* `packages/py/infrastructure/src/bolsa_infrastructure/config.py` — `repr(Settings)` y
  el DSN (`_redact_dsn_credentials`).
* `.gitignore` — excluye `.env`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from bolsa_api import logging_redact
from bolsa_infrastructure.config import Settings, _redact_dsn_credentials

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: `(secreto, texto)` — el secreto NO debe sobrevivir a `redact_text`.
_SECRET_CASES = (
    ("s3cr3t-token", "Authorization: Bearer s3cr3t-token"),
    ("deadbeef", "api-key=deadbeef"),
    ("deadbeef", "api_key: deadbeef"),
    ("hunter2", "password=hunter2"),
    ("appsecret", "app_password=appsecret"),
    ("authsecret", "app_auth_secret=authsecret"),
    ("dbsecret", "db_password=dbsecret"),
    ("xtbuser", "xtb_user=xtbuser"),
    ("xtbpass", "xtb_pass=xtbpass"),
    ("xtbtoken", "xtb_token=xtbtoken"),
)


@pytest.mark.parametrize(("secret", "text"), _SECRET_CASES)
def test_redact_text_hides_secret(secret: str, text: str) -> None:
    redacted = logging_redact.redact_text(text)
    assert secret not in redacted
    assert "***" in redacted


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("password=hunter2", "password=***"),
        ("api-key=deadbeef", "api-key=***"),
        ("db_password=dbsecret", "db_password=***"),
    ],
)
def test_redact_text_keeps_key_label(text: str, expected: str) -> None:
    """Solo se tapa el VALOR: la clave sigue visible para poder diagnosticar."""
    assert logging_redact.redact_text(text) == expected


def test_redact_filter_scrubs_record_msg() -> None:
    record = logging.LogRecord(
        name="bolsa_api.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Authorization: Bearer top-secret-token",
        args=(),
        exc_info=None,
    )
    logging_redact.RedactFilter().filter(record)
    assert "top-secret-token" not in record.getMessage()


def test_redact_filter_scrubs_tuple_args() -> None:
    record = logging.LogRecord(
        name="bolsa_api.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="%s",
        args=("api-key=abc123",),
        exc_info=None,
    )
    logging_redact.RedactFilter().filter(record)
    assert "abc123" not in record.getMessage()


def test_redact_filter_scrubs_dict_args() -> None:
    record = logging.LogRecord(
        name="bolsa_api.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="%(detail)s",
        args=(),
        exc_info=None,
    )
    # El constructor de LogRecord no acepta un mapping directo; se asigna como en
    # `logger.info("%(detail)s", {"detail": ...})`.
    record.args = {"detail": "password=zzz999"}
    logging_redact.RedactFilter().filter(record)
    assert "zzz999" not in record.getMessage()


# ── repr(Settings) y DSN redactan credenciales ────────────────────────────────────
def test_settings_repr_redacts_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "pw-secret-123")
    monkeypatch.setenv("APP_AUTH_SECRET", "auth-secret-456")
    monkeypatch.setenv("DB_PASSWORD", "db-secret-789")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)
    text = repr(settings)
    assert "pw-secret-123" not in text
    assert "auth-secret-456" not in text
    assert "db-secret-789" not in text
    assert "database_url=" in text


def test_dsn_credentials_redacted_keeps_host_and_db() -> None:
    url = "postgresql+psycopg://bolsa:dsn-secret-xyz@dbhost:5432/bolsa_v1"
    redacted = _redact_dsn_credentials(url)
    assert "dsn-secret-xyz" not in redacted
    assert redacted == "postgresql+psycopg://bolsa:***@dbhost:5432/bolsa_v1"


def test_gitignore_excludes_dotenv() -> None:
    lines = {
        line.strip()
        for line in (_REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    }
    assert ".env" in lines, "`.env` debe estar en .gitignore (credenciales fuera del repo)"
