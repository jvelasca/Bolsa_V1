# Traspaso — F1 Integridad financiera (2026-08-11)

> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5 (sub-entrada del Plan F1).
> **Fuentes de verdad (leer primero):** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) (mapa P0/P1/P2 + D0–D5) · [plan-f1-integridad-financiera-2026-08-11.md](./plan-f1-integridad-financiera-2026-08-11.md) (M1–M5, documento de trabajo).
> **Checkpoint git:** tag anotado `audit-checkpoint-2026-08-11` (HEAD `2683c49` · árbol con docs sin commitear). **Punto de retroceso.**
> **Rama de ejecución:** `stage/f1-integridad-financiera-2026-08-11` (**CREADA desde `7edb3d1`**, decisión del usuario; no desde el checkpoint) · remota `origin/stage/f1-integridad-financiera-2026-08-11`.
> **Regla del hilo:** NO se toca código fuera de F1. Cada micro-cambio atómico se valida con la batería (ruff+mypy+pytest) antes de commit. Commit + push por paso aprobado. Si algo falla → volver al checkpoint.
> **Estado:** F1 EN CURSO. M1 (`3d093cb`) y M2 (`113e27a`) COMMIT+push aprobados. M3 EN CURSO. Ver §5 y §7.

---

## 1. Objetivo de F1

Garantizar que **ninguna operación mutante sobre cartera/cuenta/ledger pueda dejar la contabilidad incoherente** (concurrencia, doble envío, precisión silenciosa). Riesgo de dinero → orden F1 primero (D0). Cero features (D5).

## 2. Hallazgos verificado en código (matizan a las auditorías)

- ✅ La DB **ya usa `Decimal`/`Numeric(18,6)`** en todo el dinero (`tables.py`). **No migrar esquema.**
- ⚠️ El `float` vive solo en **dominio** (`Portfolio.cash`, `Transaction.*`, `AccountSummary.*`, `LedgerEntry.*`, `CashMovementResult.*`) y **DTOs HTTP** (`schemas/portfolio.py`); se pasa a `Decimal` al borde del repo.
- 🔴 `execute_trade` / `deduct_cash` / `transfer_cash` / `add_cash` usan `session.get` **sin `with_for_update()`** → M1.
- 🔴 `deduct_cash` hace `fee = min(fee, row.cash)` (descuento **silencioso** de lo pedido) → M2.
- 🟠 `ExecuteTrade.execute` recalcula `trade_balance` a mano en vez de usar el saldo devuelto por el repo → M3.
- 🟠 `TradeRequestDto` permisivo (`type: str`, `quantity/price: float` → NaN/Inf/negativos) y **sin idempotencia** en `POST /api/portfolio/trade` → M4.
- 🟠 Sin tests de invariantes contables → M5.

## 3. Decisiones ya pactadas (no renegociar)

- **D0** orden: F1 → F2 → F3b → F5a → (F3a + F4 + F5b).
- **D1** backtest `next_open` + recálculo trials → **F2, NO ahora**.
- **D2** Alembic única autoridad BD; usar Alembic en F1 **solo si** idempotencia requiere columna/índice nuevo (nunca `db push`).
- **D4** auth local diferida. **D5** solo F1–F5, cero features.

## 4. DECISIÓN M2 RESUELTA — Opción B (acordada en el traspaso, 2026-08-11)

> **No renegociar.** Es la que fija la implementación de M2.
>
> **Problema estructural confirmado en código:** `ApplyCustodyFees.execute` (`application/accounts.py`) calcula el cargo sobre el **patrimonio total** (`total_equity * pct/100`) pero lo descuenta del **cash de una sola cartera** (`deduct_cash(charge_legacy_id, fee_amount)`). Por tanto `fee > cash` es un caso **esperable** (patrimonio invertido ≠ cash disponible), no un error de uso.

### Resolución

- `deduct_cash` gana una **política explícita** de agotamiento: `allow_partial: bool` (default `False`).
- `allow_partial=False` (operaciones de **usuario**: trade): si `amount > row.cash` → **`ValueError("Efectivo insuficiente...")`**, sin truncar. → arregla M2.
- `allow_partial=True` (solo **custodia**): descuenta **lo que haya** (mínimo) y `ApplyCustodyFees` lo registra en el ledger de forma **explícita y parcial documentada** (importe real en `amount`, `balance_after` real, descripción aclarando cargo parcial por saldo). Nunca descuento menor "en silencio": queda en ledger.

### Efectos

