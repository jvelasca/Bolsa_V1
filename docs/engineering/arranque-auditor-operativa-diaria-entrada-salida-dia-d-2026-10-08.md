# Arranque del auditor — **Operativa diaria: entrada/salida · estrategia/indicadores · DÍA-D (reorden FASE 3)**

> **AsOf:** 2026-10-08 · **Objeto:** premisas de producto + reorden de la FASE 3 + auditoría read-only de los tres pilares (**documentación**, no código).
> **Base de código auditada:** `main` = `origin/main` = `e92e9cf5` (sello [`v2.88.94-beta`](./evidence/v2.88.94/README.md) → commit `20fd538c`).
> **Naturaleza:** auditoría **en solo lectura**. **`Δ AUTO decision/execution motor = 0`**: sin contrato HTTP nuevo, sin Alembic, sin bump de versión, sin tocar `packages/py/**`.
> **Nota de auditabilidad (declarada).** Al ser un cambio **solo de documentación**, **no** hay tag de release ni `Release tag CI` propio para estos documentos; viven en `main`. La evidencia de motor que respaldan es la del sello base: `Release tag CI` [`37823112083`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37823112083) **VERDE** (`replay-repro` reproducido `1E3ADAC2…` ⇒ `Δ motor = 0`).

---

## 0. Objeto de esta auditoría

El propietario **reordenó la FASE 3**: la completitud contable de motor (`PortfolioDecision` durable, materialización de posición, P&L realizado) queda **parkeada** como deuda declarada, y el foco pasa a **cuatro prioridades de producto** (`P1`–`P4`). El entregable es una **auditoría read-only** de los tres pilares que sustentan esas prioridades, desde la que se definirán (sin ejecutar) los slices de mejora.

| # | Documento | Qué resuelve |
| --- | --- | --- |
| 1 | [`PROJECT_PREMISES.md`](../PROJECT_PREMISES.md) §6 | **Premisas de producto `P1`–`P4`** (operativa ganadora diaria · claridad entrada/salida · estrategia confirmada con indicadores · evaluación DÍA-D), enlazadas desde §0. |
| 2 | [auditoría FASE 2](./auditoria-operativa-auto-fase-2-2026-10-08.md) §8 | Declara el **reorden** y mantiene abiertos `F2-1`…`F2-4` como deuda. |
| 3 | [plan de cierre de motor](./plan-cierre-operativa-auto-2026-10-08.md) | **PARKED** con dueño y disparador: se retoma **solo si** un pilar `P1`–`P4` lo exige. |
| 4 | **[auditoría diaria entrada/salida · estrategia/indicadores · DÍA-D](./auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md)** | **El entregable a juzgar.** 12 hallazgos falsables `P2-*`/`P3-*`/`P4-*` con `file:line` + 4 slices derivados `S1`–`S4`. |
| 5 | [entrega a auditoría externa (MIA) del ciclo](./entrega-auditoria-externa-mia-v2.88.94-reorden-fase-3-2026-10-08.md) | Resumen formal: qué se entrega/NO, cambios, medición, hallazgos abiertos, gates, sello y guion desde GitHub. |

---

## 1. Prompt listo para pegar (chat nuevo del auditor)

