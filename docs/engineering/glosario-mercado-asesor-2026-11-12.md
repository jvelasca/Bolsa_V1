# Glosario canónico de mercado — recomendación y tendencia (S1 · 2026-11-12)

> **Qué fija este documento:** la **única** tabla de nombres visibles para las 7 posturas
> del motor, los 19 motivos que las justifican y las etiquetas de tendencia. No cambia
> ninguna decisión: `compute_stance`, `map_io_to_stars`, los umbrales y el gate siguen
> byte-idénticos.
>
> **Invariantes del slice:** `Δ motor = 0` · `Δ decisión = 0` · **sin migración**
> (`head` sigue `067_opinion_account_scope`) · **sin `contract:gen`** · sin cambios en
> `openapi.json` ni en `schema.d.ts`.
>
> **Fuente de verdad en código:** [`packages/shared/src/market-vocabulary.ts`](../../packages/shared/src/market-vocabulary.ts).
> El espejo Python del email de alarmas es una **segunda fuente declarada**
> ([`estudio_opinion_email.py`](../../packages/py/infrastructure/src/bolsa_infrastructure/alerts/estudio_opinion_email.py));
> si diverge, falla el test de cuerpo.

---

## 1. Las 7 recomendaciones

La clave interna viaja intacta en el DTO. Lo que cambia es **solo** el nombre visible.

| Clave del motor | Denominación visible | Familia | Canal | Disparador (motor, sin umbrales nuevos) |
| --- | --- | --- | --- | --- |
| `buy` | **Comprar** | alcista | alarma (★≥4) | Sin posición, IO ≥ 80 y estrategia #1 del Lab ≥ 3★ |
| `hold_watch` | **Mantener** | neutral | silencio | Con posición: la señal no pide salir ni reforzar. Sin posición: no hay entrada hoy |
| `overbought` | **Sin respaldo** | sin señal | aviso | Posición abierta, estrategia #1 < 3★ e IO > 45 |
| `reduce` | **Reducir** | bajista | alarma (★≥3) | Posición abierta y (alerta fundamental o IO ≤ 45) |
| `sell_exit` | **Vender** | bajista | alarma (★≥3) | Posición abierta, sin distress e IO ≤ 30 |
| `no_trade` | **por causa** (ver §2) | sin señal | silencio | Falta un término: cierre de sesión, cartera medida, distress o veto de riesgo |
| `review_strategy` | **Revisar estrategia** | sin señal | aviso | Sin TOP o TOP con más de 30 días |

**Decisiones cerradas que no se reabren:**

- `hold_watch` **nunca** se llama «Vigilar» en una superficie de recomendación. «Vigilar»
  sigue siendo válido como categoría WATCH de Mesa (`MESA_ENTRY_STATUS_LABEL.WATCH`).
- `overbought` **nunca** se llama «Sobrecomprado»: la postura dice que la estrategia ya no
  respalda la posición, no que el precio esté técnicamente sobrecomprado.
- `review_strategy` revisa la **estrategia del Lab**, no la «tesis» del valor. El motor no
  conoce tesis.
- `buy` exige el respaldo del Lab. Unas ★ altas del dictamen, solas, **no** autorizan compra.

## 2. `no_trade` se lee por su causa

La etiqueta base «No operar» sola sería deshonesta: confundiría «no se midió» con «se midió
y no se opera». Se afina por la causa declarada en `reasons`, con esta precedencia:

| Causa presente | Etiqueta | Detalle | Nota |
| --- | --- | --- | --- |
| `position_unmeasured` | **No evaluable** | «Cartera sin medir» | Jamás «sin posición» ni «No operar» |
| `position_closed` | **No evaluable** | «Posición no confirmada» | Defensa: no se afirma ausencia de posición |
| `gate_veto` | «Operativa bloqueada» | «Filtro de riesgo en veto» | **Solo diagnóstico**; no alcanzable en producto |
| `eod_data_stale` | **No operar** | «Sin cierre de sesión» | El dato falta; no hay señal |
| `fa_distress` (sin posición) | **No operar** | «Alerta fundamental» | — |

