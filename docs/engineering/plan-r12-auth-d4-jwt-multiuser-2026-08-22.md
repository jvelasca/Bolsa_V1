# PLAN R-12 — Auth D4: JWT / multi-user (post F1+F2+F3)

> **Padre:** [`plan-r12-auditoria-ux-2026-08-21.md`](./plan-r12-auditoria-ux-2026-08-21.md) §2 gate R12-AUTH · [`plan-r12-auth-fase1-2026-08-22.md`](./plan-r12-auth-fase1-2026-08-22.md) (F1–F3 cerradas).
> **Contexto freeze:** [`plan-refactor-refuerzo-post-v1-3-0-2026-08-21.md`](./plan-refactor-refuerzo-post-v1-3-0-2026-08-21.md) §4 «Auth global → multiusuario real» · [`plan-r8-prevencion-riesgo-2026-08-20.md`](./plan-r8-prevencion-riesgo-2026-08-20.md) R-8B.2 (cookie HttpOnly, **no JWT**).
> **Premisas:** `docs/PROJECT_PREMISES.md` ⭐§0 · 0 commits sin OK del propietario.
> **AsOf:** 2026-08-22 · R12-AUTH F1 `e52e016` · F2 `9f3354f` · F3 `5fe5ace` · **F5–F9** `5e7c67b`.
> **Decisión propietario (2026-08-22):** **Opción C (híbrido)** · ADR-027 **Aceptado** · **F4–F10 cerradas** en `main` (`2cd20b0` · `837ec85`).

---

## 0. Propósito

Documentar la **decisión y la hoja de ruta** para levantar el freeze **D4** (auth JWT / multi-user), **después** del aislamiento mecánico single-tenant ya entregado en R12-AUTH F1–F3. Este plan **no autoriza implementación** hasta OK explícito del propietario (E1/E7).

---

## 1. Estado actual (verificado en código)

### 1.1 Gate de acceso — `APP_PASSWORD` (global, un solo operador)

| Pieza                    | Evidencia                                                                     | Comportamiento                                                                                                           |
| ------------------------ | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Password única           | `config.py:35-41` (`APP_PASSWORD`, `APP_AUTH_SECRET`, `APP_AUTH_TTL_SECONDS`) | Si vacía → auth desactivada (salvo `ENVIRONMENT=production` → fail-closed, `config.py:190-203`).                         |
| Token determinista       | `auth/tokens.py:7-19`                                                         | SHA-256 de `bolsa:{password}:{secret}` — **no es JWT**, no lleva `sub`/`exp` en el token en sí.                          |
| Cookie HttpOnly (R-8B.2) | `auth/session.py:32-70` · `routes/auth.py:46-73`                              | Valor `exp.token.sig` (HMAC-SHA256); TTL `APP_AUTH_TTL_SECONDS` (default 86400).                                         |
| Middleware               | `middleware/auth.py:25-56`                                                    | Públicos: health, login/logout/status, docs. Resto: Bearer **o** cookie válida → 401.                                    |
| Login / status           | `routes/auth.py:46-106`                                                       | Login compara password con `secrets.compare_digest`; body solo `authEnabled` (sin token). Status expone `authenticated`. |

**Nota doc obsoleta:** ADR-004 §0 aún describe token en `sessionStorage` + Bearer; el FE migró a cookie HttpOnly en R-8B.2 (`auth-store.ts`, `auth-gate.tsx`). Bearer sigue como fallback API (`middleware/auth.py:47-49`).

### 1.2 Principal single-tenant — `principal="app"` (R12-AUTH F1)

