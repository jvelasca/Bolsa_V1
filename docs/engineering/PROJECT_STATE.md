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

| Código         | Objetivo                                                                                                                                    | Estado                             | Riesgo     | Fracción            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | ---------- | ------------------- |
| **F-IND-1**    | Causality Layer: distinguir indicadores **causales vs visualización**; prohibir features no causales (chikou/fractals) en backtest/research | ✅ MERGED (79fa155)                | Medio      | v1                  |
| **F-IND-2**    | Batería de tests de causalidad en CI (`feature_at_t` con/sin barra futura idéntico para todos los indicadores)                              | 🟢 COMMITED (09fb06b, pend. merge) | Bajo       | 🔵 **activa ahora** |
| **F-FIN-1**    | `get_or_create_default_portfolio()` por nombre global → scope por cuenta (ADR-008)                                                          | 🟢 COMMITED (f595761, pend. merge) | Alto       | v3                  |
| **F-FIN-2**    | `GetTaxReport` `limit=10000` + sin filtro por año en SQL                                                                                    | 🟠 PENDIENTE                       | Medio      | 🔵 **activa ahora** |
| **F-SEG-1**    | Fail-closed production + comparaciones constantes (`secrets.compare_digest`) — **auth JWT sigue diferida (D4)**                             | 🟠 PENDIENTE                       | Bajo       | v5                  |
| **F-SEG-2**    | Auditoría historial git (repo público) + rotación de logs + tests negativos de redacción                                                    | 🟠 PENDIENTE                       | Bajo-Medio | v6                  |
| **F-SEG-3**    | CORS mínimo privilegio + `X-Forwarded-For`/TrustedHost en rate-limit                                                                        | 🟡 PENDIENTE                       | Bajo       | v7                  |
| **F-HLTH-1**   | Mojibake en `workspace-store-core.ts` (2 strings UI + ~26 JSDoc)                                                                            | 🟡 PENDIENTE                       | Bajo       | v8                  |
| **F-DEBT-1**   | Deuda cierre ola: P1.9 API thin + P2.6 DTOs TS↔Py + mypy ~450 por fases                                                                     | 🟡 PENDIENTE                       | Medio      | v9                  |
| **F-WORKER-1** | Warning auto-sync ticker `BP/.L` (Yahoo 404) — retomar subagente con `resume`                                                               | 🟡 ABIERTO                         | Bajo       | v10                 |

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

### Aún vigentes (hacen el plan)

1. **Look-ahead en `chikou` (Ichimoku) y `fractals`** → F-IND-1/F-IND-2. `compute.py:824-825` (`chikou[index]=bars[index+displacement]`) y `:778-779` (fractals usa `bars[index±2]`). Correcto para visualización; NO como feature causal.
2. **`GetTaxReport` `limit=10000` sin filtro por año** → F-FIN-2 (`accounts.py:589-603`).
3. **Fail-closed production ausente** → F-SEG-1 (`config.py`, no valida `ENVIRONMENT=prod`+sin password).
4. **Comparaciones `==` no constantes** → F-SEG-1 (`tokens.py:17`, `auth.py:42`).
5. **Repo público + 155,8 MB de logs sin rotación** → F-SEG-2.
6. **CORS `allow_methods=["*"]`/`allow_headers=["*"]`** → F-SEG-3.
7. **Mojibake `workspace-store-core.ts`** (halzg encontrado por auditoría interna propia) → F-HLTH-1.

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
> `stage/f1-integridad-financiera-2026-08-11` (HEAD `79fa155` = merge F-IND-1 · más `09fb06b` F-IND-2 commited y
> `f595761` F-FIN-1 commited, pend. push/merge). Árbol limpio. CI verde.
>
> Estado vivo y deuda priorizada en `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO). Mapa de fases mergeadas en
> `docs/engineering/engineering-index-2026-08-03.md` §5.
>
> F-IND-1 (Causality Layer), F-IND-2 (batería de causalidad `feature_at_t` con/sin
> barra futura en CI) y F-FIN-1 (fail-closed del default de cartera por cuenta) **hechas** (ver §3).
>
> PRÓXIMA FASE pactada: **F-FIN-2** — `GetTaxReport` `limit=10000` + sin filtro por año en SQL
> (`accounts.py:589-603`). Riesgo Medio. Después: F-SEG-1..3, F-HLTH-1, F-DEBT-1, F-WORKER-1 (ver §3).
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

| Fecha      | Acción                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-19 | Recibida Auditoría externa 1 (análisis cuantitativo/causalidad). Verificada contra el código real. Se detecta que gran parte ya está corregida (ola F1–F5a) y que el hueco real persiste en la causalidad de indicadores.                                                                                                                                                                                                                                  |
| 2026-08-19 | Pactado el plan profundo por fases (F-IND/F-FIN/F-SEG/F-HLTH/F-DEBT/F-WORKER) con orden por riesgo de dinero/verdad.                                                                                                                                                                                                                                                                                                                                       |
| 2026-08-19 | Creado este documento maestro como fuente única de estado y punto de entrada de relevos.                                                                                                                                                                                                                                                                                                                                                                   |
| 2026-08-19 | Decisiones del usuario: arrancar F-IND-1 · crear PROJECT_STATE.md (sí) · auth diferida (fail-closed + compare_digest solo en F-SEG-1).                                                                                                                                                                                                                                                                                                                     |
| 2026-08-19 | **F-IND-1 MERGED** (`79fa155`, merge): Causality Layer — metadatos causal/confirmationLag/visualizationOffset en indicator-universe + guardia `_NON_CAUSAL_OUTPUT_LINES` (chikou/fractals excluidas del backtest) + `validate_strategy_definition` rechaza no causales.                                                                                                                                                                                    |
| 2026-08-19 | **F-IND-2 COMMITED** (`09fb06b`, pend. push/merge): batería `test_causality_battery_ind_2.py` (34 tests) — `feature_at_t` con/sin barra futura idéntico para todos los indicadores; 31 causales estables + 2 canarios no causales (chikou/fractals) + guard de cobertura. ruff/mypy ✓ · pytest analytics 362✓.                                                                                                                                             |
| 2026-08-19 | **F-FIN-1 COMMITED** (`f595761`, pend. push/merge): fail-closed del default de cartera. Eliminado `get_or_create_default_portfolio()` (default global por nombre); `_resolve_portfolio` exige `legacy_portfolio_id: str` y lanza `ValueError` si no existe — el scope a la cartera siempre viene resuelto por cuenta (ADR-008). Test anti-regresión `test_fin1_no_global_default_portfolio_by_name`. ruff/mypy ✓ · infra 49p · application 224p · api 29p. |
