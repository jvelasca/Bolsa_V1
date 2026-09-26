# Arranque del agente siguiente — tras `v2.77-beta` (`AUTO-MATERIAL-5`: MARKET OPERABILITY)

> **AsOf:** 2026-09-26 · **Punto de partida:** `v2.77-beta` (`2.02.0-beta`) · **Base:** `v2.76-beta`
> **Estado:** el forward PAPER ya opera con **precio y régimen de MERCADO** (`v2.76`) y ahora su
> veredicto diario es un **journal de operabilidad** que reparte cada veto en su **CAUSA**. **SIN
> migración** (head `046_fill_reference_mid`). **Freeze y reparto intactos** (`auto18-v1` /
> `auto15-v1`).

## Dónde estás

El instrumento de medición ya **no** es un bloqueante de código. Lo que falta sigue siendo
**calendario**:

- **El cubo sale del reloj real**: `sim_fill_finance_context.created_at = datetime.now(UTC)`. Un
  replay rápido daría **1 cubo**; la diversidad exige **≥4 días reales**.
- **La causa del no-operar ya se lee**: el forward smoke real declara `regime=40` + `top_n=24` con
  `0 fills`, el eje en `BEAR_TREND` y **4/8** símbolos que por sí solos admitirían LONG. Esto es
  **medición**, no conclusión: el gobernador conservador **puede** ser la causa estructural, y el
  journal está para probarlo o refutarlo **día a día**.
- **CAPABLE ≠ ACTIVE**: el par A/B tiene la arquitectura lista (`pairCapable=true`) pero solo opera
  una versión (`pairActive=false`) mientras no promuevas una **ACTIVE** con `EdgeReport`.

## Tu primera tarea: operar la ventana (no programar)

1. **Barras reales frescas**: `SyncInstrumentDailyBars` / `auto_sync_worker`. Sin barras no hay ATR
   ni régimen (el motor veta por `atr_source` / `regime_invalid` y el material no nace).
2. **Preflight antes de comprometer días** (read-only, no escribe nada):
   `v2_76_forward_market_material.py --preflight-only --watch-size 20`. `exit 2` = el eje veta las
   entradas LONG **hoy**; el resumen dice **por símbolo** quién está en `trend_down`. Si el eje veta,
   deja el runner corriendo igual (el régimen cambia con el mercado) **o** reduce `--watch-size`
   (menos símbolos ⇒ agregado menos restrictivo: es parámetro operativo, no política).
3. **Forward diario** con `--out forward-YYYYMMDD.json` hasta **≥32 ciclos medibles/versión** y **≥4
   cubos** compartidos. Deja `XTB_BRIDGE_URL` vivo para capturar `market_live`; si cae, `market_close`
   es el respaldo declarado (más plano ⇒ menos cierres).
4. **Captura diaria** (una línea):
   `uv run --no-sync python apps/api-python/scripts/v2_77_market_operability.py --forward
   'operability_runs/forward-*.json' --render`.
5. **Gate** a `--level evidence` con cada avance (no debe bajar umbrales).
6. **Prerrequisito de `pairActive`**: promueve una estrategia **ACTIVE** + `EdgeReport` por el flujo
   de ciclo de vida existente. Sin ella, `pairCapable=true` / `pairActive=false` y `P3-2` no tiene
   par.
7. Solo con **≥4 cubos compartidos** y **≥2 episodios**: `auto_evidence_run.py` (AUTO-22) y
   `auto_evidence_validate.py` (AUTO-23) → cierre de `P3-2`/`P3-3`.

**Regla dura:** no se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida;
no se fija `AUTO_ENGINE_SIM_V2_REGIME` (garantiza **1 solo** episodio). Si el material sigue
degenerado, el veredicto correcto es `INCONCLUSIVE` / `NO MEDIDO`.

## Cómo leer el journal (sin sesgo)

- `state=vetoed` con `regime=N` ⇒ el **hecho de mercado** (long-only veta en tendencia bajista).
- `state=vetoed` con `governor=N` ⇒ el **PERMISO** del gobernador (AUTO no puede abrir), distinto del
  mercado.
- `state=vetoed` con `top_n=N` ⇒ tope de **EVALUACIÓN** (la candidata ni se evaluó), no un veto de
  mercado.
- `state=no_signal` ⇒ el motor no llegó a considerar candidata (ni propuestas ni vetos).
- `symbolsOperable = k/n` alto con `Long=NO` ⇒ tensión del **agregado conservador** (varios símbolos
  operables, el eje los veta todos). Es el dato que decide si conviene reducir el watch.

## Después

La **auditoría externa de `v2.77-beta`** es la siguiente parada; el pack está en el
[audit-pack](./audit-pack-v2-77-auto-material-5-market-operability-2026-09-26.md). Lo que esta fase
acredita es el **instrumento medido** (clasificación por familia, `no_signal` fail-closed, CAPABLE ≠
ACTIVE, mutaciones mordiendo), **no** un cierre estadístico: no hubo ventana.

## Ficheros de la fase

[Plan](./plan-v2-77-auto-material-5-market-operability-2026-09-26.md) ·
[Audit-pack](./audit-pack-v2-77-auto-material-5-market-operability-2026-09-26.md) ·
[Auditor](./arranque-auditor-v2-77-auto-material-5-market-operability-2026-09-26.md) ·
[Relevo](./traspaso-relevo-post-v2-77-auto-material-5-2026-09-26.md) ·
[Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
Evidencia: `evidencia-operabilidad-v2.77-2026-09-26.txt` ·
`evidencia-matriz-mutaciones-v2.77-210-2026-09-26.txt`
