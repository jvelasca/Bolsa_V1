# RELEVO — tag v1.26-beta → auditoría / siguiente chat (2026-08-28)

> **Padre:** [`traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md`](./traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **PUBLICACIÓN** — tag `v1.26-beta` (SHA se pincha al crear el tag).  
> **Siguiente código:** V1.27 Position Operating Model — [`roadmap-v127-path-to-10-2026-08-28.md`](./roadmap-v127-path-to-10-2026-08-28.md).  
> **Estudio AUTO+gráfico:** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) §8 **Aplazado** — **sin drag / sin AUTO ampliado**.

---

## 0. Confirmación

- Geometría fail-closed · `signedStop` round-trip · `stop_invalid` DENY · what-if `candidateSector` · nacimiento SEMI (`test_v126_semi_position_birth`): **código + tests**.
- Confirm = firma. `PAPER_D_EXECUTE` default **OFF**. AUTO **off**. LLM no ejecuta. Gráfico **G0**.
- Cerrado vs v1.25: **position lifecycle integrity** (el fill SEMI graba lo firmado).
- Deuda abierta: V1.27 POM · V1.28 cockpit/toasts · Lab `risk_policy` · Frente A/B hasta N4 + §8 ACUERDO — **no mezclar**.

## 1. Release

| Pieza   | Valor                                                                                                                                                     |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tag     | `v1.26-beta` (ver SHA al pie tras `git tag`)                                                                                                              |
| Previo  | `v1.25-beta` → `d3c2fd6b`                                                                                                                                 |
| Feat    | `8b3dfb67` V1.26 lifecycle + estudio AUTO/chart                                                                                                           |
| Relevo  | [`traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md`](./traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md)                  |
| Roadmap | [`roadmap-v127-path-to-10-2026-08-28.md`](./roadmap-v127-path-to-10-2026-08-28.md)                                                                        |
| Estudio | §8 Aplazado · [Deep](./respuesta-auditor-Deep-operativa-auto-grafico-2026-08-28.md) · [A0](./respuesta-auditor-A0-position-operating-model-2026-08-28.md) |
| Spine   | `pnpm test:decision-spine` **512** (2026-08-28 local)                                                                                                     |
| Shared  | `pnpm --filter @bolsa/shared test` **418**                                                                                                                |
| Web tsc | `pnpm --filter @bolsa/web exec tsc --noEmit` OK                                                                                                           |

### Owner: publicar

```bash
git push origin main
git tag v1.26-beta
git push origin v1.26-beta
```

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · AUTO off · trail thin ≠ autoridad · **sin drag gráfico** · nav L1 congelada · BETA.

## 3. Next

**Un** epic: V1.27 Position Operating Model (`PositionDecision` proyección + ExitPolicy en plantillas + Golden Path). No thaw/AUTO/drag.
