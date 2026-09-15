# Audit Pack — V2.39.3 · Cierre del P1/N1 (lock de cuenta) y del P2/N2 (secuenciador forzado)

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.39.3** — cierra los dos hallazgos de la **auditoría interna sobre `v2.39.2-beta`**
> (AUDITORIA 1 y AUDITORIA 2) y el bug de `totalSamples` en `discovery_evidence.py`.
>
> **Base auditada:** `v2.39.2-beta` (`9444b364`).
> **Commit de código:** `b77a36aa` (package **`1.64.3-beta`**).
> **Tag:** `v2.39.3-beta` (anotado) — el auditor lo resuelve con `git rev-list -n 1 v2.39.3-beta`.
> **Alembic head:** `039_research_trials_regime` (esta fase **no** añade migración).
> **Flags:** sin cambios.
>
> **Nota de honestidad.** La verificación local está en verde (§6); el sello CI del tag
> (`release-tag-ci`) queda por ejecutarse en GitHub tras el push. Este documento no afirma
> un `GREEN` de CI hasta que `certify` lo confirme.

---

## 0. Resumen ejecutivo

La auditoría sobre `v2.39.2-beta` confirmó dos hallazgos sobre el **secuenciador del ledger**,
uno sobre `discovery_evidence.py` y un detalle a confirmar (no fallo) del script de limpieza:

| Hallazgo                                                                       | Naturaleza        | Impacto                                                                      |
| ------------------------------------------------------------------------------ | ----------------- | ---------------------------------------------------------------------------- |
| **P1/N1** — `next_executed_at` es por cuenta, pero el lock era de **cartera**  | Bug de producción | Dos carteras de la misma cuenta no se excluyen → `executed_at` **duplicado** |
| **P2/N2** — `append_*` aceptaba `executed_at` externo                          | Contrato débil    | Cualquier caller podía **saltarse el secuenciador** con `datetime.now()`     |
| **Auditoría 2** — `totalSamples` sumaba familias descartadas por `min_samples` | Bug de cálculo    | El contador global del carril `adaptive` quedaba **inflado**                 |
| Detalle del script de limpieza (`custody_obligation` vs `custody_obligations`) | **No es fallo**   | La migración 006 no borra la 005; ambas coexisten y la lista es correcta     |

**Veredicto:** el mutex financiero pasa a nivel de **cuenta** (alineado con la unidad de
secuenciación), los `append_*` **fuerzan** el secuenciador internamente (no por disciplina del
caller), y `totalSamples` publica solo la evidencia **útil**.

---

## 1. P1/N1 — Lock de cuenta (mutex financiero por cuenta)

**Diagnóstico.** `SqlAlchemyLedgerRepository.next_executed_at(account_id)` lee
`MAX(executed_at)` **por cuenta**, pero el lock que lo protegía era `with_for_update` sobre
`PortfolioRow` (por `legacy_portfolio_id`). Dos carteras de la **misma cuenta** no comparten
`legacy_portfolio_id`, así que sus escritores **no se excluyen entre sí**: ambos pueden leer el
mismo `MAX(executed_at)` antes del commit del otro y emitir asientos con **idéntico instante**
(el desempate por `id`, UUID v4 aleatorio, no rescata el orden).

**Fix.** Nuevo `SqlAlchemyAccountRepository.lock_account(account_id)`:

```python
stmt = (
    select(InvestmentAccountRow.id)
    .where(InvestmentAccountRow.id == account_id)
    .with_for_update()
)
```

Es el **mutex financiero por cuenta**. Se cablea como lock **externo**, antes de cualquier lock
de cartera, en los cuatro escritores financieros (orden determinista **cuenta → cartera**):

- `accounts/trade.py` — `ExecuteTrade.execute`: tras `resolve_scope`, antes de `execute_trade`.
- `accounts/cash.py` — `DepositCashToAccount.execute` y `WithdrawCashFromAccount.execute`.
- `accounts/custody.py` — `ApplyCustodyFees.execute`: tras `claim_custody_charge`, antes del primer `deduct_cash`.

El docstring de `next_executed_at` se actualiza: la exclusión es por **cuenta**, no por cartera.

---

## 2. P2/N2 — Forzar el secuenciador en los `append_*`

**Diagnóstico.** `append_trade`, `append_fee`, `append_custody_fee` y `append_cash_movement`
aceptaban `executed_at: datetime | None = None` con fallback `executed_at or now`, permitiendo
que cualquier caller **se saltara el secuenciador** con `datetime.now()`.

**Fix.** Se elimina el parámetro `executed_at` de los cuatro métodos y cada uno obtiene
internamente `await self.next_executed_at(account_id)`. La secuencia deja de ser disciplina del
caller y pasa a ser **obligatoria por infraestructura**.

