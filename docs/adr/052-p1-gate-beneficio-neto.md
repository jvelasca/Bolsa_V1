# ADR-052 — P1 como gate real: beneficio neto, expectativa y ausencia declarada

**Estado:** **Accepted — implementado en el árbol.** El LAB selecciona por **beneficio neto** y
**expectativa** medidas, con la fricción aplicada en la rejilla; un run sin medición neta declarada
no puede promocionar. **`Δ motor = 0`** (no se toca el motor de decisión de TRADING) ·
**`Δ score = 0,25`** (el peso deliberadamente no se cambia, para aislar la causa) ·
**`activationAllowed = false`** (el embudo se congela hasta que haya un run nuevo con coste medido).
**Fecha:** 2026-11-16
**Contexto:** [auditoría LAB 2026-11-16](../engineering/plan-remediacion-laboratorio-2026-11-16.md) ·
[ADR-017](./017-baseline-v1-5-research-observatory.md) (baseline del laboratorio) ·
[ADR-009](./009-backtesting-research-platform-h0.md) (motor de medición).
**Depende de:** [ADR-016](./016-research-persistence-model.md) (persistencia del dominio
Scientific) · [RFC-008](./rfc/008-cognitive-decision-architecture.md) (Evidence / MKL / Gate).

**Afecta a:**
[`backtest-paper-gate.ts`](../../apps/web/src/features/backtests/backtest-paper-gate.ts) ·
[`backtest-paper-checklist.tsx`](../../apps/web/src/features/backtests/backtest-paper-checklist.tsx) ·
[`research-trial-result-block.tsx`](../../apps/web/src/features/research/research-trial-result-block.tsx) ·
[`strategy_lab_phase.py`](../../packages/py/application/src/bolsa_application/strategy_lab_phase.py) ·
[`accounts.ts`](../../packages/shared/src/accounts.ts) ·
[`backtest-oos-evidence.ts`](../../apps/web/src/features/backtests/backtest-oos-evidence.ts) ·
[ADR-053](./053-disparador-gobernado-embudo-auto.md).

---

## 1. El problema

El score del LAB elegía el campeón con una magnitud **bruta**: la rejilla optimizaba el retorno
antes de costes, y el coste aparecía (si aparecía) al publicar. Tres consecuencias medidas en la
auditoría:

1. **Selección invertida.** Con una fricción de referencia de 32 bps, un campeón con ventaja bruta
   pequeña puede quedar **perdedor neto**. La rejilla seguía eligiéndolo porque nunca restaba.
2. **Gate fantasma.** El checklist pre-paper no tenía check de rentabilidad neta ni de
   expectativa: un run sin costes medidos pasaba igual. El hueco no era «no medido», era «cero
   implícito» — el peor de los tres estados posibles.
3. **Métricas inventadas.** Varios checks rellenaban con `?? 0` los campos ausentes (OOS,
   hold-out, CPCV, WFE). Un `0` silencioso se lee como «medido y malo», no como «no medido».

## 2. Decisión

### 2.1 La rejilla aplica la fricción

La rejilla del LAB aplica el coste de ida y vuelta **por operación** al evaluar cada punto del
grid. El campeón es el mejor por magnitud **neta**, no bruta. La referencia de fricción se declara
junto al resultado (`roundTripCostBps`), no se deduce del entorno.

### 2.2 Claves nuevas, con la ausencia declarada

El resultado publica el bloque neto **solo si se midió**:

| Campo | Significado | Ausencia |
|-------|-------------|----------|
| `returnBasis` | `net` \| `gross` | Ausente ⇒ no se puede usar como evidencia P1 |
| `netReturnPct` | Retorno neto de costes (%) | Ausente ⇒ «Sin dato todavía» |
| `expectancyCurrency` | Expectativa por operación (divisa) | Ausente ⇒ «Sin dato todavía» |
| `roundTripCostBps` | Fricción aplicada (bps ida y vuelta) | Ausente ⇒ no se puede verificar el suelo |
| `netTradeCount` | Operaciones que sostienen la medida | Ausente ⇒ `UNKNOWN ≠ 0` |

**`UNKNOWN ≠ 0`**: una métrica no medida **nunca** se colapsa a cero. La UI muestra «Sin dato
todavía», y el gate la trata como no superada (fail-closed), no como fallo medido.

### 2.3 El gate `p1`

`p1` es un gate más del dominio (viaja en `StrategyEvaluation.gates`, como `oos`, `dsr` o
`drawdown`). Se compone de dos checks del checklist pre-paper (`net_profit`, `expectancy`) y de
tres reglas duras del servidor:

- `returnBasis == 'gross'` ⇒ **bloqueo**: seleccionar por bruto es exactamente el defecto que este
  ADR corrige.
- `roundTripCostBps < 22` ⇒ **bloqueo**: por debajo del suelo de fricción, la medida no es
  creíble para el universo operado.
- `netReturnPct <= 0` ⇒ **bloqueo**: el campeón no gana dinero después de costes.

El estado del gate es `PASS` \| `FAIL` \| `NOT_EVALUATED`, y `NOT_EVALUATED` **no aprueba**
(fail-closed). La UI lo rotula «Sin dato todavía», jamás «Cumple» ni «No cumple».

### 2.4 Aplicado a la vez en los cuatro sitios

El gate se calcula con **una sola** función compartida (`p1_gate_from_metrics`) y se aplica en los
cuatro puntos que deciden o muestran: la evaluación del trial del orquestador, el manifiesto del
`backtest_run`, el checklist pre-paper (web) y el panel de resultado del trial. Cuatro
implementaciones divergentes del mismo gate es exactamente el fallo que R1 evitó.

## 3. Consecuencias

**Buenas.**
- El campeón es el mejor **neto**, y el «bruto ganador / neto perdedor» queda bloqueado por test.
- Un run sin coste medido ya no puede promocionar: se declara la ausencia, no se inventa un cero.
- La UI explica **de qué base** viene el número («Medido neto de costes» vs «Medido SIN costes»),
  en lugar de mostrar un porcentaje de procedencia desconocida.

**Costes aceptados.**
- **El embudo se congela** hasta que exista un run nuevo con coste medido: los TOP vigentes,
  calculados con la rejilla bruta, no satisfacen P1. Es una decisión consciente: preferimos un
  embudo parado a un embudo que promociona por bruto. La UI lo declara como estado esperado.
- Ningún umbral de PBO/WFE/DSR/drawdown cambia, y el peso `0,25` del score se mantiene: el cambio
  de causa queda aislado y su efecto es atribuible.

## 4. Lo que este ADR no hace

- **No** migra datos históricos ni re-ejecuta la rejilla (§ documento de plan).
- **No** cambia el motor de decisión de TRADING ni la ejecución real.
- **No** toca el ledger.
- **No** fabrica `expectancyR`: sin unidad de riesgo declarada, la expectativa se publica en
  **divisa** (`expectancyCurrency`), nunca en R.

## 5. Verificación

`backtest-paper-gate.test.ts` (check de beneficio neto, suelo de fricción, ausencia declarada,
expectativa, separación de payloads) · `test_grid_costs.py` (caso bruto-ganador/neto-perdedor de
la auditoría §4.3, con `COSTS_42_BPS` vs `REFERENCE_COSTS` 32 bps) ·
`test_top_provenance.py` (un slot TOP exige un `runId` cuyo manifiesto satisfaga
`p1_gate_from_metrics`) · `paper-paths-copy.test.ts` (la copy canónica coincide en UI y docs).
El criterio de hecho: **quitar el gate `p1` rompe al menos tres tests; volver a poner los `?? 0`
rompe al menos dos.**
