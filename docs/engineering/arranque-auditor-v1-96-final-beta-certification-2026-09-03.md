# Arranque auditor externo — V1.96 tip (Final Beta / T2) (2026-09-03)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **candidato `v1.96-beta` → `30479e97`** (partida **`v1.95-beta` → `6f262293`** · Release-tag CI **GREEN** [run 33808076820](https://github.com/jvelasca/Bolsa_V1/actions/runs/33808076820) · lifecycle-pg **25 passed** · V1.95 = PASS con 1 P1 de cobertura T2). **No** LIVE · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`**.

**Alcance V1.96 (certificación T2, no arquitectura nueva):**

- Confirm SEMI: `reduce` + `exitPlan.primaryReason=TARGET_2` → `T2_TRIGGERED` + `T2_EXECUTED` (paridad AUTO)
- Golden HTTP `test_lifecycle_golden_v196.py`: OPEN→T1→T2→EXIT → GET `/api/lifecycle/integrity` clean → corromper ledger T2 → drift/BLOCKED → Confirm nuevo OPEN DENY
- Golden V1.95 (OPEN→T1→EXIT) intacto como regresión
- `reason_code` viaja en payload outbox (drain remapea; no usa `row.kind` para el mapping)
- Idempotencia: T2 reduce no colisiona con T1 (mismo `decisionId`)
- CI: Release-tag `lifecycle-pg` incluye `test_lifecycle_golden_v196.py`
- `CURRENT_SYSTEM.md` del commit etiquetado ya dice V1.96 (no frases de tip V1.95 pendiente tag)
- Detect/report; **no** auto-heal

**Regla:** NINGÚN estado ambiguo → COMPRAR. DryRun honesto. No unificar ledger/mesa. No LIVE.

Lee: `CURRENT_SYSTEM.md` · `respuesta-auditor-v195` · `spec-v196` · `lifecycle_from_fill.py` · `lifecycle_t2_bridge.py` · `lifecycle_from_auto.py` · `test_lifecycle_golden_v196.py` · [`relevo`](./traspaso-relevo-v1-96-final-beta-certification-2026-09-03.md).

**Foco:**

1. ¿CI del commit candidato es GREEN (Ruff + Typecheck + lifecycle-pg con golden V1.96)?
2. ¿Confirm SEMI OPEN→T1→T2→EXIT escribe `T2_EXECUTED` (no un segundo T1)?
3. ¿Corrupción ledger T2 produce fill-drift y DENY de nuevo OPEN?
4. ¿El drain sin `reason_code` en payload degradaría T2 a T1?
5. ¿Freeze intacto? ¿Candidata **beta estable** / PAPER explotable?

**No pedir:** LIVE · bump · Playwright frontend-ci obligatorio · unificar ledger · queue_sequence · auto-heal · E2E integrado en esta rebanada · V1.97 por inercia.

**Respuesta:** (pendiente — no inventar PASS).

---
