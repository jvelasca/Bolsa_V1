# Evidencia `v2.88.149-beta` — auditoría read-only: el gate de régimen de la ventana PAPER es inalcanzable por construcción

> **Bump:** `2.11.148-beta` → **`2.11.149-beta`** (`package.json` + `meta.bump` de los **13** CLIs;
> guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py)
> **2 passed**). Tag **unsigned**.
>
> **Cambio:** **sólo documentación + un instrumento read-only**. No se toca el motor, ni umbrales,
> ni pesos A/B, ni el contrato HTTP, ni el esquema: **`Δ motor = 0`** · **`Δ decisión = 0`** ·
> **`Δ contrato HTTP = 0`** (`openapi.json`/`schema.d.ts` **sin diff**) · **SIN migración**
> (head `056_auto_ops_jobs`). Auditoría completa:
> [`auditoria-alcanzabilidad-ventana-paper-2026-10-19.md`](../../auditoria-alcanzabilidad-ventana-paper-2026-10-19.md).

## 1. La pregunta

Tras el sello `.148`, la ventana PAPER seguía en **`NO_MEDIDO`**: `3` días de ventana, `0` medidos,
`3` vetos por `BEAR_TREND`. El estado del proyecto lo describía como «falta **OPERACIÓN**». Esta
auditoría comprueba si eso es cierto o si el gate de la ventana es **inalcanzable por
construcción**.

## 2. Método (read-only, mismas piezas que el tick)

- Preflight real: `pnpm window:preflight` (no escribe nada).
- Recomposición: `make_bar_snapshot_loader` → `classify_market_regime` →
  `aggregate_trial_regime` → `map_trial_regime` → `regime_allows_entry_for`.
- **Backtest as-of**: para cada índice `t`, clasificar cada símbolo **sólo** con `bars[:t+1]`.
- Instrumento reproducible (solo `SELECT`):
  [`audit_regime_reachability.py`](./audit_regime_reachability.py).

## 3. Lo medido

| Medición | Resultado |
| --- | --- |
| Preflight de hoy (`2026-10-19`) | watch **35** (ESTUDIO) · `trend_down 22` / `range 8` / `trend_up 5` ⇒ **`BEAR_TREND`** ⇒ LONG **vetadas** (exit 2) |
| Frescura | **120** barras por símbolo; última `2026-10-16` (34) o `2026-10-19` (1, parcial) |
| Bajistas | movimiento 10d-vs-40d **-9,07 % … -1,11 %**; **0** con `·<1 %·` ⇒ **no hay ruido clasificado** |
| Ledger del runner | `20261014/15/16` = `NO_MEDIDO_REGIMEN`; `20261017/18` = `NON_MARKET_DAY` |
| **Alcanzabilidad as-of** | **61** fechas: agregado `trend_down` **61/61** ⇒ **0/61** con LONG permitidas |
| Mejor fecha as-of | **30/35 (85,7 %)** no bajistas ⇒ **también** vetada |

**Dictamen:** el detector no está sesgado y el veto es correcto **respecto al motor** (el motor es
long-only y consume **un único eje global** por tick). Pero como el agregado es el **peor caso
presente** (`_REGIME_CONSERVATIVE_PRIORITY`), un solo símbolo en `trend_down` veta los otros 34: un
día medible exige **unanimidad** no-bajista, y eso no ocurrió en **ninguna** de las 61 fechas.

## 4. Qué NO cambia (invariantes)

- **SIM-only:** ninguna orden real; la operativa sigue contra ledger virtual/PAPER.
- **Decisión:** sin umbrales, reparto, `TOP_N`, régimen, protección ni ejecución tocados.
- **Contrato HTTP:** `openapi.json`/`schema.d.ts` **sin diff**; `contract:check` **OK**.
- **Ventana PAPER:** sigue **`NO_MEDIDO`** (`3` días de ventana, `0` medidos) ⇒ **no demuestra
  rentabilidad**; la **magnitud del P&L** sigue **NO MEDIDA**.

## 5. Verificación medida

| Comando | Resultado |
| --- | --- |
| `pnpm lint:py` | **`All checks passed!`** |
| `pnpm imports:py` | **`4 kept, 0 broken`** |
| `pnpm types:py` | **`Success: no issues found in 566 source files`** |
| `python -m pytest test_dia_d_bump_guard` | **2 passed** |
| `pnpm window:test` | **48 passed** |
| `pnpm contract:check` | **OK** |
| `git diff --name-only -- packages/py apps/api-python/src` | **vacío** ⇒ `Δ motor = 0` |
| `pnpm window:freeze` | **TREE_MOVED** (esperado: el bump toca `apps/api-python/scripts`) ⇒ re-anclaje y **`freeze OK`** |

