# Plan detallado F1 — Integridad financiera (2026-08-11)

> **Padre:** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) §5 D0 (F1 primero) · D5 (solo F1–F5).
> **Checkpoint git:** `audit-checkpoint-2026-08-11` (HEAD `2683c49`).
> **Regla del hilo:** NO se toca código fuera de este plan. Cada cambio atómico se valida con la batería antes de commit. GitHub siempre recuperable.
> **Estado:** PLAN PARA REVISIÓN Y APROBACIÓN. No se ha tocado ningún fichero de código.

---

## 0. Lo que la verificación en código confirma (antes de escribir el plan)

He leído los ficheros reales para que el plan no sea especulativo. **Conclusión clave que matiza a las auditorías externas:**

- ✅ **La capa de persistencia YA usa `Decimal`/`Numeric(18,6)`** en todas las columnas de dinero (`tables.py`: `cash`, `quantity`, `avg_cost`, `price`, `total`, `balance_after`, `initial_cash`, `final_equity`, etc.). **No hay que migrar el esquema.**
- ⚠️ El `float` está solo en **dominio** (`Portfolio.cash`, `Transaction.*`, `AccountSummary.*`, `LedgerEntry.*`, `CashMovementResult.*`) y en **DTOs HTTP** (`schemas/portfolio.py`) y se convierte a `Decimal` al borde del repo.
- 🔴 **Falta bloqueo de fila** en `portfolio_repository.execute_trade`, `deduct_cash`, `transfer_cash`, `add_cash` (usan `session.get` sin `with_for_update`).
- 🔴 **`deduct_cash` descuenta menos de lo pedido silenciosamente** (`fee = min(fee, row.cash)`).
- 🟠 **`ExecuteTrade.execute` recalcula `trade_balance` a mano** en vez de usar el saldo devuelto por el repo (riesgo de desfase con el efectivo grabado).
- 🟠 **`TradeRequestDto` permisivo** (`type: str`, `quantity: float`, `price: float` → acepta NaN/Inf/negativos; validación real delegada al repo).
- 🟠 **Sin idempotencia** en `POST /api/portfolio/trade`.

---

## 1. Alcance de F1 (riesgo de dinero → prioridad 1)

**Objetivo:** garantizar que **ninguna operación mutante sobre cartera/cuenta/ledger pueda dejar la contabilidad incoherente**, ni por concurrencia, ni por doble envío, ni por error de precisión silencioso.

**Ámbito mutante cubierto:**

- Trade (buy/sell) — `execute_trade`
- Cash: `add_cash` / `deduct_cash` / `transfer_cash`
- Ledger: `append_*` (coherente con el balance real)
- Endpoint HTTP `POST /api/portfolio/trade`
- Idempotencia en mutations

**Fuera de F1 (se tratan en F2/F3/F5):** workers, `ensure_migrated` (F3), backtest (F2), auth (F5b, diferida), contratos FE/BE (F5a).

---

## 2. Micro-cambios atómicos (orden de implementación y commit)

Cada **M** es un commit independiente, atómico, con su batería. Se aprueban uno a uno.

### M1 — `with_for_update()` en mutaciones de cartera

**Ficheros:** `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/portfolio_repository.py`
**Qué:**

- En `execute_trade`: cargar `PortfolioRow` y `PositionRow` con `.with_for_update()` (bloquear la fila de cartera y la posición hasta commit).
- En `deduct_cash`, `add_cash`, `transfer_cash`: cargar las filas con `.with_for_update()`.
- En `transfer_cash`: lockear `from` y `to` en **orden determinista por id** (evitar deadlocks A→B / B→A).
  **Criterio de hecho:** todos los `session.get` + `select` mutantes llevan `.with_for_update()`; se mantiene la transacción (sin commit temprano). `ruff` + `mypy` + `pytest` verdes.

### M2 — Corregir `deduct_cash` (no truncar silenciosamente)

**Ficheros:** `portfolio_repository.py` (misma función)
**Qué:** si `row.cash < amount`, **lanzar `ValueError("Efectivo insuficiente...")`** en lugar de `fee = min(fee, row.cash)`. El único caller legítimo con descuento parcial era la custodia (`ApplyCustodyFees`), que ya valida `total_equity > 0` y descuenta una fracción; se revisa para que no rompa ni silencie.
**Criterio de hecho:** `deduct_cash` nunca reduce menos de lo pedido sin error. Tests actualizados/creados para ambo paths (ok + insuficiente).

### M3 — `ExecuteTrade.execute` usa el saldo real devuelto por el repo

**Ficheros:** `packages/py/application/src/bolsa_application/accounts.py` (método `execute`)
**Qué:** eliminar el recálculo manual de `trade_balance`; usar el `summary.portfolio.cash` resultante del repo como `balance_after` del ledger (única fuente de verdad).
**Criterio de hecho:** `balance_after` del ledger siempre coincide con el efectivo grabado en cartera; test de coherencia.

