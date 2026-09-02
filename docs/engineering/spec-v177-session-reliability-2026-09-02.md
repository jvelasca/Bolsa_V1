# Spec — V1.77 Session Reliability / Operational Truth Certification

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + E2E mock locales · commit `1f25d351`; **sin stamp CI GREEN**).  
> **Padre:** [`spec-v176-certification-hardening-2026-09-02.md`](./spec-v176-certification-hardening-2026-09-02.md) · relevo [`traspaso-relevo-v1-76-certification-hardening-2026-09-02.md`](./traspaso-relevo-v1-76-certification-hardening-2026-09-02.md).  
> **Partida tip:** **V1.76** Certification Hardening [`bf6ba462`](https://github.com/jvelasca/Bolsa_V1/commit/bf6ba462) (post V1.75 `b5b114ff`). **Commit:** [`1f25d351`](https://github.com/jvelasca/Bolsa_V1/commit/1f25d351). **No** LIVE.

Una certificación **journey-style** (mock E2E) que une identidad multi-instrumento (V1.73) con fail-closed stale / UNKNOWN (V1.75–V1.76) y añade **verdad operativa** en cada transición. No es un reloj de sesión de producción ni el golden MERCADO→EXIT completo.

```text
A → B → C → A
→ refresh
→ stale
→ recovery
→ UNKNOWN
→ recon drift
→ back to clean
```

En **cada** transición asertar identidad + verdad operativa:

| Eje            | Señales                                                                                       |
| -------------- | --------------------------------------------------------------------------------------------- |
| Identidad      | `instrumentId` · `symbol` · `positionId` · `tradePlanId` · `decisionId`                       |
| HUD / fase     | `data-phase` / phase label · precio actual · stop · T1 · T2                                   |
| Acción         | `primaryAction` (POV / Decision Surface) · CTA visible ≠ COMPRAR ambiguo                      |
| Explainability | panel WHY (`decision-explain-*` / `operativa-cockpit-why`) **si** la superficie está presente |
| Reconciliación | `operativa-cockpit-recon` · `data-recon` · copy REVISAR cuando aplique                        |

Regla absoluta: **NINGÚN estado ambiguo → COMPRAR**.

```text
P0  GP-V177-01 — A→B→C→A: identidad + verdad operativa rematch (sin residual)
P0  GP-V177-02 — Refresh: foco conserva identidad + phase/levels/primaryAction/recon
P0  GP-V177-03 — Stale: transición → BLOCKED/ENTRY_STALE · 0 COMPRAR · IDs intactos
P1  GP-V177-04 — Recovery post-stale: superficie deja deny stale sin inventar COMPRAR
P1  GP-V177-05 — UNKNOWN: lifecycle unknown · REVISAR · no resend · 0 COMPRAR · IDs
P1  GP-V177-06 — Recon drift: data-recon ≠ OK · REVISAR · 0 COMPRAR · IDs del foco
P1  GP-V177-07 — Clean: recon OK · freshness current · primaryAction coherente · 0 COMPRAR ambiguo
P2  GP-V177-08 — (opt) nits V1.76: incident wire · data-status current · badge freshness attr
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler prod · sin bump `1.35.0-beta` · sin `dryRun=false` browser · sin stamp CI GREEN obligatorio.  
V1.72–V1.76 intactos (WHY · multi-instrument · Paper Day · stale/UNKNOWN spine · certification hardening).

Regla: `Ranking ≠ Signal ≠ Proposal ≠ Authorization ≠ Order ≠ Fill`.  
Stale deny **≠** UNKNOWN **≠** recon drift. Cada modo tiene contrato visible propio; ninguno verdea COMPRAR por apariencia compatible.

Preferencia de certificación: **mock E2E** que extiende fixtures/helpers V1.73 + V1.75/76 — **no** full production session clock.

## 1. Semántica por transición

| Transición  | Contrato visible (mínimo)                                                                                                                                                                                                             |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A→B→C→A     | Chart + cockpit + lista: IDs/símbolo/posición rematch fixture activa · phase `posicion` (si qty) · stop/T1/T2 ≈ fixture · `primaryAction` display-only coherente · `data-recon` OK o ausente-no-CRITICAL · 0 COMPRAR en foco posición |
| Refresh     | Tras `reload` + re-seed del foco B: mismos IDs/niveles/phase · sin residual de A                                                                                                                                                      |
| Stale       | `freshness`/data-status stale **o** candidato `ENTRY_STALE_DATA` · CTA/attention BLOCKED · frase Datos obsoletos cuando superficie Hoy · **0 COMPRAR** · identidad del instrumento pedido intacta                                     |
| Recovery    | Mock vuelve a `current` / quita deny stale · **no** aparece COMPRAR solo por recovery · identidad estable                                                                                                                             |
| UNKNOWN     | `ord-unknown-001` (o equivalente aislado) · lifecycle `unknown` · REVISAR / no reenviar · **0 COMPRAR** · sin auto-heal                                                                                                               |
| Recon drift | `data-recon` ATTENTION\|CRITICAL · copy REVISAR / drift · **0 COMPRAR** · IDs del foco                                                                                                                                                |
| Clean       | `data-recon` OK (o ausente-no-CRITICAL) · data-status `current` del instrumento · primaryAction ≠ BLOQUEADO por stale/drift · **ningún** CTA COMPRAR ambiguo                                                                          |

## 2. IN

| ID         | Pri    | Comportamiento                                                                                                                                                                                                                                                                                                                                                                    |
| ---------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GP-V177-01 | P0     | Mock Mercado multi (≥3 PAPER): click A→B→C→A. En cada foco: `chart-indicators-zone` + `operativa-cockpit` + list row comparten `instrumentId`/`symbol`/`positionId`; si fixture trae plan: `data-trade-plan-id` / `data-decision-id`; phase + stop/T1/T2 visibles alineados; `primaryAction` label presente y **≠** COMPRAR; WHY visible si panel montado; **0** botones COMPRAR. |
| GP-V177-02 | P0     | Foco en B → `page.reload()` + re-seed storage chart B → rematch identidad + phase + levels + recon del foco B (sin residual A).                                                                                                                                                                                                                                                   |
| GP-V177-03 | P0     | Desde foco limpio (o Hoy stub): inyectar stale (Mercado `data-status` stale **y/o** Hoy `ENTRY_STALE_DATA`) → superficie BLOCKED / Datos obsoletos · **0 COMPRAR** · IDs del instrumento pedido sin contaminar vecinos.                                                                                                                                                           |
| GP-V177-04 | P1     | Tras GP-V177-03: mock recovery a freshness `current` / quita deny · assert recovery **sin** inventar COMPRAR · IDs estables · (si cockpit) phase coherente.                                                                                                                                                                                                                       |
| GP-V177-05 | P1     | Fixture UNKNOWN aislada (reusar `hoyUnknown` / `ord-unknown-001` o Mercado thin): lifecycle `unknown` · Orden desconocida / no reenviar · REVISAR · **0 COMPRAR** / resend / auto-heal · identidad intacta.                                                                                                                                                                       |
| GP-V177-06 | P1     | Mock recon drift en foco activo: `operativa-cockpit-recon` `data-recon` ATTENTION\|CRITICAL · CTA/copy REVISAR · **0 COMPRAR** · `instrumentId`/`positionId` del foco.                                                                                                                                                                                                            |
| GP-V177-07 | P1     | Tras drift: mock limpia recon → `data-recon` OK (o no CRITICAL) · data-status `current` · primaryAction coherente con POSITION limpia · **0 COMPRAR** ambiguo.                                                                                                                                                                                                                    |
| GP-V177-08 | P2 opt | Endurecer nits V1.76 (no blockers): assert wire de incidente vacío/aislado cuando contrato lo pide; assert explícito `data-status.freshnessStatus===current` en tramo clean; assert badge `chart-data-status` `data-freshness-status` en stale y clean.                                                                                                                           |

### Invariantes

```
autoDesk.dryRun === true                    (si superficie Hoy en el journey)
autoDesk.paperDExecute === false
estado ambiguo (stale | UNKNOWN | recon drift | recovery incompleta)
  ⇒ 0 botones COMPRAR ∧ CTA ≠ execute feliz
activeChart.instrumentId
  == listRow.data-instrument-id
  == chart-indicators-zone.data-instrument-id
  == operativa-cockpit.data-instrument-id
  == operativa-cockpit.data-symbol (fixture)
stale ≠ UNKNOWN ≠ recon drift (contratos DOM/API distintos)
V1.73 / V1.74 / V1.75 / V1.76 mock siguen verdes (regresión)
```

### Entregables esperados (post-GO implementación)

1. Helpers journey / assert operational truth en `apps/web/e2e/integration.ts` + `fixtures.ts` (extender, **sin** mega-split)
2. `apps/web/e2e/gp-v177-session-reliability-mock.spec.ts` (GP-V177-01..07; 08 opt)
3. Docs cierre: auditor · relevo · `CURRENT_SYSTEM.md` · engineering-index (**solo en cierre**, no en esta apertura)

## 3. OUT

- Golden session completa MERCADO → candidato → ENTRY → STALE → REVISAR → recovery → ENTRY válido → Paper execution → POSITION → T1 → T2 → TRAIL → RECON DRIFT → REVISAR → reconciliación → POSITION limpia → EXIT (**candidato V1.78+** / madurez aspiracional)
- LIVE · scheduler prod · bump `1.35.0-beta` · `dryRun=false` browser
- Stamp CI GREEN remoto obligatorio (Playwright mock no corre en `frontend-ci.yml`)
- Rewrite Decision Engine / Paper Desk / motor de fases
- Split masivo de `apps/web/e2e/integration.ts` (salvo P2 posterior si el helper journey lo exige por tamaño — **no** en scope P0)
- Inferencia WHY desde strings (`alcista` / `bull`)
- Gate estructurado `_gate_reason_code` (`DATA_STALE` → `ENTRY_STALE_DATA`) — sigue OUT de V1.76
- Reloj de sesión producción / scheduler de día operativo real

## 3bis. Benchmark aspiracional (fuera de slice)

Documentado para madurez; **no** es DoD de V1.77:

```text
MERCADO → candidato → ENTRY → STALE → REVISAR → recovery
→ ENTRY válido → Paper execution → POSITION → T1 → T2 → TRAIL
→ RECON DRIFT → REVISAR → reconciliación → POSITION limpia → EXIT
```

V1.77 certifica el **núcleo reliability** (identidad + fail-closed + recon/clean) en mock. El golden largo es **V1.78+**.

## 4. Pre-flight (propuesto post-implementación)

```bash
# Certificación V1.77
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v177

# Regresión identidad / stale / hardening
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v173
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v175
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v176
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v174

pnpm --filter @bolsa/web exec tsc --noEmit
```

## 5. Decisiones GO (apertura docs 2026-09-02)

1. **Slice** = mock E2E journey A→B→C→A→refresh→stale→recovery→UNKNOWN→recon→clean.
2. **GP-V177-01..03** = P0; **04..07** = P1; **08** = P2 opt (nits V1.76).
3. **Golden MERCADO→EXIT** = OUT / V1.78+.
4. **Partida** = V1.76 pending commit (post-`b5b114ff`); package `1.35.0-beta` sin bump.
