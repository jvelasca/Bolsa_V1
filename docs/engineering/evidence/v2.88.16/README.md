# Evidencia del sello `v2.88.16-beta` — `GRANULARIDAD-OPERATIVA` · **W3** (Fase B · anclaje temporal `OPEN(D+1)`)

> **Objeto:** tag anotado **`v2.88.16-beta`** · **Versión:** `2.11.16-beta` · **Alembic head:**
> `046_fill_reference_mid` (**sin migración**).
> **Naturaleza:** **primer** incremento de la serie que **cambia resultados** y por eso exige
> **golden nuevo** con el delta old-vs-new **medido** (no narrado). Fija **cuándo** se decide y se
> ejecuta, **sin** tocar todavía el **proveedor** de precio (eso es `W4`).
> **Base del diff:** `v2.88.15-beta` (padre del árbol sellado).
> **AsOf:** 2026-09-30.

---

## 1. Qué es este sello

`W3` del [plan de trabajos](../../plan-granularidad-operativa-auto-post-auditoria-2026-09-30.md).
Dos movimientos del **tiempo** del motor, ninguno observable con un test de caja blanca del helper:

1. **NO lookahead (frontera de barras cerradas).** La decisión de la barra `B` se alimenta con las
   barras **cerradas** `<= B-1`. La frontera la aporta el motor (`_v2_closed_bar_as_of`) y la aplica
   el cargador que el motor **compone** (`make_closed_bar_loader`) para la señal, el régimen y el ATR.
2. **Ancla de ejecución = barra corriente (`OPEN(D+1)`).** La orden se ejecuta anclada a la barra
   que **contiene** el instante (`bar_tick`), no al minuto del bucle: se elimina
   `seed = self._minute * 100_003 + …` y el anclaje a `_price_script(symbol, self._minute)` del fill.

El contrato temporal es **uno solo** y vive en `packages/py/application/src/bolsa_application/closed_bars.py`
(nuevo): el **MOTOR AUTO** y el **instrumento de investigación** (`replay_oos`) comparten la **misma**
frontera, en vez de dos definiciones parecidas que se separan con el tiempo.

**NO** enmienda el ADR 010 y **NO** toca `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B.

---

## 2. Ficheros del sello

| Fichero | Δ | Rol |
| --- | --- | --- |
| `packages/py/application/src/bolsa_application/closed_bars.py` | **nuevo**, 193 líneas | frontera única: `bar_day`, `bar_tick`, `last_closed_bar_day`, `clamp_bars_as_of`, `make_closed_bar_loader`, `resolve_as_of` |
| `packages/py/application/src/bolsa_application/simulated_broker.py` | `+19` | `fill_seed(bar_tick, instrument_id)` — **única fuente** de la derivación del seed del book |
| `packages/py/application/src/bolsa_application/replay_oos.py` | `+?/−?` | converge a `closed_bars` y re-exporta `bar_day`/`clamp_bars_as_of`/`make_as_of_bar_loader` (contrato público intacto) |
| `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | `+161/−?` | `_v2_bar_tick` (`:3107`), `_v2_closed_bar_as_of` (`:3118`), `_next_logical_order_id` anclada a barra (`:1224`), fill con `fill_seed(bar_tick_now, symbol)` (`:1403`), régimen/ATR/señal compuestos con la frontera (`:5656`, `:5695`, `:5868`) |
| `packages/py/application/tests/test_closed_bars.py` | **nuevo**, 237 líneas, **19 tests** | la frontera pura: `B-1`, barras sub-diarias/indatadas fail-closed, proveedor de `as_of`, guardia en cliente |
| `apps/api-python/tests/test_auto_v2_closed_bars_and_bar_idempotency.py` | **nuevo**, 480 líneas, **5 tests** | cableado del motor + idempotencia intra-barra (ver §3 y §5) |
| `apps/api-python/scripts/v2_88_16_golden_day_delta.py` | **nuevo**, 342 líneas | medición reproducible del delta del golden (ver §4) |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | `+37` | **`M279`→`M282`** (la matriz llega a **`M282`**) |
| `apps/api-python/scripts/v2_74_paper_producer_evidence.py` · `v2_75_paper_sample_accumulation.py` | rebaseline | el sondeo de instrumentos usa `fill_seed(bar_tick, …)` (ver §7) |
| `apps/api-python/tests/test_auto_v2_golden_day_evidence.py` | rebaseline | día golden `2026-09-15 → 2026-09-17` (ver §4) |
| `apps/api-python/tests/test_auto_v2_durable_pg.py` · `test_concurrent_auto_pg.py` · `test_auto_v46_concurrent.py` · `test_auto_v46_crash_recovery.py` · `test_auto_v74_producer_pg_e2e.py` · `test_crash_recovery_day_process_pg.py` · `test_golden_day_v2_process_pg.py` · `test_a9_scheduler_process_pg_zero_human.py` | rebaseline | el sondeo de instrumentos pasa a `fill_seed(tick_de_barra, id)` (barra real del run) |
| `.github/workflows/python-ci.yml` (`:361`) · `release-tag-ci.yml` (`:564`) | `+1` cada uno | alta **manual** de `packages/py/application/tests/test_closed_bars.py` (ese directorio **no** tiene pase de directorio: `OBS-19`) |

