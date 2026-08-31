# RELEVO — V1.45 PAPER AUTO position execute (2026-08-31)

> **Padre:** [`spec-v145-paper-auto-position-2026-08-31.md`](./spec-v145-paper-auto-position-2026-08-31.md) · [ADR-043](../adr/043-position-automation.md) · [`plan-v145-paper-auto-position-2026-08-31.md`](./plan-v145-paper-auto-position-2026-08-31.md) · tip `v1.44-beta` → `db346a11`.  
> **Estado:** **CERRADO (código)** — `ExecutePositionPolicyAuto` → JIT Permission → protect | Router reduce/exit → PositionRevision. `PAPER_D_EXECUTE` **default off**. **No** LIVE. **Tag tip:** [`v1.45-beta` → `1627e9c9`](./traspaso-relevo-tag-v1-45-beta-2026-08-31.md) (CI pending).  
> **Arranque auditor:** [`arranque-auditor-v1-45-beta-2026-08-31.md`](./arranque-auditor-v1-45-beta-2026-08-31.md).

---

## 0. Qué cierra

| Pieza                                                                     | Estado |
| ------------------------------------------------------------------------- | ------ |
| Spec + plan + ADR-043 execute PAPER                                       | DOCS   |
| `ExecutePositionPolicyAuto`                                               | CÓDIGO |
| Router `resolve_exit_sell_quantity` / reduce parcial                      | CÓDIGO |
| `RouterPaperPositionSell` + HTTP `POST /position-automation/execute-auto` | CÓDIGO |
| GP-AUTO-01 E2E pytest + env-off / stale / closed / protective             | CÓDIGO |

```text
AUTO: Event → Policy → ExitPermission JIT → protect|Router sell → PositionRevision
SEMI: intacto (Confirm = firma)
```

## 1. Pre-flight

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-automation-golden-path.test.ts src/cognitive/position-policy-decision.test.ts src/exit-permission.test.ts
pytest packages/py/application/tests/test_execute_position_policy_auto.py packages/py/application/tests/test_execution_router_reduce.py -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
pnpm --filter @bolsa/web exec tsc --noEmit
```

Resultado local (2026-08-31): shared build OK · 34 shared spot · tsc OK · pytest **11** (execute-auto + router-reduce) · ruff OK.

## 2. Freeze (intactos)

Confirm = firma · `PAPER_D_EXECUTE` off · sin Lab SoT · sin LIVE · sin OCO · sin Lab P2 · sin auto-promote · sin Alembic · sin bump `package.json` · Mercado = terminal.

## 3. OUT

- Tag `v1.45-beta` (owner + CI GREEN)
- Browser E2E / Daily Journal UI
- Retrofit Lab EvaluatePositionExits
- `PAPER_D_EXECUTE` default on · thaw LIVE

## 4. Next

1. Tag `v1.45-beta` cuando owner pida + relevo-tag.
2. Auditar con arranque auditor.
3. V1.46 Autonomous Paper Desk — solo tras tip certificado. NO LIVE.
