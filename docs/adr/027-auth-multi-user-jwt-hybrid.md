# ADR 027: Auth multi-user — Opción C híbrida (JWT + transición APP_PASSWORD)

## Estado

**Aceptado** — 2026-08-22  
(**F5–F10 + F8b–F8e en `main` (`01ee1ae`). Defer: `scan.completed` worker async. Fallback APP_PASSWORD intacto.**)

**Decisión del propietario (2026-08-22):** **Opción C (híbrido)** — fases incrementales C.1 → C.2 → C.3 documentadas en [`plan-r12-auth-d4-jwt-multiuser-2026-08-22.md`](../engineering/plan-r12-auth-d4-jwt-multiuser-2026-08-22.md) §3.

## Contexto

R12-AUTH F1–F3 entregaron **aislamiento mecánico single-tenant** sin identidad real:

- Tras auth OK (o auth-off): `request.state.principal = Settings.owner_principal()` (default `"app"`, env `APP_OWNER_ID`).
- No hay tabla `users` ni `request.user`.
- Token actual: SHA-256 determinista de password global (`auth/tokens.py`) — **no es JWT**, no lleva `sub`/`exp` en el payload.
- Cookie HttpOnly R-8B.2 (`auth/session.py`, `routes/auth.py`) con valor `exp.token.sig` (HMAC-SHA256); Bearer como fallback API (`middleware/auth.py`).
- Cuentas: `InvestmentAccountRow.user_id` nullable; legacy `user_id is None` visible para todos los principals (`principal.py:36-38`).

El freeze **D4** (auth JWT / multi-user) quedó diferido hasta decisión del propietario (`plan-refactor-refuerzo-post-v1-3-0-2026-08-21.md` §4). R12-AUTH F1–F3 prepararon la tubería `principal → owner_user_id → account_repository`; D4 sustituye **de dónde sale** el principal, no reescribe `ExecuteTrade`.

**Opciones evaluadas** (plan D4 §3):

| Opción | Resumen                                                                |
| ------ | ---------------------------------------------------------------------- |
| **A**  | Mantener `APP_PASSWORD` + principal fijo `"app"` — no abrir multi-user |
| **B**  | Multi-user JWT completo desde F5 (tabla `users`, varios operadores)    |
| **C**  | Híbrido incremental: bootstrap instancia → JWT admin → multi-user real |

El propietario eligió **Opción C** el 2026-08-22.

## Decisión

Implementar auth multi-user mediante **Opción C (híbrido)** en tres sub-fases:

| Fase    | Alcance                                                                                                 | Principal                                    |
| ------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| **C.1** | Introducir tabla `users`; mantener `APP_PASSWORD` como «modo instancia» con user bootstrap `app` en BD  | Constante `"app"` o user bootstrap hasta C.2 |
| **C.2** | Login emite **JWT**; middleware resuelve `request.state.principal = claims["sub"]` para user admin seed | Identidad autenticada (single admin)         |
| **C.3** | Admin UI/API crea users adicionales; cierre política legacy `user_id is None` (anexo)                   | Multi-tenant estricto                        |

### Formato JWT

Tokens firmados (HS256 inicialmente; rotación documentada en F10). Claims mínimos:

| Claim  | Obligatorio | Semántica                                                       |
| ------ | ----------- | --------------------------------------------------------------- |
| `sub`  | Sí          | ID del user (`users.id`) — fuente de `request.state.principal`  |
| `exp`  | Sí          | Expiración UTC (epoch seconds)                                  |
| `iat`  | Sí          | Emisión UTC                                                     |
| `sv`   | Sí (F10)    | `session_version` del user — revocación logout-all              |
| `role` | No          | Rol opcional (`admin` \| `operator`); `require_role` helper F10 |

**No incluir** en el JWT: password, email en claro, datos de cuenta. TTL alineado con `APP_AUTH_TTL_SECONDS` (default 86400) salvo decisión F10.

**Clave de firma:** preferir `JWT_SIGNING_KEY` dedicada; reutilizar `APP_AUTH_SECRET` solo en transición C.1–C.2 con ventana de deprecación documentada en F10.

### Transporte de sesión (compatibilidad R-8B.2)

| Canal                                    | Comportamiento                                                                                                                                                                                                 |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cookie HttpOnly**                      | Primario FE (`auth-store.ts`, `credentials: "include"`). Misma política R-8B.2: `Secure`, `SameSite`, path `/`, TTL = `exp` del JWT. Valor = JWT (sustituye token SHA-256 determinista tras ventana acordada). |
| **Header `Authorization: Bearer <JWT>`** | Fallback API / scripts / integraciones — **mantener** durante toda la transición y post-C.3 para clientes no-browser.                                                                                          |

