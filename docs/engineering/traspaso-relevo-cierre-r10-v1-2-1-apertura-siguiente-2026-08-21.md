# RELEVO / TRASPASO — cierre R-10 / v1.2.1 (F1–F5 COMPLETA) → apertura siguiente fase (2026-08-21)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT** que retome el proyecto tras el cierre de **R-10 / v1.2.1**. Es el ancla anti-saturación / anti-alucinación de relevo: cualquier agente nuevo **LEE ESTE DOC + `backlog-trabajo-2026-08-20.md` §0/§1 ANTES de tocar nada**.
> **Estado al redactar (verificado):** `local main = origin/main = 2093296` · working tree limpio · **R-10 COMPLETA (F1–F5 cerradas y pusheadas)** · **v1.2.1 taggeada** (`v1.2.1` sobre `2093296`).
> **AsOf:** 2026-08-21 (≈09:10).

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** `main` == `origin/main` == `2093296`. Árbol limpio (`git status --short` vacío). Cierre de R-10 (`2093296`) **ya pusheado**; tag **`v1.2.1`** sobre ese commit (anotado, sincronizado en `origin`).
- **R-10 COMPLETA:** las 6 correcciones P1/P2 de la **auditoría externa post‑v1.2.0** implementadas, verificadas, aprobadas por commit y pusheadas a `main`. **v1.2.0** (`b28e956`) intacta como baseline auditado. El proyecto sigue **NO en producción** (DEMO/paper).
- **Últimos commits (`main`, de más nuevo a más antiguo):**

  | Commit    | Contenido                                                                                                              |
  | --------- | ---------------------------------------------------------------------------------------------------------------------- |
  | `2093296` | docs: cierre **v1.2.1** (CHANGELOG `[1.2.1]` + docs de estado R-10 COMPLETA + limpieza E8 inventariada) + tag `v1.2.1` |
  | `c84e1e3` | docs: cierre R-10 F3+F4a y apertura F4b (traspaso nuevo; viejo archivado `-obsoleto`)                                  |
  | `e12a125` | **F4b** — custodia fuera del GET → job `RunCustodyJob` (D4/D4.1)                                                       |
  | `5c304e6` | **F4a** — custodia Opción B: tabla `custody_obligation` (PENDING/APPLIED) + `ApplyCustodyFees` (ADR 026)               |
  | `49e2731` | docs(adr): **ADR 026** — custodia Opción B (docs-only)                                                                 |
  | `b79e5dd` | **F3** — `balance_after` trade+fee secuencial por fila, sin backfill (D6)                                              |
  | `2137c53` | docs: cierre R-10 F1+F2a+F2b + apertura F3 (traspaso relevo)                                                           |
  | `86c315a` | **F2b** — comparación idempotente exacta normalizada a 6 decimales (sin tolerancia 0.01)                               |
  | `b4dcc72` | **F2a** — `TaxProfileDto` estricto (Pydantic fail-fast 422)                                                            |
  | `a1501e6` | **F1** — `idempotency_key` OBLIGATORIA en deposit/withdraw/trade (contrato + regen OpenAPI)                            |
  | `4e4a81a` | docs: abrir R-10/v1.2.1 (plan + decisiones de las 6 correcciones)                                                      |

- **Logros clave de R-10:** núcleo financiero endurecido **por** las 6 correcciones; **M-4/T-M4 (job dedicado de custodia) REACTIVADO y CERRADO por F4b** (`e12a125`) — la custodia ya es un job periódico, no muta en GET; `GetAccountSummary`/`GetTaxReport` quedan **100% de solo lectura**.

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente (las 3 reglas que no se negocian) — VIGENTE

> Reglas invariantes (premisas **E1–E9** en `docs/PROJECT_PREMISES.md` ⭐§0 y §4 "Orquestación, relevo de chat y anti-alucinación").

1. **Read-first anti-alucinación:** antes de abrir CUALQUIER fase/subagente, **LEE** `docs/engineering/backlog-trabajo-2026-08-20.md` **§0 y §1**, el plan de la fase (ver §4) y `docs/engineering/PROJECT_STATE.md`. Si el repo no coincide con backlog/plan → **PARAR y re-leer**; nunca seguir por inercia.
2. **Una fase = un subagente acotado + verificación del coordinador + batería real + aprobación de usuario POR COMMIT + push a `main` (rama protegida, requiere aprobación nativa).** El coordinador **nunca** se fía del reporte de un subagente: contrasta cada diff contra el código real y corre la batería él mismo. Máx. ~3 subagentes en paralelo por chat, con alcances **disjuntos** (ficheros distintos). Inyectar en cada brief el **mapa de consumidores ya verificado**.
3. **Anti-alucinación / anti-pérdida y control de saturación:** todo hallazgo del subagente se verifica en código (file:line). **Vigilar la saturación del hilo principal:** read-first acotado (greps + bloques, no leer archivos enteros); si se degrada el contexto, cerrar el hilo y abrir otro pegando el texto de paso de este doc + bloque de estado verificado. Cada relevo incluye **firma de estado** (HEAD, rama, árbol, tags).

