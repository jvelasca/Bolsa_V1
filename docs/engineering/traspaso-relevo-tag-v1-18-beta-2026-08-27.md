# RELEVO — tag v1.18-beta → auditoría (2026-08-27)

> **Padre:** [`audit-pack-estado-global-2026-08-27-v118.md`](./audit-pack-estado-global-2026-08-27-v118.md) · [`traspaso-relevo-tag-v1-17-1-beta-2026-08-27.md`](./traspaso-relevo-tag-v1-17-1-beta-2026-08-27.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **STAMP / PUBLICACIÓN** — tag `v1.18-beta` → tip feature `4d1b2e6` (L1+L2a + MR-1 + Stress MVP + OpportunityEvidence). **Release tag CI:** _pendiente push_.
> **Arranque chat nuevo / auditor:** pack v118 + ADR-038/039 + `CURRENT_SYSTEM.md` + este relevo.

---

## 0. Confirmación

- **L1+L2a · MR-1 · Stress MVP · OpportunityEvidence V1:** código + tests + pack v118.
- DEX-1…DEX-5 **intactos**. Confirm = firma.
- Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- Cerrado vs v1.17.1: lineage Position→Package · originThesis · Mesa honesty residual · Stress cota · Opportunity contrato.
- Deuda abierta: correlación/VaR · Opp UI/wire · V118 B-read/backfill · backtest≠policy · thaw.

## 1. Release

| Pieza        | Valor                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------- |
| Tag          | `v1.18-beta` → `4d1b2e6`                                                                       |
| Previo       | `v1.17.1-beta` → `e0ae633` (git tag `9c98fb8`)                                                 |
| Pack auditor | [`audit-pack-estado-global-2026-08-27-v118.md`](./audit-pack-estado-global-2026-08-27-v118.md) |
| Spine        | `pnpm test:decision-spine` **497**                                                             |
| Planes       | L1 · L2a · MR-1 · Stress MVP · OpportunityEvidence                                             |
| CI tag       | _pin URL tras GREEN_                                                                           |

### Owner: publicar

```bash
git push origin main
git tag v1.18-beta
git push origin v1.18-beta  # Actions → GREEN → pin docs CI URL
```

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/shared build
pnpm test:decision-spine
# expect: 497 passed

pnpm --filter @bolsa/shared exec vitest run portfolio-risk-metrics portfolio-scenario investment-position-aggregate operational-priority mesa-next-action mesa-hoy-model opportunity-evidence position-lineage data-freshness
pnpm --filter @bolsa/web test -- mesa-hoy mesa-position
```

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · LIVE experimental · Accept estricto parked · AUTO on no · scenario ≠ permiso · Opportunity ≠ Permission · Stress ≠ permiso · BETA.

## 4. Next (post-auditoría)

Elegir **un** epic: Opp UI/wire Priority · Stress correlación · V1.18 B-read/backfill · Lab backtest≠policy. No mezclar con thaw/AUTO sin palabra explícita.
