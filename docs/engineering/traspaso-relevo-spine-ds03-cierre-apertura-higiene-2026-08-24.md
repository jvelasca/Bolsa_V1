# RELEVO — Spine DS-03 CERRADA → higiene dev

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** tras DS-03 Mandate de cuenta. **Siguiente = higiene dev** (secuencia pactada: DS-03 → higiene → Research→Radar → tag beta).
> **AsOf:** 2026-08-24. Ancla `origin/main` = **`5100d23`**. **DS-03 en working tree** (sin commit — coordinador). Ciclo previo U6→DS-05→ops CERRADO.
> **Protocolo:** máx. 1 writer + 1 verifier RO. Coordinador re-lee file:line. Pre-commit: batería de la fase + update-last.

---

## 1. Qué quedó hecho (Spine DS-03)

| Entrega     | Detalle                                                                                                   |
| ----------- | --------------------------------------------------------------------------------------------------------- |
| Gap elegido | **DS-03** Mandate de cuenta BLOCK (Account OperatingMandate gate)                                         |
| Enfoque     | **Código** — tenure server-side en `mandate_tenures` (ADR-020 M1b), no gate client-only                   |
| Gate puro   | `account_mandate_veto_reason` + params en `check_opening` (`account_mandate_gate.py`, `risk_engine.py`)   |
| Reglas      | Sin tenure abierto → `account_mandate:no_open_tenure` · mismatch estrategia AUTO → `strategy_mismatch`    |
| SEMI        | `mandates.get_open_mandate_for_instrument` → `require_account_mandate=True`; lookup raise → veto          |
| AUTO        | Mismo lookup + `signal.strategy_definition_id` como propuesta                                             |
| Exits       | `exit` / `exit_hint` / `reduce` **no** pasan por mandate gate                                             |
| DI          | `get_confirm_intent_use_case` + `get_execution_router_use_case` inyectan `SqlAlchemyAccountMandateLookup` |
| Tests       | unit risk · AUTO `test_ds03_auto…` · SEMI no-tenure/open/fail                                             |
| Batería     | `pnpm test:decision-spine` **53 passed**                                                                  |
| Freeze      | Sin OrderProposal · sin H3 orphan change · sin bypass confirm · sin `contract:gen` · ops intacto          |

**Honest inventory (no bloqueado):**

- `strategy-adoption.ts` sigue siendo proyección **cliente** (localStorage); el gate **no** lee adopción directamente.
- El gate usa **`mandate_tenures` en PostgreSQL** (sync vía `PUT /api/accounts/{id}/mandates`).
- Playbook ticker copy UI (`OperatingMandate` rail) **no es** este gate — distinto de DS-03 spine VETO.
- Estados `candidata` / `obsoleta` sin tenure abierto en BD → VETO en apertura (comportamiento fail-closed pactado).

**Archivos (código):**

- `packages/py/application/src/bolsa_application/account_mandate_gate.py` (nuevo)
- `packages/py/application/src/bolsa_application/risk_engine.py`
- `packages/py/application/src/bolsa_application/confirm_recommendation.py`
- `packages/py/application/src/bolsa_application/execution_router.py`
- `apps/api-python/src/bolsa_api/api/dependencies.py`
- tests: `test_risk_engine.py` · `test_decision_spine.py` · `test_execute_trade_idempotency.py`

**Docs (update-last):** backlog §0 · `CURRENT_SYSTEM.md` · `PROJECT_STATE.md` · `decision-spine-cadena-2026-08-24.md` · este relevo.

---

## 2. Residuales que quedan (inventario honesto)

| Hueco                            | Estado                                          | Next slice id sugerido         |
| -------------------------------- | ----------------------------------------------- | ------------------------------ |
| Composite `portfolioConstraints` | Doc honesty (`not_evaluated`)                   | spine-fit-composite (opcional) |
| Dos call-sites `ExecuteTrade`    | Diferido (grande)                               | execute-converge               |
| H3 orphan apertures              | Freeze doc-only                                 | —                              |
| DS-12–15 broker                  | Fuera                                           | —                              |
| Mandate gate ↔ adopción UI sync  | Ops: cliente debe sync BD antes de confirm/AUTO | higiene / runbook              |

---

## 3. Freeze (sigue intacto)

OrderProposal · Journal · Attribution · orquestador · Daily Mission · Track B B1–B12 · Belief · `PAPER_D_EXECUTE` **off** · sin broker live · Lab→spine · `contract:gen` salvo fase pactada · **no bypass human confirm** · **no cambio H3 orphan execute**.

---

## 4. Siguiente · higiene dev

Secuencia pactada por propietario:

```
DS-03 (este relevo)  →  higiene dev  →  Research→Radar  →  tag beta
```

**Abrir chat higiene dev** con:

```
CONTEXTO: DS-03 Mandate de cuenta CERRADA (working tree, sin commit).
Ancla origin/main = 5100d23. Batería decision-spine = 53 passed.
Freeze intacto. Siguiente fase = higiene dev (no Research→Radar todavía).
Relevo: traspaso-relevo-spine-ds03-cierre-apertura-higiene-2026-08-24.md
```

---

## 5. Commit sugerido (coordinador — no ejecutado aquí)

```
feat(spine): DS-03 Account Mandate Gate fail-closed en check_opening

Wire tenure BD (mandate_tenures) en SEMI confirm y AUTO router vía
check_opening; VETO sin mandato abierto y mismatch estrategia AUTO.
Exits exempt. Batería decision-spine 53.
```
