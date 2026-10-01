# Audit-pack — `W3.3` + `W4` + `W4.1` / `V2.88.17.1` — proveedor de precio REAL del motor AUTO (tras interruptor) + bundle del fix direccional del scorer OOS y casa única de geometría direccional + robustez del instrumento OOS

> **Objeto auditado:** tag anotado **`v2.88.17.1-beta`** → **`6221700c`** · **Versión `2.11.17.1-beta`**
> (**bump** `2.11.16.3-beta → 2.11.17-beta → 2.11.17.1-beta`) · **Base del diff:** **`v2.88.16.2-beta`**
> · **AsOf:** 2026-10-01 · **Alembic head:** **`046_fill_reference_mid`** (**SIN migración**).
> **Remote:** `github.com/jvelasca/Bolsa_V1.git` — **PÚBLICO** (el auditor clona sin credenciales).
> **Punto de entrada del auditor:** [`arranque-auditor-v2-88-17-1-w4-2026-10-01.md`](./arranque-auditor-v2-88-17-1-w4-2026-10-01.md)
> (**léelo primero**). **Entrega (preguntas + prompt):**
> [`entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md`](./entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md).
> **Evidencia cruda:** [`evidence/v2.88.16.3/README.md`](./evidence/v2.88.16.3/README.md) +
> [`evidence/v2.88.17/README.md`](./evidence/v2.88.17/README.md) +
> [`evidence/v2.88.17.1/README.md`](./evidence/v2.88.17.1/README.md).
> **Contexto de la serie:** [`plan-granularidad-operativa-auto-post-auditoria-2026-09-30.md`](./plan-granularidad-operativa-auto-post-auditoria-2026-09-30.md)
> (`W1`…`W6`) · [`rethink-granularidad-operativa-auto-v2-2026-09-30.md`](./rethink-granularidad-operativa-auto-v2-2026-09-30.md) ·
> [`replay-oos-viabilidad-auto-v2.86-2026-09-29.md`](./replay-oos-viabilidad-auto-v2.86-2026-09-29.md).

---

## 1. Qué es esta fase

El tramo `v2.88.16.2-beta → v2.88.17.1-beta` cierra **la primera mitad de la serie de granularidad
operativa** y arregla, de paso, el defecto que la propia serie dejó a la vista. Tiene **tres objetos**
independientes, todos sellados en el mismo tag:

**(1) Robustez del instrumento OOS (`W3.3`, `v2.88.16.3-beta`).** `W3.2` había demostrado que el
artefacto OOS es **reproducible**; `W3.3` mide **de qué depende**. El ruido del venue es determinista y
cuelga de una línea (`seed = fill_seed(bar_tick, symbol)`): el replay es un **sorteo del venue**.
La banda de `K = 12` sorteos **cruza el cero** ⇒ se declara `point_citable = False`. CERO `src` de
producto: es instrumento.

**(2) El bundle direccional (`v2.88.17-beta`).** Dos defectos gemelos: (a) `replay_oos._realized_r`
calculaba el R realizado **siempre como largo** y el scorer clasificaba apertura=`buy`/cierre=`sell`
**fijos** ⇒ el OOS era long-only **más allá del R**; (b) la regla direccional estaba **reimplementada
en cuatro sitios** (`expected_value._risk_geometry`/`_target_r`, `portfolio_reservation.stop_distance`,
`position_state.signed_r_from_price` y el propio OOS). Se crea **una sola casa**
(`bolsa_analytics.cognitive.directional_geometry`) y los cuatro **delegan** conservando su `_round4`
⇒ `Δ = 0` estricto en long-only.

**(3) El proveedor de precio REAL del motor AUTO (`W4`, `v2.88.17-beta`).** Motivo medido: el simulado
sorteaba el venue sobre un `base_mid` **plano de 100.0** (`flat_price_script`) ⇒ el book es casi todo
ruido y ninguna lectura de mérito es separable del dado. Se introduce el **seam que puede decir «no hay
precio»** — algo que `PriceScript = Callable[[str, int], float]` **no podía expresar** (su único recurso
era mentir con `100.0` o `0`) — y se une a la **frontera de barras cerradas** de `W3`: `mid(...)`
(decisión) lee el `close` de la última barra **cerrada** (`<= B-1`, sin lookahead); `execution(...)`
(fill y marca) lee la barra **corriente** (`OPEN(D+1)`, ya declarada y conocida). Todo ello **tras
interruptor** `AUTO_ENGINE_SIM_REAL_PRICE`, **default OFF** (costura inerte: `Δ = 0`, byte a byte).

**(4) El hotfix `W4.1` (`v2.88.17.1-beta`)** existe porque el tag `v2.88.17-beta` salió **ROJO en
`lifecycle-pg`** por un **sorteo del arnés del certifier `A11`** (`uuid4()`) y **no** por el producto
(`python` y `replay-repro` quedaron verdes en ese mismo run). Es **test-only**: `Δ src = 0`.

