# Auditoría Consolidada (interna + externas) · Plan de Hardening Pactado — 2026-08-11

> **AsOf:** 2026-08-11
> **Checkpoint git:** tag anotado `audit-checkpoint-2026-08-11` (HEAD `2683c49` · rama `stage/estudio-membership-operativa-2026-08-04` · árbol limpio) — **punto de retroceso** ante cualquier fallo durante la ejecución del plan.
> **Padre:** copia del [general-audit-plan-2026-08-10.md](./general-audit-plan-2026-08-10.md) y del [improvement-roadmap-post-audits-2026-08-02.md](./improvement-roadmap-post-audits-2026-08-02.md). Nuevo doc: **Audit Consolidado** (módulo) → una entrada en [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5.
> **Regla del hilo:** **NO se toca ningún fichero de código** durante esta auditoría/plan. Todo se documenta y se ejecuta por módulos, validando cada cambio con su batería, sin romper nada, y con GitHub siempre sincronizado y recuperable.

---

## 0. Fuentes del diagnóstico

1. **Auditoría interna (esta sesión, 2026-08-11):** frontend React (apps/web/src, ~647 ficheros), backend Python (domain/application/infrastructure/analytics/market/ai + FastAPI, ~385 módulos), capa de datos y shared (Prisma/SQLAlchemy/scripts), proceso/riesgos/CI. Hallazgos clave C1–C5, A1–A9, F1–F5.
2. **Auditoría externa 1 (2026-08-11):** 4 "fuegos críticos" (P0.1 look-ahead, P0.2 dataVersion, P0.3 ciclos, P0.4 mypy) + plan H1–H4.
3. **Auditoría externa 2 (2026-08-11):** análisis estático profundo del backend (~82k líneas Python / 614 ficheros) + 25 hallazgos puntuados y fases F0–F6.
4. **Auditoría externa 3 (2026-08-11):** consolidación de la 1+2 en un mapa definitivo P0/P1/P2 + sprint de hardening de 5 fases.

**Veredicto compartido por las 4 fuentes:** la arquitectura es conceptualmente sólida (Clean Architecture en Python, gobernanza de IA, Research Observatory), pero **no está lista para producción ni para investigación rigurosa** hasta cerrar: integridad financiera (concurrencia), rigor científico (backtest + hash de datos), arquitectura de procesos (workers) y contratos/seguridad.

---

## 1. Mapa consolidado de hallazgos

Códigos: **I**=interna, **E**=externa (1/2/3), ✅=verificado en código por esta sesión.

### 🔴 P0 — Bloqueantes de integridad/producción

| #        | Hallazgo                                                                                                                                                                                                                    | Fuente     | Verific.                             | Dónde                                                                                            |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| **P0.1** | **Backtest ejecuta en la misma barra (look-ahead/same-bar).** Señal calculada al cierre de `t` y fill al cierre de la misma barra `t` (`mid=bar.close`). Falta un `execution_model` explícito y fill a `open[t+1]` para 1D. | E1, E2, E3 | ✅                                   | `packages/py/analytics/src/bolsa_analytics/backtest.py:314,336-359`                              |
| **P0.2** | **`dataVersion`/BarFingerprint incompleto** (hash ~ timestamp+close): ATR/Keltner/Volumen/Costes v2 pueden cambiar sin que el manifest detecte el cambio de dataset.                                                        | E1, E3     | ⚠️ (requiere confirmar función hash) | componentes de fingerprint/manifest en analytics                                                 |
| **P0.3** | **Concurrencia financiera sin bloqueo de fila.** `execute_trade`/`deduct_cash`/`transfer_cash` sin `with_for_update()`/optimistic lock. Riesgo de sobregiro/doble gasto bajo requests+workers concurrentes.                 | I, E2, E3  | ✅                                   | `infrastructure/database/repositories/portfolio_repository.py:181-230,292-304`                   |
| **P0.4** | **Workers/schedulers embebidos en FastAPI `lifespan`** (≥9 tareas de fondo). `--workers 4` → duplicación de crons.                                                                                                          | E2, E3     | ✅                                   | `apps/api-python/src/bolsa_api/main.py:56-71` (scan ya tiene escape `arq`; crons no)             |
| **P0.5** | **Caos de esquema BD: Prisma + SQLAlchemy + Alembic(baseline)+scripts.** Alembic sin historial DDL; sólo ext Timescale. SQLAlchemy re-declara tablas a mano; runtime no usa Prisma.                                         | I, E2, E3  | ✅                                   | `packages/py/infrastructure/alembic/`, `models/tables.py`, `packages/database/prisma`            |
| **P0.6** | **Ciclo de dependencias `analytics ↔ market`** + deps no declaradas en `pyproject.toml`.                                                                                                                                    | E2, E3     | ✅                                   | `analytics/knowledge/filing_summary.py:10` (→market) · `market/news_snapshot.py:11` (→analytics) |

### 🟠 P1 — Calidad de servicio / resiliencia / seguridad

| #         | Hallazgo                                                                                                                                                                                              | Fuente    | Verific.               | Dónde                                                                            |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---------------------- | -------------------------------------------------------------------------------- |
| **P1.1**  | **Side-effects contables en GET**: `GetAccountSummary`/`GetTaxReport` invocan `ApplyCustodyFees` (deduce cash + ledger) en **lectura**; doble `resolve_scope`. Un GET muta saldos.                    | I         | ✅                     | `application/accounts.py:134,547` · `ApplyCustodyFees:327-386`                   |
| **P1.2**  | **`ensure_migrated()` en el path de peticiones**: migraciones/backfill destructivos (`_consolidate_single_portfolio_per_account` funde/borra) por request, flag per-instancia → reintentos/race.      | I, E2     | ✅                     | `infrastructure/.../account_repository.py:89-97,571`                             |
| **P1.3**  | **Token estático determinista sin expiración**: `sha256("bolsa:password:secret")`, sin nonce/TTL/revocación. Guardado en `localStorage` (`bolsa-auth`). `APP_AUTH_SECRET` default `bolsa-dev-secret`. | I, E2, E3 | ✅                     | `apps/api-python/.../auth/tokens.py:6-17` · `config.py` · `stores/auth-store.ts` |
| **P1.4**  | **Sin idempotencia**: `POST /api/portfolio/trade` y mutantes sin `idempotency_key`/`client_order_id` → doble click/retry duplica operación.                                                           | E2, E3    | ⚠️ (diseño confirmado) | esquema trades/trades request                                                    |
| **P1.5**  | **Drift de contratos FE/BE**: DTOs TypeScript a mano vs Pydantic; sin cliente generado desde OpenAPI → drift silencioso.                                                                              | I, E2, E3 | ✅                     | `packages/shared` (manual) · `api.ts`                                            |
| **P1.6**  | **Mypy no es gate duro**: `continue-on-error: true`, ~115–500 errores tipado.                                                                                                                         | I, E2, E3 | ✅                     | `.github/workflows/python-ci.yml`                                                |
| **P1.7**  | **Filings `index.json` read-modify-write sin lock** + filesystem síncrono en async + carga en memoria.                                                                                                | E2        | ⚠️                     | `data/filings/` + endpoint upload                                                |
| **P1.8**  | **Rate limit in-memory por proceso** (no compartido entre workers) y prefijos mal ordenados (`/api/ai/fundamentals` inalcanzable).                                                                    | I, E2     | ✅                     | `middleware/rate_limit.py`                                                       |
| **P1.9**  | **Api no "thin"**: rutas con SQL directo + composition root ~1100 líneas; use-cases con `session` crudo.                                                                                              | I, E2     | ✅                     | `api/dependencies.py`, `routes/research.py`, `accounts.py`, `ai_governance.py`   |
| **P1.10** | **Dominio/ledger en `float`** (+`Decimal(str(...))` al borde) en lugar de `Decimal`+`NUMERIC` consistente; `deduct_cash` descuenta menos silenciosamente (`fee=min(fee,cash)`).                       | I, E2, E3 | ✅                     | `domain/entities/account.py` · `portfolio_repository.py:292-304`                 |

### 🟡 P2 — Mantenibilidad / higiene

| #         | Hallazgo                                                                                                                                          | Fuente    | Dónde                                                                 |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | --------------------------------------------------------------------- |
| **P2.1**  | God-component / god-store frontend: `backtests-page.tsx` (~192KB / un componente), `workspace-store.ts` (~137KB).                                 | I, E1, E3 | `features/backtests/backtests-page.tsx` · `stores/workspace-store.ts` |
| **P2.2**  | Query keys incoherentes (`portfolio` con distintos scoping) + boilerplate de invalidación duplicado.                                              | I         | varios paneles (ver interna)                                          |
| **P2.3**  | `upsert_bars()` N+1: loop de `INSERT` 1×1 en vez de bulk `ON CONFLICT DO UPDATE`.                                                                 | E2        | `ohlcv_repository.py`                                                 |
| **P2.4**  | Validación de OHLCV asimétrica entre parser diario vs intradía de Yahoo.                                                                          | E2        | `yahoo_chart.py`                                                      |
| **P2.5**  | `/api/health` público expone detalles (URLs, Redis, errores DB).                                                                                  | E2        | health endpoint                                                       |
| **P2.6**  | `packages/shared`: 110 fuentes, 1 test, sin script `test` propio; lógica de negocio duplicada TS↔Py (`ai-indicator-series.ts`, `policy-gate.ts`). | I, E2     | `packages/shared`                                                     |
| **P2.7**  | DTOs Pydantic demasiado permisivos en trading (float genérico → NaN/Inf/negativos).                                                               | E2        | `TradeRequestDto`                                                     |
| **P2.8**  | Migraciones "legacy" dispersas en frontend; `toLocaleString("es-ES")` duplicado; `as unknown as` sistemático; timers 1.5–2s; a11y `Dialog`.       | I         | varios (ver interna)                                                  |
| **P2.9**  | Features críticos frontend sin tests (workspace, alerts, sync, auth, dashboard); tests frágiles (MagicMock ancho, PostgreSQL real).               | I, E2     | —                                                                     |
| **P2.10** | scripts/research copiados (campañas), baterías manuales paralelas, sin CI; índices docs desactualizados.                                          | I, E2     | `scripts/research/*` · `engineering-index`                            |

### ✅ Aspectos que las auditorías refuerzan como POSITIVOS (no tocar)

- Gobernanza de IA: **LLM ≠ ejecutor de órdenes** (interpreta/propone → confirmación humana → Execution Router → paper). Mantener.
- Separación del dominio ("no depende de infraestructura") protegida por Import Linter. Mantener.
- Motor científico: walk-forward, CPCV, PBO, OOS, WFE, edge reports, manifests, trials. Dirección correcta.
- Higiene de dependencias y gestión de secretos (gitleaks, `.gitignore`, `.secrets/` vacío) — **bien resuelto**.

---

## 2. Priorización acordada (cross fuentes → plan de hardening)

Las 4 fuentes coinciden en un plan de hardening **cero-features** en fases. Mapeo de fases a los P0/P1/P2 y a los módulos M0–M7 ya existentes:

| Fase   | Nombre                         | Contiene                                                                                                                   | Relación con M0–M7            |
| ------ | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| **F1** | Integridad financiera          | P0.3 (locks+Decimal), P1.10 (Decimal/NUMERIC), P1.4 (idempotencia), ledger invariants tests                                | extiende **M4** (riesgo alto) |
| **F2** | Rigor científico (backtest)    | P0.1 (fill `t+1 open` + `execution_model`), P0.2 (fingerprint OHLCV), test anti-lookahead, recálculo trials                | extiende **M6**               |
| **F3** | Arquitectura de procesos y DB  | P0.4 (workers fuera de FastAPI), P0.5 (Alembic única autoridad), P1.2 (quitar `ensure_migrated` del path), P1.9 (API thin) | **M4** + nuevo                |
| **F4** | Arquitectura Python            | P0.6 (romper ciclo analytics↔market, mover `MarketEvent` a domain), P1.6 (mypy gate por fases)                             | **M6** + M2                   |
| **F5** | Contratos, seguridad, frontend | P1.5 (openapi-typescript), P1.3 (auth HttpOnly cookie/TTL), P2.1 (backtests-page / workspace-store), P1.8, P2.3–P2.7       | **M5** + M0/M2                |

**Anti-objetivos (mantener el freeze):** no añadir features/familias/indicadores/ML; no reabrir Belief/Fase H; no tocar los positivos de gobernanza IA y dominio.

---

## 3. Protocolo de ejecución (para respetar "sin romper nada")

1. **Cada módulo/fase en un hilo/chat propio**, con su documento de trabajo (patrón `traspaso-*`).
2. **Batería por módulo** (como en general-audit-plan §8):
   - Web: `pnpm --filter @bolsa/web typecheck` + `lint` (0) + `test` + `build`.
   - Py: `ruff` + `mypy` + `pytest`.
   - Global: `pnpm test` (turbo) + CI en GitHub.
3. **Elevación de versión / recuperabilidad:** anclados al tag `audit-checkpoint-2026-08-11`. Toda rama de ejecución nace `stage/*` desde un merge a `origin/main` o desde el checkpoint, commit + push por paso aprobado. Si algo falla → volver al checkpoint.
4. **Decisión explícita** por cada cambio (nunca silencioso). Cambios atómicos y pequeños.

---

## 4. Decisiones abiertas a pactar (antes de ejecutar)

1. **P0.1 — ¿modelo de ejecución de backtest?** (a) `next_open` como default inmutable para 1D + `execution_model` explícito para MOC. (b) Backwards-compat configurable. Requiere confirmar impacto sobre los trials existentes (¿recalcular? ¿migrar parámetros?).
2. **P0.2 — ¿volcado del fingerprint?** Confirmar la función hash actual y el alcance del DatasetManifest.
3. **P0.5 — ¿Alembic única autoridad vs Prisma?** ADR-025 fija fuente de verdad del modelo; se propone reforzar Alembic como autoridad `postgres` y Prisma como cliente/léxico read-only (o retirar). Confirmar.
4. **P0.4 — ¿hasta dónde separar workers?** `arq`/proceso separado sólo para crons, o también scans/optimización. Confirmar con el estado `SCAN_QUEUE_BACKEND`.
5. **P1.3 — auth:** proyecto personal/local → mínimo `HttpOnly cookie + TTL + revocación` (sin OAuth2 todavía). Confirmar deadline de exposición pública (si la hay).
6. **Orden de ejecución propuesto (recomendado):** F1 → F2 → F3 → F4 → F5, respetando "cerrar el motor determinista antes que IA/ML".

---

## 5. Decisiones pactadas (RESUELTAS, 2026-08-11)

> Acuerdo con el usuario en esta sesión. Cada una pasa a ser política del plan; se ejecuta en su fase y hilo correspondiente, validando con la batería y con GitHub recuperable.

| #      | Decisión                        | Resolución                                                                                                                                                                                                                                               | Fase           |
| ------ | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| **D0** | Orden de ejecución              | F1 → F2 → F3b → F5a → (F3a + F4 + F5b). Priorizado por **riesgo de dinero / verdad de los resultados** (no por severidad etiquetada).                                                                                                                    | —              |
| **D1** | Modelo de backtest              | `next_open` inmutable para 1D (fill en `open[t+1]`) + `execution_model` explícito. **RECALCULAR trials/resultados históricos** (CORE-R, Finalistas, Lista AUTO, DÍA D) tras el cambio.                                                                   | F2             |
| **D2** | Fuente de verdad del esquema BD | **Alembic = única autoridad PostgreSQL**; SQLAlchemy = ORM; Prisma degradado a cliente/léxico read-only (o retirado progresivamente). ADR-025 reforzado.                                                                                                 | F3/K           |
| **D3** | Workers                         | **Extraer TODOS los workers/schedulers/crons** de `main.py` a proceso separado (`arq`/proceso dedicado).                                                                                                                                                 | F3             |
| **D4** | Auth                            | App **local/personal**. Auth (token sha256 + localStorage) **NO es prioridad ahora**; se documenta el riesgo y se difiere a eventual exposición pública.                                                                                                 | F5b (diferida) |
| **D5** | Alcance total                   | **Solo F1–F5.** Cero features. Se incluye (como criterio de hecho transversal) garantizar invariantes contables y ausencia de regresiones con la batería; no se abre suite de concurrency-testing como fase separada salvo que surja dentro de una fase. | todas          |

**Decisión de producto derivada (honesta):** F1 y F2 son el ~90% del valor comercial/científico real; F3–F5 son fortalecimiento. El éxito de la nota real del sistema depende sobre todo de **corregir el sesgo de ejecución (F2)** y la **integridad contable (F1)**, en ese orden de impacto sobre la calidad percibida.

---

## 6. Próximo hilo recomendado (tras este documento)

1. **Hilo de apertura: F1 — Integridad financiera** (rama `stage/f1-integridad-financiera-*` desde el checkpoint) con:
   - `with_for_update()` en `portfolio_repository` (trade/add/deduct/transfer) + locking determinista en transferencias.
   - Migrar `float`→`Decimal`/`NUMERIC` en el ledger (mantener float en analytics).
   - Idempotencia (`idempotency_key` UNIQUE) en trade/transfer/deposit/withdraw.
   - Tests de invariantes contables (cash ≥ 0, position ≥ 0, ledger = transacciones).
2. Cada paso: batería Py (ruff+mypy+pytest) + battery web si toca + `pnpm test` + CI GitHub. Commit+push por paso aprobado. Si falla → volver a `audit-checkpoint-2026-08-11`.

---

## 7. Registro

| Fecha      | Acción                                                                                                                                                  |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-11 | Auditoría interna completa (4 frentes). Verificación en código de C1–C5 y de los hallazgos críticos externos (P0.1 backtest, P0.4 workers, P0.6 ciclo). |
| 2026-08-11 | Recibidas auditorías externas 1, 2 y 3 (la 3 consolida la 1+2). Cruzadas contra la interna.                                                             |
| 2026-08-11 | Checkpoint git `audit-checkpoint-2026-08-11` creado y publicado.                                                                                        |
| 2026-08-11 | Este documento consolidado de auditoría + plan de hardening pactado.                                                                                    |
| 2026-08-11 | **Decisiones D0–D5 pactadas** (ver §5) y registro de orden de prioridad por riesgo de dinero/verdad.                                                    |

_(Enlace entre esta auditoría y el plan por módulos:_ [general-audit-plan-2026-08-10.md](./general-audit-plan-2026-08-10.md) _· Roadmap:_ [improvement-roadmap-post-audits-2026-08-02.md](./improvement-roadmap-post-audits-2026-08-02.md)_)_
