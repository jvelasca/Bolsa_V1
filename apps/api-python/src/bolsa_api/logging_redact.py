"""Redact secrets from log records (Q2.4)."""

from __future__ import annotations

import logging
import re

#: Patrones base (histórico `Q2.4`/`F-SEG-2`). Se conservan tal cual.
_BASE_SENSITIVE_PATTERNS = (
    re.compile(r"(authorization\s*[:=]\s*bearer\s+)\S+", re.I),
    re.compile(r"(authorization\s*[:=]\s*)(?!bearer\b)\S+", re.I),
    re.compile(r"(api[_-]?key\s*[:=]\s*)\S+", re.I),
    re.compile(r"(password\s*[:=]\s*)\S+", re.I),
    # F-SEG-2: además de los genéricos, cubrir las credenciales concretas de la app
    # (settings de auth/BD) para que sus valores no cuelen en logs como key=value.
    re.compile(r"(app_[_-]?password\s*[:=]\s*)\S+", re.I),
    re.compile(r"(app_[_-]?auth[_-]?secret\s*[:=]\s*)\S+", re.I),
    re.compile(r"(db[_-]?password\s*[:=]\s*)\S+", re.I),
    re.compile(r"(bearer\s+)\S+", re.I),
    re.compile(r"(xtb[_-]?(?:user|pass|token)\s*[:=]\s*)\S+", re.I),
)

#: Separador tolerante al `repr()` de un mapping (`{'client_secret': 'x'}`) y a espacios.
_KV_SEP = r"""\s*['"]?\s*[:=]\s*['"]?"""
#: Valor hasta el siguiente delimitador (espacio, comilla, coma o cierre de llave), de
#: modo que en `{'client_secret': 'x'}` solo se tapa `x` y no las comillas ni la llave.
_KV_VAL = r"""[^\s'",}]+"""

#: Nombres de clave que amplían la cobertura base (auditoría 2, `G6`): credenciales
#: frecuentes fuera de la lista original. Se aplican con separador tolerante para cubrir
#: también valores NO-str (dicts/objetos volcados por `%s`).
_EXTRA_KEY_NAMES = (
    r"password",
    r"app[_-]?password",
    r"app[_-]?auth[_-]?secret",
    r"db[_-]?password",
    r"client[_-]?secret",
    r"app[_-]?secret",
    r"secret[_-]?key",
    r"signing[_-]?key",
    r"jwt[_-]?signing[_-]?key",
    r"private[_-]?key",
    r"(?:refresh|access|id)[_-]?token",
    r"passphrase",
    r"secret",
    r"token",
)
_EXTRA_SENSITIVE_PATTERNS = tuple(
    re.compile(rf"({name}{_KV_SEP}){_KV_VAL}", re.I) for name in _EXTRA_KEY_NAMES
)

_SENSITIVE_PATTERNS = (*_BASE_SENSITIVE_PATTERNS, *_EXTRA_SENSITIVE_PATTERNS)


def redact_text(text: str) -> str:
    out = text
    for pat in _SENSITIVE_PATTERNS:
        out = pat.sub(r"\1***", out)
    return out


#: Atributos estándar de `LogRecord`; todo lo demás es `extra=` y se inspecciona.
_STANDARD_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)))


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_text(v) if isinstance(v, str) else v for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_text(a) if isinstance(a, str) else a for a in record.args
                )
        # Args NO-str (dicts/objetos) y `msg` no-str: se redacta la representación ya
        # formateada. No se tocan los tipos de `args` para no romper `%d`/`%r`; solo se
        # colapsa a texto cuando aparece un secreto.
        rendered = self._render(record)
        if rendered is not None and redact_text(rendered) != rendered:
            record.msg = redact_text(rendered)
            record.args = None
        # Campos `extra=` (str) que el formato pudiera volcar a la salida.
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_ATTRS or not isinstance(value, str):
                continue
            record.__dict__[key] = redact_text(value)
        # El traceback (`exc_info` es una tupla, no str): se pre-formatea redactado para
        # que el `Formatter` use `exc_text` en vez de volcar el original.
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if isinstance(record.exc_text, str):
            record.exc_text = redact_text(record.exc_text)
        return True

    @staticmethod
    def _render(record: logging.LogRecord) -> str | None:
        try:
            return record.getMessage()
        except Exception:  # noqa: BLE001 — un formato inválido lo reporta el handler
            return None


#: Loggers de la app/uvicorn cuyos handlers deben quedar redactados.
_REDACT_LOGGER_NAMES = ("uvicorn", "uvicorn.error", "uvicorn.access", "bolsa_api")


def _attach_redact(logger: logging.Logger, redact: RedactFilter) -> None:
    """Adjunta ``redact`` al logger y a sus handlers (idempotente).

    El filtro de un ``Logger`` solo se evalúa en el logger EXACTO que emite
    (``Logger.handle``); un registro que propaga a un ancestro lo entrega
    directamente a los **handlers** de ese ancestro (``Logger.callHandlers``), sin
    volver a pasar por el ``.filter()`` del ancestro. Por eso hay que adjuntar el
    filtro también a nivel de **handler**: ahí sí se evalúa sobre cualquier registro
    propagado, venga del ``logging.getLogger(__name__)`` que sea (el patrón real de
    routers, ``background/*_worker.py`` y ``workers/*``).
    """
    if not any(isinstance(f, RedactFilter) for f in logger.filters):
        logger.addFilter(redact)
    for handler in logger.handlers:
        if not any(isinstance(f, RedactFilter) for f in handler.filters):
            handler.addFilter(redact)


def install_log_redact(root: logging.Logger | None = None) -> None:
    """Instala la redacción de credenciales en root, ``bolsa_api`` y uvicorn.

    Se puede invocar varias veces sin duplicar filtros (arranque + reload/workers).
    """
    redact = RedactFilter()
    base = root or logging.getLogger()
    _attach_redact(base, redact)
    stdlib_root = logging.getLogger()
    if base is not stdlib_root:
        _attach_redact(stdlib_root, redact)
    for name in _REDACT_LOGGER_NAMES:
        _attach_redact(logging.getLogger(name), redact)
    # ``callHandlers`` recurre a ``logging.lastResort`` cuando ningún logger de la
    # jerarquía tiene handler; sin esto, un log emitido antes de que exista root
    # handler saldría por ahí sin redactar.
    last_resort = logging.lastResort
    if last_resort is not None and not any(
        isinstance(f, RedactFilter) for f in last_resort.filters
    ):
        last_resort.addFilter(redact)
