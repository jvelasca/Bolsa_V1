# Arranque auditor externo — v1.42-beta (2026-08-31)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 post-tag **`v1.42-beta` → `5e3fb1a4`** (Operating Excellence F2–F8 sobre tip `v1.41.3-beta` → `a8101ab7`; tip movido tras unblock CI ruff + frase Mantener).

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-42-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-42-beta-2026-08-31.md)
3. [`docs/engineering/spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) · [ADR-042](../adr/042-operating-excellence.md)
4. Relevos F2→F8 en `docs/engineering/traspaso-relevo-v1-42-*`
5. Previo: [`traspaso-relevo-tag-v1-41-3-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-41-3-beta-2026-08-31.md)

**Preguntas de foco (Operating Excellence — proyecciones, no motores nuevos):**

1. ¿`ExecutionState` / GP-03/04/10 coherentes entre Mercado / Hoy / Journal / Operaciones?
2. ¿F2b list intents descubre UNKNOWN sin re-POST Confirm?
3. ¿§A.8: `full_exit` gana a `protectionDiscrepancy` como CTA primaria?
4. ¿TradeStory en Journal ≠ Historial técnico · sin inventar `asOf`?
5. ¿Mercado **DECISIÓN** + Hoy 4 cubos consumen POT/EOT (no segundo motor)?
6. ¿SEMI: ningún execute sin Confirm · trail hint ≠ applied?
7. ¿F8 PAPER AUTO: arm ≠ execute · `PAPER_D_EXECUTE` default off · sin thaw LIVE?
8. ¿Release-tag CI del tip `v1.42-beta` GREEN?

**Deuda aparcada:** trail durable SEMI = **cerrado en `v1.43-beta`** · thaw LIVE · OCO · Lab P2 · OpportunityScore · package bump · auto-promote / broker trail.

**No pedir:** nav L1 nueva · motores nuevos · simulaciones E2E completas de la APP.

---
