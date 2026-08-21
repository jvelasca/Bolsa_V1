# RELEVO / TRASPASO — cierre R-11 hardening (C1–C6 + D1 + D2) → apertura siguiente (2026-08-21)

> **⚠️ HISTÓRICO — NO es el relevo vivo.** Cierre de R-11 / release `v1.3.0`. Los SHA incrustados (`870fb21`, `deafa27`) **no son HEAD**. Fuente viva: `PROJECT_STATE.md` · backlog §0 · `traspaso-relevo-r12-apertura-2026-08-21.md`. Coordinación: GitHub `origin/main` (`git fetch && git rev-parse origin/main`).
>
> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Propósito (archivo):** registro del cierre R-11 para auditoría; **no** usarlo como texto de paso de un chat nuevo.
> **Estado al redactar (histórico):** `local main = origin/main = 870fb21` en la apertura de este doc; release posterior `v1.3.0` tag `b778292`.
> **AsOf:** 2026-08-21.
>
> **>>> ACTUALIZADO (cierre de release 2026-08-21, tarde):** R-11 se RELEASA como **`v1.3.0`** — tag anotado sobre `b778292` (padre `deafa27` = fix `test_execute_trade_con_fees_reconcilia` + delete dev `acc_broken_72ab7c2aa881` → `verify_ledger_balance_chain.py` EXIT 0). Ver §3/§6. Este doc queda como referencial-histórico; el estado VIVO es `PROJECT_STATE.md` y `backlog §0/§1`.

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** `main` == `origin/main` == `870fb21`. Árbol limpio (`git status --short` vacío). Todos los commits de R-11 **ya pusheados** a `origin/main`.
- **R-11 COMPLETA:** las fases C1–C6 (hallazgos P1/P2 de la **auditoría externa sobre v1.2.1**) + D1 (limpieza E8) + D2 (cierre documental) implementadas, verificadas, **aprobadas por commit** y pusheadas a `main`. El proyecto sigue **NO en producción** (DEMO/paper).
- **Últimos commits (`main`, de más nuevo a más antiguo):**

  | Commit    | Contenido                                                                                                                       |
  | --------- | ------------------------------------------------------------------------------------------------------------------------------- |
  | `870fb21` | **D1** — quitar métodos de custodia muertos (`get_by_account` + `get_by_account_period`, criterio E8)                           |
  | `db95709` | **C6+D2** — cierre documental: ADR 026 `custody_charge_source=DEFAULT_PORTFOLIO` + estado C1–C5 (docs only)                     |
  | `6762614` | **C5** — mypy == 0 gate CI (+`packages/py/application/src`) + limpieza 105 errores en 33 ficheros                               |
  | `157bb45` | **C4** — `contract:check` EXIT 0 (regen acotada `openapi.json`, Opción A)                                                       |
  | `cda26e9` | **C3** — precisión Decimal end-to-end en `ExecuteTrade.execute`                                                                 |
  | `17a1107` | **C2** — endurecer `idempotency_key` end-to-end (DTO 16–128 + strip, repo obligatoria no vacía)                                 |
  | `c3327c1` | **C1** — custodia **multi-periodo** (PK `id` + `UNIQUE(account_id, period)`, migración `006`, liquidar PENDING antiguo primero) |
  | `1ae93f9` | docs: plan R-11 hardening tras auditoría v1.2.1 (apertura)                                                                      |

- **C1–C6 cronología:** `1ae93f9` (plan) → `c3327c1` (C1) → `17a1107` (C2) → `cda26e9` (C3) → `157bb45` (C4) → `6762614` (C5) → `db95709` (C6+D2 docs) → `870fb21` (D1). El **plan director** (`docs/engineering/plan-r11-hardening-auditoria-v1-2-1-2026-08-21.md`) está **cerrado en todas sus fases**.
- **Logros clave de R-11:** el núcleo financiero P1+P2 de la auditoría queda corregido (custodia multi-periodo con liquidación del PENDING más antiguo; `idempotency_key` validada end-to-end; precisión Decimal sin `Decimal→float→Decimal` en notional); la deuda de **calidad/CI** se cierra (mypy 0 con la capa `application` en gate; `contract:check` EXIT 0); se documenta la política de carga de custodia (**`DEFAULT_PORTFOLIO`**, ADR 026); y se hace una **limpieza transversal E8** (D1) sin tocar ningún ítem RIESGO ALTO.

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente (las 3 reglas que no se negocian) — VIGENTE

