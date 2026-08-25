# Referencia API HTTP — Bolsa V1

**Base URL:** `http://localhost:8000`  
**OpenAPI interactivo:** http://localhost:8000/api/docs  
**Auth:** `Authorization: Bearer <token>` (si `APP_PASSWORD` definido)

Rutas públicas sin token: `/api/health`, `/api/auth/login`, `/api/auth/status`, `/api/docs`, `/api/openapi.json`.

---

## Health

| Método | Ruta          | Descripción                                                                                            |
| ------ | ------------- | ------------------------------------------------------------------------------------------------------ |
| GET    | `/api/health` | Estado servicio + BD + componentes (`database`, `yahoo`, `xtb`, `redis`, `auth`, `worker_arq`, `risk`) |

`components.risk` expone kill switch efectivo (`env` / runtime / Redis) y si `PAPER_D_EXECUTE` está on (solo lectura; default off).

---

## Risk (OR-P7 / A3)

| Método | Ruta                    | Body                   | Descripción                                                            |
| ------ | ----------------------- | ---------------------- | ---------------------------------------------------------------------- |
| GET    | `/api/risk/kill-switch` | —                      | Estado kill switch (env + memoria + Redis) + `paperDExecuteEnv`        |
| POST   | `/api/risk/kill-switch` | `{ enabled: boolean }` | Activa/desactiva runtime (&lt;1s vía Risk Engine); no reinicia proceso |

Bloquea aperturas **automáticas** (`paper_auto` / futuro AUTO). No sustituye Confirm SEMI.

---

## Auth

| Método | Ruta               | Body           | Respuesta                  |
| ------ | ------------------ | -------------- | -------------------------- |
| GET    | `/api/auth/status` | —              | `{ authEnabled: boolean }` |
| POST   | `/api/auth/login`  | `{ password }` | `{ token, expiresAt }`     |

---

## Instruments

| Método | Ruta                                      | Descripción                          |
| ------ | ----------------------------------------- | ------------------------------------ |
| GET    | `/api/instruments`                        | Lista catálogo con meta sync         |
| GET    | `/api/instruments/search?q=`              | Catálogo local + hits Yahoo externos |
| POST   | `/api/instruments/import`                 | Importar activo Yahoo al catálogo    |
| GET    | `/api/instruments/{id}`                   | Detalle + lastSync + priceSummary    |
| GET    | `/api/instruments/{id}/ohlcv?limit=`      | Barras OHLCV diarias                 |
| GET    | `/api/instruments/{id}/indicators?limit=` | SMA/EMA/RSI calculados               |
| GET    | `/api/instruments/{id}/live-quote`        | Cotización live (XTB/Yahoo)          |
| POST   | `/api/instruments/{id}/sync`              | Sincronizar histórico Yahoo          |

### POST `/api/instruments/import`

```json
{
  "yahooSymbol": "AAPL",
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "exchange": "NMS",
  "currency": "USD",
  "sync": true,
  "yearsBack": 5
}
```

Caso de uso: `bolsa_application/import_instrument.py`.

### POST `/api/instruments/{id}/sync`

```json
{ "yearsBack": 5 }
```

Caso de uso: `bolsa_application/sync_instrument.py`.

---

## Lists

| Método | Ruta                     | Descripción                   |
| ------ | ------------------------ | ----------------------------- |
| GET    | `/api/lists`             | Resumen listas                |
| POST   | `/api/lists`             | Crear lista                   |
| GET    | `/api/lists/{id}`        | Detalle + instrumentIds       |
| PATCH  | `/api/lists/{id}`        | Actualizar nombre/miembros    |
| DELETE | `/api/lists/{id}`        | Eliminar                      |
| GET    | `/api/lists/{id}/quotes` | Instrumentos con meta para UI |

---

## Scope headers (cuentas)

| Header         | Descripción                                                                                                        |
| -------------- | ------------------------------------------------------------------------------------------------------------------ |
| `X-Account-Id` | Cuenta de inversión activa (si omitido: cuenta default). La cartera operativa es siempre la default de esa cuenta. |

