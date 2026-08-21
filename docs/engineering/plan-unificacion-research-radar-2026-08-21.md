# PLAN — Unificación Research → Radar (embudo científico→operativo) — (draft)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`, rama del traspaso R-11 → aparcado «Unificación Research→Radar»).
> **Propósito:** plan director (read-only, **draft**) para consolidar la superficie UX Research→Radar: unificar puente y navegación entre el hub científico `/research` (`features/research`) y el hub operativo `/screeners` (`features/screeners`, nav **Rastreadores**), reutilizando el puente B0 `promote-finalist-to-tracker.ts` ya implementado y el embudo backend/shared ya consolidado. Sin features nuevas (freeze E7).
> **Estado:** **APARCADO / DRAFT — pendiente de decisión y aprobación del propietario para abrir.** Ninguna fase está abierta ni cerrada. NO abrir código hasta decisión (E1).
> **AsOf:** 2026-08-21.
> **Nota de estado vivo:** R-11 ya se **RELEASEó como `v1.3.0`** (2026-08-21): HEAD `main` = `b778292`, tag anotado `v1.3.0` sobre el cierre de R-11 (`deafa27`). Árbol de trabajo **limpio (`git status --short` vacío)**.

---

## 0. Contexto y foco (qué es y qué NO es)

- **Qué unifica:** capa de **navegación y superficie** que hoy separa el observatorio científico/Asesor (`/research`, `features/research`) del screener→rastreador/Radar (`/screeners`, `features/screeners`). El **contrato de datos y el puente B0 ya existen y están consolidados**; este plan trabaja presentación/navegación y, solo donde haga falta, cableado de consumidores.
- **Qué NO toca (freeze):**
  - **Ninguna feature nueva** (E7). No se añade pantalla, motor ni flujo que no exista.
  - **Gobernanza IA NO se toca** (`ai_governance`, botón IA informativo, Belief/Discovery). `research-page.tsx:176-177` ya documenta «Sin Belief ni Discovery Score».
  - **`pending-delete` riesgo alto NO se toca** (`pending-delete/README.md`; R-11 D1 solo borró lo que cumplía E8 completo).
  - **R-8C.2 (scheduler-vs-worker) NO se toca**; se documenta, no se modifica.
  - **NO `contract:gen` salvo decisión explícita.** Toda fase declara batería sin regen de contrato (D5: `openapi.json`/`schema.d.ts` sin diff). Si una fase detectara necesidad de regen → **parar y elevar al propietario**.
- **Aceptación general:** unificación = **inyectar reutilización de lo ya consolidado**; **no re-descubrir ni duplicar**. Cada fase entrega ficheros exactos, batería, mapa de consumidores y criterio de «hecho».

---

## 1. Diseño — qué se unifica y qué queda separado

### 1.1 Unificar (superficie + navegación)

| Ítem                           | Hoy                                                                                                                                                                                                                                              | Unificación propuesta                                                                                                                         |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Nav Radar                      | `NavLink /screeners` etiqueta **«Rastreadores»** + badge screener (`app-top-bar.tsx:420-444`; icono `Radar` en `:35`/`:434`).                                                                                                                    | Mantener hub `screeners` como destino del Radar; alinear copy y deep-links para que el puente B0 desemboque de forma consistente en esta hub. |
| Nav Research                   | `RESEARCH_MENU` (`app-top-bar.tsx:274-279`): Resumen/Diario/Historial/Opiniones → `/research?tab=…`, activo por `isResearchRoute` (`:284`).                                                                                                      | Conservar `/research` como **superficie científica/Asesor**. Unificación = **puente/copy**, no fusión de páginas.                             |
| CTA Finalistas→Rastreador (B0) | Helpers en `features/backtests/promote-finalist-to-tracker.ts` (`:1-6`), consumidos por `use-activate-instrument-tracking.ts:11`, `instrument-strategy-top-panel.tsx:36`, `instruments-page.tsx:82`; test `promote-finalist-to-tracker.test.ts`. | Trazar y **garantizar un único call-path** de promoción; documentar mapa de consumidores (inyectar, no re-descubrir).                         |
| Embudo backend/shared          | Ya consolidado (§3.2).                                                                                                                                                                                                                           | **No se re-implementa.** Solo se consume/cablea contra el contrato existente.                                                                 |

### 1.2 NO se toca (límites firmes)