> Reglas invariantes (premisas **E1–E9** en `docs/PROJECT_PREMISES.md` ⭐§0 y §4 "Orquestación, relevo de chat y anti-alucinación").

1. **Read-first anti-alucinación:** antes de abrir CUALQUIER fase/subagente, **LEE** `docs/engineering/backlog-trabajo-2026-08-20.md` **§0 y §1**, el plan de la fase (ver §4) y `docs/engineering/PROJECT_STATE.md`. Si el repo no coincide con backlog/plan → **PARAR y re-leer**; nunca seguir por inercia.
2. **Una fase = un subagente acotado + verificación del coordinador + batería real + aprobación de usuario POR COMMIT + push a `main` (rama protegida, requiere aprobación nativa).** El coordinador **nunca** se fía del reporte de un subagente: contrasta cada diff contra el código real y corre la batería él mismo. Máx. ~3 subagentes en paralelo por chat, con alcances **disjuntos** (ficheros distintos). Inyectar en cada brief el **mapa de consumidores ya verificado**.
3. **Anti-alucinación / anti-pérdida y control de saturación:** todo hallazgo del subagente se verifica en código (file:line). **Vigilar la saturación del hilo principal:** read-first acotado (greps + bloques, no leer archivos enteros); si se degrada el contexto, cerrar el hilo y abrir otro pegando el texto de paso de este doc + bloque de estado verificado. Cada relevo incluye **firma de estado** (HEAD, rama, árbol, tags).

### Batería mínima (re-verificada por el coordinador en cada fase)