| Pieza                                      | Evidencia                                                    | Comportamiento                                                                                                                                                                                                                                |
| ------------------------------------------ | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Resolución                                 | `auth/principal.py:23-33` · `middleware/auth.py:36`          | Tras auth OK (o auth-off): `request.state.principal = Settings.owner_principal()` (default `"app"`, env `APP_OWNER_ID`, `config.py:214-220`).                                                                                                 |
| **No hay** `request.user` ni tabla `users` | búsqueda repo: 0 modelos `UserRow`                           | El «usuario» del dominio es un **string constante**, no identidad autenticada.                                                                                                                                                                |
| Visibilidad cuenta                         | `principal.py:36-38` · `account_repository.py:40-44,183-195` | Cuenta visible si `user_id is None` (legacy) **o** `user_id == principal`. Ajeno → `ValueError` → 404 vía `require_account_access`.                                                                                                           |
| Stamp en altas                             | `account_repository.py:229` · seed `account_migration.py:89` | Nuevas cuentas: `user_id=_app_owner_id()`.                                                                                                                                                                                                    |
| Guards HTTP                                | `dependencies.py:334-361` · rutas F1–F3                      | `require_account_access` (path) y `require_account_header_access` (`X-Account-Id`) en cuentas, CORE-R, mandatos, F3 queue, perfil activo, cartera GET, pending orders, **deposit/withdraw/trade** (`plan-r12-auth-fase1-2026-08-22.md` §5–6). |

### 1.3 Modelo de datos preparado pero incompleto

ADR-008 (`docs/adr/008-investment-accounts-and-ledger.md:22`): `userId` nullable en cuentas hasta auth completo — **implementado** en `InvestmentAccountRow.user_id` (`tables.py:1099`).

Otras columnas `user_id` nullable **sin scoping HTTP uniforme**:

| Tabla / entidad       | `tables.py` | Gap D4                                                                                                                               |
| --------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `investor_profiles`   | ~1072       | `list_profiles(user_id=…)` existe (`investor_profile_repository.py:48-51`) pero rutas globales no filtran por principal del request. |
| `execution_policies`  | ~492        | Sin guard de owner en API.                                                                                                           |
| `tracker_definitions` | ~729        | Idem.                                                                                                                                |
| `platform_events`     | ~553        | Append-only telemetría; sin aislamiento.                                                                                             |
| Workspaces / listas   | —           | Sin columna `user_id` detectada en modelos workspace.                                                                                |

### 1.4 Jobs / paths internos sin filtro owner

| Hallazgo                                              | Evidencia                       | Riesgo multi-user                                                                                                               |
| ----------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `list_active_accounts` sin `_owner_visibility_clause` | `account_repository.py:168-181` | Job custodia (`RunCustodyJob`) opera **todas** las cuentas activas, no solo las del principal.                                  |
| `ListAccounts` / `GetAccount` use-cases               | `accounts/crud.py:15-16,71-72`  | No reciben `owner_user_id`; dependen del default `_app_owner_id()` del repo o de guards HTTP previos.                           |
| `GET /accounts` list                                  | `routes/accounts.py:61-66`      | Filtra por owner vía repo default — OK single-tenant; en multi-user debe pasar `get_request_principal(request)` explícitamente. |

### 1.5 Frontend (solo referencia — **NO tocar en fases D4 salvo fase FE pactada**)

- `auth-store.ts` + `auth-gate.tsx`: bootstrap vía `/api/auth/status` + cookie `credentials:"include"`.
- Sin pantalla registro ni selector de usuario.
- ADR-004 prevé multi-usuario futuro con admin que crea usuarios.

---

## 2. Qué resolvió R12-AUTH F1–F3 (base para D4)

F1–F3 entregaron **aislamiento mecánico** sin identidad real:

1. Stamp `user_id` en cuentas nuevas con el owner single-tenant.
2. 404 en rutas `{account_id}` y en cash/trade cuando `user_id` ≠ principal.
3. Legacy `user_id is None` **sigue visible** (política explícita: no backfill masivo en F1–F3).

**Implicación D4:** la tubería `principal → owner_user_id → account_repository` ya existe; D4 sustituye **de dónde sale** el principal (JWT/`users` en lugar de constante `"app"`), no reescribe `ExecuteTrade`.

---

## 3. Opciones de decisión (propietario)