Middleware: JWT válido → `principal = sub`; rutas públicas sin cambio (health, login/logout/status, docs).

### Fallback `APP_PASSWORD` (solo C.1 / transición C.2)

Durante **C.1** y ventana acordada en **C.2**:

- Si JWT ausente o inválido **y** `APP_PASSWORD` configurada → gate legacy actual (token SHA-256 determinista + cookie HMAC existente).
- Principal legacy: user bootstrap `app` (o `APP_OWNER_ID`) — **no** identidad multi-user.
- **Deprecación:** retirar fallback en **F10** (endurecimiento) salvo OK explícito del propietario para prolongar.

**Prohibido:** fallback legacy en `ENVIRONMENT=production` cuando auth está desactivada (fail-closed ya vigente en `config.py:190-203`).

### Fail-closed production

| Condición                                                                        | Comportamiento                                            |
| -------------------------------------------------------------------------------- | --------------------------------------------------------- |
| `ENVIRONMENT=production` + auth desactivada (sin password ni users)              | **Rechazar arranque** o equivalente fail-closed existente |
| `ENVIRONMENT=production` + JWT inválido/expirado + sin fallback legacy permitido | **401** en rutas protegidas                               |
| Token legacy SHA-256 tras ventana de deprecación                                 | **401** (no silent downgrade a auth-off)                  |

Sin registro público en ninguna sub-fase C.1–C.3; bootstrap admin vía migración/env **una sola vez** (F5).

### Deprecación token SHA-256 determinista

`auth/tokens.py` (hash `bolsa:{password}:{secret}`) se retira tras ventana acordada post-F5 (target F10). ADR-027 no autoriza borrado en F5.

## Anexo: Política legacy `user_id is NULL`

Legacy: cuentas con `user_id is None` son visibles para **cualquier** principal (`account_visible_to_principal`). Deuda consciente single-tenant; **bloqueante** para multi-user estricto.

**Política por defecto (F7 — requiere OK propietario en fase F7):**

| ID                           | Política                                                       | Descripción                                                                                                                                                   |
| ---------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F7a — Soft (default ADR)** | Visibilidad legacy solo para principal bootstrap `app` / admin | Otros users JWT **no** ven filas `user_id IS NULL`                                                                                                            |
| **F7b — Backfill one-shot**  | Script migración offline                                       | `UPDATE investment_accounts SET user_id = :bootstrap WHERE user_id IS NULL` en ventana de mantenimiento; **prohibido** en hot path API / `database_bootstrap` |
| **F7c — Hard close**         | Match estricto                                                 | `account_visible_to_principal` exige `user_id == principal` (requiere F7b previo o acepta romper huérfanos)                                                   |

**Orden recomendado:** F5 (JWT `sub`) → F6 (list/get scoped) → F7b staging → F7c opcional.

**Jobs:** `list_active_accounts` filtrado por owner en **F8** (`5e7c67b`). Custodia multi-tenant: filtrar por owner — **hecho F8**. Trackers/policies scoped en **F8b** (`2cd20b0`).

**Ventana de convivencia C.1–C.3:** legacy NULL permanece bajo F7a hasta F7; no backfill automático en F5–F6.

## NO-touch (todas las fases F5+)

**NO tocar** salvo fase explícita y OK del propietario:

| Área                                                                                                                             | Motivo                                                   |
| -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `packages/py/application/**` paths de dinero (`ExecuteTrade`, `DepositCashToAccount`, `WithdrawCashFromAccount`, custodia apply) | R12-AUTH F3: guards solo en rutas; motor intacto         |
| `openapi.json` / `contract:gen`                                                                                                  | Salvo fase con regen acotada (login/register/me/refresh) |
| `pending-delete/**` purge storage                                                                                                | Riesgo alto; E8                                          |
| Gobernanza IA / `ai_governance` routes                                                                                           | Freeze R-12                                              |
| `PAPER_D_EXECUTE`                                                                                                                | Freeze                                                   |
| FE auth (`apps/web/**` auth)                                                                                                     | Implementación solo fase **F9** pactada                  |

## Criterios de aceptación (propietario — gate F5+)

### Gate ADR-027 (F4 → F5)

- [ ] Propietario marca ADR-027 **Aceptado** (este documento).
- [ ] Opción C confirmada; sub-fases C.1–C.3 entendidas.
- [ ] Política legacy F7a/F7b/F7c elegida o diferida explícitamente a F7.
- [ ] NO-touch list aceptada.

### F5 — Identidad mínima (C.2)

