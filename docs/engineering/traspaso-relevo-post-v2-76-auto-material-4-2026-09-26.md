# Traspaso / relevo — tras `v2.76-beta` (`AUTO-MATERIAL-4`: MARKET MATERIAL)

> **AsOf:** 2026-09-26 · **Etiqueta:** `v2.76-beta` · **Versión:** `2.01.0-beta` · **Base:** `v2.75-beta`
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Freeze intacto** · **Reparto
> congelado** (`auto18-v1` / `auto15-v1`) · **`ALLOCATION = none`**.

## Qué quedó hecho

1. **Precio de MERCADO por el único seam** (`price_script`): `MarketPriceSnapshot` (nuevo) sirve la
   cotización viva XTB y **solo** rellena los símbolos ausentes con el cierre durable; un valor
   `None`/`NaN`/`inf`/`<= 0` **no es un precio** (fail-closed) y un símbolo fuera del watch **no**
   entra en el cache. **`auto_simulation_worker.py` no se toca.**
2. **Par real de versiones sobre UNA cuenta** (`auto_forward_deciders.py`, nuevo): `split_watch`
   reparte el universo de forma determinista/disjunta/exhaustiva; la **versión A** estampa
   `auto-2.0:<vA>` y re-entra con el símbolo plano (fail-closed si la lectura de posición falla); la
   **versión B** es la estrategia **ACTIVE** promovida (`active-strategy:<vB>`), enrutadas por símbolo.
3. **Runner forward + preflight** (`v2_76_forward_market_material.py`, nuevo): worker con
   `price_script=snapshot` y **reloj real**, `snapshot.refresh()` **entre** ticks (fuera del worker
   congelado), **sin** fijar `AUTO_ENGINE_SIM_V2_REGIME` (el régimen lo aportan las barras), gate leído
   con la MISMA pieza que el gate y `--preflight-only` **read-only** para saber si el universo puede
   operar antes de comprometer días.
4. **Puros registrados en CI** (`quality`): `test_market_price_snapshot.py` (**14**) y
   `test_auto_forward_deciders.py` (**11**) — **25** tests, entran **explícitos** (ese directorio no
   tiene pase de directorio en ese job).
5. **Matriz de mutaciones 200 → 205** con `M201`–`M205` (respaldo que no sobrescribe; precio no
   utilizable que no se sirve; A que no apila; enrutado que no se rompe; reparto sin solape).
   **205/205**, restauración **byte a byte**, árbol **intacto**.
6. **Evidencia cruda** en 4 `.txt` (matriz, CI offline, forward smoke, régimen de mercado) y
   **bump** `2.00.0-beta` → **`2.01.0-beta`**; tag **`v2.76-beta`**.

## Hallazgo central (declarado y medido)

1. **El agregado de régimen es el veredicto MÁS CONSERVADOR presente.** Con watch amplio, **un solo**
   `trend_down` deja el eje en `BEAR_TREND` y el motor (long-only) veta por `regime_invalid` **todas**
   las entradas del tick. Medido el 2026-09-26 con el catálogo real: 12 símbolos →
   `{range: 5, trend_down: 6, trend_up: 1}` ⇒ `BEAR_TREND` ⇒ 0 entradas.
2. **El respaldo de precio funciona con el bridge caído**: `XTB_BRIDGE_URL=http://localhost:3002`
   **no** escuchaba y 8/8 símbolos se sirvieron por `market_close` (respaldo declarado, sin fallo
   silencioso).
3. **La diversidad de cubos exige tiempo real** y **no** se puede comprimir: el cubo sale de
   `sim_fill_finance_context.created_at = datetime.now(UTC)`.

## Lo que NO quedó hecho (y por qué)

- **La ventana de acumulación (≥4 días de calendario)**: **NO ejecutada**. Es operación de **tiempo
  real** y esta fase se cerró el mismo día (`2026-09-26`, sábado, mercado cerrado). Un replay rápido
  daría **1 cubo** y no cerraría nada (es el hallazgo de `v2.75`).
- **`P3-2` / `P3-3`**: **ABIERTAS**, por el mismo motivo. El instrumento está **listo**: ya no falta
  código, falta **tiempo de mercado**.