**Sin migración.** El head sigue en `packages/py/infrastructure/alembic/versions/046_fill_reference_mid.py`.

**El test nuevo `apps/api-python/tests/…` entra en AMBOS workflows por el pase de directorio** de
`apps/api-python/tests` (`python-ci.yml:362`, `release-tag-ci.yml:565`); **no** requiere registro manual.

---

## 3. El contrato temporal (una sola definición)

| Helper (`closed_bars.py`) | Qué fija |
| --- | --- |
| `last_closed_bar_day(moment, timeframe)` | día ISO de la última barra **cerrada** (`B-1`): el `as_of` de todo dato que alimente la decisión |
| `bar_tick(moment, timeframe)` | índice ENTERO de la barra que **contiene** `moment`: **constante dentro** de la barra, distinto entre barras |
| `clamp_bars_as_of(bars, as_of)` | guardia en CLIENTE: `día <= as_of`; una barra **sin fecha** se **descarta** |
| `make_closed_bar_loader(ohlcv, symbols, as_of, …)` | `refresh()` async acotado a `<= as_of`; usa `date_to` del repositorio **y** la guardia en cliente |

**Fail-closed por diseño (medido en `test_closed_bars.py`, 19/19):**

- Sin `as_of` resoluble (o con provider vacío) la ventana es **`[]`** ⇒ el motor queda en **HOLD**.
- Con una barra **sub-diaria** (`1m`, `1h`) la frontera «día» **no es expresable** ⇒ `""` y ventana
  vacía. **Nunca** degrado a «las barras de hoy» (que es justo el lookahead que esto cierra).
- Una barra **sin fecha legible** se **descarta** (jamás se asume del pasado).
- Un port de barras de **firma reducida** (sin `date_to`) cae al camino sin filtro y la guardia en
  CLIENTE hace el trabajo: lee de más, **no decide** de más.

El motor mueve la frontera **en cada tick** con un **provider** (`_v2_closed_bar_as_of`), sin
recomponer el cargador (`auto_simulation_worker.py:5900`).

---

## 4. Golden day — delta old-vs-new **medido** (gate de cierre de `W3`)

**Qué cambió y por qué.** Con el ancla vieja el seed del book colgaba del **minuto** del bucle
(`seed = self._minute * 100_003 + sum(ord(símbolo)) % 9999`): el ruido se re-sorteaba **cada 60 s**, de
modo que hasta **1.440 reintentos/día** rescataban una orden rechazada. Con el ancla de **barra** el
desenlace de la barra es **único**: si la barra rechaza, **no** se reintenta dentro de ella.