### Opción A — Mantener single-tenant (no abrir D4)

**Qué:** conservar `APP_PASSWORD` + principal fijo `"app"`; endurecer solo operativa (rotación secretos, TTL, rate-limit ya en R-8B.1).

**Pros:** cero migración · cero regen contrato · alineado con instancia personal / demo cerrada (ADR-004, premisas OR-lite).

**Contras:** no cumple auditoría «auth global multiusuario» (`plan-refactor-refuerzo-post-v1-3-0-2026-08-21.md:144`); cualquier cookie válida sigue siendo «el mismo operador».

**Cuándo elegir:** la app **no** se expone a terceros con datos separados.

---

### Opción B — Multi-user JWT (identidad real, varios operadores)

**Qué:** tabla `users` (id, email/login, password_hash, role, status); login emite **JWT** (o PASETO) con `sub=user.id`; middleware resuelve `request.state.principal = sub`; cuentas/recursos scoped por ese id; sesiones revocables (denylist o `session_version` en user).

**Pros:** modelo estándar · encaja ADR-004/008 · desbloquea SaaS / equipos · revocación por usuario.

**Contras:** migración + backfill · regen contrato acotada (login/register/refresh/me) · superficie FE · riesgo regresión en jobs (custodia, scheduler).

**Cuándo elegir:** decisión de **exponer** la instancia a >1 operador con datos aislados.

---

### Opción C — Híbrido (recomendado como transición si se abre D4)

**Qué:** fases incrementales:

1. **C.1** — Mantener `APP_PASSWORD` como «modo instancia» (1 user bootstrap `app` en BD) **mientras** se introduce tabla `users`.
2. **C.2** — JWT con un solo user admin creado por migración; principal deja de ser constante.
3. **C.3** — Admin UI/API crea users adicionales; legacy `user_id is None` se cierra por política (§6).

**Pros:** rollback fácil · compatibilidad despliegues actuales · prueba JWT sin multi-tenant completo el día 1.

**Contras:** dos modos coexisten temporalmente → requiere ADR claro de deprecación de `APP_PASSWORD`-as-principal.

**Recomendación de plan:** **Opción C** si el propietario aprueba abrir D4; **Opción A** si la app permanece single-tenant.

**✅ Elegida por el propietario (2026-08-22): Opción C.** Formalizada en ADR-027 (Propuesto).

---

## 4. ADR necesarios (antes de código F5+)

| ADR                           | Tema                     | Contenido mínimo                                                                                                                                                                                                             |
| ----------------------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ADR-027** (nuevo)           | Modelo auth multi-user   | ✅ Creado **Propuesto** [`docs/adr/027-auth-multi-user-jwt-hybrid.md`](../adr/027-auth-multi-user-jwt-hybrid.md) · Opción **C** · JWT claims · cookie/Bearer · fail-closed · anexo legacy NULL · NO-touch · criterios F5–F7. |
| **ADR-027 anexo**             | Legacy `user_id is None` | Incluido en ADR-027 (F7a/F7b/F7c).                                                                                                                                                                                           |
| **Actualizar ADR-004** §0     | Estado UI auth           | ✅ Nota cookie HttpOnly + roadmap JWT (2026-08-22).                                                                                                                                                                          |
| **Actualizar ADR-008** (nota) | Multi-usuario            | ✅ Nota enforced ADR-027 (2026-08-22).                                                                                                                                                                                       |

**Gate:** ningún commit de implementación F5+ sin ADR-027 **Aceptado** por propietario (actualmente **Propuesto**).

---

## 5. Fases de implementación F4+ (post F1–F3)

### Leyenda NO-touch (todas las fases)

**NO tocar** salvo fase explícita y OK:

| Área                                                                                                                             | Motivo                                                            |
| -------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `packages/py/application/**` paths de dinero (`ExecuteTrade`, `DepositCashToAccount`, `WithdrawCashFromAccount`, custodia apply) | R12-AUTH F3: guards solo en rutas; motor intacto (`5fe5ace`).     |
| `openapi.json` / `contract:gen`                                                                                                  | Salvo fase con regen acotada pactada (login/register/me/refresh). |
| `pending-delete/**` purge storage                                                                                                | Riesgo alto; E8.                                                  |
| Gobernanza IA / `ai_governance` routes                                                                                           | Freeze R-12.                                                      |
| `PAPER_D_EXECUTE`                                                                                                                | Freeze.                                                           |
| FE auth (`apps/web/**` auth)                                                                                                     | Documentar en plan; implementación solo fase **F9** pactada.      |

---

### F4 — Decisión + ADR + inventario gaps (docs + tests read-only)

**Estado:** **✅ CERRADA** (`cdda80d`) — Opción C · ADR-027 **Aceptado**.

---

### F5 — Identidad mínima (tabla `users` + login JWT, single admin)

**Estado:** **✅ CERRADA** (`02c86fc` / `98b4986`).

**Qué (Opción C.2):**

1. Migración Alembic: `users` (id UUID/text, login unique, password_hash argon2/bcrypt, role, created_at, disabled_at).
2. Seed/bootstrap: user `app` o admin desde env **una sola vez** (no registro público).
3. `POST /api/auth/login`: validar contra `users`; emitir JWT firmado con `APP_AUTH_SECRET` (o clave dedicada `JWT_SIGNING_KEY`); cookie HttpOnly con JWT (misma forma `Secure`/TTL R-8B.2) **o** header Bearer JWT.
4. Middleware: si JWT válido → `request.state.principal = claims["sub"]`; si falla JWT, **fallback temporal** a gate `APP_PASSWORD` legacy (solo si ADR-027 lo permite).
5. Deprecar token SHA-256 determinista (`tokens.py`) tras ventana acordada.

**NO:** multi-registro · refresh rotation compleja · FE · backfill masivo legacy.

**Batería:**

- `pytest apps/api-python/tests/test_auth.py` (ampliar JWT + fallback)
- `pytest apps/api-python/tests/test_account_isolation.py` (principal distinto de `"app"` vía JWT mockeado)
- ruff/mypy zona `bolsa_api/auth/**`
- **no** chaos money · **no** `contract:gen` salvo DTO login acordado

---

### F6 — Scoping list/get accounts al principal JWT

**Estado:** **✅ CERRADA** (`98b4986`).

**Qué:**

1. `ListAccounts` / list summaries: pasar `owner_user_id=get_request_principal(request)` desde rutas (`accounts.py:61-76`).
2. `GetAccount` y mutaciones sin guard previo: exigir owner en repo o Depends.
3. Tests: user A no ve cuentas de user B en `GET /accounts`.

**NO:** money paths · jobs.

**Batería:** pytest isolation ampliado · integration `test_accounts.py` list filter.

---

### F7 — Política legacy `user_id is None` (backfill controlado)

**Estado:** **F7a ✅ CERRADA** (`98b4986`) · F7b/F7c pendientes decisión propietario.

**Qué (decisión en ADR-027 anexo):**

| Política                             | Descripción                                                                                                                                        |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F7a — Soft (default recomendado)** | Mantener visibilidad legacy solo para principal bootstrap `app` / admin; otros users no ven `NULL`.                                                |
| **F7b — Backfill one-shot**          | Script migración: `UPDATE investment_accounts SET user_id = :bootstrap WHERE user_id IS NULL` en ventana de mantenimiento; **no** en hot path API. |
| **F7c — Hard close**                 | Cambiar `account_visible_to_principal` a exigir match estricto (rompe datos huérfanos sin F7b).                                                    |

**Evidencia premisa previa:** R10 D6 «sin backfill» fue decisión **fiscal/idempotencia**, no auth — re-evaluar solo para auth con OK propietario.

**Batería:** tests legacy + post-backfill · verify en DB staging.

---

### F8 — Recursos colaterales (`investor_profiles`, trackers, policies, events)