```text
Eres auditor externo de Bolsa V1. Solo ves GitHub (jvelasca/Bolsa_V1, rama main).

Objeto: auditoría de DOCUMENTACIÓN (no de motor) sobre el reorden de la FASE 3:
  - docs/PROJECT_PREMISES.md §6 (premisas de producto P1-P4)
  - docs/engineering/auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md (entregable)
  - docs/engineering/auditoria-operativa-auto-fase-2-2026-10-08.md §8 (reorden)
  - docs/engineering/plan-cierre-operativa-auto-2026-10-08.md (PARKED)
Punto de entrada: docs/engineering/arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md

Base de código: main = e92e9cf5 (sello v2.88.94-beta). Cambio solo de documentación:
no hay tag de release ni CI nuevo para estos documentos. Δ motor = 0.

Reglas: una regla que no se pueda afirmar se declara ABIERTA con su remediación, nunca
se silencia. No inventar PASS. Un hueco NO es un 0: se rotula «Sin dato todavía».
Ranking ≠ decisión. Propuesta ≠ posición materializada.

Alcance (veredicto por pilar, con evidencia file:line sobre el código de main):
  P2 · Entrada/salida — ¿el punto de entrada y el de salida son inequívocos a primer nivel?
  P3 · Estrategia/indicadores — ¿se declaran la estrategia confirmada y SUS indicadores?
  P4 · DÍA-D — ¿la medición declarado vs ejecutado vs OOS es suficiente? (NO se re-mide)

Comprueba en el código de main (no te fíes del reporte):
  - f3-exit-plan-block.tsx (¿precio de salida por peldaño?)
  - decision-surface-compact.tsx (T1/T2 en Journey HUD: visibles o sr-only)
  - operational-plan-chart-levels.ts (¿«Entrada» literal en simple + prepared?)
  - instrument-strategy-top-panel.tsx + backtest-deep-coach.ts (¿indicadores/reasons visibles?)
  - dia_d_auto_feedback.py (¿se emite CONFIRMED? ¿qué veredictos existen?)
  - operability_window.py window_gate (veredictos READY/INCONCLUSIVE)

Contrasta §5 de PROJECT_PREMISES.md (que describe un veredicto CONFIRMED) con el código:
el código RESERVA CONFIRMED para evidencia PAPER y NO lo emite. ¿Es incoherencia doc↔código?

Responde: veredicto por pilar (CUMPLE / CUMPLE PARCIAL / NO CUMPLE), hallazgos y si
aceptas o refutas los 4 slices S1-S4 ANTES de que se lancen.
```

---

## 2. Orden de lectura

1. **Este arranque.**
2. [`PROJECT_PREMISES.md`](../PROJECT_PREMISES.md) — §0 (índice) y **§6 (P1–P4)**; contraste con §5 (cómo se mide AUTO/PAPER).
3. **[auditoría diaria entrada/salida · estrategia/indicadores · DÍA-D](./auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md)** — §1–§3 (evidencia por pilar), §4 (tabla de hallazgos), §5 (slices).
4. [auditoría FASE 2](./auditoria-operativa-auto-fase-2-2026-10-08.md) §8 — el reorden y la deuda `F2-*`.
5. [plan de cierre de motor PARKED](./plan-cierre-operativa-auto-2026-10-08.md) — dueño y disparador.
6. **Padres de contrato:** [ADR-040](../adr/040-user-information-architecture.md) · [ADR-045](../adr/045-ui-contract-5-0.md) · [spec UI 5.0](./spec-ui-contract-5-0-2026-10-08.md) · [ADR-021 (DÍA-D)](../adr/021-dia-d-reconciliation.md) · [domain-language](../domain-language.md).
7. **Evidencia base:** [evidence/v2.88.94](./evidence/v2.88.94/README.md) · [entrega MIA v2.88.94](./entrega-auditoria-externa-mia-v2.88.94-2026-10-08.md) §7.

---

## 3. Qué tiene que comprobar el auditor

### 3.1 `P2` · Entrada/salida (veredicto esperado: **CUMPLE PARCIAL**)

1. **Entrada clara.** Cockpit `full` y HUD muestran Entrada/Stop/T1; el ticket Confirm los muestra. Evidencia: `apps/web/src/features/trading/decision-surface-compact.tsx:296-402`; `f3-trade-plan-risk-first-block.tsx:85-125`.
2. **`P2-2` salida sin precio.** El `ExitPlan` del ticket declara intent/qty/estado/acción/motivo pero **no** un precio de salida por peldaño. Evidencia: `apps/web/src/features/trading/f3-exit-plan-block.tsx:85-104`.
3. **`P2-3` entrada no literal.** En `focus simple` + `phase prepared` no se dibuja «Entrada» (se usa `Trigger`). Evidencia: `apps/web/src/features/charts/operational-plan-chart-levels.ts:159-201`.
4. **`P2-4` objetivos en Journey.** Con Journey activo, T1/T2 quedan en `sr-only`. Evidencia: `decision-surface-compact.tsx:643-671`; `operator-cabin-ui.tsx:600-618`.

