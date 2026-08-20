# RELEVO / TRASPASO — R-9: cierre F1–F7 → apertura F8 (2026-08-20)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT** que debe continuar la refactorización R-9 (abriendo la siguiente fase **F8**). Es el ancla anti-saturación / anti-alucinación de relevo: cualquier agente nuevo **LEE ESTE DOC + `backlog-trabajo-2026-08-20.md` §0/§1 ANTES de tocar nada**.
> **Estado al redactar (verificado):** `local main = origin/main = fa529dd` · working tree limpio · F1–F7 de R-9 cerradas y pusheadas.
> **AsOf:** 2026-08-20 (≈23:05). Motivo del relevo: saturación de contexto del chat (regla E2/E3) tras ejecutar la fase F7 completa.

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** `main` == `origin/main` == `fa529dd`. Árbol limpio (`git status --short` vacío).
- **Últimos commits (`main`, de más nuevo a más antiguo):**

  | Commit    | Contenido                                               |
  | --------- | ------------------------------------------------------- |
  | `fa529dd` | docs: cerrar R-9 F7 (plan + backlog + estado)           |
  | `5d59671` | F7 — suite de concurrencia/invariantes + scripts/verify |
  | `2d2006e` | docs: cerrar R-9 F6 (plan + backlog + estado)           |
  | `e5d8926` | F6 — balance_after postcondición app + corregir docs    |
  | `14585bf` | docs: cerrar R-9 F5 (plan + backlog + estado)           |
  | `ef4c136` | F5 — sesión epoch UTC (`session.py`)                    |
  | `2d39502` | docs: relevo/traspaso cierre F1–F4 + brief apertura F5  |
  | `0800ee9` | docs: registrar cierre F4 (R-9.4) en plan y backlog     |
  | `b384f31` | F4 — DTOs financieros estrictos Pydantic                |
  | `fbfefc7` | docs: registrar cierre F3 (R-9.3) en plan y backlog     |
  | `26f5ca1` | F3 — carrera de custodia idempotente (no 500)           |

- **R-9 F1–F7 COMPLETAS** en `main` (ver §6 para detalle de cada una). La **fase en curso/corta a abrir es F8**.
- Antecedentes cerrados en `main` (no afectan a F8): R-7 y R-8 completas (R-8 = hasta `fb95b27`; CONTRACT-STALE `aecbb28`).

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente (las 3 reglas que no se negocian)

Estas reglas siguen siendo las mismas (premisas **E1–E9** en `docs/PROJECT_PREMISES.md` ⭐§0):

1. **Read-first anti-alucinación:** antes de abrir CUALQUIER fase/subagente, **LEE** `docs/engineering/backlog-trabajo-2026-08-20.md` **§0 y §1**, `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md` (§ de la fase a abrir) y `docs/engineering/PROJECT_STATE.md`. Si el repo no coincide con el backlog/plan → **PARAR y re-leer**; nunca seguir por inercia.
2. **Una fase = un subagente acotado + verificación del coordinador + batería real + aprobación de usuario POR COMMIT + push a `main` (rama protegida, requiere aprobación nativa).** El coordinador **nunca** se fía del reporte de un subagente: contrasta cada diff contra el código real y corre la batería él mismo. Máx. ~3 subagentes en paralelo por chat, con alcances disjuntos.
3. **Anti-alucinación / anti-pérdida:** todo hallazgo del subagente se verifica en el código (file:line). El coordinador inyecta en el brief el **mapa de consumidores ya verificado** para que el subagente no redis cubra call-sites. **Vigilar la saturación del hilo principal:** hacer read-first acotado (greps + bloques, no leer archivos enteros), y si se degrada el contexto, hacer un relevo al cierre de la fase.

### Batería mínima (re-verificada por el coordinador en cada fase)