Consecuencias en `accounts/trade.py`: se eliminan `_ledger_ordering`/`_FEE_ORDER_GAP` y la
llamada manual a `next_executed_at`; `append_trade` produce X y `append_fee` produce X+1µs de
forma natural (el orden trade→fee se conserva). `cash.py` y `custody.py` dejan de pasar
`executed_at`.

Callers y tests actualizados: `scripts/verify/verify_account_isolation.py` (no pasaba
`executed_at`), los fakes de `test_execute_trade_idempotency.py` (secuencian internamente) y
los fakes de cuenta de las suites de trade/cash/custody (ganan `lock_account` no-op).

---

## 3. Auditoría 2 — `totalSamples` inflado en `discovery_evidence.py`

**Diagnóstico.** `compute_lane_weights()` y el payload `"totalSamples"` sumaban
`sample_sizes.values()` **sin filtrar**, contando familias descartadas por `min_samples`. Con un
puñado de familias de pocos trials se podía superar `min_total_samples` con **un solo dato real**.

**Fix.** Se extrae un único cálculo:

```python
def _effective_total_samples(family_weights, sample_sizes):
    return sum(int(n) for key, n in sample_sizes.items() if key in family_weights)
```

y se usa en `compute_lane_weights()` y en el payload `"totalSamples"`. Ambos cuentan solo las
familias que superaron `min_samples` y aportan peso, unificando la puerta de decisión con lo
publicado al operador.

---

## 4. Test de concurrencia multi-portfolio (N3)

Nuevo test de regresión con PostgreSQL real en la suite chaos:
`packages/py/infrastructure/tests/chaos/test_multi_portfolio_ledger_sequence.py` →
`same_account_two_portfolios_concurrent_ledger_sequence`.

- Cuenta A con **dos carteras** (P1 default con seed + P2 creada con `PortfolioRow` +
  `InvestmentPortfolioRow`).
- Varias ráfagas concurrentes (2 carteras × 60 operaciones, 5 ráfagas) mezclando depósitos
  repartidos entre P1 y P2; cada escritor hace `lock_account(A)` → `add_cash` → `append_cash_movement`.
- Aserciones: `executed_at` **estrictamente creciente** por cuenta (sin duplicados);
  `sorted(ledger, executed_at)` reconstruye la cadena `balance_after` por cartera; M-2
  (`Σ ledger.amount == Σ cash`).

Nota: como `resolve_scope` colapsa a la cartera default, el test orquesta a nivel de repositorio
para reproducir exactamente la carrera entre dos carteras.

---

## 5. Detalle del script de limpieza — **no es fallo**

`scripts/ops/cleanup_residual_accounts.py` lista `custody_obligation` (migración 005) y
`custody_obligations` (migración 006) en `ACCOUNT_CHILD_TABLES`. Ambas tablas **coexisten
legítimamente**: la migración 006 introduce `custody_obligations` (tabla de obligación pendiente,
ADR-026) y **no borra** `custody_obligation` (obsoleta de 005). La lista es correcta tal cual; no
hay que tocarla.

---

## 6. Verificación

| Batería         | Comando                                                                                   | Resultado                               |
| --------------- | ----------------------------------------------------------------------------------------- | --------------------------------------- |
| Lint            | `ruff check packages/py apps/api-python --config pyproject.toml`                          | **All checks passed**                   |
| Tipos           | `mypy` full-tree (`domain/market/infrastructure/application/src` + `apps/api-python/src`) | **Success (477 ficheros)**              |
| Imports         | `lint-imports --config packages/py/.importlinter`                                         | **4 contratos kept, 0 broken**          |
| Aplicación      | `pytest` idempotencia trade/cash/custodia + `test_discovery_evidence.py`                  | **143 passed**                          |
| Infraestructura | `pytest` ledger / aislamiento / concurrencia / atomicidad / custodia                      | **12 passed**                           |
| Chaos           | `pytest packages/py/infrastructure/tests/chaos/test_multi_portfolio_ledger_sequence.py`   | **1 passed** (PG real `bolsa_v1_chaos`) |

Sin migración nueva (Alembic head `039_research_trials_regime`).

> **Nota de entorno (no del código).** La batería offline **completa** del job `quality` no se
> puede reproducir localmente en Windows: `test_vectorbt_optuna.py` importa `numba`, cuya DLL nativa
> la bloquea la directiva de Control de aplicaciones local (`os error 4551`). Es un bloqueo de
> entorno ajeno a este delta (el CI corre en Ubuntu, donde `numba` carga sin problema); la batería
> **salvo ese único módulo** queda cubierta y en verde por los resultados de la tabla. La
> certificación definitiva la ejecuta el CI en el tag.

## 7. Fuera de alcance (anotado, no tocado)

- `transfer_cash` no usa el secuenciador hoy; verificar en una pasada futura si escribe ledger y
  necesita el lock de cuenta.
- La alternativa **Opción B** (tabla `account_ledger_sequence` explícita) queda documentada como
  evolución futura si se quiere hacer explícito el recurso concurrente.
