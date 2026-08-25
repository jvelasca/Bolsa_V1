# ADR-023 — Thaw condicionado Camino D / Libro AUTO

- **Estado:** **Accepted — BETA parcial / condicionado** (2026-08-25)
- **Fecha:** 2026-08-04 (Proposed) · Accept BETA 2026-08-25
- **Padres:** [freeze](../engineering/post-audit-decision-freeze-2026-08-03.md) · [checklist thaw](../engineering/camino-d-auto-thaw-checklist-2026-08-04.md) · ADR-022 · medición [`thaw-p1-p5-measurement-2026-08-25.md`](../engineering/thaw-p1-p5-measurement-2026-08-25.md) · perfil [`thaw-beta-adapted-remeasure-2026-08-25.md`](../engineering/thaw-beta-adapted-remeasure-2026-08-25.md)

## Contexto

Prep A0–A5 cerrada en código. La barra **estricta** P1–P5 (60d / 50 SEMI / Prec≥70% / Rec≥55%) **FAIL** en DEMO live (2026-08-25). El propietario autorizó **thaw** + **adapta y repite** → perfil **BETA-D** (Informe 2 + waivers W2–W4).

## Decisión (Accepted BETA-D)

1. Libro DEMO modo AUTO (**UI**) habilitado tras armado local; execute sigue opt-in env.
2. Todo execute AUTO → **Risk Engine** (`check_opening`) + kill switch efectivo + gates I1/I3/RX1.
3. Opt-in: `PAPER_D_EXECUTE=1` **y** opcional `PAPER_D_ACCOUNT_ID=<cuenta DEMO>`. Default de repo **sigue off**.
4. Doble confirmación UI (armado local) obligatoria antes de modo AUTO efectivo.
5. Freeze amend: Camino D thaw **parcial / BETA-D** (no broker live · no claim precisión Estudio).
6. Thaw **estricto** (filas 60/50/70/55) permanece **deuda** — no sustituido.

## Evidencia

### Estricto (referencia — sigue FAIL)

| Criterio               | Evidencia adjunta   | Estado |
| ---------------------- | ------------------- | ------ |
| P1 ≥60d dictámenes     | 28 días             | ❌     |
| P2 ≥50 SEMI fills      | 0 confirm live      | ❌     |
| P3 Precisión BUY ≥70%  | null / 0 buy-alarma | ❌     |
| P4 Recall ≥55%         | 0.0                 | ❌     |
| P5 MaxDD trading + Lab | 0 trades seed       | ⚠      |

### Adaptado BETA-D (PASS + waivers)

| Criterio                          | Evidencia adjunta                            | Estado           |
| --------------------------------- | -------------------------------------------- | ---------------- |
| P1' ≥25d dictámenes               | 28 días A0/SQL                               | ✅               |
| P2' SEMI path (W2)                | `test:decision-spine` 159; fills live waived | ✅ W2            |
| P3' Precisión diferida (W3)       | sin claim hasta buy-alarma                   | ✅ W3            |
| P4' Recall diferido (W4)          | sin claim                                    | ✅ W4            |
| P5' MaxDD cash ≤10% seed          | 0.2%                                         | ✅               |
| P6–P8 Gate / kill / doble confirm | A2–A3 + UI AUTO on                           | ✅ producto BETA |

## Consecuencias

- SEMI Confirm sigue siendo el camino humano por defecto.
- AUTO DEMO: UI on + `PAPER_D_EXECUTE=1` local + armado; sin broker.
- No afirmar precisión/recall Estudio hasta re-medida A0 con `stance=buy`.
- No flip silencioso: default código/env example permanece off salvo opt-in local.

## No incluye

Belief→Coach · `CORE_R_CRON` · Strategy Studio · broker live · thaw estricto cerrado · producción.
