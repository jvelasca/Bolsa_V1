# RELEVO / TRASPASO — cierre R-13 consolidación BETA → apertura siguiente (2026-08-22)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT** tras el cierre de **R-13**. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2ad + premisas ⭐§0 **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch && git rev-parse origin/main` (no asumir SHA de este fichero).
> **Estado al redactar (verificado):** `local main = origin/main = 84ca970` · working tree limpio · **R-13 COMPLETA (A0–A3 cerradas y pusheadas)** · tag **`v1.6.0-beta` → `c3964fc`** · tag **`v1.5.0-beta` → `5e52bd6`** · tag **`v1.3.0` → `b778292`** intactos · **R-12 CERRADA** · **no hay ciclo activo predefinido**.
> **AsOf:** 2026-08-22.

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** `main` == `origin/main` == `84ca970`. Árbol limpio. Todos los commits de R-13 **ya pusheados**.
- **R-13 COMPLETA:** fases A0–A3 implementadas, verificadas, aprobadas por commit y pusheadas. Track B producto **permanece BLOQUEADO** (no formaba parte del cierre de R-13).
- **Últimos commits R-13 (`main`, de más nuevo a más antiguo):**

  | Commit    | Contenido                                                                                              |
  | --------- | ------------------------------------------------------------------------------------------------------ |
  | `84ca970` | docs: stamp cierre A3; alineación estado R-13                                                          |
  | `c3964fc` | **A0–A2 + A3 tag** — apertura R-13, inventario A1, purge `normalizeChartNewTabSeed`, tag `v1.6.0-beta` |
  | `5edbcb5` | docs: stamp post F7c/scan/cron (partida histórica R-12 → R-13)                                         |

- **Serie R-13:** A0 cierre + firma → A1 inventario residual (plan §4 file:line) → A2 E8 micro + tests (`chart-new-tab-setup.test.ts`; purge `normalizeChartNewTabSeed`) → **A3 tag `v1.6.0-beta` = `c3964fc`**.
- **Herencia R-12 (no repetir):** Track A+B `48cc255` · Track C C1–C5 + leftover + copy E8 · R12-409 · EXEC-B-CONC · R12-SCHED · R12-ACCOUNTS · R12-AUTH F1–F10 + F8b–F8e · F7b apply **local** (103→0) · F7c · JWT-only · `scan.completed` + cron stamp · purge V2 T+0 19/19 (E8 N).

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente — VIGENTE

> Premisas **E1–E9** en `docs/PROJECT_PREMISES.md` ⭐§0 y §4.

1. **Read-first:** backlog §0/§1 · `PROJECT_STATE.md` · plan de la fase que se abra. Si el repo no coincide → **PARAR**.
2. **Una fase = un subagente acotado + verificación del coordinador + batería + aprobación por commit + push `main`.**
3. **Anti-saturación:** relevo con texto de paso firmado si el hilo se degrada.

### Batería mínima

- **Backend:** `ruff check packages/py apps/api-python` → 0 · mypy gate CI · pytest zona.
- **Frontend/shared:** `pnpm --filter @bolsa/web typecheck|lint|test` · `pnpm --filter @bolsa/shared typecheck|lint|test|build` · `contract:check` si cambia OpenAPI.
- **Verificadores:** `scripts/verify/verify_ledger_balance_chain.py` (EXIT 0 en dev limpio).

---

## 3. Deudas / decisiones pendientes (NO auto-cerrar)

| Ítem                 | Origen            | Regla / estado                                                                                           |
| -------------------- | ----------------- | -------------------------------------------------------------------------------------------------------- |
| **Track B producto** | R-13 plan §2      | **BLOQUEADO** — god-page / Research→Radar / split `backtests-page`. Plan propio + OK línea a línea (E1). |
| **Purge storage V2** | R-12/R-13 A1 §4.3 | **MONITOR** 4–8 semanas · T+0 19/19 · E8 **N** (sin purge).                                              |
| **Apply F7b prod**   | R-12 F7b          | Solo ventana mantenimiento + URL explícita. Local `bolsa_v1` ya aplicado (103→0 NULL).                   |
| **Ops manuales**     | ops-r1            | `TRUSTED_PROXIES` prod · secret scanning UI · `BP/.L`→`BP.L` en BD · `logs/dev`.                         |
| **Gobernanza IA**    | freeze E7         | NO tocar salvo decisión.                                                                                 |
| **`contract:gen`**   | freeze            | NO salvo fase pactada.                                                                                   |
| **Motor money**      | freeze            | NO tocar (`ExecuteTrade`, custodia apply).                                                               |