- **Backend (py):** `uv run ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de los ficheros en gate CI (`uv run mypy <files> --config-file pyproject.toml`, `*> archivo.txt` + leer en Powershell) · pytest de la zona.
- **Git:** `git status` acotado a los ficheros declarados por la fase.
- **Frontend/shared/contract:** SOLO si la fase toca web/shared/OpenAPI. F8 puede tocar web/shared (limpieza) → si toca, aplicar `pnpm --filter @bolsa/web typecheck|lint|test` · `contract:check` (precedido de `$env:PYTHONIOENCODING='utf-8'`) si cambia OpenAPI.

---

## 3. TRABAJO PENDIENTE A CERRAR (nuevo agente)

### 3.1 ▶️ FASE 8 — R-9.8: Limpieza de código/doc obsoletos + DOCSTRINGS + deuda menor (la siguiente)

> **Dentro del plan director** (`plan-r9-refactor-hardening-2026-08-20.md` § FASE 8). Criterio **E8**.

- **Alcance (criterio E8):** eliminar/archivar código y documentos que ya no reflejan la realidad (p. ej. deuda "Alembic baseline pendiente" ya resuelta, helpers muertos), **SOLO** si 0 imports y no dependen de storage por nombre. Rellenar docstrings de símbolos públicos tocados. Depurar documentación que diverge del código (README vs realidad, §1.3).
- **Decisión §5.2 F8 YA DECIDIDA (2026-08-20):** `pending-delete/README.md` de riesgo alto → **Opción A: solo inventariar, NO ejecutar** (hasta decisión explícita de `purge storage`). **NO tocar** esos ítems.
- **Riesgos/aviso:** es una fase **transversal** (puede tocar Python + web + shared). Requiere read-first acotado y subagente(s) con alcances **disjuntos** (por superficie) + mapa de consumidores. Ojo: eliminar solo lo que tenga **0 imports** y no dependa de storage por nombre; verificar con `rg` call-sites. No tocar `pending-delete` riesgo alto ni features.
- **Criterio de aceptación:** battery/typecheck verdes tras limpiar; `git status` acotado; docs actualizadas sin perder evidencia.
- **No hay decisión EXTRA de usuario pendiente para F8** (la única, "solo inventariar", ya está tomada). Salvo que el nuevo agente encuentre un ítem ambiguo → presentar y esperar.

### 3.2 🟡 Ítems de decisión de usuario (NO auto-cerrar — presentar y esperar)

| Ítem                                                                                                                                                                        | Origen   | Regla vigente                                                                                                                           |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Contrato F2/F4:** el `409 IDEMPOTENCY_KEY_REUSED` (F2) NO figura en `openapi.json`/`schema.d.ts` (no se hizo regen). También el contrato F4 (DTOs estrictos) no se regen. | R-9.2/4  | **Pendiente decisión** si exponer el 409 + DTOs estrictos en OpenAPI + `contract:check`. No se ejecutó `contract:gen`.                  |
| **`pending-delete/README.md` riesgo alto**                                                                                                                                  | R-8D     | **NO tocar** hasta decisión de `purge storage`. F8: solo inventariar (decisión tomada).                                                 |
| **R-8C.2 scheduler-vs-worker** y **M-4/T-M4** (job dedicado custodia)                                                                                                       | R-7/R-8C | **Documentadas, NO tocar código** salvo decisión.                                                                                       |
| Fase opcional **F9** (V2: desacoplar `analytics↔market`, puente legacy, import-linter, tipos compartidos a domain)                                                          | R-9 plan | Requiere ADR + decisión explícita. Una por chat, con diseño en el plan + subagente + aprobación por commit. No es la siguiente (va F8). |

### 3.3 🏁 Cierre por fase (obligatorio al terminar cada una)

Al cerrar cada fase: **update-last en `backlog-trabajo-2026-08-20.md`** (§0 relego + §6 historial con commits/batería) **y** `plan-r9-refactor-hardening-2026-08-20.md` (añadir el § "Estado ... IMPLEMENTADO" al pie de la fase). Commit de docs separado del commit de código, ambos con push a `main`.

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-20, ≈23:05): repo `Bolsa_V1`, `main` = `fa529dd`, árbol limpio. **R-9 en curso: F1–F7 completas y pusheadas** (ver §6). El plan director está en `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md` y las premisas E1–E9 en `docs/PROJECT_PREMISES.md` ⭐§0.
> **LEE PRIMERO (obligatorio):** `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1 · `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md` § FASE 8 · `docs/engineering/PROJECT_STATE.md` · este doc (`traspaso-relevo-cierre-r9-f1-f7-apertura-f8-2026-08-20.md`).
> **Tarea inmediata:** abrir **F8 (R-9.8)** — limpieza transversal (criterio E8) según §3.1 de este doc. La decisión §5.2 F8 ("solo inventariar `pending-delete`") YA está tomada. Protocolo: read-first acotado → inventariar lo eliminable (0 imports, sin storage por nombre) → documentar en el plan → lanzar **uno** o más subagentes acotados con alcances **disjuntos** (Python / web / shared) → verificación del coordinador (diff + batería real) → **aprobación del usuario por commit** → push a `main`.
> **NO tocar** (salvo decisión de usuario): `pending-delete` riesgo alto (solo inventariar), regen OpenAPI/`contract:gen` (pendiente decisión F2/F4), scheduler/worker R-8C.2, M-4/T-M4, gobernanza IA, features nuevas, ni migraciones fuera de la fase.

