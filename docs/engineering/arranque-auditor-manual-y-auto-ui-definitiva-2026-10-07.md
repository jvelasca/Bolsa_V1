# Arranque del auditor — **MANUAL (libro DEMO)** + **UI AUTO definitiva / TOP 3 OPORTUNIDADES**

> **AsOf:** 2026-10-07 · **Objeto:** dos documentos de **diseño/auditoría** (no código).
> **Base de código auditada:** `main` = `origin/main` = `3aa0241e` (sello [`v2.88.84-beta`](./evidence/v2.88.84/README.md)).
> **Naturaleza:** auditoría en solo lectura + spec de diseño congelada. **`Δ AUTO decision/execution motor = 0`**. Sin contrato HTTP nuevo, sin Alembic, sin bump de versión.
> **Nota de auditabilidad (declarada).** Al ser un cambio **solo de documentación**, **no** hay tag de release ni `Release tag CI` propio; los tres documentos viven en `main`. La evidencia de motor que respaldan las afirmaciones del TOP3 **sí** está certificada: `Release tag CI` [`37629056130`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37629056130) **VERDE** (tag `v2.88.84-beta`, `replay-repro` reproducido ⇒ `Δ motor = 0`).

---

## 0. Objeto de esta auditoría

Dos entregables que cierran la definición de producto pendiente y que, con el OK del auditor, desbloquean el **desarrollo y la refactorización**:

| # | Documento | Qué resuelve |
| --- | --- | --- |
| 1 | [auditoria-manual-modo-demo-2026-10-07.md](./auditoria-manual-modo-demo-2026-10-07.md) | Auditoría profunda del **modo MANUAL** del libro DEMO. Hallazgo **H1 (P1)**: la posición abierta en MANUAL **no se puede cerrar** desde la app. |
| 2 | [spec-auto-ui-definitiva-2026-10-07.md](./spec-auto-ui-definitiva-2026-10-07.md) | Semántica congelada **«TOP 3 OPORTUNIDADES»** y diseño de la UI AUTO definitiva sobre el TOP3 cross-asset ya productivo. |

---

## 1. Prompt listo para pegar (chat nuevo del auditor)

```text
Eres auditor externo de Bolsa V1. Solo ves GitHub (jvelasca/Bolsa_V1, rama main).

Objeto: auditoría de DISEÑO (no de motor) sobre dos documentos nuevos:
  - docs/engineering/auditoria-manual-modo-demo-2026-10-07.md
  - docs/engineering/spec-auto-ui-definitiva-2026-10-07.md
Punto de entrada: docs/engineering/arranque-auditor-manual-y-auto-ui-definitiva-2026-10-07.md

Base de código: main = 3aa0241e (sello v2.88.84-beta). Cambio solo de documentación:
no hay tag de release ni CI nuevo para estos documentos. Δ motor = 0.

Reglas: una regla que no se pueda afirmar se declara ABIERTA con su remediación, nunca
se silencia. No inventar PASS. Un hueco no es un 0. Propuesta ≠ operación.

Alcance:
  1. MANUAL: confirmar el dead-end de salida (H1) y valorar las 3 opciones de diseño.
  2. UI AUTO / TOP3: validar la semántica «TOP 3 OPORTUNIDADES», la escalera
     TOP3 → Decision → Risk Gate → Order → Fill → Materialización SIM → Position,
     y los estados honestos (vacío / hueco / degradado).

Verifica sobre el código (main): execute_gated_portfolio_trade.py (fence sell),
propose-position-exit.ts (throw en MANUAL), top3_opportunities.py (endpoint) y
auto_simulation_worker.py (_v2_persist_top3). Confirma que NO existe consumidor web
de /api/v1/top3-opportunities/*.

Responde: veredicto por documento, hallazgos, y si das el OK para empezar desarrollo.
```

---

## 2. Orden de lectura

1. **Este arranque.**
2. [auditoría MANUAL](./auditoria-manual-modo-demo-2026-10-07.md) — §4 cadena, §5 hallazgos, §9 falsabilidad.
3. [spec UI AUTO definitiva](./spec-auto-ui-definitiva-2026-10-07.md) — §1 definición de TOP3, §2 escalera, §8 falsabilidad.
4. **Padres de diseño** (para comprobar que la spec «congela» y no inventa): [spec 3.0](./spec-auto-ui-refactor-3-0-2026-10-06.md) · [operación para usuario básico](./spec-auto-operacion-usuario-basico-2026-10-06.md) · [modelo semántico 1.0](./spec-auto-ui-semantic-model-1-2026-10-05.md) · [HOME vacío vs hueco](./spec-auto-home-vacio-hueco-2026-10-06.md) · [ADR-044](../adr/044-auto-workspace-information-architecture.md).
5. **Padres de MANUAL:** [brief de modos DEMO](./demo-operating-modes-brief-2026-08-03.md) · [estudio operativa auto y gráfico](./estudio-operativa-auto-y-grafico-2026-08-28.md) · [ADR-034](../adr/034-operational-integrity-continuity.md) · [ADR-035](../adr/035-operational-reliability.md).
6. **Evidencia de motor (TOP3):** [evidence/v2.88.84](./evidence/v2.88.84/README.md) · [evidence/v2.88.83](./evidence/v2.88.83/README.md) · [auditoría composition-root evidencia/TOP3](./auditoria-composition-root-evidence-top3-v2.88.83-2026-10-07.md).

