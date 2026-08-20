# Plan R-8 — Prevención de riesgo + corrección de errores + mejoras (2026-08-20)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Fase:** R-8 — nueva ola de hardening tras el **cierre completo de R-7** (deuda de dinero real cerrada; solo `M-4/T-M4` diferido por freeze). Motiva este plan la **auditoría externa de 2026-08-20** (3ª ronda) cruzada contra el código real de `main`, detectando que **su P0 de arranque ya está corregido** y dejando **2 P0 reales** sin cubrir.
> **Estado:** ⏳ **R-8A IMPLEMENTADA + verificada (ruff/mypy/pytest verdes), pendiente aprobación y commit final.** Fase 0 (docs) y R-8A (P0 hardening) ejecutadas. R-8B/C/D pendientes de decisión por fase.
> **Decisión de usuario 2026-08-20:** (1) levantar freeze `D4` (auth) **solo** para la fase R-8B.2 acotada · (2) incluir **ambos P0** como R-8A prioritario · (3) arrancar en **modo docs_solo** (Fase 0 = solo documentos) · (4) R-8A: `database_bootstrap()` con `pg_advisory_lock` de sesión global (P0-A) y catch `IntegrityError`+savepoint+re-SELECT (P0-B).

---

## 1. Por qué existe este plan (hechos, no opiniones)

### 1.1 La auditoría externa NO está leyendo `main` real (causa raíz ya conocida)

La auditoría de hoy declara un **P0.1 de arranque** ("`RateLimitMiddleware.__init__` no acepta `redis_url`/`trusted_proxies` → TypeError al crear la app"). **Verificado en `main` actual (`4120029`): es FALSO.**

```137:144:apps/api-python/src/bolsa_api/middleware/rate_limit.py
    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool = True,
        redis_url: str | None = None,
        trusted_proxies: str = "",
    ) -> None:
```

- `main.py:151-156` pasa `redis_url` y `trusted_proxies` correctamente.
- `test_rate_limit.py:16` instancia el middleware con `redis_url=""` — el constructor lo acepta.
- Los commits `16a0477` (rate-limit distribuido) y `e628ae3` (F-SEG-3, 2026-08-19) ya aportaron esos parámetros.

**Anti-patrón a evitar:** recrear trabajo ya hecho o asumir hallazgos caducos. Esto ya está documentado como causa de la "no-visibilidad" en `PROJECT_STATE.md §4` (el auditor contrasta un estado previo al sincronizado). **Este plan asume que TODO hallazgo externo se contrasta contra código antes de abrir una fase.**

### 1.2 Los 2 P0 reales en `main` (sí vigentes)

| Código                           | Superficie  | Hallazgo verificado                                                                                                                                                                                                                                                                                                | Evidencia                                                                         |
| -------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| **P0-A / bootstrap**             | infra       | `ensure_migrated` (Alembic) y `run_account_data_migration` se ejecutan en `lifespan` de FastAPI **y** en `scheduler_worker`; con `uvicorn --workers N` se repiten por worker. **No hay `pg_advisory_lock` en todo el repo** (grep exhaustivo). `_ensure_default_account` tiene el patrón SELECT→INSERT en carrera. | `main.py:46,54` · `scheduler_worker.py:75` · `account_migration.py:60,80-103,304` |
| **P0-B / idempotencia concurr.** | application | `UNIQUE(portfolio_id, idempotency_key)` y guard `find_transaction_by_idempotency` existen, pero hay una ventana SELECT→INSERT: dos requests con la misma key pasan ambos y el 2º recibe excepción en vez de "ya ejecutado". **Sin catch de `IntegrityError` → re-SELECT.**                                         | `accounts.py:574-600` (trade) · `accounts.py:280-317` (deposit/withdraw)          |

### 1.3 Freeze vigente vs hallazgos externos

El freeze dice _"auth JWT diferida (D4)"_. La auditoría externa pide exactamente eso (punto 10/P1.2). **Por decisión del usuario (2026-08-20), D4 se levanta SOLO para la fase acotada R-8B.2.**

---

## 2. Premisas ESENCIALES ratificadas (se materializan en `docs/PROJECT_PREMISES.md` en Fase 0-ejecutable)

> Estas premisas **ya existen dispersas** en `backlog`/`PROJECT_STATE`/`engineering-index`. R-8 las **ratifica como premisa de proyecto única** (sin duplicar ni crear raíces paralelas, per `engineering-index` anti-patrón).