### Batería mínima (re-verificada por el coordinador en cada fase)

- **Backend (py):** `ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de los ficheros en gate CI · pytest de la zona.
- **Git:** `git status` acotado a los ficheros declarados por la fase.
- **Frontend/shared/contract:** `pnpm --filter @bolsa/web typecheck|lint|test` · `pnpm --filter @bolsa/shared typecheck|lint|test|build` · `contract:check` **si cambia OpenAPI** (precedido de `$env:PYTHONIOENCODING='utf-8'`). **NO ejecutar `contract:gen`** salvo fase pactada (decisión contrato pendiente, ver §3).
- **Verificación invariante ledger:** `scripts/verify/verify_ledger_balance_chain.py` (puede devolver EXIT 1 solo por fixture dev `acc_broken_72ab7c2aa881`, cuentas de simulación; NO es regresión de fase — ver §3).

---

## 3. Deudas / decisiones de usuario pendientes (NO auto-cerrar — presentar y esperar)

| Ítem                                                                                                                                                                                                                          | Origen         | Regla vigente / estado                                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Contrato F2/F4:** el `409 IDEMPOTENCY_KEY_REUSED` (F2) y los DTOs estrictos (F4) NO figuran en `openapi.json`/`schema.d.ts`; `contract:check` queda ROJO por ese **drift baseline preexistente** (no es regresión de R-10). | R-9 F2/F4      | **Pendiente decisión** si exponer el 409 + DTOs estrictos en OpenAPI + `contract:gen`. No colar en fases sin autorización.                    |
| **`pending-delete/README.md` riesgo alto** (`readLegacyPendingOrders`, `chartDataStrip`/`chartNewTabSeed`/`newChartConfigSource`, `readLegacyTimeframeFavorites`, …)                                                          | R-8D / R-10 E8 | **NO tocar** hasta decisión de `purge storage`. R-10 F5 solo **inventarió** (no borró).                                                       |
| **R-8C.2 scheduler-vs-worker** (coexistencia scheduler no‑ARQ)                                                                                                                                                                | R-7/R-8C       | Documentada; **NO tocar código** salvo decisión. F4b respetó `_queue_loop_starters`/ARQ intactos.                                             |
| **Fixture dev `acc_broken_72ab7c2aa881`** (cuenta de simulación con saldo a medio) → `verify_ledger_balance_chain.py` EXIT 1                                                                                                  | F3             | Deuda de datos dev, NO regresión de fase. Si se quiere `verify` EXIT 0 global: corregir/eliminar esa cuenta de simulación (D6: sin backfill). |
| **Test infra `test_execute_trade_con_fees_reconcilia` roto** (`ExecuteTrade.execute(...)` pide `idempotency_key` tras F1)                                                                                                     | R-10 F1        | Deuda conocida ajena a F3/F4a/F4b/F5. Fichero no reescrito por R-10. Corregible actualizando el test para pasar la key.                       |
| **mypy `accounts.py`:** 7 errores pre‑existentes (líneas ~37,67,105,118,568,861,899) ajenos a R-10                                                                                                                            | pre-R-10       | No introducidos por R-10; no bloquean la batería. No tocar en fases de features sin autorización.                                             |
| **Gobernanza IA** y features nuevas / workers bajo decisión                                                                                                                                                                   | freeze / E7    | NO tocar salvo decisión explícita.                                                                                                            |

> **Punto de decisión (NO es una fase en curso):** R-10 quedó **CERRADA**. La próxima tarea, si el propietario la pide, es **definir la siguiente fase** (no existe fase activa definida). No abrir ninguna sin **plan/decisión aprobada** (E1).

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-21, firma verificada): repo `Bolsa_V1`, `main` = `2093296`, árbol **limpio**, **R-10 / v1.2.1 COMPLETA y CERRADA** (F1 `a1501e6` · F2a `b4dcc72` · F2b `86c315a` · F3 `b79e5dd` · F4a ADR `49e2731`+impl `5c304e6` · F4b `e12a125` · cierre docs `2093296`) — todas pusheadas · **tag `v1.2.1`** sobre `2093296`. **v1.2.0** (`b28e956`) intacta. No hay fase activa en curso.
> **LEE PRIMERO (obligatorio):** este doc (§1–§6) · `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1/§6 · `docs/PROJECT_PREMISES.md` ⭐§0 (E1–E9) y §4 · `docs/engineering/PROJECT_STATE.md` · el plan de la fase según lo que se abra.
> **Tarea inmediata (decisión, NO fase abierta):** confirmar con el propietario **qué fase se abre a continuación** de R-10 (no hay fase predefinida). NO abrir código sin **plan/decisión aprobada** (E1). Los ítems §3 NO son fases; son decisiones de usuario.
> **NO tocar** (salvo decisión): regen OpenAPI/`contract:gen` (contrato F2/F4), `pending-delete` riesgo alto, worker/scheduler R-8C.2, gobernanza IA, features nuevas, migraciones fuera de fase. Si se abre fase con migración Alembic: nuevas versiones van en `alembic/versions/` con cabecera `down_revision` de la `005_custody_obligation` (es decir, siguiente en cadena será `006_*`).

