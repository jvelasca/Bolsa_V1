# RELEVO — V2.10.1 CI GREEN / Certification Fix (2026-09-05)

> **Padre:** [relevo tag v2.10-beta](./traspaso-relevo-tag-v2-10-beta-2026-09-05.md) · [relevo V2.10](./traspaso-relevo-v2-10-seed-ops-2026-09-05.md) · auditoría externa tip `v2.10-beta`.  
> **Estado:** **CÓDIGO HOTFIX LISTO** · tip producto vigente sigue `v2.10-beta` · package `1.39.0-beta` (sin bump hasta tip/dispatch).  
> **Para quién:** certificación CI · **NO MÁS PANELES** · no reabrir motor FSM.  
> **Origen CI rojo:** [run 33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `conclusion=failure`.

## Objetivo

Cerrar el único bloqueo P1 de la auditoría V2.10: Release-tag CI **no certificable**.

No es regresión del motor financiero ni de V2.46–V2.53 cabina (v28/v29 ya PASS en ese run). Fallan:

1. **frontend** — 7 Vitest (copy / journal / KPI / HUD desfasados).
2. **playwright-mock** — 20 E2E (Hoy `no_operar` colapsado + `position-decision-stop` ausente con journey HUD).

## Freeze intacto

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · **NO MÁS PANELES** · package `1.39.0-beta` · **no afirmar CI GREEN sin `conclusion=success`**.

## Entrega

| ID            | Fix                                                                                              | Evidencia local                   |
| ------------- | ------------------------------------------------------------------------------------------------ | --------------------------------- |
| **Cluster A** | `expandDailyDeskBucketIfCollapsed` antes de assert deny `ENTRY_STALE_DATA` (E2E + Vitest expand) | gp-v175/176/178-03/179 stale PASS |
| **Cluster B** | `sr-only` `position-decision-stop` / t1 / t2 en rama journey de `decision-surface-compact`       | gp-v177…v183 PASS                 |
| **Frontend**  | Vitest alineados a copy cabina actual                                                            | web **1253/1253** PASS            |
| **Docs**      | este relevo · P2 diferidos · honestidad CI                                                       | —                                 |

## Smoke stamp (local 2026-09-05)

| Check                                                                           | Resultado                                                                                                                   |
| ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `pnpm --filter @bolsa/web test`                                                 | **PASS** · 1253 tests                                                                                                       |
| `E2E_RUN=1 pnpm e2e -- gp-v175 gp-v176 gp-v177 gp-v178 gp-v179 gp-v181 gp-v183` | **PASS** · 24/24                                                                                                            |
| Release-tag CI tip `v2.10-beta`                                                 | [run 33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `conclusion=failure` · **NO CERTIFICABLE** |
| Release-tag CI post-hotfix                                                      | **pendiente** commit + `workflow_dispatch` o tip `v2.10.1-beta`                                                             |

## Matriz UI Certification (honestidad · P2-01)

| Certificación               | Local Win          | CI Linux                   |
| --------------------------- | ------------------ | -------------------------- |
| Functional E2E              | sí                 | sí (tras GREEN)            |
| Keyboard / Touch / Overflow | sí                 | sí                         |
| Contrast WCAG-ish 4.5:1     | sí                 | sí                         |
| Pixel snapshots             | sí (`*-win32.png`) | **no** (`test.skip` en CI) |

CI GREEN ≠ pixel-perfect. Contrast = **Operational Contrast Smoke**, no auditoría WCAG completa (P2-02). Tipografía `text-[9px]` = metadata auxiliar, no verdad operacional (P2-03).

## OUT / Next

1. Commit hotfix (pedido explícito) · opcional tip `v2.10.1-beta` / bump `1.39.1-beta`.
2. Release-tag CI → exigir `conclusion=success` en security · shared · spine · frontend · python · playwright-mock · lifecycle-pg · certify.
3. Stamp CI **solo** con URL + `conclusion=success` → entonces V2.10 = **CERTIFICABLE**.
4. Auditoría final V2.10 — **no** V2.11 todavía.
5. No reabrir motor FSM / PAPER AUTO execute / paneles.
