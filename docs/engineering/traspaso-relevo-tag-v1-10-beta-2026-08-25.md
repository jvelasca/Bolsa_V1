# RELEVO — tag v1.10-beta → auditoría (2026-08-25)

> **Padre:** [`audit-pack-estado-global-2026-08-25-v110.md`](./audit-pack-estado-global-2026-08-25-v110.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN.** Tag `v1.10-beta` para auditar Operational Authority v1.10 (H1→P4). **Release tag CI GREEN.**
> **Arranque chat nuevo:** este fichero + pack v110 + ADR-033 + `CURRENT_SYSTEM.md` + roadmap v1.10.

---

## 0. Confirmación

- H1+H2+P1+P2+P3+P4 (Consola P4.1+P4.2): **código + tests + stamp**.
- Planes nuevos de modelo: **ninguno** obligatorio tras este tag (broker = fase explícita posterior).

## 1. Release

| Pieza        | Valor                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------- |
| Tag          | `v1.10-beta` → `047ddb6`                                                                       |
| Release base | `2ea53be2` (stamp funcional H1→P4)                                                             |
| Previo       | `v1.9-beta` → `7d90d965`                                                                       |
| Pack auditor | [`audit-pack-estado-global-2026-08-25-v110.md`](./audit-pack-estado-global-2026-08-25-v110.md) |
| Spine        | `pnpm test:decision-spine` **260**                                                             |
| Shared       | `@bolsa/shared` (ver CI)                                                                       |
| CI tag       | `release-tag-ci.yml` (sin path-filter)                                                         |

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · broker **no** · thin 5.x/8.x congelados · `PAPER_D_EXECUTE` default off · BETA.

## 3. E1

1. Auditar contra pack v110 + ADR-033 + tag + Actions GREEN.
2. Seguir SEMI operado (checklists P4) · wire broker (mucho más tarde).
3. No módulos thin nuevos.