**Consecuencia legítima (no un defecto):** el guion del día golden exige una barra donde las **tres**
compras y las **dos** salidas de la misma barra llenen **completas**. `2026-09-15` dejó de cumplirlo
(el buy de `BBB` topa con `noise_reject`, ≈**5,6 %** por orden) ⇒ el fixture se re-elige a
**`2026-09-17`**, que es el **primer** día posterior que sostiene la premisa.

**Medición reproducible** (`apps/api-python/scripts/v2_88_16_golden_day_delta.py`, salida literal):

```
old_day_fails_with_bar_anchor          True
old_day_was_rescuable_by_minute_retry  True
new_day_holds_with_bar_anchor          True
new_day_is_first_valid                 True
```

| Barra | Ancla de barra | Ancla de minuto (histórica) |
| --- | --- | --- |
| `2026-09-15` | buy `BBB` → `rejected/noise_reject` (0) ⇒ **no sostiene** | **rescatable** (minutos útiles/orden: buy `AAA` 1258 · buy `BBB` 1270 · buy `CCC` 1271 · sell `BBB` 1080 · sell `CCC` 1102 de 1440) |
| `2026-09-17` | 3 compras + 2 salidas en barra **completas** ⇒ **sostiene** | — |
| `2026-11-01` (`time_exit` de `AAA`, salto de reloj del guion) | sell `AAA` `filled` (250) | — |

El script **re-deriva** el primer día válido (barrido de 30 días) y lo compara con el declarado, así
que la elección del fixture **no** es narrada: si el delta no se reproduce, el script sale con código
**2** y el sello no se firma. El test `test_auto_v2_golden_day_evidence.py` (5/5) queda rebaselado al
día nuevo con la razón documentada en su cabecera.

---

## 5. Idempotencia intra-barra (el desenlace de la barra es ÚNICO)

`test_auto_v2_closed_bars_and_bar_idempotency.py` (5/5) se construye con la propiedad **inversa** a
propósito, para que el test **mida** y no narre:

- **Fase A — la barra rechaza.** Un instrumento elegido para que el ancla de **barra** lo **rechace**
  y el ancla de **minuto** (minuto 2) lo **llene**: tres turnos en la MISMA barra reintentan la
  entrada y llegan al venue con el **mismo `seed` y el mismo `order_id`**; la posición del rechazo
  **no** se materializa. Si alguien devuelve el seed al minuto (`M280`), el reintento **llena** y el
  test rompe.
- **Fase B — la barra llena PARCIAL.** Con el compromiso de la barra **vivo**, el reintento
  intra-barra **no vuelve a emitir**: una sola llamada al venue y la posición **no** crece (la mitad
  financiera del invariante: «cero doble efecto», no «cero reintento»). Una única reserva viva.
- **Cruce de barra.** Ancla distinta ⇒ identidad distinta (sin colisión) y **sorteo nuevo**
  (`M281`, un tick congelado repartiría el mismo desenlace a todas las barras).

Y el cableado del motor se comprueba en el **mismo objeto** que lo usa: la frontera `B-1` a lo largo
del reloj (`test_the_closed_bar_boundary_is_the_bar_before_the_one_in_course`), la ventana del
cargador que **excluye** la barra en curso —incluso con port de firma reducida—, la ventana **vacía**
fail-closed con barra sub-diaria/indatada, y que **régimen y ATR** se componen **ambos** con la
frontera del motor (`test_the_runtime_composes_regime_and_atr_with_the_closed_bar_boundary`).

---

## 6. Mutaciones (`M279` → `M282`, +4)

