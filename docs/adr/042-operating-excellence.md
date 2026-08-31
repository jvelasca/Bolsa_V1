# ADR-042: Operating Excellence — contrato de operativa (V1.42)

**Estado:** Accepted — **contrato**; **F2–F8 CÓDIGO** (2026-08-31; serie Operating Excellence completa)  
**Fecha:** 2026-08-31  
**Contexto:** Auditoría externa sobre tip `v1.41.3-beta` → `a8101ab7` (CI GREEN). Honesty operativa PASS. El backend no debe retocarse para parches de UI. El cuello de botella es un **contrato único** (Operating Model + Golden Paths + UI State Machine) antes de programar ExecutionState / Mercado 2.0 / Hoy 2.0. F2 implementa la proyección `ExecutionState` en `@bolsa/shared` sin motor ni tabla. F2b añade GET read-only de intents in-flight para UNKNOWN en Mercado sin Confirm. F5 renombra chrome a **DECISIÓN** y estructura CONTEXTO→ESTADO→ACCIÓN sin motores nuevos. F6 proyecta Hoy a cuatro cubos §B.7 sin DailyEngine. F7 cierra simetría SEMI entrada/salida (Confirm = firma; trail honesty; copy §B.5). F8 productiza PAPER AUTO (mismos objetos; omite Confirm; arm ≠ execute; `PAPER_D_EXECUTE` opt-in).

**Depende de:** [ADR-031](./031-operational-model-tesis-plan-permiso.md) · [ADR-032](./032-operational-core-tradeplan-positionstate-execution.md) · [ADR-037](./037-mesa-hoy-operational-ux.md) · [ADR-040](./040-user-information-architecture.md) · [ADR-041](./041-operational-coherence.md) · spec [`spec-v142-operating-excellence-2026-08-31.md`](../engineering/spec-v142-operating-excellence-2026-08-31.md).

---

## 1. Decisión

Se acepta el spec V1.42 como **contrato definitivo de la operativa de producto**. Este ADR no implementa código, tablas ni endpoints.

```text
DOMAIN (intocado)
  → authorities existentes (check_opening, Confirm, PositionState, ExitPermission)
  → proyecciones canónicas (EntryOperatingTruth, OperationalTruth, ExecutionState, …)
  → UI (Mercado = terminal · Hoy = command center)
```

**No** se crean motores: ni OpportunityEngine, ni ExecutionEngine2, ni DailyEngine, ni PositionEngine2, ni TradeStoryEngine.

Tesis ≠ plan ≠ permiso ≠ ejecución permanece (ADR-031/032). Ranking ≠ BUY. Confirm = firma. LLM ≠ execution.

## 2. Proyecciones de lectura (no entidades)

| Proyección               | Rol                                   | Relación con lo existente                          |
| ------------------------ | ------------------------------------- | -------------------------------------------------- |
| `EntryOperatingTruth`    | Pre-posición                          | Ya en código (V1.38)                               |
| `ExecutionState`         | Ciclo de orden/fill/UNKNOWN/reconcile | Nuevo; germen = `orderPending` / PaperOrder / OR-2 |
| `PositionOperatingTruth` | Vida de la posición + nextAction      | **Compone** `OperationalTruth`; no la sustituye    |
| `TradeStory`             | Timeline idea→cierre                  | Journal consume; no duplica Journal                |

Detalle de campos, CTA y simetría ENTRY/EXIT: spec §A.

## 3. Autoridad vs UX fail-closed

- `entriesBlocked` = prevención UX / no generar propuestas desde superficies.
- `check_opening` = autoridad de apertura.
- `POST /ai/recommendations/propose` **no** se modifica en este ADR. Propose ≠ execute.

## 4. UI

- Panel derecho de Mercado = **DECISIÓN** (no Operativa / Asesor / Trading). Shell `LISTAS | GRÁFICO | DECISIÓN` intacto en geometría. Enmienda [ADR-041 §1.6](./041-operational-coherence.md).
- **Una CTA primaria** por activo. Copy de usuario, nunca enums internos (`T1_REACHED`).
- Si `full_exit` es válido y urgente → CTA `exit`. Discrepancia de protección = condición **secundaria**. Cambio de contrato vs `mapMesaNextAction` actual; se aplica en F3, no como parche previo.
- Hoy 2.0 = cuatro cubos (requiere acción / oportunidades / vigilar / sin acción). No segundo Mercado.
- Trailing hint ≠ `currentStop`. Camino: propuesta → Policy → Confirm → PositionRevision.

## 5. Golden Paths

Los diez escenarios del spec §C **son** el DoD de V1.42 (código futuro). V1.27 cubre un subconjunto de dominio; no cierra el producto.

## 6. Versionado

Cinco verdades distintas: product · git tag · package · schema · API. [`versioning.md`](../engineering/versioning.md). `package.json` permanece `1.35.0-beta` hasta V1.42 **estable**.

## 7. Consecuencias

- Spec canónico: [`spec-v142-operating-excellence-2026-08-31.md`](../engineering/spec-v142-operating-excellence-2026-08-31.md).
- Enmienda ADR-041 §1.6 · diseño Mercado 2.0 (etiqueta DECISIÓN).
- Implementación: **F2–F8 CÓDIGO** ([plan F8](../engineering/plan-v142-f8-paper-auto-2026-08-31.md) · [relevo F8](../engineering/traspaso-relevo-v1-42-f8-paper-auto-2026-08-31.md)); residual trail durable **CERRADO** SEMI ([relevo V1.43](../engineering/traspaso-relevo-v1-43-trail-revision-2026-08-31.md)); parked: thaw estricto · LIVE · OCO · Lab P2.
- Backend money path / Confirm SEMI intocados en F8 (solo posture UI + gates existentes). Sin nav L1 nueva. Sin thaw. Sin Lab P2.

## 8. Fuera

OpportunityScore · drag · OCO · trail autoridad automática · bump package · `propose` + `entriesBlocked` en backend.
