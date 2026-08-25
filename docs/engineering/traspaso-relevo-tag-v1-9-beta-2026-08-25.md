# RELEVO — tag v1.9-beta → auditoría (2026-08-25)

> **Padre:** [`audit-pack-estado-global-2026-08-25-v19.md`](./audit-pack-estado-global-2026-08-25-v19.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN.** Tag `v1.9-beta` para auditar Operational Core + Release tag CI.
> **Arranque chat nuevo:** este fichero + pack v19 + ADR-032 + `CURRENT_SYSTEM.md`.

---

## 0. Confirmación

- F1–F4 + ExitPermission + INFRA CI-by-tag: **código + tests + stamp**.
- Planes nuevos de modelo: **ninguno** obligatorio tras este tag (wire/broker = fase explícita).

## 1. Release

| Pieza        | Valor                                        |
| ------------ | -------------------------------------------- |
| Tag          | `v1.9-beta` → `7d90d965`                     |
| Previo       | `v1.8.1-beta` → `e78fbb9`                    |
| Pack auditor | `audit-pack-estado-global-2026-08-25-v19.md` |
| Spine        | `pnpm test:decision-spine` **217**           |
| Shared       | `@bolsa/shared` **134**                      |
| CI tag       | `release-tag-ci.yml` (sin path-filter)       |

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · broker **no** · thin 5.x/8.x congelados · `PAPER_D_EXECUTE` default off · BETA.

## 3. E1

1. Auditar contra pack v19 + tag + Actions GREEN.
2. Seguir SEMI · o wire ExitPermission→Execution (plan) · o broker (mucho más tarde).
3. No módulos thin nuevos.
