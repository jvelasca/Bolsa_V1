# Arranque auditor externo — v1.41-beta (2026-08-31)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 post-tag **`v1.41-beta`** (serie V1.37→V1.41: Operational Truth → Daily Desk). Tip SHA: ver [`traspaso-relevo-tag-v1-41-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-41-beta-2026-08-31.md).

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-41-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-41-beta-2026-08-31.md)
3. [`docs/engineering/traspaso-relevo-v1-41-daily-desk-2026-08-31.md`](./traspaso-relevo-v1-41-daily-desk-2026-08-31.md)
4. [`docs/engineering/traspaso-relevo-v1-40-exit-management-ux-2026-08-31.md`](./traspaso-relevo-v1-40-exit-management-ux-2026-08-31.md)
5. [`docs/engineering/traspaso-relevo-v1-39-position-operating-ux-2026-08-31.md`](./traspaso-relevo-v1-39-position-operating-ux-2026-08-31.md)
6. [`docs/engineering/traspaso-relevo-v1-38-entry-operating-ux-2026-08-31.md`](./traspaso-relevo-v1-38-entry-operating-ux-2026-08-31.md)
7. [`docs/engineering/traspaso-relevo-v1-37-operational-truth-2026-08-31.md`](./traspaso-relevo-v1-37-operational-truth-2026-08-31.md)
8. Contexto previo: [`docs/engineering/traspaso-relevo-v1-36-daily-operating-ui-2026-08-31.md`](./traspaso-relevo-v1-36-daily-operating-ui-2026-08-31.md) · tag `v1.35-beta`

**Preguntas de foco (proyección UX — no nuevos motores ni nav L1):**

1. ¿`OperationalTruth` es la única autoridad de acción de posición abierta en Mercado / Hoy / Journal / Operaciones (`protect_hint` thin no gana)?
2. ¿`EntryOperatingTruth` unifica PREPARADA→CONFIRMADA con CTAs sin BUY/COMPRAR y Confirm = firma?
3. ¿Position Operating UX muestra **una** CTA primaria alineada a `truth.primaryCta` / `decision.action`?
4. ¿`ExitRouteView` proyecta Entrada → Stop (Proteger) / T1 / T2 (trailing thin) de forma coherente cross-surface, con T1 tocado ≠ gestionado?
5. ¿Daily Desk (Hoy) es inbox por `attention` sin paneles de ranking/KPI en el chrome (no segundo Mercado)?
6. ¿Freeze intacto: Confirm = firma · `PAPER_D_EXECUTE` off · AUTO execute off · Ranking ≠ BUY · sin drag entry/exit · backend operativo intocado?

**Deuda explícita a validar como aparcada (no implementar):** P2 Lab · móvil · push · thaw estricto · OCO · trail autoridad · segundo Mercado · entry/T1/T2 drag · OpportunityScore.

**No pedir:** nav L1 nueva · thaw · promover thin trail a autoridad · motores nuevos de decisión/salida.

---

Opcional (solo si el owner lo pide): Bugbot / Security Review sobre el tip vs `v1.35-beta` / `v1.36` tip.