Aplica a `/api/portfolio`, `/api/portfolio/trade`, `/api/portfolio/transactions`, `/api/pending-orders`.

---

## Investment accounts

| Método | Ruta                                                           | Descripción                                           |
| ------ | -------------------------------------------------------------- | ----------------------------------------------------- |
| GET    | `/api/accounts`                                                | Listar cuentas                                        |
| POST   | `/api/accounts`                                                | Crear cuenta simulada (wizard payload)                |
| GET    | `/api/accounts/{id}`                                           | Detalle cuenta                                        |
| PATCH  | `/api/accounts/{id}`                                           | Editar nombre y descripción                           |
| PATCH  | `/api/accounts/{id}/settings`                                  | Comisiones y fiscal (sin perfil inversor)             |
| POST   | `/api/accounts/{id}/close`                                     | Cerrar cuenta (conserva historial)                    |
| DELETE | `/api/accounts/{id}`                                           | Eliminar cuenta demo cerrada (hard delete)            |
| GET    | `/api/accounts/{id}/summary`                                   | Resumen (dispara custodia anual si procede)           |
| GET    | `/api/accounts/{id}/daily-ops-report?asOf=&instrumentIds=`     | Resumen operativo diario (R1 preview Asesor → Diario) |
| GET    | `/api/accounts/{id}/daily-ops-report.pdf?asOf=&instrumentIds=` | R4 — descarga PDF del resumen                         |
| POST   | `/api/accounts/{id}/daily-ops-report/email`                    | R3/R4 — envío HTML digest (+ `attachPdf`)             |
| GET    | `/api/accounts/{id}/ledger?limit=&offset=`                     | Libro mayor                                           |
| GET    | `/api/accounts/{id}/tax-report?year=`                          | Informe plusvalías                                    |
| POST   | `/api/accounts/{id}/deposits`                                  | Depósito externo (simulado)                           |
| POST   | `/api/accounts/{id}/withdrawals`                               | Retirada externa (simulada)                           |

Body depósito/retirada: `{ amount, note? }`.

Body editar cuenta: `{ name?, description? }`.

DTO cuenta incluye `activeProfileId` (FK al catálogo ART-PROFILE).

**Ciclo de vida demo:** `POST …/close` solo pone `status=closed` (sigue en BD). `DELETE` exige demo ya cerrada y borra cuenta + carteras/posiciones/ledger/órdenes; perfiles del catálogo se conservan; filas cognitivas sueltas desvinculan `accountId`.

Mantenimiento en lote: `GET/POST /api/database/closed-accounts[/purge]` (Configuración → BD).

Ver [PORTFOLIO_AND_CASH.md](./PORTFOLIO_AND_CASH.md) para reglas de movimientos.

---

## Investor profiles (RFC-008 ART-PROFILE)

Catálogo reutilizable; no vive en `settings_json`.

| Método | Ruta                                           | Descripción                                                |
| ------ | ---------------------------------------------- | ---------------------------------------------------------- |
| GET    | `/api/investor-profiles`                       | Listar perfiles del catálogo                               |
| POST   | `/api/investor-profiles`                       | Crear perfil (declared + plantilla)                        |
| GET    | `/api/investor-profiles/{id}`                  | Detalle                                                    |
| PATCH  | `/api/investor-profiles/{id}`                  | Actualizar                                                 |
| DELETE | `/api/investor-profiles/{id}`                  | Eliminar (cuentas con ese activo → `activeProfileId` null) |
| PUT    | `/api/accounts/{id}/active-profile`            | Asignar perfil activo (`{ profileId }`)                    |
| GET    | `/api/accounts/{id}/active-profile`            | Perfil activo de la cuenta                                 |
| POST   | `/api/investor-profiles/{id}/refresh-observed` | Recalcula Observed desde Decision Memory → `observed_json` |

`POST /api/accounts` acepta opcionalmente `investorProfile` (crear + asignar) o `activeProfileId` (asignar del catálogo). Si ninguno: crea y asigna un perfil **moderate** por defecto.