## 6. Límites declarados (sin fabricar)

- **5 filas** de ledger observadas; la del `14/10` se lee de sus etiquetas (watch de 20 del
  catálogo, ya no reconstruible).
- El backtest usa el **watch ACTUAL** (ESTUDIO, 35), alinea por **índice** (no por calendario) y
  el universo está **seleccionado a día de hoy** ⇒ sesgo de supervivencia **declarado**. Mide
  **alcanzabilidad del gate**, no el histórico de la ventana.
- El instrumento **sólo hace `SELECT`**: no escribe ledger, journal, pin ni BD.
- **No** se baja ningún umbral ni se fuerza el régimen; **no** se escogen símbolos por su régimen
  (sería look-ahead).
- La auditoría **no** promociona evidencia, **no** emite `CONFIRMED` y **no** demuestra
  rentabilidad.

## 7. Publicación

Commit de la auditoría + bump (`1cf7fb75`) y re-anclaje del pin (`637a4433`, `window:freeze OK`).
Tag `v2.88.149-beta` (**anotado, unsigned**) publicado junto con `main`.

**`Release tag CI` [run `39231461820`](https://github.com/jvelasca/Bolsa_V1/actions/runs/39231461820) VERDE**
(09:37:29Z → 09:49:27Z, ~**11m58s**; **13 jobs `success` + `certify` `success`**; `playwright (integrated
E2E, opt-in)` `skipped`, declarado):

- `shared` ⇒ **`[window-pin] freeze OK (1cf7fb75)`**.
- `replay-repro` ⇒ **`REPRODUCIDO`** (`sha256 1E3ADAC2…929A37E7`, idéntico a `.136`…`.148` ⇒
  **`Δ decisión = 0` medido por el CI**, coherente con que esta entrega sólo añade documentación y un
  script de inspección).
- `python` (ruff/imports/mypy/pytest offline), `frontend` (typecheck/lint/test/build + `contract:check`),
  `lifecycle-pg`, `dr-verify`, `a7-gate`, `decision-spine` y las tres capas de `playwright`
  (`mock E2E`, `integrated axe`, `integrated AUTO S5`) ⇒ **`success`**.
- `main` (push, run `39231458362` `Python CI`, `39231458366` `Gitleaks`, `39231458412` `Optimize lab`)
  ⇒ **`success`**.

## 8. Siguiente (decisión, no implementación)

El propietario eligió **no** dejar la ventana sin horizonte: se abre la opción **A** de la auditoría
como [ADR-047](../../../adr/047-gate-direccional-por-simbolo.md) en estado **Proposed** y
**docs-only** — gate direccional **por símbolo**, con el agregado conservado como **declaración** de
riesgo, plan de **baseline de replay nuevo** (`1E3ADAC2…929A37E7` queda como segmento PRE) y política
de **re-emisión segmentada** de la evidencia `.136`…`.149`.

**Lo que este sello NO hace:** no toca código, ni umbrales, ni el gate. El motor sigue byte-idéntico
y la ventana sigue `NO_MEDIDO`; la implementación, si se acepta, será un sello propio con
**`Δ decisión ≠ 0`**.

## 9. Medida previa del POST (simulación, POST-TAG)

El instrumento de §3 se **extendió después del tag** (sólo añade una simulación; no escribe, no toca
el motor y no cambia el `sha256` del sello) para medir el **techo** de ADR-047: en la **misma**
pasada as-of, cuántos símbolos pasarían el gate **por sí mismos**.

```text
as-of hoy (eje global)     LONG permitida 0/61
as-of POST (por símbolo)   días con >=1 operable 61/61
                           días con 1 solo        0
                           días con TODOS         0
                           operables/día          min 10 · p25 16 · mediana 22 · p75 25 · máx 30
                           símbolos nunca operables 0
```

Comando:

```text
uv run --no-sync python \
  docs/engineering/evidence/v2.88.149/audit_regime_reachability.py --watch-from-estudio
```

**Límites:** es un **techo** (ser operable no es ser medido: falta señal, edge y ciclo) y hereda los
límites del instrumento (alineación por índice, watch ACTUAL, sesgo de supervivencia). Prueba que el
cuello es el **agregado**; **no** prueba P&L ni promociona evidencia.