**Estado:** **✅ CERRADA** (`5e7c67b` + **F8b** `2cd20b0` + **F8e** 2026-08-22) — perfiles inversor + job custodia + **trackers/policies scoped**. **Gaps residuales:** `platform_events` · workspaces.

**F8b (trackers + execution_policies):** list/create/get/update/delete scoped por `principal`; repos filtran owner + F7a legacy NULL; tests `test_trackers_policies_isolation.py` (7 passed).

**Qué:** propagar `principal` a repositorios con columna `user_id`; guards en rutas de catálogo; jobs internos filtran por owner cuando apliquen.

**Gap crítico:** `list_active_accounts` (`account_repository.py:168-181`) debe aceptar `owner_user_id` o documentar «job system opera all tenants» (inaceptable en multi-user → filtrar).

**NO:** gobernanza IA · ExecuteTrade.

**Batería:** pytest por recurso · job custodia test con 2 users.

---

### F9 — Frontend auth (solo si fase pactada)

**Estado:** **✅ CERRADA** (`26494d8`) — login FE con campo `login` opcional.

**Qué:** login por user/password (no password global); bootstrap status con JWT; opcional admin users.

**NO:** refactors shell · contract:gen salvo endpoints nuevos.

**Batería:** web typecheck · lint · vitest auth · build.

---

### F10 — Endurecimiento (refresh, revocación, roles)

**Estado:** **✅ CERRADA** (`837ec85`) — migración `008_users_session_version` · claim JWT `sv` · `POST /api/auth/refresh` · logout invalida sesión · `require_role` helper · rate-limit por user · audit login. **Fallback `APP_PASSWORD` intacto** (opcional diferido).

**Qué:** refresh token rotativo · `session_version` en user · roles (`admin`/`operator`) · rate-limit por user · auditoría login.

**Opcional:** retirar fallback `APP_PASSWORD` legacy.

**Batería:** test_auth completo · penetration checklist OR-S1.

---

## 6. Migración / backfill `user_id` (política)

1. **Cuentas nuevas (ya hecho F1):** siempre `user_id = principal` al crear (`account_repository.py:229`).
2. **Legacy `NULL`:** visible para todos los principals hoy (`principal.py:37-38`) — **deuda consciente** para single-tenant; **bloqueante** para multi-user estricto.
3. **Orden recomendado:** F5 (JWT sub) → F6 (list/get) → F7b backfill staging → F7c hard close opcional.
4. **Prohibido en F5–F6:** backfill automático en `database_bootstrap` (side-effect sorpresa en prod).
5. **Seed demo:** `account_migration.py:89` ya estampa `owner_principal()` en cuenta demo nueva — alinear con user bootstrap post-F5.

---

## 7. Batería mínima por fase (resumen)

| Fase | pytest                                      | ruff/mypy      | contract                   | chaos money |
| ---- | ------------------------------------------- | -------------- | -------------------------- | ----------- |
| F4   | existente verde                             | —              | no                         | no          |
| F5   | test_auth + isolation JWT                   | auth/\*\*      | solo si DTO login cambia   | no          |
| F6   | test_account_isolation + test_accounts list | routes+deps    | no                         | no          |
| F7   | legacy + post-backfill                      | repo principal | no                         | no          |
| F8   | per-resource + custody job                  | repos tocados  | no                         | no          |
| F9   | web tests                                   | web auth       | regen acotada si API nueva | no          |
| F10  | auth extended + rate-limit                  | auth           | regen si refresh/me        | no          |

Comando base API: `pytest apps/api-python/tests/test_auth.py apps/api-python/tests/test_account_isolation.py`.

---

## 8. Evaluación de riesgos

