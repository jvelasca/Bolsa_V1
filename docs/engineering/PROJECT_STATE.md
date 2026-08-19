# PROJECT_STATE — Estado vivo del proyecto (fuente única de continuación)

> **Propósito:** Punto de ENTRADA y SALIDA de cada chat/agente/relevo. Es el "único padre" del estado actual, según audit externa 2026-08-19 (evitar _documentation archaeology_).
> **AsOf:** 2026-08-19 (revisado)
> **Base de referencia (checkpoint):** rama `stage/f1-integridad-financiera-2026-08-11` · commit `4ec0520` (merge PR #53 → openapi-fetch). Árbol limpio en el momento de redactar.
> **Padre documental:** [Engineering Index](./engineering-index-2026-08-03.md) (este doc es un nodo de estado, no una nueva raíz).
> **Regla del hilo actual (pactada 2026-08-19):** NO tocar código fuera del alcance de la fase declarada. Cada fase se ejecuta EN UN SUBAGENTE acotado, con batería y APROBACIÓN del usuario por commit. Máx. ~3 subagentes en paralelo por chat. Al cerrar un chat se actualiza ESTE documento y el `engineering-index` §5.

---

## 1. Arquitectura / capas (para orientación rápida)

```
apps/web            React 19 + Vite + zustand + TanStack Query + lightweight-charts
apps/api-python     FastAPI (API activa, :8000) — capa delgada + DI (dependencies.py)
packages/py/domain        entidades puras + Protocols (cero deps; import-linter lo fuerza)
packages/py/application   casos de uso (sin HTTP)
packages/py/infrastructure SQLAlchemy + Alembic (autoridad DB) + repos
packages/py/analytics     indicadores, señales, predict, optimize, cognitive
packages/py/market        providers (Yahoo, XTB), indices, fundamentals
packages/py/ai            gobernanza LLM (proxy → motor determinista; LLM NO ejecutor)
packages/shared           DTOs TS (contrato con FE)
packages/database         Prisma → DEGRADADO a cliente/léxico read-only (Alembic = autoridad)
```

Patrón sancionado: **LLM interpreta/propone → motor determinista decide → confirmación humana → Execution Router → paper**. No romper.

---

## 2. Estado de ejecución — ola de refactorización/integridad

Plan original de hardening pactado 2026-08-11 (fases F1–F5a). Estado MERGEADO (todo en la rama base arriba):

| Fase          | Contenido                                                                                | Estado                                                                         |
| ------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **F1**        | Integridad financiera: `with_for_update`, `deduct_cash`, idempotencia trade, invariantes | ✅ MERGED                                                                      |
| **F2**        | Backtest `next_open` (fill `open[t+1]`), fingerprint, recálculo de trials                | ✅ MERGED (**NOTA: NO incluye causalidad de indicadores — pendiente F-IND-1**) |
| **F3a/F3b**   | Workers fuera de FastAPI (D3) + Alembic única autoridad (D2)                             | ✅ MERGED                                                                      |
| **F4**        | Arquitectura Python: ciclo analytics↔market roto, ruff+mypy gates                        | ✅ MERGED                                                                      |
| **F5a**       | openapi-fetch cliente completo + contract bidireccional (`contract-check.ts`)            | ✅ MERGED (PR #52/#53)                                                         |
| **F5b/F5c**   | rate-limit distribuido, upsert bulk, P2.7 amounts, cleanup frontend                      | ✅ MERGED                                                                      |
| **P2.1/P2.8** | god-components + as-unknown-as                                                           | ✅ MERGED                                                                      |

**Consecuencia clave:** gran parte de los hallazgos de las auditorías externas de 2026-08-11 **ya están corregidos**. La auditoría externa recibida el 2026-08-19 combina hallazgos desactualizados con otros vigentes (ver §4).

---

## 3. Deuda PENDIENTE (priorizada 2026-08-19)

> Orden por **riesgo de dinero / verdad de resultados** (no por severidad rotulada). Prioridad síntoma: **causalidad de indicadores** = único hueco serio de integridad que queda tras F2.

| Código         | Objetivo                                                                                                                                                                 | Estado                             | Riesgo     | Fracción            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------- | ---------- | ------------------- |
| **F-IND-1**    | Causality Layer: distinguir indicadores **causales vs visualización**; prohibir features no causales (chikou/fractals) en backtest/research                              | ✅ MERGED (79fa155)                | Medio      | v1                  |
| **F-IND-2**    | Batería de tests de causalidad en CI (`feature_at_t` con/sin barra futura idéntico para todos los indicadores)                                                           | 🟢 COMMITED (09fb06b, pend. merge) | Bajo       | 🔵 **activa ahora** |
| **F-FIN-1**    | `get_or_create_default_portfolio()` por nombre global → scope por cuenta (ADR-008)                                                                                       | 🟢 COMMITED (f595761, pend. merge) | Alto       | v3                  |
| **F-FIN-2**    | `GetTaxReport` `limit=10000` + sin filtro por año en SQL                                                                                                                 | 🟢 COMMITED (9a35405, pend. merge) | Medio      | v4                  |
| **F-SEG-1**    | Fail-closed production + comparaciones constantes (`secrets.compare_digest`) — **auth JWT sigue diferida (D4)**                                                          | 🟢 COMMITED (4b7a984, pend. merge) | Bajo       | v5                  |
| **F-SEG-2**    | Auditoría historial git (repo público) + rotación de logs + tests negativos de redacción                                                                                 | 🟢 COMMITED (dcb8a37, pend. merge) | Bajo-Medio | v6                  |
| **F-SEG-3**    | CORS mínimo privilegio + `X-Forwarded-For`/TrustedHost en rate-limit                                                                                                     | 🟢 COMMITED (e628ae3, pend. merge) | Bajo       | v7                  |
| **F-HLTH-1**   | Mojibake en `workspace-store-core.ts` (2 strings UI + ~26 JSDoc)                                                                                                         | 🟢 COMMITED (2400a4b, pend. merge) | Bajo       | v8                  |
| **F-DEBT-1**   | P1.9 API thin (adelgazar endpoints FastAPI). **mypy ~450 ya cerrado (P1.6, `6a89f6c`)**; P2.6 DTOs TS↔Py → F-DEBT-2 (deuda futura)                                       | 🟠 PENDIENTE                       | Medio      | 🔵 **activa ahora** |
| **F-DEBT-2**   | (Deuda futura) P2.6 DTOs TS↔Py: consolidar tipos web-only (`RecommendationV1`/`CoreRVerdict`/`RunManifest`/`execution-policies`/`tax-report`, etc.) en `packages/shared` | 🟡 PENDIENTE                       | Bajo-Medio | v10                 |
| **F-WORKER-1** | Warning auto-sync ticker `BP/.L` (Yahoo 404) — retomar subagente con `resume`                                                                                            | 🟡 ABIERTO                         | Bajo       | v10                 |

**Anti-objetivos (freeze vigente):** sin features nuevas · sin reabrir Belief/H · sin tocar gobernanza IA ni dominio puro · auth JWT diferida (decisión D4) hasta decisión de exponer la app.

---

## 4. Verificación de la Auditoría externa 1 (2026-08-19) contra el código real

> Realizado por el agente coordinador el 2026-08-19. Para NO recrear trabajo ya hecho ni asumir hallazgos caducados.

### Ya corregidos (no volver a tocar)

- Backtest "misma barra" → **corregido** a `next_open` (`backtest.py:253,320,343`).
- Concurrencia sin lock → **corregido**: `with_for_update=True` en trade/cartera/posición/transferencias (`portfolio_repository.py:238-259,373-404`).
- `APP_AUTH_SECRET="bolsa-dev-secret"` default → **corregido**: default vacío + validator que lo rechaza (`config.py:31,158-167`).
- Workers en `lifespan` FastAPI → **corregido** (F3a/D3): `scheduler_worker` dedicado (`main.py:56-65`).
- Sin idempotencia trade → **corregido**: `idempotencyKey` + test (`accounts.py:494-503`).
- Drift contrato FE/BE → **corregido**: openapi-fetch + gate bidireccional (`contract-check.ts`).
- Ciclo analytics↔market → **corregido** (F4).
- Rate limit in-memory → **parcialmente corregido**: `RedisStore` con fallback. **Pendiente**: IP sin `X-Forwarded-For` (F-SEG-3).
- Default global por nombre → **corregido** (F-FIN-1, `f595761`): `get_or_create_default_portfolio()` eliminado; scope fail-closed obligatorio por cuenta (`portfolio_repository.py:_resolve_portfolio`).
- Tax-report con `limit=10000` y sin filtro por año → **corregido** (F-FIN-2, `9a35405`): `fiscal_year_range` en dominio; transacciones hasta el fin del ejercicio sin truncado de cost basis; ledger/total_fees filtrados por rango; `fees_paid_total` solo del año.
- Fail-closed production ausente → **corregido** (F-SEG-1, `4b7a984`): `config.py` bloquea el arranque si `ENVIRONMENT=prod`/`production` sin `APP_PASSWORD` o con `APP_AUTH_SECRET` vacío/`bolsa-dev-secret`.
- Comparaciones `==` no constantes → **corregido** (F-SEG-1, `4b7a984`): `secrets.compare_digest` en `tokens.py:17` y `routes/auth.py:42`.
- Repo público + 155,8 MB de logs sin rotación → **corregido** (F-SEG-2, `dcb8a37`): `pruneStampedLogs()` en `logger.mjs` conserva las 10 sesiones `dev` más recientes (`DEV_LOG_KEEP` configurable), invocado en `run-dev.mjs`. Historial git auditado (solo valores dev históricos; purga no ejecutada por protocolo). **Pendiente manual**: limpiar ~150 MB de `logs/dev/*.log` antiguos en disco.
- Redacción de secretos en logs/repr → **corregido** (F-SEG-2, `dcb8a37`): `__repr__` de `config.py` redacta `app_password`/`app_auth_secret`/`db_password` + credenciales DSN; `logging_redact.py` +3 patrones (`.app_password`/`.app_auth_secret`/`.db_password`).
- CORS `allow_methods=["*"]`/`allow_headers=["*"]` → **corregido** (F-SEG-3, `e628ae3`): `main.py` pasa a listas explícitas (`GET/POST/PUT/PATCH/DELETE/OPTIONS`; `Content-Type/Authorization/X-Account-Id/Accept`).
- Rate-limit confiaba en `client.host` sin `X-Forwarded-For` → **corregido** (F-SEG-3, `e628ae3`): `get_client_ip()` en `rate_limit.py` usa la primera IP del `XFF` **solo** si el peer inmediato está en `TRUSTED_PROXIES` (config nueva, default vacío → dev/local sin proxy usa `client.host`; anti-spoofing).
- Mojibake `workspace-store-core.ts` → **corregido** (F-HLTH-1, `2400a4b`): 2 strings UI (`Gráfico`) + ~28 JSDoc/comentarios en UTF-8 correcto; lógica intacta.

### Aún vigentes (hacen el plan)

1. **Look-ahead en `chikou` (Ichimoku) y `fractals`** → F-IND-1/F-IND-2. `compute.py:824-825` (`chikou[index]=bars[index+displacement]`) y `:778-779` (fractals usa `bars[index±2]`). Correcto para visualización; NO como feature causal.

---

## 5. Protocolo de ejecución (obligatorio por fase)

1. Cada fase = un SUBAAGENTE acotado (tarea + archivos + criterios de aceptación claros; prohibido tocar fuera).
2. Batería por fase:
   - Py: `ruff` + `mypy` + `pytest` (y el test específico de la fase).
   - Web: `pnpm --filter @bolsa/web typecheck` + `lint` + `build` (+ `test` si toca FE).
   - Global: `pnpm test` (turbo) + CI GitHub al merge.
3. Commit + push POR PASO APROBADO por el usuario. Todo en rama `stage/*` desde el checkpoint.
4. Si algo falla → volver al checkpoint y documentar.
5. Control de saturación: máx. ~3 subagentes en paralelo por chat. Al cerrar un chat, actualizar ESTE doc + texto de paso (§6).

---

## 6. Texto de traspaso (pegable en el próximo chat)

> CONTEXTO: Proyecto en ola de hardening pactada 2026-08-11, casi todo MERGED en
> `stage/f1-integridad-financiera-2026-08-11` (HEAD `79fa155` = merge F-IND-1 · más `09fb06b` F-IND-2,
> `f595761` F-FIN-1, `9a35405` F-FIN-2, `4b7a984` F-SEG-1, `dcb8a37` F-SEG-2, `e628ae3` F-SEG-3 y
> `2400a4b` F-HLTH-1 commited/pusheados, pend. merge). Árbol limpio. CI verde.
>
> Estado vivo y deuda priorizada en `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO). Mapa de fases mergeadas en
> `docs/engineering/engineering-index-2026-08-03.md` §5.
>
> F-IND-1 (Causality Layer), F-IND-2 (batería de causalidad), F-FIN-1 (fail-closed del default de cartera por
> cuenta), F-FIN-2 (ejercicio fiscal en `GetTaxReport`), F-SEG-1 (fail-closed production + `compare_digest`),
> F-SEG-2 (rotación de logs + redacción de secretos), F-SEG-3 (CORS mínimo privilegio + `X-Forwarded-For`/
> TrustedHost en rate-limit) y F-HLTH-1 (mojibake) **hechas** (ver §3).
>
> PRÓXIMA FASE pactada: **F-DEBT-1 = P1.9 API thin** (adelgazar endpoints FastAPI; proxies/serializaciones
> delgados actuales = deuda de F4/F5b). **Alcance exclusivo: SOLO P1.9**. **mypy ~450 ya cerrado (P1.6, `6a89f6c`)**
> y **P2.6 DTOs TS↔Py → F-DEBT-2** (deuda futura). **Riesgo Medio**. Después: F-WORKER-1 · F-DEBT-2 (ver §3).
>
> Nota F-IND-1/2: la guardia de causalidad puede cambiar resultados de backtests que usen
> chikou; documentado y ya respaldado por la batería F-IND-2 (no recalcular aún).
>
> Regla: tipo de cambio = un subagente acotado + batería + aprobación por commit. No tocar código fuera del alcance
> declarado. Auth JWT diferida (D4). NO reabrir Belief/H ni gobernanza IA.
>
> Warning operativo abierto: auto-sync ticker `BP/.L` (Yahoo 404) — retomar con `resume` si el informe del
> subagente previo no está (F-WORKER-1).

---

## 7. Registro del plan 2026-08-19

| Fecha      | Acción                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-19 | Recibida Auditoría externa 1 (análisis cuantitativo/causalidad). Verificada contra el código real. Se detecta que gran parte ya está corregida (ola F1–F5a) y que el hueco real persiste en la causalidad de indicadores.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| 2026-08-19 | Pactado el plan profundo por fases (F-IND/F-FIN/F-SEG/F-HLTH/F-DEBT/F-WORKER) con orden por riesgo de dinero/verdad.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| 2026-08-19 | Creado este documento maestro como fuente única de estado y punto de entrada de relevos.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| 2026-08-19 | Decisiones del usuario: arrancar F-IND-1 · crear PROJECT_STATE.md (sí) · auth diferida (fail-closed + compare_digest solo en F-SEG-1).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 2026-08-19 | **F-IND-1 MERGED** (`79fa155`, merge): Causality Layer — metadatos causal/confirmationLag/visualizationOffset en indicator-universe + guardia `_NON_CAUSAL_OUTPUT_LINES` (chikou/fractals excluidas del backtest) + `validate_strategy_definition` rechaza no causales.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| 2026-08-19 | **F-IND-2 COMMITED** (`09fb06b`, pend. push/merge): batería `test_causality_battery_ind_2.py` (34 tests) — `feature_at_t` con/sin barra futura idéntico para todos los indicadores; 31 causales estables + 2 canarios no causales (chikou/fractals) + guard de cobertura. ruff/mypy ✓ · pytest analytics 362✓.                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| 2026-08-19 | **F-FIN-1 COMMITED** (`f595761`, pend. push/merge): fail-closed del default de cartera. Eliminado `get_or_create_default_portfolio()` (default global por nombre); `_resolve_portfolio` exige `legacy_portfolio_id: str` y lanza `ValueError` si no existe — el scope a la cartera siempre viene resuelto por cuenta (ADR-008). Test anti-regresión `test_fin1_no_global_default_portfolio_by_name`. ruff/mypy ✓ · infra 49p · application 224p · api 29p.                                                                                                                                                                                                                                                                                                          |
| 2026-08-19 | **F-FIN-2 COMMITED** (`9a35405`, pusheado): ejercicio fiscal en `GetTaxReport`. `fiscal_year_range(year,start_month)` en dominio (rango `[inicio,fin)` UTC). `list_transactions` acepta `limit=None`+`executed_before=fiscal_end` (preserva carry-in FIFO/avg, excluye años futuros, elimina el truncado de `limit=10000`). `list_for_account`/`total_fees_for_account` filtran por rango. `fees_paid_total` suma solo fees del año. Test `test_tax_report_fiscal.py` (5). ruff/mypy ✓ · domain 14p · application 224p · infra 49p · api 29p + integration 1p.                                                                                                                                                                                                      |
| 2026-08-19 | **F-SEG-1 COMMITED** (`4b7a984`, pusheado): fail-closed production + comparaciones constantes. `config.py` bloquea el arranque si `ENVIRONMENT=prod`/`production` sin `APP_PASSWORD` o con `APP_AUTH_SECRET` vacío/`bolsa-dev-secret` (fail-closed condicionado a prod para no romper dev/tests/CI). `tokens.py:17` y `routes/auth.py:42` de `==` → `secrets.compare_digest`. Test `test_config.py` +5 (prod sin password, secreto vacío, dev-secret, secreto real OK) + anti-regresión dev sin password. ruff/mypy ✓ · config/auth 14p · api 29p · infra 49p + app 224p + startup 5p.                                                                                                                                                                              |
| 2026-08-19 | **F-SEG-2 COMMITED** (`dcb8a37`, pusheado): auditoría git + rotación de logs + redacción de secretos. Historial 417 commits auditado (solo valores dev `bolsa:bolsa_dev`/`bolsa-dev-secret` históricos, ya eliminados en HEAD; purga no ejecutada por protocolo; activar GitHub secret scanning). Rotación: `pruneStampedLogs()` en `logger.mjs` conserva 10 sesiones dev (`DEV_LOG_KEEP`), invocado en `run-dev.mjs`. Redacción: `__repr__` de `config.py` redacta `app_password`/`app_auth_secret`/`db_password` + credenciales DSN; `logging_redact.py` +3 patrones. +5 tests negativos (test_config ×3, test_q2_hygiene ×2). Batería: ruff 0 · node --check OK · config 15p ✓ · hygiene 3p ✓ · infra 57p ✓.                                                     |
| 2026-08-19 | **F-SEG-3 COMMITED** (`e628ae3`, pusheado): CORS mínimo privilegio + rate-limit TrustedHost. `main.py`: `allow_methods`/`allow_headers` pasan de `*` a listas explícitas (`GET/POST/PUT/PATCH/DELETE/OPTIONS`; `Content-Type/Authorization/X-Account-Id/Accept`) según el contrato real del FE (verificado en `apps/web/src/lib/api.ts`). `rate_limit.py`: nueva `get_client_ip()` anti-spoofing — usa la primera IP de `X-Forwarded-For` **solo** si el peer inmediato está en `TRUSTED_PROXIES` (config nueva `trusted_proxies`, default vacío → dev/local sin proxy usa `client.host`); fallback `RedisStore`→`MemoryStore` intacto. +10 tests (`test_cors.py` ×5, `test_rate_limit.py` +5). Batería: ruff 0 · CORS/rate-limit/config 38p ✓ · API offline 47p ✓. |
| 2026-08-19 | **F-HLTH-1 COMMITED** (`2400a4b`, pusheado): corregido mojibake en `apps/web/src/stores/workspace-store-core.ts` (patrón UTF-8→Latin-1). 2 strings UI `Gráfico` (labels por defecto de pestaña) + ~28 JSDoc/comentarios (último/gráficos/más/membresía/política/pestañas/próximo + →/—/…). Solo comentarios y strings de label; lógica intacta (verificado por diff). Hecho directo en el hilo sin subagente (fix acotado a un archivo). Batería web: typecheck 0 ✓ · lint 0 ✓ (2 warnings preexistentes ajenos) · build OK ✓.                                                                                                                                                                                                                                      |
| 2026-08-19 | **F-DEBT-1 IMPLEMENTACIÓN PENDIENTE** (próxima fase, Riesgo Medio): deuda cierre de ola — P1.9 API thin + P2.6 DTOs TS↔Py + mypy ~450 por fases.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
