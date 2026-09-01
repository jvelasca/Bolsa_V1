# RELEVO — tag v1.60-beta → auditoría / CI (2026-09-02)

> **Padre:** [`spec-v160-ux-mercado-2026-09-02.md`](./spec-v160-ux-mercado-2026-09-02.md) · [`traspaso-relevo-v1-60-ux-mercado-2026-09-02.md`](./traspaso-relevo-v1-60-ux-mercado-2026-09-02.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **tag emitido** — tip `v1.60-beta` → `7ac8ad9b`.  
> **Arranque auditor:** [`arranque-auditor-v1-60-ux-mercado-2026-09-02.md`](./arranque-auditor-v1-60-ux-mercado-2026-09-02.md).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · scheduler · package bump · CI integration obligatorio en Release-tag.

---

## 0. Confirmación

Sobre tip previo `v1.59-beta` → `b5c5c6ab`:

| Pieza          | Entrega                                                         |
| -------------- | --------------------------------------------------------------- |
| GP-V160-01..04 | Tarjeta estrella POV en DECISIÓN · hook · vitest                |
| Wire           | `operativa-cockpit-card` + fase T2/recon · recon chip POV-aware |
| V1.59 stack    | intacto (integration **7**)                                     |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta`.

## 1. Release

| Pieza      | Valor                                                            |
| ---------- | ---------------------------------------------------------------- |
| Tag tip    | `v1.60-beta` → `7ac8ad9b`                                        |
| Previo tip | `v1.59-beta` → `b5c5c6ab`                                        |
| CI tag     | **pendiente** — Release-tag CI tras `git push origin v1.60-beta` |

## 2. Pre-flight

Ver [`plan-v160-ux-mercado-2026-09-02.md`](./plan-v160-ux-mercado-2026-09-02.md). Local post close-out (2026-09-02):

| Suite                    | Resultado     |
| ------------------------ | ------------- |
| shared vitest POV        | **18** passed |
| web vitest Mercado       | **40** passed |
| pytest V1.59 integration | **7** passed  |
| pytest V1.58 block       | **13** passed |
| tsc web                  | OK            |

## 3. Auditoría

**Alcance:** UX Mercado POV tarjeta estrella (GP-V160-01..04). **No** sustituye Golden Session · **no** Playwright CI obligatorio · **no** cambia wire HTTP V1.59.

## 4. Next

1. **NO LIVE** · scheduler · package bump · encolar STRUCTURAL_STOP a apertura.
2. Thaw Accept · TRUSTED_PROXIES producción.
