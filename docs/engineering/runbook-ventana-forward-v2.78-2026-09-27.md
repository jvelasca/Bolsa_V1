# Runbook — ventana forward `≥4 días` (operación del propietario)

> **AsOf:** 2026-09-27 · **Objeto:** obtener el primer dataset PAPER **forward** con **diversidad de
> mercado** (≥4 cubos de calendario compartidos y ≥2 episodios de régimen) para cerrar `P3-2`/`P3-3`.
> **Herramienta:** `v2_76_forward_market_material.py` (AUTO-MATERIAL-4) + journal de operabilidad
> `v2_77_market_operability.py` (AUTO-MATERIAL-5) + **capturador de la ventana**
> `v2_80_market_window.py` (AUTO-MATERIAL-8, read-only sobre el journal **durable**).
> **Regla dura:** esto es **operación**, no una fase de código. **No** se bajan umbrales, **no** se
> fuerza el régimen, **no** se backdatea nada.

## 1. Preflight real de hoy (2026-09-27) — hecho y declarado

```bash
uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py --preflight-only --watch-size 20
# exit 2  ·  {'range': 8, 'trend_down': 9, 'trend_up': 3}  ⇒  agregado trend_down  ⇒  BEAR_TREND
#           ⇒  entriesAllowedLong=False  ⇒  todas las entradas LONG vetadas por regime_invalid
```

**Lectura honesta.** El mercado de **hoy** veta todo el universo LONG con el **agregado más
conservador** (un solo `trend_down` empuja el eje a `BEAR_TREND`). **No** se fuerza
`AUTO_ENGINE_SIM_V2_REGIME`: eso convertiría el material en guionizado y repetiría el defecto que
`v2.76` vino a cerrar. La ventana se corre **cuando el mercado lo permita**, y su veredicto correcto
mientras no lo permita es **`INCONCLUSIVE` / `NO MEDIDO`**.

## 2. Brechas de entorno a resolver ANTES del día 1

| # | Brecha | Por qué importa | Cómo se resuelve |
|---|---|---|---|
| 1 | **No hay estrategia ACTIVE** sobre la cuenta de la ventana (`versionB=""`, `pairActive=false`) | sin B, el par A/B no opera y el material no gana diversidad por estrategia | promover una estrategia **ACTIVE** + su `EdgeReport` sobre la cuenta; verificar `pairActive=true` |
| 2 | **`--account-id` no fijado** | sin fijarlo, **cada corrida siembra una cuenta nueva** y el journal no acumula (el dedupe del journal es por `(day, account)`) | fijar `--account-id <uuid>` **desde el día 2** (y reusar `--version-a` del día 1) |
| 3 | **Scheduler de barras** | el régimen y el ATR salen de `ohlcv_bars` **reales**; sin barras frescas el preflight cae en `UNKNOWN` | mantener vivo `SyncInstrumentDailyBars` / `auto_sync_worker` (corren dentro del proceso API) |
| 4 | **Glob de corridas reales distinguible** | en `operability_runs/` ya hay **fixtures**; no hay que borrarlos ni mezclarlos | usar el glob `operability_runs/forward-market-*.json` para las corridas **reales** |

## 3. Cadencia diaria (una vez por día de mercado)

```bash
# 0) Barras: deja que el scheduler del API corra (o sincroniza) — el régimen sale de barras reales.

# 1) Preflight (read-only, no escribe):
uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --preflight-only --watch-size 20
#    exit 0 ⇒ el universo admite LONG hoy; exit 2 ⇒ veta (BEAR_TREND/UNKNOWN). Si veta, DECLARA y no fuerces.

# 2) Forward del día (reloj REAL; los cubos salen de created_at = now):
uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --account-id "$ACCOUNT" --version-a "$VERSION_A" \
    --interval-seconds 60 --max-ticks 400 --stop-when-ready --level evidence \
    --json --out "operability_runs/forward-market-$(date +%Y%m%d).json"

# 3) Journal de operabilidad (publica la tabla diaria + el desglose por familia):
uv run --no-sync python apps/api-python/scripts/v2_77_market_operability.py \
    --forward "operability_runs/forward-market-$(date +%Y%m%d).json" --render

# 4) Serie diaria de la VENTANA desde el journal DURABLE (read-only, AUTO-MATERIAL-8).
#    Reutiliza el mismo censo (entrada vs posicion) y el mismo R que el informe; declara
#    los huecos (None/UNKNOWN) y el gate honesto (>=4 dias / >=2 episodios / >=32 ciclos):
$env:BROKER_VENUE="paper"
uv run --no-sync python apps/api-python/scripts/v2_80_market_window.py \
    --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --days 4 --render \
    --out "operability_runs/window-$(date +%Y%m%d).json"
```