### Candidatos próximos (aparcado — requieren decisión del propietario)

| Candidato                       | Plan / evidencia                                                 |
| ------------------------------- | ---------------------------------------------------------------- |
| Unificación Research→Radar      | `plan-unificacion-research-radar-2026-08-21.md` (DRAFT/APARCADO) |
| Split `backtests-page.tsx`      | ~4698 LOC · Track B                                              |
| R-9 F9 analytics↔market         | `plan-r9` + traspaso R-9 F9                                      |
| Auditoría externa estado global | `audit-pack-estado-global-2026-08-20.md` (actualizar)            |
| Modo monitor puro               | Purge V2 + ops checklist, sin commits de código                  |

> **Punto de decisión:** R-13 quedó **CERRADA**. La próxima tarea requiere **definir el siguiente ciclo** (p. ej. Track B, auditoría, monitor). No abrir código sin plan/decisión aprobada (E1).

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-22, firma verificada): repo `Bolsa_V1`, `main` = `84ca970`, árbol **limpio**, **R-13 COMPLETA y CERRADA** (A0–A3: `c3964fc` + docs `84ca970`) · tag **`v1.6.0-beta` → `c3964fc`** · tag **`v1.5.0-beta` → `5e52bd6`** · tag **`v1.3.0` → `b778292`**. **R-12 CERRADA.** **No hay ciclo activo predefinido.**
> **LEE PRIMERO:** este doc (§1–§5) · `docs/engineering/backlog-trabajo-2026-08-20.md` §0 · `docs/PROJECT_PREMISES.md` ⭐§0 · `docs/engineering/PROJECT_STATE.md` §2ad.
> **Tarea inmediata (decisión, NO fase abierta):** confirmar con el propietario **qué ciclo se abre** (Track B producto · auditoría externa · monitor purge/ops · otro). NO abrir código sin plan/decisión (E1).
> **NO tocar:** purge storage alto · gobernanza IA · motor money · apply F7b prod · `contract:gen` salvo fase · Track B sin plan aprobado.

### 4.2 Brief subagentes (patrón)

> Una fase = subagente acotado: read-first backlog §0 + premisas E1–E9 + archivos exactos + qué NO tocar + mapa consumidores + batería esperada + **NO commits ni push** + reporte file:line. Coordinador re-verifica antes de proponer commit.

---

## 5. Enlaces (fuentes de verdad)

- Backlog: `docs/engineering/backlog-trabajo-2026-08-20.md` (§0 · §6)
- Plan R-13: `docs/engineering/plan-r13-consolidacion-beta-2026-08-22.md` (✅ CERRADO)
- Premisas: `docs/PROJECT_PREMISES.md` ⭐§0
- Estado vivo: `docs/engineering/PROJECT_STATE.md` §2ad
- Índice: `docs/engineering/engineering-index-2026-08-03.md` §5
- Relevo R-13 apertura (histórico): `traspaso-relevo-r13-apertura-2026-08-22.md`
- Relevo R-12 (histórico): `traspaso-relevo-r12-apertura-2026-08-21.md`
- Pending-delete alto: `docs/engineering/pending-delete/README.md`
- Ops: `docs/engineering/ops-r1-seguridad-operaciones-2026-08-19.md`

---

## 6. Cierres R-13 registrados

| Fecha      | Hito                                 | Commits / tag                                |
| ---------- | ------------------------------------ | -------------------------------------------- |
| 2026-08-22 | **A0** cierre + firma R-13           | `c3964fc` (con A1/A2)                        |
| 2026-08-22 | **A1** inventario residual (plan §4) | `c3964fc`                                    |
| 2026-08-22 | **A2** E8 micro + tests              | `c3964fc` (purge `normalizeChartNewTabSeed`) |
| 2026-08-22 | **A3** tag **`v1.6.0-beta`**         | tag → `c3964fc`                              |
| 2026-08-22 | **Cierre documental R-13**           | docs post-A3 + este traspaso                 |

> Track B producto **no cerrado** — permanece **BLOQUEADO** para ciclo futuro con plan propio.
