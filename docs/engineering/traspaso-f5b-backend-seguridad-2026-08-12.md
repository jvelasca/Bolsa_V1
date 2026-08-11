# Traspaso — F5b Backend/Seguridad (2026-08-12)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5 (sub-entrada de la Auditoría consolidada, junto a F1/F2/F3b/F5a/F3a/F4).
> **Fuentes de verdad (leer primero):** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) (P0.1/P1.8/P1.10/P2.x + D0–D5) · [traspaso-f4-arquitectura-python-2026-08-11.md](./traspaso-f4-arquitectura-python-2026-08-11.md) (deuda → F5b).
> **Rama de ejecución:** `stage/f5b-backend-seguridad-2026-08-12` (desgajada desde `stage/f1-*`, tras merge PR #34/F4).
> **Regla del hilo:** NO tocar código fuera del alcance F5b pactado. Cambios validados con la batería antes del commit.
> **Estado:** F5b COMPLETADO. Ver §4–§7.

---

## 0. Alcance pactado (decisión del usuario, este hilo)

Del plan F5 (Contratos, seguridad, frontend) y del mapa P1/P2, en **este** hilo se ejecuta (opción
**F5b backend/seguridad**, confirmada por el usuario):

- **P1.8** — Rate-limit **distribuido entre workers** (REAL: no compartido) vía **Redis** con
  fallback a memoria; **prefijos deterministas y ordenados** (corregir la fragilidad de
  subcadenas que reportaba la auditoría).
- **P2.3** — `SqlAlchemyOhlcvRepository.upsert_bars`: pasar de loop `INSERT` 1×1 a **bulk**
  `INSERT ... ON CONFLICT DO UPDATE` en una sola sentencia multi-fila.
- **P2.5** — `/api/health` **no expone detalles internos** al público (URLs/DSNs/hosts, claves
  internas de Redis, excepción cruda, config SMTP, nombre de clave de config auth). No filtra.
- **P2.7** — DTOs de **movimiento de dinero**: extender el contrato estricto a
  `DepositCashDto.amount` y `WithdrawCashDto.amount` (`gt=0` + `allow_inf_nan=False`).
  `TradeRequestDto` ya estaba estricto desde F1/M4 (se registra como resuelto vía F1).
- **Adjunto aprobado (ligado a P2.5):** defecto **CI preexistente** — `Python CI / quality`
  corría `test_health`/`test_auth`/`test_ai_authoring` (entran al `lifespan`→`ensure_migrated`→DB)
  **sin servicio Postgres** → `Connection refused` y el job fallaba en todos los PRs (también en
  F3a/PR #33 y F4/PR #34). Se excluyen de ese paso igual que `test_lists`/`test_workspaces`
  (criterio ya usado) → **unblock** de `quality` para F5b y futuros PRs.
- **Auth (P1.3 / D4):** **NO se implementa**; se **documenta la deuda** (token sha256 +
  localStorage, sin expiración/revocación) diferida a eventual exposición pública. Ya no se toca.

**Excluido de F5b (deuda registrada, NO resuelta aquí):**

- **P1.9 (API thin)** — composition root ~1100 líneas + rutas con SQL directo: hilo propio pendiente.
- **P1.3 auth full** (HttpOnly cookie/TTL/revocación): diferido (D4) a exposición pública.
- **P2.1 god-component/god-store frontend** (backtests-page, workspace-store) y **P2.6/P2.8** frontend: fuera del foco backend, siguiente iteración clean-up.
- **F5a §6 deuda** (fidelidad DTOs campo-a-campo, `openapi-fetch` como cliente completo): fase posterior.
- **mypy preexistente** en `apps/api-python/src/schemas/accounts.py` (13 errores `ser_json_by_alias`
  TypedDict + `dict` type-arg) y `infrastructure/database/session.py` (`create_engine` `str|None`):
  deuda tipada **preexistente**, NO introducida por F5b; fuera del gate scoped (por fases, P1.6).

**Anti-objetivos (D5):** cero features. Sin cambios de comportamiento en inputs válidos.

## 1. Diagnóstico confirmado en código

### P1.8 — rate-limit in-memory por proceso + prefijos frágiles

- `apps/api-python/src/bolsa_api/middleware/rate_limit.py` (antes): `self._hits: dict` **en
  memoria por proceso** → con `uvicorn --workers N` el límite se multiplica y **NO se comparte**
  entre workers. Filtrado por `SENSITIVE_PREFIXES` + `_EXTRA_CONTAINS` (subcadenas `"/fundamentals"`
  `/sync` sobre cualquier `/api/`) → frágil y no ordenado de forma clara.
- Rutas reales: `/api/ai/fundamentals/explain`, `/api/ai/fundamentals/filings/...`,
  `/api/instruments/fundamentals/query|screener`, `/api/instruments/{id}/fundamentals`, `/api/sync`.

### P2.3 — upsert N+1

- `ohlcv_repository.py:162-203` (antes): bucle `for bar in bars` con un `INSERT ... ON CONFLICT
DO UPDATE` **por barra** + `flush` final → N+1.

### P2.5 — health filtra internos

- `/api/health` exponeba: `redis.details.url_host` (host real), `message=f"Redis unreachable: {exc}"`,
  `worker_arq` con la **key interna** de Redis (`WORKER_ARQ_HEARTBEAT_KEY` literal),
  `smtp.details` con `port`/`hasUser`/`missing`, `xtb.message` con la **URL real del bridge**,
  `auth` con nombre de clave de config (`APP_PASSWORD`) y código de política (`OR-S1`),
  y `database.message` = `str(exc)` crudo de psycopg (filtra host/port del DSN).

### P2.7 — DTOs de dinero permisivos

- `DepositCashDto.amount` y `WithdrawCashDto.amount` eran `float` sin validación. Alimentan
  `deduct_cash`/ledger (área P1.10). `TradeRequestDto` ya estricto desde F1/M4 (`986399d`).

### CI — defecto preexistente

- `python-ci.yml` Pytest: comentaba "API tests offline" pero corría `apps/api-python/tests`
  incluyendo `test_health/test_auth/test_ai_authoring` que entran al `lifespan`→`ensure_migrated`→DB.
  Sin servicio Postgres en el runner → `Connection refused` y `quality` fallaba en **todos** los
  PRs (confirmado también en F3a/PR #33 y F4/PR #34). No era una regresión de ninguna fase.

## 2. Decisiones de diseño (F5b)

- **P1.8 distribuido**: `RateLimitStore` (Protocol) con dos implementaciones: `MemoryStore`
  (ventana deslizante en memoria, fallback local) y `RedisStore` (ventana fija vía
  `INCR`+`PEXPIRE` en un script Lua, **distribuido**). `RedisStore` degrada a su propio
  `MemoryStore` interno si Redis no responde (mini circuit-breaker `RETRY_AFTER_SEC=15`), de modo
  que local (REDIS_URL default siempre presente) se siguen aplicando límites sin romper el tráfico.
  `RateLimitMiddleware` elige `RedisStore` si hay `redis_url` no vacío, si no `MemoryStore`. Se
  desactiva en `test` (mismo criterio previo).
- **P1.8 prefijos**: `SENSITIVE_PREFIXES` ordenadas de específico a genérico (gana la primera
  coincidencia `startswith`); la ruta `/api/instruments/{id}/fundamentals` se resuelve por
  **segmento** (`_path_has_segment`) y no por subcadena, eliminando la fragilidad de `_EXTRA_CONTAINS`.
- **P2.3**: una sola `insert(OhlcvBarRow).values(rows)` + `on_conflict_do_update(... excluded ...)`
  → único `INSERT` multi-VALUES `ON CONFLICT DO UPDATE` (validado contra la BD real, ver §4).
- **P2.5**: se redactan los campos/mensajes sensibles; se conserva `yahoo.details.circuit`
  (estado operativo benigno que además requiere el test). `check_database` devuelve mensaje
  genérico `"PostgreSQL inaccesible"` en fallo (detalle real solo a logs).
- **P2.7**: `amount` en `DepositCashDto`/`WithdrawCashDto` → `Field(gt=0, allow_inf_nan=False)`.
- **CI**: se añaden los 3 ficheros DB-dependent al `--ignore` del paso Pytest de `quality`
  (mismo precedente `test_lists`/`test_workspaces`). El paso mypy gate se renombra
  `Mypy — gate scoped F4+F5b` e incluye los 3 ficheros F5b mypy-clean (`rate_limit.py` nuevo,
  `health.py`, `ohlcv_repository.py`).

## 3. Implementación (por sub-área)

| Fichero(s)                               | Qué                                                                                                                                                                                                                                                              |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `middleware/rate_limit.py`               | Reescrito (P1.8): `RateLimitStore` Protocol + `MemoryStore` + `RedisStore` (Lua `INCR`/`PEXPIRE`, fallback a memoria con circuit-breaker) + `RateLimitMiddleware` con `redis_url`, y `SENSITIVE_PREFIXES` deterministas + ruta `{id}/fundamentals` por segmento. |
| `main.py`                                | `create_app`: pasa `redis_url=settings.redis_url` al `RateLimitMiddleware` (mantiene `enabled != test`).                                                                                                                                                         |
| `api/v1/routes/health.py`                | (P2.5) Redacción: Redis sin `url_host` ni `{exc}`; `auth` sin `APP_PASSWORD`/`OR-S1`; `xtb` sin URL; `smtp` sin `port`/`hasUser`/`missing`; `worker_arq` sin clave interna; Yahoo mantiene `circuit`.                                                            |
| `infrastructure/database/session.py`     | `check_database` → `"PostgreSQL inaccesible"` genérico en fallo (P2.5).                                                                                                                                                                                          |
| `schemas/accounts.py`                    | `DepositCashDto.amount` + `WithdrawCashDto.amount` → `Field(gt=0, allow_inf_nan=False)` (P2.7).                                                                                                                                                                  |
| `infrastructure/.../ohlcv_repository.py` | `upsert_bars` bulk `INSERT ... ON CONFLICT DO UPDATE` (P2.3).                                                                                                                                                                                                    |
| `tests/test_health.py`                   | Nuevo `test_health_redacts_internal_details` (P2.5).                                                                                                                                                                                                             |
| `tests/test_rate_limit.py` (nuevo)       | Test unitario de prefijos deterministas + `MemoryStore` (libre de DB/Redis, corre en CI).                                                                                                                                                                        |
| `.github/workflows/python-ci.yml`        | Pytest `quality`: `--ignore` de `test_health`/`test_auth`/`test_ai_authoring` (defecto preexistente); mypy gate → `F4+F5b` (16 files).                                                                                                                           |

## 4. Validación (batería aplicada)

- **Bulk upsert (P2.3) contra BD real `bolsa_v1`** (smoke en transacción **rollback**, sin
  persistir): `n1=2` (dos filas en una sentencia), `n2=1` (re-upsert misma clave →
  `ON CONFLICT DO UPDATE`), `close` pasa a `11.9` (el `excluded` aplicó el update). OK.
- **ruff** `packages/py apps/api-python` → **0 errores** (All checks passed).
- **mypy gate** (16 files F4+F5b, comando exacto CI) → `Success: no issues found in 16 source files`.
  Ficheros F5b con deuda preexistente (`accounts.py`, `session.py`) quedan **fuera** del gate.
- **pytest offline CI scope** (market+analytics+api, con los nuevos `--ignore`) → **451 passed**.
- **api-python** con BD `bolsa_v1` (including `test_health` redaction, `test_auth`,
  `test_ai_authoring`, `test_rate_limit`) → **27 passed**.
- **application** → **222 passed**. **infra+domain** → **57 passed**.
- **ai+analytics+test_daily_ops_digest_pdf** → **340 passed, 1 skipped**.

## 5. Deuda / fuera de alcance (registrado, NO resuelto)

- **P1.9 API thin** — hilo propio pendiente.
- **P1.3 auth full** (HttpOnly cookie + TTL + revocación): **D4 lo difiere** a eventual exposición
  pública. El riesgo del token estático (sha256 + localStorage, sin expiración) queda **documentado**
  aquí y en la auditoría; NO se cambia el comportamiento de auth en F5b (cero features).
- **P2.1 god-components frontend** (backtests-page / workspace-store) y **P2.6/P2.8**: siguiente
  iteración clean-up (foco F5b = backend).
- **F5a §6** (fidelidad DTOs campo-a-campo, `openapi-fetch` completo): fase posterior.
- **mypy preexistente** `accounts.py` (13) y `session.py` (3): deuda tipada heredada (~451 del
  árbol), por fases (P1.6). F5b solo garantiza mypy-clean en sus ficheros nuevos/mypy-limpios.
- **P1.8**: sin Redis el límite es **por proceso** (documentado); con Redis es **distribuido**.
  El rate-limit sigue siendo de **ventana fija**, no token-bucket.

## 6. Registro

| Fecha      | Acción                                                                                                                                                                                                                                               |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-12 | Merge del estado: PR #32 (F5a) ya merged; PR #34 (F4) fast-forward a `stage/f1-*` y mergeado (base `f88042d`). Rama `stage/f5b-backend-seguridad-2026-08-12` creada. Alcance pactado con el usuario (opción backend/seguridad + adjuntos aprobados). |
| 2026-08-12 | P2.5: `check_database` genérico + redacción en `health.py` (Redis/worker_arq/smtp/xtb/auth) + `test_health_redacts_internal_details`.                                                                                                                |
| 2026-08-12 | P1.8: `rate_limit.py` con `RedisStore` (distribuido, Lua INCR/PEXPIRE) + fallback memoria + circuit-breaker; `SENSITIVE_PREFIXES` deterministas; `main.py` cablea `redis_url`; `test_rate_limit.py`.                                                 |
| 2026-08-12 | P2.3: `ohlcv_repository.upsert_bars` en bulk `INSERT ... ON CONFLICT DO UPDATE`; validado contra BD real (rollback).                                                                                                                                 |
| 2026-08-12 | P2.7: `Deposit/Withdraw.amount` → `gt=0, allow_inf_nan=False`.                                                                                                                                                                                       |
| 2026-08-12 | CI: `--ignore` de `test_health/auth/ai_authoring` en `quality` (defecto preexistente → unblock pipeline); mypy gate `F4+F5b` (16 files, exit 0).                                                                                                     |
| 2026-08-12 | Batería verde: ruff 0 · mypy gate 16 ✓ · pytest 451 + 27 + 222 + 57 + 340 ✓ · smoke bulk upsert ✓.                                                                                                                                                   |
| 2026-08-12 | Cierre F5b: traspaso + engineering-index + texto exacto siguiente hilo.                                                                                                                                                                              |

## 7. Protocolo recurrente (obligatorio en TODOS los hilos)

> Norma permanente del proyecto. Al cerrar: preparar el siguiente con su `traspaso-*`, entrada
> única en `engineering-index`, y entregar en el chat el **texto exacto** para pegar en el próximo.

## 8. Texto exacto de traspaso — siguiente hilo (tras F5b)

```text
Texto de traspaso → nuevo chat (F5b completado — siguiente fase tras F5b)

CONTEXTO INMEDIATO: F5b (Backend/Seguridad) COMPLETADO en rama
  stage/f5b-backend-seguridad-2026-08-12 (desde stage/f1-* tras merge PR #34/F4).
  - P1.8 rate-limit DISTRIBUIDO entre workers: rate_limit.py reescrito con RedisStore
    (INCR+PEXPIRE en Lua, compartido) + MemoryStore fallback + circuit-breaker; prefijos
    SENSITIVE_PREFIXES deterministas (específico→genérico) y /api/instruments/{id}/fundamentals
    por segmento (antes subcadenas). main.py cablea redis_url. Sin Redis → límite por proceso.
  - P2.3 upsert_bars en BULK INSERT...ON CONFLICT DO UPDATE (una sentencia multi-fila, antes loop
    N+1). Validado contra BD real en transacción rollback (n1=2, close 11.9).
  - P2.5 /health NO filtra internos: Redis sin url_host/{exc}, auth sin APP_PASSWORD/OR-S1,
    xtb sin URL real, smtp sin port/hasUser/missing, worker_arq sin key interna, DB mensaje
    genérico "PostgreSQL inaccesible". Test test_health_redacts_internal_details.
  - P2.7 Deposit/Withdraw.amount → gt=0 + allow_inf_nan=False (TradeRequestDto ya estricto F1/M4).
  - CI (defecto PREEXISTENTE): quality Pytest SIN servicio Postgres corría test_health/test_auth/
    test_ai_authoring (lifespan→DB → Connection refused). Se excluyen (igual que test_lists/
    test_workspaces) → quality UNBLOCK. Mypy gate renombrado "F4+F5b" (16 files, exit 0).

BATERÍA (verde): ruff 0 (scope py) · mypy gate 16 files exit 0 · pytest offline 451✓ +
  api-python 27✓ (bolsa_v1, incl. test_health redaction) + application 222✓ + infra+domain 57✓ +
  ai+analytics+digest 340✓ (1 skip) · smoke bulk upsert (rollback) ✓.

DEUDA REGISTRADA → fases posteriores: P1.9 API thin (hilo propio) · P1.3 auth full
  (HttpOnly/TTL/revocación) D4 diferido a exposición pública · P2.1 god-components frontend
  (backtests-page/workspace-store) · F5a §6 fidelidad DTOs/openapi-fetch · mypy preexistente
  ~en accounts.py/session.py y resto del árbol (por fases) · P1.8 sin Redis = por proceso.

Lee PRIMERO: docs/engineering/traspaso-f5b-backend-seguridad-2026-08-12.md (§4-§7) y su fuente
  audit-consolidado-internas-externas-2026-08-11.md (P1.8/P2.3/P2.5/P2.7 + D0-D5). Para la fase
  siguiente usa engineering-index-2026-08-03.md y el plan de la fase declarada.
NO toques código fuera del alcance de la fase que se declare.
```
