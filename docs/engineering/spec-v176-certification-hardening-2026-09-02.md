# Spec — V1.76 Certification Hardening

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + E2E mock locales · **sin stamp CI GREEN**).  
> **Padre:** [`spec-v175-chaos-stale-no-execute-2026-09-02.md`](./spec-v175-chaos-stale-no-execute-2026-09-02.md) · partida **V1.75** (`b5b114ff`). **No** LIVE.

Cierra las reservas de calidad de prueba de V1.75. El motor no se rediseña: se certifica **causa**, no una apariencia compatible.

```text
P0  GP-V175-01 — stale deny = BLOCKED + ENTRY_STALE_DATA + 0 COMPRAR · NO AUTO feliz
P0  GP-V175-04 — UNKNOWN aislado (ord-unknown-001) · REVISAR · no resend · no auto-heal
P1  GP-V175-03 — data-status echo del instrumento pedido (NVDA ≠ AAPL)
P1  GP-V176-01 — causalidad Hoy: freshness stale → ENTRY_STALE_DATA → BLOCKED → 0 COMPRAR
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · **NO LIVE** · sin scheduler prod · sin bump `1.35.0-beta` · sin `dryRun=false` browser · V1.72–V1.75 intactos (WHY · multi-instrument · Paper Day · stale/no-execute spine).

Regla: `Ranking ≠ Signal ≠ Proposal ≠ Authorization ≠ Order ≠ Fill`.  
Stale deny **≠** UNKNOWN. `REVISAR` es el contrato UNKNOWN/recon, no el de `ENTRY_STALE_DATA`.

## 1. Semántica

| Caso                    | Contrato visible                                                                                                                                                                                                                                                                    |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Stale deny (Hoy)        | `attention=BLOCKED` · `reasonCode=ENTRY_STALE_DATA` · «Datos obsoletos — no proponer.» · CTA `Entradas bloqueadas` · **0 COMPRAR**. La postura global «AUTO armado · ejecución off» puede existir (`arm ≠ execute`); el candidato stale **no** puede verdear el test por esa frase. |
| UNKNOWN order (Mercado) | `orderId=ord-unknown-001` · lifecycle `unknown` · «Orden desconocida» · «no reenviar» · CTA Ver operaciones · **0 COMPRAR** · 1 intent. Sin incidente stale y sin `ENTRY_STALE_DATA`.                                                                                               |
| Mercado NVDA stale      | `GET .../instruments/inst-nvda/data-status` body `instrumentId=inst-nvda` · `freshnessStatus=stale` · cockpit NVDA · **0 COMPRAR**.                                                                                                                                                 |

## 2. IN

| ID         | Comportamiento                                                                                                                                                                                                                                                      |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GP-V175-01 | Ítem `daily-desk-item-auto-deny-inst-msft`: `data-attention=BLOCKED` · `data-reason-code=ENTRY_STALE_DATA` · frase Datos obsoletos · CTA ≠ COMPRAR ≠ AUTO armado · 0 botones COMPRAR · daily-report `dryRun=true` · `paperDExecute=false` · `humanMessage` no vacío |
| GP-V175-02 | Intacta (deny nombrado en cubo `no_operar`)                                                                                                                                                                                                                         |
| GP-V175-03 | Intercept `data-status` de NVDA: `instrumentId===inst-nvda` · `freshnessStatus===stale` · cockpit `data-instrument-id=inst-nvda` · badge `chart-data-status` misma identidad · 0 COMPRAR · **no** depende de incidente `portfolio_drift`                            |
| GP-V175-04 | Fixture `hoyUnknown` aislado: 1 intent `ord-unknown-001` · cockpit `data-execution-lifecycle=unknown` · Orden desconocida + no reenviar · CTA operaciones · 0 COMPRAR / resend / auto-heal · incidents vacíos · data-status `current`                               |
| GP-V176-01 | Cadena Hoy: `candidates[0].freshness=stale` → `reasonCode=ENTRY_STALE_DATA` → `humanMessage` ≠ empty → DOM BLOCKED + data-reason-code → 0 COMPRAR → `dryRun && !paperDExecute`. **Sin** asertar REVISAR                                                             |

### Invariantes

```
autoDesk.dryRun === true
autoDesk.paperDExecute === false
ENTRY_STALE_DATA ⇒ BLOCKED ∧ no COMPRAR ∧ no AUTO feliz en el ítem
UNKNOWN ⇒ lifecycle unknown ∧ no resend ∧ no auto-heal ∧ 1 intent
data-status.instrumentId === instrumento solicitado
V1.74 happy-path mock sigue verde
```

## 3. OUT

- V1.77 session reliability (`A→B→C→A→refresh→stale→UNKNOWN→recon`)
- Split de `apps/web/e2e/integration.ts`
- Gate estructurado `_gate_reason_code` (`DATA_STALE` → `ENTRY_STALE_DATA`)
- Inferencia WHY desde strings (`alcista` / `bull`)
- Stamp CI GREEN remoto (Playwright mock no corre en `frontend-ci.yml`)
- LIVE · scheduler · bump package · `dryRun=false` browser · nuevo motor

## 4. Pre-flight

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v175
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v176
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v174
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm --filter @bolsa/web test -- daily-desk-inbox
pnpm --filter @bolsa/shared test -- daily-desk-auto-projection
```