| Id | Defecto inyectado | Mata |
| --- | --- | --- |
| `M279` | **LOOKAHEAD**: la frontera devuelve el día de la barra **EN CURSO** ⇒ la señal, el régimen y el ATR deciden con datos que la barra todavía no cerró | `test_the_closed_bar_boundary_is_the_bar_before_the_one_in_course`, `test_the_loader_the_engine_composes_excludes_the_bar_in_course`, `test_last_closed_bar_day_*`, `test_loader_*`, `test_an_intra_bar_retry_…` |
| `M280` | **seed por MINUTO**: un reintento intra-barra es un sorteo NUEVO (puede llenar lo que la barra ya rechazó y duplicar dinero) | `test_an_intra_bar_retry_reuses_the_bar_anchor_and_cannot_double_the_day` |
| `M281` | **`bar_tick` CONSTANTE**: todas las barras comparten ancla y la identidad de la orden colisiona entre días | `test_bar_tick_*`, `test_an_intra_bar_retry_…` |
| `M282` | **ejecución en `D`/`CLOSE(D)`**: el ancla de ejecución se corre a la barra YA cerrada en vez de la corriente (`OPEN(D+1)`) | `test_the_closed_bar_boundary_…`, `test_an_intra_bar_retry_…` |

**Resultado:** `4/4` muerden; la sonda restaura el árbol **byte a byte** (`medidas: 4/4`; salida literal:

```
### M279 ... rojo en: test_an_intra_bar_retry_..., test_last_closed_bar_day_..., test_the_closed_bar_boundary_..., test_the_loader_...
### M280 ... rojo en: test_an_intra_bar_retry_reuses_the_bar_anchor_and_cannot_double_the_day
### M281 ... rojo en: test_an_intra_bar_retry_..., test_bar_tick_distinguishes_hours_within_a_day, test_bar_tick_is_constant_within_the_bar_and_moves_between_bars
### M282 ... rojo en: test_an_intra_bar_retry_..., test_the_closed_bar_boundary_...
  intacto: la sonda no altero el arbol
  medidas: 4/4 (ninguna se quedo sin fragmento)
```
)

---

## 7. Scripts de evidencia rebaselinados (producen muestra)

El sondeo de instrumentos de los dos scripts usaba el seed por minuto; pasa a la **misma**
derivación que el motor (`fill_seed(bar_tick, …)`) sobre la barra del round-trip, y exige el llenado
**COMPLETO** de la cantidad real (el ancla de barra hace **un** sorteo: un fill parcial deja residuo
que **no** se limpia dentro del día).

| Script | Resultado |
| --- | --- |
| `v2_74_paper_producer_evidence.py` | **`PRODUCER_READY`** (8 fills, 1 ciclo medible) |
| `v2_75_paper_sample_accumulation.py` | **`EVIDENCE_READY`** · **40/40** round-trips cerrados · **40** ciclos medibles (≥ `32`) · **320** fills · `Allocation FROZEN` |

**Correcciones de la herramienta (declaradas):** el `print` final leía la clave vieja
`instrument` (el esquema pasó a `instruments`/`instrumentFamily`) ⇒ `KeyError` corregido; y el
sondeo aceptaba un fill CUALQUIERA en vez de COMPLETO, lo que con el ancla de barra dejaba residuo y
envenenaba los round-trips posteriores que reusaban el mismo id.

---

## 8. Verificación local (números exactos)

| Gate | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `mypy` (targets de CI, `--follow-imports=silent`) | `Success: no issues found in 511 source files` |
| `lint-imports --config packages/py/.importlinter` | `Contracts: 4 kept, 0 broken.` |
| `pytest packages/py/application/tests/test_closed_bars.py` | **`19 passed`** |
| `pytest apps/api-python/tests/test_auto_v2_closed_bars_and_bar_idempotency.py` | **`5 passed`** |
| `pytest apps/api-python/tests/test_auto_v2_golden_day_evidence.py` | **`5 passed`** |
| mutación `M279`→`M282` | **`4/4`** (árbol intacto) |
| 5 suites PG del sello (`durable` 3 · `v74` 1 · `concurrent` 3 · `crash` 1 · `golden` 1) | **`9 passed`** |
| delta golden (`v2_88_16_golden_day_delta.py`) | **`DELTA REPRODUCIDO`** (exit `0`) |
| batería offline del listado de `release-tag-ci.yml` | **`3203 passed + 1 failed`** sobre **`3204`** recogidos (ver §9) |