- No rompe el GET que invoca la custodia (`GetAccountSummary`/`GetTaxReport`); la custodia no pasa por el camino que lanza error.
- M2 se cumple tal cual ("nunca descuento menos de lo pedido en silencio"): el parcial es explícito y trazable.

### Nota (NO tocar en F1)

- El audit **P1.1**: un GET muta saldos vía `ApplyCustodyFees`. Es **fase F3/F5**, fuera de F1. Solo anotar en el registro.

---

## 5. Orden de commits (M1 → M5, aprobación previa a cada uno)

| #      | Commit                                                       | **Qué**                                                                                                                                                                                                                               | Ficheros                                                                                            |
| ------ | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **M1** | `feat(infra): with_for_update en mutaciones de cartera`      | `with_for_update()` en `execute_trade`/`deduct_cash`/`add_cash`/`transfer_cash`; en `transfer_cash` lockear from+to en **orden determinista por id** (evitar deadlock A→B/B→A).                                                       | `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/portfolio_repository.py` |
| **M2** | `fix(infra): deduct_cash no trunca saldo silenciosamente`    | Añadir `allow_partial: bool=False`; usuario→ValueError; custodia→parcial documentado en ledger.                                                                                                                                       | `portfolio_repository.py` + `application/accounts.py` (`ApplyCustodyFees`) + tests                  |
| **M3** | `fix(app): ExecuteTrade usa saldo real del repo para ledger` | Eliminar recálculo manual de `trade_balance`; usar `summary.portfolio.cash` devuelto por el repo como `balance_after`.                                                                                                                | `apps/api-python/src/bolsa_api/...` (o `application/accounts.py` método `execute`)                  |
| **M4** | `feat(api): idempotencia y contrato estricto en POST trade`  | `TradeRequestDto`: `Literal["buy","sell"]`, `gt=0`, rechazar NaN/Inf/neg (422 Pydantic); `idempotency_key` opcional con `UNIQUE(account_id, idempotency_key)` (Alembic si columna nueva). Doble POST idéntico → una sola transacción. | `schemas/portfolio.py` · ruta `portfolio.py` · `application/accounts.py` ± Alembic                  |
| **M5** | `test(application): invariantes contables F1`                | Suite `test_financial_invariants.py`: cash≥0, qty≥0, reconcile ledger, anti-doble-gasto bajo concurrencia (dos `execute_trade` entrelazados).                                                                                         | tests nuevos en `packages/py/application/tests/` (o infra)                                          |

**Criterio de hecho F1:** todas las mutaciones con bloqueo de fila (o idempotencia); `deduct_cash` sin descuento silencioso; `balance_after` = cash grabado; `POST /trade` idempotente y estricto; suite invariantes verde; batería Py + `pnpm test` + CI green; cero regresiones operativa.

## 6. Batería por micro-cambio

- **Py (siempre):** `ruff check` + `mypy` (por fichero tocado) + `pytest` (application + infrastructure + api-python).
- **Global (fin de F1):** `pnpm test` / batería operativa (DÍA D, CORE-R — no debería alterarse salvo cartera).
- **CI:** green en GitHub tras push.

## 7. Registro

| Fecha      | Acción                                                                                                                                                                                                                                                                                                                                         |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-11 | Traspaso creado tras leer los 3 docs fuente de verdad y verificar el código (estado git: HEAD `2683c49` = checkpoint, tag ok, sin rama F1 aún).                                                                                                                                                                                                |
| 2026-08-11 | **M2 resuelta = Opción B** (acordada con el usuario en el chat de traspaso): `allow_partial` explícito, usuario→ValueError, custodia→parcial documentado.                                                                                                                                                                                      |
| 2026-08-11 | Rama `stage/f1-integridad-financiera-2026-08-11` creada **desde `7edb3d1`** (decisión del usuario; incluye traspaso+plan+auditoría).                                                                                                                                                                                                           |
| 2026-08-11 | **M1 commit+push `3d093cb`** — `with_for_update()` en `execute_trade` (portfolio+position), `deduct_cash`, `add_cash`, `transfer_cash` (lock determinista por id). Ruff✓ · mypy✓ · pytest 257✓.                                                                                                                                                |
| 2026-08-11 | **M2 commit+push `113e27a`** — `deduct_cash(allow_partial: bool=False)`; usuario→ValueError; `ApplyCustodyFees` con `allow_partial=True` registra importe real + `balance_after` real + descripción de cargo parcial. Test `test_deduct_cash_allow_partial.py` (3, DB-requeridos, skip sin PG). Ruff✓ · pytest 260✓ · mypy sin errores nuevos. |
| 2026-08-11 | M3 EN CURSO — `ExecuteTrade.execute` debe usar `summary.portfolio.cash` del repo como `balance_after` (eliminar recálculo manual de `trade_balance`). Deuda mypy pre-existente en `accounts.py` (no-untyped `execute`), gate mypy es `continue-on-error: true`.                                                                                |

