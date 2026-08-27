# RELEVO — tag v1.17.1-beta → auditoría (2026-08-27)

> **Padre:** [`audit-pack-estado-global-2026-08-27-v1171.md`](./audit-pack-estado-global-2026-08-27-v1171.md) · [`traspaso-relevo-tag-v1-17-beta-2026-08-27.md`](./traspaso-relevo-tag-v1-17-beta-2026-08-27.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — tag `v1.17.1-beta` (hardening + refino Mesa). SHA stamp en `CURRENT_SYSTEM` tras tag.
> **Arranque chat nuevo / auditor:** pack v1171 + plan-v1171 + ADR-038/039 + `CURRENT_SYSTEM.md` + este relevo.

---

## 0. Confirmación

- **H1…H6 + R1…R5:** código + tests + pack v1171.
- DEX-1…DEX-5 **intactos**. Confirm = firma.
- Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- Deuda cerrada vs v1.17: Router sanity · EdgeReport paper_auto · Redis SHA256 · stubs 1R/`*10`.
- Deuda abierta: Stress stub · Opportunity · V1.18 lineage · backtest≠policy · thaw.

## 1. Release

| Pieza        | Valor                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------ |
| Tag          | `v1.17.1-beta`                                                                                   |
| Previo       | `v1.17-beta` → `62ebc4f`                                                                         |
| Pack auditor | [`audit-pack-estado-global-2026-08-27-v1171.md`](./audit-pack-estado-global-2026-08-27-v1171.md) |
| Spine        | `pnpm test:decision-spine` **495**                                                               |
| Plan         | [`plan-v1171-hardening-2026-08-27.md`](./plan-v1171-hardening-2026-08-27.md)                     |
| CI tag       | `release-tag-ci.yml` (sin path-filter)                                                           |

### Owner: publicar

```bash
git tag v1.17.1-beta
git push origin main v1.17.1-beta  # Actions → GREEN → pin docs CI URL
```

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/shared build
pnpm test:decision-spine
# expect: 495 passed

pnpm --filter @bolsa/shared exec vitest run portfolio-risk-metrics portfolio-scenario investment-position-aggregate operational-priority mesa-next-action mesa-hoy-model
pnpm --filter @bolsa/web test -- mesa-hoy
```

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · LIVE experimental · Accept estricto parked · AUTO on no · scenario ≠ permiso · BETA.

## 4. Next (post-auditoría)

Elegir **un** epic: refinamiento Mesa residual · **V1.18** lineage Position→DecisionPackage · Stress Risk · Opportunity Engine. No mezclar con thaw/AUTO sin palabra explícita.
