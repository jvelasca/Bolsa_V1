# Spec — V1.72 Decision Explainability TOP (WHY rico)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + tests locales; **sin stamp CI GREEN**).  
> **Padre:** [`spec-v171-identity-certification-2026-09-02.md`](./spec-v171-identity-certification-2026-09-02.md) · partida **V1.71** (`b70849bd`). **No** LIVE.

Convierte el «¿Por qué?» de V1.66 en una ficha operacional TOP. El motor decide; la UI explica. **Sin** LLM · **sin** COMPRAR · **sin** inventar geometría Ideal/Máxima.

```text
P0  GP-V172-01 — DecisionExplainView schema 1.1.0 (score X/10 · LONG · factors · entryGeometry)
P0  GP-V172-02 — DecisionExplainPanel layout TOP + testids
P0  GP-V172-03 — Entry Surface: mark + distancia (omitir Ideal/Máxima)
P1  GP-V172-04 — Paridad Python del explain view + goldens
P1  GP-V172-05 — T2_READY: producto MONITOR documentado; headline «T2 alcanzado» sin cambiar mapping
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin scheduler · sin bump `1.35.0-beta` · sin segunda Decision Engine · sin LLM en hot path · V1.71 journey/identidad intactos.

## 1. IN

| ID         | Comportamiento                                                                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GP-V172-01 | `buildDecisionExplainView` proyecta `score`, `thesisDirection` (LONG≠COMPRAR), `factors[]` pass/fail/unknown, `levels`, `entryGeometry`, `authorization`                 |
| GP-V172-02 | Panel Mercado: hero SÍMBOLO·X/10 · DECISIÓN LONG · POR QUÉ checklist · Entrada/Precio/distancia · Stop · T1/T2 · invalidación · autorización «no es orden»               |
| GP-V172-03 | `buildOperationalPlanFromStudy` / `buildEntryOperatingTruth` aceptan `markPrice`; EntryCompact muestra Precio actual + Distancia solo si ambos finitos; sin Ideal/Máxima |
| GP-V172-04 | Espejo Python `decision_explain_view.py` + goldens (LONG≠COMPRAR, unknown≠pass, distancia null sin mark)                                                                 |
| GP-V172-05 | Spec: `T2_READY` → desk `reduced` → `MONITOR` es **intencional**. Headline Position Surface «T2 alcanzado»; **no** se cambia `resolvePaperDeskNextAction`                |

### Factores (fail-closed)

Checklist fija: `tendencia` · `momentum` · `volumen` · `regimen` · `rr` · `riesgo` · `perfil`.

- `unknown` **nunca** se pinta como check verde.
- `momentum` / `volumen` solo si el caller pasa `taComponents`; si no → `unknown`.
- `perfil` solo `fail` con `whyNot` fit/mandate; **no** se inventa `pass`.

### Tesis ≠ orden

`recommend_long` → `LONG` · `recommend_short` → `SHORT` · `wait` → `ESPERAR` · `reduce` → `REDUCIR` · `exit_hint` → `SALIDA`.  
El label **no** contiene COMPRAR ni BUY. Autorización (`entriesBlocked` / gate) va en sección aparte.

### Geometría de entrada

Componer lo que el motor ya emite: `plan.entry` + `currentPrice` (mark) + distancia.  
`Ideal` / `Máxima` **no existen** en TradePlan → omitir (ni DOM ni números).

### T2_READY (producto)

Cadena vigente (no se toca):

```
T2_READY → deskStatus reduced → APPLIED → MONITOR
```

Un usuario puede esperar «gestionar T2»; el desk dice MONITOR porque T2_READY es estado de nivel alcanzado, no orden ejecutada. Copy: «T2 alcanzado · mesa MONITOR». Mapping intacto.

## 2. OUT

- Multi-instrumento A→B→C→A (**V1.73**)
- Entry→Buy→Position browser (**V1.73**)
- Refresh integrity (**V1.73**)
- Stale → no execute E2E (**V1.74/V1.75**)
- Ideal/Máxima / micro-motor geométrico
- LLM · segunda Decision Engine · scheduler · LIVE · bump package
- POV blob rebuild · STOP_FILL parity · logging recon · fixture AAPL determinista · split `integration.ts`
- Paper Autonomous Day (**V1.74**)
- Rediseño Paper Desk / `T2_READY` → GESTIONAR T2
- HUD why (V1.63)

## 3. Pre-flight

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/decision-explain-view.test.ts src/cognitive/operational-plan-view.test.ts src/cognitive/entry-operating-truth.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/decision-explain-panel.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/position-decision-surface.test.ts src/features/trading/decision-surface-compact.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
python -m pytest packages/py/analytics/tests/test_decision_explain_view.py -q
```