- **Motor científico** (backend): `research_trials`, `research_tree`, `research_evidence`, research→knowledge/hypotheses. No se altera lógica ni API.
- **Motor de escaneo/trackers** (backend): `scans`, `scan_jobs`, `scans/manifests`, `trackers`, `tracker_schedule`, `tracker_alarms`. No se mueve lógica.
- **Persistencia/workspaces/storage**: no se toca `workspace-store-*` ni el modelo `UI_PREFS_LOCALSTORAGE`.
- **Contrato OpenAPI / types shared ya en su sitio**: `tracker-definitions.ts`, `scan-api.ts`, `scan-manifests.ts`, `research-trials-api.ts`, `research-platform.ts`. Sin `regen_full` / sin `contract:gen`.

---

## 2. Inventario de superficie (file:line — solo lo relevante)

### 2.1 FE — rutas y menús

- **Router** `apps/web/src/app.tsx`: `{ path: "research", element: <ResearchPage /> }` (`:76`) · `{ path: "screeners", element: <ScreenersPage /> }` (`:78`).
- **Nav** `apps/web/src/components/layout/app-top-bar.tsx`:
  - `RESEARCH_MENU` (`:274-279`) · `isResearchRoute` (`:284`).
  - NavLink Radar/Rastreadores → `/screeners` (`:420-432`), `Radar` (`:434`), `«Rastreadores»` (`:435`), badge `${screenerNavBadge} rastreos` (`:436-443`); fuente `useScreenerNavBadge` (`:49`).
  - `useAsesorAlarmaBadge` (`:50`), pin dictamen (`:410-418`).