---

## 8. Protocolo recurrente (obligatorio en TODOS los hilos)

> Establecido en el chat de traspaso (2026-08-11) como **norma permanente** de este proyecto, no solo de F1.

1. **Al cerrarse cualquier hilo de chat** (fin de módulo, fase, frente o saturación de contexto), el agente DEBE **preparar el siguiente hilo** antes de terminar: crear/actualizar su `traspaso-*` con estado, decisiones y deuda residual.
2. El traspaso DEBE incluir **el texto exacto** que el usuario deberá pegar al abrir el siguiente chat, listo para que un agente nuevo arranque sin re-leer todo el contexto.
3. Cada traspaso lista su **un solo padre** en el índice (regla de docs) y añade/actualiza su entrada en `engineering-index-2026-08-03.md`.
4. El texto exacto de traspaso del próximo hilo se entrega al usuario **de forma explícita en el propio chat** (block de pegado), no solo guardado en el doc.

**Este documento, §8, es el ancla normativa** para "preparar el siguiente hilo con su texto exacto".

---

## 9. Texto exacto de traspaso — siguiente hilo (F1, continúa en M3)

> Pegha este bloque en un chat NUEVO si este hilo se satura. Arranca en M3 sobre la rama ya creada. No renegociar D0–D5 ni M2 (Opción B).

```text
Texto de traspaso → nuevo chat (F1 — Integridad financiera, continuación M3/M4/M5)

Lee docs/engineering/traspaso-f1-integridad-financiera-2026-08-11.md (documento de
trabajo, ya actualizado con el progreso de ejecución) y sus fuentes [plan-f1-2026-08-11.md]
y [audit-consolidado-internas-externas-2026-08-11.md]. Trabaja SOBRE ESE CONTEXTO y NO
toques nada fuera del alcance.

ESTADO git (verificado): rama stage/f1-integridad-financiera-2026-08-11 (local, rastrea
origin). HEAD en el último commit aprobado. M1=3d093cb (with_for_update) y M2=113e27a
(deduct_cash allow_partial) COMMIT+push aprobados. M3 SIGUIENTE.

Checkpoint de retroceso: tag audit-checkpoint-2026-08-11 (2683c49). Si un paso falla,
volver al checkpoint.

Decisiones pactadas (NO renegociar): D0 orden F1→F2→F3b→F5a→(F3a+F4+F5b). D1 backtest
→F2. D2 Alembic única autoridad BD (nunca db push). D4 auth diferida. D5 solo F1–F5.
M2 RESUELTA = Opción B: deduct_cash tiene allow_partial:bool=False (usuario→ValueError;
solo custodia usa True→parcial explícito en ledger; nunca en silencio).

FICHEROS NUCLEO ya modificados por mí (M1+M2): portfolio_repository.py (execute_trade/
deduct_cash/add_cash/transfer_cash con with_for_update) y accounts.py (ApplyCustodyFees
registra importe real parcial). Nuevo test test_deduct_cash_allow_partial.py.

PENDIENTE (orden, aprobación previa a cada commit):
- M3 ExecuteTrade.execute usa saldo real del repo (summary.portfolio.cash) como
  balance_after, elimina recálculo manual de trade_balance.
- M4 idempotencia idempotency_key UNIQUE(account_id,key) vía Alembic (solo si columna
  nueva, nunca db push) + TradeRequestDto estricto (Literal buy/sell, gt=0, rechaza
  NaN/Inf/neg → 422) en POST /api/portfolio/trade.
- M5 suite invariantes contables (cash>=0, qty>=0, reconcile ledger, anti-doble-gasto
  bajo concurrencia). Según convenga integrar el test DB de M2 en la suite.

Deuda técnico conocida: mypy gate es continue-on-error:true (P1.6); hay no-untyped
execute() pre-existentes en accounts.py — NO es regresión de F1, no tocar fuera de alcance.

Protocolo (innegociable): NO tocar código fuera de F1. Batería por cambio (ruff+mypy+
pytest). Commit atómico+push por paso aprobado. Al terminar F1: pnpm test + CI green +
cero regresiones. Al saturarse o acabar, preparar siguiente hilo con su texto exacto.
```