1. **Read-first obligatorio.** Todo subagente o chat nuevo lee `backlog-trabajo-2026-08-20.md` §0 y §1 **antes** de tocar nada. Si no coincide con el repo → PARAR y re-leer (anti-alucinación, ya norma).
2. **Una fase = un subagente acotado.** Brief explícito con: contexto, archivos exactos, alcance (qué NO tocar), batería esperada, y orden de **escribir el resultado en el backlog/traspaso** al terminar.
3. **El subagente no auto-aprueba.** El coordinador revisa diff + batería antes de proponer commit al usuario.
4. **Aprobación del usuario por commit.** No se auto-commitea jamás.
5. **Batería mínima por fase (py):** `ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de ficheros en gate CI · pytest de la zona · `git status` acotado. **(web):** `pnpm --filter @bolsa/web typecheck` + `lint` + `build` (+ `test` si toca FE). Global: `pnpm test` + CI + `contract:check` si se toca contrato.
6. **Trigger de relevo por saturación.** Si el contexto del chat se llena, cerrar hilo y abrir otro pegando el texto de relevo del traspaso + backlog. Máx. ~3 subagentes en paralelo por chat.
7. **Verificación adversarial anti-alucinación.** Si un subagente afirma un hallazgo (file:line, commit, test, resultado), el coordinador lo contrasta con **código/datos reales** antes de aceptarlo. Sin evidencia reproducible → rechazo.
8. **Firma de estado en cada relevo.** Todo text de traspaso incluye bloque "estado verificado" (HEAD, rama, árbol, CI) para que el siguiente chat arranque sin adivinar.
9. **Criterio de borrado de código/doc obsoleto** (fase R-8D): cero imports en `apps/`+`packages/` (excl. tests que solo validan el alias) + sin lectura de storage dependiente del nombre + battery/typecheck verdes tras quitar (patrón `pending-delete/README.md`).
10. **Documentar en la capa correcta** (ya premisa §1 `PROJECT_PREMISES.md`): docstrings en símbolos públicos tocados + docs/ADR si cambia comportamiento/contrato/política.

---

## 3. Fases propuestas (una fase = subagente + batería + aprobación + relevo)

### 📋 Fase 0 — Docs (cero riesgo, es ESTE plan)

| #   | Acción                                                                                              | Riesgo      | Batería    |
| --- | --------------------------------------------------------------------------------------------------- | ----------- | ---------- |
| 0.1 | Ratificar las premisas §2 en `docs/PROJECT_PREMISES.md` (append a §1, no duplicar)                  | nulo (docs) | —          |
| 0.2 | Registrar este plan en `engineering-index.md` §1 (entrada con 1 padre)                              | nulo        | —          |
| 0.3 | Corregir `README.md` §Roadmap/Deuda: quitar `transfer_cash` (ya eliminado `7cffaa7`)                | nulo        | —          |
| 0.4 | `pending-delete/` + docs `CHART_*` obsoletos → aplicar criterio donde aplique (sin borrar a ciegas) | bajo (docs) | revisiones |

### 🔴 Fase R-8A — P0 hardening (prioridad máxima, no requiere nuevo freeze)

| Código     | Superficie  | Alcance                                                                                                                                                                                                    |
| ---------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R-8A.1** | infra       | `database_bootstrap()` con `pg_advisory_lock`: serializa `alembic upgrade head` + `run_account_data_migration`, usado desde FastAPI (`lifespan`), scheduler_worker y CLI. Un único ancla.                  |
| **R-8A.2** | application | Catch `IntegrityError` → rollback/rollback-to-savepoint → re-SELECT por `idempotency_key` → devolver el movimiento/transacción existente. Aplicar a `execute_trade`, `deposit`, `withdraw` (mismo patrón). |

### 🟠 Fase R-8B — P1 hardening

| Código     | Superficie | Alcance                                                                                                                                                                                       | Depende de          |
| ---------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| **R-8B.1** | api        | Añadir `/api/auth/login` y `/api/auth/status` a `SENSITIVE_PREFIXES` (login rate-limit). No es feature nueva.                                                                                 | —                   |
| **R-8B.2** | api+web    | Migrar auth: token SHA-256 determinista + localStorage → **sesión HttpOnly + Secure + SameSite + TTL** (server-side o cookie firmada). **Requiere freeze D4 levantado por decisión usuario.** | decisión D4 (hecho) |
| **R-8B.3** | shared     | Reducir DTOs duplicados `packages/shared` vs OpenAPI (continuación R-2/R-3/R-4). Fases pequeñas, NO `regen_full`.                                                                             | —                   |

### 🟡 Fase R-8C — Mejoras consolidadoras

| Código     | Superficie | Alcance                                                                                                                                                                              |
| ---------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **R-8C.1** | infra      | Ampliar invariantes a nivel DB: `balance_after[n] = balance_after[n-1] + amount[n]` por cuenta (complementa los tests ya existentes).                                                |
| **R-8C.2** | workers    | Separación scheduler vs worker: en modo no-ARQ el `scheduler_worker` ejecuta loops inline. **Documentar como deuda con trade-off** (no tocar salvo decisión), como R-6 hizo con F-3. |

### 🧹 Fase R-8D — Limpieza transversal

Revisar `pending-delete/` (§1.3.9 criterio), docs obsoletos (`CHART_*`, `transfer_cash`), `logs/dev` (acciones manuales fuera de repo). Con batería completa.

---

### ✅ Cierre R-8A — P0 hardening (2026-08-20, implementado y verificado)

| Código          | Superficie               | Qué se implementó                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| --------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R-8A.1 P0-A** | infra                    | `database_bootstrap(engine, session_factory)` en `migrations.py`: toma `pg_advisory_lock` (key global `774_104_253`) sobre conexión async, corre `ensure_migrated` (Alembic, via thread) + `run_account_data_migration`, y libera en `finally`. Usado desde `main.py:lifespan` y `scheduler_worker.py._run_scheduler`. **Serializa el bootstrap entre N workers FastAPI + scheduler.**                                                                                                                                                               |
| **R-8A.2 P0-B** | domain+infra+application | Excepción de dominio `IdempotencyKeyExists` (`bolsa_domain/errors.py`) + helper `is_unique_violation` (SQLSTATE 23505) (`db_errors.py`). `execute_trade` y `append_cash_movement` envuelven su write-path en `begin_nested()` (savepoint) y relanzan `IdempotencyKeyExists` **solo** ante violación de unicidad (no FK/check). Los use-cases `ExecuteTrade`, `DepositCashToAccount`, `WithdrawCashFromAccount` capturan y re-SELECT + devuelven el existente. Deposit/withdraw usan `_idempotent_savepoint` sobre `add_cash`/`deduct_cash`+`append`. |

**Design decisions (aprobadas por el usuario 2026-08-20):**

- P0-A: advisory lock de **sesión global** sobre el bloque completo (cover de Alembic + migración de datos).
- P0-B: catch **en el repositorio** (donde ocurre el `flush` y está la sesión); trade 100% autocontenido en el repo; deposit/withdraw con `session` property + savepoint en los use-cases (no-op en fakes de test).

**Verificación (batería R-8A):** ruff check+format 0 en ficheros · mypy `domain+infra+api` Success (exit 0) · pytest `application` 249 passed · pytest `infrastructure` 78 passed + 1 xfail · pytest `api-python` 56 passed · **Nuevos tests:** `infrastructure/tests/test_r8a_idempotency_backstop.py` (repo relanza `IdempotencyKeyExists` ante colisión real).

**Hallazgos del mapeo read-only (contrastados):** confirmó ambos P0; el P0.1 de auditoría externa (`RateLimitMiddleware`) era FALSO en `main` (ya corregido).

---

## 4. Regla de ejecución de cada fase (protocolo R-8)

1. **Mapeo read-only** (subagente, sin tocar código): hallazgo file:line verificado + consumidores + si el fix rompe comportamiento esperado.
2. **Decisión de usuario:** alcance y si el cambio de valor esperado es aceptable.
3. **Subagente de implementación acotado** + **verificación coordinador** (diff + test + batería real) + **aprobación + commit + push** (rama `main` protegida; el push requiere tu aprobación) + **relevo documentado** (actualizar backlog §0/§6 y traspaso).
4. Escribir evidencia en `backlog-trabajo-2026-08-20.md` (update-last) y `PROJECT_STATE.md` (registro).

---

## 5. Estado al abrir (firma)

- `local main = origin/main = 4120029` · árbol limpio · working tree sin cambios.
- Freeze: sin features nuevas; **`D4` (auth) levantado solo para R-8B.2** por decisión usuario 2026-08-20.
- R-7 completo (todos sus items cerrados; `M-4/T-M4` diferido).
- Batería base confirmada en el último cierre: ruff 0 (config CI raíz) · mypy infra/domain Success · pytest infra Postgres real 76+1xfail · domain 21 · application 245 · api-python 32 · CI verde.

---

## 6. Historial de cierres (se rellenará por fase)

| Fecha      | Fase / Código      | Commit(s)                                | Batería                                                                      | Estado                       |
| ---------- | ------------------ | ---------------------------------------- | ---------------------------------------------------------------------------- | ---------------------------- |
| 2026-08-20 | R-8 Fase 0         | — (docs)                                 | docs                                                                         | ⏳ Fase 0 (este doc)         |
| 2026-08-20 | R-8A (P0-A + P0-B) | pendiente de commit (aprobación usuario) | ruff 0 · mypy Success · app 249 · infra 78+1xfail · api 56 · +tests backstop | ✅ IMPLEMENTADA + verificada |

---

## 7. Enlaces

- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md`
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Índice: `docs/engineering/engineering-index-2026-08-03.md`
- Auditoría externa motivo: tercera ronda 2026-08-20 (conversación) — P0 reales: bootstrap concurr., idempotencia concurr.
- Premisas: `docs/PROJECT_PREMISES.md`
