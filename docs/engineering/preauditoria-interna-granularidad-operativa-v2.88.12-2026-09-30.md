# Pre-auditoría interna — diseño de granularidad operativa del motor AUTO (`v2.88.12-beta`, 2026-09-30)

> **[NATURALEZA — NO ES UNA AUDITORÍA EXTERNA.]** Documento **interno** de **autocrítica + verificación
> reproducible**. Lo produce **el autor** del diseño, así que **carece de independencia** y **no** sustituye
> el veredicto del auditor externo (MIA). Su cometido es endurecer el objeto antes de esa auditoría y
> dejar por escrito lo verificado, lo no verificado y lo que no debe creerse sin medida.
>
> **Objeto pre-auditado:** [`rethink-granularidad-operativa-auto-2026-09-30.md`](./rethink-granularidad-operativa-auto-2026-09-30.md)
> dentro del tag **`v2.88.12-beta`** (versión `2.11.12-beta`).
> **Cita POST-TAG del sello:** `Release tag CI` `36715434260` — attempt 1 ROJO (`OBS-23`), attempt 2 VERDE.

---

## 0. Resumen

- **Veredicto provisional (autor, NO vinculante): `VIABLE CON CAMBIOS`.**
- El **diagnóstico** se sostiene en sus puntos cargados y es **reproducible** (§1): el motor corre **sin
  `price_script`** (precio plano), el **fill** usa `seed = minute`, la **decisión** está *hardwired* a
  **D1** y la **cadencia** del bucle es de **60 s**.
- Aparecen **4 hallazgos menores** (§2) y **7 respuestas** a las preguntas de la entrega (§3).
- Se declara **lo que no se pudo verificar** interna/independientemente (§4).

---

## 1. Verificación de las citas de §2 del diseño

Verificado sobre el árbol **sin cambios** del sello (el motor es byte-idéntico a `v2.88.11-beta`).

| Afirmación del diseño | Cita | Resultado |
| --- | --- | --- |
| `KERNEL_TIMEFRAMES = {1d,1wk}` | `packages/py/domain/src/bolsa_domain/platform_kernel.py:5` | **Resuelve** (exacto). También `packages/shared/src/platform-kernel.ts:13` y ADR 010 `:74` |
| `ohlcv_bars.timeframe` default `1d` | `packages/py/infrastructure/.../tables.py:145` | **Resuelve** (exacto) |
| Cadencia 60 s | `apps/api-python/src/.../auto_simulation_worker.py:6036` | **Resuelve**: `_sim_interval_seconds(default=60.0)`, env `AUTO_ENGINE_SIM_INTERVAL_SECONDS` |
| **Precio plano en producción** | worker sin `price_script` (`:5768`) → `flat_price_script` (`:317`, default `:616`) | **Resuelve y se confirma**: `AutoSimRuntime` (5768-5776) construye el worker **sin `price_script`** ⇒ default `flat_price_script` (100.0) |
| Fill con `seed = minute` | `auto_simulation_worker.py:1324` | **Resuelve** (exacto): `seed=self._minute * 100_003 + …`, `base_mid=self._price_script(symbol, self._minute)` |
| Protección evaluada cada tick | `protection_compat.py:87` + worker `:4677` | **Resuelve**: `protection_exit_reason(...)` con `minute=self._minute` (`:4683`) |
| Régimen/ATR/señal en D1 *hardwired* | `active_strategy_signal_evaluator.py:74` | **Resuelve**: `make_bar_snapshot_loader(..., timeframe=None)` ⇒ `effective_timeframe = TimeFrame.D1`; el worker **no** pasa `timeframe` (5490, 5514, 5681) |
| Gate de ventana ≥4/≥2/≥32 | `operability_window.py:88-90` | **Resuelve** (exacto) |
| Cubo `day` + ≥4 cubos | `auto_adaptive_correlation.py:62/:71/:75` | **Resuelve** (exacto) |
| Ingesta sólo diaria | `sync_instrument.py:83` (`fetch_daily_bars`), `yahoo_chart.py:21` | **Resuelve** |
| Post-mercado 17:35 | `sync_scheduler.py:26` (`is_post_market_window`) | **Resuelve** la función (el literal `17:35` no se reprodujo en línea) |
| Ciclos ≥32 / episodios ≥2 | `paper_material_readiness.py:103`, `auto_adaptive_uncertainty.py:122` | **Resuelve** (exacto, ambos = valor citado) |
| Replay OOS = modelo de referencia | `replay_oos.py` (`make_as_of_bar_loader`, `as_of()` = día anterior, no-lookahead) | **Resuelve** (concepto confirmado) |
| Único punto con cuotas reales | `scripts/v2_76_forward_market_material.py:603` (`MarketPriceSnapshot`) | **Resuelve** (exacto) |

**Cobertura declarada:** se verificaron las citas que sostienen el **diagnóstico** y la **recomendación**.
**NO** se reprodujeron una a una las líneas de §2.3 (`_advance` `:1284`, settlement `:4802`, reservas
`:5160`, `record_tick` `:5168`) ni `tables.py:24`. → **`NO MEDIDO`** (parcial).

