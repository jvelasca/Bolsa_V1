# RELEVO / TRASPASO — R-9: cierre F1–F8 (R-9 COMPLETA) → decisión apertura F9 / cierre R-9 (2026-08-20)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT** que retome el proyecto tras el cierre de la refactorización **R-9**. Es el ancla anti-saturación / anti-alucinación de relevo: cualquier agente nuevo **LEE ESTE DOC + `backlog-trabajo-2026-08-20.md` §0/§1 ANTES de tocar nada**.
> **Estado al redactar (verificado):** `local main = origin/main = 5c557fa` · working tree limpio · **R-9 COMPLETA (F1–F8 cerradas y pusheadas)**.
> **AsOf:** 2026-08-20 (≈23:35).

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** `main` == `origin/main` == `5c557fa`. Árbol limpio (`git status --short` vacío).
- **R-9 COMPLETA:** las 8 fases (F1–F8) están cerradas y pusheadas a `main`. Decisión del propietario (2026-08-20): **CERRAR R-9**; la fase opcional **F9 (V2)** queda **documentada como pendiente de decisión futura** (no se ejecuta ahora).
- **Últimos commits (`main`, de más nuevo a más antiguo) de la R-9:**

  | Commit    | Contenido                                                  |
  | --------- | ---------------------------------------------------------- |
  | `5c557fa` | docs: cerrar R-9 completa + diferir F9/V2 como pendiente   |
  | `c2b3797` | docs: cerrar R-9 F8 (plan + backlog + estado)              |
  | `5ea336f` | F8 — limpieza transversal R-9.8 (E8)                       |
  | `8cd39ad` | docs: inventario F8 + decisiones aprobadas                 |
  | `fe1049b` | docs: relevo R-9 cierre F1–F7 + brief apertura F8          |
  | `fa529dd` | docs: cerrar R-9 F7 (plan + backlog + estado)              |
  | `5d59671` | F7 — suite concurrencia/invariantes + scripts/verify       |
  | `2d2006e` | docs: cerrar R-9 F6 (plan + backlog + estado)              |
  | `e5d8926` | F6 — balance_after postcondición app + corregir docs       |
  | `14585bf` | docs: cerrar R-9 F5 (plan + backlog + estado)              |
  | `ef4c136` | F5 — sesión epoch UTC (`session.py`)                       |
  | `2d39502` | docs: relevo/traspaso R-9 cierre F1–F4 + brief apertura F5 |
  | `0800ee9` | docs: registrar cierre F4 (R-9.4) en plan y backlog        |
  | `b384f31` | F4 — DTOs financieros estrictos (Pydantic fail-fast 422)   |
  | `fbfefc7` | docs: registrar cierre F3 (R-9.3) en plan y backlog        |
  | `26f5ca1` | F3 — carrera de custodia idempotente (no 500)              |
  | `2823eae` | docs: registrar cierre F2 (R-9.2) en plan y backlog        |
  | `31954dd` | F2 — 409 ante idempotency_key con payload distinto         |
  | `29f444f` | docs: premisas E1–E9 + plan R-9 + cierre F1                |
  | `fa070ec` | F1 — idempotencia deposit/withdraw aislada por cuenta+type |

- Antecedentes cerrados en `main` (no afectan a la siguiente decisión): R-7 y R-8 completas (R-8 = hasta `fb95b27`; CONTRACT-STALE `aecbb28`).

> **Punto de decisión (NO es una fase en curso):** la próxima tarea, si el propietario la pide, es **decidir si se abre F9 (V2)** o se deja R-9 cerrado. Detalle en §3.

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente (las 3 reglas que no se negocian) — VIGENTE

Estas reglas siguen siendo las mismas que en los relevos R-7/R-8 (premisas **E1–E9** en `docs/PROJECT_PREMISES.md` ⭐§0):

1. **Read-first anti-alucinación:** antes de abrir CUALQUIER fase/subagente, **LEE** `docs/engineering/backlog-trabajo-2026-08-20.md` **§0 y §1**, `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md` y `docs/engineering/PROJECT_STATE.md`. Si el repo no coincide con el backlog/plan → **PARAR y re-leer**; nunca seguir por inercia.
2. **Una fase = un subagente acotado + verificación del coordinador + batería real + aprobación de usuario POR COMMIT + push a `main` (rama protegida, requiere aprobación nativa).** El coordinador **nunca** se fía del reporte de un subagente: contrasta cada diff contra el código real y corre la batería él mismo. Máx. ~3 subagentes en paralelo por chat, con alcances disjuntos.
3. **Anti-alucinación / anti-pérdida:** todo hallazgo del subagente se verifica en el código (file:line). El coordinador inyecta en el brief el **mapa de consumidores ya verificado**. **Vigilar la saturación del hilo principal:** read-first acotado (greps + bloques, no leer archivos enteros), y si se degrada el contexto, hacer un relevo al cierre de la fase.