### Supervisado / Intent (F3) + DecisionSession

| Método | Ruta                                         | Descripción                                                                     |
| ------ | -------------------------------------------- | ------------------------------------------------------------------------------- |
| POST   | `/api/ai/recommendations/propose`            | OHLCV → Assessment[] → Runtime → Recommendation + Session propose               |
| POST   | `/api/ai/intents/confirm`                    | Confirma Recommendation → Intent (+ trade opcional). Body: `sessionId` opcional |
| GET    | `/api/ai/decision-sessions`                  | Lista DecisionSession                                                           |
| GET    | `/api/ai/decision-sessions/learning-summary` | Hit-rate Outcomes (Learning v1)                                                 |
| GET    | `/api/ai/decision-sessions/{id}`             | Payload completo                                                                |
| GET    | `/api/ai/decision-sessions/{id}/replay`      | Timeline caja negra                                                             |
| POST   | `/api/ai/decision-sessions/{id}/outcome`     | Cierra con Outcome (`auto` = D1+N)                                              |
| GET    | `/api/ai/effectiveness`                      | Edge + Memory Gate + **sessionLearning**                                        |
| POST   | `/api/ai/decision-memory`                    | Append Memory (Gate)                                                            |
| POST   | `/api/ai/trials`                             | Append trial                                                                    |
| POST   | `/api/ai/edge-reports`                       | Append edge report                                                              |

### Predictions (F2)

| Método | Ruta                            | Descripción                                      |
| ------ | ------------------------------- | ------------------------------------------------ |
| GET    | `/api/predictions/models`       | Modelos (memoria + PG) + `lightgbmAvailable`     |
| GET    | `/api/predictions`              | Lista Predictions PG (`instrumentId`, `modelId`) |
| POST   | `/api/predictions/predict`      | PredictionV1 + persistencia PG best-effort       |
| POST   | `/api/predictions/models/train` | Entrena modelo + upsert `model_artifacts`        |

---

## Workspaces (espacios de trabajo)

| Método | Ruta                      | Descripción                                                      |
| ------ | ------------------------- | ---------------------------------------------------------------- |
| GET    | `/api/workspaces`         | Listar resúmenes                                                 |
| GET    | `/api/workspaces/default` | Preferido (`isDefault`) o primero                                |
| GET    | `/api/workspaces/{id}`    | Documento + `dockLayout` (campo legado; el cliente no lo aplica) |
| POST   | `/api/workspaces`         | Crear (`name`, `document?`, `dockLayout?`, `isDefault?`)         |
| PUT    | `/api/workspaces/{id}`    | Actualizar nombre / documento / dock (ignorado en UI) / default  |
| DELETE | `/api/workspaces/{id}`    | Eliminar                                                         |

**UI:** chip barra superior → gestor. Nuevo = documento vacío; duplicar = clona el activo vía `POST` con el documento actual. Arranque cliente: `activeWorkspaceId` local → default → primero. Paneles y anchos de columnas: local por dispositivo. Detalle: [WORKSPACE_PERSISTENCE.md](./WORKSPACE_PERSISTENCE.md).

## Database (mantenimiento)

| Método | Ruta                                  | Descripción                                   |
| ------ | ------------------------------------- | --------------------------------------------- |
| GET    | `/api/database/summary`               | Conexión + conteos por tabla                  |
| GET    | `/api/database/orphans`               | Instrumentos sin lista persistente            |
| POST   | `/api/database/orphans/purge`         | Purga lote huérfanos (`{ limit }`)            |
| GET    | `/api/database/closed-accounts`       | Demos `simulated` + `closed`                  |
| POST   | `/api/database/closed-accounts/purge` | Hard-delete lote demos cerradas (`{ limit }`) |

UI: **Configuración → BD**.

## Portfolio

