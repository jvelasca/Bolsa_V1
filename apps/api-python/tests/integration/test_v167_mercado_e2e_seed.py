"""V1.67 GP-V167-07 — Mercado E2E seed harness (HTTP paridad Playwright)."""

from __future__ import annotations

import pytest
from tests.integration.v159_harness import (
    create_funded_account,
    first_instrument_id,
    integration_client,
    seed_buy_trade,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_gp_v167_07_mercado_seed_fixture() -> None:
    """GP-V167-07: cuenta aislada + mandate + buy → portfolio con posición."""
    async with integration_client() as (app, client):
        account_id = await create_funded_account(client, name_prefix="v167")
        instrument_id = await first_instrument_id(client)
        await seed_buy_trade(app, client, account_id, instrument_id)

        portfolio = await client.get(
            "/api/portfolio",
            headers={"X-Account-Id": account_id},
        )
        assert portfolio.status_code == 200, portfolio.text
        positions = portfolio.json()["data"]["positions"]
        match = next(p for p in positions if p["instrumentId"] == instrument_id)
        assert match["quantity"] > 0

        workspace = await client.post(
            "/api/workspaces",
            json={
                "name": "v167-e2e-mercado",
                "isDefault": False,
                "document": {
                    "version": 1,
                    "id": "v167-ws",
                    "name": "v167-e2e-mercado",
                    "updatedAt": "2026-09-02T12:00:00.000Z",
                    "layout": {
                        "listPanelOpen": True,
                        "listPanelSizePct": 26,
                        "rightPanelOpen": False,
                        "rightPanelSizePct": 22,
                        "chartInspectorOpen": False,
                        "activeRoute": "/trading",
                    },
                    "preferences": {"autoSave": False, "openOnStartup": True},
                    "charts": [
                        {
                            "id": "v167-tab",
                            "instrumentId": instrument_id,
                            "label": "E2E",
                            "timeframe": "1d",
                            "seriesType": "candles",
                            "chart": {
                                "id": "default",
                                "grid": {"visible": True},
                                "cursor": {"mode": "magnet"},
                                "colors": {},
                                "display": {},
                            },
                            "indicatorInstances": [],
                            "drawings": [],
                        }
                    ],
                    "activeChartId": "v167-tab",
                    "chartStateByListInstrument": {},
                    "chartListContext": None,
                    "indicatorTemplates": [],
                    "indicatorPresets": [],
                    "indicatorFavoritesByListId": {},
                    "defaultIndicatorTemplateId": None,
                    "chartToolbarGlobal": {
                        "defaultTimeframe": "1d",
                        "defaultSeriesType": "candles",
                        "activeDrawTool": "select",
                        "lastDrawToolByGroup": {},
                        "timeframeFavorites": ["1d"],
                        "seriesTypeFavorites": ["candles"],
                        "indicatorTemplateFavorites": [],
                        "drawToolFavorites": [],
                        "inspectorBarShortcutFavorites": [],
                        "chartVisibilityDefaults": {},
                        "chartLayoutDefaults": {},
                    },
                    "list": {
                        "carouselListIds": [],
                        "carouselHiddenListIds": [],
                        "columnLayoutsByListId": {},
                        "sortByListId": {},
                        "visualizationEntries": [],
                    },
                },
            },
        )
        assert workspace.status_code == 201, workspace.text
        assert workspace.json()["data"]["id"]
