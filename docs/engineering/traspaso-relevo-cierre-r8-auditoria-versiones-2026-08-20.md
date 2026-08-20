# RELEVO / TRASPASO — Cierre R-8·R-8B.3 → CONTRACT-STALE + auditoría externa + versión GitHub (2026-08-20)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE** que debe cerrar lo pendiente (abriendo los subagentes que hagan falta) y, al final, **documentar todo y elevar la versión en GitHub**. Es el ancla anti-saturación / anti-alucinación de relevo: cualquier agente nuevo **LEE ESTE DOC + el backlog §0/§1 ANTES de tocar nada**.
> **Estado al redactar (verificado):** `local main = origin/main = 681a46c` · working tree limpio · CI verde pre-R-8B.3 (Python quality / Frontend / scientific / optimize / gitleaks).
> **AsOf:** 2026-08-20.

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** `main` == `origin/main` == `681a46c`. Árbol limpio (`git status --short` vacío).
- **Últimos commits (`main`):**
  | Commit | Contenido |
  |---|---|
  | `681a46c` | docs: cerrar R-8B.3 completa (update-last backlog/plan/PROJECT_STATE) |
  | `fb95b27` | R-8B.3 D (account-settings `notes?`) |
  | `e6dde15` | R-8B.3 C (dictamen 8 campos `?` + fix `opinion-channel-map`) |
  | `ce1d5ca` | R-8B.3 B (signal-alerts `channels?`) |
  | `756e3a1` | R-8B.3 FIE FUND (11 campos `?` scores) |
  | `89b179b` | docs: cerrar R-8B.3 Fase A + registrar CONTRACT-STALE |
  | `158b3db` | R-8B.3 Fase A (cash `description?`) |
  | `71fd957` | (base) docs: cerrar R-8C y R-8D |
- **R-8 COMPLETA en `main`:** R-8A (`edf2d0c`+`7f327ab`) · R-8B.1 (`ac147fe`+`a1360bb`) · R-8B.2 (`abf3dc2`) · R-8C (`3ad48aa`) · R-8D (`dbd1ee5`) · **R-8B.3** (`158b3db`,`756e3a1`,`ce1d5ca`,`e6dde15`,`fb95b27`).
- **R-7 COMPLETA** (deuda dinero real cerrada; solo `M-4/T-M4` diferido por freeze).

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente (las 3 reglas que no se negocian)

1. **Read-first anti-alucinación:** antes de abrir CUALQUIER fase/subagente, **LEE** `docs/engineering/backlog-trabajo-2026-08-20.md` **§0 y §1** y `docs/engineering/PROJECT_STATE.md`. Si el repo no coincide con el backlog → **PARAR y re-leer**; nunca seguir por inercia.
2. **Una fase = un subagente acotado + verificación del coordinador + batería real + aprobación de usuario POR COMMIT + push a `main` (rama protegida, requiere aprobación nativa)**. El coordinador **nunca** se fía del reporte de un subagente: contrasta cada diff contra el código real y corre la batería él mismo. Máx. ~3 subagentes en paralelo por chat.
3. **Anti-alucinación / anti-pérdida:** todo hallazgo del subagente se verifica en el código (file:line); si un subagente afirma algo sin evidencia reproducible, se rechaza y se re-pide. Los subagentes en paralelo deben recibir **alcances disjuntos (ficheros distintos)** y el **mapa de consumidores ya verificado** inyectado en el brief para que no redis cubran/alucinen call-sites.

### Batería mínima (re-verificada por el coordinador en cada fase)

