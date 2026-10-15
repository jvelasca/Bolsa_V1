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

import io
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


# ── Propagación REAL: el filtro debe correr aunque el log venga de un logger hijo ──
#
# Regresión G6 (auditoría 2): `install_log_redact()` adjuntaba el filtro solo
# como `Logger.addFilter`, y el filtro de un logger NO se evalúa sobre los registros que
# propaga un descendiente (`Logger.callHandlers` los entrega directo a los HANDLERS de los
# ancestros). Estos casos emiten por un logger HIJO y leen lo que LLEGA AL HANDLER — el
# camino real de la app (`logging.getLogger(__name__)` en routers y workers).


def test_install_log_redact_redacts_descendant_logger(
    logging_redact_state: None,
) -> None:
    """Un log de un logger hijo (no el que lleva el filtro de logger) queda redactado."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    root.addHandler(handler)
    previous_level = root.level
    root.setLevel(logging.INFO)
    try:
        logging_redact.install_log_redact()
        logging.getLogger("bolsa_api.background.scan_worker").warning(
            "arranque ok xtb_token=SEKRET-XYZ"
        )
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)

    emitted = stream.getvalue()
    assert "SEKRET-XYZ" not in emitted, "el secreto cruzó el handler de root sin redactar"
    assert "***" in emitted


def test_install_log_redact_covers_uvicorn_access_handler(
    logging_redact_state: None,
) -> None:
    """El handler propio de uvicorn.access (propagate=False) también queda redactado."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    access = logging.getLogger("uvicorn.access")
    access.handlers = [handler]
    access.propagate = False
    previous_level = access.level
    access.setLevel(logging.INFO)
    try:
        logging_redact.install_log_redact()
        access.info("10.0.0.1 - api_key=LEAK-ACCESS")
    finally:
        access.setLevel(previous_level)

    emitted = stream.getvalue()
    assert "LEAK-ACCESS" not in emitted
    assert "***" in emitted


def test_install_log_redact_is_idempotent(logging_redact_state: None) -> None:
    """Doble instalación (arranque + reload/worker) no duplica filtros."""
    root = logging.getLogger()
    handler = logging.StreamHandler(io.StringIO())
    root.addHandler(handler)
    logging_redact.install_log_redact()
    logging_redact.install_log_redact()

    assert sum(isinstance(f, logging_redact.RedactFilter) for f in root.filters) == 1
    assert sum(isinstance(f, logging_redact.RedactFilter) for f in handler.filters) == 1
    assert (
        sum(
            isinstance(f, logging_redact.RedactFilter)
            for f in logging.getLogger("bolsa_api").filters
        )
        == 1
    )


@pytest.mark.parametrize(
    "worker_file",
    ["scheduler_worker.py", "queue_poll_worker.py", "arq_worker.py"],
)
def test_worker_entrypoints_install_log_redact(worker_file: str) -> None:
    """Procesos worker que emiten por `getLogger(__name__)` deben instalar la redacción."""
    source = (
        _REPO_ROOT / "apps" / "api-python" / "src" / "bolsa_api" / "workers" / worker_file
    ).read_text(encoding="utf-8")
    assert "install_log_redact()" in source, f"{worker_file} no instala la redacción de logs"


# ── Endurecimiento (auditoría 2, `G6` revisado): más claves + valores NO-str ──────
_NEW_SECRET_CASES = (
    ("cs-1", "client_secret=cs-1"),
    ("jwtkey-2", "jwt_signing_key=jwtkey-2"),
    ("sign-3", "signing_key=sign-3"),
    ("sk-4", "secret_key=sk-4"),
    ("pk-5", "private_key=pk-5"),
    ("rt-6", "refresh_token=rt-6"),
    ("at-7", "access_token=at-7"),
    ("pp-8", "passphrase=pp-8"),
)


@pytest.mark.parametrize(("secret", "text"), _NEW_SECRET_CASES)
def test_redact_text_hides_extended_key_names(secret: str, text: str) -> None:
    redacted = logging_redact.redact_text(text)
    assert secret not in redacted
    assert "***" in redacted


def test_redact_text_hides_mapping_repr_value() -> None:
    """El `repr()` de un dict (`{'client_secret': 'x'}`) también se tapa."""
    redacted = logging_redact.redact_text("{'client_secret': 'LEAK-REPR', 'ok': 1}")
    assert "LEAK-REPR" not in redacted
    assert "'ok': 1" in redacted  # lo inocuo no se toca


class _TokenCarrier:
    """Arg NO-str cuyo `str()` contiene un par clave=valor sensible."""

    def __str__(self) -> str:
        return "access_token=LEAK-NONSTR"


def test_redact_filter_covers_non_str_arg(logging_redact_state: None) -> None:
    """Un arg NO-str (dict/objeto) se redacta vía la representación formateada."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    root.addHandler(handler)
    previous_level = root.level
    root.setLevel(logging.INFO)
    try:
        logging_redact.install_log_redact()
        logging.getLogger("bolsa_api.background.scan_worker").warning(
            "cfg %s / payload %s", {"refresh_token": "LEAK-DICT"}, _TokenCarrier()
        )
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)

    emitted = stream.getvalue()
    assert "LEAK-DICT" not in emitted
    assert "LEAK-NONSTR" not in emitted


def test_redact_filter_covers_extra_str_field(logging_redact_state: None) -> None:
    """Un campo `extra=` de tipo str con un secreto queda redactado en el record."""
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record)  # type: ignore[method-assign]
    root = logging.getLogger()
    root.addHandler(handler)
    previous_level = root.level
    root.setLevel(logging.INFO)
    try:
        logging_redact.install_log_redact()
        logging.getLogger("bolsa_api.background.scan_worker").info(
            "ok", extra={"client_secret": "client_secret=LEAK-EXTRA"}
        )
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)

    assert len(records) == 1
    assert "LEAK-EXTRA" not in records[0].client_secret


def test_redact_filter_covers_exception_traceback(logging_redact_state: None) -> None:
    """El traceback (`exc_info` es una tupla, no str) se pre-formatea redactado."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    root.addHandler(handler)
    previous_level = root.level
    root.setLevel(logging.INFO)
    try:
        logging_redact.install_log_redact()
        logger = logging.getLogger("bolsa_api.background.scan_worker")
        try:
            raise RuntimeError("db_password=LEAK-EXC")
        except RuntimeError:
            logger.exception("fallo al conectar")
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)

    emitted = stream.getvalue()
    assert "LEAK-EXC" not in emitted
    assert "Traceback" in emitted
