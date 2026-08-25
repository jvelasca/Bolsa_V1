# Plan — INFRA CI reproducible por tag (pre-v1.9-beta)

> **Padre:** [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md) · triage [`audit-ext-v181-triage-2026-08-25.md`](./audit-ext-v181-triage-2026-08-25.md) §4 · relevo F4 [`traspaso-relevo-f4-execution-plan-paper-2026-08-25.md`](./traspaso-relevo-f4-execution-plan-paper-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (D1–D8 OK) · spine partida **203**.
> **Método:** workflow de **release-tag** sin path-filter. Path-filters diarios intactos. No crea tag `v1.9-beta`.

---

## 0. Objetivo

Que un push de tag `v*` dispare gates reproducibles aunque el commit sea docs-only.

## 1. Decisiones (D1–D8) — OK

| Id     | Decisión                                                                          |
| ------ | --------------------------------------------------------------------------------- |
| **D1** | `.github/workflows/release-tag-ci.yml` nuevo. CI diario path-filter **intacta**.  |
| **D2** | Trigger: `push.tags: ['v*']` + `workflow_dispatch`.                               |
| **D3** | Jobs: security · shared · spine · frontend · python offline.                      |
| **D4** | Job `certify` + artefacto `release-tag-ci-summary.json`.                          |
| **D5** | `contract:check` (no `contract:gen`).                                             |
| **D6** | Sin Postgres; mismos ignores que `python-ci.yml`. Optimize/Fase2 no obligatorios. |
| **D7** | Stamp CURRENT_SYSTEM / CHANGELOG / roadmap / relevo.                              |
| **D8** | E1: ExitPermission · SEMI · o tag `v1.9-beta` (owner + workflow GREEN).           |

## 2. Ficheros

- `.github/workflows/release-tag-ci.yml`
- Stamp + relevo [`traspaso-relevo-infra-ci-by-tag-2026-08-25.md`](./traspaso-relevo-infra-ci-by-tag-2026-08-25.md)

## 3. Freeze (intactos)

Path-filters diarios · `PAPER_D_EXECUTE` off · broker no · thin · F1–F4 · opening/Confirm · no crear tag en este slice.
