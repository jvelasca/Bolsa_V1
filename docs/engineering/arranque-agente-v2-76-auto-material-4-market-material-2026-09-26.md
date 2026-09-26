# Arranque del agente siguiente — tras `v2.76-beta` (`AUTO-MATERIAL-4`: MARKET MATERIAL)

> **AsOf:** 2026-09-26 · **Punto de partida:** `v2.76-beta` (`2.01.0-beta`) · **Base:** `v2.75-beta`
> **Estado:** el forward PAPER ya corre con **precio de MERCADO** (cotización viva + cierre durable) y
> **régimen real** (sin override), con **dos versiones** sobre la misma cuenta. **SIN migración**
> (head `046_fill_reference_mid`). **Freeze y reparto intactos** (`auto18-v1` / `auto15-v1`).

## Dónde estás

La fuente del material ya **no** es un bloqueante de código. Lo que falta es **calendario**:

- **El cubo sale del reloj real**: `sim_fill_finance_context.created_at = datetime.now(UTC)`. Un
  replay rápido daría **1 cubo** (es el hallazgo de `v2.75`); la diversidad exige **≥4 días reales**.
- **El régimen ya no se fuerza**: `AUTO_ENGINE_SIM_V2_REGIME` **no** se fija, así que los episodios
  salen de `DiscoveryRegimeSource` (barras reales).
- **Hallazgo nuevo y central:** el agregado de régimen es el veredicto **más conservador** presente
  (`high_vol` > `trend_down` > `range` > `trend_up` > `low_vol`). Con watch amplio, **un solo**
  `trend_down` deja el eje en `BEAR_TREND` y el motor (long-only) veta por `regime_invalid` **todas**
  las entradas del tick. Medido el 2026-09-26: 12 símbolos → `{range: 5, trend_down: 6, trend_up: 1}`
  ⇒ `BEAR_TREND` ⇒ 0 entradas ⇒ 0 fills. **No es un defecto**: es el instrumento congelado.

## Tu primera tarea: operar la ventana (no programar)

1. **Barras reales frescas**: `SyncInstrumentDailyBars` / `auto_sync_worker`. Sin barras no hay ATR ni
   régimen (el motor veta por `atr_source` / `regime_invalid` y el material no nace).
2. **Preflight antes de comprometer días** (read-only, no escribe nada):
   `v2_76_forward_market_material.py --preflight-only --watch-size 20`. `exit 2` = el eje veta las
   entradas LONG **hoy**; el resumen dice **por símbolo** quién está en `trend_down`. Si el eje veta,
   deja el runner corriendo igual (el régimen cambia con el mercado) **o** reduce `--watch-size` (menos
   símbolos ⇒ agregado menos restrictivo: es parámetro operativo, no política).
3. **Forward diario** con `--interval-seconds` razonable hasta **≥32 ciclos medibles/versión** y **≥4
   cubos** compartidos; el bridge XTB es **opcional** (sin él, respaldo por cierre diario: menos
   movimiento intradía ⇒ menos cierres).
4. **Gate** a `--level evidence` con cada avance (no debe bajar umbrales) y, con material diverso,
   **`AUTO-22`** → **`AUTO-23`**; entonces cerrar `P3-2` (correlación con `≥4` cubos) y `P3-3`
   (`P(R>0)` vs N con **`Effective-N > 1`**).

**Regla dura:** no se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida; no
se fija `AUTO_ENGINE_SIM_V2_REGIME` (garantiza **1 solo** episodio). Si el material sigue degenerado, el
veredicto correcto es `INCONCLUSIVE` / `NO MEDIDO`.

## Prerrequisito que puede faltar

La **versión B** es la estrategia **ACTIVE** promovida (`active-strategy:<vB>`). Sin una ACTIVE con su
`EdgeReport`, B queda fail-closed a `HOLD` y el runner lo declara (`pairAvailable: false`): `P3-2` no
tendría par. Comprueba el `pairAvailable` del payload antes de esperar correlación.

## Después

La **auditoría externa de `v2.76-beta`** es la siguiente parada; el pack está en el
[audit-pack](./audit-pack-v2-76-auto-material-4-market-material-2026-09-26.md). Lo que esta fase
acredita es el **mecanismo medido** (precio de mercado servido, régimen real, veto honesto declarado),
**no** un cierre estadístico: no hubo ventana.

## Ficheros de la fase

[Plan](./plan-v2-76-auto-material-4-market-material-2026-09-26.md) ·
[Audit-pack](./audit-pack-v2-76-auto-material-4-market-material-2026-09-26.md) ·
[Auditor](./arranque-auditor-v2-76-auto-material-4-market-material-2026-09-26.md) ·
[Relevo](./traspaso-relevo-post-v2-76-auto-material-4-2026-09-26.md) ·
[Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
Evidencia: `evidencia-matriz-mutaciones-v2.76-205-2026-09-26.txt` ·
`evidencia-forward-smoke-v2.76-2026-09-26.txt` ·
`evidencia-regimen-mercado-v2.76-2026-09-26.txt` ·
`evidencia-ci-offline-quality-v2.76-2026-09-26.txt`
