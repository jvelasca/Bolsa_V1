# Traspaso — F5a §6 fidelidad restante: `openapi-fetch` como cliente completo (2026-08-12)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5
> (fase F5a §6 fidelidad restante, deuda registrada en
> [traspaso-f5a-fidelidad-gate-2026-08-12.md](./traspaso-f5a-fidelidad-gate-2026-08-12.md) §7 y
> [traspaso-nueva-ola-fin-refactorizacion-2026-08-12.md](./traspaso-nueva-ola-fin-refactorizacion-2026-08-12.md) §3).
> **Rama de ejecución:** `stage/f5a-openapi-fetch-2026-08-12` (desde base `d25d71f` = tip PR #51 en
> `stage/f1-integridad-financiera-2026-08-11`).
> **Regla del hilo:** NO tocar código fuera del alcance de la fase. Batería por paso.
> **Estado:** **COMMITEADO + PR #52 ABIERTO** (commit `a302f22`). Batería local VERDE. CI: `scan` ✓, `quality`/`battery` pendientes.

---

## 1. Deuda que resuelve esta fase (contexto)

Cierre de F5a-contratos (ADR-003 §2 fija como contrato objetivo `FastAPI → openapi.json →
openapi-typescript + openapi-fetch → apps/web`): el gate `contract-check.ts` quedó bidireccional sobre 11
sentinelas (unidireccional antes) pero el cliente HTTP seguía siendo `apps/web/src/lib/api.ts` (~2.073
líneas) con transporte **manual** `request<T>` (fetch + `JSON.stringify` + cabeceras acumuladas) y DTOs
`@bolsa/shared` escritos a mano. Este traspaso resuelve la parte de **transporte**: adoptar `openapi-fetch`
como cliente íntegro, **sin** reconciliar DTOs campo-a-campo ni fidelidad de tipos de valor (→ P2.6).

## 2. Alcance de esta fase (decisión del usuario)

**D5 cero features, cambio de transporte solo:**

- **`openapi-fetch@^0.17.0`** como cliente HTTP completo de `apps/web/src/lib/api.ts` (≈145 métodos).
- **NO** reconciliar los ~87+ DTOs de wire restantes vs contrato (→ P2.6). **NO** fidelidad de tipos de
  valor (`manifest`, `number↔integer`, `null↔undefined`). **NO** tocar `contract-check.ts`/sentinelas.
- **NO** tocar el backend / OpenAPI / `schema.d.ts` / `openapi.json`. Superficie pública `api` **idéntica**
  (cero call sites afectados).

## 3. Implementación

| #     | Fichero                                                  | Qué                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | `apps/web/package.json` (+ lockfile)                     | `openapi-fetch@^0.17.0` en `dependencies` (vía `pnpm --filter @bolsa/web add openapi-fetch@^0.17.0`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| **B** | `apps/web/src/lib/api.ts` (modificado, 2083→1904 líneas) | Cliente `createClient<paths>` (`baseUrl: API_URL` desde `resolveApiBaseUrl()`) + **un único middleware** `onRequest`/`onError` (inyecta `Authorization`, `X-Account-Id`, `Content-Type` respetando cabeceras ya presentes; `TypeError` de red → `ApiError(..., 0)`). Helper `call<T>(fn)` que desenvuelve `{data,error,response}` replicando `request<T>` (401 → `"Sesión expirada..."`, no-OK → `formatApiErrorDetail(error) ?? statusText`, 204/body vacío → `undefined`). Helper `apiBody<T>(body): never` (cast benigno para optionality/index-signature del requestBody, wire idéntico). Cada método → `call(() => client.GET/POST/PUT/PATCH/DELETE(route, { params, body, headers, signal }))` con path params snake_case del contrato (`{instrument_id}`, `{account_id}`, `{run_id}`…) via `params.path` y query via `params.query`. |

**Casos especiales preservados (D5):**

- `depositCash`/`withdrawCash`: `params.path.account_id` **y** `headers["X-Account-Id"]` por-request
  (precedencia sobre el middleware si el accountId difiere del activo).
- `updateWorkspaceKeepalive` (PUT fire-and-forget `keepalive:true`) y los formatos `FormData`/blob
  conservan su `fetch` crudo.
- Métodos con `signal` (p. ej. `runBacktest`) reenvían `{ signal }` a openapi-fetch (no se pierde la
  cancelación).

## 4. Batería (aplicada y verificada)

- `contract:check` (`PYTHONIOENCODING=utf-8`) → **VERDE** ✓ reproducible (sin diff en `openapi.json`/`schema.d.ts`).
- `pnpm --filter @bolsa/web typecheck` → **✓** (0) — incluye el gate `contract-check.ts` bidireccional.
- `pnpm --filter @bolsa/web lint` → **0 errores** (2 warnings pre-existentes en `backtests-page.tsx`, no tocados).
- `pnpm --filter @bolsa/web test` → **714 passed (141 files)** — sin regresiones.
- `pnpm --filter @bolsa/shared typecheck` → **✓** (0).

## 5. Registro

