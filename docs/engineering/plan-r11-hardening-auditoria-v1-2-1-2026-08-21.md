# PLAN — R-11: endurecimiento tras auditoría externa v1.2.1 (C1–C2–C3 núcleo financiero)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 · **AsOf:** 2026-08-21.
> **Propósito:** plan profundo aprobado por el propietario para corregir los hallazgos vigentes de la auditoría externa sobre **v1.2.1 (2093296)**. Alcance inicial aprobado: **C1 · C2 · C3** (núcleo financiero P1+P2). C4–D2 quedan documentadas como fases posteriores pendientes de revisión del propietario.
> **Estado:** **R-11 COMPLETA y CERRADA (2026-08-21)** — C1–C6 + D1 + D2 todas pusheadas a `main` (C1 `c3327c1` · C2 `17a1107` · C3 `cda26e9` · C4 `157bb45` · C5 `6762614` · C6+D2 `db95709` · D1 `870fb21`). Cierre/traspaso: `traspaso-relevo-cierre-r11-c1-c6-d1-d2-siguiente-2026-08-21.md`. Ver §3/§4.

---

## 0. Firma de estado inicial (verificada)

- `HEAD = 75e8c23` · `main = origin/main` · árbol **limpio** · tag **`v1.2.1`** sobre `2093296`.
- Proyecto NO en producción (paper/DEMO) → refactorizable manteniendo la idea.
- Base: R-10/v1.2.1 CERRADA. Siguiente migración Alembic que se cree será **`006_*`** encadenando sobre `005_custody_obligation`.

---

## 1. Confirmación de hallazgos de la auditoría externa (verificados en código)

| ID auditoría         | Descripción                                                                   | Evidencia verificada                                                                                                                                                                                                                                                                                          | Tipo                                          |
| -------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| **R-10.6** 🔴        | Pérdida de obligación PENDING al cambiar de año                               | `005_custody_obligation.py:41-59` (PK=`account_id`, una fila/cuenta) · `tables.py:1397-1401` · `custody_obligation_repository.py:70-75` (upsert sobrescribe `period/status/outstanding/total_fee`) · `accounts.py:576,662-671` (`period=now.year`) · `custody_job.py:66-74` (solo `get_by_account`, una fila) | **P1 financiero**                             |
| **#2** 🟠            | Custodia cobra de una única cartera pese a equity agregada                    | `accounts.py:595-623`                                                                                                                                                                                                                                                                                         | Def. documentar (Decisión: DEFAULT_PORTFOLIO) |
| **R-10.7 / #7** 🟠   | Repo trades acepta `idempotency_key=None`                                     | `portfolio_repository.py:323`                                                                                                                                                                                                                                                                                 | P2                                            |
| **R-10.7 / #8** 🟠   | Claves no validadas (vacías/whitespace)                                       | `schemas/accounts.py:291,299` · `schemas/portfolio.py:69`                                                                                                                                                                                                                                                     | P2                                            |
| **R-10.8 / #12** 🟠  | `Decimal→float→Decimal` en notional de trade                                  | `accounts.py:796`                                                                                                                                                                                                                                                                                             | P2                                            |
| **R-10.9 / #16** 🟠  | `contract:check` rojo por drift baseline (409 + DTOs estrictos no declarados) | backlog §0/§6 · deuda §3                                                                                                                                                                                                                                                                                      | Calidad/CI                                    |
| **R-10.9 / #17** 🟠  | mypy 7 errores preexistentes                                                  | traspaso §3 (`accounts.py:37,67,105,118,568,861,899`)                                                                                                                                                                                                                                                         | Calidad/CI                                    |
| **R-10.10 / #20** 🟠 | `CUSTODY_INTERVAL_DAYS=365` vs `period="%Y"`                                  | `accounts.py:555,584`                                                                                                                                                                                                                                                                                         | Def. documentar                               |

**Cerrados (sin acción):** idempotencia exacta 6 decimales · TaxProfileDto estricto · balance_after secuencial · custodia fuera del GET · idempotency_key API obligatoria · UNIQUE `(account_id, ref_type, ref_id, type)` · sesión epoch UTC · rate-limit · CORS.

---

## 2. Decisiones del propietario (2026-08-21)

