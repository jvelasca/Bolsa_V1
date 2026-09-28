# Fase B (operación) — preflight + sonda corta: el bloqueante **NO** era el dato (2026-09-28)

> **AsOf:** 2026-09-28 · **Objeto vivo:** tag **`v2.85.2-beta`** (`2.10.2-beta`, docs-only) ·
> **Cuenta PAPER:** `1484e253d2d54645945a6b1d7` · **Versión A:** `v283-window-a` ·
> **Freeze:** `apps` `ddcf636f39054e29cf9013e0273da2b773c1fd76` / `packages`
> `ba90ccf233bce9bada4e41cf81eb0b69312fd0d1` (**intacto**: esta entrega es **docs-only**, no toca
> `apps/` ni `packages/`).
> **Naturaleza:** **OPERACIÓN**, no fase de código. No se toca motor, gobernador, `TOP_N`, umbrales,
> allocation, pesos A/B ni migraciones. No se bajan `min cycles`/`min R`/`folds`/`min_episodes`.
> **Veredicto:** la ventana sigue **`NO MEDIDO`**, **pero el bloqueante declarado en `v2.85.2` §2 queda
> REFUTADO por medición**: el material está **fresco** y el eje **sigue en `BEAR_TREND`**.

## 1. Qué se ha hecho (operación read-only)

| Paso | Herramienta | Resultado |
|---|---|---|
| 0 · Verificar el material | `GetInstrumentDataStatus` + `ohlcv_bars`/`data_sync_log` (read-only) | **20/20 `current`**, barra `2026-09-28`, último sync `15:48–16:04Z` |
| 1 · Preflight (**puerta de corte**) | `v2_76 --preflight-only --watch-size 20` | **exit 2** · `BEAR_TREND` · `entriesAllowedLong=false` |
| 2 · Sonda corta (evidencia parcial) | `v2_76 --max-ticks 20` → `probe-market-20260928.json` | `decided=400` · `proposals/orders/fills=0` · `vetoes=400` |
| 3 · Serie diaria | `v2_77_market_operability.py --forward …` | fila `2026-09-28 · BEAR_TREND · Long=NO · 11/20 · Veto=8000` |
| 4 · Ventana / gate | `v2_80 --days 4` · `paper_material_readiness --level evidence` | **exit 2** los dos (sin material durable) |
| 5 · `OBS-13` | `logs/dev/fase-b-obs13-repro.py` sobre 2 evidencias | **CONFIRMADA** (dos muestras independientes) |

**No se lanzó el forward de 400 ticks**: la puerta del preflight (`exit 2`) lo declara `NO MEDIDO`
antes de gastar ~7 h. Es exactamente el corte temprano que el cierre de `v2.85.2` midió como causa del
sobrecoste (la corrida de D1 pagó 400 ticks por un resultado legible desde el tick 10).

## 2. Paso 0 — el material está **FRESCO** (corrige el bloqueante declarado)

El [relevo de `v2.85.2`](./traspaso-relevo-post-v2-85-2-auto-material-13-no-medido-2026-09-28.md) §2 declara
como «bloqueante real medido» que las barras de `ohlcv_bars` estaban **estancadas en `2026-09-26`**.
Medido hoy (read-only):

| Hecho | Valor |
|---|---|
| Instrumentos del watch con barra D1 | **20/20** (1 284 barras cada uno) |
| Última barra | **`2026-09-28`** en los 20 |
| Frescura (`GetInstrumentDataStatus`) | **`{'current': 20}`** · 0 sin barra del día esperado |
| Último `data_sync_log` (tabla **singular**) | **`success`**, `2026-09-28T15:48–16:04Z` |
| `sync_settings` | `auto_sync_enabled=True` · `post_market_only=False` · `scope=lists` · `30 min` |

⇒ **la afirmación «barras estancadas en `2026-09-26`» queda refutada**: el `2026-09-26` es **sábado** y
aparece con **1 sola barra** (un instrumento), igual que `2026-09-20` (domingo) y `2026-09-19` (sábado).
Es un **artefacto recurrente de fin de semana** en `ohlcv_bars`, no un estancamiento del sincronizador.
**Se declara, no se borra** (regla dura: el capturador es read-only).

## 3. Paso 1 — preflight: la puerta está CERRADA (y es legítimo)

```
watch                          20 símbolos
barras servidas por el loader  20
régimen por símbolo            {'range': 6, 'trend_down': 9, 'trend_up': 5}
agregado (más conservador)     trend_down
eje operativo                  BEAR_TREND
entradas LONG                  VETADAS (regime_invalid)
```

