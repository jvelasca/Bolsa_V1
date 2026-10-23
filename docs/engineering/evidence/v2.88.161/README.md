# Evidencia `v2.88.161-beta` — la reserva de entrada y la intención de salida dejan de ser fail-open

## 1. Qué publica este sello

Acota el commit funcional `815ed4d0` («la reserva de entrada y la intención de salida dejan de ser
fail-open»), el test de la **ruta real del productor** `9ab5ebed`, su corrección **solo de lint**
`2aeb0d8d` (4 × `I001`) y la cita del CI `3e71de49`. **No** toca umbrales, pesos A/B, régimen,
sizing, `TOP_N`, optimizador, orquestador ni replay OOS. **Sin migración:** `head` sigue
`057_top3_opportunity_identity`. El único cambio de comportamiento está en **rutas de fallo** que
antes eran fail-open.

**Límite de entrada (declarado antes de medir).** `PRODUCER_READY` no es `EVIDENCE_READY`, y este
sello **no** cambia la ventana: la evidencia duradera de la cuenta operativa sigue `BLOCKED`.

## 2. Los tres huecos

| Hueco | Síntoma medido (2026-10-23) | Cierre |
| --- | --- | --- |
| **W-161-1** | `_v2_persist_tick_reservations` declaraba `blocked = ∅` cuando no había espejo de reservas ⇒ el tick abría la posición **sin reserva** y el fill nacía sin denominador de riesgo | La emisión se **veta** (`RESERVATION_UNMEASURABLE`); un `save_claim` rechazado o con excepción no deja contexto financiero huérfano |
| **W-161-2** | `_v2_save_exit_order` devolvía `False` sin que el llamante lo comprobara ⇒ la venta se emitía **sin intención durable** | Se persiste `EMERGENCY` con el **mismo `cycle_id`** (reducir riesgo nunca se bloquea); si tampoco es posible, `SYSTEM_ERROR` durable en `auto_kill_state` y la venta **no** se emite |
| **W-161-3** | El gate colapsaba dos causas distintas en un solo rótulo | `paper_material_readiness_v3` separa `no exit orders` de `no exit orders with cycle`; `bucket_closed_cycles` distingue `unattributed` (sin identidad durable) de `undated_with_identity` (hay identidad, falta el instante) |

## 3. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| Ruta **REAL** del productor sobre PostgreSQL (`AUTO_REAL_ROUTE_PRODUCER_PG_REQUIRED=1`) | **7 passed in 9.31 s** (1 positivo + 6 controles negativos, **0 skips**) |
| Ruta real con PostgreSQL inalcanzable y el gate activo | **7 errores, 0 skips** (fail-hard, no se auto-salta) |
| Readiness + operability + productor V2.73/V2.74 | **55 passed in 2.49 s** |
| Worker fail-closed + matriz de crash de salida | **35 passed in 1.17 s** |
| Guardián de bump (`test_dia_d_bump_guard`) | **2 passed in 0.52 s** |
| `ruff` (`packages/py` + `apps/api-python`) | **All checks passed!** |

**Los 6 controles negativos** (el positivo está en §3.1): sin espejo de reservas · claim rechazado ·
claim con excepción · falta la barra de ejecución `B` (cae a `HOLD` fail-closed) · fallo al persistir
el INTENT de salida (cae a `EMERGENCY`) · fallo dual INTENT + emergencia (para de forma durable en
`auto_kill_state`). Un control negativo que **pasa** significa que el sistema hizo lo correcto al
fallar; si alguno dejara de fallar cerrado, el test se pone **rojo**.

### 3.1 Qué demuestra el positivo — y qué no

El positivo recorre el camino productivo (`AutoSimRuntime.run_tick` con `OhlcvPriceSource`, estrategia
activa de PostgreSQL y `paper_material_readiness_v3`) y comprueba: `producer_ready is True`,
`producer_blockers == ()`, `evidence_ready is False`, `fillsWithoutCycle == 0`, `closedCycles >= 1` y
`measurableCycles >= 1`. Es decir: **un** ciclo enlazado, no una muestra.

## 4. La ventana operativa NO mejora (medido, read-only)

Lectura de la cuenta `1484e253d2d54645945a6b1d7` con el lector canónico:

| Dato | Valor |
| --- | --- |
| Veredicto | **`BLOCKED`** |
| Fills durables | **24** |
| Fills **sin** `cycle_id` | **24** (**20** con versión `v283-window-a`; **4** `sell` con versión `NULL`) |
| `portfolio_reservations` | **0** (`n_tup_ins = 0`: nunca hubo alta) |
| `auto_exit_orders` | **0** (ídem) |
| Ciclos medibles | **0** frente al mínimo **32** por estrategia |

**No se backfillea nada.** Que el productor sepa enlazar un ciclo **hacia adelante** no repara los
fills históricos, y no se les inventa identidad ni día. El `4` de `undatedCycles` se lee como «no hay
identidad», no como «no hay fecha».

## 5. Freeze

El bump mueve `apps` —los `meta.bump` de los **13** CLIs viven en `apps/api-python/scripts`— ⇒ el pin
PAPER se **re-ancla** al árbol del sello en un commit **posterior** al del sello, porque el gate
`window:freeze` del job `shared` es **fail-closed** y corre en el CI del tag. El tag apunta al commit
de re-anclaje, no al del sello.

**Consecuencia declarada:** los días medidos bajo el pin anterior quedan **`STALE`** y la medición
válida arranca en el primer día de sesión posterior al tag. Re-anclar **no** crea ciclos ni mejora el
veredicto: cambia el árbol de referencia.

## 6. Dictamen

**Sello PREPARADO, NO CERRADO.** El commit del sello existe y el tag anotado se crea **sobre el
commit de re-anclaje** (§5), no sobre el del sello. Las comprobaciones de §3 están verdes en este
árbol. La condición de cierre del dictamen —**CI obligatorio del tag verde**— sigue **PENDIENTE**:
ningún run del `Release tag CI` se ha ejecutado para `v2.88.161-beta` en el momento de escribir esta
evidencia, y ese run es el **primero** que ejecuta los gates ESTUDIO/identidad (universo, DÍA-D trace,
daily watch, PAPER window, cadena por valor y batería de identidad) que ningún run por commit corre.
Hasta que exista ese verde, el sello **no se declara cerrado**.

## 7. Límites declarados

- **AUTO sigue OFF.** Operativa **100 % PAPER virtual**; cero LIVE, cero XTB real.
- `PRODUCER_READY` acredita el **recorrido** del escenario E2E, **no** la ventana: `evidence_ready`
  sigue **`false`**.
- La ventana sigue **`INCONCLUSIVE`**; `CONFIRMED` **no** se emite.
- Un CI verde **no** certifica rentabilidad: certifica que los gates pasan.
- Los artefactos históricos **no** se reescriben ni se backfillean.
