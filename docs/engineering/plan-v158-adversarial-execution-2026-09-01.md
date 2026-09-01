# Plan — V1.58 Adversarial Execution

> **Padre:** [`spec-v158-adversarial-execution-2026-09-01.md`](./spec-v158-adversarial-execution-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md).  
> **AsOf:** 2026-09-01.  
> **Estado:** **implementación CERRADA** — partida `v1.57-beta` pendiente (working tree sobre `v1.56-beta` → `5c598a62`). Tag `v1.58-beta` pendiente.

| ID  | Entrega                                                                              | Estado |
| --- | ------------------------------------------------------------------------------------ | ------ |
| D0  | spec/plan V1.58 + stamp CURRENT_SYSTEM                                               | DONE   |
| P0  | `AdversarialSell` + `test_paper_desk_golden_day_adversarial.py` GP-GOLDEN-DAY-ADV-01 | DONE   |
| P0b | `execute_position_policy_auto` — failed solo en blocked/rejected                     | DONE   |
| P1  | GP-V158-STOP-CLOSED en adversarial suite                                             | DONE   |
| R1  | relevo + arranque auditor + pre-flight                                               | DONE   |

## Criterios

```bash
python -m pytest packages/py/application/tests/test_paper_desk_golden_day_adversarial.py packages/py/application/tests/test_paper_desk_golden_day.py packages/py/application/tests/test_paper_desk_golden_session_adverse.py packages/py/application/tests/test_inv_operational_truth.py -q
python -m ruff check packages/py/application/src/bolsa_application packages/py/application/tests/test_paper_desk_golden_day_adversarial.py --config pyproject.toml
```

## No hacer

LIVE · bump package · encender `PAPER_D_EXECUTE` default · scheduler · encolar STRUCTURAL_STOP a apertura · Playwright E2E · UX Mercado · cambiar política PAPER stop cerrado.