- [ ] Migración Alembic `users` (id, login unique, password_hash argon2/bcrypt, role, created_at, disabled_at).
- [ ] Seed bootstrap: user `app` o admin desde env **una sola vez** (sin registro público).
- [ ] `POST /api/auth/login` valida contra `users`; emite JWT con claims `sub`, `exp`, `iat` (+ `role` opcional).
- [ ] Cookie HttpOnly con JWT **y** Bearer JWT aceptados en middleware.
- [ ] JWT válido → `request.state.principal = claims["sub"]`.
- [ ] Fallback `APP_PASSWORD` legacy operativo solo si ADR-027 lo permite (ventana C.2).
- [ ] `pytest apps/api-python/tests/test_auth.py` ampliado (JWT + fallback).
- [ ] `pytest apps/api-python/tests/test_account_isolation.py` con principal distinto de `"app"` vía JWT mockeado.
- [ ] ruff/mypy zona `bolsa_api/auth/**` verde.
- [ ] **Sin** multi-registro, refresh rotation, FE, backfill masivo legacy.

### F6 — Scoping list/get accounts

- [ ] `ListAccounts` / summaries pasan `owner_user_id=get_request_principal(request)`.
- [ ] `GetAccount` y mutaciones sin guard previo exigen owner en repo o Depends.
- [ ] Tests: user A no ve cuentas de user B en `GET /accounts`.
- [ ] **Sin** tocar money paths ni jobs.

### F7 — Política legacy `user_id is NULL`

- [ ] Política F7a, F7b o F7c aplicada según decisión de fase.
- [ ] Tests legacy + post-backfill en staging si F7b.
- [ ] **Prohibido** backfill automático en `database_bootstrap`.

## Alternativas consideradas y por qué se descartan

| Alternativa                             | Por qué se descarta                                                                                               |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Opción A — permanecer single-tenant** | Rechazada por el propietario 2026-08-22; no cumple auditoría «auth global multiusuario».                          |
| **Opción B — JWT multi-user día 1**     | Mayor riesgo de regresión y rollback; Opción C permite validar JWT con un solo admin antes de abrir multi-tenant. |
| **JWT solo Bearer (retirar cookie)**    | Rompe R-8B.2 y FE actual; cookie HttpOnly + Bearer es el contrato acordado.                                       |
| **Registro público**                    | Fuera de alcance; admin crea users (ADR-004).                                                                     |
| **Backfill legacy en F5/F6**            | Side-effect sorpresa en prod; relegado a F7 script offline.                                                       |

## Consecuencias

### Positivas

- Rollback fácil en C.1 (modo instancia intacto).
- Compatibilidad despliegues actuales (`APP_PASSWORD` + cookie R-8B.2).
- JWT con identidad real desbloquea F6–F10 sin reescribir guards F1–F3.
- Alineación ADR-004/008 multi-usuario.

### Negativas / coste

- Dos modos de auth coexisten temporalmente (legacy SHA-256 + JWT).
- Complejidad middleware (orden JWT → fallback legacy).
- Migración + tests ampliados; regen contrato acotada en fases posteriores.
- F8+ necesario para recursos colaterales (`investor_profiles`, trackers, jobs custodia).

### Riesgos mitigados

- Money motor intacto (NO-touch).
- Fail-closed production preservado.
- Legacy NULL acotado por anexo F7 antes de multi-user real (C.3).
- Clave JWT dedicada + rotación en F10 reduce reuse de `APP_AUTH_SECRET`.

## Referencias

- Plan D4: [`plan-r12-auth-d4-jwt-multiuser-2026-08-22.md`](../engineering/plan-r12-auth-d4-jwt-multiuser-2026-08-22.md)
- R12-AUTH F1–F3: [`plan-r12-auth-fase1-2026-08-22.md`](../engineering/plan-r12-auth-fase1-2026-08-22.md)
- R-8B.2 cookie HttpOnly: [`plan-r8-prevencion-riesgo-2026-08-20.md`](../engineering/plan-r8-prevencion-riesgo-2026-08-20.md)
- ADR-004 §0 auth UI · ADR-008 §8 multi-usuario
- Deuda V2 auth: [`plan-refactor-refuerzo-post-v1-3-0-2026-08-21.md`](../engineering/plan-refactor-refuerzo-post-v1-3-0-2026-08-21.md) §4

## Historial

| Fecha      | Evento                                                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| 2026-08-22 | ADR creado (Propuesto) en R12-AUTH F4; propietario elige **Opción C (híbrido)**.                                                                 |
| 2026-08-22 | **Aceptado**; F5–F9 en `main` (`5e7c67b`). **F8b** `2cd20b0` · **F10** `837ec85`: trackers/policies scoped · session_version/refresh/rate-limit. |