| Método | Ruta                                 | Descripción                                                                                     |
| ------ | ------------------------------------ | ----------------------------------------------------------------------------------------------- |
| GET    | `/api/portfolio`                     | Resumen cartera (scoped por headers)                                                            |
| GET    | `/api/portfolio/transactions?limit=` | Historial operaciones                                                                           |
| POST   | `/api/portfolio/trade`               | Compra/venta paper. **Buy** pasa `check_opening` (403 `risk_veto` si veta). Sell no abre cesta. |

Body trade: `{ instrumentId, type: "buy"|"sell", quantity, price }`.

---

## Indicators (BT-3)

| Método | Ruta                      | Descripción                                           |
| ------ | ------------------------- | ----------------------------------------------------- |
| POST   | `/api/indicators/compute` | Calcula series desde `IndicatorSpec[]` + barras OHLCV |

**Body:** `{ bars: OhlcvBarDto[], specs: IndicatorSpec[] }` — límite 5000 barras.

Respuesta: `{ data: [{ definitionId, parameters, specKey, lines: [{ key, points }] }] }`.

---

## Signals (SC-1)

| Método | Ruta                    | Descripción                                                    |
| ------ | ----------------------- | -------------------------------------------------------------- |
| POST   | `/api/signals/evaluate` | Evalúa `StrategyDefinitionV1` sobre barras → `SignalEventV1[]` |

**Body:** `{ definition, instrumentId?, bars, mode?: 'raw' \| 'gated', dataVersion?, indicatorSnapshotHash? }` — límite 5000 barras.

- `raw` — cada cruce/regla (screener)
- `gated` — long-only alternado (paridad backtest H0)

---

## Scans (SC-2)

| Método | Ruta             | Descripción                                              |
| ------ | ---------------- | -------------------------------------------------------- |
| POST   | `/api/scans/run` | Escanea universo (lista o IDs) — señales en última barra |

**Body:** `{ presetKey? \| strategyDefinitionId? \| definition?, universe: { listId?, instrumentIds? }, timeframe?, barLimit?, maxResults? }`

**Kernel ADR-010 (P1):** `timeframe` solo `1d` o `1wk`. Sync: máx **500** instrumentos/universo. Async jobs: máx **5000** (ver `/scans/jobs`).

**Chunking (P2):** universos async >250 instrumentos generan job **parent** + chunks de 250; poll el `id` del parent.

Respuesta: `{ data: { scanId, scannedCount, hitCount, hits[], skipped[], timeframe } }`.

---

## Signal alerts (SC-3 / SC-6)

| Método | Ruta                                   | Descripción                                      |
| ------ | -------------------------------------- | ------------------------------------------------ |
| GET    | `/api/signal-alerts`                   | Suscripciones a señales de estrategia            |
| POST   | `/api/signal-alerts`                   | Crear suscripción                                |
| DELETE | `/api/signal-alerts/{id}`              | Eliminar                                         |
| POST   | `/api/signal-alerts/{id}/reset-dedupe` | Permitir re-disparo en barra actual              |
| POST   | `/api/signal-alerts/evaluate`          | Evaluar suscripciones activas + dispatch canales |

**Body crear:** `{ instrumentId, strategyDefinitionId? | presetKey?, signalKinds?, channels?, webhookUrl?, emailTo?, note? }`

- `channels`: `toast` (default), `webhook`, `email` — combinables
- `webhookUrl` obligatorio si incluye `webhook`
- `emailTo` obligatorio si incluye `email` (requiere SMTP en servidor)

**Evaluate respuesta:** `{ data: TriggeredSignalAlert[], dispatches: AlertChannelDispatch[] }`

Evaluación automática en servidor cada `SIGNAL_ALERT_EVAL_INTERVAL_SECONDS` (default 20) vía `signal_alert_evaluator` — webhook/email funcionan sin cliente abierto.

Payload webhook (POST JSON): `{ type: "signal_alert", subscriptionId, symbol, signal, ... }`

Coexiste con `/api/alerts` (price_alerts legacy).

---

## Scan jobs (SC-5)

