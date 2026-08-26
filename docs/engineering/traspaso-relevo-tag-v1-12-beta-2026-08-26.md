# RELEVO — tag v1.12-beta → auditoría (2026-08-26)

> **Padre:** [`audit-pack-estado-global-2026-08-26-v112.md`](./audit-pack-estado-global-2026-08-26-v112.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **PUBLICACIÓN.** Tag `v1.12-beta` → `369b5d1`. **Release tag CI GREEN.** Auditoría externa recibida → OR-2 **PARTIAL** · apertura V1.13: [`traspaso-relevo-audit-ext-v112-apertura-v113-2026-08-26.md`](./traspaso-relevo-audit-ext-v112-apertura-v113-2026-08-26.md).
> **Arranque chat nuevo / auditor:** pack v112 + ADR-035 + `CURRENT_SYSTEM.md` + triage [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md).

---

## 0. Confirmación

- D0 + **OR-1…OR-6**: código + tests + stamp docs.
- Accept estricto **NO** (deuda P1–P5). `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**.
- Planes nuevos de modelo: **ninguno** obligatorio tras este tag. Thaw estricto / AUTO on / UI resolución recon = fuera.

## 1. Release

| Pieza        | Valor                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------- |
| Tag          | `v1.12-beta` → `369b5d1`                                                                       |
| Previo       | `v1.11-beta` → `76d0f951`                                                                      |
| Pack auditor | [`audit-pack-estado-global-2026-08-26-v112.md`](./audit-pack-estado-global-2026-08-26-v112.md) |
| Spine        | `pnpm test:decision-spine` **433** (2026-08-26)                                                |
| OR gates     | pytest OR **42** · vitest web **5** · vitest shared **13**                                     |
| CI tag       | `release-tag-ci.yml` (sin path-filter)                                                         |

### Owner: publicar

```bash
git tag v1.12-beta          # 369b5d1
git push origin v1.12-beta  # Actions → GREEN → pin docs SHA
```

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` default off · mesa paper · LIVE experimental · Accept estricto parked · broker producción no · AUTO on no · BETA.

## 3. E1

1. Auditar contra pack v112 + ADR-035 + tag + Actions GREEN. **Hecho** — triage [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md).
2. Opción operativa: SEMI TRIGGERED → Confirm → `Ejecutar en PAPER` · suite A–L · readiness en barra.
3. No Accept estricto sin DoD §4 + palabra **thaw**.
4. No módulos thin nuevos · no reabrir OR-1/3/4/5/6. OR-2 físico = **DEX-1** (V1.13), no reabrir OR-2 como fase v1.12.
