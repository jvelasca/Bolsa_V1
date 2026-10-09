# Entrega a auditoría externa (MIA) — reorden de la FASE 3 (`docs-only` · `Δ motor = 0`)

> **Fecha:** 2026-10-08 (S1–S3 implementados 2026-10-09) · **Producto:** `V2.88.94-beta` (base) → **`V2.88.95-beta`** (sello de `S1`–`S3`) · **Package:** `2.11.94-beta` (base) → **`2.11.95-beta`** · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base auditada:** `1a2ce597` (commit de `main` en el momento de la auditoría; sobre el sello [`v2.88.94-beta`](./evidence/v2.88.94/README.md) → commit `20fd538c`). El rango `20fd538c → 1a2ce597` es **solo documentación** (`packages/py/**` sin mover) ⇒ el **código auditado sigue siendo el de `v2.88.94-beta`**.
> **Continuación (2026-10-09):** los slices `S1`–`S3` se **implementaron** en [`704c4547`](https://github.com/jvelasca/Bolsa_V1/commit/704c4547) (`apps/web/**` + `packages/shared/**`, `Δ motor = 0`) y se **sellaron** como **`v2.88.95-beta`** / `2.11.95-beta` (ver [entrega MIA `v2.88.95`](./entrega-auditoria-externa-mia-v2.88.95-2026-10-09.md)); `S4` **no lanzado**. Ver §4.bis.
> **Unidad de esta entrega:** **documentar** las prioridades de producto del propietario (`P1`–`P4`), **reordenar** la FASE 3 (parkear el motor con dueño y disparador) y **auditar read-only** los tres pilares reales (entrada/salida · estrategia/indicadores · DÍA-D) con hallazgos falsables, para que el auditor decida **antes** de que se lancen los slices.
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente o `UNKNOWN` se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde. `ranking ≠ decisión` y `propuesta ≠ posición materializada` se conservan.
> **`Δ motor = 0`.** Todo el diff es **documentación** en `docs/**`: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin `packages/py/**`, sin bump**. **El contrato HTTP NO cambia.**
> **Nota de auditabilidad (declarada).** Al ser un cambio **solo de documentación**, **no** hay tag de release ni `Release tag CI` propio para esta entrega. La evidencia de motor que respalda es la del sello base: `Release tag CI` [`37823112083`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37823112083) **VERDE** (`replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).
> **Punto de entrada:** [`arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`](./arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md).
> **Dictamen del auditor (2026-10-08):** [`respuesta-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`](./respuesta-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md) — auditoría **ACEPTADA**; `S1`–`S3` aceptados; `S4` reformulado.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el reorden de la FASE 3 hacia las prioridades de producto:

1. **Premisas de producto (`P1`–`P4`).** `PROJECT_PREMISES.md` gana **§6** (operativa ganadora en rango diario · claridad del punto de entrada y salida · estrategia confirmada con los mejores indicadores · evaluación DÍA-D), enlazada desde el índice **§0**. Fija **qué es prioritario**; no sustituye a §5 (que gobierna *cómo se mide* AUTO/PAPER). Invariante preservado: separación estricta SIM/dinero real XTB (§6.2).
2. **Reorden declarado.** El [plan de cierre de motor](./plan-cierre-operativa-auto-2026-10-08.md) queda **PARKED** con **dueño** (propietario) y **disparador** (que un pilar `P1`–`P4` exija decisión durable de cartera o materialización de posición). La [auditoría FASE 2](./auditoria-operativa-auto-fase-2-2026-10-08.md) **§8** anota el reorden y mantiene `F2-1`…`F2-4` como deuda declarada.
3. **Auditoría read-only de los tres pilares** ([documento](./auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md)). **12 hallazgos falsables** (`P2-*`/`P3-*`/`P4-*`) con evidencia `file:line`, veredictos **CUMPLE PARCIAL** por pilar, y **4 slices** derivados **definidos y no ejecutados**.
4. **Arranque del auditor** ([documento](./arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md)). Prompt copiable + orden de lectura + qué comprobar + qué falsaría el OK.

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`).
- **NO** se toca `packages/py/**`.
- **NO** se ejecuta ningún slice de mejora: `S1`–`S4` se **definen**, no se implementan.
- **NO** se re-mide DÍA-D ni se emite `CONFIRMED` (fuera de alcance).
- **NO** hay tag de release para esta entrega (es premisa/auditoría).
- **NO** se cierran las deudas estructurales: `F2-1`…`F2-4`, `PortfolioDecision` durable, materialización SIM, PIT histórico institucional y Execution Analysis.

---

## 2. Cambios verificables (documento por documento)

| # | Tensión de origen | Cambio | Fichero(s) |
| --- | --- | --- | --- |
| 1 | Las prioridades del propietario no estaban formuladas como premisa | **`§6` (`P1`–`P4`)** + enlace desde `§0` + `AsOf` de §6 | [`docs/PROJECT_PREMISES.md`](../PROJECT_PREMISES.md) |
| 2 | La FASE 3 de motor se leía como vigente | **`ESTADO: PARKED`** con dueño y disparador | [`plan-cierre-operativa-auto-2026-10-08.md`](./plan-cierre-operativa-auto-2026-10-08.md) |
| 3 | La auditoría FASE 2 no declaraba el reorden | **§8** reescrito: deuda declarada + puntero a la nueva auditoría | [`auditoria-operativa-auto-fase-2-2026-10-08.md`](./auditoria-operativa-auto-fase-2-2026-10-08.md) |
| 4 | No existía auditoría de los 3 pilares reales | **Auditoría read-only** con 12 hallazgos `file:line` + 4 slices | [`auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`](./auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md) |
| 5 | El auditor no tenía punto de entrada para este ciclo | **Arranque del auditor** (prompt + orden + qué falsaría) | [`arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`](./arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md) |

**Diff del ciclo (solo documentación):**
```bash
git diff --stat 20fd538c 1a2ce597
# docs/** (premisas, auditorías, arranque, entrega MIA, CHANGELOG, CURRENT_SYSTEM)
# Δ motor = 0: git diff --name-only 20fd538c 1a2ce597 -- packages/py   # vacío
```

---

## 3. Medición

- **Motor:** sin cambio esperado. La evidencia del sello base sigue `REPRODUCIDO` (`1E3ADAC2…`) ⇒ **`Δ motor = 0`**.
- **Contrato/esquema:** head Alembic `052_top3_opportunities` sin mover; sin `contract:gen`.
- **Tests:** no aplica cambio de código; no se re-ejecutan baterías por un diff documental.
- **`Δ motor = 0`:** `git diff --name-only 20fd538c 1a2ce597 -- packages/py` → **vacío**.

---

## 4. Hallazgos abiertos (declarados, con remediación)

> Salen de la auditoría de los tres pilares. Los que tienen slice asociado se **mitigan** con `S1`–`S3` (implementados en `704c4547`); **no** se re-auditan aquí. `P4`/`F2` siguen abiertos.

| ID | Pilar | Gap declarado | Remediación | Estado |
| --- | --- | --- | --- | --- |
| `P2-2` | Entrada/salida | El `ExitPlan` del ticket **no** declara precio de salida por peldaño. | Slice `S1-exit-precio`. | **MITIGADO** `704c4547` |
| `P2-3` | Entrada/salida | En `focus simple` + `prepared` la línea «Entrada» no se dibuja (se usa `Trigger`). | Slice `S2-entrada-literal`. | **MITIGADO** `704c4547` |
| `P2-4` | Entrada/salida | Con Journey activo, T1/T2 quedan en `sr-only`. | Diseño de primer nivel (fuera de `S1`–`S3`). | **ABIERTO** |
| `P3-1`/`P3-3`/`P3-4` | Estrategia/indicadores | Los indicadores detectados y las `reasons` **no** se muestran en primer nivel. | Slice `S3-indicadores-razon`. | **MITIGADO** `704c4547` |
| `P4-2` | DÍA-D | `CONFIRMED` está **reservado** y **no se emite**; el lado ejecutado queda `NOT_MEASURED`. | Slice `S4-agregador-evidencia` (read-only) **sin** emitir `CONFIRMED`. | **NO LANZADO** |
| `P4-3` | DÍA-D | La medición es por **artefacto CLI**, no en vivo. | Diseño, no código, en este ciclo. | **ABIERTO** |
| `P4-4` | DÍA-D | Veredicto **fragmentado** en tres superficies. | Slice `S4-agregador-evidencia`. | **NO LANZADO** |
| — | Doc ↔ código | **§5 de `PROJECT_PREMISES.md` describe un veredicto `CONFIRMED` que el código no emite** (el gate usa `READY`/`INCONCLUSIVE`). | **Resuelto**: `§5.2` realineada a la jerarquía de 4 capas (VENTANA · RECONCILIACIÓN · EVIDENCIA OOS · EVIDENCIA PAPER); `CONFIRMED` reservado. Ver [respuesta del auditor](./respuesta-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md). | **RESUELTO** |
| `F2-1`…`F2-4` | FASE 2 | Completitud contable: `PortfolioDecision` durable, posición por operación, P&L agregado, motivo de ranking por ciclo. | **Deuda PARKED**; solo si `P1`–`P4` lo exige. | **PARKED** |

---

## 4.bis Slices `S1`–`S3` (implementados)

| Slice | Commit | Alcance | Gate |
| --- | --- | --- | --- |
| `S1-exit-precio` | [`704c4547`](https://github.com/jvelasca/Bolsa_V1/commit/704c4547) | `f3-exit-plan-block.tsx` + `propose-position-exit.ts` (T1/T2 de `position.operational.target*`) | `Δ motor = 0` |
| `S2-entrada-literal` | [`704c4547`](https://github.com/jvelasca/Bolsa_V1/commit/704c4547) | `operational-plan-chart-levels.ts` (`Entrada`≠`Trigger`, sin duplicar) | `Δ motor = 0` |
| `S3-indicadores-razon` | [`704c4547`](https://github.com/jvelasca/Bolsa_V1/commit/704c4547) | `instrument-strategy-top-panel.tsx` + `strategy-top1-chart-indicators.ts` + `coach-facts-api.ts` (persistir `reasons`) | `Δ motor = 0` |

Verificación: `typecheck` web **OK** · `vitest run` web **281 ficheros / 1750 passed** · `packages/shared` build **OK** · `S4` **no lanzado**.

---

## 5. Gates

| Gate | Resultado |
| --- | --- |
| `git diff --name-only 20fd538c 1a2ce597 -- packages/py` | **vacío** ⇒ `Δ motor = 0` |
| Cambio de contrato HTTP (`contract:gen`) | **sin cambio** |
| Migraciones Alembic | **sin migración nueva** (head `052_top3_opportunities`) |
| `Release tag CI` (sello base `v2.88.94-beta`) | [`37823112083`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37823112083) **VERDE** (`replay-repro` `REPRODUCIDO` `1E3ADAC2…`) |
| `Tag de release de **esta** entrega** | **no aplica** a `1a2ce597` (docs-only) |
| **Slices `S1`–`S3` (implementación)** [`704c4547`](https://github.com/jvelasca/Bolsa_V1/commit/704c4547) | `typecheck` web **OK** · `vitest` web **281 ficheros / 1750 passed** · `packages/shared` build **OK** · **`Δ motor = 0`** (`git diff --name-only -- packages/py` **vacío**) |

---

## 6. Sello

- **Producto:** `V2.88.94-beta` (sin cambio). **Package:** `2.11.94-beta` (sin bump). **Sin migración.** **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `docs/engineering/auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`, `docs/engineering/arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`, este documento.
- **Modificados:** `docs/PROJECT_PREMISES.md`, `docs/engineering/auditoria-operativa-auto-fase-2-2026-10-08.md`, `docs/engineering/plan-cierre-operativa-auto-2026-10-08.md`.
- **Base auditada:** `1a2ce597` (`main` en el momento de la auditoría); rango `20fd538c → 1a2ce597` **solo documentación**.
- **Tag:** **no aplica** (entrega documental sin bump); la evidencia de motor es la del sello `v2.88.94-beta`.

---

## 7. Guion de auditoría desde GitHub

1. **Punto de entrada.** Abrir [`arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`](./arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md) y usar su **prompt**.
2. **Premisas.** Leer [`PROJECT_PREMISES.md`](../PROJECT_PREMISES.md) **§0 + §6** y contrastarlas con **§5**.
3. **Entregable.** Leer la [auditoría diaria](./auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md): §1–§3 evidencia, §4 hallazgos, §5 slices.
4. **Reorden.** Leer [auditoría FASE 2 §8](./auditoria-operativa-auto-fase-2-2026-10-08.md) y el [plan PARKED](./plan-cierre-operativa-auto-2026-10-08.md).
5. **`Δ motor = 0`.** Verificar que el diff del ciclo **no toca** `packages/py/**`:
   ```bash
   git diff --name-only 20fd538c 1a2ce597 -- packages/py   # vacío
   ```
6. **Verificar los hallazgos en el código de `main`** (no fiarse del reporte): `f3-exit-plan-block.tsx`, `decision-surface-compact.tsx`, `operational-plan-chart-levels.ts`, `instrument-strategy-top-panel.tsx`, `backtest-deep-coach.ts`, `dia_d_auto_feedback.py`, `operability_window.py` (`window_gate`).
7. **Qué falsaría el OK:** que §6 no esté enlazada desde §0 · que el plan de motor se lea como vigente · que un hallazgo no cite `file:line` · que un slice toque motor/contrato/Alembic sin declararlo · que la auditoría re-mida DÍA-D · que un dato ausente se pinte `0` o verde.
8. **Decisión esperada:** aceptar o refutar `S1`–`S4` **antes** de lanzarlos; si un slice exige motor, reabrir el [plan PARKED](./plan-cierre-operativa-auto-2026-10-08.md) con dueño y disparador.