- **Frontend (shared/web):** `pnpm --filter @bolsa/shared typecheck|lint|test` (17) · `pnpm --filter @bolsa/web typecheck|lint|test` (714) · si toca FE: `build`. **D5:** `contract:check` (ojo: en PowerShell Windows ejecutar `$env:PYTHONIOENCODING='utf-8'` antes o falla por encoding, no por contrato).
- **Backend (py):** `ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de los ficheros en gate CI · pytest de la zona.
- **Git:** `git status` acotado a los ficheros declarados por la fase.

---

## 3. TRABAJO PENDIENTE A CERRAR (nuevo agente)

> ⚠️ **Clave:** distinguir lo **accionable ya** de lo **explícitamente "no tocar" hasta decisión de usuario**. El nuevo agente **NO** auto-cierra ítems bloqueados; los presenta y pide decisión. Solo el **CONTRACT-STALE** es técnicamente accionable ahora (más la versión + documentación).

### 3.1 🔴 CONTRACT-STALE — ÚNICO trabajo técnico accionable ahora (subagente recomendado)

- **Qué:** `apps/web/api/openapi.json` + `apps/web/src/api/schema.d.ts` están **stale** respecto al código Python (drift preexistente de R-8A/R-8B.2). `contract:check` → **ROJO** (por drift, NO por R-8B.3; probado: `sync-contract.mjs` solo lee FastAPI/Pydantic, nunca `packages/shared`).
- **Qué falta incluir:** `DepositCashDto.idempotencyKey`/`WithdrawCashDto.idempotencyKey` (`apps/api-python/src/bolsa_api/schemas/accounts.py:252,260`) · default `AuthStatusDataDto.authenticated` (R-8B.2) · descripción `logout`.
- **Riesgo / decisión previa:** el `contract:gen` en Windows falla por `UnicodeEncodeError` (ver R-8B.2): requiere **regeneración MANUAL acotada** (subagente que: corra el dump + genere schema, revisa el diff componente a componente para NO meter scope-scope de otras fases ni claves nuevas, y ajuste call-sites web si algún tipo cambia). **Decisión usuario 2026-08-20: NO se regen dentro de las fases de R-8B.3**; se abre como **fase propia** ahora.
- **Subagente sugerido (read-only primero):** mapear el diff de `sync-contract.mjs --check` (componente a componente) para listar EXACTAMENTE qué cambia vs lo commiteado; decidir qué es legítimo (idempotencyKey/authenticated) vs cualquier drift no deseado; NO tocar `packages/shared` ni `index.ts`. Luego, bajo aprobación, `contract:gen` manual + fix de call-sites web si tsc falla + `contract:check` VERDE.
- **Criterio de aceptación:** `contract:check` OK · web typecheck/lint/test verdes · `git status` acotado a `openapi.json`+`schema.d.ts`+(call-sites web si procede) · diffs mínimos.

### 3.2 🟡 Ítems de decisión de usuario (NO auto-cerrar — presentar y esperar)

| Ítem                                                                                                                                                                                                                                                 | Origen | Regla vigente                                                                                                                                                             |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`pending-delete/README.md` riesgo alto** (`readLegacyPendingOrders` gate bolsa-trading-ui · `chartDataStrip`/`chartNewTabSeed`/`newChartConfigSource` migración workspaces · `readLegacyTimeframeFavorites` · re-export `presetRuleGroups` shared) | R-8D   | **NO tocar hasta decisión explícita de `purge storage`** (dependen del nombre en localStorage). Fuente: `docs/engineering/pending-delete/README.md` + `PROJECT_STATE.md`. |
| **R-8C.2 scheduler-vs-worker** (no-ARQ comparte event-loop)                                                                                                                                                                                          | R-8C   | **documentada SOLA; NO tocar código worker salvo decisión.** `PROJECT_STATE.md §3`.                                                                                       |
| **M-4/T-M4** (job dedicado custodia fuera del path de lectura)                                                                                                                                                                                       | R-7    | **diferido por freeze.**                                                                                                                                                  |
| Checklist operativo manual (§4 backlog): secret scanning UI, `TRUSTED_PROXIES` prod, `BP/.L→BP.L` en BD, limpiar `logs/dev`                                                                                                                          | R-1    | **acciones manuales / fuera de repo** — informar al usuario, no resolver por código.                                                                                      |

### 3.3 🏁 Cierre global (obligatorio al final de todo)

1. **Documentar todo:** update-last en `backlog-trabajo-2026-08-20.md` (§0 estado + §6 historial con commits/batería), `plan-r8-prevencion-riesgo-2026-08-20.md` (§5/§6), `PROJECT_STATE.md` (§2 ejecución + §3 deuda, marcando CONTRACT-STALE resuelto o su estado), y registrar en `engineering-index-2026-08-03.md` §5.
2. **Elevar versión en GitHub (release/tag):** precedente = tag anotado `v1.0.0` en `879ea23` con mensaje `release: Bolsa V1.0.0 — embudo, DÍA D, CORE-P/R, FA`. Versiones actuales: root `package.json` `1.0.0`, web/shared `0.1.0`. **Recomendación (pendiente confirmar con el usuario/propietario):** `v1.1.0` como release anotado (incluye R-7+R-8 hardening: auth sesión HttpOnly `abf3dc2`, rate-limit `ac147fe`, bootstrap P0 `edf2d0c`, idempotencia, invariante balance, fidelidad wire R-8B.3). Antes de taggear: confirmar en `apps/web/package.json`/`packages/shared/package.json` si se trackea subversión (`0.1.x`) o solo tag raíz.
3. **Auditoría externa del estado global** (petición del usuario): tras el tag, encargar una auditoría externa nueva sobre `main` nuevo tip (vía `TRUSTED_PROXIES`... no; vía el flujo habitual: pack de estado = `docs/engineering/audit-pack-estado-global-2026-08-20.md`). Esto es **manual/decisión**, no un subagente de código.

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-20): repo `Bolsa_V1` en `main` = `681a46c`, árbol limpio. **R-7 y R-8 completas en `main`** (incl. R-8B.3). Tienes que cerrar lo pendiente.
> **LEE PRIMERO (obligatorio):** `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1 · `docs/engineering/PROJECT_STATE.md` · `docs/engineering/traspaso-relevo-cierre-r8-auditoria-versiones-2026-08-20.md` (= este doc).
> **Alcance de trabajo:** (1) **CONTRACT-STALE** — fase dedicada con subagente read-only + regen manual acotado para dejar D5 `contract:check` VERDE (NO `regen_full`, NO cambiar `packages/shared`, revisar diff componente a componente). (2) Presentar al usuario (NO auto-cerrar) los ítems §3.2 (pending-delete riesgo alto, R-8C.2, M-4/T-M4, checklist manual). (3) Al final: **documentar todo** (update-last backlog/plan/PROJECT_STATE/index) y **elevar versión en GitHub** (ver §3.3).
> **Protocolo:** una fase = un subagente acotado + verificación del coordinador (diff + batería real) + **aprobación de usuario por commit** + push a `main` (protegida, aprobación nativa). Máx 3 subagentes paralelos, alcances disjuntos, mapa de consumidores verificado inyectado. Anti-alucinación: contrastar contra código.
> **NO tocar:** `pending-delete` riesgo alto, worker scheduler (R-8C.2), M-4/T-M4, gobernanza IA, Belief/H, features nuevas. No `regen_full` ni `contract:gen` salvo la fase pactada.

