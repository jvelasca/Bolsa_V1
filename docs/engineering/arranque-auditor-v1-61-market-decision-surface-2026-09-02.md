# Arranque auditor externo — V1.60→V1.61 stack (Market Decision Surface) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **stack V1.60 UX Mercado → V1.61 Market Decision Surface**. Producto bajo revisión **`V1.61` implementación CERRADA**. Partida certificada **`v1.60-beta` → `7ac8ad9b`**. El stack **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance:** V1.60 stack **intacto** · V1.61 consolida panel **DECISIÓN** fase posición en **una** Position Decision Surface (`position-operational-star-card.tsx`): NIVEL 1 qué ocurre · NIVEL 2 decisión/ejecución · NIVEL 3 por qué + stop history. GP-V161-01..06: recon fail-closed · tono por estado · sin Summary/Plan apilados · honesty · cross-surface POV. **No** motores nuevos · **no** EntryOperationalView · **no** Playwright CI.

**Contexto local (2026-09-02):** shared POV+cross **26** · web Mercado **51** · V1.59 integration **7** · V1.58 block **13** · tsc OK.

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/spec-v161-market-decision-surface-2026-09-02.md`](./spec-v161-market-decision-surface-2026-09-02.md)
3. [`docs/engineering/plan-v161-market-decision-surface-2026-09-02.md`](./plan-v161-market-decision-surface-2026-09-02.md)
4. [`docs/engineering/traspaso-relevo-v1-61-market-decision-surface-2026-09-02.md`](./traspaso-relevo-v1-61-market-decision-surface-2026-09-02.md)
5. [`docs/engineering/spec-v160-ux-mercado-2026-09-02.md`](./spec-v160-ux-mercado-2026-09-02.md)
6. [`docs/engineering/spec-v157-operational-truth-2026-09-01.md`](./spec-v157-operational-truth-2026-09-01.md)
7. [ADR-042](../adr/042-operating-excellence.md)

**Preguntas de foco:**

1. ¿**GP-V161-01** mapea `error`/`unknown`/`degraded` → `unavailable` → `RECONCILIATION_ERROR` y nunca CLEAN silencioso?
2. ¿**GP-V161-02** `data-tone` esmeralda/ámbar/rosa según `operatingState` (drift rosa ≠ protected esmeralda)?
3. ¿**GP-V161-03** fase posición muestra Decision Surface única sin `position-operating-summary` ni `OperationalPlanView`?
4. ¿**GP-V161-04/05** honestidad acción (PROTECTED→Mantener · T2→Pendiente · sin COMPRAR) y líneas DECISIÓN/EJECUCIÓN?
5. ¿**GP-V161-06** misma fixture → mismos hechos POV en builders cross-surface?
6. ¿**GP-V160-01..04** siguen verdes (T2_READY/EXECUTED · drift · stop history · testids)?
7. ¿V1.59 integration (**7**) y V1.58 block (**13**) sin regresión?

**Deuda aparcada:** EntryOperationalView · gráfico-puente · DTO HTTP POV Python · Browser E2E full stack · Paper Autonomous Desk · LIVE.

**No pedir:** LIVE · bump package · motores nuevos · segundo Mercado.

---