### 3.2 `P3` · Estrategia/indicadores (veredicto esperado: **CUMPLE PARCIAL**)

1. **`P3-1` indicadores no visibles.** Los Finalistas muestran `#rank label ★ · source · ret · DD` sin indicadores. Evidencia: `apps/web/src/features/backtests/instrument-strategy-top-panel.tsx:169-190`.
2. **`P3-2` tipo ejecutable correcto.** El `strategyType` se sanea al preset de la definición. Evidencia: `apps/web/src/features/backtests/instrument-top-strategy-type.ts:14-28`.
3. **`P3-3` catálogo desacoplado.** El catálogo de indicadores es del **gráfico**, no de la estrategia. Evidencia: `apps/web/src/features/charts/indicators-catalog-dialog.tsx:93-130`.
4. **`P3-4` `reasons` no aterrizan.** El coach produce y persiste `reasons`, pero la superficie no las muestra. Evidencia: `apps/web/src/features/backtests/backtest-deep-coach.ts:434-481`, `:1046`, `:1112`.

### 3.3 `P4` · DÍA-D (veredicto esperado: **CUMPLE PARCIAL**)

1. **`P4-1` comparador honesto.** Declarado↔ejecutado paso a paso con `MATCH`/`DIVERGENT`/`NOT_MEASURED`/`PARTIAL`. Evidencia: `packages/py/application/src/bolsa_application/dia_d_auto.py:50-59`, `:138-199`.
2. **`P4-2` sin `CONFIRMED` (clave).** El código **reserva** `CONFIRMED` para PAPER y **no lo emite**; el lado ejecutado queda `NOT_MEASURED`. Evidencia: `packages/py/application/src/bolsa_application/dia_d_auto_feedback.py:65-82`, `:151-153`.
3. **`P4-3` medición por artefacto CLI**, no en vivo. Evidencia: `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py:35-59`, `:248-291`.
4. **`P4-4` veredicto fragmentado** en tres superficies (reconciliación Trading · declarado↔ejecutado · feedback OOS). Evidencia: `dia-d-reconciliation.ts:149-165` vs `dia_d_auto.py:184-199` vs `dia_d_auto_feedback.py:374-407`.

---

## 4. Qué falsaría el OK

- Que §6 **no** esté enlazada desde §0 de `PROJECT_PREMISES.md`, o que relaje el invariante SIM/XTB (§6.2).
- Que el plan de motor **no** figure como PARKED, o que se lea como vigente.
- Que un hallazgo de la auditoría **no** cite `file:line` verificable, o que invente un PASS.
- Que un slice de §5 de la auditoría **toque motor, contrato HTTP o Alembic** sin declararlo.
- Que la auditoría **re-mida** DÍA-D (está fuera de alcance: solo juzga si la medición es suficiente).
- Que un dato ausente se pinte `0` o verde (debe ser «Sin dato todavía»).

---

## 5. Límites declarados (qué NO se entrega)

- **No** se toca motor, worker, umbrales, ledger, contrato HTTP ni Alembic (`Δ motor = 0`).
- **No** se toca `packages/py/**`.
- **No** se ejecuta ningún slice de mejora: solo se **definen** `S1`–`S4`.
- **No** se emite `CONFIRMED` ni se re-mide DÍA-D.
- **No** hay tag de release para estos documentos (son premisa/auditoría).
- Siguen abiertas las deudas previas: `F2-1`…`F2-4` (completitud contable), `PortfolioDecision` durable, materialización SIM, PIT histórico institucional, Execution Analysis.

---

## 6. Decisión esperada

Con el **OK** del auditor sobre premisas + reorden + hallazgos:

1. Aceptar o refutar los **4 slices** de [§5 de la auditoría](./auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md): `S1-exit-precio`, `S2-entrada-literal`, `S3-indicadores-razon`, `S4-veredicto-unico`.
2. Si algún slice **exige** motor (p. ej. emitir `CONFIRMED` con evidencia PAPER), **parar** y reabrir el [plan PARKED](./plan-cierre-operativa-auto-2026-10-08.md) con dueño y disparador.

Ningún slice mueve el motor: son producto y presentación sobre un motor ya certificado.