- **Backend (py):** `ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de los ficheros en gate CI (incluye **`packages/py/application/src`** desde C5) · pytest de la zona.
- **Git:** `git status` acotado a los ficheros declarados por la fase.
- **Frontend/shared/contract:** `pnpm --filter @bolsa/web typecheck|lint|test` · `pnpm --filter @bolsa/shared typecheck|lint|test|build` · `contract:check` **si cambia OpenAPI** (precedido de `$env:PYTHONIOENCODING='utf-8'`). **NO ejecutar `contract:gen`** salvo fase pactada (ver §3).
- **Verificación invariante ledger:** `scripts/verify/verify_ledger_balance_chain.py` → **EXIT 0 global** desde `v1.3.0` (2026-08-21, cuenta `acc_broken_72ab7c2aa881` eliminada por path canónico).

---

## 3. Deudas / decisiones de usuario pendientes (NO auto-cerrar — presentar y esperar)

| Ítem                                                                                                                                                                                            | Origen                   | Regla vigente / estado                                                                                                                                                                                                                                                 |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Tag de release R-11** (p.ej. `v1.3.0`)                                                                                                                                                        | cierre R-11              | **PENDIENTE decisión del propietario → resuelta: ✅ release `v1.3.0` (2026-08-21), tag anotado sobre `deafa27`, cierre en §6.**                                                                                                                                        |
| **`pending-delete/README.md` riesgo alto** (`readLegacyPendingOrders`, `chartDataStrip`/`chartNewTabSeed`/`newChartConfigSource`, `readLegacyTimeframeFavorites`, re-export `presetRuleGroups`) | R-8D / R-10 E8 / R-11 D1 | **NO tocar** hasta decisión de `purge storage`. R-11 D1 solo **borró** lo que cumplía E8 completo (`get_by_account`/`get_by_account_period` del repo custodia); el resto sigue **inventariado y no borrable** (persistencia/migración/repunte de imports fuera de D1). |
| **Contrato F2/F4 (residual):** el `409 IDEMPOTENCY_KEY_REUSED` sigue solo en runtime (handler global), **NO** en `openapi.json`/`schema.d.ts`.                                                  | R-9 F2/F4 / R-11 C4      | `contract:check` está **EXIT 0** (R-11 C4, Opción A: regen acotada sin exponer el 409). La opción de exponer el 409 en OpenAPI sigue **pendiente de decisión** del propietario.                                                                                        |
| **R-8C.2 scheduler-vs-worker** (coexistencia scheduler no‑ARQ)                                                                                                                                  | R-7/R-8C                 | Documentada; **NO tocar código** salvo decisión.                                                                                                                                                                                                                       |
| **Fixture dev `acc_broken_72ab7c2aa881`** (cuenta de simulación con saldo a medio) → `verify_ledger_balance_chain.py` EXIT 1                                                                    | F3                       | ✅ **CERRADA (2026-08-21, `v1.3.0`)** — cuenta de simulación huérfana "R8C broken" eliminada por path canónico `close_account`→`delete_simulated_account` (D6 prohíbe backfill); `verify_ledger_balance_chain.py` **EXIT 0** global.                                   |
| **Test infra `test_execute_trade_con_fees_reconcilia` roto** (`ExecuteTrade.execute(...)` pide `idempotency_key` tras F1/C2)                                                                    | R-10 F1                  | ✅ **CERRADA (2026-08-21, `deafa27`, `v1.3.0`)** — test corregido añadiendo `idempotency_key=f"trade-{uuid4().hex[:8]}"`; batería coordinador `test_m2` 7 passed 1 xfailed.                                                                                            |
| **Gobernanza IA** y features nuevas / workers bajo decisión                                                                                                                                     | freeze / E7              | NO tocar salvo decisión explícita.                                                                                                                                                                                                                                     |

### Aparcado de R-11 (§4 del plan — fuera de este ciclo, candidatos próximos)

| Ítem aparcado                    | Contenido                                                                                                                                             |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unificación Research→Radar**   | COnsolidar las próximas UX tras lo ya hecho en R-9 (ver `docs/engineering/research-radar-unification-2026-07-31.md`).                                 |
| **Puente legacy↔nuevo (V2/ADR)** | Decidir el modelo de migración de workspaces/storage legacy a nuevo esquema (paso previo al `purge storage` que desbloquearía los ítems riesgo alto). |
| **Auditoría de caos financiero** | Propuesta tras C1–C5; ampliar verificaciones de invariante más allá de `balance_after`/ledger.                                                        |
| **scheduler-vs-worker (R-8C.2)** | Ya citado en deudas §3.                                                                                                                               |
| **Semver real de packages**      | Estandarizar versionado de `packages/*`; ligado a la decisión de tag de release R-11.                                                                 |

> **Punto de decisión (NO es una fase en curso):** R-11 quedó **CERRADA**. La próxima tarea, si el propietario la pide, es **definir la siguiente fase** entre los aparcados/§3 o una release tag `v1.3.0`. No abrir ninguna sin **plan/decisión aprobada** (E1).

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-21, firma verificada): repo `Bolsa_V1`, `main` = `870fb21`, árbol **limpio**, **R-11 (hardening post-v1.2.1) COMPLETA y CERRADA** (C1 `c3327c1` · C2 `17a1107` · C3 `cda26e9` · C4 `157bb45` · C5 `6762614` · C6+D2 `db95709` · D1 `870fb21`) — todas pusheadas · **último tag de release sin cambio: `v1.2.1`** sobre `2093296` (decidir si se taggea R-11, p.ej. `v1.3.0`). No hay fase activa en curso.
> **LEE PRIMERO (obligatorio):** este doc (§1–§6) · `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1/§6 · `docs/PROJECT_PREMISES.md` ⭐§0 (E1–E9) y §4 · `docs/engineering/PROJECT_STATE.md` · el plan de la fase según lo que se abra.
> **Tarea inmediata (decisión, NO fase abierta):** confirmar con el propietario **qué se abre a continuación** de R-11. Candidatos: (a) tag de release `v1.3.0` + cierre; (b) alguno del **aparcado §4** (unificación Research→Radar, auditoría de caos financiero, puente legacy V2, semver packages); (c) deuda §3 (corregir `test_execute_trade_con_fees_reconcilia`, fixture dev `acc_broken`). NO abrir código sin **plan/decisión aprobada** (E1).
> **NO tocar** (salvo decisión): regen OpenAPI/`contract:gen` (contrato F2/F4 residual), `pending-delete` riesgo alto, worker/scheduler R-8C.2, gobernanza IA, features nuevas. Si se abre fase con migración Alembic: nuevas versiones encadenan sobre **`006_custody_obligations_period`** (la actual) — siguiente será `007_*`.

### 4.2 Brief para los SUBAGENTES (patrón de cualquier fase futura)

> Una fase = un subagente acotado con brief explícito: (1) read-first `backlog §0/§1` + premisas E1–E9 + `PROJECT_STATE`; (2) contexto + archivos **exactos** a tocar y **qué NO tocar**; (3) **mapa de consumidores ya verificado** (inyectar, no re-descubrir); (4) batería esperada (ruff/mypy/pytest + verifier si aplica); (5) **NO commits ni push**; (6) reporte con file:line + evidencia reproducible + `git status --short` final. Máx ~3 en paralelo con alcances disjuntos. El coordinador **re-verifica** cada diff/resultado contra el código y corre la batería él mismo antes de proponer commit al propietario (E4).

### 4.3 Brief para cierre de fase (patrón de cualquier cierre)

> Al cerrar una fase: actualizar **backlog §0/§6**, `PROJECT_STATE.md`, `engineering-index` y el `plan-<fase>`; registrar batería y deuda NO regresión; texto de paso con **firma de estado** (HEAD/rama/árbol/tags); commit de docs + commit de código separados; **aprobación del propietario por commit**; push a `main`. Si cierra una **release**: añadir entrada en `CHANGELOG.md`, tag `vX.Y.Z` sobre el commit de cierre y pushar rama+tag.

---

## 5. Enlaces (fuentes de verdad — no inventar estado)

- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md` (§0/§1 · §6 historial)
- Plan de la R-11: `docs/engineering/plan-r11-hardening-auditoria-v1-2-1-2026-08-21.md` (✅ CERRADO en todas las fases)
- Premisas E1–E9: `docs/PROJECT_PREMISES.md` (⭐§0 · §4 orquestación)
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Índice / registro: `docs/engineering/engineering-index-2026-08-03.md` §5
- ADR 026 (custodia multi-periodo + política `DEFAULT_PORTFOLIO`): `docs/adr/026-custodia-obligacion-pendiente.md`
- Inventario obsoleto no-borrable (riesgo alto): `docs/engineering/pending-delete/README.md`
- Relevo R-10 previo (cierre R-10/v1.2.1 → apertura siguiente): `docs/engineering/traspaso-relevo-cierre-r10-v1-2-1-apertura-siguiente-2026-08-21.md`
- Relevo R-9 de cierre (referencia de estructura): `docs/engineering/traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md`
- Verificadores invariante: `scripts/verify/verify_ledger_balance_chain.py` · `verify_account_isolation.py`

---

## 6. Cierres de la R-11 registrados (completos)

| Fecha      | Hito                                                                                                                                                      | Commits `main`              |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| 2026-08-21 | **C1** — custodia multi-periodo: PK `id` + `UNIQUE(account_id, period)`, migración `006`, liquidar PENDING antiguo primero                                | `c3327c1` (+plan `1ae93f9`) |
| 2026-08-21 | **C2** — `idempotency_key` end-to-end (DTO 16–128 + strip, repo obligatoria no vacía, guard uuid4)                                                        | `17a1107`                   |
| 2026-08-21 | **C3** — precisión Decimal en `ExecuteTrade.execute` (float solo en borde repo/ledger)                                                                    | `cda26e9`                   |
| 2026-08-21 | **C4** — `contract:check` EXIT 0 (Opción A: regen acotada `openapi.json`; 409 sigue solo runtime)                                                         | `157bb45`                   |
| 2026-08-21 | **C5** — mypy == 0 gate CI (+`packages/py/application/src`) + limpieza 105 errores en 33 ficheros                                                         | `6762614`                   |
| 2026-08-21 | **C6** — política `custody_charge_source = DEFAULT_PORTFOLIO` documentada (ADR 026, solo docs)                                                            | `db95709` (con D2)          |
| 2026-08-21 | **D1** — limpieza E8: quitar `get_by_account` + `get_by_account_period` muertos del repo custodia (+fakes test)                                           | `870fb21`                   |
| 2026-08-21 | **D2** — cierre documental C6+D2 (PROJECT_STATE/backlog/plan/index/ADR 026/CHANGELOG + docstrings)                                                        | `db95709`                   |
| 2026-08-21 | **RELEASE `v1.3.0`** — tag anotado sobre `deafa27` + CHANGELOG `[1.3.0]` + cierre deuda §3 (fix test `deafa27` + delete dev `acc_broken` → verify EXIT 0) | `deafa27` (tag `v1.3.0`)    |

> **R-11 RELEASED como `v1.3.0`** (2026-08-21) sobre `deafa27`. Último tag release previo: **`v1.2.1`** sobre `2093296`.
