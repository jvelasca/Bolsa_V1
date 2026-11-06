"""Sonda de integracion real contra la API y PostgreSQL (workspace fixture).

No forma parte de la suite: se ejecuta a mano contra una instancia de API apuntando a
la BD de auditoria (`bolsa_v1_audit`). Crea un workspace fixture, ejercita la
concurrencia optimista y el cierre compacto, deja el estado en un fichero temporal para
que la fase `verify` lo compruebe DESPUES de reiniciar el proceso de API, y lo borra.

Uso:
    uv run --no-sync python docs/engineering/evidence/auditoria-persistencia-2026-11-02/probe_integration.py setup
    # reiniciar el proceso de la API
    uv run --no-sync python docs/engineering/evidence/auditoria-persistencia-2026-11-02/probe_integration.py verify
    uv run --no-sync python docs/engineering/evidence/auditoria-persistencia-2026-11-02/probe_integration.py cleanup

`BOLSA_AUDIT_API` (por defecto http://127.0.0.1:8010) selecciona la instancia.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx

BASE_URL = os.environ.get("BOLSA_AUDIT_API", "http://127.0.0.1:8010").rstrip("/")
STATE_FILE = Path(tempfile.gettempdir()) / "bolsa_audit_fixture.json"
LIST_ID = "estudio"
OPEN_INSTRUMENTS = ["SAN", "BBVA", "ITX"]
CLOSED_INSTRUMENTS = ["BBVA", "ITX"]


def tab(tab_id: str, instrument_id: str) -> dict[str, Any]:
    return {
        "id": tab_id,
        "instrumentId": instrument_id,
        "label": instrument_id,
        "sourceListId": LIST_ID,
        "timeframe": "1D",
        "seriesType": "candles",
        "indicatorInstances": [],
        "drawings": [],
    }


def document(active: str = "BBVA") -> dict[str, Any]:
    charts = [tab(f"t{index}", instrument) for index, instrument in enumerate(OPEN_INSTRUMENTS)]
    return {
        "version": 1,
        "id": "doc",
        "name": "Fixture auditoria",
        "updatedAt": "2026-11-02T00:00:00.000Z",
        "charts": charts,
        "activeChartId": active,
        "chartStateByListInstrument": {
            f"{LIST_ID}::{instrument}": {
                "timeframe": "1D",
                "seriesType": "candles",
                "indicatorInstances": [],
                "drawings": [],
            }
            for instrument in OPEN_INSTRUMENTS
        },
        "chartListContext": {"listId": LIST_ID, "instrumentId": "BBVA"},
        "list": {
            "id": LIST_ID,
            "apiListId": LIST_ID,
            "visualizationEntries": [
                {
                    "instrumentId": instrument,
                    "symbol": instrument,
                    "name": instrument,
                    "firstViewedAt": "2026-11-01T00:00:00.000Z",
                    "lastViewedAt": "2026-11-01T00:00:00.000Z",
                    "viewCount": 1,
                }
                for instrument in OPEN_INSTRUMENTS
            ],
        },
    }


def check(condition: bool, label: str, extra: Any = None) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -> {extra!r}" if extra is not None else ""))
    if not condition:
        raise SystemExit(f"Fallo de integracion: {label}")


async def create_fixture(client: httpx.AsyncClient) -> tuple[str, str]:
    response = await client.post(
        "/api/workspaces",
        json={"name": "Fixture auditoria", "document": document()},
    )
    check(response.status_code == 201, "crear workspace fixture", response.status_code)
    data = response.json()["data"]
    return data["id"], data["updatedAt"]


async def fresh_update(client: httpx.AsyncClient, workspace_id: str, revision: str) -> str:
    response = await client.put(
        f"/api/workspaces/{workspace_id}",
        json={"name": "Fixture auditoria v2", "document": document(), "expectedUpdatedAt": revision},
    )
    check(response.status_code == 200, "PUT con revision vigente", response.status_code)
    return response.json()["data"]["updatedAt"]


async def stale_update(client: httpx.AsyncClient, workspace_id: str, revision: str) -> None:
    response = await client.put(
        f"/api/workspaces/{workspace_id}",
        json={"document": document(), "expectedUpdatedAt": revision},
    )
    body = response.json()
    check(
        response.status_code == 409 and body["detail"]["code"] == "workspace_conflict",
        "PUT con revision obsoleta devuelve 409",
        (response.status_code, body.get("detail")),
    )


async def invalid_revision(client: httpx.AsyncClient, workspace_id: str) -> None:
    response = await client.put(
        f"/api/workspaces/{workspace_id}",
        json={"document": document(), "expectedUpdatedAt": "no-es-fecha"},
    )
    body = response.json()
    check(
        response.status_code == 400 and body["detail"]["code"] == "workspace_invalid_revision",
        "revision malformada devuelve 400 (no fail-open)",
        (response.status_code, body.get("detail")),
    )


async def concurrent_updates(client: httpx.AsyncClient, workspace_id: str, revision: str) -> str:
    payload = {
        "document": document(),
        "expectedUpdatedAt": revision,
    }
    first, second = await asyncio.gather(
        client.put(f"/api/workspaces/{workspace_id}", json={**payload, "name": "Concurrente A"}),
        client.put(f"/api/workspaces/{workspace_id}", json={**payload, "name": "Concurrente B"}),
    )
    statuses = sorted([first.status_code, second.status_code])
    check(statuses == [200, 409], "dos PUT concurrentes: exactamente uno gana", statuses)
    winner = first if first.status_code == 200 else second
    return winner.json()["data"]["updatedAt"]


async def close_tabs(client: httpx.AsyncClient, workspace_id: str, revision: str) -> dict[str, Any]:
    response = await client.post(
        f"/api/workspaces/{workspace_id}/charts/close",
        json={
            "instrumentIds": CLOSED_INSTRUMENTS,
            "activeChartId": "t0",
            "expectedUpdatedAt": revision,
        },
    )
    check(response.status_code == 200, "cierre compacto de 2 de 3 pestanas", response.status_code)
    return response.json()["data"]


def assert_closed_state(document_data: dict[str, Any], label: str) -> None:
    charts = [item.get("instrumentId") for item in document_data.get("charts", [])]
    check(charts == ["SAN"], f"{label}: charts podado", charts)

    entries = [
        entry.get("instrumentId")
        for entry in document_data.get("list", {}).get("visualizationEntries", [])
    ]
    check(entries == ["SAN"], f"{label}: visualizationEntries podado", entries)

    snapshots = list(document_data.get("chartStateByListInstrument", {}))
    check(snapshots == [f"{LIST_ID}::SAN"], f"{label}: snapshots podados", snapshots)

    context = document_data.get("chartListContext")
    check(context is None, f"{label}: chartListContext huerfano eliminado", context)

    check(document_data.get("activeChartId") == "t0", f"{label}: pestana activa recalculada")


async def setup(client: httpx.AsyncClient) -> None:
    workspace_id, revision = await create_fixture(client)
    print(f"workspace fixture: {workspace_id}")

    revision_v1 = await fresh_update(client, workspace_id, revision)
    await stale_update(client, workspace_id, revision)
    await invalid_revision(client, workspace_id)
    revision_v2 = await concurrent_updates(client, workspace_id, revision_v1)
    closed = await close_tabs(client, workspace_id, revision_v2)
    assert_closed_state(closed["document"], "respuesta del cierre")

    # El cierre idempotente con revision obsoleta tambien debe dar 409.
    noop = await client.post(
        f"/api/workspaces/{workspace_id}/charts/close",
        json={"instrumentIds": ["NO-EXISTE"], "expectedUpdatedAt": revision_v1},
    )
    check(noop.status_code == 409, "cierre idempotente con revision obsoleta da 409", noop.status_code)

    STATE_FILE.write_text(
        json.dumps({"workspace_id": workspace_id, "updated_at": closed["updatedAt"]}),
        encoding="utf-8",
    )
    print(f"estado guardado en {STATE_FILE}")


async def verify(client: httpx.AsyncClient) -> None:
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    response = await client.get(f"/api/workspaces/{state['workspace_id']}")
    check(response.status_code == 200, "releer tras reiniciar la API", response.status_code)
    data = response.json()["data"]
    check(
        data["updatedAt"] == state["updated_at"],
        "la revision sobrevive al reinicio",
        (data["updatedAt"], state["updated_at"]),
    )
    assert_closed_state(data["document"], "post-reinicio")


async def cleanup(client: httpx.AsyncClient) -> None:
    if not STATE_FILE.exists():
        print("no hay fixture que borrar")
        return
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    response = await client.delete(f"/api/workspaces/{state['workspace_id']}")
    check(response.status_code == 204, "borrar fixture", response.status_code)
    STATE_FILE.unlink(missing_ok=True)


async def main(phase: str) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        if phase == "setup":
            await setup(client)
        elif phase == "verify":
            await verify(client)
        elif phase == "cleanup":
            await cleanup(client)
        else:
            raise SystemExit(f"fase desconocida: {phase}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
