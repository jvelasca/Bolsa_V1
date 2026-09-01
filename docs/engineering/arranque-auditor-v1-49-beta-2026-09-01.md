# Arranque auditor externo — V1.49 Paper Desk Entry AUTO (2026-09-01)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **V1.49 Paper Desk Entry AUTO** product **`V1.49-beta`** tip **`c8975c9d`** (previo tip **`v1.48-beta` → `d5852e8d`**). V1.48 es Event Continuity (PositionTick). V1.49 cierra EntryTick real: Estudio → rank → TradePlan → `check_opening`. **No** LIVE. `PAPER_D_EXECUTE` default **off**.

**Contexto CI (2026-09-01):** tag `v1.49-beta` pusheado → `c8975c9d` · Release-tag CI **GREEN** ([run 33480370327](https://github.com/jvelasca/Bolsa_V1/actions/runs/33480370327)) · pre-flight local verde (vitest 7 · pytest 70 · ruff · tsc).

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-v1-49-paper-desk-entry-auto-2026-09-01.md`](./traspaso-relevo-v1-49-paper-desk-entry-auto-2026-09-01.md)
3. [`docs/engineering/spec-v149-paper-desk-entry-auto-2026-09-01.md`](./spec-v149-paper-desk-entry-auto-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md)
4. PositionTick previo: [`spec-v148-paper-desk-event-continuity-2026-09-01.md`](./spec-v148-paper-desk-event-continuity-2026-09-01.md)

**Preguntas de foco:**

1. ¿`EstudioPaperDeskEntry` implementa `PaperDeskEntryPort` y reutiliza `ProposeEstudioAutoOpenings` (no lógica duplicada)?
2. ¿Universo = lista `estudio` vía `GetInstrumentList`? ¿Empty ≠ unavailable (notas honestas)?
3. ¿Ranking = `select_estudio_opening_candidates` (alarma ★≥4 antes que dictamen)? ¿Paper-D **no** entra al desk entry?
4. ¿Solo hits con TradePlan `TRIGGERED` cuentan como `proposed_count` (`hitCount`)?
5. ¿`dry_run=true` → propose sin Router; `dryRun=false` + env + policy → Router + `check_opening`?
6. ¿OR-4 en `PaperDeskCycle` bloquea entry (drift/unavailable) **antes** del port, pero PositionTick protectivo sigue?
7. ¿GP-DESK-03: ciclo dry_run muestra `proposed_count > 0` sin mutar ledger?
8. ¿Golden Session / CAOS V1.48 intactos (PositionTick sin regresión)?
9. ¿`HonestStubPaperDeskEntry` permanece para tests aunque DI producción use Estudio?
10. ¿Confirm SEMI / package `1.35.0-beta` / sin LIVE / sin scheduler / `PAPER_D_EXECUTE` default off?

**Deuda aparcada:** Paper-D desk entry · scheduler · UI Mercado · Golden entry birth+exit mismo ciclo · LIVE · OCO.

**No pedir:** nav L1 · `PAPER_D_EXECUTE` default on · LIVE · DeskRunner semanas · bump package.

---