| Método | Ruta                            | Descripción                      |
| ------ | ------------------------------- | -------------------------------- |
| POST   | `/api/scans/jobs`               | Encola scan async (202)          |
| GET    | `/api/scans/jobs`               | Jobs recientes                   |
| GET    | `/api/scans/jobs/{id}`          | Estado + resultado               |
| GET    | `/api/scans/manifests/{scanId}` | `ScanManifestV1` persistido (P4) |

Worker en lifespan API procesa cola `scan_jobs` cada 5s. Cache de features por `IndicatorSpec` hash (P8): `FEATURE_CACHE_BACKEND=memory|redis`.

**RD-2:** cola scan jobs — `SCAN_QUEUE_BACKEND` (R12-SCHED / R-8C.2: una autoridad por proceso):

- `postgres` (default): poll PG cada 5s en proceso dedicado `bolsa-queue-poll-worker` (no en el scheduler de crons)
- `redis`: LPUSH/BRPOP en `bolsa:scan_jobs:pending` — mismo `bolsa-queue-poll-worker`
- `arq`: encolado Arq + worker dedicado `bolsa-arq-worker` (`queue_poll` no-op)
- Crons periódicos: siempre `bolsa-scheduler-worker` (sin scan/optimize)

---

## Trackers (ADR-010 P3)

Rastreadores persistidos (`TrackerDefinitionV1`). Los scans desde tracker enlazan `scan_jobs.tracker_definition_id`.

| Método | Ruta                               | Descripción                                                 |
| ------ | ---------------------------------- | ----------------------------------------------------------- |
| GET    | `/api/trackers`                    | Listado (`?enabled_only=true` opcional)                     |
| GET    | `/api/trackers/{id}`               | Detalle + spec JSON                                         |
| POST   | `/api/trackers`                    | Crear (201)                                                 |
| PATCH  | `/api/trackers/{id}`               | Actualizar                                                  |
| DELETE | `/api/trackers/{id}`               | Eliminar (204)                                              |
| POST   | `/api/trackers/{id}/scan`          | Scan sync desde spec guardada                               |
| POST   | `/api/trackers/{id}/scan-jobs`     | Encola scan async (202), FK + payload `trackerDefinitionId` |
| POST   | `/api/trackers/schedules/evaluate` | Evalúa schedules `on_bar_close` (`?trackerId=&force=false`) |

Schedule `on_bar_close`: tras cierre de barra (`1d`/`1wk`), el worker encola scan si hay barra nueva. Estado en `schedule.lastBarTimestamp` / `lastRunAt`.

Validación kernel: `timeframe` ∈ `{1d, 1wk}`; universo vía `listId` o `instrumentIds`.

---

## Execution policies (ADR-010 P5)

Políticas de ejecución manual/auto sobre señales de scan.

| Método | Ruta                                 | Descripción                                                                              |
| ------ | ------------------------------------ | ---------------------------------------------------------------------------------------- |
| GET    | `/api/execution-policies`            | Listado (`?enabled_only=true` opcional)                                                  |
| GET    | `/api/execution-policies/{id}`       | Detalle + `ExecutionPolicyV1`                                                            |
| POST   | `/api/execution-policies`            | Crear (201)                                                                              |
| PATCH  | `/api/execution-policies/{id}`       | Actualizar                                                                               |
| DELETE | `/api/execution-policies/{id}`       | Eliminar (204)                                                                           |
| POST   | `/api/execution-policies/{id}/route` | Enrutar hits. `paper_auto` exige `PAPER_D_EXECUTE` (403 `paper_auto_env_blocked` si off) |
| POST   | `/api/scans/jobs/{jobId}/execute`    | Igual: hits de job completado; mismo gate `paper_auto`                                   |

Modos: `inform_only`, `alert`, `paper_auto` (live reservado). `paper_auto` requiere `accountId` paper/simulated **y** `PAPER_D_EXECUTE=1` en estos HTTP (Ciclo I3; **no** es thaw).

---

## Position policies (ADR-010 P6)

Política sobre una posición ya abierta (cuenta + instrumento).

