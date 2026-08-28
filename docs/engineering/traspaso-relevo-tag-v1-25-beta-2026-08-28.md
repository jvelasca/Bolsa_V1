# RELEVO — tag v1.25-beta → auditoría / mañana (2026-08-28)

> **Padre:** [`traspaso-relevo-v1-25-operational-safety-2026-08-28.md`](./traspaso-relevo-v1-25-operational-safety-2026-08-28.md) · [`contrato-confirm-v125-ticket-2026-08-28.md`](./contrato-confirm-v125-ticket-2026-08-28.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — tag `v1.25-beta` → tip `d3c2fd6b` (docs pin `4455cee1`). **Release tag CI:** [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33149344989).
> **Arranque chat nuevo:** este relevo + contrato V1.25 + freeze SEMI · auditor externo: [`arranque-auditor-v1-25-beta-2026-08-28.md`](./arranque-auditor-v1-25-beta-2026-08-28.md).

---

## 0. Confirmación

- **Sizing único · ticket Confirm slim · riesgo €+R · what-if · stop editable · assessments avanzados · propose sin cash sizer:** código + tests locales.
- DEX-1…DEX-5 **intactos**. Confirm = firma.
- Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- Cerrado vs v1.24: **operational safety en Confirm** (una autoridad de sizing hasta firma) **sin nav nueva ni motores de ejecución**.
- Deuda abierta: V1.26 lifecycle · V1.27 Mercado operativo · V1.28 UX 10/10 · Lab risk_policy · OpportunityScore · thaw — **no mezclar**.

## 1. Release

| Pieza     | Valor                                                                                                                |
| --------- | -------------------------------------------------------------------------------------------------------------------- |
| Tag       | `v1.25-beta` → `d3c2fd6b` (feat `f8e53f57` + CI fixes)                                                               |
| Previo    | `v1.24-beta` → `c75b26a6` (tip docs `0d19e3aa`)                                                                      |
| Relevo    | [`traspaso-relevo-v1-25-operational-safety-2026-08-28.md`](./traspaso-relevo-v1-25-operational-safety-2026-08-28.md) |
| Contrato  | [`contrato-confirm-v125-ticket-2026-08-28.md`](./contrato-confirm-v125-ticket-2026-08-28.md)                         |
| Daily ops | `pnpm test:daily-ops:offline` PASS (6/6; spine 497 en fase 5)                                                        |
| Auditor   | [`arranque-auditor-v1-25-beta-2026-08-28.md`](./arranque-auditor-v1-25-beta-2026-08-28.md)                           |
| Spine     | subset daily-ops **497**                                                                                             |
| ADR       | [ADR-040 §10](../adr/040-user-information-architecture.md) · Operative Flow                                          |
| CI tag    | [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33149344989)                                               |

### Owner: publicar

```bash
git push origin main
git tag v1.25-beta
git push origin v1.25-beta  # Actions → GREEN → pin docs CI URL
```

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm test:daily-ops:offline
pnpm test:decision-spine
```

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · LIVE experimental · Accept estricto parked · AUTO on no · trail thin ≠ autoridad · OpportunityScore aparcado · BETA · nav L1 congelada · sin drag gráfico.

## 4. Preguntas de foco (auditor mañana)

1. ¿Confirm default muestra riesgo €, R y % cartera (no `riskPct={null}` con plan TRIGGERED)?
2. ¿What-if Antes→Después visible en ticket sin segundo calculador?
3. ¿Propose con plan TRIGGERED usa qty del plan (no `% caja` como SoT)?
4. ¿Stop editable invalida firma stale y recalcula R?
5. ¿Assessments bajo «Ajustes avanzados» (no bloquean ticket slim)?

## 5. Next

Elegir **un** epic: V1.26 position lifecycle **o** Lab `risk_policy` wiring. No thaw/AUTO/drag gráfico.