| Ítem            | Decisión aprobada                                                                                                                                                                                                                                                                                                                      |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1 (R-10.6)     | **PK `id` autoincremental + `UNIQUE(account_id, period)`** con migración `006`; el job **liquida primero el PENDING más antiguo** antes de generar/cobrar el periodo nuevo.                                                                                                                                                            |
| C6 (#2)         | **DEFAULT_PORTFOLIO** explícito — cobrar siempre de la cartera default/seleccionada; **solo documentar** la regla, sin cambio de comportamiento. ✅ **DOCUMENTADA 2026-08-21** en [`docs/adr/026-custodia-obligacion-pendiente.md`](../adr/026-custodia-obligacion-pendiente.md) (fila 3 de «Decisiones del propietario» + Historial). |
| Alcance inicial | **C1 + C2 + C3** (núcleo financiero P1+P2). C4–D2 se revisan después.                                                                                                                                                                                                                                                                  |

---

## 3. Fases (orden, alcance exacto, batería)

### Fase C1 — 🔴 R-10.6 · Custodia multi-periodo (arreglo) — ✅ CERRADA (`c3327c1`)

- **Migración `006_custody_obligations_period`:** nueva tabla `custody_obligations` con PK `id` + `UNIQUE(account_id, period)` + `created_at`/`updated_at`; migrar filas existentes de `custody_obligation` preservando PENDING actuales (D6: sin backfill retroactivo).
- **Modelo `tables.py` + repo** `custody_obligation_repository.py`: `list_pending_by_account`, `get_by_account_period`, `upsert(account_id, period)`.
- **`ApplyCustodyFees` / `RunCustodyJob`:** liquidar primero el PENDING más antiguo (cobro parcial si el saldo no cubre el total); después generar/cobrar el periodo actual.
- **Tests:** `test_custody_obligation_multi_period.py` (PENDING 2026 + 2027 coexisten sin sobrescritura; job cobra primero el más antiguo; PENDING no bloquea el proceso del periodo nuevo). Migración desde DB con filas 005 existentes.
- **Batería:** ruff 0 · mypy ficheros tocados · pytest zona custodia (app + infra PG real) · verificar invariante Σ ledger == cash.
- **Resultado ✅ (`c3327c1`, pusheado `main`):** tabla `custody_obligations` PK `id` autoincrement + `UNIQUE(account_id, period)` + `created_at`/`updated_at`; migración Alembic `006_custody_obligations_period` (encadena sobre `005`); reparado el `upsert` para no sobrescribir y añadidos `get_pending_by_account`/`get_by_account_period`; `ApplyCustodyFees` y `RunCustodyJob` liquidan primero el PENDING más antiguo antes del periodo nuevo.

### Fase C2 — 🟠 R-10.7 · Endurecer `idempotency_key` end-to-end — ✅ CERRADA (`17a1107`)

- DTOs `schemas/accounts.py` y `schemas/portfolio.py`: `str` con `min_length=16`, `max_length=128`, `strip()` y rechazo de whitespace → 422 limpio.
- `portfolio_repository.py:execute_trade`: `idempotency_key: str` obligatorio; rechazo explícito de `""`/whitespace.
- Tests unit + API integr (sin clave, clave vacía, clave válida 16–128, whitespace).
- **Batería:** ruff 0 · pytest app + api-python · sin regen OpenAPI salvo decisión contrato (no propio de esta fase).
- **Resultado ✅ (`17a1107`, pusheado `main`):** DTOs `DepositCashDto`/`WithdrawCashDto`/`TradeRequestDto` con `str_strip_whitespace=True`, `min_length=16`, `max_length=128`; repo `execute_trade` con `idempotency_key: str` obligatoria y rechazo de `""`/whitespace; guard en `ConfirmRecommendationIntent` (uuid4 fallback).

### Fase C3 — 🟠 R-10.8 · Eliminar `Decimal→float→Decimal` en notional de trade — ✅ CERRADA (`cda26e9`)

- `accounts.py:796` y `cash_before/trade_balance/fee_balance` en `Decimal` íntegro hasta `Numeric(18,6)`; float solo en el borde del wire contract (compat frontend, sin cambio de schema).
- Tests de precisión con >6 decimales y comparación exacta.
- **Batería:** ruff 0 · mypy · pytest trade/fee (app + infra PG real) · invariante secuencial.
- **Resultado ✅ (`cda26e9`, pusheado `main`):** precisión Decimal end-to-end en `ExecuteTrade.execute` (`notional`/`cash_before`/`amount`/`trade_balance`/`fee_balance` en `Decimal`, `float` solo en el borde al invocar repo/ledger); invariante secuencial exacta.

---

## 4. Fases posteriores (documentadas, NO autorizadas para ejecutar ahora)

| Fase | Contenido                                                                                                | Dependencia           |
| ---- | -------------------------------------------------------------------------------------------------------- | --------------------- |
| C4   | `contract:check` EXIT 0: exponer `409` + DTOs estrictos en OpenAPI (decisión contrato, patrón `aecbb28`) | Decisión proprietario |
| C5   | `mypy` == 0 en gate CI (7 preexistentes)                                                                 | —                     |
| C6   | Documentar `custody_charge_source = DEFAULT_PORTFOLIO` (Decisión del propietario)                        | —                     |
| D1   | Limpieza transversal `pending-delete` que cumpla criterio E8 (sin tocar RIESGO ALTO)                     | Previa revisión       |
| D2   | Docstrings + actualización `PROJECT_STATE`/backlog/index/ADR/CHANGELOG                                   | Post C1–C5            |

> **ESTADO (2026-08-21):** **R-11 COMPLETA y CERRADA.** **C4 ✅ CERRADA** (`157bb45`) — `contract:check` EXIT 0 (Opción A): regen acotada de `apps/web/api/openapi.json` (`idempotencyKey` con `minLength/maxLength` R-11 C2 · `TaxProfileDto` con `minimum:0.0` R-10 F1); `schema.d.ts` sin cambio; el 409 sigue solo en runtime (handler global), no en OpenAPI (decisión C4 Opción A). · **C5 ✅ CERRADA** (`6762614`) — mypy == 0 en gate CI: añadida `packages/py/application/src` al step Mypy de `.github/workflows/python-ci.yml`; limpiados **105 errores en 33 ficheros** de la capa application; semántica mínima en `ledger_repository` (`limit: int|None=50`), `market_indices`, `fetch_core_r_pnl_extra_rows` (guard numérico), `scans.py` (fix de `TypeError` latente: `expected_last_daily_bar()` se invocaba sin el `exchange` obligatorio; ahora por instrumento). · **C6 ✅ DOCUMENTADA 2026-08-21** en ADR 026 (política `DEFAULT_PORTFOLIO`; solo documenta la regla, sin cambio de comportamiento). · **D2 ✅ CERRADA** (`db95709`, con C6) — fase documental C6+D2 (docstrings + estado documental): este plan, backlog §0/§6, PROJECT_STATE, engineering-index y CHANGELOG (sección `## R-11 hardening post-v1.2.1 — 2026-08-21`, sin tag) se actualizaron aquí. · **D1 ✅ CERRADA** (`870fb21`) — limpieza transversal E8: `custody_obligation_repository.get_by_account` + `get_by_account_period` (0 callers producción) quitados del repo y de fakes de test; se mantienen `get_pending_by_account`/`upsert`; **sin tocar ítems RIESGO ALTO**. **Sin tag de release R-11** (último `v1.2.1`). Relevo activo: `traspaso-relevo-cierre-r11-c1-c6-d1-d2-siguiente-2026-08-21.md`.

**Aparcado (freeze/decisión, NO en este ciclo):** puente legacy↔nuevo (V2/ADR) · auditoría de caos financiero (propuesta tras C1–C5) · scheduler-vs-worker (R-8C.2) · gobernanza IA · semver real de packages.

---

## 5. Protocolo de ejecución (premisas E1–E9)

1. Una fase = un subagente acotado, alcance disjunto, brief con read-first backlog §0/§1 + premisas E1–E9 + archivos exactos + batería esperada. **No commits ni push** por el subagente.
2. El coordinador **re-verifica** cada diff y corre la batería él mismo antes de proponer commit.
3. **Aprobación del propietario por commit** y push a `main` (rama protegida).
4. Test/script de verificación en cada fase (E6); docstrings en lo tocado (E5); actualizar backlog/PROJECT_STATE al cerrar (E9).
5. Control de saturación: máx ~3 subagentes en paralelo con alcances disjuntos; si se satura el hilo, relevo con texto de paso firmado.