Con el material **fresco**, el eje **sigue** en `BEAR_TREND`. Comparado con D1 (`{range: 8,
trend_down: 9, trend_up: 3}`) el reparto por símbolo **cambia** (6/9/5 vs 8/9/3) pero el **agregado no**:
`trend_down` domina las dos veces. La conclusión del auditor externo («AUTO no entró por
`BEAR_TREND`, no por estar roto») **se mantiene y ahora no depende de barras viejas**.

## 4. Paso 2 — sonda corta: evidencia parcial **operativa** sin tocar código

El `--out` del forward solo se escribe al terminar, así que la evidencia parcial se consigue con una
corrida **completa pero corta** (no requiere cambiar `v2_76`):

```powershell
uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py `
  --account-id "1484e253d2d54645945a6b1d7" --version-a "v283-window-a" `
  --interval-seconds 60 --max-ticks 20 --level evidence --json `
  --out "operability_runs/probe-market-20260928.json"
```

| Métrica | Valor |
|---|---|
| `ticks` / `stopReason` | **20** / `completed` |
| `decided` / `proposals` / `orders` / `fills` / `cycles` | **400** / **0** / **0** / **0** / **0** |
| `vetoes` | **400** |
| `journalReasons` | `{regime_invalid: 100, top_n_excluded: 100}` ⇒ `vetoCounted=200` |
| Régimen | `BEAR_TREND` · `entriesAllowedLong=false` |
| SHA-256 del JSON | `2ADD6BB3FD7E07853A49A2535976EA58D5868EDB082AA419FB9BB013815E7046` |

**Declaración de no contaminación:** el nombre `probe-market-*.json` es **deliberado** — **no** entra en
el glob `operability_runs/forward-market-*.json` que consumen `v2_80`/`v2_83` (el dedupe de
`_load_evidence` es por **día** y cogería la primera coincidencia ordenada). El `v2_77` confirma el
dedupe: `0 fila(s) nueva(s), 1 ya presente(s)` — la sonda **no** añade un día a la ventana.

## 5. `OBS-13` — **CONFIRMADA** (dos muestras independientes)

Reproducida con `logs/dev/fase-b-obs13-repro.py` (read-only, gitignored) sobre **dos** evidencias:

| Evidencia | ticks | `vetoes` | `vetoCounted` | censo/tick | `|watchA|` | `vetoes×|watchA|/|watch|` |
|---|---|---|---|---|---|---|
| D1 del tag (`v2.85.2`) | 400 | 8 000 | 4 000 | **10.00** | 10 | 4 000 |
| sonda de hoy | 20 | 400 | 200 | **10.00** | 10 | 200 |

⇒ el censo del journal cubre **exactamente** la versión A (`|watchA|` símbolos por tick); la versión B
(`secondary`) **no** aporta. `vetoCounted == vetoes × |watchA| / |watch|` se cumple en las dos.
La hipótesis de `OBS-13` queda **confirmada**; el arreglo (censo explícito `A` / `B` / `A+B`) es
**fase de código** y **no** entra aquí.

## 6. Hallazgo estructural (por qué PAPER no genera material) — medido en código

1. `aggregate_trial_regime` = **el veredicto más conservador presente**
   (`packages/py/application/src/bolsa_application/auto_v2_entry.py:2330-2354`): **un solo `trend_down`
   de 20** deja el eje en `BEAR_TREND`. Un día operable exige que **ninguno** de los 20 sea `trend_down`
   ni `high_vol`.
2. El régimen se pasa al motor como **un único valor por tick**
   (`apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:2944` → `plan_v2_tick(regime=…)`),
   y `decide_portfolio` lo aplica como veto **fail-closed** para longs
   (`packages/py/application/src/bolsa_application/portfolio_decision_engine.py:507-509`).
3. **`TOP_N` es un tope de EVALUACIÓN y corre ANTES del gate de régimen**
   (`auto_v2_entry.py:1168-1207`: `select_top_opportunities(top_n=cfg.top_n)` journaliza
   `top_n_excluded` **sin evaluar**, y solo el TOP pasa al bucle de decisión). Con `TOP_N=5` y
   `|watchA|=10`, cada tick deja **5 `top_n_excluded` + 5 `regime_invalid`** — que es exactamente el 5/5
   observado. **Matiz honesto:** el 5/5 del censo **no** prueba que los símbolos `range` pasaran el
   régimen; el reparto por símbolo (`5 trend_down / 5 range`) es una **coincidencia de conteo**, no una
   clasificación del journal.

## 7. Estado de la ventana y de la deuda

- **Ventana D1..D4: `NO MEDIDO`** (sin cambio). `v2_80 --days 4` → **exit 2** («no hay ningún día de
  operabilidad que leer en la ventana»): la ventana se construye **solo** del material durable
  (`fills ∪ cycles ∪ journal`), que sigue **vacío** para esta cuenta.
- **`paper_material_readiness --level evidence` → exit 2**: `0` fills · `0` ciclos cerrados · `0`
  reservas · `BLOCKED`.
- **`OBS-13`: CONFIRMADA** (no cerrada: exige el arreglo del censo). `OBS-11`, `H-4`, `OBS-9`, `P3-5`,
  `OBS-5` siguen **ABIERTAS**. `P3-2`/`P3-3` siguen **ABIERTAS**.
- **Nada se cierra por documentación.**

## 8. Robustez registrada (NO implementada) — deuda `P3-2`

El auditor tiene razón en que una ventana de ≥4 días es **frágil** con el diseño actual:

| Debilidad medida | Evidencia |
|---|---|
| Suspensión del equipo | D1 perdió **~58 min** (salto `12:28:06Z → 13:35:25Z`, tick 230→240) |
| Sin `watchdog`/`heartbeat`/`resume`/`checkpoint` | La sesión continúa, pero no hay continuidad garantizada |
| `--out` solo al final | No hay evidencia parcial nativa: se pagó ~7 h por un resultado legible en el tick 10 |

Registrado como recomendación en `P3-2` (ver la
[deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)): `tick N → checkpoint → tick N+1` y
`restart → recover → continue` **sin duplicar ciclos**, más evidencia incremental del `--out`.
**No se implementa ahora** (una ventana viva y un freeze intacto lo prohíben).

## 9. Qué falta (el experimento crítico sigue pendiente)

1. **Un día PAPER con régimen operable** (`entriesAllowedLong=true`: ningún símbolo `trend_down`/
   `high_vol` en el watch). Solo entonces se observa `SIGNALS → TOP_N → RISK → RESERVATION → ORDER →
   FILL → CYCLE`.
2. **El objetivo real es un FILL, no un día «operable»**: `v2_80` construye la ventana del material
   **durable**; un día operable sin fill **no crea día**.
3. Repetir el ciclo hasta **≥4 días de calendario** con ≥2 episodios y ≥32 ciclos medibles, con cuenta
   y versión **fijas** y el **equipo sin suspensión** (declarando cada salto).
4. Guardar la evidencia cruda con SHA-256 en `docs/engineering/evidence/<tag>/` al primer día con
   material (patrón de `v2.85.2`).

**Lo que NO se hace** (reacción prematura): no se toca `TOP_N`, régimen, umbrales, riesgo, allocation,
A/B ni filtros de entrada para «producir» operaciones. La ausencia de ciclos **no** demuestra que A/B
esté mal: `A/B = NO MEDIDO`.

## 10. Cadena de reproducción

```powershell
# Paso 0 — material (read-only)
uv run --no-sync python logs/dev/fase-b-verify-material.py

