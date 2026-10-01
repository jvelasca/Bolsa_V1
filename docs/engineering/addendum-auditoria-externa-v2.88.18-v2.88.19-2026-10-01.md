# Addendum de auditoría externa — `v2.88.18-beta` + `v2.88.19-beta`

> **Clase:** **docs-only** (SIN bump, SIN tag, CERO `src`, CERO tests). **Fecha:** 2026-10-01.
> **Qué es:** el **delta** que hay que añadir al paquete de handover ya publicado ([`entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md`](./entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md) + [audit-pack](./audit-pack-v2.88.17-w4-bundle-direccional-2026-10-01.md) + [arranque del auditor](./arranque-auditor-v2-88-17-1-w4-2026-10-01.md)). Ese paquete auditaba el trozo **`v2.88.4`…`v2.88.17.1`**; desde entonces se han sellado **dos** versiones más.
> **Objeto vigente:** tag anotado **`v2.88.19-beta`** → commit **`c712f2a5`** · package **`2.11.19-beta`** · Alembic head **`046_fill_reference_mid`** (sin migración) · `main` → **`5c75ce07`** (commit de cita POST-TAG).

---

## 1. El delta: dos versiones

| Versión | Clase | Qué trae | Evidencia |
|---|---|---|---|
| **`v2.88.18-beta`** (`ed1affd3`) | **CI/tests** (`Δ src = 0` de producto) | Compuerta **`G2`** (`OBS-19`): los tests que **ningún job ejecutaba** bajan de **205 a 53** ficheros — **152 herméticos cableados** por **pase de directorio**, **40 `--ignore` justificados**, **53 declarados con motivo y tanda**; instrumento **`scripts/ci/test_selection.py`** (el censo se **deriva** de los workflows) + línea base + guarda de censo | [`evidence/v2.88.18/README.md`](./evidence/v2.88.18/README.md) |
| **`v2.88.19-beta`** (`c712f2a5`) | **producto** (`Δ src ≠ 0`) | **`OBS-21`**: dos defectos cazados por la certificación concurrente — (A) la **matrícula del tick** deja de poder reventar (`UniqueViolation` del **PK**), (B) la **ventana de gracia** deja de envejecer una reserva recién nacida (retirada `cancel` **falsa** sobre un fill parcial) | [`evidence/v2.88.19/README.md`](./evidence/v2.88.19/README.md) · [informe](./obs-21-matricula-tick-y-ventana-de-gracia-v2.88.19-2026-10-01.md) |

**Rojo citado que NO se borra:** el tag **`v2.88.18-beta`** quedó público con **`lifecycle-pg` rojo** — `Release tag CI` run [`36886166182`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36886166182), **11 de 12** jobs verdes (`python` y `replay-repro` incluidos) y **una** prueba caída: `test_concurrent_auto_n_sessions_claim_one_signal_pg[5]` (`apps/api-python/tests/test_concurrent_auto_pg.py:346`, `AssertionError: la retirada debe DECLARAR que había cola de fill parcial: motivo='cancel' status='RELEASED_BY_CANCEL'`). **`v2.88.19-beta` lo supersede.**

**Verde vigente:** `Release tag CI` run [`36895471323`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36895471323) → **`SUCCESS`**: **11 jobs `success`** + `playwright (integrated E2E, opt-in)` `skipped` por diseño, **`certify` `success`**.

---

## 2. Las afirmaciones falsables de este delta (lo que hay que intentar romper)

Cada una se puede comprobar **desde el clon público**, sin credenciales.

### 2.1 Encaje de cuentas del job offline (el sello **no** esconde tests)

| Run | Job `python` |
|---|---|
| Rojo de `v2.88.18-beta` (`36886166182`) | **`4157 passed, 42 skipped`** |
| Tag `v2.88.19-beta` (`36895471323`) | **`4158 passed, 42 skipped`** |