---

## 2. Hallazgos de la pre-auditoría (menores, ninguno cambia conclusiones)

1. **Deriva de línea en algunas citas.** `auto_turn` se cita en `:4614` y está en **`:4602`**; `bar_window`
   se cita en `:3022` y el método `_v2_current_bar_start` está en **`:3020`** (con la llamada a `bar_window`
   en `:3026`). El §10 afirma que **todas** las citas resuelven a línea real ⇒ conviene **re-anclar** esas
   pocas o **declarar tolerancia**.
2. **El *seam* de short-circuit ya existe parcialmente.** `_v2_current_bar_start()` (`:3020`) + el libro
   `self._v2_consumed_bar` (`:3036-3038`, `:3052`, `:3072`, `:3099`) ya evitan **re-emitir señal** en la
   misma barra. Lo que **no** se salta es el trabajo por tick (protección/marcas/reservas/settlement). Esto
   **abara** F1 (opción A) pero el documento **no lo explicita**: merece una línea.
3. **Cifras sin medida (deben marcarse `NO MEDIDO`).** «~99 % del trabajo inútil» (tabla §4 fila A) y el
   ahorro de CPU son **estimaciones**; «~1.440 ticks/día» asume **24 h continuas** (cota superior, no el
   cómputo en horario de mercado). El propio §7-F1 difiere la instrumentación.
4. **Verificación débil en §10.** El §10 no aporta **comando** que resuelva las citas (el resto de la casa
   exige comando por cifra). Sugerencia: un `rg`/script que resuelva `fichero:línea` de §2.

---

## 3. Respuestas a las 7 preguntas de la entrega (visión del autor)

| # | Pregunta | Posición (autor) | Certeza |
| --- | --- | --- | --- |
| a | ¿Diagnóstico completo? | Cubre las superficies localizadas; **vacío posible**: la **ingesta intra-día por API** como superficie y el **auto-sync de 15 s** como cadencia paralela no están inventariados (sólo §2.6). | Media |
| b | ¿`OperativeGranularity` en app o en kernel? | ADR 010 ya centraliza `KERNEL_TIMEFRAMES` y su validación (`platform_kernel.py:32`). Poner el VO en **dominio/kernel** y la *policy* en aplicación evita un tercer sitio de verdad; el doc lo deja en aplicación **sin justificar** ⇒ a consensuar. | Media |
| c | ¿Matriz + gate fail-closed bastan? | Coherente con `signal_identity.bar_window`. **Falta** declarar el **default cuando la capacidad no se pide** y el **dueño** del gate. | Media |
| d | ¿F1 primero? | Sí: mejor ratio riesgo/beneficio y **sin cambio de semántica** (`1d`→`1d`). El *seam* ya medio-existente (hallazgo 2) lo abarata. El éxito debe ser **medido**, no estimado. | Alta |
| e | ¿Cubo fijado por granularidad? | Correcto; migrar a `1wk` **cambia el denominador** del gate ⇒ acto explícito y sellado. Correcto que **no** mueva `P3-2`/`P3-3`. | Alta |
| f | ¿Riesgos en *grace window*/settlement? | `reservation_grace_window` **deriva de `_sim_interval_seconds()`** (`:455`/`:465`) y quedaría mal dimensionada. **Invariante que falta fijar:** gracia en **turnos/barra** y barrido de arranque que distinga huérfana vs viva (`OBS-14.b`, abierta). | Alta |
| g | ¿ADR 010? | `1d`/`1wk` dentro del kernel (sin enmienda); intradía exige **enmienda + ingesta intra-día**. El límite está bien trazado. | Alta |

---

## 4. Lo que **no** se pudo verificar (declarado, no omitido)

- **Independencia:** cualquier sesgo del autor (elección de opciones, framing).
- **Producción en vivo:** que el scheduler real corra con `AUTO_ENGINE_SIM_INTERVAL_SECONDS=60` y **sin**
  `price_script` **en el entorno desplegado** (se verificó en **código**, no en el proceso).
- **Coste real:** sin medición de CPU/ticks (F1 lo instrumenta). → `NO MEDIDO`.
- **Citas de §2.3 y `tables.py:24`:** no reproducidas una a una.

---

## 5. Veredicto provisional y recomendación

**`VIABLE CON CAMBIOS`** (autor, **no vinculante**). Antes/durante F1: (1) re-anclar o declarar tolerancia
en las citas con deriva; (2) marcar `NO MEDIDO` las cifras no medidas; (3) explicitar el *seam*
`_v2_consumed_bar` ya existente; (4) decidir el hogar de `OperativeGranularity` (app vs dominio/kernel).

**Este documento no cierra ni mueve deuda** y **no** es la auditoría externa: el veredicto independiente
sigue pendiente y vive en la entrega
[`entrega-auditoria-externa-mia-v2.88.12-2026-09-30.md`](./entrega-auditoria-externa-mia-v2.88.12-2026-09-30.md).
