# Evidencia `v2.88.70-beta` — `NÚCLEO`: **equity del libro en el turno**

**Producto:** `V2.88.70-beta` · **Package:** `2.11.70-beta` · **AsOf:** 2026-10-06. **SIN migración.** **Δ motor ≠ 0.**

**Padre:** [`v2.88.69`](../v2.88.69/README.md).

## Qué cambia

El scheduler (`AutoSimRuntime.run_tick`) lee `GetPortfolioSummary.total_equity` en la sesión del tick y esa cifra es la equity del turno. Si la lectura lanza, falta la cuenta, o el valor no es positivo, las compras quedan vetadas (`book_equity_unreadable`). No hay sustitución silenciosa por `AUTO_ENGINE_SIM_V2_EQUITY` ni por 100_000.

El camino hermético no llama a `load_book_equity`. Ahí la base declarada por env sigue existiendo, porque esos tests no abren el libro.

## Test

`test_book_equity_is_authority_when_required` y `test_unreadable_book_vetoes_and_does_not_fall_back_to_100k` — **passed**.

## Replay

No se fuerza el hash `1E3ADAC2`. Este sello cambia la decisión del turno real.
