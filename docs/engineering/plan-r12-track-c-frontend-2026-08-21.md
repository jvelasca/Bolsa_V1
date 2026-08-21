# PLAN R-12 Track C — Mesa 5 puertas (frontend acotado)

> **Padre:** `docs/engineering/plan-r12-auditoria-ux-2026-08-21.md` §4.
> **Hipótesis aprobada:** `docs/engineering/estudio-flujo-semi-vs-tops-2026-08-21.md` (propietario, 2026-08-21, línea a línea).
> **Premisas:** `docs/PROJECT_PREMISES.md` ⭐§0 · E1–E9. Una fase = un subagente. 0 commits sin OK.
> **Estado:** plan **aprobado** (propietario, 2026-08-21). **C1** `5bc51ff` · **C2** `01af9ff` · **C3 en este commit** (local). Siguiente: C4. C5 no abierta.
> **AsOf:** 2026-08-21 · coordinación GitHub `origin/main`.

---

## 0. Anti-alucinación

Track B **no** autoriza un rediseño libre. Autoriza hacer obvio el oficio ya existente:

> La app propone; yo firmo; el libro cuadra.

**Cero features nuevas.** Reordenar superficie, copy y primer nivel de Confirm. El motor SEMI, la cola F3, el ledger y `PAPER_D_EXECUTE=off` no cambian.

### NO tocar (todas las fases C)

- Núcleo financiero / `ExecuteTrade` `cash_before` / `accounts.py` split
- Gobernanza IA (LLM, Belief, `ai_governance`)
- `PAPER_D_EXECUTE` (flag, API, thaw Camino D)
- `contract:gen` / OpenAPI / DTOs shared
- `pending-delete` riesgo alto
- scheduler-vs-worker (R-8C.2)
- Split de `backtests-page.tsx` (~4513 LOC) — higiene, no mesa diaria
- Fusión de páginas `/research` + `/screeners` (plan Research→Radar sigue **APARCADO**; aquí solo copy/nav)

---

## 1. Evidencia de partida (file:line)

| Pieza                 | Hoy                                                                                                                                                              | Dónde                                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Confirm no es ruta    | `app.tsx` hijos: trading, overview, instruments, backtests, research, screeners, alerts, accounts, operations, history, fiscal, settings. **No hay `/confirm`.** | `apps/web/src/app.tsx:57-90`                                                                          |
| Confirm vive en Ayuda | `openHelpAiPlatform({ panel: "supervised-f3" })` dispara `bolsa:open-help`                                                                                       | `supervised-f3-queue-store.ts:169-181`                                                                |
| Call-sites → Ayuda    | Scan, Operativa, gráfico, Finalistas, alarmas, Asesor, threads, backtests                                                                                        | p.ej. `scan-results-panel.tsx:204,254` · `trading-operativa-panel.tsx:237,459`                        |
| Panel vivo            | `SupervisedF3Panel` ancla `#supervised-f3-panel`                                                                                                                 | `features/settings/supervised-f3-panel.tsx`                                                           |
| Nav principal         | Overview · Trading · Cuentas · Alertas · Instrumentos + menú Backtesting + menú Asesor + **Rastreadores**                                                        | `app-top-bar.tsx:243-444`                                                                             |
| Libro                 | Rutas `/operations` y `/history`; **no están en nav principal**                                                                                                  | `operations-page.tsx` · `history-page.tsx` · HELP `app-help-menu.tsx:134-138`                         |
| AUTO                  | Pill visible, `DEMO_BOOK_AUTO_UI_ENABLED = false`; prefs fuerzan `auto→semi`; execute congelado                                                                  | `demo-book-auto-copy.ts:9` · `demo-book-prefs.ts:66-68` · status bar `trading-status-bar.tsx:160-173` |
| Lista AUTO (Lab)      | Keep-alive en `PlatformShell`; **no es** modo AUTO de cuenta                                                                                                     | `platform-shell.tsx` · `list-auto-activity-store.ts`                                                  |

---

## 2. Mesa objetivo (copy trader)

| Puerta        | Ruta / superficie                                                               | Fase      |
| ------------- | ------------------------------------------------------------------------------- | --------- |
| **Universo**  | Estudio en `/trading` (membresía ADR-024). Copy, no página nueva.               | C2 (copy) |
| **Señales**   | `/screeners` (hoy «Rastreadores»). Asesor (`/research`) pasa a menú secundario. | C2        |
| **Dictamen**  | Columna Operativa en gráfico. **No se mueve.**                                  | —         |
| **Confirmar** | Nueva ruta `/confirm` + ítem de nav con badge de cola.                          | **C1**    |
| **Libro**     | Nav «Libro» → `/operations` + `/history` (dropdown; no fusionar páginas).       | C4        |
| Laboratorio   | Backtesting sale del grupo diario; label «Laboratorio».                         | C2        |
| AUTO cuenta   | Ocultar o «No disponible (BETA)». No thaw.                                      | C3        |

Frase SEMI (UI): _«La app propone operaciones sobre tu Universo. Tú las firmas aquí. Nunca se envían solas.»_

---

## 3. Fases (orden fijo; una = un subagente)

### C1 — Confirmar de primer nivel (recomendado primero)

**Estado:** **hecha en este commit** (2026-08-21). Push a GitHub pendiente de OK.

**Qué:** Confirm deja de ser un rincón de Ayuda.

