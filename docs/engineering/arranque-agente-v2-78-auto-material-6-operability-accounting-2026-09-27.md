# Arranque del agente siguiente — tras `v2.78-beta` (`AUTO-MATERIAL-6`: OPERABILITY ACCOUNTING)

> **AsOf:** 2026-09-27 · **Punto de partida:** `v2.78-beta` (`2.03.0-beta`) · **Base:** `v2.77-beta`
> **Estado:** el **instrumento** de medición ya cuenta **vetos puros** (`approved`/`risk_exit` no
> inflan `vetoCounted`) y la **ausencia** de medición se declara `unknown` (nunca `no_signal`).
> **SIN migración** (head `046_fill_reference_mid`). **Freeze y reparto intactos** (`auto18-v1` /
> `auto15-v1`).

## Dónde estás

El bloqueante **sigue siendo de CALENDARIO**, no de código. `v2.78` cierra el defecto semántico del
instrumento (`P3-6`), de modo que un día que **sí opere** se puede leer como **censo** de vetos y no
como **cota superior**; y `P3-7` hace que un payload vacío/malformado se lea **no medido** en vez de
«sin señal». Lo que falta es **tiempo de mercado**:

- **El cubo sale del reloj real**: `sim_fill_finance_context.created_at = datetime.now(UTC)`. Un
  replay rápido daría **1 cubo**; la diversidad exige **≥4 días reales**.
- **La causa del no-operar ya se lee**: el forward smoke real declara `regime=40` + `top_n=24` con
  `0 fills`, el eje en `BEAR_TREND` y **4/8** símbolos que por sí solos admitirían LONG. Es
  **medición**, no conclusión.
- **CAPABLE ≠ ACTIVE**: `pairCapable=true` / `pairActive=false` mientras no se promueva una
  **ACTIVE** con `EdgeReport`.

## Tu primera tarea: operar la ventana (no programar)

1. **Barras reales frescas**: `SyncInstrumentDailyBars` / `auto_sync_worker`. Sin barras no hay ATR
   ni régimen.
2. **Preflight antes de comprometer días** (read-only):
   `v2_76_forward_market_material.py --preflight-only --watch-size 20`. `exit 2` = el eje veta las
   entradas LONG **hoy**; el resumen dice **por símbolo** quién está en `trend_down`.
3. **Forward diario** con `--out forward-YYYYMMDD.json` hasta **≥32 ciclos medibles/versión** y **≥4
   cubos** compartidos. Deja `XTB_BRIDGE_URL` vivo para capturar `market_live`; si cae, `market_close`
   es el respaldo declarado.
4. **Captura diaria** (una línea):
   `uv run --no-sync python apps/api-python/scripts/v2_77_market_operability.py --forward
   'operability_runs/forward-*.json' --render`.
5. **Gate** a `--level evidence` con cada avance (no debe bajar umbrales).
6. **Prerrequisito de `pairActive`**: promueve una estrategia **ACTIVE** + `EdgeReport`.
7. Solo con **≥4 cubos compartidos** y **≥2 episodios**: `auto_evidence_run.py` (AUTO-22) y
   `auto_evidence_validate.py` (AUTO-23) → cierre de `P3-2`/`P3-3`.

**Regla dura:** no se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida;
no se fija `AUTO_ENGINE_SIM_V2_REGIME` (garantiza **1 solo** episodio). Si el material sigue
degenerado, el veredicto correcto es `INCONCLUSIVE` / `NO MEDIDO`.

## Cómo leer el journal (sin sesgo, ya con `v2.78`)

- `state=vetoed` con `regime=N` ⇒ el **hecho de mercado** (long-only veta en tendencia bajista).
- `state=vetoed` con `governor=N` ⇒ el **PERMISO** del gobernador (AUTO no puede abrir).
- `state=vetoed` con `top_n=N` ⇒ tope de **EVALUACIÓN**, no un veto de mercado.
- `state=no_signal` ⇒ el motor no llegó a considerar candidata (ni propuestas ni vetos).
- `state=unknown` ⇒ **no medido** (payload vacío/truncado): no se puede leer como un hecho del mercado.
- `vetoCounted` = **vetos puros**; `nonVetoCounted` (línea `aprobaciones/salidas`) son **atribuciones**
  que **no** son vetos. En un día operado, `vetoCounted == vetoes` y `other` debe estar **vacía**.
- `symbolsOperable = k/n` alto con `Long=NO` ⇒ tensión del **agregado conservador**.

## Después

La **auditoría externa de `v2.78-beta`** es la siguiente parada; el pack está en el
[audit-pack](./audit-pack-v2-78-auto-material-6-operability-accounting-2026-09-27.md). Lo que esta
fase acredita es la **contabilidad del instrumento**, **no** un cierre estadístico: no hubo ventana.

## Ficheros de la fase

[Plan](./plan-v2-78-auto-material-6-operability-accounting-2026-09-27.md) ·
[Audit-pack](./audit-pack-v2-78-auto-material-6-operability-accounting-2026-09-27.md) ·
[Auditor](./arranque-auditor-v2-78-auto-material-6-operability-accounting-2026-09-27.md) ·
[Relevo](./traspaso-relevo-post-v2-78-auto-material-6-operability-accounting-2026-09-27.md) ·
[Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
Evidencia: `evidencia-operabilidad-v2.78-2026-09-27.txt` ·
`evidencia-matriz-mutaciones-v2.78-213-2026-09-27.txt`