⇒ **+1** = **exactamente** la guarda hermética nueva (`test_reservation_grace_window_sums_the_stamp_resolution`), con los **mismos `42` skips** (ningún `skip` se movió). Y prueba **de paso** que esa guarda **sí corre** en el job offline: **no** es de la clase `OBS-19`.
**Cómo romperlo:** cuente los tests del fichero y compárelo con el delta; o intente encontrar un test del sello que **no** aparezca en ninguna lista de workflow (el instrumento `scripts/ci/test_selection.py` existe precisamente para que eso se pueda hacer sin leer YAML a ojo).

### 2.2 El job que dio el rojo es el que certifica

`lifecycle-pg` corrió **verde** en el tag `v2.88.19-beta` **con** los gates `*_PG_REQUIRED: 1` (incl. **`AUTO_CONCURRENT_PG_REQUIRED`** y **`AUTO_V2_DURABLE_PG_REQUIRED`**) ⇒ el fichero de concurrencia corrió **de verdad**. En el tag rojo, ese job corrió **el mismo comando** y falló.
**Cómo romperlo:** compruebe en el log del run verde que el step de concurrencia **no** figura como `skipped` y que el gate `*_PG_REQUIRED` estaba en `1`.

### 2.3 Los dos arreglos son INERTES para el instrumento OOS

El sello toca `packages/py/application` (**`Δ src ≠ 0`**) y aun así `replay-repro` dio **`REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)`**: render **LF** `3 340 728` B / `1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7`, **2ª corrida IDÉNTICA**, artefacto `11178993346`.
**Cómo romperlo:** parta del fixture congelado y regenere con el script del sello; el par CRLF sellado es `3 445 622` B / `240662250347A2AAD0F8E9F0101185D8ACC80C1D4BD1B4BBFF02D4766D9F54F0`.

### 2.4 Los arreglos están en el código, no sólo en el relato

- **`record_tick`**: `.on_conflict_do_nothing()` **sin árbitro** + `.returning(AutoEngineTickRow.tick_id)` + `if inserted.scalar_one_or_none() is None:` — y **no** queda ningún `rowcount == 0` ni ningún `constraint=` en ese camino.
- **`reservation_grace_window`**: suma `V2_RESERVATION_GRACE_STAMP_RESOLUTION` (`timedelta(seconds=1)`); si alguien lo quita, la guarda hermética **debe** caer.
**Cómo romperlo:** aplique cada mutación y corra su guarda. El repo declara el resultado esperado en la evidencia (§5 de `evidence/v2.88.19`).

### 2.5 La declaración de lo que **NO** se cierra

`OBS-14.b` (**alcance** del barrido de arranque), `OBS-19`/`G2` (**53** ficheros declarados sin correr en ningún job) y `P3-2`/`P3-3` (ventana PAPER real: ≥4 días / ≥32 ciclos / A-B real) siguen **ABIERTAS** — declaradas en `evidence/v2.88.19` §7, en el `CHANGELOG` y en el informe. El sello **no** las toca.
**Cómo romperlo:** si encuentra un documento del sello que insinúe lo contrario, es un hallazgo **suyo** que nos interesa.

---

## 3. Trampas declaradas (para no leer mal el artefacto)

1. **`mypy` sin argumentos no es el gate.** El gate de CI es la lista de rutas de `python-ci.yml`/`release-tag-ci.yml` (`packages/py/{domain,market,infrastructure,application}/src apps/api-python/src --follow-imports=silent`) → `no issues found in **512** source files`. Un `uv run mypy` **desnudo** recorre también tests y scripts y devuelve **2 690** errores **preexistentes**, ajenos a este sello.
2. **La cita del CI es POST-TAG** (patrón `OBS-3`/`OBS-4`): el tag `v2.88.19-beta` **no** contiene el run que lo certifica (vive en `main`, commit `5c75ce07`). Dentro del tag, el documento lo declara como pendiente **a propósito**.
3. **El tag `v2.88.18-beta` es un rojo citado**, no un error de publicación: se conserva a propósito (el repo nunca borra un tag rojo).
4. **`replay-repro` acepta dos renders** (CRLF del sello / LF del runner) y **declara cuál ha visto**; un fichero manipulado sigue dando `NO reproducido`. La autoridad para el `Δ = 0` es el par **sellado**, no un render local de Windows.
5. **Los artefactos de `operability_runs/` no viajan** (gitignored): se declaran con SHA-256 y se **regeneran**; el fixture congelado es lo que viaja.