### M4 — Idempotencia + contrato estricto en `POST /api/portfolio/trade`

**Ficheros:** `apps/api-python/src/bolsa_api/schemas/portfolio.py` (DTO), `apps/api-python/src/bolsa_api/api/v1/routes/portfolio.py` (ruta), `packages/py/application/src/bolsa_application/accounts.py` (use-case), más tabla/índice si hace falta.
**Qué:**

- `TradeRequestDto`: `type: Literal["buy","sell"]`, `quantity: float = Field(gt=0)`, `price: float = Field(gt=0)`, `idempotencyKey`/`clientOrderId` opcional en request.
- Aceptar un `idempotency_key` opcional en mutaciones. Con `UNIQUE(account_id, idempotency_key)` y comprobación previa → si se repite, devolver el resultado original (no duplicar).
- Validación Pydantic estricta en el borde (rechaza NaN/Inf/negativos antes de llegar al repo).
  **Criterio de hecho:** doble `POST` con la misma `idempotency_key` produce **una sola** transacción; valores inválidos → 422 Pydantic (no 500). Tests de duplicación.

### M5 — Invariantes contables (tests)

**Ficheros:** tests nuevos bajo `packages/py/application/tests/` (o infra, según convención) — ej. `test_financial_invariants.py`
**Qué:** tests que verifican, ante operaciones concurrentes simuladas y secuenciales:

- `cash >= 0` siempre (no sobregiro).
- `position.quantity >= 0`.
- `executed_at` / `balance_after` coherentes.
- ledger reconcile: suma de movimientos = saldo final.
- idempotencia no duplica.
  **Criterio de hecho:** la suite F1 existe y pasa; se añade un smoke de concurrencia (dos `execute_trade` entrelazados) que demuestra que el lock evita el doble gasto.

---

## 3. Batería de verificación por micro-cambio

- **Py (siempre):** `ruff check` + `mypy` (cada fichero tocado) + `pytest` (paquetes afectados: application + infrastructure + api-python).
- **Global (al final de F1):** `pnpm test` / batería `pnpm test:operativa` etc. si algo del backend afecta al flujo de operativa (los tests de operativa ya cubren DÍA D/CORE-R; F1 no debería alterar esos flujos salvo cartera).
- **CI:** confirmar green en GitHub tras push.

---

## 4. Riesgos y mitigaciones

| Riesgo                                                                      | Mitigación                                                                                                                                                     |
| --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Que M2 (validar) rompa `ApplyCustodyFees` si descuenta más de lo disponible | Revisar su flujo: ya valida `total_equity > 0`; si `fee > cash`, decidir explícitamente (lanzar o descuento máximo documentado). Se decide en el micro-cambio. |
| Que añadir `with_for_update` degrade lecturas concurrentes                  | Solo se aplica a **escrituras**; las lecturas de `get_summary` no se tocan.                                                                                    |
| Que idempotencia requiera cambio de esquema                                 | Si hace falta columna/índice, se añade vía **Alembic** (alineado con D2), no por `db push`.                                                                    |
| Doctypes/DTOs compartidos en frontend al cambiar contrato de trade          | Solo se añaden campos **opcionales** (`idempotencyKey`); no se rompe el contrato actual. La generación OpenAPI es F5a, posterior.                              |

---

## 5. Orden de commits propuesto (secuencial)

1. `M1` `feat(infra): with_for_update en mutaciones de cartera`
2. `M2` `fix(infra): deduct_cash no trunca saldo silenciosamente`
3. `M3` `fix(app): ExecuteTrade usa saldo real del repo para ledger`
4. `M4` `feat(api): idempotencia y contrato estricto en POST trade`
5. `M5` `test(application): invariantes contables F1`

> Cada commit se revisa y aprueba antes de continuar. Si algo falla en un paso → volver al checkpoint `audit-checkpoint-2026-08-11`.

---

## 6. Criterio de "hecho" de F1

- Todas las mutaciones de cartera/estado usan bloqueo de fila (o idempotencia donde aplique).
- `deduct_cash` no reduce saldo silenciosamente.
- `balance_after` del ledger siempre coincide con el efectivo grabado.
- `POST /trade` es idempotente ante retry y rechaza valores no financieros.
- Suite de invariantes contables pasa.
- Batería completa (Py + global + CI) en verde. **Cero regresiones** en la operativa actual.

---

## 7. Registro

| Fecha      | Acción                                                                                                                                      |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-11 | Verificación en código del estado de F1 (Decimal ya en DB, falta de locks, deduct_cash, recálculo manual, DTO permisivo, sin idempotencia). |
| 2026-08-11 | Plan atómico M1–M5 redactado para revisión. **Pendiente de aprobación** por el usuario antes de abrir rama y tocar código.                  |
