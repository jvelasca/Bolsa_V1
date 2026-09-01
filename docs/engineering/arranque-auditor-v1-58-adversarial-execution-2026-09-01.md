# Arranque auditor externo — V1.57→V1.58 stack (Adversarial Execution) (2026-09-01)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **stack V1.57 Operational Truth → V1.58 Adversarial Execution**. Producto bajo revisión **`V1.58` implementación local CERRADA**, tag **pendiente**. Partida certificada **`v1.56-beta` → `5c598a62`** (+ V1.57 en working tree). El stack **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance:** V1.57 stack **intacto** · V1.58: GP-GOLDEN-DAY-ADV-01 (día encadenado BUY→dup→T1→crash→TRAIL→T2 net fail→retry→dup evt→EXIT→recon) · P0b network skip no marca leg `failed` · GP-V158-STOP-CLOSED certifica contrato stop + mercado cerrado. **No** motores nuevos · **no** E2E FastAPI · **no** UX Mercado · **no** encolar stop a apertura.

**Contexto local (2026-09-01):** pytest adversarial + golden + adverse + INV **22** · ruff OK.

**GitHub (auditor):**

- Partida certificada: [`v1.56-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.56-beta) → `5c598a62`
- Tip V1.58: working tree local (tags `v1.57-beta` / `v1.58-beta` aún no emitidos)

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/spec-v158-adversarial-execution-2026-09-01.md`](./spec-v158-adversarial-execution-2026-09-01.md)
3. [`docs/engineering/plan-v158-adversarial-execution-2026-09-01.md`](./plan-v158-adversarial-execution-2026-09-01.md)
4. [`docs/engineering/traspaso-relevo-v1-58-adversarial-execution-2026-09-01.md`](./traspaso-relevo-v1-58-adversarial-execution-2026-09-01.md)
5. [`docs/engineering/spec-v157-operational-truth-2026-09-01.md`](./spec-v157-operational-truth-2026-09-01.md)
6. [`docs/engineering/spec-v148-paper-desk-event-continuity-2026-09-01.md`](./spec-v148-paper-desk-event-continuity-2026-09-01.md)
7. [ADR-043](../adr/043-position-automation.md)

**Preguntas de foco:**

1. ¿**GP-GOLDEN-DAY-ADV-01** encadena en un solo store sin duplicar Position, open fill, ni sells por replay/duplicate event?
2. ¿El skip de red **no** consume idempotency key ni incrementa `execute_count`, y el retry T2 ejecuta con fill distinto?
3. ¿**P0b** deja T1/T2 leg sin `failed` en `skipped`/`network_failure` y solo marca `failed` en `blocked`/`rejected`?
4. ¿**GP-V158-STOP-CLOSED** demuestra STRUCTURAL_STOP + `session=CLOSED` vende, mientras T1 + CLOSED sigue en `queue_next_session`?
5. ¿El hallazgo STRUCTURAL_STOP mercado cerrado queda **certificado** sin cambiar política PAPER (contrato V1.48)?
6. ¿Freeze intacto: Confirm SEMI · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`** · **no LIVE**?

**Deuda aparcada:** V1.59 E2E FastAPI+DB · V1.60 UX Mercado · encolar STRUCTURAL_STOP a apertura (LIVE) · thaw Accept (0/5 PASS) · TRUSTED_PROXIES IPs de producción (`BLOCKED_ON_OWNER`).

**No pedir:** LIVE · bump package · segundo motor ranking · Alembic · scheduler · rediseño Mesa/Mercado.

---
