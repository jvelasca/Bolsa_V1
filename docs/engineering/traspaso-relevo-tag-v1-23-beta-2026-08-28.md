# RELEVO — tag v1.23-beta → auditoría (2026-08-28)

> **Padre:** [`traspaso-relevo-v1-23-ux-consolidation-2026-08-27.md`](./traspaso-relevo-v1-23-ux-consolidation-2026-08-27.md) · [ADR-040](../adr/040-user-information-architecture.md) §9 · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — tag `v1.23-beta` → tip `4bc7426c` (feat `2ff759fe` + ruff `4bc7426c`). **Release tag CI:** [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33122128224).
> **Arranque chat nuevo / auditor:** relevo V1.23 + ADR-040 §9 + diseño Mercado 2.0 + este relevo.

---

## 0. Confirmación

- **Estudio ok/empty/unavailable · H2 T1 cockpit · funnel as-of · Mercado Estudio-first · InstrumentOperationalContext · Hoy inbox 4 niveles · Prioridad ≠ orden · Asesor explains:** código + tests + §4 local + CI tag.
- DEX-1…DEX-5 **intactos**. Confirm = firma.
- Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- Cerrado vs v1.22: consolidación UX operativa (cockpit, inbox Hoy, overlays plan, H1 en offline) **sin motores nuevos**.
- Deuda abierta: OpportunityScore · correlación/VaR · batch propose · promover trail · grid Cobertura 180 · thaw — **no mezclar**.

## 1. Release

| Pieza     | Valor                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Tag       | `v1.23-beta` → `4bc7426c`                                                                                        |
| Previo    | `v1.21-beta` → `dad8f51c` (V1.22 en main sin tag beta dedicado)                                                  |
| Relevo    | [`traspaso-relevo-v1-23-ux-consolidation-2026-08-27.md`](./traspaso-relevo-v1-23-ux-consolidation-2026-08-27.md) |
| Daily ops | `pnpm test:daily-ops:offline` PASS (6 fases; H1 en `py-operativa`)                                               |
| Spine     | `pnpm test:decision-spine` **497**                                                                               |
| ADR       | [ADR-040](../adr/040-user-information-architecture.md) §9                                                        |
| CI tag    | [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33122128224)                                           |

### Owner: publicar

```bash
git push origin main
git tag v1.23-beta
git push origin v1.23-beta  # Actions → GREEN → pin docs CI URL
```

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm test:daily-ops:offline
pnpm test:decision-spine
```

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · LIVE experimental · Accept estricto parked · AUTO on no · trail thin ≠ autoridad · OpportunityScore aparcado · BETA.

## 4. Preguntas de foco (auditor)

1. ¿Hoy es solo atención (inbox), sin pestaña Confirmar?
2. ¿Mercado: listas → niveles en gráfico → panel contextual → Confirm sin salir?
3. ¿T1 tocado ≠ gestionado?
4. ¿as-of null sin scan?
5. ¿Freeze SEMI intacto?

## 5. Next (post-auditoría)

Elegir **un** epic. No mezclar OpportunityScore / thaw / AUTO sin palabra explícita.