En una frase: **el motor gana la capacidad de cotizar de verdad y el OOS gana la capacidad de medir el
lado corto, y ninguna de las dos cambia un byte de lo ya sellado hasta que el propietario encienda el
interruptor o existan cortas.**

---

## 2. Diff esperado (acotado)

| Verdad | Valor |
| --- | --- |
| Rango | `v2.88.16.2-beta` → `v2.88.17.1-beta` |
| Ficheros | **33** (`+3 548 / −130`) |
| **`src` de producto (sin tests)** | **8 ficheros, `+728 / −90`** |
| Ficheros de `src` | `auto_price_provider.py` (+274, **NUEVO**) · `auto_simulation_worker.py` (+227) · `directional_geometry.py` (+125, **NUEVO**) · `replay_oos.py` (±107) · `expected_value.py` (±50) · `position_state.py` (±17) · `portfolio_reservation.py` (±12) · `auto_v2_entry.py` (+6) |
| Migraciones | **NINGUNA** (`git diff --name-only … -- "*alembic*" "*versions*"` ⇒ vacío) |
| Umbrales `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B | **INTACTOS** (ninguno en el diff) |
| ADR 010 | **NO se enmienda** en este tramo |
| Hotfix `W4.1` (`v2.88.17-beta`→`v2.88.17.1-beta`) | **8 ficheros, `+258 / −3`** — 1 test PG (`+96`), la matriz de mutaciones (`+18`), docs y `package.json`; **`src` = 0** |

Comandos de comprobación (el auditor los corre **en el clon**, no confía en esta tabla):

```bash
git diff --stat v2.88.16.2-beta v2.88.17.1-beta
git diff --stat v2.88.16.2-beta v2.88.17.1-beta -- packages/py/analytics/src packages/py/application/src apps/api-python/src
git diff --name-only v2.88.17-beta v2.88.17.1-beta -- packages/py apps/api-python/src   # vacío (test-only)
```

### 2.1 Anexo declarado (fuera de las tesis falsables de §3)

* `scripts/v2_88_16_3_oos_seed_robustness.py` (**+528**): el **instrumento de medición** de `W3.3`.
* `scripts/v2_44_mutation_audit.py` (`+158` en el tramo, `+18` en el hotfix): la matriz de mutaciones.
* 4 tests nuevos (`test_auto_v2_real_price_{source,fail_closed,production_pg}.py`,
  `test_auto_v2_closed_bars_and_bar_idempotency.py` y los casos nuevos de `test_replay_oos.py` /
  `test_directional_geometry.py`).
* `plan-w4-precio-real-2026-10-01.md` (**+414**), evidencia y CHANGELOG/`PROJECT_STATE`/índice.

---

## 3. Tesis falsables (lo que el auditor debe intentar **romper**)

**T1 — El interruptor es inerte por defecto (`Δ = 0`).** Con `AUTO_ENGINE_SIM_REAL_PRICE` **sin
definir**, ninguna lectura de precio del motor cambia respecto de `v2.88.16.2-beta`: el camino hermético
(`ConstantPriceSource`) devuelve **exactamente** lo que devolvía el `PriceScript` y **nunca** `None`.
*Falsación:* el default va **comentado** en `.env.example`; el job `replay-repro` regenera el artefacto
OOS desde la entrada congelada y **assertea** el par sellado; `test_golden_day_v2_process_pg` (`1 passed`,
precio hermético `100.0`). Si cualquiera de los tres se moviera, **T1 es falsa**.

**T2 — Fail-closed por símbolo, jamás una constante.** Sin la barra D1 de hoy,
`OhlcvPriceSource.mid`/`execution` devuelven `None`; el motor declara ese símbolo en **`HOLD`**
(declarado y contado) y el turno en **`BLOCKED`** si **ningún** símbolo tiene precio. *Falsación:*
`test_auto_v2_real_price_fail_closed.py` + buscar en `auto_price_provider.py` **cualquier** rescate
silencioso (`return 100.0`, `or 100.0`, `or 0.0`). El defecto que el módulo dice matar es exactamente
ése.

**T3 — Fronteras temporales disjuntas y sin lookahead.** Decisión = `close` de la última barra
**cerrada** (`<= B-1`); ejecución y marca = barra **corriente**. *Falsación:*
`test_every_price_read_in_a_bar_shares_the_bar_tick` (un script **registra** el tick que recibe y el
test exige que **todas** las lecturas de la barra compartan el tick de **barra**, no el minuto) + la
mutación `M292` (revierte una lectura al minuto) + la ablación del control a `2099` de `W3.2`.
**Ojo:** el paso `2b` unifica **cinco** lecturas al tick de barra y **deja deliberadamente** la sexta
(`protection_exit_reason(..., minute=self._minute)`) en el minuto ⇒ ver el límite `W5` en §5.

**T4 — `Δ = 0` del bundle direccional en long-only.** Para `direction="long"` y precios positivos, la
aritmética es la de antes y la serialización no cambia (`to_dict()` de `RoundTrip`/`OpenPosition`/
`ScoreReport` **intactos**; la dirección viaja **en proceso**). *Falsación:* `replay-repro` verde + el
`git diff` de esos `to_dict` (debe ser vacío) + `test_directional_geometry.py`.

**T5 — El long-only del OOS era LATENTE, no una regresión live.** AUTO es long-only hoy
(`auto_v2_entry._ENTRY_DIRECTION == "long"`), así que el defecto **no rompía** el golden ni el
`replay-repro`, pero **descartaba en silencio** cualquier corta futura. *Falsación:* leer
`_ENTRY_DIRECTION`; si algún día vale `both`/`short`, esta tesis caduca y el bundle pasa de
«higiene» a «cambio de resultados».

**T6 — El instrumento OOS es un sorteo del venue y su banda CRUZA el cero.** `K = 12` sorteos:
ciclos `43…107` (media `70,9 ± 17,8`; dispersión `64`) · **R total `−37,7244 … +0,8182`** (media
`−13,3941 ± 10,1381`; mediana `−12,6662`; dispersión `38,54`) · `decided = 24 500` en las **doce**
(la estrategia evalúa lo mismo; cambia el desenlace del venue) · fills `516…1252` · signo positivo
`27,9 % … 48,5 %` · **`SE(media R) = 2,9266`** e **IC 95 % ±5,7362** ⇒ **`point_citable = False`**:
**un solo sorteo — que es lo que hace `replay-repro` — NO es una medida de mérito citable.**
*Falsación:* re-correr `scripts/v2_88_16_3_oos_seed_robustness.py` con otra `K` y ver si la banda deja
de contener el cero.

**T7 — El hotfix `W4.1` es test-only (`Δ src = 0`).** El tag rojo `v2.88.17-beta` cayó por el **arnés**
del certifier `A11`, no por el producto: en ese mismo run, `python` y `replay-repro` fueron **verdes**.
El arreglo barre ids de instrumento hasta encontrar uno que llene la pata BUY **en la barra corriente y
en la siguiente** (un cruce de medianoche UTC no debe fabricar un rojo nuevo). *Falsación:*
`git diff --name-only v2.88.17-beta v2.88.17.1-beta -- packages/py apps/api-python/src` ⇒ **vacío**.

**T8 — Las mutaciones MUERDEN.** `M8`/`M10`/`M238` **retargeteadas** (la regla se mudó a
`directional_geometry`/`_realized_r`), `M288`–`M291` (bundle: dirección ignorada, apertura
hardcodeada, fail-closed roto, geometría invertida), `M292` (una lectura vuelve al minuto) y `M293`
(se **invierte** la condición de la barrida del certifier). La matriz llega a **`M293`**, con el árbol
restaurado **byte a byte**. *Falsación:* correr la matriz filtrada y ver si alguna se queda **sin
fragmento** (una mutación que no muerde es una tesis que no está guardada).

---

## 4. Compuertas medidas (números exactos)

| Compuerta | Medida |
| --- | --- |
| `Release tag CI` del tag **`v2.88.17.1-beta`** | run **[`36848732534`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36848732534)** — **11 jobs `success` + 1 `skipped`** (`playwright (integrated E2E, opt-in)` por diseño) + `certify` **GREEN** |
| Job `python` (offline) | **`3 219 passed, 41 skipped`** — **idéntico** al run rojo: el certifier `A11` es **PG-gated**, luego el arreglo no toca el offline |
| Job `lifecycle-pg` | **`167 passed`** (`= 165` + el rojo que pasa + la guarda pura nueva) |
| Job `replay-repro` | **`REPRODUCIDO`** — par sellado **`1E3ADAC2…929A37E7` / 3 340 728 B** (LF, el del runner) y **`240662250347A2AA…6D9F54F0` / 3 445 622 B** (CRLF, el del sello original en Windows) |
| Delta del paso `2b` (A/B aislado) | `pytest apps/api-python/tests -k auto` ⇒ **`1 failed, 475 passed` CON `2b`** vs **`2 failed, 474 passed` SIN `2b`** (el rojo es el **pre-existente** `v70`, §5) |
| Bundle direccional (local, sin PG) | `packages/py/analytics/tests` + `packages/py/application/tests` ⇒ **`3 461 passed`**; suites del bundle ⇒ **`155 passed`** |
| Mutaciones del bundle | corrida filtrada `M8/M10/M238/M288–M291` ⇒ **`27/27 medidas`** (ninguna sin fragmento), árbol **intacto** |
| Sorteo del venue (rejilla determinista de **20 000** ids equiespaciados sobre los 40 bits del id) | **`12,30 %` (2 460/20 000) NO llenan** la pata BUY en la barra corriente ⇒ el `uuid4()` del arnés era un dado |
| Certifier `A11` con el arreglo | **`3/3`** verde sobre PG real (2,3 s por corrida) y **`25/25`** en la sesión de diagnóstico, frente a **`19/25`** con el `uuid4` crudo |
| Alembic | head **`046_fill_reference_mid`**, **sin migración** en todo el tramo |

---

## 5. Límites declarados (honestidad)

1. **`W5` NO está.** El `ProtectionClock` legacy sigue leyendo `self._minute`
   (`protection_exit_reason(..., minute=self._minute)`), **deliberadamente**: es el incremento
   siguiente. Consecuencia **real**: la **protección** y el **coste de oportunidad** son los dos
   consumidores que aún no comparten el tick de barra con la decisión, el fill y la marca.
2. **`W6` diferido** (planificador de barra cerrada / intradía). No sellado, no prometido.
3. **`OBS-19` (causa estructural) sigue ABIERTA.** Las listas de pytest se mantienen **a mano** ⇒ el
   peaje se paga en cada tramo. En **este** tramo se pagó **dos veces**: (a) `test_replay_oos.py`
   (**18** tests) no estaba en **ningún** workflow y se da de alta a mano; (b) el hallazgo (4).
4. **Test PG invisible — hallazgo propio (2026-10-01), NO arreglado en este sello.**
   `apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py` (sonda PG, L244) asertaba
   `document["measuredCycles"] == len(e2e._SPECS)` ⇒ **`17 != 26`**, y **falla** cuando corre contra
   PG. **Diagnóstico:** el `17` es **CORRECTO** — `measuredCycles` cuenta los ciclos **con R medible**,
   que en el fixture `AUTO-20B` son los **9 de la familia A + 8 de la B** (`_RISK_CYCLES` = 17); el
   `26` es el **total** de ciclos del fixture (12 A + 8 B + 5 C + 1 U). Es decir: **el test tiene la
   expectativa stale; el producto está bien.** **Por qué nadie lo vio:** el job **offline** lo colecta
   pero `_require_or_skip` hace `pytest.skip` (sin PG y **sin** `AUTO20B_EXPORT_PG_REQUIRED=1`), y los
   jobs **con** PG usan listas **explícitas** en las que el fichero **no figura** (`v70` aparece **0**
   veces en `.github/workflows/`). Se declara aquí, se cita en la entrega y se propone como el
   **siguiente trabajo** (con su alta en CI, que es lo que cierra el peaje de `OBS-19`).
5. **El hash local del `Δ = 0` NO es el sello.** La evidencia cita a veces
   `697526ED…C298967` / `3 448 185 B`; ése es el render **LOCAL en Windows** y **no** coincide con el
   par sellado — *ni coincidía antes de este tramo* (drift de plataforma/seed local, declarado en
   `evidence/v2.88.17` §1.3). **La autoridad es el `assert-artifact` de `replay-repro`** con el par de
   §4, no un número medido en una máquina que no es el runner.
6. **La regla direccional sigue duplicada en 4 módulos** (`risk_allocator`, `trade_plan`,
   `portfolio_decision_engine`, `exit_plan`): convergencia **diferida y declarada**, fuera de alcance.
7. **La dirección NO se serializa** en el artefacto OOS (a propósito: preserva `replay-repro`). Si un
   día se re-baselina la referencia, podrá añadirse.
8. **AUTO es long-only hoy.** El fix direccional **no cambia ningún resultado de producción actual**;
   su valor es que deja de **descartar en silencio** las cortas y prepara el terreno.
9. **El precio real NO se ha ejercido en operación.** Está **sellado tras interruptor**, no medido en
   una ventana larga: `P3-2` (ventana PAPER real ≥ 4 días con material) **sigue sin arrancar**. Nadie
   debe leer «proveedor de precio real» como «medido en producción».
10. **Sin LIVE.** `LIVE_EXECUTION_UNLOCKED` off, `PAPER_D_EXECUTE` off, cancel XTB **PARKED**, sin thaw.
    **BETA / no producción.**

---

## 6. Qué NO es este sello

* **No** es una mejora de rendimiento: el proveedor de precio real está **apagado** por defecto.
* **No** cambia ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B): el diff lo demuestra.
* **No** cierra `OBS-19`, ni `W5`, ni `P3-2`, ni la duplicación direccional residual.
* **No** habilita cortas: `_ENTRY_DIRECTION` sigue en `"long"`.
* **No** es una medida de mérito del OOS: `W3.3` concluye lo contrario (**`point_citable = False`**).
