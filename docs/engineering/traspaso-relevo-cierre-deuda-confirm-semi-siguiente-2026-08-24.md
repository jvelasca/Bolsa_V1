RELEVO / TRASPASO — Cierre deuda confirm SEMI (Bug 1 + Bug 2) CERRADA → apertura fase siguiente

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT**. La **rebanada de cierre de la deuda diferida del confirm SEMI** (Bug 1: `wait` sin sesión; Bug 2: `reduce`/`exit_hint` vs abrir short) queda **CERRADA y VERIFICADA (verificador read-only APROBADO)**, pendiente del **commit aprobado por el propietario**. La fase siguiente **la decide el propietario** a partir del backlog. Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **Fase 0 Decision Spine COMPLETA** (F0.1–F0.6 + D2 `f7b1f6c` + Escalón 3/D1 `7530556`) · **Cierre deuda confirm SEMI verificado APROBADO** (pendiente commit) · **D3** (`Lab/Radar fuera del spine`, ADR-019) ⏳ recomendada pendiente de confirmar.
> **SHA al cerrar este hilo:** la rebanada está SIN commitear (a la espera de aprobación del propietario sobre el cambio). Partida `origin/main` = `6de4176` (relevo Escalón 3/D1 → siguiente fase) con el **working tree sucio** solo en los 2 archivos declarados.

---

## 1. Qué está hecho (alcance de esta rebanada — pendiente commit)

El propietario aprobó la fase = **ambos ítems de la deuda diferida del confirm SEMI** en una rebanada, con alcance:

- **Bug 1 — `wait` no trade:** una tesis `wait` (incluso con `suggested_quantity > 0`) ya NO desencadena un **sell default**. Queda fuera de las acciones transaccionales.
- **Bug 2 — side de `exit_hint`/`reduce`:** el lado de un cierre/reducción se deriva del `action` del **`DecisionPackage` de la sesión** (`recommend_long`→`sell`, `recommend_short`→`buy`). Si **NO hay sesión/package** para determinarlo → **fail-closed** `rejected_by_gate`/`unknown_position_side` (nunca se asume el lado). Mismatch contra package presente → `decision_package_conflict`.

### Deltas verificados (file:line, `git diff`)

- **`packages/py/application/src/bolsa_application/confirm_recommendation.py`**
  - Constantes: `_TRADE_ACTIONS = _OPENING_ACTIONS | _CLOSING_ACTIONS` (sin `wait`).
  - `_intent_side_matches_package_side` + `_identity_reconciles` → **`_required_fill_side(action, package_action) -> (determinable, side)`** y **`_reject_reason_for_execute(...) -> str|None`**.
  - Puerta de ejecución: `rec.action in _TRADE_ACTIONS` (excluye `wait`) + routing de `reject_reason` hacia `rejected_by_gate` + `intent.status=rejected_by_gate`.
  - Docstring de módulo actualizado (D2 + Escalón 3/D1 + Bug 1/Bug 2).
- **`packages/py/application/tests/test_execute_trade_idempotency.py`**
  - `test_confirm_exit_hint_no_sometido_a_cesta` **RENOMBRADO** → `test_confirm_exit_hint_orphan_fail_closed_unknown_side` (cambio de comportamiento INTENCIONAL: orphan `exit_hint` ahora fail-closed, antes ejecutaba sell).
  - **4 tests nuevos:** `test_confirm_wait_no_ejecuta_sell_default` · `test_confirm_reduce_short_conflict_no_reapertura` · `test_confirm_exit_hint_short_conflict_no_reapertura` · `test_confirm_exit_hint_largo_con_package_ejecuta_sell`.

### Cambio de comportamiento intencional (aprobado por el propietario)

- Orphan `exit_hint`/`reduce` (sin sesión/package) → **fail-closed `unknown_position_side`** (antes ejecutaba un sell a ciegas, que podía re-abrir un short).
- `exit_hint`/`reduce` contra package `recommend_short` → `intent.side=sell` (mapping por defecto en `order_intent.py` intacto) **no cuadra** con el `buy` requerido → `decision_package_conflict` (no se auto-cubre un short; la UI/persona debe enviar el lado correcto).
- `exit_hint` contra package `recommend_long` → ahora **ejecuta** `sell` (antes D2 lo rechazaba). Es el fix aprobado: cerrar un largo es vender.

### Qué NO toca (sin cambio de contrato HTTP, sin `order_intent.py`, sin `dependencies.py`)

## 2. Batería (verificada por el coordinador + verificador read-only APROBADO)

