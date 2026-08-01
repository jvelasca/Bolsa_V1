"""Resolución de universo para scans — compartido RunScan y EnqueueScanJob."""

from __future__ import annotations

from typing import Any

from bolsa_domain.platform_kernel import validate_scan_universe_size
from bolsa_infrastructure.database.repositories.list_repository import SqlAlchemyListRepository


async def resolve_scan_universe_instrument_ids(
    list_repository: SqlAlchemyListRepository,
    *,
    list_id: str | None,
    instrument_ids: list[str] | None,
    async_job: bool = False,
) -> list[str]:
    if list_id:
        # Solo materializa IBEX si el scan apunta a esa lista (no fuerza recreación global).
        if list_id in {"ibex35", "IBEX35"}:
            await list_repository.ensure_ibex_catalog_list()
        detail = await list_repository.get_by_id(list_id)
        if detail is None:
            raise ValueError("Lista no encontrada")
        resolved = list(detail.instrument_ids)
    elif instrument_ids:
        resolved = list(dict.fromkeys(instrument_ids))
    else:
        raise ValueError("Indica universe.listId o universe.instrumentIds")

    if not resolved:
        raise ValueError("El universo no tiene instrumentos")

    validate_scan_universe_size(len(resolved), async_job=async_job)
    return resolved


def universe_from_payload(payload: dict[str, Any]) -> tuple[str | None, list[str] | None]:
    universe = payload.get("universe") or {}
    list_id = universe.get("listId")
    instrument_ids = universe.get("instrumentIds")
    return list_id, instrument_ids
