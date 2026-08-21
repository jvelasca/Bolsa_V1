"""OpenAPI response declarations for idempotency conflicts (R12-409 B1).

Runtime maps IdempotencyKeyReused + IdempotencyKeyExists → HTTP 409 with
body ``{"detail": "<string>"}`` via the app-wide handler in ``main.py``.
These dicts only declare that shape in OpenAPI; they do not change handlers.
"""

from __future__ import annotations

from typing import Any

IDEMPOTENCY_CONFLICT_RESPONSES: dict[int | str, dict[str, Any]] = {
    409: {
        "description": (
            "Idempotency key conflict (reused with different payload, or key exists)."
        ),
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"detail": {"type": "string"}},
                    "required": ["detail"],
                }
            }
        },
    }
}