# Paso 1 — puerta de corte
uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py --preflight-only --watch-size 20

# Paso 5 — OBS-13 (dos evidencias)
uv run --no-sync python logs/dev/fase-b-obs13-repro.py `
    docs/engineering/evidence/v2.85.2/forward-market-20260928.json `
    operability_runs/probe-market-20260928.json
```

Los tres helpers de operación viven en `logs/dev/` (**gitignored**, mismo patrón que el autopiloto de
D1): `fase-b-verify-material.py`, `fase-b-obs13-repro.py` y los logs `preflight-*`, `probe-*`,
`verify-material-*`. **No** son artefactos del repo ni mueven el freeze.

### Bucle diario en un solo comando

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File logs\dev\fase-b-puerta-diaria.ps1
```

Encadena **paso 0 → paso 1 (puerta) → paso 2 → paso 3** y deja el log en
`logs/dev/puerta-diaria-<dia>.log`. Con la puerta **cerrada** (`exit 2`) declara `NO MEDIDO` y
**termina sin lanzar el forward de 400 ticks** (validado hoy: `paso 0 exit 0` → `preflight exit 2` →
`NO MEDIDO`, salida `0`). Con la puerta **abierta** (`exit 0`) sigue con la sonda, el forward completo y
la cadena `v2_77`/`v2_80`/`v2_83`/`readiness`. Cuenta y versión están **fijas** en el script
(`1484e253d2d54645945a6b1d7` / `v283-window-a`); el `freeze` se imprime en la cabecera del log en cada
corrida para declararlo (gitignored ⇒ **no** mueve el árbol de código). PC **sin suspensión** durante la
corrida completa.