| Método | Ruta                            | Descripción                                 |
| ------ | ------------------------------- | ------------------------------------------- |
| GET    | `/api/position-policies`        | Listado (`?accountId=` opcional)            |
| GET    | `/api/position-policies/lookup` | Por `accountId` + `instrumentId`            |
| GET    | `/api/position-policies/{id}`   | Detalle + `PositionPolicyV1`                |
| POST   | `/api/position-policies`        | Crear (201) — unique por cuenta+instrumento |
| PATCH  | `/api/position-policies/{id}`   | Actualizar                                  |
| DELETE | `/api/position-policies/{id}`   | Eliminar (204)                              |

Modos: `manual`, `exit_strategy` (+ `exitStrategyDefinitionId`), `full_auto` (+ `executionPolicyId`).

| Método | Ruta                                    | Descripción                                                     |
| ------ | --------------------------------------- | --------------------------------------------------------------- |
| POST   | `/api/position-policies/evaluate-exits` | Evalúa salidas (`?accountId=&executeTrades=false&timeframe=1d`) |

---

## Platform events (ADR-010 P10)

Bus append-only de auditoría interna.

| Método | Ruta                   | Descripción                                              |
| ------ | ---------------------- | -------------------------------------------------------- |
| GET    | `/api/platform-events` | Listado (`?limit=50&type=scan.completed&correlationId=`) |

Tipos: `signal.emitted`, `scan.completed`, `backtest.completed`, `execution.order_requested`, `execution.order_filled`.

---

## Backtests

| Método | Ruta                  | Descripción                             |
| ------ | --------------------- | --------------------------------------- |
| GET    | `/api/backtests`      | Listado runs                            |
| GET    | `/api/backtests/{id}` | Detalle + trades + manifest             |
| POST   | `/api/backtests/run`  | Ejecutar (preset o estrategia guardada) |

## Strategies (BT-2)

| Método | Ruta                                | Descripción                                 |
| ------ | ----------------------------------- | ------------------------------------------- |
| GET    | `/api/strategies`                   | Listado estrategias guardadas               |
| GET    | `/api/strategies/{id}`              | Detalle + `StrategyDefinitionV1`            |
| POST   | `/api/strategies/from-preset`       | Crear desde preset (`name`, `presetKey`, …) |
| POST   | `/api/strategies/draft-from-prompt` | Borrador desde NL (AI-1 H0)                 |
| POST   | `/api/strategies`                   | Crear con `definition` JSON completa        |
| PATCH  | `/api/strategies/{id}`              | Actualizar                                  |
| DELETE | `/api/strategies/{id}`              | Eliminar                                    |

**`POST /api/strategies/draft-from-prompt`** — body `{ prompt, instrumentIds? }`. Via `AIGovernanceProxy` + fallback heurístico. Respuesta `data`: `draftKind`, `presetKey`, `definition`, `confidence`, `feedback` (incluye `fundamentalPreview` si el prompt menciona PER/capitalización).

## Indicators IA

| Método | Ruta                                | Descripción                         |
| ------ | ----------------------------------- | ----------------------------------- |
| POST   | `/api/indicators/draft-from-prompt` | Borrador `IndicatorPreset` desde NL |

**`POST /api/indicators/draft-from-prompt`** — body `{ prompt, chartTimeframe? }`. Authoring vía `AIGovernanceProxy` (RFC-007): `BOLSA_LLM_PROVIDER=ollama|openai|none`; fallback heurístico local. Respuesta: `definitionId`, `preset`, `confidence`, `feedback`.

| GET | `/api/ai/status` | Estado Proxy (provider, Ollama/OpenAI, audit sink) |

**Env LLM:** `BOLSA_LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OPENAI_API_KEY`, `BOLSA_LLM_AUDIT_PATH` (JSONL), `BOLSA_LLM_AUDIT_BACKEND=pg|both` (tabla `llm_calls`).

### Features (RFC-005)

