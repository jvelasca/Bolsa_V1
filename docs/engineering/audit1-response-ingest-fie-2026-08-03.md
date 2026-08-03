# Respuesta a Auditoría 1 — mapeo a Bolsa_V1 (2026-08-03)

> **Propósito:** contrastar el informe de auditoría 1 (principios / FIE / ingesta / UI) con el **código real** de este monorepo y registrar qué se cerró.  
> **Stack real:** FastAPI Python (`apps/api-python`) + `packages/py/{market,analytics,application,…}` + React (`apps/web`). **No** tRPC / `bolsa_core` / `packages/market-data`.  
> **Premisas:** [PROJECT_PREMISES.md](../PROJECT_PREMISES.md) · Freeze: [post-audit-decision-freeze-2026-08-03.md](./post-audit-decision-freeze-2026-08-03.md).

---

## 0. Resumen ejecutivo

La auditoría 1 es un buen **checklist conceptual**, pero varias brechas ya estaban cerradas en Bolsa_V1 (Q2 roadmap) o se referían a otra arquitectura.  
En esta pasada (A → B) se implementaron solo los **gaps reales** que faltaban.

| Tema auditoría | Veredicto previo | Acción 2026-08-03 |
|----------------|------------------|-------------------|
| Validación OHLC | **Parcial** (Pydantic + intradía) | Cuarentena diaria + contadores/logs |
| Circuit breaker Yahoo | **Missing** | `YahooCircuitBreaker` + wire en client |
| Retry/backoff Yahoo | **Ya existía** | Sin cambio |
| `/api/health` | **Parcial** | + Redis ping + circuit/quarantine details |
| Rate limiting API | **Ya existía** | Sin cambio |
| Walk-forward / costes | **Ya existían** (costes gated) | No reabrir freeze |
| Score_FUND warnings/confidence | **Ya existía** | + test cobertura parcial |
| GET fundamentals / card | **Ya existía** | Sin cambio |
| Feature Store / microservicios / Risk 3 capas | Horizonte / fuera de freeze | No abrir |

---

## 1. Opción A — Ingesta (hechos)

| Entrega | Evidencia |
|---------|-----------|
| Circuit breaker Yahoo | `packages/py/market/src/bolsa_market/yahoo_circuit_breaker.py` · wired en `yahoo_client.fetch_chart_payload` · env `YAHOO_CB_*` |
| Cuarentena OHLCV | `ohlcv_quarantine.py` · daily+intraday en `yahoo_chart.py` · tests en `test_yahoo_chart.py` |
| Health | `GET /api/health` → components `yahoo` (circuit + quarantine), `redis` (ping best-effort), `xtb`, `database` |
| Tests | `test_yahoo_circuit_breaker.py` · health ASGI |

**No implementado (a propósito):** fallback Alpaca; tabla BD de cuarentena; tRPC health.

---

## 2. Opción B — FIE F1 (hechos)

| Entrega | Evidencia |
|---------|-----------|
| warnings / confidence / coverage / distress | Ya en `score_fund.py` (`ScoreFundResult`) |
| display 0–100 | `fund_score_to_display_100` / card `scoreDisplay100` |
| bias | En `FundamentalAssessment`, **no** en card (producto: «Sin bias en card») |
| Test cobertura parcial | `test_score_fund_partial_coverage_medium` |
| Endpoint FA | `GET /api/instruments/{id}/fundamentals` + `FundamentalCardDto` |

**No implementado (a propósito):** copiar el `score_fund.py` del informe (rompe pesos/API actuales); Feature Store `fundamental_features`.

---

## 3. Brechas mal etiquetadas por el informe

- «Costes no implementados» → `cost_model_v2` existe, flag `COST_MODEL_V2_ENABLED=false` ([freeze](./post-audit-decision-freeze-2026-08-03.md)).  
- «No hay Walk-Forward» → Lab WF en `optimize/walk_forward.py` + UI.  
- «Sin rate limit / health» → middleware + `/api/health` (Q2).  
- Propuestas tRPC / `packages/market-data` → **no aplican** a este repo.

---

## 4. Cómo verificar

```bash
python -m pytest packages/py/market/tests/test_yahoo_circuit_breaker.py packages/py/market/tests/test_yahoo_chart.py packages/py/analytics/tests/test_fundamental_card_f1.py -q
python -m pytest apps/api-python/tests/test_health.py -q
# Con API:
# curl http://127.0.0.1:8000/api/health
```

---

## 5. Para las 3 auditorías

Empezar por [audit-pack-post-audits-2026-08-03.md](./audit-pack-post-audits-2026-08-03.md) y este doc como **errata** frente al checklist genérico de auditoría 1.
