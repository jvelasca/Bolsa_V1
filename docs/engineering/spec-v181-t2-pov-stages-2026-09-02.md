# Spec — V1.81 T2 POV Stages (mock E2E)

> **AsOf:** 2026-09-02 · **Estado:** **ABIERTA** (implementación en paralelo; tip/commit TBD; **sin stamp CI GREEN**).  
> **Padre:** [`spec-v180-ci-green-tip-honesty-2026-09-02.md`](./spec-v180-ci-green-tip-honesty-2026-09-02.md) · relevo [`traspaso-relevo-v1-80-ci-green-tip-honesty-2026-09-02.md`](./traspaso-relevo-v1-80-ci-green-tip-honesty-2026-09-02.md).  
> **Partida tip:** **V1.80** CERRADA — tag [`v1.80-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.80-beta) → [`7bd6ed81`](https://github.com/jvelasca/Bolsa_V1/commit/7bd6ed81) · CI GREEN [run 33644966298](https://github.com/jvelasca/Bolsa_V1/actions/runs/33644966298) · docs tip [`3b5f10a0`](https://github.com/jvelasca/Bolsa_V1/commit/3b5f10a0). **No** LIVE.

Certificación **mock E2E** de stages POV `T2_READY` / `T2_EXECUTED` sobre la **misma identidad AAPL** del lifecycle V1.79. El dominio **ya** emite `T2_READY`/`T2_EXECUTED` (V1.57); esta rebanada cierra la brecha de fixtures/stages mock + un test GP-V181-01. **No** es rediseño de mesa CTA («GESTIONAR T2»).

```text
… → T1_EXECUTED → T2_READY → T2_EXECUTED → (opcional continuar lifecycle)
identidad AAPL · 0 COMPRAR
```

Regla absoluta: **NINGÚN estado ambiguo → COMPRAR**.  
`primaryAction` = **MONITOR** (UI **Mantener** / mesa MONITOR) — **intencional**. Mapping desk `T2_*` → `reduced` → APPLIED → MONITOR intacto (V1.72 GP-V172-05).

```text
P0  GP-V181-01 — Mock stateful: tras T1_EXECUTED → T2_READY → T2_EXECUTED (AAPL · 0 COMPRAR · MONITOR/Mantener)
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler prod · sin bump `1.35.0-beta` · sin `dryRun=false` browser · sin fills ledger · **sin stamp CI GREEN** obligatorio.  
V1.72–V1.80 intactos (WHY · multi-instrument · Paper Day · stale/UNKNOWN · session reliability · golden · lifecycle · tip honesty gate).  
**No** mega-split de `fixtures.ts` (overlays puntuales). **No** Playwright en `frontend-ci`. **No** integrated E2E obligatorio.

## 1. Semántica T2 (producto)

| Estado      | Contrato visible (mínimo)                                                                                          |
| ----------- | ------------------------------------------------------------------------------------------------------------------ |
| T2_READY    | `data-pov-state=T2_READY` · CTA Mantener / mesa MONITOR · IDs AAPL congelados · 0 COMPRAR                          |
| T2_EXECUTED | `data-pov-state=T2_EXECUTED` · Mantener / MONITOR · remaining coherente post-T2 · evento `T2_EXECUTED` · 0 COMPRAR |

Dominio: T2 `triggered` → `T2_READY`; T2 `executed` + remaining > 0 → `T2_EXECUTED` (V1.57).  
**No** enum `EXIT_EXECUTED`. Terminal de cierre sigue siendo `CLOSED` + `POSITION_CLOSED`.

## 2. IN

| ID         | Pri | Comportamiento                                                                                                 |
| ---------- | --- | -------------------------------------------------------------------------------------------------------------- |
| GP-V181-01 | P0  | Un test mock: stages `t2_ready` \| `t2_executed` · identidad AAPL · assert POV + MONITOR/Mantener · 0 COMPRAR. |

### Entregables técnicos

1. `E2eGoldenPositionStage += t2_ready | t2_executed` en `apps/web/e2e/helpers/golden-session.ts`
2. Overlays en `apps/web/e2e/fixtures.ts` (**sin** mega-split)
3. `apps/web/e2e/gp-v181-t2-pov-stages-mock.spec.ts` (GP-V181-01)
4. `release-tag-ci.yml` job `playwright-mock` filtro `+= |gp-v181`
5. Docs: spec · plan · arranque · relevo · CURRENT_SYSTEM · engineering-index §50

### Invariantes

```
autoDesk.dryRun === true
autoDesk.paperDExecute === false
mismo instrumentId AAPL (lifecycle V1.79)
T2_READY / T2_EXECUTED ⇒ primaryAction MONITOR ∧ UI Mantener ∧ 0 COMPRAR
NO rediseño desk «GESTIONAR T2»
V1.73–V1.80 mock / tip honesty intactos
sin stamp CI GREEN remoto hasta cierre explícito
```

## 3. OUT

- LIVE · scheduler · bump package · `dryRun=false` browser · fills ledger
- Enum `EXIT_EXECUTED` · rewrite motor
- Mega-split `fixtures.ts` (**V1.82** candidato post-cierre)
- Playwright en `frontend-ci.yml`
- E2E integrado / PG obligatorio en cada certify
- Rediseño CTA mesa `T2_*` → GESTIONAR T2
- Stamp CI GREEN remoto sin tip/commit de cierre

## 4. Pre-flight (esperado al cerrar)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v181
# → 1 passed (esperado)

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179|gp-v181"
# → curado tip honesty + V1.81 (esperado)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```
