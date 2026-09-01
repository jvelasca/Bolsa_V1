# Arranque auditor externo — V1.54→V1.55 stack (Operational Hardening) (2026-09-01)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **stack V1.54 Operating Desk → V1.55 Operational Hardening**. Producto bajo revisión **`V1.55-beta`** tip funcional **`c797e234`**. Partida certificada **`v1.54-beta` → `e057a8cc`** (Release-tag CI GREEN). El stack **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance:** V1.54 proyección autoDesk → Daily Desk inbox (GP-DESK-UI-01..09) **intacta** · V1.55 endurecimiento operativo: GP-SESSION-01..10 + GP-GOLDEN-DAY-01 · `PositionOperationalView` proyección canónica · `PaperDailyReport` por secciones · Mesa cinco cubos · Consola solo excepciones · una CTA primaria por posición (AUTO sin COMPRAR). **No** motores nuevos · **no** segundo ranking · **no** CTA BUY desde filas AUTO.

**Contexto CI (2026-09-01):** tag `v1.55-beta` → `c797e234` · Release-tag CI **in_progress** ([run 33508058559](https://github.com/jvelasca/Bolsa_V1/actions/runs/33508058559); job python Ruff failure al snapshot docs). Tip previo: `v1.54-beta` → `e057a8cc` (**GREEN**). Pre-flight local post close-out: pytest **25** · shared vitest **34** · web vitest **29** · ruff OK · tsc OK.

**GitHub (auditor):**

- Código tip: [`v1.55-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.55-beta) → commit `c797e234`
- Partida certificada: [`v1.54-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.54-beta) → `e057a8cc` (CI GREEN)

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/spec-v155-operational-hardening-2026-09-01.md`](./spec-v155-operational-hardening-2026-09-01.md)
3. [`docs/engineering/spec-v154-operating-desk-2026-09-01.md`](./spec-v154-operating-desk-2026-09-01.md)
4. [ADR-043](../adr/043-position-automation.md)
5. Tags relevo: [`traspaso-relevo-tag-v1-54-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-54-beta-2026-09-01.md) · [`traspaso-relevo-tag-v1-55-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-55-beta-2026-09-01.md)

**Preguntas de foco:**

1. ¿**GP-SESSION-05** (stop loss Estudio → CLOSED qty=0) y **GP-SESSION-06..07** (T1 parcial Buy 100 → Sell 30 → remaining 70; T2 → remaining 0 · `target2Leg.executed`) adversos sin bypass paper?
2. ¿**GP-SESSION-08** trailing monotónico (never down) y **GP-SESSION-09** crash BUY→FILL→recover → 1 Position sin duplicar posición?
3. ¿**GP-SESSION-10** recon drift → `exceptionFacts` → RESOLVED fail-closed (OR-2/OR-4)?
4. ¿**GP-GOLDEN-DAY-01** jornada completa EXPECTED=ACTUAL (Estudio → birth → protect → T1 → TRAIL×2 → exit → cierre)?
5. ¿**PositionOperationalView** es proyección canónica read-only (no sustituye `PositionState`); UI consume DTO sin reinterpretar en React (`operatingState` · `primaryAction` · `levels` · `stopHistory` · eventos STOP/T1)?
6. ¿**PaperDailyReport** secciones DECISIONES · OPERATIVA · RESULTADO · NO OPERADAS coherentes con sesión golden y adverse pytest?
7. ¿**Mesa 5 cubos** remap honesto: 🔴 REQUIERE ACCIÓN · 🟠 PROTEGER · 🟢 POSICIONES · 🔵 OPORTUNIDADES · ⚪ NO OPERAR — sin filas engañosas ni inbox duplicado?
8. ¿**Consola excepciones-only**: solo incidentes · recon · birth_failed · UNKNOWN — no replica cubo Mesa ni propone COMPRAR?
9. ¿**CTA única** por posición · AUTO sin COMPRAR · sin `rankingEngineId` · sin segundo motor?
10. ¿V1.54 **autoDesk → EntryOpportunity thin** + **GP-DESK-UI-01..09** + wire `exceptionFacts` **sin regresión** tras remap cubos V1.55?
11. ¿Freeze intacto: Confirm SEMI · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`** · **no LIVE** · **no** scheduler · **no** bump package?

**Deuda aparcada:** LIVE · scheduler · browser E2E Journal · package bump · redesign Daily Desk · `PAPER_D_EXECUTE` default on.

**No pedir:** nav L1 · LIVE · bump package · segundo motor ranking · Alembic tabla nueva · thaw freeze Confirm.

---