- **Hub Research** `apps/web/src/features/research/research-page.tsx`: `ResearchPage()` (`:52`), `Asesor` (`:172`), «Ruta `/research` (API sin cambios). Sin Belief ni Discovery Score» (`:174-178`).
- **Hub Radar** `apps/web/src/features/screeners/screeners-page.tsx`: `ScreenersPage()` (`:4`), `Rastreadores` (`:9`), `ScreenersHub` (`:2`,`:25`); layout `screeners-hub.tsx`/`screener-hub-layout.tsx` + sub-paneles (`scan-results-table`, `scan-jobs-panel`, `trackers-panel`, `tracker-alarms.ts`/,test.ts`, `execution-policies-panel`, `position-policies-panel`, `paper-d-propose-panel`, `open-hit-in-trading`…).

### 2.2 FE — puente B0 (Finalista → Rastreador)

- `apps/web/src/features/backtests/promote-finalist-to-tracker.ts` (`:1-6`; `@see docs/engineering/research-radar-unification-2026-07-31.md`).
- **Consumidores (mapa a inyectar):** `promote-finalist-to-tracker.test.ts` (`:26`) · `instruments/use-activate-instrument-tracking.ts` (`:11`) · `backtests/instrument-strategy-top-panel.tsx` (`:36`) · `instruments/instruments-page.tsx` (`:82` `screenersHrefAfterTrackerCreate`).
- **Shared usados por el puente** (`@bolsa/shared`, `tracker-definitions.ts`): `CreateTrackerDefinitionDto`, `InstrumentStrategyTopSlotV1`, `KernelTimeframe`, `ExecutionMode`, `TrackerScheduleKind`, `isKernelTimeframe` (import en `promote-finalist-to-tracker.ts:8-15`).

### 2.3 Backend/shared — embudo YA consolidado (referencia, no trabajo)

- **Application (py)** `packages/py/application/src/bolsa_application/`: `scans.py`, `scan_jobs.py`, `scan_universe.py`, `scan_manifests.py`, `trackers.py`, `tracker_schedule.py`, `tracker_alarms.py`, `research_trials.py`, `research_tree.py`, `research_evidence.py`.
- **API** `apps/api-python/...`:
  - `routes/trackers.py`: `:72 GET /trackers`, `:82 /trackers/schedules/evaluate`, `:121 POST /trackers`, `:149 PATCH`, `:186 DELETE`, `:197 POST /trackers/{id}/scan`, `:212 POST /trackers/{id}/scan-jobs`.
  - `routes/scans.py`: `:51 POST /scans/run`, `:91 POST /scans/jobs`, `:105 GET /scans/jobs`, `:114 GET /scans/manifests/{scan_id}`, `:126 GET /scans/jobs/{job_id}`.
  - `routes/research.py`: trials (`:116`,`:161`,`:173`), hypotheses (`:219`,`:242`,`:298`,…), knowledge (`:380`,`:406`,…), tree (`:491`), evidence (`:583`,`:633`), summary (`:645`), lab-health (`:667`).
  - `schemas/: trackers.py`, `scans.py`, `research.py`.
- **Shared types FE** `packages/shared/src/`: `tracker-definitions.ts`, `scan-api.ts`, `scan-manifests.ts`, `research-trials-api.ts`, `research-platform.ts`.

> El embudo **no es objeto de trabajo** de esta unificación; es la fuente del contrato que los hubs FE ya consumen. Cada fase lo **inyecta** para evitar re-descubrimiento.

---

## 3. Descomposición en fases acotadas (una por subagente — alcances disjuntos)

> Regla transversal: **una fase = un subagente** · verificación del coordinador · batería real · **NO commits ni push hasta aprobación del propietario por commit** · máx. ~3 en paralelo con **ficheros disjuntos**. Estado de cada fase: **pendiente de decisión/aprobación del propietario para abrir** (ninguna marcada como cerrada).

### Fase 1 — Trazado e inyección del mapa de consumidores B0 (→ plantilla documental + guard estático)

- **Objetivo:** confirmar/actualizar la **única fuente** §2.2 (mapa real por call-site de `promote-finalist-to-tracker.ts`) y opcionalmente añadir JSDoc `@see` de trazabilidad en los consumidores instrumentales si se pacta (cambio mín.).
- **Ficheros exactos a tocar (candidatos):** `docs/engineering/plan-unificacion-research-radar-2026-08-21.md` (§2.2) · (solo si se pacta) `apps/web/src/features/instruments/use-activate-instrument-tracking.ts` (JSDoc) · `apps/web/src/features/instruments/instruments-page.tsx` (JSDoc).
- **Qué NO tocar:** lógica del puente; `backtests/*`; `screeners/*`; `research/*`; contrato.
- **Batería esperada:** web `pnpm --filter @bolsa/web typecheck|lint|test` · shared `pnpm --filter @bolsa/shared typecheck|lint|test|build`. **Sin `contract:gen`.** Python solo si aplica (esta fase es FE/docs ⇒ no).
- **Mapa consumidores (inyectar):** `use-activate-instrument-tracking.ts:11` · `instrument-strategy-top-panel.tsx:36` · `instruments-page.tsx:82` · `promote-finalist-to-tracker.test.ts`.
- **Criterio «hecho»:** §2.2 espeja 1:1 los imports reales; JSDoc (si aplica) compila; batería verde; **cero** cambios de comportamiento.

### Fase 2 — Copy y deep-link de Radar coherentes con el puente (superficie `screeners`)

- **Objetivo:** auditar que el destino del CTA Finalista→Tracker (`screenersHrefAfterTrackerCreate`, `instruments-page.tsx:82`) y la nav Radar (`app-top-bar.tsx:420-435`) sean coherentes en copy/ruta; alinear micro-copy de `screeners-page.tsx`/`screeners-hub.tsx` al concepto Radar.
- **Ficheros exactos a tocar (candidatos — verificar en apertura):** `apps/web/src/features/screeners/screeners-page.tsx` · `apps/web/src/features/screeners/screeners-hub.tsx` · (solo si hay divergencia de constante) `apps/web/src/features/backtests/promote-finalist-to-tracker.ts` (expone `screenersHrefAfterTrackerCreate`).
- **Qué NO tocar:** lógica scan/trackers; `research/*`; lógica `tracker-alarms.ts`; contrato.
- **Batería esperada:** web `typecheck|lint|test` · shared `typecheck|lint|test|build`. **Sin `contract:gen`.** Python no aplica (FE-only).
- **Mapa consumidores (inyectar):** `screeners-page.tsx:1-30` · `screeners-hub.tsx` · consumidor del deep-link `screenersHrefAfterTrackerCreate` (`instruments-page.tsx:82`).
- **Criterio «hecho»:** nav y deep-link devuelven a la misma hub Radar con label coherente; batería verde; sin cambio de wire.

### Fase 3 — Documentación de contorno de freeze y trazabilidad del puente

- **Objetivo:** trazado del aparcado en docs de ingeniería: registrar la fase/estado en `PROJECT_STATE.md`, enlazarlo desde `engineering-index-2026-08-03.md` §1, y confirmar que `research-radar-unification-2026-07-31.md` §3/§4 (B0 ✅, B1 ✅) es la referencia viva. **Docs only.**
- **Ficheros exactos a tocar (docs only):** `docs/engineering/PROJECT_STATE.md` · `docs/engineering/engineering-index-2026-08-03.md` (§1 `Product / Ops`) · `docs/engineering/research-radar-unification-2026-07-31.md` (nota de estado, si procede). **Sin tocar código.**
- **Qué NO tocar:** código; `CHANGELOG.md` (solo si hay release, no en esta fase); `contract:gen`.
- **Batería esperada:** ninguna de código (docs only); validar referencias/estado por el coordinador. Python no aplica.
- **Criterio «hecho»:** el aparcado del traspaso R-11 apunta a este plan; índice enlaza; sin cambios de código.

---

## 4. Riesgos y deudas

| Riesgo / deuda                                                                          | Mitigación en el plan                                                                                         |
| --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Freeze / features nuevas (E7)** — tentación de crear un hub único o fusionar páginas. | Diseño §1 mantiene **dos hubs separados** (científico vs operativo); se unifica **puente/copy**, no páginas.  |
| **Gobernanza IA tocada al mover copy de Research.**                                     | Límite firme `research-page.tsx:174-178`; Fase 3 docs-only; ninguna fase abre `research/*` lógica.            |
| **`contract:gen` no autorizado** rompe D5.                                              | Toda batería declara **sin `contract:gen`**; necesidad detectada → **parar y elevar**.                        |
| **`pending-delete` riesgo alto removido.**                                              | NO se toca; sigue inventariado en `pending-delete/README.md`.                                                 |
| **R-8C.2 scheduler-vs-worker aludido.**                                                 | Se referencia, no se toca código.                                                                             |
| **Re-descubrimiento / duplicación del puente B0.**                                      | Fase 1 inyecta mapa de consumidores verificado, no re-implementa.                                             |
| **Copy divergente (Rastreadores vs Radar).**                                            | Fase 2 acota copy a `screeners-page.tsx`/`screeners-hub.tsx` y al constate `screenersHrefAfterTrackerCreate`. |
| **Docs desalineadas con el estado vivo (R-11 released v1.3.0).**                        | Cabecera/cuerpo declaran AsOf 2026-08-21 + nota `v1.3.0`/`b778292`; Fase 3 actualiza índice/PROJECT_STATE.    |

---

## 5. Texto de paso corto para inyectar en cada subagente futuro

> **CONTEXTO (2026-08-21):** repo `Bolsa_V1`, `main` limpio, HEAD `= b778292`, **R-11 RELEASEado como `v1.3.0`**. El plan `docs/engineering/plan-unificacion-research-radar-2026-08-21.md` está **APARCADO/draft** — fase **pendiente de decisión/aprobación del propietario para abrir**; prohibido abrir código sin aprobación (E1).
> **LEE PRIMERO:** this doc (§0–§4) · `docs/PROJECT_PREMISES.md` ⭐§0 (E1–E9) y §4 · `docs/engineering/PROJECT_STATE.md` · `docs/engineering/research-radar-unification-2026-07-31.md` (B0 ✅).
> **Alcance de TU fase:** copia la sección correspondiente (§3, Fase N) y ciñete a sus **ficheros exactos**; usa el **mapa de consumidores ya verificado** (§2.2 — inyéctalo, NO re-descubras). Respeta límites firmes §1.2.
> **Batería esperada:** web `pnpm --filter @bolsa/web typecheck|lint|test` · shared `pnpm --filter @bolsa/shared typecheck|lint|test|build` · python solo si aplica (mayoría FE-only ⇒ no). **NO `contract:gen`.**
> **Entrega:** NO commits ni push; reporte con file:line real + evidencia reproducible + `git status --short` final. El coordinador re-verificará (E4).

---

## 6. Enlaces (fuentes de verdad)

- R-11 / traspaso activo: `docs/engineering/traspaso-relevo-cierre-r11-c1-c6-d1-d2-siguiente-2026-08-21.md`.
- Contrato de producto unificación: `docs/engineering/research-radar-unification-2026-07-31.md`.
- Premisas E1–E9 y freeze: `docs/PROJECT_PREMISES.md` (⭐§0 · §4) · `docs/engineering/post-audit-decision-freeze-2026-08-03.md`.
- Estado vivo: `docs/engineering/PROJECT_STATE.md` · backlog: `docs/engineering/backlog-trabajo-2026-08-20.md`.
- Riesgo alto no-borrable: `docs/engineering/pending-delete/README.md`.
- Índice: `docs/engineering/engineering-index-2026-08-03.md`.

---

> **Estado formal:** **DRAFT / APARCADO.** Ninguna fase está abierta ni cerrada. Unificación pendiente de **decisión explícita del propietario** para abrir la primera fase (E1). Hasta entonces no se modifica ningún fichero de código.