- **`AUTO-22` / `AUTO-23` sobre material de mercado**: **no corridos** (no hay bundle que producir: el
  material forward de esta fase son 8 ticks en mercado cerrado, 0 fills — un bundle sobre vacío no
  acreditaría nada y no se fabrica para «tener uno»).
- **El fallo local de la sonda PG de `AUTO-23`**: **pre-existente** y **ajeno** al diff (medido también
  en `HEAD` prístino con `git stash`: `assert 17 == 26`); en CI ese test **se salta** porque el job
  `quality` no tiene Postgres. Se declara para que nadie lo confunda con una regresión de esta fase.

## Lo que hereda el siguiente

**El bloqueante ya no es de CÓDIGO ni de CANTIDAD ni de FUENTE DE PRECIO: es de CALENDARIO.** El
siguiente paso es **operar**, no programar:

```bash
# 0) Barras reales frescas (ATR y régimen reales):
#    SyncInstrumentDailyBars / auto_sync_worker
# 1) ¿Puede operar el universo HOY? (read-only, no escribe nada; exit 2 = vetado)
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --preflight-only --watch-size 20
# 2) Forward con reloj real (el bridge XTB es opcional: sin él, respaldo por cierre diario):
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --watch-size 20 --interval-seconds 60 --json --out evidencia-forward.json
# 3) Gate con cada avance (NO debe bajar umbrales):
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py \
    --account-id <u> --strategy-version <vA> --strategy-version <vB> --level evidence
# 4) Con >=4 cubos compartidos y >=2 episodios:
#    auto_evidence_run.py      --account-id <u> --strategy-version <vA> --strategy-version <vB> \
#                              --bucket day --folds 3                      # AUTO-22
#    auto_evidence_validate.py --account-id <u> --strategy-version <vA> --strategy-version <vB> \
#                              --sizes 16,32,64,128 --buckets day,week,month # AUTO-23
```

Notas de operación:

- El runner imprime `marketRegime` en **cada** corrida (y el preflight lo detalla por símbolo): si el
  eje es `BEAR_TREND`/`UNKNOWN`, **no habrá entradas** ese día aunque se deje corriendo. **No** se
  fuerza `AUTO_ENGINE_SIM_V2_REGIME` (forzarlo garantiza **1 solo** episodio: es el hallazgo de
  `v2.75`).
- Un watch **más pequeño** hace el agregado conservador **menos** restrictivo (menos símbolos que
  puedan estar en `trend_down`); es un parámetro operativo (`--watch-size`), no una política.
- **Prerrequisito** `<vB>`: sin estrategia **ACTIVE** promovida + `EdgeReport`, la versión B no opera y
  `pairAvailable` sale `false` (declarado, no disfrazado).

## Reglas duras que siguen vigentes

- **No** se rellena el histórico legacy (sin backfill de `cycle_id`); el productor solo **acuna**.
- **No** se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
- **No** se infiere `cycle_id` ni `reserved_risk`; **no** se convierte N fills en N operaciones.
- **No** se sobrescribe una corrida o validación (`evidence_runs/`, `evidence_validations/`).
- **Forward, no replay:** no se inyecta ni se backdatea `created_at`.
- **No** se toca el freeze. **Sin migración.** `ALLOCATION = none`.

## Ficheros de la fase

- [Plan](./plan-v2-76-auto-material-4-market-material-2026-09-26.md) ·
  [Audit-pack](./audit-pack-v2-76-auto-material-4-market-material-2026-09-26.md) ·
  [Auditor](./arranque-auditor-v2-76-auto-material-4-market-material-2026-09-26.md) ·
  [Agente](./arranque-agente-v2-76-auto-material-4-market-material-2026-09-26.md)
- Evidencia: `evidencia-matriz-mutaciones-v2.76-205-2026-09-26.txt` ·
  `evidencia-ci-offline-quality-v2.76-2026-09-26.txt` (sin PG) ·
  `evidencia-ci-offline-quality-local-con-pg-v2.76-2026-09-26.txt` (con PG: 1 fallo pre-existente) ·
  `evidencia-forward-smoke-v2.76-2026-09-26.txt` · `evidencia-regimen-mercado-v2.76-2026-09-26.txt`
- Contexto previo: [relevo v2.75](./traspaso-relevo-post-v2-75-auto-material-3-2026-09-26.md) ·
  [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