| Riesgo                                         | Severidad | Mitigación                                                              |
| ---------------------------------------------- | --------- | ----------------------------------------------------------------------- |
| Regresión money por tocar application layer    | **Alto**  | NO-touch estricto; guards solo en `bolsa_api` (patrón F3).              |
| Legacy `user_id NULL` filtra datos entre users | **Alto**  | F7 antes de abrir multi-user real; tests explícitos.                    |
| Job custodia opera cuentas ajenas              | **Alto**  | F8: `list_active_accounts` con owner o job impersonation documentada.   |
| Rotura FE login (cookie/JWT)                   | **Medio** | F9 separada; mantener fallback Bearer en middleware durante transición. |
| Regen contrato no controlada                   | **Medio** | Regen acotada por fase; `contract:check` gate CI.                       |
| JWT secret reuse con `APP_AUTH_SECRET`         | **Medio** | ADR-027: clave dedicada + rotación.                                     |
| Scope creep (workspaces, lists sin user_id)    | **Medio** | Inventario F4; fases F8+ o ADR V2 workspace-per-user.                   |
| Confusión ADR-004 / docs viejos                | **Bajo**  | Actualizar ADR-004 en F4.                                               |

---

## 9. Gaps documentados (file:line)

| #   | Gap                                                                        | Evidencia                                     | Estado F8 |
| --- | -------------------------------------------------------------------------- | --------------------------------------------- | --------- |
| G1  | Principal no derivado de credenciales                                      | `middleware/auth.py` JWT → `sub`              | ✅ F5     |
| G2  | Token no identifica usuario                                                | `jwt.py` + login `users`                      | ✅ F5     |
| G3  | Sin tabla `users`                                                          | migración + `UserRow`                         | ✅ F5     |
| G4  | `list_active_accounts` sin filtro owner                                    | `account_repository.py` + `custody_job.py`    | ✅ F8     |
| G5  | Use-cases CRUD sin `owner_user_id` param                                   | `accounts/crud.py` + rutas F6                 | ✅ F6     |
| G6  | Perfiles / trackers / policies: `user_id` nullable sin guard HTTP uniforme | perfiles ✅ F8 · trackers/policies ✅ **F8b** | ✅ F8b    |
| G7  | ADR-004 desactualizado (sessionStorage)                                    | nota cookie HttpOnly añadida F4               | docs OK   |
| G8  | Workspaces sin columna `user_id`                                           | búsqueda modelos workspace: 0 matches         | abierto   |

---

## 10. Criterios de cierre D4 (global)

1. ADR-027 aceptado y opción A/B/C ejecutada según decisión.
2. Si multi-user: JWT (o sucesor) resuelve `request.state.principal` desde identidad autenticada.
3. Cuentas y rutas F1–F3 siguen 404 cross-tenant **con principals distintos** (tests verdes).
4. Política legacy `user_id NULL` documentada y aplicada (F7).
5. Jobs críticos (custodia) no cruzan tenants.
6. Freeze actualizado en `PROJECT_STATE.md` / backlog §0 / traspaso R-12.
7. Cero cambios no autorizados en money motor ni purge pending-delete.

---

## 11. Primera fase recomendada tras OK del propietario

**D4 Opción C — F4–F10 cerradas** en `main` (`2cd20b0` · `837ec85`).

**Siguiente R-12 (fuera D4):** monitor ventana purge V2 (E8 N, abierta 2026-08-22) · opcional retirar fallback `APP_PASSWORD` · F7b/F7c legacy NULL.

---

## 12. Referencias

- R12-AUTH F1–F3: [`plan-r12-auth-fase1-2026-08-22.md`](./plan-r12-auth-fase1-2026-08-22.md)
- Relevo gates: [`traspaso-relevo-r12-apertura-2026-08-21.md`](./traspaso-relevo-r12-apertura-2026-08-21.md) §2 NO tocar JWT/D4
- R-8B.2 sesión cookie: [`plan-r8-prevencion-riesgo-2026-08-20.md`](./plan-r8-prevencion-riesgo-2026-08-20.md) §R-8B.2
- Deuda V2 auth global: [`plan-refactor-refuerzo-post-v1-3-0-2026-08-21.md`](./plan-refactor-refuerzo-post-v1-3-0-2026-08-21.md) §4