### 4.2 Brief para los SUBAGENTES (patrón de cualquier fase futura)

> Una fase = un subagente acotado con brief explícito: (1) read-first `backlog §0/§1` + premisas E1–E9 + `PROJECT_STATE`; (2) contexto + archivos **exactos** a tocar y **qué NO tocar**; (3) **mapa de consumidores ya verificado** (inyectar, no re-descubrir); (4) batería esperada (ruff/mypy/pytest + verifier si aplica); (5) **NO commits ni push**; (6) reporte con file:line + evidencia reproducible + `git status --short` final. Máx ~3 en paralelo con alcances disjuntos. El coordinador **re-verifica** cada diff/resultado contra el código y corre la batería él mismo antes de proponer commit al propietario (E4).

### 4.3 Brief para cierre de fase (patrón de cualquier cierre)

> Al cerrar una fase: actualizar **backlog §0/§6**, `PROJECT_STATE.md`, `engineering-index` y el `plan-<fase>`; registrar batería y deuda NO regresión; texto de paso con **firma de estado** (HEAD/rama/árbol/tags); commit de docs + commit de código separados; **aprobación del propietario por commit**; push a `main`. Si cierra una **release**: añadir entrada en `CHANGELOG.md`, tag `vX.Y.Z` sobre el commit de cierre y pushar rama+tag.

---

## 5. Enlaces (fuentes de verdad — no inventar estado)

- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md` (§0/§1 · §6 historial)
- Plan de la R-10: `docs/engineering/plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md` (✅ COMPLETADO)
- Premisas E1–E9: `docs/PROJECT_PREMISES.md` (⭐§0 · §4 orquestación)
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Índice / registro: `docs/engineering/engineering-index-2026-08-03.md` §5
- ADR 026 (custodia Opción B): `docs/adr/026-custodia-obligacion-pendiente.md`
- Relevo R-10 previo (cierre F3+F4a → apertura F4b): `docs/engineering/traspaso-relevo-cierre-r10-f3-f4a-apertura-f4b-2026-08-21.md`
- Relevo R-10 previo (cierre F1+F2a+F2b → apertura F3, archivado `-obsoleto`): `docs/engineering/traspaso-relevo-cierre-r10-f1-f2ab-apertura-f3-2026-08-21-obsoleto.md`
- Relevo R-9 de cierre (referencia de estructura, v1.2.0): `docs/engineering/traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md`
- Verificadores invariante: `scripts/verify/verify_ledger_balance_chain.py` · `verify_account_isolation.py`

---

## 6. Cierres de la R-10 registrados (completos)

| Fecha      | Hito                                                                                                     | Commits `main`                        |
| ---------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| 2026-08-21 | **F1** — `idempotency_key` obligatoria (contrato + regen OpenAPI)                                        | `a1501e6` (+docs `2137c53`/`4e4a81a`) |
| 2026-08-21 | **F2a** — `TaxProfileDto` estricto (Pydantic fail-fast 422)                                              | `b4dcc72` (+docs `2137c53`)           |
| 2026-08-21 | **F2b** — idempotencia exacta normalizada a 6 decimales (sin tolerancia 0.01)                            | `86c315a` (+docs `2137c53`)           |
| 2026-08-21 | **F3** — `balance_after` trade+fee secuencial, sin backfill (D6) + reset datos sim dev                   | `b79e5dd` (+docs)                     |
| 2026-08-21 | **F4a** — custodia Opción B: ADR 026 (docs) + tabla `custody_obligation` + repo + `ApplyCustodyFees`     | `49e2731` + `5c304e6`                 |
| 2026-08-21 | **F4b** — custodia fuera del GET → job `RunCustodyJob` (D4) + reactiva M-4/T-M4                          | `e12a125` (+docs `c84e1e3`)           |
| 2026-08-21 | **F5 — CIERRE v1.2.1** — CHANGELOG `[1.2.1]` + docs de estado R-10 COMPLETA + limpieza E8 (inventariado) | `2093296` + tag **`v1.2.1`**          |