| Check                                                                 | Resultado                                                                                                                          |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `ruff` (2 archivos cambiados)                                         | **0**                                                                                                                              |
| `mypy` fuente `confirm_recommendation.py`                             | **0**                                                                                                                              |
| `pytest test_execute_trade_idempotency.py`                            | **20/20** (16 + 1 actualizado + 4 nuevos)                                                                                          |
| `pytest risk/fit/router` (4 ficheros)                                 | **10/10**                                                                                                                          |
| `pytest packages/py/application/tests`                                | **327 passed / 1 fail pre-existente ajeno** (`test_list_account_summaries_one_summary_per_account`, fake repo sin `owner_user_id`) |
| mypy archivo de tests                                                 | 12 errores **PRE-EXISTENTES**, ninguno en líneas nuevas                                                                            |
| **Verificador read-only** (alcance disjunto, subagente independiente) | **APROBADO**                                                                                                                       |

## 3. Qué NO tocar (freeze)

- Motor money / ledger / `ExecuteTrade` internals.
- Believe / gobernanza IA · `contract:gen` salvo fase pactada · Track B B1–B12.
- `pending-delete` · no `regen_full`. Purge storage E8 N.
- F0.5b · F0.6 (backend+UI) · D2 · Escalón 3/D1 · **Cierre deuda confirm SEMI**: ya cerrados y verificados, NO reescribir salvo fase pactada que exponga un hueco real.
- `order_intent.py` (`intent_from_recommendation`): el fix deliberadamente NO toca su mapping por defecto `exit_hint`/`reduce`→`sell` (otros call-sites). Corregirlo ahí sería una fase separada con auditoría de call-sites.

## 4. Tarea del siguiente chat (fase nueva — SIN aprobar)

**PASO 0 (obligatorio, sin código):** el propietario decide qué fase sigue y **aprueba el commit de esta rebanada pendiente** (si aún no lo hizo). El agente solo presenta opciones ancladas al backlog y espera decisión. NO abrir código antes.

Candidatos registrados (a partir del backlog §0, PROJECT_STATE §3 y DEUDA §4):

- **D3** — Lab/Radar fuera del spine (ADR-019): pendiente de `confirmar` (recomendada).
- **Backlog §4 (ops, fuera de repo, no bloquea código):** secret scanning UI · `TRUSTED_PROXIES` prod · corregir `BP/.L`→`BP.L` en BD · limpiar `logs/dev`.
- Otros (a decidir por el propietario): M-4/T-M4 job dedicado (diferido por freeze) · gobernanza IA · F9/V2 (ADR + decisión).

**Después (con fase aprobada):** implementar la rebanada acordada, una a la vez, path:line verificado, batería, aprobación antes de commit.

## 5. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO: Fase 0 Decision Spine COMPLETA (D2 f7b1f6c DecisionPackage=contrato +
Escalón 3/D1 7530556 VETO cesta fail-closed) + Cierre deuda confirm SEMI (Bug 1 + Bug 2)
VERIFICADO APROBADO pero PENDIENTE de commit del propietario (working tree sucio solo en
confirm_recommendation.py + test_execute_trade_idempotency.py).
Bug 1: wait sin sesión ya NO ejecuta sell default (wait fuera de _TRADE_ACTIONS, trade=None).
Bug 2: side de exit_hint/reduce derivado del action del DecisionPackage de la sesión
(recommend_long->sell, recommend_short->buy); sin sesión/package -> fail-closed
rejected_by_gate/unknown_position_side; mismatch vs package -> decision_package_conflict.
Aperturas orphan siguen ejecutando (contract=absent). D2/Esc.3/D1 intactos. Sin cambio HTTP,
sin tocar order_intent.py. Batería: ruff 0, mypy fuente 0, confirm 20/20, risk/fit/router 10,
application 327/328 (1 fail pre-existente ajeno test_list_account_summaries).
LEE (read-first, obligatorio): backlog §0 + PROJECT_STATE §3 + PROJECT_PREMISES ⭐§0.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.

TAREA: PRIMERO -> el propietario aprueba/commitea la rebanada pendiente (si no se hizo) y
decide QUÉ FASE SIGUE (E1). Candidata registrada: D3 (Lab/Radar fuera del spine, ADR-019)
pendiente de confirmar. NO lanzo agentes ni código hasta aprobar la fase y su alcance.
DESPUÉS -> rebanada acotada, path:line verificado, batería, verificador read-only
(alcance disjunto), aprobación del propietario antes de commit.

NO TOCAR: money/ledger/ExecuteTrade internals, gobernanza IA, contract:gen salvo fase pactada,
Track B B1-B12 (cerrado), pending-delete (E8 N), regen_full sin decisión,
order_intent.py (mapping default exit/reduce->sell, fase dedicada con auditoría de call-sites).
NO REABRIR: F0.5/F0.6/F0.6-UI/D2/Escalón 3/D1/Cierre deuda confirm SEMI.
Backlog §4 activo (fuera de repo, no bloquea código): secret scanning UI, TRUSTED_PROXIES
prod, corregir BP/.L→BP.L en BD, limpiar logs/dev.

Protocolo: subagente acotado + verificador read-only, alcance disjunto, batería,
aprobación del propietario antes de commit.
```