### Batería mínima (re-verificada por el coordinador en cada fase)

- **Backend (py):** `uv run ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de los ficheros en gate CI (`uv run mypy <files> --config-file pyproject.toml`, usando `*> archivo.txt` + leer en Powershell) · pytest de la zona.
- **Git:** `git status` acotado a los ficheros declarados por la fase.
- **Frontend/shared/contract:** `pnpm --filter @bolsa/web typecheck|lint|test` · `pnpm --filter @bolsa/shared typecheck|lint|test|build` · `contract:check` (precedido de `$env:PYTHONIOENCODING='utf-8'`) **si cambia OpenAPI**. Precisión: **NO ejecutar `contract:gen`** salvo fase pactada (decisión F2/F4 pendiente, ver §3.2).

---

## 3. PUNTO DE DECISIÓN (nuevo agente) — abrir F9 o cerrar R-9

### 3.1 FASE 9 — (Opcional / V2) Arquitectura Python + puente legacy — **NO AUTO-CERRAR; decidir y esperar**

> **Dentro del plan director** (`plan-r9-refactor-hardening-2026-08-20.md` § FASE 9). **Requisito previo del plan (§3 y §6): ADR + diseño en el plan + decisión explícita del propietario antes de abrir código.** No es la siguiente fase por defecto: la R-9 quedó **CERRADA**.

- **Alcance previsto (más amplio, requiere ADR):**
  - Re-verificar dependencias `analytics ↔ market` y **declarar** en `pyproject.toml` lo realmente usado (tras auditoría read-only; no asumir).
  - Definir direcciones unívocas (`domain ↑ analytics ↑ application ↑ infrastructure ↑ api`) y los tipos compartidos a `domain`.
  - Plan de deprecación del puente `legacy_portfolio_id`.
- **Criterio de aceptación (del plan):** `import-linter` verde; dependencias declaradas; sin ciclo analytics↔market.
- **Recomendación del plan (§5.2):** Opción A — **diferir a V2/otro plan**, no abrir ahora (mayor alcance, colinda con features/freeze). La decisión de cerrar R-9 (tomada 2026-08-20) va en esa dirección.
- **Trabajo de apertura SI se decide:** modo Plan primero (ADR en `docs/adr/` + sección de diseño en `plan-r9-*`) + subagentes de exploración (alcances disjuntos) para inventariar la deuda (`analytics↔market`, dependencias no declaradas, puente legacy) antes de tocar código.

### 3.2 Ítems de decisión de usuario (NO auto-cerrar — presentar y esperar)

| Ítem                                                                                                                                                                                            | Origen   | Regla vigente                                                                                                          |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Contrato F2/F4:** el `409 IDEMPOTENCY_KEY_REUSED` (F2) NO figura en `openapi.json`/`schema.d.ts`; los DTOs estrictos (F4) tampoco se regen.                                                   | R-9.2/4  | **Pendiente decisión** si exponer el 409 + DTOs estrictos en OpenAPI + `contract:check`. No se ejecutó `contract:gen`. |
| **`pending-delete/README.md` riesgo alto** (`readLegacyPendingOrders`, `chartDataStrip`/`chartNewTabSeed`/`newChartConfigSource`, `readLegacyTimeframeFavorites`, re-export `presetRuleGroups`) | R-8D     | **NO tocar** hasta decisión de `purge storage`. F8 solo inventarió.                                                    |
| **R-8C.2 scheduler-vs-worker** y **M-4/T-M4** (job dedicado custodia)                                                                                                                           | R-7/R-8C | **Documentadas, NO tocar código** salvo decisión.                                                                      |
| Fase opcional **F9 (V2)**                                                                                                                                                                       | R-9 plan | Requiere ADR + decisión explícita. No es la siguiente por defecto; R-9 cerrada.                                        |

### 3.3 Estado global alcanzado (no es deuda de la R-9)

- Núcleo financiero determinista cerrado (E7): idempotencia aislada por cuenta+type (F1), 409 primer/segundo uso (F2), carrera de custodia idempotente-no-500 (F3), DTOs financieros estrictos fail-fast 422 (F4), sesión epoch UTC (F5), `balance_after` postcondición app documentada (F6), suite concurrencia/invariantes + verifiers (F7), limpieza transversal E8 (F8).
- Pendientes operativos (checklist manual §4 del backlog, FUERA de repo): activar GitHub secret scanning · `TRUSTED_PROXIES` prod · corregir registro BD `BP/.L` → `BP.L` · limpiar `logs/dev` locales · (opcional) purga de valores dev en historial git.

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-20, ≈23:35): repo `Bolsa_V1`, `main` = `5c557fa`, árbol limpio. **R-9 COMPLETA: F1–F8 cerradas y pusheadas** (ver §6). El plan director está en `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md` y las premisas E1–E9 en `docs/PROJECT_PREMISES.md` ⭐§0.
> **LEE PRIMERO (obligatorio):** `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1 · `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md` § FASE 9 · `docs/engineering/PROJECT_STATE.md` · este doc (`traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md`).
> **Tarea inmediata (decisión, NO fase abierta):** confirmar con el propietario si se **abre F9 (V2)** — arquitectura Python + puente legacy — **o** se mantiene **R-9 cerrado**. NO abrir F9 sin: ADR + diseño en el plan + aprobación explícita. Si se abre: protocolo (read-first → diseño Plan → documentar ADR/plan → subagentes de exploración de alcances disjuntos → verificación del coordinador → aprobación por commit → push a `main`).
> **NO tocar** (salvo decisión de usuario): regen OpenAPI/`contract:gen` (pendiente decisión F2/F4), `pending-delete` riesgo alto, scheduler/worker R-8C.2, M-4/T-M4, gobernanza IA, features nuevas, ni migraciones fuera de la fase.

