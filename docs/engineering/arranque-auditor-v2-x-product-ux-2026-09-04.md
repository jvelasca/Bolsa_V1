# Arranque auditor externo — V2.x Product UX (cabina Mercado) (2026-09-04)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **candidato V2.x Product UX** (partida motor tip [`v2.0-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.0-beta) → [`e05fc6b0`](https://github.com/jvelasca/Bolsa_V1/commit/e05fc6b0) · Release-tag CI V2.0 **GREEN**).  
**Código UX tip local (sin tag producto):** tip cadena `a39595ce`…`b8192d3a` (ver relevo). **No** LIVE · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`** sin bump · **no** segundo FSM · Confirm = firma · Ranking ≠ BUY.

**Alcance V2.x (producto / UX — no reabrir motor PAPER AUTO):**

- Mercado = cabina LISTAS | GRÁFICO | DECISIÓN con **PRÓXIMA ACCIÓN** como héroe
- Opportunity Card (ESPERAR TRIGGER / ENTRADA LISTA) sin CTA COMPRAR/EJECUTAR que salte Confirm
- Position Card: misión Entrada→Stop→T1→T2→Trailing + Risk Box
- AUTO Desk (Manual / Asistido / Automático) · arm ≠ execute
- Hoy 4 cubos · Asesor explicativo · Journal memoria + learning strip (SoT `decision_sessions` intacto)
- V2.08: CTA **Proteger** en `OPEN_UNPROTECTED` (bootstrap stop 5%) → Confirm
- V2.09: polish tipografía/a11y cabina

**Regla:** NINGÚN estado ambiguo → COMPRAR. DryRun honesto. No inventar tip `v2.x-beta` si no está en `origin`. No mezclar PASS/FAIL del motor V1.99 / V2.0 FSM.

Lee:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`traspaso-relevo-v2-x-product-ux-2026-09-04.md`](./traspaso-relevo-v2-x-product-ux-2026-09-04.md)
3. [`traspaso-relevo-v2-0-cierre-paper-auto-2026-09-04.md`](./traspaso-relevo-v2-0-cierre-paper-auto-2026-09-04.md) (padre motor — freeze)
4. Código: `packages/shared/src/cognitive/operator-cabin-view.ts` · `daily-desk.ts` · `apps/web/src/features/trading/operator-cabin-ui.tsx` · `operativa-cockpit-card.tsx` · `auto-desk-panel.tsx` · `decision-surface-compact.tsx` · `propose-position-exit.ts` (`positionShowsProtectCta`)

**Foco:**

1. ¿En &lt;10 s un operador ve **PRÓXIMA ACCIÓN** sin jerga Lifecycle/Outbox/Spine?
2. ¿Confirm sigue siendo la única firma (SEMI) y Ranking ≠ BUY?
3. ¿Position mission + Risk Box / AUTO Desk son honestos (arm ≠ execute)?
4. ¿`OPEN_UNPROTECTED` ofrece Proteger → Confirm sin inventar orden broker?
5. ¿Freeze motor intacto? (`TRANSITIONS`, no LIVE, no bump, `PAPER_D_EXECUTE` off)
6. ¿Smoke ops (BBVA PAPER · protect 24.00 · Hoy 1/1) es evidencia suficiente o falta tip GitHub?

**No pedir:** LIVE · bump package · tip motor nuevo · colapso L1 (ADR-040) por inercia · reabrir FSM/outbox/integrity.

**Respuesta:** (pendiente — no inventar PASS).

---
