# Spec — V1.75 Chaos & stale → no-execute E2E

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (GO + implementación).  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · relevo V1.74 · [`spec-v174` §2 OUT](./spec-v174-paper-autonomous-day-2026-09-02.md) · adversarial [`spec-v158`](./spec-v158-adversarial-execution-2026-09-01.md).  
> **Partida tip:** `67f922bf` (feat v1.74 Paper Autonomous Day). **No** LIVE.

Certifica **fail-closed** ante datos stale / recovery ligera / no-execute, visible en mesa (E2E mock) y anclado en spine (pytest dryRun):

```text
stale market/data → no execute / no COMPRAR / deny honesto (ENTRY_STALE_DATA)
crash | duplicate | UNKNOWN → sin auto-heal indebido · sin segundo fill
```

```text
P0  GP-V175-01 — Hoy: candidato ENTRY_STALE_DATA → frase honest · 0 COMPRAR
P0  GP-V175-02 — Hoy: stale ≠ «0 oportunidades» (deny nombrado, no vacío)
P1  GP-V175-03 — Mercado: surface entrada stale → sin COMPRAR · deny visible
P1  GP-V175-04 — UNKNOWN / recovery: CTA no reenvía · copy sin auto-heal
P1  GP-V175-05 — pytest dryRun: STALE permission → held/data_stale · 0 sells
P1  GP-V175-06 — pytest: ENTRY_STALE_DATA mapea reasonCode + humanMessage
P2  GP-V175-07 — (opt) pytest adversarial smoke: crash replay / duplicate sin 2º fill
```

## 0. Freeze

Confirm SEMI intacto · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler prod · sin bump `1.35.0-beta` · sin `dryRun=false` en browser E2E · **V1.72–V1.74 intactos** (WHY rico · multi-instrument · Paper Autonomous Day).

Regla global: `Ranking ≠ Signal ≠ Proposal ≠ Authorization ≠ Order ≠ Fill`.  
Stale / UNKNOWN / duplicate **nunca** inventan COMPRAR ni auto-heal de libros.

## 1. Inventario previo (no reinventar)

| Capa                        | Ya existe                                                                                                                                            | Gap V1.75                                                  |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Contrato `ENTRY_STALE_DATA` | `paper_desk_entry.py` · `paper_desk_cycle.py` · `paper-daily-report.ts` · copy UI `daily-desk-auto-projection.ts` («Datos obsoletos — no proponer.») | **Sin** E2E mock Hoy/Mercado                               |
| DS-05 AUTO stale → skip     | `test_ds05_auto_stale_data_does_not_execute_trade` · `test_risk_engine` · `test_allow_opening_fill_stale_bar_vetoes`                                 | Spine unit OK; no journey mesa                             |
| Paper desk stale HOLD       | `test_auto_06_stale_deny` (`data_stale`, 0 sells) · GP-AUTO stale T1 HOLD                                                                            | Reutilizar; añadir dryRun + reasonCode entry si falta      |
| Chaos / crash / dup         | V1.58 `test_paper_desk_golden_day_adversarial.py` · `fail_next` · AUTO-05 crash replay · DEX-3 no auto-heal                                          | Playwright/UI surface **ausente**; smoke pytest opt-in     |
| Fixtures día                | V1.74 `paperAutonomousDayAutoDesk` · `installHoyPaperDayApiMocks`                                                                                    | Extender variante **stale** (`hoyStale` / helper dedicado) |

## 2. IN

| ID         | Prioridad | Comportamiento                                                                                                                                                                  |
| ---------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------ |
| GP-V175-01 | P0        | Mock Hoy: autoDesk con candidato `reasonCode: ENTRY_STALE_DATA` + `humanMessage` alineado a copy canónica · badge AUTO armado · ejecución off · **0** botones `COMPRAR`         |
| GP-V175-02 | P0        | Mismo mock: frase visible `/Datos obsoletos                                                                                                                                     | ENTRY_STALE_DATA | stale/i` · cubo oportunidades **no** trata el deny como ranking vacío silencioso (deny nombrado en inbox / reason) |
| GP-V175-03 | P1        | Mock Mercado (entry-only o cockpit pre-posición): surface con stale/deny · **0** `COMPRAR` · CTA no execute                                                                     |
| GP-V175-04 | P1        | Mock Hoy/Consola thin: instrumento/orden `UNKNOWN` (o incidente) · CTA ≠ reenviar compra · copy menciona no auto-heal **o** ausencia de heal CTA (misma honestidad V1.42/DEX-3) |
| GP-V175-05 | P1        | pytest (application o integration dryRun): `PaperDeskCycle` / policy con `permission="STALE"` · posición `held` · `reason == data_stale` · **0** sells / **0** `ExecuteTrade`   |
| GP-V175-06 | P1        | pytest: mapeo gate freshness → `ENTRY_STALE_DATA` + humanMessage no vacío (`paper_desk_entry` / daily report candidates)                                                        |
| GP-V175-07 | P2 opt    | pytest smoke: re-run acotado adversarial V1.58 (crash replay **o** duplicate event) → inserts/fills sin duplicar; **sin** ampliar día GOLDEN                                    |

### Invariantes

```
autoDesk.dryRun === true          (browser)
autoDesk.paperDExecute === false  (browser)
ENTRY_STALE_DATA ⇒ no COMPRAR ∧ no executedCount++
stale position path ⇒ data_stale ∧ 0 sells
UNKNOWN / drift ⇒ sin auto-heal de cash/holdings/PositionState
V1.74 happy-path mock sigue verde
```

### Entregables esperados (post-GO)

1. Helpers mock stale (+ opcional UNKNOWN) en `apps/web/e2e/integration.ts` / `fixtures.ts`
2. `apps/web/e2e/gp-v175-chaos-stale-no-execute-mock.spec.ts` (GP-V175-01..04)
3. pytest: ampliar o nuevo `test_v175_*` / anclar GP-V175-05..06 (+07 opt)
4. Docs: plan · auditor · relevo · actualizar `CURRENT_SYSTEM.md` + `engineering-index`

## 3. OUT

- `dryRun=false` browser execute · LIVE fills · thaw · scheduler prod
- bump package `1.35.0-beta`
- Chaos money-path masivo (500× / kill O/S) — ya cerrado post-v1.3; **no** reabrir
- Encolar `STRUCTURAL_STOP` a apertura (LIVE gap V1.58)
- Rediseño Paper Desk / Daily Desk UI
- Sustituir o reescribir V1.58 GOLDEN-DAY-ADV
- Stamp CI GREEN obligatorio (certificación = mock local + pytest opt-in, como V1.74)

## 4. Pre-flight (propuesto)

```bash
# Mock (certificación cierre)
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v175

# Regresión día feliz
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v174

# pytest (local)
pnpm --filter @bolsa/api-python test -- -k "v175 or stale_deny or ENTRY_STALE" -q
# o archivo dedicado post-GO:
# pnpm --filter @bolsa/api-python test -- tests/integration/test_v175_chaos_stale_no_execute.py -m integration

pnpm --filter @bolsa/web exec tsc --noEmit
```

## 5. Decisiones GO (2026-09-02)

1. **GP-V175-03 Mercado** — **P1 obligatorio**.
2. **GP-V175-07** — **adversarial smoke** incluido (crash replay / duplicate corto; no reescribir GOLDEN-DAY-ADV).
3. **Fixture** — helper **`installHoyStaleNoExecuteMocks` separado** (no contaminar V1.74 `hoyDay`).