### 4.2 Brief para el SUBAGENTE de FASE 8 (a lanzar cuando el usuario apruebe abrir F8)

> Fase **R-9.8** — limpieza transversal (E8). Repo `main` debería estar limpio y con el inventario de lo eliminable ya documentado en `plan-r9-*`. Alcance por superficie con alcances disjuntos: **eliminar SOLO símbolos/código con 0 imports y sin dependencia de storage por nombre** (verificar con `rg` call-sites, no inferir); rellenar docstrings de símbolos públicos tocados; **NO tocar `pending-delete` riesgo alto** (solo inventariar) ni features. Depurar docs que divergen del código sin perder evidencia. Battery según surface (Python: ruff 0 · mypy gate 0 · pytest zona; web/shared: typecheck 0 · lint 0 · test; si cambia OpenAPI: `contract:check` verde con `PYTHONIOENCODING=utf-8`). `git status` acotado a los ficheros declarados. Devuelve file:line de lo que eliminas/limpias + batería. **NO commits ni push.**

### 4.3 Brief para F9 (opcional, NO es la siguiente)

> **NO abrir F9** aún. Requiere ADR + decisión de usuario sobre arquitectura Python (`analytics ↔ market`, tipos compartidos a `domain`, plan de deprecación del puente `legacy_portfolio_id`). Tras cerrar F8, re-leer el plan y decidir con el usuario si se abre F9 o se cierra R-9.

---

## 5. Enlaces (fuentes de verdad — no inventar estado)

- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md` (§0/§1 · §4 checklist · §6 historial)
- Plan de la R-9: `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md`
- Premisas E1–E9: `docs/PROJECT_PREMISES.md` (⭐§0)
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Índice / registro: `docs/engineering/engineering-index-2026-08-03.md` §5
- Relevo R-9 previo (F1–F4): `docs/engineering/traspaso-relevo-cierre-r9-f1-f4-2026-08-20.md`
- Relevo R-8 previo: `docs/engineering/traspaso-relevo-cierre-r8-auditoria-versiones-2026-08-20.md`

---

## 6. Cierres de la R-9 registrados hasta este relevo

| Fecha         | Hito                                                    | Commits `main`              |
| ------------- | ------------------------------------------------------- | --------------------------- |
| 2026-08-20    | **F1** idempotencia por cuenta+type (R-9.1)             | `fa070ec` (+docs `29f444f`) |
| 2026-08-20    | **F2** 409 idempotency_key con payload distinto (R-9.2) | `31954dd` (+docs `2823eae`) |
| 2026-08-20    | **F3** carrera de custodia idempotente, no 500 (R-9.3)  | `26f5ca1` (+docs `fbfefc7`) |
| 2026-08-20    | **F4** DTOs financieros estrictos (R-9.4)               | `b384f31` (+docs `0800ee9`) |
| 2026-08-20    | **F5** sesión epoch UTC (R-9.5)                         | `ef4c136` (+docs `14585bf`) |
| 2026-08-20    | **F6** balance_after postcondición app (R-9.6)          | `e5d8926` (+docs `2d2006e`) |
| 2026-08-20    | **F7** suite concurrencia/invariantes + scripts/verify  | `5d59671` (+docs `fa529dd`) |
| **siguiente** | **F8** limpieza transversal (R-9.8)                     | _(por abrir — usar §4.2)_   |