`gate_veto` no es un estado operativo: `daily_opinion_hints.py` fija `allow_trading=True`
([`daily_opinion_hints.py` L255-L265](../../packages/py/application/src/bolsa_application/daily_opinion_hints.py))
y `estudio_daily_ops.py` lo declara advisory
([`estudio_daily_ops.py` L480-L483](../../packages/py/application/src/bolsa_application/estudio_daily_ops.py)).
Por eso `visibleReasons` lo filtra **siempre**.

## 3. Los 19 motivos

| Código | Texto visible |
| --- | --- |
| `eod_data_stale` | Sin cierre de sesión |
| `gate_veto` | Filtro de riesgo en veto *(solo diagnóstico)* |
| `stale_top` | Estrategia del Lab desactualizada |
| `no_valid_top` | Sin estrategia del Lab |
| `fa_distress` | Alerta fundamental |
| `strong_buy_signal` | Señal de compra fuerte |
| `neutral_no_position` | Sin señal de entrada |
| `overbought_or_exit` | Señal de salida |
| `holding_position` | Posición abierta: se mantiene |
| `top_high` | Estrategia del Lab con respaldo alto |
| `top_medium` | Estrategia del Lab con respaldo suficiente |
| `top_low` | Estrategia del Lab sin respaldo |
| `io_high` | Calidad de señal alta |
| `io_low` | Calidad de señal baja |
| `io_medium` | Calidad de señal sin señal de compra |
| `position_open` | Ya hay posición abierta |
| `position_closed` | Posición no confirmada |
| `position_unmeasured` | Cartera sin medir |
| `io_unmeasured` | Calidad de señal sin medir |

**Los motivos no son medidas.** `io_medium` se emite también con IO 85 o `null`; por eso su
texto **no** lleva rango numérico. El número vive en «Confianza».

Reglas de presentación (puras, `visibleReasons`):

1. Máximo **3** motivos visibles; el resto va al tooltip con su recuento (`(+N)`).
2. Se suprime `io_medium` cuando el IO ≥ 80 o es `null`: afirmaría una falta de compra que
   el motor no está diciendo.
3. Se deduplica `position_open` cuando ya aparece `holding_position`.
4. `gate_veto` no entra en producto.
5. Sin etiquetas repetidas.

## 4. Tendencia: `Lateral` ≠ `Mixta` ≠ `Neutra`

Son tres cosas distintas y fusionarlas sería corregir el vocabulario creando un error de
significado.

| Valor de `study.trends` | Etiqueta | Tono | Base |
| --- | --- | --- | --- |
| `strong_bullish` | Alcista fuerte | `bullish` | ADX + DI con fuerza |
| `bullish` | Alcista | `bullish` | ADX + DI |
| `weak` | **Lateral** | `range` | Tendencia débil o **rango** (ADX ≤ 25) |
| `strong_bearish` | Bajista fuerte | `bearish` | ADX + DI con fuerza |
| `bearish` | Bajista | `bearish` | ADX + DI |
| `mixed` | **Mixta** | `mixed` | Las **medias** no coinciden en una estructura |
| `neutral` | **Neutra** | `neutral` | Sin dirección declarada |
| `null` / desconocido | Sin dato de tendencia | `unknown` | Hueco declarado |

- `weak` es rango **literal**: [`technical_facts.py` L45-L53](../../packages/py/analytics/src/bolsa_analytics/knowledge/technical_facts.py).
- `mixed` describe `structure.sma`: [`decision_journal_studies.py` L43-L47](../../packages/py/application/src/bolsa_application/decision_journal_studies.py).
- `neutral` ya no cae en `unknown`: se añadió su tono en la proyección
  ([`instrument-daily-analysis.ts`](../../packages/shared/src/cognitive/instrument-daily-analysis.ts)).
- La banda sigue mostrando el `display` literal del parte; si falta, se traduce el `value`
  canónico. Un valor desconocido **no** se pinta en crudo.
- `structure.sma`: `bullish_stack` → «Alineada alcista», `bearish_stack` → «Alineada
  bajista», `mixed` → «Mixta».

## 5. ★ y confianza

- Las **★ del dictamen** miden la señal del día; **no** son las ★ de la estrategia del Lab.
  Esa distinción se explica en prosa, no con la fórmula «★ dictamen ≠ ★ TOP».
