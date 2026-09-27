# Arranque operativo de la ventana PAPER forward — semilla A/B y cuenta fija (2026-09-27)

> **AsOf:** 2026-09-27 · **Naturaleza:** **operación** (no es una fase de motor) ·
> **Objeto:** dejar listo el entorno para la ventana PAPER **≥4 días** de `AUTO-MATERIAL-12`
> que persigue cerrar `P3-2`/`P3-3`. **No** se toca motor, gobernador, `TOP_N`, umbrales,
> allocation, pesos A/B ni migraciones (head sigue `046_fill_reference_mid`).
> Ejecutado por el script [`ops_seed_window_pair.py`](../../apps/api-python/scripts/ops_seed_window_pair.py).

## 1. Qué se ha hecho (una sola vez, antes de D1)

| # | Acción | Resultado |
|---|---|---|
| 1 | Cuenta simulada **dedicada y fija** de la ventana | `1484e253d2d54645945a6b1d7` (`PAPER-VENTANA-a9c515`) |
| 2 | **Versión B** con definición ejecutable sembrada | `v283-window-b` (preset `sma_crossover`) |
| 3 | Fila **localizadora** de promoción keyed por la cuenta | `strategy_promotions.instrument_id = 1484e253d2d54645945a6b1d7`, `promoted=true` |
| 4 | `EdgeReport` de **A** y de **B** sobre la misma cuenta | 2 filas (`edge_score=0.90`, `credibility=0.80`) |
| 5 | `.env` del operador | `PAPER_D_ACCOUNT_ID=1484e253d2d54645945a6b1d7`, `BROKER_VENUE=paper` |
| 6 | API reiniciada para releer `.env` | `/api/health/ready` = `ready`, head `046_fill_reference_mid` |
| 7 | Registro de setup | `operability_runs/window-setup.json` (no versionado) |

**Identificadores fijos de la ventana (D1..D4):**

- `$ACCOUNT` = `1484e253d2d54645945a6b1d7`
- `$VERSION_A` = `v283-window-a`
- `$VERSION_B` = `v283-window-b` (ACTIVE sembrada, `sma_crossover`)
- watch = los 20 símbolos del catálogo real (derivación determinista por `id`, `>=60` barras D1)

## 2. Declaración de honestidad: la B es una SEMILLA, no una promoción certificada

El material de la ventana **no** gana crédito por esto; gana **medibilidad**. Sin ambigüedad:

- La fila de `strategy_promotions` es un **localizador de ámbito**, no una certificación. Lo declara
  el propio store: *«la fila de localización NO certifica shadow»*
  ([`strategy_lifecycle_store.py`](../../packages/py/application/src/bolsa_application/strategy_lifecycle_store.py), `save_active`).
- Por eso la fila se inserta con **`shadow_validated=false`** y con
  **`reasons=["semilla_operativa_ventana_no_gate_certificada"]`**, que viaja en la propia DB.
- El `EdgeReport` de B (y el de A) es **sintético**, con el mismo criterio y valores que el que el
  propio runner siembra para A cuando crea la cuenta
  ([`v2_76_forward_market_material.py`](../../apps/api-python/scripts/v2_76_forward_market_material.py), `_seed_edge_report`).
  La ausencia de edge **no** se rellena por defecto en producción: aquí se siembra **declarándolo**.
- La definición ejecutable de B se construye con el constructor del repo
  ([`strategy_definition_from_preset`](../../packages/py/analytics/src/bolsa_analytics/signals/preset_catalog.py)),
  no se inventa: la señal se evalúa de verdad (`evaluate_strategy_last_bar`).

**Consecuencia exacta:** `pairActive=true` significa **«par A/B operativo sembrado»**, *no*
«promoción certificada por los gates». `P3-3` (A/B) **no se cierra** con esta semilla: queda
**medible**. Del mismo modo, `P3-2` sigue exigiendo **≥4 días de calendario reales**; una fixture o
una corrida rápida no la cierran.

## 3. Verificación ejecutada (antes de D1)

**Preflight read-only (no escribe nada)** — `v2_76 … --preflight-only --watch-size 20`:

```
régimen por símbolo            {'range': 8, 'trend_down': 9, 'trend_up': 3}
agregado (más conservador)     trend_down
eje operativo                  BEAR_TREND
entradas LONG                  VETADAS (regime_invalid)
exit 2
```

**Lectura honesta (idéntica a la del runbook §1).** El mercado de hoy veta todas las entradas LONG
con el agregado más conservador. Si la ventana arranca en `BEAR_TREND`, `signals=0`/`fills=0` es un
**veto legítimo de régimen**, **no** un fallo de AUTO. No se fuerza `AUTO_ENGINE_SIM_V2_REGIME` y el
veredicto honesto mientras no haya material sigue siendo **`INCONCLUSIVE` / `NO MEDIDO`**.

**Sonda read-only de la B** (sin abrir el motor ni escribir material): `get_active(instrument_id=$ACCOUNT)`
devuelve `v283-window-b` con `executable` presente; `load_active_strategy_decider(...)` devuelve un
decider real con `source="active-strategy:v283-window-b"` ⇒ **`secondaryActive=true`**,
`versionB` no vacío y `watchB` no vacío ⇒ **`pairActive=true`** en el JSON del forward.

## 4. Reglas duras durante la ventana (no negociables)

- `$ACCOUNT` y `$VERSION_A` **constantes** D1..D4; un cambio de cuenta intermedio **invalida** la ventana.
- **No** se toca el gobernador (`aggregate_trial_regime`), `TOP_N`, umbrales `32/3/8/4/2`, allocation,
  pesos A/B, ni la lógica A/B durante la observación: se **mide** el AUTO congelado, no se optimiza.
- **No** se fuerza el régimen, **no** se backdatea `created_at`, **no** se baja
  `min cycles`/`min R`/`folds`/`min_is`/`min_oos`/`min_episodes`.
- **Forward, no replay.** Capturador y auditor **read-only**; no se escribe en `evidence_runs/` ni
  `evidence_validations/` ni en el journal durable desde el auditor.
- **No** se borran los *fixtures* de `operability_runs/`; el glob de las corridas **reales** es
  `operability_runs/forward-market-*.json`.
- `otherCount > 0` ⇒ `H-4` deja de ser teórico: catalogar los `signal_*` **antes** de cerrar la fase
  estadística. `n/d` = **no medido**, nunca `0`.
- Ninguna deuda (`P3-2`, `P3-3`, `H-4`) se cierra por documentación: **primero datos, después evidencia**.

## 5. Cadencia diaria D1..D4

Los comandos exactos (PowerShell) están en el
[runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md) §3.1, con `$ACCOUNT` y
`$VERSION_A` de esta tabla. Resumen del encadenado por día:

```
preflight v2_76  →  forward v2_76 (--account-id fijo)  →  journal v2_77
                 →  ventana v2_80 (--days 4 --forward 'operability_runs/forward-market-*.json')
                 →  auditoría read-only v2_83 (--window operability_runs/operability-window.json)
```

El gate de evidencia (§4 del runbook) solo se lee con **≥4 cubos de calendario compartidos**,
**≥2 episodios** de régimen y **≥32 ciclos** medibles; hasta entonces el veredicto es
**`NO MEDIDO`**.

## 6. Qué NO cambia

El tag `v2.83.1-beta` (objeto auditado) permanece **intacto**: este arranque es operación sobre el
mismo instrumento read-only y el mismo AUTO congelado. Diff de producto: **ninguno** (solo el script
de operación, `.env` local no versionado y este documento).
