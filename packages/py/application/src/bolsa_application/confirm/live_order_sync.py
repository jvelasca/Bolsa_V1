"""LiveOrderCoordinator — XL-3 cable Confirm (persist only · sin recovery/query).

Vive en su propio módulo para mantener ``ConfirmRecommendationIntent`` como
orquestador fino (invariante ``dex4_module_is_thin``), reutilizando el puerto
``LiveOrderStore`` y la lógica pura ``live_order_from_submit_result`` del dominio.

* Solo persiste rastro LIVE cuando el adapter responde ``submitted``/``unknown``
  (bridge lo retiene o no sabemos si existe). Nunca un FILLED inventado.
* ``PAPER`` / sandbox VIRTUAL ``not_wired`` / ``rejected`` / ``executed``(XL-2
  cerrado→ledger) no escriben la máquina.
* UNKNOWN = first-class: NO re-POST. ``query_broker`` (moverse fuera) queda
  PARKED → lo abrirá el sled PG de V2.12. ≠ thaw · ≠ PAPER_D_EXECUTE.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from bolsa_application.live_order_store import live_order_from_submit_result


class LiveOrderCoordinator:
    """Publica/persiste la máquina XL-3 tras un submit LIVE real."""

    def __init__(
        self,
        *,
        live_order_store: Any | None = None,
    ) -> None:
        # Default: store de proceso (persist SQL nada aquí → V2.12). Si se inyecta
        # una instancia aislada (tests) o un Sled futuro, se usa esa.
        if live_order_store is None:
            from bolsa_application.live_order_store import process_live_order_store

            live_order_store = process_live_order_store()
        self._store = live_order_store

    async def persist_after_submit(
        self,
        *,
        result: dict[str, Any],
        intent: Any,
        pb: Any,
        order_id: str,
        account_id: str | None = None,
    ) -> None:
        """Persiste/expona ``result["liveOrder"]`` cuando proceda (ver docstring)."""
        store = self._store
        if store is None or pb is None:
            return
        if getattr(pb, "venue", None) != "LIVE":
            out = result.get("liveOrder")
            if out is not None:
                # Hoy no limpio el rastro ya persistido: podría provenir de una
                # decisión LIVE previa re-expuesta por el request (fail-closed
                # sería borrarlo, pero no disponemos de transición abort/fill
                # aquí sin riesgo). Conservamos + anotamos que este paso no toca.
                result["liveOrderPersist"] = {
                    "status": "skipped",
                    "reason": "non_live_adapter",
                }
            return

        order_id = (order_id or "").strip()
        # La cuenta durable se deriva del intent cuando el caller no la precisa.
        effective_account = account_id or getattr(intent, "account_id", None) or None
        try:
            existing = await store.get(order_id) if order_id else None
        except Exception:  # noqa: BLE001 — store read fallo → no cascada
            existing = None

        target = live_order_from_submit_result(
            order_id=order_id,
            instrument_id=intent.instrument_id,
            side=intent.side,
            quantity=float(intent.quantity),
            intent_id=intent.intent_id,
            pb=pb,
            existing=existing,
        )
        if target is None:
            return
        if effective_account and target.account_id is None:
            target = dataclasses.replace(target, account_id=effective_account)
        try:
            await store.put(target, account_id=effective_account)
            result["liveOrder"] = target.to_dict()
        except Exception as exc:  # noqa: BLE001 — persist no tumba el confirm
            result["liveOrderPersist"] = {
                "status": "error",
                "reason": str(exc),
            }
