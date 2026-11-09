# Dinero en `Decimal` — Fase 2.3 — 2026-11-08

Cierre de `p2-decimal` (Fase 2 / 2.3 del plan de remediación). El dominio contable deja de
acumular dinero en `float`; el contrato HTTP no cambia.

## Política (una sola, ejecutable)

`packages/py/domain/src/bolsa_domain/money.py` es la fuente de verdad:

- **Campo monetario ⇒ `Decimal`**: nombres `amount`, `price`, `cost`, `fee`, `commission`,
  `balance`, `equity`, `cash`, `pnl`, `value`, `deposit`, `outstanding`, `margin_used`,
  `free_margin` y `total`, incluidos sus compuestos (`total_equity`, `avg_cost`,
  `balance_after`, `total_fee`, ...).
- **Ratio ⇒ `float`**: `*_pct`, `*_ratio`, `leverage`. Son magnitudes continuas que no se
  suman en un libro de caja.
- **Conversión**: `to_decimal` usa `Decimal(str(valor))`. No inventa precisión: `0.1`
  entra como `Decimal("0.1")`; `0.1 + 0.2` entra como `Decimal("0.30000000000000004")`
  porque ese ya es otro número. Rechaza `bool`, `NaN`, `Infinity`, `None` y texto no
  numérico.
- **Redondeo explícito**: `quantize_money` (céntimos) y `quantize_price` (4 decimales),
  ambos `ROUND_HALF_EVEN`. Construir la entidad **no** redondea; el redondeo se declara
  donde se persiste o publica.
- **`None` = no medido**, nunca un cero fabricado. `coerce_money_fields` conserva `None`.

## Qué se migró

- Entidades de libro (`packages/py/domain/src/bolsa_domain/entities/`):
  - `InvestmentAccount.initial_deposit`.
  - `AccountSummary`: `cash`, `total_market_value`, `total_cost`, `total_unrealized_pnl`,
    `total_equity`, `margin_used`, `free_margin`, `total_realized_pnl`.
  - `LedgerEntry`: `amount`, `balance_after`, `price`.
  - `CashMovementResult`: `amount`, `balance_after`.
  - `CustodyObligation`: `outstanding`, `total_fee`.
  - `Portfolio.cash`; `Position`: `avg_cost`, `last_price`, `market_value`,
    `unrealized_pnl`; `PortfolioSummary` (4 totales); `Transaction`: `price`, `total`.
  - Normalización en `__post_init__` con `coerce_money_fields`, así que mocks, tests y
    llamadores que sigan pasando `float` no rompen: obtienen `Decimal`.
- Repositorio de cartera (`portfolio_repository.py`): `_latest_closes` y
  `_latest_transaction_prices` devuelven `dict[str, Decimal]`; el resumen se calcula en
  `Decimal`.
- Aplicación: `accounts/summary.py` (margen y margen libre en `Decimal`), `accounts/custody.py`
  (`fee_amount = quantize_money(total_equity * pct / 100)`), `accounts/tax.py` y
  `tax_report.py` (conversión explícita `Decimal -> float` en el borde de la calculadora
  fiscal).
- DTOs (`apps/api-python/src/bolsa_api/schemas/accounts.py`): los campos monetarios usan
  `Money = Annotated[Decimal, PlainSerializer(float, when_used="json"), WithJsonSchema(
  {"type": "number"}, ...)]`.
  - El JSON sigue siendo **número**, no string: `schema.d.ts` y los consumidores TS no
    cambian.
  - Los dos `WithJsonSchema` (validación y serialización) impiden que OpenAPI degrade el
    tipo a `string`.
  - `account_mappers.settings_dto_to_domain` convierte los topes de comisión a `float` para
    `CommissionProfile`, que sigue en `float` por contrato (ver excepciones).

## Bordes que siguen en `float` (declarados, no olvidados)

`packages/py/domain/tests/test_money_decimal_guard.py` recorre **todas** las dataclasses de
`bolsa_domain` y falla si un campo monetario numérico no es `Decimal`, salvo las clases
listadas en `EXEMPT_CLASSES` con su motivo:

| Clase | Motivo |
| --- | --- |
| `CommissionProfile`, `TradeFeeBreakdown` | Calculadora de comisiones en `float`; el importe final entra como `Decimal` al asiento. |
| `BacktestRun`, `BacktestRunDetail`, `BacktestTrade` | Motor vectorizado (numpy) trabaja en `float`; no es un libro contable. |
| `PredictionRecord` | `value` es una métrica de predicción, no dinero. |
| `LiveQuoteReference` | Precio entrante del proveedor; se convierte al cruzar al dominio contable. |
| `_ResidualPosition`, `TaxReportTransaction`, `RealizedGainLine`, `UnrealizedGainLine`, `TaxReportSummary` | Calculadora fiscal en `float`; el mapeador convierte `Decimal -> float` en el borde. |

`optimize.py` no acumula dinero: sus salidas son ratios/métricas y `initial_cash` es un
escalar que alimenta el simulador vectorizado (numpy). Convertirlo forzaría aritmética
`Decimal` dentro de numpy sin ganancia de correctitud; el módulo lo declara en su docstring
y el guard cubre las entidades.

El test también es un ratchet contra la lista obsoleta: si una clase exenta deja de tener
campos monetarios en `float`, **obliga a borrar la excepción**. Y `test_guard_detects_a_violation`
demuestra que el guard falla de verdad con una clase sintética.

## Cómo añadir un campo monetario

1. Anótalo `Decimal` (o `Decimal | None` si `None` = no medido).
2. Añádelo a la llamada `coerce_money_fields(self, ...)` del `__post_init__`.
3. Cuantiza solo en el borde (`quantize_money` al persistir/publicar).
4. En un DTO, usa `Money`, no `Decimal` a secas: mantiene el JSON numérico.
5. Ejecuta el guard; si el campo es de un borde deliberado, añade la clase a
   `EXEMPT_CLASSES` **con motivo**.

## Verificación ejecutada

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run pytest packages/py/domain/tests/test_money_decimal_guard.py -q
uv run pytest packages/py/{domain,market,infrastructure,application,analytics}/tests -q
uv run pytest apps/api-python/tests -q
```

- Ruff: `All checks passed!`
- Import-linter: `4 kept, 0 broken`.
- Guard: 15 passed.
- Paquetes: **5.395 passed**.
- API: **1.805 passed, 7 skipped**. Los fallos que aparecieron con una BD scratch sin datos
  de mercado (`risk_veto` por `mandate`/sin barras) se resolvieron copiando `instruments` y
  `ohlcv_bars` del entorno de desarrollo a la BD scratch; no eran regresiones.
- `mypy` no se pudo ejecutar en esta máquina: Windows Application Control bloquea el
  binario (`os error 4551`). Queda como verificación pendiente en CI.

`Δ motor = 0`: mismos valores, misma semántica; solo cambia el tipo que los transporta y el
punto donde se redondea. El contrato HTTP (`openapi.json` / `schema.d.ts`) conserva
`number`.