### 4.2 Brief para los SUBAGENTES de apertura de FASE 9 (solo si el propietario decide abrirla)

> Fase **R-9.9 / V2** — desacoplar `analytics ↔ market` + tipos compartidos a `domain` + plan del puente `legacy_portfolio_id` + declarar dependencias en `pyproject.toml`. Alcances disjuntos (por dir de paquete: `analytics` / `market` / `pyproject`/import-linter). Cada subagente: read-only primero, devuelve inventario de dependencias/imports reales con file:line y el ciclo `analytics↔market` (evidencia, no inferir). Prohibido tocar: workers R-8C.2, `pending-delete`, gobernanza IA, features, contrato. Battery según superficie; `import-linter` como meta-batería una vez diseñado. NO commits ni push; devuelve file:line + evidencia + propuesta de diseño (no implementación) si el alcance lo pide.

### 4.3 Brief para cierre operativo (sin F9)

> Si se decide NO abrir F9: la R-9 queda cerrada; próximos pasos opcionales son los del checklist operativo §4 del backlog (acciones manuales) y/o una decisión sobre el contrato F2/F4. No hay pendientes de código de la R-9.

---

## 5. Enlaces (fuentes de verdad — no inventar estado)

- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md` (§0/§1 · §4 checklist · §6 historial)
- Plan de la R-9: `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md`
- Premisas E1–E9: `docs/PROJECT_PREMISES.md` (⭐§0)
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Índice / registro: `docs/engineering/engineering-index-2026-08-03.md` §5
- Relevo R-9 previo (F1–F4): `docs/engineering/traspaso-relevo-cierre-r9-f1-f4-2026-08-20.md`
- Relevo R-9 previo (F1–F7): `docs/engineering/traspaso-relevo-cierre-r9-f1-f7-apertura-f8-2026-08-20.md`
- Relevo R-8 previo: `docs/engineering/traspaso-relevo-cierre-r8-auditoria-versiones-2026-08-20.md`

---

## 6. Cierres de la R-9 registrados (completos)

| Fecha      | Hito                                                    | Commits `main`                        |
| ---------- | ------------------------------------------------------- | ------------------------------------- |
| 2026-08-20 | **F1** idempotencia por cuenta+type (R-9.1)             | `fa070ec` (+docs `29f444f`)           |
| 2026-08-20 | **F2** 409 idempotency_key con payload distinto (R-9.2) | `31954dd` (+docs `2823eae`)           |
| 2026-08-20 | **F3** carrera de custodia idempotente, no 500 (R-9.3)  | `26f5ca1` (+docs `fbfefc7`)           |
| 2026-08-20 | **F4** DTOs financieros estrictos (R-9.4)               | `b384f31` (+docs `0800ee9`)           |
| 2026-08-20 | **F5** sesión epoch UTC (R-9.5)                         | `ef4c136` (+docs `14585bf`)           |
| 2026-08-20 | **F6** balance_after postcondición app (R-9.6)          | `e5d8926` (+docs `2d2006e`)           |
| 2026-08-20 | **F7** suite concurrencia/invariantes (R-9.7)           | `5d59671` (+docs `fa529dd`)           |
| 2026-08-20 | **F8** limpieza transversal E8 (R-9.8)                  | `5ea336f` (+docs `8cd39ad`/`c2b3797`) |
| 2026-08-20 | **FIN R-9** — decisión cerrar; F9 diferida              | `5c557fa` (docs)                      |
