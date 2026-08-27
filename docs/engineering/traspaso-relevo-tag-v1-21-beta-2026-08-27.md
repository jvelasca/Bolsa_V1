# RELEVO — tag v1.21-beta → auditoría (2026-08-27)

> **Padre:** [`audit-pack-estado-global-2026-08-27-v121.md`](./audit-pack-estado-global-2026-08-27-v121.md) · [`traspaso-relevo-v1-21-coherence-2026-08-27.md`](./traspaso-relevo-v1-21-coherence-2026-08-27.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — tag `v1.21-beta` (tip SHA pin post-commit). **Release tag CI:** pendiente de pin tras Actions GREEN.
> **Arranque chat nuevo / auditor:** pack v121 + ADR-041 + ADR-040 §7 + `CURRENT_SYSTEM.md` + este relevo.

---

## 0. Confirmación

- **Estudio Daily Ops · OperationalPlanView · stop vigente · T1 · AdminRail · higiene cuentas · trailing advisory:** código + tests + pack v121.
- DEX-1…DEX-5 **intactos**. Confirm = firma.
- Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- Cerrado vs v1.20: coherencia operativa (universo Estudio, un plan visual, un stop, AdminRail, OP-08 close extras, trail UI advisory).
- Deuda abierta: OpportunityScore · correlación/VaR · V118 B-read · backtest≠policy · thaw — **no pedir al auditor nuevos motores**.

## 1. Release

| Pieza        | Valor                                                                                                      |
| ------------ | ---------------------------------------------------------------------------------------------------------- |
| Tag          | `v1.21-beta` → tip (pin SHA abajo tras commit)                                                             |
| Previo       | `v1.20-beta` → `4c0bfe7b`                                                                                  |
| Pack auditor | [`audit-pack-estado-global-2026-08-27-v121.md`](./audit-pack-estado-global-2026-08-27-v121.md)             |
| Daily ops    | `pnpm test:daily-ops:offline` **1159** (6 fases)                                                           |
| Spine        | `pnpm test:decision-spine` **497**                                                                         |
| ADR          | [ADR-041](../adr/041-operational-coherence.md) · [ADR-040](../adr/040-user-information-architecture.md) §7 |
| CI tag       | pendiente pin                                                                                              |

### Owner: publicar

```bash
git push origin main
git tag v1.21-beta
git push origin v1.21-beta  # Actions → GREEN → pin docs CI URL
```

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm test:daily-ops:offline
pnpm test:decision-spine
# expect: daily-ops 6 fases OK (≥1145; local 1159) · spine 497
```

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · LIVE experimental · Accept estricto parked · AUTO on no · scenario ≠ permiso · Opportunity ≠ Permission · Stress ≠ permiso · trail thin ≠ autoridad · OpportunityScore aparcado · BETA.

## 4. Preguntas de foco (auditor)

1. ¿Estudio es el único universo Daily Ops?
2. ¿Un stop vigente?
3. ¿AdminRail ≠ ⚙?
4. ¿T1 idempotente?
5. ¿Freeze SEMI intacto?

## 5. Next (post-auditoría)

Elegir **un** epic: OpportunityScore · Stress correlación · V1.18 B-read/backfill · Lab backtest≠policy. No mezclar con thaw/AUTO sin palabra explícita. UX: no añadir puertas L1 ni barras en Trading.