- `map_io_to_stars(null)` devuelve **3**. Ese 3 es de reserva, **no** una medición: la UI
  pinta **«Sin medir»** cuando `ioScore` es `null` y **nunca** un ★3 con apariencia medida.
- «Confianza» es el IO en escala 0–100 (`formatConfidence`); sin IO, «Sin medir».

## 6. Termómetro de proximidad (display)

Se deriva en el cliente de precio + entrada + niveles; **no** es un dato del motor ni una
orden. Estados y precedencia:

| Precedencia | Estado | Significado |
| --- | --- | --- |
| 0 | **Sin entrada** | No hay entrada publicada o falta el precio |
| 1 | **Extendido** | El precio ya superó el Objetivo 1: comprar aquí es perseguir |
| 2 | **Caliente** | El precio ya está en la zona de activación |
| 3 | **Templado** | Cerca de la entrada (±3 %), sin activarla |
| 4 | **Frío** | Lejos de la entrada |

Si el precio está por debajo de la invalidación, el detalle lo **declara** sin cambiar de
estado: la geometría publicada ya no es válida. `source` es siempre `"display"`.

## 7. Reglas de honestidad (falsables por test)

1. **Ninguna clave interna se pinta.** `snake_case` prohibido en superficies de
   recomendación; toda clave pasa por la tabla.
2. **Un dato ausente se declara**: «Sin medir», «Sin entrada publicada», «Sin nivel
   medido», «Sin dato de tendencia». Nunca se colapsa a 0 ni a una postura inventada.
3. **El motor no se toca:** `daily_opinion_stance.py` y su test deben quedar sin diff
   (`git diff --exit-code`).
4. **El contrato no se toca:** `openapi.json` y `schema.d.ts` fuera del diff.
5. **El email de alarmas** no imprime `row.stance` ni códigos; su cuerpo se testea contra
   `snake_case` y contra las 7 claves.

Guardas:

- `packages/shared/src/market-vocabulary.test.ts` — totalidad de las 7 posturas y los 19
  motivos, `Sin respaldo`, `Comprar`/Lab, `No evaluable`, `Mixta` ≠ `Lateral`, termómetro.
- `apps/web/src/features/trading/operativa-recomendacion-vocabulary.test.tsx` — render de
  las 7 posturas sin clave interna, textos retirados y mapa interno de canales.
- `packages/py/infrastructure/tests/test_estudio_opinion_email_notify.py` — cuerpo del email
  sin claves crudas y sin ★3 fabricadas.

## 8. Superficies afectadas (S1)

| Superficie | Fichero |
| --- | --- |
| OPERATIVA · Decisión | [`operativa-dictamen.tsx`](../../apps/web/src/features/trading/operativa-dictamen.tsx) |
| OPERATIVA · Análisis diario | [`operativa-analisis-diario.tsx`](../../apps/web/src/features/trading/operativa-analisis-diario.tsx) |
| Asesor · Opiniones de hoy | [`asesor-opiniones-panel.tsx`](../../apps/web/src/features/research/asesor-opiniones-panel.tsx) |
| Estudio · Operativa diaria | [`estudio-daily-ops-panel.tsx`](../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx) |
| Instrumento · evolución del dictamen | [`instrument-dictamen-evolution.tsx`](../../apps/web/src/features/instruments/instrument-dictamen-evolution.tsx) |
| Listas · columna de recomendación | [`list-recommendation-scores-context.tsx`](../../apps/web/src/features/trading/lists-tab/list-recommendation-scores-context.tsx) |
| Email de alarmas | [`estudio_opinion_email.py`](../../packages/py/infrastructure/src/bolsa_infrastructure/alerts/estudio_opinion_email.py) |

## 9. Estado de S0 (precondición)

El árbol contiene trabajo sin sellar de la rama `feat/f4-067-opinion-account-scope`.
La revisión de S1 confirma que **cuatro** de los ficheros tocados llevan cambios ajenos
(Asesor, hub de instrumentos, evolución del dictamen y los tipos de opinión) y que la
proyección del análisis diario solo tiene ruido de fin de línea.

**S0 no está autorizado:** no se sella ni se commitea nada en este slice. S1 escribe solo
contenido nuevo y **nunca** usa `git add -A`.