| Método | Ruta                    | Descripción                                                         |
| ------ | ----------------------- | ------------------------------------------------------------------- |
| GET    | `/api/features/catalog` | Catálogo bootstrap DEFs + `fset_core_v1`                            |
| GET    | `/api/features/latest`  | Materializa snapshot (`instrumentId`, `featureSetId?`, `barLimit?`) |

Motores IA en chart: `technical_rating_v1`, `bar_data_quality_v1`, `ai_global_score_v1`, `strategy_hybrid_score_v1` (publicado desde estrategia guardada).

**Body `POST /api/backtests/run`:**

| Campo                  | Tipo                                    | Default                              |
| ---------------------- | --------------------------------------- | ------------------------------------ |
| `instrumentId`         | string                                  | —                                    |
| `strategyType`         | `sma_crossover` \| `rsi_mean_reversion` | — (si no hay `strategyDefinitionId`) |
| `strategyDefinitionId` | string                                  | — (alternativa a `strategyType`)     |
| `initialCash`          | number                                  | 10000                                |
| `limit`                | number                                  | 500                                  |
| `timeframe`            | string                                  | `1d`                                 |
| `commissionBps`        | number                                  | 0                                    |
| `slippageBps`          | number                                  | 0                                    |

Cada run persiste un **RunManifest** JSON (reproducibilidad). El detalle incluye `equityCurve` (BT-4) y `trades`. Ver [research-platform.ts](../packages/shared/src/research-platform.ts) y [BACKTESTING_DATA_ARCHITECTURE.md](./BACKTESTING_DATA_ARCHITECTURE.md).

### POST `/api/backtests/optimize` (RD-3)

Grid search SMA crossover sobre histórico en BD. Motores: `vectorbt_sma_grid`, `optuna_sma`, `sma_grid_h0`.

| Campo          | Tipo                                     | Default              |
| -------------- | ---------------------------------------- | -------------------- |
| `instrumentId` | string                                   | —                    |
| `fastPeriods`  | number[]                                 | 10,15,20,25,30       |
| `slowPeriods`  | number[]                                 | 40,50,60,80,100      |
| `initialCash`  | number                                   | 10000                |
| `barLimit`     | number                                   | 500                  |
| `timeframe`    | string                                   | `1d`                 |
| `maxTrials`    | number                                   | 200 (Optuna cap 100) |
| `engine`       | `auto` \| `vectorbt` \| `optuna` \| `h0` | `auto`               |

Respuesta: `{ data: { instrumentId, barCount, baseline, trials[], engine } }` — `engine`: `vectorbt_sma_grid`, `optuna_sma` o `sma_grid_h0`.

---

## Alerts

| Método | Ruta                          | Descripción         |
| ------ | ----------------------------- | ------------------- |
| GET    | `/api/alerts?activeOnly=`     | Listar alertas      |
| POST   | `/api/alerts`                 | Crear alerta precio |
| DELETE | `/api/alerts/{id}`            | Eliminar            |
| POST   | `/api/alerts/{id}/reactivate` | Reactivar disparada |
| POST   | `/api/alerts/evaluate`        | Evaluar manualmente |

Evaluación automática en background cada ~20 s (`daily_alert_evaluator` para price; `signal_alert_evaluator` para estrategia + webhook/email).

---

## Market

| Método | Ruta                             | Descripción          |
| ------ | -------------------------------- | -------------------- |
| GET    | `/api/market/providers`          | Estado Yahoo/XTB     |
| GET    | `/api/market/fx?from=USD&to=EUR` | Tipo de cambio Yahoo |

---

## Cliente frontend

Todos los métodos están en `apps/web/src/lib/api.ts`. Los tipos en `packages/shared/src/types.ts`.

Convención JSON: **camelCase** en request/response (Pydantic `alias`).

---

## Códigos de error habituales

| HTTP | Significado                           |
| ---- | ------------------------------------- |
| 401  | Token inválido o auth requerida       |
| 404  | Instrumento/lista no encontrado       |
| 422  | Validación Pydantic                   |
| 502  | Sync Yahoo fallido (`status: failed`) |

Errores en frontend: clase `ApiError` con `message` y `status`.
