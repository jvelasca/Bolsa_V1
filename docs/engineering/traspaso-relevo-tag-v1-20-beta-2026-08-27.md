# RELEVO — tag v1.20-beta → auditoría (2026-08-27)

> **Padre:** [`audit-pack-estado-global-2026-08-27-v120.md`](./audit-pack-estado-global-2026-08-27-v120.md) · [`traspaso-relevo-tag-v1-19-beta-2026-08-27.md`](./traspaso-relevo-tag-v1-19-beta-2026-08-27.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — tag `v1.20-beta` → tip `cb849514` (feature `a28e4a93`). **Release tag CI:** pin URL tras GREEN.
> **Arranque chat nuevo / auditor:** pack v120 + ADR-040 + ADR-037 §8 + `CURRENT_SYSTEM.md` + este relevo.

---

## 0. Confirmación

- **User IA · Nav L1 · Trading terminal · Hoy views · Continuidad drawer:** código + tests + pack v120.
- DEX-1…DEX-5 **intactos**. Confirm = firma.
- Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- Cerrado vs v1.19: arquitectura de usuario ≠ interna · strip Hoy fuera de Trading · OpportunityScore **aparcado**.
- Deuda abierta: OpportunityScore (backlog) · correlación/VaR · V118 B-read · backtest≠policy · thaw.

## 1. Release

| Pieza        | Valor                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------- |
| Tag          | `v1.20-beta` → `cb849514` (feature `a28e4a93`)                                                 |
| Previo       | `v1.19-beta` → `dc9327d`                                                                       |
| Pack auditor | [`audit-pack-estado-global-2026-08-27-v120.md`](./audit-pack-estado-global-2026-08-27-v120.md) |
| Spine        | `pnpm test:decision-spine` **497**                                                             |
| ADR          | [ADR-040](../adr/040-user-information-architecture.md)                                         |
| CI tag       | (pin tras Actions GREEN)                                                                       |

### Owner: publicar

```bash
git push origin main
git tag v1.20-beta
git push origin v1.20-beta  # Actions → GREEN → pin docs CI URL
```

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm test:daily-ops:offline
pnpm test:decision-spine
# expect: daily-ops 6 fases OK · spine 497 passed
```

Fases `test:daily-ops:offline`: shared domain · web Mesa/Confirm · web Trading desk · web CORE-R · py spine · py operativa. Manifest: `scripts/research/daily-ops-manifest.mjs`.

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · LIVE experimental · Accept estricto parked · AUTO on no · scenario ≠ permiso · Opportunity ≠ Permission · Stress ≠ permiso · Decision Board ≠ screener · OpportunityScore aparcado · BETA.

## 4. Next (post-auditoría)

Elegir **un** epic: OpportunityScore · Stress correlación · V1.18 B-read/backfill · Lab backtest≠policy. No mezclar con thaw/AUTO sin palabra explícita. UX: no añadir puertas L1 ni barras en Trading.