**El único rojo local** es el **PG-local PRE-EXISTENTE**
`test_auto_v70_auto23_evidence_validation.py::test_the_validation_reads_real_postgres_material_and_seals_it`
(`assert 17 == 26`), que **CI salta** (el job `python` no tiene PostgreSQL) y que ya era el rojo
declarado de `v2.88.15`. **No** es del sello.

**Encaje de cuentas:** los **`3204`** recogidos = los **`3180`** de `v2.88.15` + **`24`** tests nuevos
del bundle `W3` (`19` de `test_closed_bars.py` + `5` de `test_auto_v2_closed_bars_and_bar_idempotency.py`).
La nueva suite de aplicación se **registra a mano** en los dos workflows (§2) porque
`packages/py/application/tests` **no** tiene pase de directorio: sin alta, no correría (`OBS-19`).

---

## 9. Cita del CI (POST-TAG, 2026-09-30)

Límite estructural (`OBS-3`/`OBS-4`): `Release tag CI` **sólo corre al empujar** el tag ⇒ su resultado
no puede vivir dentro del propio tag; se cita en `main` como commit **POST-TAG**.

**Predicción declarada (Encaje `ESPERADO = OBSERVADO`):** job `python` **`3166 passed, 38 skipped`** =
los **`3142`** esperados de `v2.88.15` + **`24`** del bundle `W3`, con los **mismos `38` skips** y
`ruff`/`import-linter`/`mypy` con los mismos veredictos. **Se cita el run, no se hereda.**

> **PENDIENTE DE CITA.** Este documento se sella con la **predicción** y el **encaje que cierra** (los
> `3204` recogidos local = `3180 + 24`); la cita verbatim del run se añade en `main` como commit
> **POST-TAG** cuando el propietario publique `v2.88.16-beta` (mismo patrón que `v2.88.15`/`v2.88.14`).

---

## 10. Firma de estado (verificable)

```
git cat-file -t v2.88.16-beta                                     # tag (anotado)
git show v2.88.16-beta:package.json                               # 2.11.16-beta
git diff --stat v2.88.15-beta v2.88.16-beta -- packages/py apps/api-python/src \
  apps/api-python/scripts apps/api-python/tests .github
# Alembic: sin migración nueva (head sigue 046_fill_reference_mid)
```

---

## 11. Deuda que este sello NO cierra

`P3-2`/`P3-3` (ventana PAPER real ≥4 días con material — **se habilita de verdad con `W4`**),
`OBS-19` (**causa estructural**: listas manuales; aquí se **paga** el peaje registrando el test nuevo),
`OBS-16` (cobertura local-vs-CI), `OBS-15` (techo de `1000 APPLIED`), `OBS-22`, `OBS-14.b`, `OBS-13`,
`OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`. `OBS-21` y `OBS-23` siguen **CERRADAS**.

---

## 12. Revisión

- **Implementa** `W3` del [plan](../../plan-granularidad-operativa-auto-post-auditoria-2026-09-30.md):
  `signal_bar = D → execution_bar = corriente`, referencia de ejecución anclada a la **barra** y
  eliminación del `seed` por minuto. Converge al contrato ya probado del replay (`closed_bars`
  compartido).
- **Cambia resultados de forma legítima** ⇒ **golden nuevo** con el delta old-vs-new **medido** (§4),
  que es el **gate de cierre** del incremento.
- **Siguiente incremento:** **`W4`** (`v2.88.17-beta`) — proveedor de **precio real**: el runtime
  productivo deja de simular sobre `100.0` (`flat_price_script`) y el PAPER empieza a **medir algo
  real** (desbloquea la validación longitudinal de `P3-2`/`P3-3`).