---

## 3. Qué tiene que comprobar el auditor

### 3.1 MANUAL (auditoría)

1. **H1 (dead-end de salida).** Una venta HTTP con `PositionState` abierta lanza `ExitVetoedError("position_exit_requires_confirm")` en [`execute_gated_portfolio_trade.py`](../../packages/py/application/src/bolsa_application/execute_gated_portfolio_trade.py); y en MANUAL `buildPositionExitPayload` lanza en [`propose-position-exit.ts`](../../apps/web/src/features/operations/propose-position-exit.ts). Conclusión esperada: **no hay camino de cierre dentro de la app**.
2. **MANUAL es un interruptor de producto**, no un motor: `demoBookAllowsEnqueueConfirm/Execute/RequiresHumanConfirm` sólo son `true` para `semi` en [`demo-book-prefs.ts`](../../apps/web/src/features/trading/demo-book-prefs.ts).
3. **La vía manual no consulta el modo** (mode-agnóstica) y **nunca** alcanza broker real: [`accounts/trade.py`](../../packages/py/application/src/bolsa_application/accounts/trade.py) sólo escribe ledger paper.
4. **Materialización honesta:** `origin = HUMAN_MANUAL`, snapshot `manual-{tx}` en [`post_fill_position_sync.py`](../../packages/py/application/src/bolsa_application/post_fill_position_sync.py).
5. **Cobertura de tests:** el *fence* de backend está testeado; **no** hay test de UI/E2E del dead-end.

### 3.2 UI AUTO / TOP3 (spec)

1. **Semántica.** El título es **«TOP 3 OPORTUNIDADES»** (universo = ranking del tick), **nunca** «TOP 3 MEJORES ACCIONES».
2. **TOP3 ≠ operación.** La escalera se respeta; estar #1 no se pinta como compra.
3. **Anatomía del slot** y **7 componentes** con pesos: [`opportunity_ranker.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/opportunity_ranker.py).
4. **Degradación visible:** `scoring_historico_sin_campeon` se muestra como motivo; [`top3_opportunities.py`](../../packages/py/application/src/bolsa_application/top3_opportunities.py).
5. **No hay consumidor web** del endpoint hoy: ausente de [`lib/api.ts`](../../apps/web/src/lib/api.ts) y de `apps/web/src/api/schema.d.ts`.
6. **Fases T0–T4** declaradas aditivas y sin mover el motor.

---

## 4. Qué falsaría el OK

- **MANUAL:** que en MANUAL **sí** exista un camino de cierre (falsaría H1) · que la compra/venta manual aplique el modo del libro · que la vía manual alcance broker real.
- **TOP3:** que la UI rotule «mejores acciones» · que un slot sin hecho posterior se pinte como comprado · que el panel **re-derive** el score en el frontend · que un slot degradado se pinte igual que uno con evidencia · que «Sin TOP3 todavía» y «Sin dato todavía» compartan rótulo.
- **Ambos:** que el diff toque motor, umbrales, Alembic o el contrato HTTP existente (`Δ motor = 0`).

---

## 5. Límites declarados (qué NO se entrega)

- **No** se toca código, motor, umbrales, contratos HTTP ni Alembic.
- **No** se implementa el consumidor del TOP3 ni el arreglo del dead-end de MANUAL: se documentan como **recomendaciones** y fases futuras.
- **No** hay tag de release para estos documentos (son diseño/auditoría).
- **No** se re-mide DÍA-D.
- Siguen abiertas las deudas previas: `PortfolioDecision` durable, materialización SIM (`apply`), barrido `axe` (S4), PIT histórico institucional, Execution Analysis.

---

## 6. Decisión esperada

Con el **OK** del auditor sobre el diseño/semántica:

1. **MANUAL:** elegir una de las tres opciones de [§10 de la auditoría](./auditoria-manual-modo-demo-2026-10-07.md) y abrir su slice.
2. **UI AUTO / TOP3:** arrancar las fases **T1–T4** de [§7 de la spec](./spec-auto-ui-definitiva-2026-10-07.md) (contrato UI → hook → panel → certificación).

Ninguna de las dos mueve el motor: son producto y presentación sobre un motor ya certificado.