---

## 4. Prompt listo para pegar (auditor externo)

```text
Repo: https://github.com/jvelasca/Bolsa_V1 (público; clona sin credenciales).
Objeto a auditar: tag anotado v2.88.19-beta (commit c712f2a5), package 2.11.19-beta,
Alembic head 046_fill_reference_mid. main va por 5c75ce07 (commit de cita POST-TAG).

Contexto: el paquete de auditoría de v2.88.4..v2.88.17.1 está en
docs/engineering/entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md (+ audit-pack +
arranque del auditor). ESTE encargo es el DELTA: v2.88.18-beta (compuerta G2/OBS-19) y
v2.88.19-beta (OBS-21). Empieza por docs/engineering/addendum-auditoria-externa-v2.88.18-v2.88.19-2026-10-01.md
y sigue por docs/CURRENT_SYSTEM.md (AsOf V2.88.19) y docs/engineering/PROJECT_STATE.md.

Verifica, con comando y cita, al menos:
1. El encaje de cuentas: python del run 36886166182 (4157/42) vs run 36895471323 (4158/42)
   => +1 = la guarda nueva, mismos 42 skips, y la guarda NO está en la clase OBS-19.
2. Que el job lifecycle-pg del tag v2.88.19-beta corrió de verdad (gates *_PG_REQUIRED: 1,
   el step de concurrencia NO skipped) y que el rojo del v2.88.18-beta era la MISMA prueba.
3. Los dos arreglos en el código: (a) record_tick con on_conflict_do_nothing() SIN árbitro y
   omisión leída por RETURNING (sin rowcount==0); (b) reservation_grace_window sumando
   V2_RESERVATION_GRACE_STAMP_RESOLUTION. Muta cada uno y comprueba que su guarda muere.
4. Que replay-repro sigue REPRODUCIDO pese al Δ src en packages/py/application.
5. La declaración de lo NO cerrado: OBS-14.b, OBS-19/G2 (53 ficheros), P3-2/P3-3.

Reglas: ninguna cifra sin comando; un hueco se declara NO MEDIDO; jamás un 0 fingido.
Entregable: veredicto + bloqueantes con reproducción + observaciones por severidad + lo NO MEDIDO.
```

---

## 5. Después de la auditoría: probar la operativa en la APP

La auditoría responde *«¿el artefacto dice la verdad?»*; **no** responde *«¿qué hace la operativa durante días?»*. Eso es la prueba en la APP, y es lo único que acredita `P3-2`/`P3-3`.

- **Estado de partida (declarado, no supuesto):** camino AUTO operativo en **PAPER**; `LIVE_EXECUTION_UNLOCKED` **default off**; `AUTO_ENGINE_SIM_REAL_PRICE` **default OFF** (con él OFF el motor usa el script de precio plano — el interruptor y su efecto están en [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md), sección de estado vigente, junto con **las rutas de la APP** y la tabla `W1`…`W4.1`).
- **Lo que hay que dejar registrado** (es lo que acredita, y lo que hoy está **NO MEDIDO**): días de operación, ciclos por día, fills/órdenes, reservas retiradas por motivo, y el par A/B real con una cuenta/versión/watch y `pairActive=false`.
- **Lo que la APP debe demostrar honestamente mientras tanto** (y que los arreglos de `OBS-21` hacen posible): que una retirada **declara su causa real** (`cancel` sólo cuando **no** se materializó), que la procedencia de lo liberado es **medible**, y que la operativa no acumula residuos ni duplica matrículas de tick.

> **Regla de la casa:** ninguna cifra sin comando, un hueco se declara **NO MEDIDO**, y jamás un `0` fingido.
