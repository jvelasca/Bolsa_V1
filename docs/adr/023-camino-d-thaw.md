# ADR-023 — Thaw condicionado Camino D / Libro AUTO (borrador)

- **Estado:** Proposed (no Accepted)
- **Fecha:** 2026-08-04
- **Padres:** [freeze](../engineering/post-audit-decision-freeze-2026-08-03.md) · [checklist thaw](../engineering/camino-d-auto-thaw-checklist-2026-08-04.md) · ADR-022

## Contexto

Prep A0–A5 cerrada en código (`PAPER_D_EXECUTE` **sigue off**). Este ADR documenta **cuándo** se podrá aceptar un thaw parcial — no lo autoriza.

## Decisión (cuando se acepte)

1. Libro DEMO modo AUTO solo tras ✅ P1–P10 del checklist.
2. Todo execute AUTO → **Risk Engine** (`check_opening`) + kill switch efectivo.
3. Opt-in: `PAPER_D_EXECUTE=1` **y** opcional `PAPER_D_ACCOUNT_ID=<cuenta DEMO>`.
4. Doble confirmación UI (armado local) obligatoria antes de habilitar pill AUTO.
5. Amend freeze: Camino D thaw **parcial / condicionado** (no broker live).

## Evidencia requerida (vacía hasta medir)

| Criterio | Evidencia adjunta | Estado |
|----------|-------------------|--------|
| P1 ≥60d dictámenes | — | ☐ |
| P2 ≥50 SEMI fills | — | ☐ |
| P3 Precisión BUY ≥70% | — | ☐ |
| P4 Recall ≥55% | — | ☐ |
| P5 MaxDD DEMO | — | ☐ |
| P6–P8 Gate / kill / doble confirm | Código A2–A3 | prep ☐ producto |

## Consecuencias

- **Accepted** solo con filas evidencia + firma producto.
- Hasta entonces: SEMI Confirm es el único camino humano→DEMO fill automático vía F3.

## No incluye

Belief→Coach · `CORE_R_CRON` · Strategy Studio · broker live · flip silencioso de `.env`.