### 4.2 Brief para el SUBAGENTE de CONTRACT-STALE (fase 1 — read-only + regen acotado)

> Fase **CONTRACT-STALE**. Repo `main`=`681a46c`, árbol limpio. `contract:check` (`pnpm --filter @bolsa/web contract:check`, precedido de `$env:PYTHONIOENCODING='utf-8'`) está ROJO por drift preexistente: `openapi.json`/`schema.d.ts` stale vs FastAPI (`DepositCashDto.idempotencyKey`/`WithdrawCashDto` en `schemas/accounts.py:252,260`, default `AuthStatusDataDto.authenticated`, descripcion `logout`).
> **PASO 1 (read-only, NO tocar código):** ejecuta `contract:gen` en un trabajo aparte o `sync-contract.mjs` y genera el diff; lista componente a componente (file:line) qué cambia en `openapi.json`/`schema.d.ts` y CLASIFICA cada cambio como (a) legítimo (idempotencyKey/authenticated/logout de R-8A/8B) o (b) drift no deseado. Verifica contra el código Python real (`apps/api-python/src/bolsa_api/schemas/**`) que cada componente legítimo existe ahí. NO toques `packages/shared`, `index.ts`, ni elimines/estreches claves.
> **PASO 2 (implementación, solo bajo aprobación previa del coordinador/usuario):** aplica la regeneración acotada, revisa si algún call-site web rompe por tipos que pasan a optional/nullable (ajusta con `?? []`/`?? null`, sin cambiar semántica) para dejar `web typecheck` 0.
> **Batería de aceptación:** `contract:check` OK · shared typecheck/lint/test (17) · web typecheck 0 · lint 0 · test 714 · `git status` acotado a `openapi.json`+`schema.d.ts`+(call-sites web si procede). Devuelve diff exacto + clasificación de cada componente.

### 4.3 Brief para el momento RELEASE/TAG (después de cerrar fase + docs)

> Eleva versión en GitHub: crea tag **anotado** `v1.1.0` (u otro pendiente de aprobación) en el tip de `main` con `git tag -a v1.1.0 -m "release: Bolsa V1.1.0 — integridad R-7/R-8 y fidelidad de contrato (sesión HttpOnly, rate-limit auth, bootstrap advisory-lock, idempotencia, balance_after, fidelidad wire R-8B.3)"`. Confirma si packages tienen subversión a bumpear (`apps/web/package.json`/`packages/shared/package.json` `0.1.0`). Luego `git push origin v1.1.0`. Crea la Release en GitHub para ese tag con notas de cambios. NO quemar sin aprobación explícita del usuario/propietario en ese turno.

---

## 5. Enlaces (fuentes de verdad — no inventar estado)

- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md` (§0/§1 · §4 checklist · §6 historial)
- Estado vivo: `docs/engineering/PROJECT_STATE.md` (§2 ejecución · §3 deuda, incl. R-8C.2 y **CONTRACT-STALE** v13)
- Plan R-8: `docs/engineering/plan-r8-prevencion-riesgo-2026-08-20.md`
- Pack auditoría externa: `docs/engineering/audit-pack-estado-global-2026-08-20.md`
- Índice / registro: `docs/engineering/engineering-index-2026-08-03.md` §5
- `pending-delete`: `docs/engineering/pending-delete/README.md` (riesgo alto → hasta `purge storage`)

---

## 6. Cierres parciales registrados hasta este relevo (historial reducido)

| Fecha      | Hito                                 | Commits `main`                                                                  |
| ---------- | ------------------------------------ | ------------------------------------------------------------------------------- |
| 2026-08-20 | R-7 COMPLETA                         | (serie R-7 ya en main)                                                          |
| 2026-08-20 | R-8A · R-8B.1 · R-8B.2 · R-8C · R-8D | `edf2d0c`,`7f327ab`,`ac147fe`,`a1360bb`,`abf3dc2`,`3ad48aa`,`dbd1ee5`,`71fd957` |
| 2026-08-20 | R-8B.3 Fase A cash                   | `158b3db` (+docs `89b179b`)                                                     |
| 2026-08-20 | R-8B.3 FIE FUND / B / C / D          | `756e3a1`,`ce1d5ca`,`e6dde15`,`fb95b27` (+docs `681a46c`)                       |
