# Arranque auditor externo — V1.47 Paper Desk Runtime Truth (2026-09-01)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **V1.47 Paper Desk Runtime Truth** tip **`v1.47-beta` → `77f96ead`** (product **`V1.47-beta`**; previo certificado **`v1.45-beta` → `6ca5ec12`**). V1.46 es foundation (EntryTick **stub** + Position AUTO), **no** AUTO completo. Audita Runtime Truth, no un runner multi-semana ni Entry AUTO real.

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-v1-47-paper-desk-runtime-truth-2026-09-01.md`](./traspaso-relevo-v1-47-paper-desk-runtime-truth-2026-09-01.md)
3. [`docs/engineering/spec-v147-paper-desk-runtime-truth-2026-09-01.md`](./spec-v147-paper-desk-runtime-truth-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md)
4. Previo: [`traspaso-relevo-v1-46-paper-desk-2026-08-31.md`](./traspaso-relevo-v1-46-paper-desk-2026-08-31.md) · [`arranque-auditor-v1-46-paper-desk-2026-08-31.md`](./arranque-auditor-v1-46-paper-desk-2026-08-31.md)

**Preguntas de foco:**

1. ¿HTTP AUTO (`POST /paper-desk/cycle`, `POST /position-automation/execute-auto`) **no** acepta markPrice / dataStale / marketClosed / portfolioDrift / immediateRisk / defaultMarkPrice?
2. ¿GET `/paper-desk/daily-report` es consulta (dry-run) y **no** tiene `execute`?
3. ¿Sin MarketSnapshot válido el ciclo **no** usa `actual_entry` como mark (`data_unavailable` / `REVISAR_DATOS_NO_FRESCOS`)?
4. ¿`OperationalContext` deriva stale / sesión / drift / stopTouched (tests inyectan FakeMarketData / `build_test_operational_context`)?
5. ¿Idempotencia `positionId|eventType|asOf|sequence|action`: mismo T1 dos veces = un sell; crash/replay no duplica fill?
6. ¿`nextAction` en cada fila PositionTick? ¿autoDesk sigue siendo proyección (no estado operativo)?
7. ¿GP AUTO-01..10 (ciclo + contexto) y GP-DESK-01/02/03 verdes? ¿EntryTick sigue HonestStub?
8. ¿Confirm SEMI / package `1.35.0-beta` / sin LIVE / sin Alembic / sin scheduler / `PAPER_D_EXECUTE` default off?

**Deuda aparcada:** EntryTick Estudio/Paper-D pleno · scheduler · UI Mercado · capability matrix · tag v1.47 · LIVE · OCO.

**No pedir:** nav L1 · `PAPER_D_EXECUTE` default on · LIVE · Entry AUTO real · DeskRunner semanas.

---