Repite 1–4 **cada día de mercado**. El journal de la sonda del runner
(`operability_runs/journal.jsonl`) y el de la **ventana** (`operability_runs/window.jsonl`, ambos **no
versionados**) acumulan filas; el capturador **siempre** relee el journal **durable** (`--days`/`--since`,
sin `--forward`) y anexa a `window.jsonl` las filas nuevas por `día+cuenta+versiones` (sin duplicar), así
que `--render --days 4` re-imprime la serie completa de la ventana. La cabecera del
capturador declara `exit 0` con ≥1 día y `exit 2` sin material legible; avisa por `stderr`
(`# ALERTA CONTRATO …`) si algún día tiene `other>0`.

## 4. Cuándo se puede leer el material (gate de evidencia)

Solo cuando el forward haya producido:

- **≥4 cubos de calendario compartidos** (`sharedSingleCycleShare` < 1) **y** **≥2 episodios** de
  régimen (`min_episodes`), con `min_cycles ≥ 32` ciclos medibles.

```bash
uv run --no-sync python apps/api-python/scripts/auto_evidence_run.py            # genera la evidencia
uv run --no-sync python apps/api-python/scripts/auto_evidence_validate.py       # valida correlación por cubos y P(R>0) vs N
```

**No** se corren con material degenerado (un solo cubo o un solo episodio): darían `INCONCLUSIVE`
fabricado. Mientras no se cumpla el gate, el veredicto honesto es **`NO MEDIDO`**.

## 5. Reglas duras (no negociables)

- **No** bajar `min cycles` / `min R` / `folds` / `min_is` / `min_oos` / `min_episodes`.
- **No** forzar `AUTO_ENGINE_SIM_V2_REGIME`.
- **No** backdatear `created_at` (los cubos salen del instante **durable** del fill).
- **No** sobrescribir `evidence_runs/` ni `evidence_validations/`.
- **Forward, no replay.**
- **No** borrar los fixtures de `operability_runs/`.
- Veredicto honesto: `INCONCLUSIVE` / `NO MEDIDO` si el material sigue degenerado.

## 6. Qué mirar cada día en la tabla de operabilidad

| Columna / clave | Lectura |
|---|---|
| `Regimen` / `Long` | hecho de mercado: si `BEAR_TREND` y `Long=NO`, el bloqueo es de régimen |
| `SimbOper` (`k/N`) | cuántos símbolos admitirían LONG **por sí mismos** (la tensión del gobernador conservador) |
| `Veto` vs `vetoCounted` | deben **cuadrar**; `vetoCounted` suma familias (incl. `other`) |
| `Vetos por familia` | reparto `regime`/`governor`/`liquidity`/`risk`/`top_n`/`data`/`other` |
| `aprobaciones/salidas` | atribuciones **no** vetos (`approved`, `risk_exit`, …) |
| `eventos/posicion` | motivos de **gestión de posición** (`protect_requested`, `atr_geometry`, …): **no** son vetos |
| `otherCount` / `ALERTA CONTRATO` | `other>0` ⇒ **violación de contrato** (**AVISO**, no fallo): un motivo sin familia declarada; revisar alta de reason code |
| `Cobertura` (`declared/observed/unknown`) | prueba que `other==0` **no** es accidental; `unknown>0` nombra el hueco (hoy `H-4`: los `signal_*` pre-ranqueo) |
| `Par` (`CAPAZ`/`ACTIVO`) | `CAPAZ` sin `ACTIVO` ⇒ falta la estrategia B (brecha 1) |

## 7. Entregable

Cuando se cumpla el gate de §4, el material y su lectura son la entrada para cerrar `P3-2`/`P3-3`
(ver [`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)).
Si la ventana no se puede correr, se **declara** y las dos deudas siguen **abiertas**: no se cierran
con un material degenerado.