1. Página delgada `apps/web/src/features/confirm/confirm-page.tsx` que **reutiliza** `SupervisedF3Panel` (no reescribir la cola).
2. Ruta `{ path: "confirm", element: <ConfirmPage /> }` en `app.tsx`.
3. Nav **Confirmar** en `app-top-bar.tsx` (junto al grupo diario), badge = `useSupervisedF3QueueStore` → `items.length` (copy aria: «Pendientes de firma»).
4. `openHelpAiPlatform({ panel: "supervised-f3" })` navega a `/confirm` (SPA). Implementación: evento `bolsa:navigate` `{ to: "/confirm" }` escuchado en `PlatformShell` con `useNavigate` — **no** `window.location` (rompería keep-alive). El resto de `openHelpAiPlatform()` (sin panel F3) sigue abriendo Ayuda.
5. CTA visibles: dejar de decir «Ayuda → Plataforma IA» donde el destino sea firmar (`scan-results-panel.tsx`, `trading-operativa-panel.tsx` como mínimo).
6. Ayuda → Plataforma IA **no se borra** en C1 (red de seguridad); C5 alinea HELP.

**NO en C1:** unificar nav 5 puertas · ocultar AUTO · split backtests · mover el fichero `supervised-f3-panel.tsx` de carpeta (opcional E8 posterior).

**Archivos típicos:** `app.tsx` · `confirm-page.tsx` (nuevo) · `app-top-bar.tsx` · `supervised-f3-queue-store.ts` + test · `platform-shell.tsx` · `lib/routes.ts` si hace falta fill-hub · 2 CTA · test ruta/badge/navegación · JSDoc.

**Batería:** `pnpm` typecheck zona web · vitest `supervised-f3*` + nuevos tests confirm/nav · lint 0 · `git diff` sin `openapi.json`/`schema.d.ts`.

**Hecho cuando:** desde Trading, «Proponer» / cola F3 aterriza en `/confirm`; el ítem Confirmar muestra el número de pendientes; Ayuda genérica (sin panel F3) no se rompe.

---

### C2 — Nav diaria vs laboratorio

**Estado:** **hecha** `01af9ff` (2026-08-21, local; push pendiente). C1 SHA `5bc51ff`.

**Depende de C1** (mismo `app-top-bar.tsx`; no paralelo).

Grupo **diario** (visible): Trading · Señales (`/screeners`, hoy Rastreadores) · Confirmar · (Libro lo pone C4 si aún no existe).

Grupo **laboratorio / tesis** (menú, no primer nivel): Backtesting relabel **Laboratorio** · Asesor (`RESEARCH_MENU`) como capa de tesis.

Copy Estudio en mesa: «Universo en vigilancia» donde hoy diga solo jerga de membresía (sin cambiar API `estudio`).

**NO:** fusionar `research-page` + `screeners-page`. Deep-link B0 Finalistas→Rastreador se conserva.

**Batería:** vitest si hay helper de labels; typecheck; grep de «Rastreadores» en nav.

---

### C3 — AUTO de cuenta no disponible (BETA)

**Estado:** **hecha en este commit** (2026-08-21). C1 `5bc51ff` · C2 `01af9ff` (local; push pendiente).

**Disjunto de C1** (ficheros `demo-book-*` + status bar). Puede ir **en paralelo con C1** si el propietario lo pide.

- Pill AUTO: no seleccionable; texto fijo «AUTO · No disponible (BETA)» (`data-testid="demo-book-auto-unavailable"`). `DEMO_BOOK_AUTO_UI_ENABLED=false`.
- Status bar: no presentar Auto como modo operativo armable.
- Copy sin `PAPER_D_EXECUTE` en la mesa diaria (el flag sigue en HELP/ops).
- **No** tocar API, kill switch servidor, ni `DEMO_BOOK_AUTO_UI_ENABLED=true`.

**NO confundir** con Lista AUTO del Lab (`list-auto-activity-store`) — esa se queda.

**Archivos típicos:** `demo-book-auto-copy.ts` + tests · `demo-book-mode-panel.tsx` · `trading-status-bar.tsx` · tests prefs/arm ya existentes.

---

### C4 — Libro en nav

Dropdown **Libro**: Operaciones (`/operations`) · Historial / ledger (`/history`). No fusionar páginas. Copy de cabecera alineado a «Libro».

**Archivos:** `app-top-bar.tsx` (tras C2) · títulos `operations-page.tsx` / `history-page.tsx` · tests de labels si aplica.

---

### C5 — HELP + frase SEMI

Sincronizar `docs/HELP.md` + `app-help-menu.tsx` + `help-registry.ts`: Confirm es primer nivel; AUTO BETA; frase SEMI en mesa/Cuentas. Tracker Plataforma IA apunta a `/confirm`.

---

## 4. Fuera de Track C (explícito)

| Ítem                                                           | Por qué                                        |
| -------------------------------------------------------------- | ---------------------------------------------- |
| Split `backtests-page.tsx`                                     | Higiene M5; no desbloquea las 5 puertas        |
| Unificación Research→Radar código                              | Plan aparcado; capítulo del estudio, no fase C |
| Tag `v1.4.0` / `v1.5.0-beta`                                   | Solo si el propietario lo pide                 |
| Gates R-12 (409, EXEC-B-CONC, scheduler, split accounts, auth) | Siguen en decisión; otro track                 |

---

## 5. Versionado

Producto **BETA**. Tag `v1.3.0` → `b778292` intacto. Track C **no** tagea solo. Plan R-12 §6: C sería `v1.5.0-beta` **si** el propietario pide tag.

---

## 6. Texto de paso (tras aprobar este plan)

> Track B APROBADO. Plan C: `plan-r12-track-c-frontend-2026-08-21.md`. **C1** `5bc51ff` · **C2** `01af9ff` · **C3 en este commit.** Siguiente: C4 Libro. NO split backtests · NO fusionar research/radar · NO `PAPER_D_EXECUTE`.
