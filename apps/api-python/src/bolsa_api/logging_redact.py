"""Redact secrets from log records (Q2.4)."""

from __future__ import annotations

import logging
import re

_SENSITIVE_PATTERNS = (
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


def redact_text(text: str) -> str:
    out = text
    for pat in _SENSITIVE_PATTERNS:
        out = pat.sub(r"\1***", out)
    return out


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_text(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_text(a) if isinstance(a, str) else a for a in record.args
                )
        return True


def install_log_redact(root: logging.Logger | None = None) -> None:
    logger = root or logging.getLogger()
    # Avoid duplicate filters on reload.
    if any(isinstance(f, RedactFilter) for f in logger.filters):
        return
    logger.addFilter(RedactFilter())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "bolsa_api"):
        logging.getLogger(name).addFilter(RedactFilter())
