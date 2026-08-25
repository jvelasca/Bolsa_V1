# RELEVO — Thaw BETA-D Camino D (2026-08-25)

> **Padre:** [`thaw-beta-adapted-remeasure-2026-08-25.md`](./thaw-beta-adapted-remeasure-2026-08-25.md) · [ADR-023](../adr/023-camino-d-thaw.md).  
> **AsOf:** 2026-08-25.  
> **Estado:** **THAW BETA-D CERRADO.** Estricto P1–P5 sigue FAIL (deuda).  
> **Arranque chat nuevo:** este fichero + `CURRENT_SYSTEM.md` + ADR-023.

---

## 0. Qué se hizo

| Pieza              | Resultado                                         |
| ------------------ | ------------------------------------------------- |
| Medición estricta  | FAIL — 28d · 0 SEMI · precision null · recall 0%  |
| Adaptación         | P1'–P5' + waivers W2–W4 (Informe 2 / BETA)        |
| Remeasure adaptado | **PASS**                                          |
| ADR-023            | **Accepted — BETA parcial**                       |
| Freeze §8          | Amend thaw BETA-D                                 |
| UI                 | `DEMO_BOOK_AUTO_UI_ENABLED=true`                  |
| Execute env        | Default **off**; opt-in `PAPER_D_EXECUTE=1` local |

## 1. E1 — fork

1. Owner: poner `PAPER_D_EXECUTE=1` (+ opcional `PAPER_D_ACCOUNT_ID`) en env API DEMO y reiniciar API.
2. Acumular deuda estricto: runbook [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md) (60d · 50 SEMI live · buy-alarma P3/P4 · MaxDD trading).
3. Push commits locales (si se pide).
4. **No** broker live.

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · broker **no** · estricto **no** cerrado · W3/W4 sin claim precisión Estudio · I1/I3/RX1 gates intactos.
