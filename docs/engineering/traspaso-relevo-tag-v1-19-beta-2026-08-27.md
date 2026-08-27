# RELEVO — tag v1.19-beta → auditoría (2026-08-27)

> **Padre:** [`audit-pack-estado-global-2026-08-27-v119.md`](./audit-pack-estado-global-2026-08-27-v119.md) · [`traspaso-relevo-tag-v1-18-beta-2026-08-27.md`](./traspaso-relevo-tag-v1-18-beta-2026-08-27.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — tag `v1.19-beta` → tip feature `c30594e`. **Release tag CI:** pendiente pin tras Actions GREEN.
> **Arranque chat nuevo / auditor:** pack v119 + ADR-037/039 + `CURRENT_SYSTEM.md` + este relevo · plan [`plan-v119-opportunity-discovery-2026-08-27.md`](./plan-v119-opportunity-discovery-2026-08-27.md).

---

## 0. Confirmación

- **Opportunity Discovery · Mesa L3 · Scan opt-in · Zona 1 redirects:** código + tests + pack v119.
- DEX-1…DEX-5 **intactos**. Confirm = firma.
- Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- Cerrado vs v1.18: ranking ≠ Action Queue · Quality cableada · funnel · scan diario OFF · Mesa unifica Libro/Spine.
- Deuda abierta: OpportunityScore V1.20 · correlación/VaR · V118 B-read · backtest≠policy · thaw.

## 1. Release

| Pieza        | Valor                                                                                              |
| ------------ | -------------------------------------------------------------------------------------------------- |
| Tag          | `v1.19-beta` → `c30594e`                                                                           |
| Previo       | `v1.18-beta` → `4d1b2e6`                                                                           |
| Pack auditor | [`audit-pack-estado-global-2026-08-27-v119.md`](./audit-pack-estado-global-2026-08-27-v119.md)     |
| Spine        | `pnpm test:decision-spine` **497**                                                                 |
| Plan         | [`plan-v119-opportunity-discovery-2026-08-27.md`](./plan-v119-opportunity-discovery-2026-08-27.md) |
| CI tag       | pendiente (pin URL tras GREEN)                                                                     |

### Owner: publicar

```bash
git push origin main
git tag v1.19-beta
git push origin v1.19-beta  # Actions → GREEN → pin docs CI URL
```

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/shared build
pnpm test:decision-spine
# expect: 497 passed

pnpm --filter @bolsa/shared exec vitest run opportunity-evidence opportunity-ranking operational-priority mesa-hoy-model
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm --filter @bolsa/web test -- mesa-hoy mesa-candidates daily-nav decision-board mesa-zone1
python -m pytest packages/py/application/tests/test_opportunity_daily_discovery.py -q
```

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · LIVE experimental · Accept estricto parked · AUTO on no · scenario ≠ permiso · Opportunity ≠ Permission · Stress ≠ permiso · Decision Board ≠ screener · BETA.

## 4. Next (post-auditoría)

Elegir **un** epic: OpportunityScore V1.20 · Stress correlación · V1.18 B-read/backfill · Lab backtest≠policy. No mezclar con thaw/AUTO sin palabra explícita.
