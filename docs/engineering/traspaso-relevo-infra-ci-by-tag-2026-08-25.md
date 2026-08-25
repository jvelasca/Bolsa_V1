# RELEVO — INFRA CI-by-tag · 2026-08-25

> **Padre:** [`plan-infra-ci-by-tag-2026-08-25.md`](./plan-infra-ci-by-tag-2026-08-25.md) · roadmap [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO.** Workflow `release-tag-ci.yml`. Spine local **203**. Cambiar de chat recomendado para ExitPermission / SEMI / tag `v1.9-beta` (owner).
> **Arranque chat nuevo:** este fichero + plan INFRA + `CURRENT_SYSTEM.md` + roadmap v1.9 + triage §4.

---

## 0. Qué quedó hecho

| Pieza                                                         | Estado       |
| ------------------------------------------------------------- | ------------ |
| `.github/workflows/release-tag-ci.yml` (`v*` sin path-filter) | **Hecho**    |
| Jobs: security · shared · spine · frontend · python           | **Hecho**    |
| `certify` + artefacto `release-tag-ci-summary.json`           | **Hecho**    |
| `contract:check` (no gen)                                     | **Hecho**    |
| Path-filters diarios tocados                                  | **No**       |
| Tag `v1.9-beta` creado                                        | **No**       |
| ExitPermission / broker                                       | **No**       |
| F1–F4 modelo                                                  | **Intactos** |

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **off**. Broker **no**.
- CI diario path-filter **intacta**.
- Primer GREEN real = al pushear un tag `v*` (o `workflow_dispatch`).

## 2. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** plan D1–D8 **ExitPermission** (veto salida; ≠ auto-exit).
2. **Opción B:** operar SEMI. No reabrir thin.
3. **Opción C:** owner crea tag `v1.9-beta` cuando quiera certificar (este workflow debe quedar GREEN).
4. **No** broker adapter. **No** ActionabilityScore. **No** auto-exit producto.

## 3. Docs clave

- [`plan-infra-ci-by-tag-2026-08-25.md`](./plan-infra-ci-by-tag-2026-08-25.md)
- [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml)
- triage [`audit-ext-v181-triage-2026-08-25.md`](./audit-ext-v181-triage-2026-08-25.md) §4
- ADR-032 · `CURRENT_SYSTEM.md` · roadmap v1.9