| Fecha      | Acción                                                                                                                                                                                                |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-12 | Decisión usuario: empezar por **F5a §6 / openapi-fetch** (alcance exclusivo). Merge PR #51 (docs nueva ola) en base para trazabilidad (base `301777b` → `d25d71f`).                                   |
| 2026-08-12 | Subagente (ejecución pesada) reescribe `api.ts` con openapi-fetch 0.17.0. Batería del subagente: typecheck 0 · lint 0 · test 714 ✓ · shared 0.                                                        |
| 2026-08-12 | Verificación independiente del hilo principal: typecheck ✓ · lint 0 (2 warnings pre-existentes) · test **714/141** · shared ✓ · **contract:check VERDE** · árbol limpio (solo 3 ficheros en alcance). |
| 2026-08-12 | Commit `a302f22` y **PR #52 abierto** → base `stage/f1-*`. CI: `scan` ✓, `quality`/`battery` en curso.                                                                                                |

## 6. Deuda / fuera de alcance (sin resolver aquí)

- **Reconciliar campo-a-campo los ~87+ DTOs de wire restantes** vs contrato → **P2.6** (acuerdo de fuente de verdad).
- **Fidelidad de tipos de valor**: `manifest`, `number↔integer`, `null↔undefined`, optionality del
  `requestBody` — absorbida de momento con `apiBody<never>` (cast benigno, wire idéntico) y algún `as`
  puntual → **P2.6**. No es drift TS detectable y degradaría el FE.
- **Consolidar tipos web-only re-declarados** (`RecommendationV1`, `CoreRVerdict`, `RunManifest`) → P2.6.
- Deuda previa: P1.9 API thin (hilo propio), P1.3 auth full (D4), consumir `operations`/`paths` en más
  frentes frontend.

## 7. Cierre — resultado alcanzado y texto de traspaso

F5a §6 — adoptar `openapi-fetch` como cliente **COMPLETADO** (commit + PR):

- `apps/web/src/lib/api.ts` (2083→1904 líneas) usa `openapi-fetch@^0.17.0`: `createClient<paths>` +
  middleware (auth/`X-Account-Id`/`Content-Type` + error de red → `ApiError` 0) + `call<T>` que replica
  `request<T>` y `apiBody` para optionality benigna.
- **D5**: superficie `api` idéntica, cero call sites, cero cambios de wire, `openapi.json`/`schema.d.ts`
  sin diff.
- Batería: `contract:check` VERDE · web typecheck 0 · lint 0 · test 714/141 · shared 0.

### Texto de traspaso (pegable en el próximo chat)

> CONTEXTO INMEDIATO: **F5a §6 — adoptar `openapi-fetch`** como cliente HTTP de `apps/web/src/lib/api.ts`
> **COMMITEADO + PR #52 ABIERTO** (commit `a302f22`, rama `stage/f5a-openapi-fetch-2026-08-12` desde base
> `d25d71f` = tras merge PR #51). Base viva `stage/f1-integridad-financiera-2026-08-11`.
>
> - `api.ts` (2083→1904 líneas) usa `openapi-fetch@^0.17.0`: `createClient<paths>` + **un middleware**
>   (`Authorization`/`X-Account-Id`/`Content-Type` respetando cabeceras ya presentes; `TypeError` de red →
>   `ApiError` status 0) + helper `call<T>` que desenvuelve `{data,error,response}` replicando `request<T>`
>   (401 específico, `formatApiErrorDetail`, 204/body vacío → undefined) + `apiBody<never>` (cast benigno
>   por optionality/index-signature del requestBody, wire idéntico).
> - **D5**: superficie pública `api` idéntica, **cero call sites** tocados, **cero cambios de wire**,
>   `openapi.json`/`schema.d.ts` sin diff. Path params snake_case del contrato via `params.path`
>   (`{instrument_id}`/`{account_id}`/`{run_id}`...); query via `params.query`. `depositCash`/`withdrawCash`
>   preservan `X-Account-Id` por-request; `updateWorkspaceKeepalive` y formatos FormData/blob conservan
>   `fetch` crudo; métodos con `signal` lo reenvían.
> - BATERÍA verificada: `contract:check` VERDE (reproducible) · web typecheck 0 · lint 0 (2 warnings
>   pre-existentes) · test **714/141** · shared typecheck 0.
> - Pendiente: CI de PR #52 (`quality`/`battery`), merge en base, registro en `engineering-index` §5 +
>   cierre de este traspaso.
>
> DEUDA REGISTRADA → fases posteriores (sin resolver):
>
> - **Reconciliar ~87+ DTOs de wire** vs contrato campo-a-campo → **P2.6** (acuerdo de fuente de verdad).
> - **Fidelidad de tipos de valor** (`manifest`, `number↔integer`, `null↔undefined`) → **P2.6**; ahora
>   absorbida por `apiBody<never>` (cast benigno, wire idéntico).
> - Deuda previa: P1.9 API thin · P1.3 auth full (D4) · consumir `openapi-fetch` en más frentes.
>
> Lee PRIMERO: este traspaso y sus fuentes (`traspaso-f5a-fidelidad-gate-2026-08-12.md`,
> `traspaso-nueva-ola-fin-refactorizacion-2026-08-12.md` §3). NO toques código fuera del alcance de la fase
> que se declare.
