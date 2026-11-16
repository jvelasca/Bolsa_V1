# Verificación de ADR-050 — remedición, atribución de fallos y checklist de sello

**Fecha:** 2026-11-14 · **Árbol:** `main` = `ca0dcfe9` + ADR-050 sin commitear · **Versión de trabajo:**
`2.11.193-beta` · **Alembic head:** `068_strategy_verifications` · **Naturaleza:** remedición de la
validación global y atribución de los fallos de la suite. No cambia código de producto, no toca la
migración `067`, no amplía la allowlist de drift, no relaja umbrales ni `retries`/`timeout`.

**Dictamen.** PASS de **implementación focalizada**. Validación global **parcialmente satisfactoria**:
los fallos que quedan son **preexistentes y ajenos a ADR-050**, con causa raíz identificada y
reproducida en un baseline sin ADR-050. **Sin sello de release.** La verificación **no** demuestra
rentabilidad y `activationAllowed = false` sigue efectivo.

---

## 1 · Qué se ha hecho que no estaba hecho

La validación previa dejó **9 fallos** atribuidos a problemas preexistentes o a contención de la BD,
sin comparación contra una base. Este expediente añade lo que faltaba para que esa atribución sea
evidencia y no declaración:

1. **Remedición completa** del mismo comando, con hora de inicio y fin.
2. **Baseline aislado** en un worktree limpio sobre `ca0dcfe9`, con verificación de que los imports
   resuelven al worktree y no al árbol de trabajo.
3. **Base de datos desechable** para que el baseline pudiera ejecutar los nodos PG (la BD compartida
   está sellada en `068` y el baseline solo conoce `067`).
4. **Causa raíz por nodo**, no solo «preexistente»: commit, línea y valor medido.
5. **Corrección expresa del recuento**: el «9» estaba caducado.

---

## 2 · Niveles de prueba (remedidos)

| Nivel | Comando | Resultado | Dictamen |
| --- | --- | --- | --- |
| Suite Python completa | `python -m pytest packages/py/application/tests apps/api-python/tests -q` | **6 failed, 5306 passed, 7 skipped** (ver §2.1) | Parcial |
| Batería focalizada ADR-050 (8 ficheros) | los 8 de §11 del [método](./verificacion-periodica-estrategia-2026-11-14.md) | **87 passed** (4,79 s) | PASS |
| Guards de exclusividad, config del paquete | `pytest apps/api-python/tests/chaos/live_a7/test_exclusivity_guard.py -c apps/api-python/pyproject.toml` | **12 passed** | PASS |
| Scheduler, nodo aislado | `test_event_loop_starters_reunen_todos_los_workers_periodicos` | **1 passed** | PASS |
| Guardián de bump | `test_dia_d_bump_guard.py` | **3 passed** | PASS |
| `ruff` (ficheros ADR-050) | `ruff check --config pyproject.toml …` | **All checks passed** | PASS |
| Contrato | `pnpm --filter @bolsa/web contract:check` | **OK** | PASS |
| Alembic | `alembic_head()` | **`068_strategy_verifications`** | PASS |
| Web (392 ficheros / 2.938 tests) | no re-ejecutado en esta sesión | medido en la validación previa | Válido: sin cambios en `apps/web` además de los de ADR-050 ya medidos |
| `typecheck` 4/4 | no re-ejecutado en esta sesión | medido en la validación previa | Válido por la misma razón |

**Corrección del recuento.** La corrida de referencia dio **9 failed, 5303 passed, 7 skipped** a las
19:14. `apps/api-python/tests/test_scheduler_worker.py` se editó a las **20:16** — después de esa
corrida — para incluir `start_strategy_verification_scheduler` en el conjunto de starters esperado.
La remedición dio **8 failed y 5304 passed**: el noveno era el único fallo atribuible a ADR-050 y ya
estaba corregido cuando se midió. Tras cerrar §5, la corrida final da **6 failed y 5306 passed**.
**El «9» no debe citarse como estado actual.**

### 2.1 Secuencia de corridas y por qué el último recuento es 6

| Corrida | Inicio → fin | Resultado | Cambio entre corridas |
| --- | --- | --- | --- |
| Referencia | 2026-11-14 19:01 → 19:14 | 9 failed, 5303 passed | — |
| Remedición 1 | 2026-11-14 20:53 → 21:04 (658,65 s) | **8 failed, 5304 passed** | el scheduler ya estaba corregido |
| Remedición 2 | 2026-11-15 00:47 → 09:59 | **6 failed, 5306 passed** | §5 cerrado (+3), §3.1 nuevo (−1) |

**Sobre el tiempo de la corrida 2.** Reporta `33141,87 s` de reloj, pero el equipo estuvo suspendido
durante la noche: **no es tiempo de cómputo** y no debe citarse como tal. La cifra comparable es la de
la corrida 1 (658,65 s). El recuento de pruebas sí es válido.


---

## 3 · Los fallos, uno por uno

Estado **después** de cerrar §5 (corrida 2: 6 failed). Se conserva la columna de baseline como
evidencia de la atribución.

| Nodo | Causa raíz medida | Atribución | Baseline (sin ADR-050) |
| --- | --- | --- | --- |
| `chaos/live_a7/test_exclusivity_guard.py::test_a_foreign_fresh_claim_is_reported_as_contention` | `async def functions are not natively supported`: la invocación resuelve rootdir a la raíz, cuyo `pyproject.toml` declara `[tool.pytest.ini_options]` **sin** `asyncio_mode`; las tres pruebas async no llevan marcador | **Invocación/configuración.** No es producto | **3 failed, 9 passed** con config raíz y **12 passed** con config del paquete |
| `…::test_this_suite_workers_do_not_count_as_contention` | idem | idem | idem |
| `…::test_an_unreadable_claim_query_is_not_turned_into_a_skip` | idem | idem | idem |
| `test_database_maintenance_pg.py::test_report_reads_the_real_catalog` | `report.schema.status = 'warning'` por el drift de §4 | **Estado de la BD local compartida** | **pass** en BD desechable migrada solo por alembic |
| `test_schema_drift_gate_pg.py::test_metadata_and_database_are_in_sync` | índice único en BD donde `Base.metadata` declara `UniqueConstraint` de §4 | **Estado de la BD local compartida** | **pass** en BD desechable migrada solo por alembic |
| `test_auto_identity_chain_battery_pg.py::test_identity_chain_battery_complete_end_to_end_pg` | §3.1: residuo sub-céntimo en el P&L del ciclo | **ESTRUCTURAL: cuantización por fill** — **resuelto por el contrato A1** (ADR-051) sin relajar la igualdad | no reproducido en baseline (ver §3.1) |
| `test_lifecycle_golden_v191.py::…` · `v195` · `v196` | `stale_price`: precio confirmado a ±5 % con banda 0,02 | **Preexistente, introducido por #116** — **CERRADO en §5** | **failed idéntico** |

**Ninguno es atribuible a ADR-050.** Evidencia estructural adicional: el diff del árbol de trabajo
**no toca** `packages/py/application/src/bolsa_application/confirm/` ni la ruta de confirmación, y la
`068` solo añade `strategy_verification_runs` (tabla nueva, sin relación con `instrument_daily_opinions`
ni con la revalidación de precio).

### 3.1 El fallo de la batería de identidad es ESTRUCTURAL: cuantización por fill

```
E  AssertionError: el P&L del ciclo debe cuadrar EXACTO con el libro aplicado:
   ciclo=-29.248900720000 libro=-29.248900
E  assert Decimal('-29.248901') == Decimal('-29.248900')
```

- Falla **determinista** en aislamiento (dos ejecuciones seguidas, 2,20 s y 2,16 s), y **pasó** en las
  corridas del 2026-11-14: **no es contención**.
- **Causa raíz (medida el 2026-11-15).** El libro aplicado mueve `round6(q × p)` **fill a fill**
  (todas las columnas monetarias son `NUMERIC(18, 6)`); el ciclo FIFO suma exacto y solo se
  cuantiza al publicar. Con el libro plano, `libro − ciclo = Σ signo · (round6(q·p) − q·p)`:
  los `0,00000072` medidos son **dos** residuos de venta (`+0,00000044` y `+0,00000028`) sobre un
  ciclo de 6 fills. No hay fuga, ni pérdida de acumulación, ni reparto culpable: el quantum se
  aplica en puntos distintos. Detalle, tabla por fill y salidas posibles:
  [diagnóstico del residuo sub-céntimo](./diagnostico-residuo-subcentimo-2026-11-15.md).
- **Por qué parecía «de fecha».** El arnés importa `_filling_instrument_id` de
  `test_golden_day_v2_process_pg.py`, cuyo docstring declara «mismo id en cada ejecución del mismo
  día»: la fecha selecciona el instrumento, el instrumento fija el troceado y el troceado decide
  **si** algún producto tiene un séptimo decimal. La fecha es la **condición de visibilidad**, no
  la causa: con productos exactos a 6 dp el hueco es 0 y el nodo pasaría sin cambiar nada.
- **La conciliación del producto no lo detecta por construcción.** `pnl_reconciliation` compara
  `CYCLE_CLOSED.pnl` contra `SETTLEMENT.pnl` —dos derivados del MISMO FIFO— y cuantiza el total,
  así que da `reconciled = True` mientras el libro discrepa. Y el `SETTLEMENT` publica el dinero
  como `float` (`_number()` en `auto_operational_audit`), que no es el tipo del dinero.
- **No atribuible a ADR-050 ni a los golden re-anclados**: este fichero no importa
  `opening_gate_seed` ni los golden de ciclo de vida, y el cambio de §5 solo altera literales
  numéricos en `test_lifecycle_golden_v191/v195/v196`.
- **Contrato DECIDIDO e IMPLEMENTADO el 2026-11-15**: A1 — `pnl` publicado = `Σ signo ·
  round6(q·p)` con `ROUND_HALF_UP`; FIFO exacto conservado como `pnlExact`; `pnlPolicy` en el
  hecho de settlement y en la clave de deduplicación; reemisión histórica con identidad nueva.
  Ver [ADR-051](../adr/051-dinero-del-ciclo-cuantizacion-por-fill.md) y el
  [expediente del contrato](./contrato-dinero-ciclo-2026-11-15.md). El nodo rojo pasa por
  contrato —`libro − pnl = 0`— y el residuo se sigue midiendo contra `pnlExact`.
- **Sin migración, sin sello y sin tag**: `pnlPolicy` vive en el JSONB del payload; `AUTO` sigue
  OFF. Los dos defectos colaterales (conciliación de la misma autoridad y transporte `float`)
  quedan declarados con su propio contrato, no absorbidos.


---

## 4 · El drift de esquema es de la BD local, no del repositorio

**Hecho medido en la BD compartida** (`instrument_daily_opinions`):

```
[constraints] …_instrument_id_fkey (f), …_idempotency_key_key (u), …_pkey (p)
              ← NO existe constraint única para (instrument_id, as_of_bar_date, source, account_id)
[indices]     …_instrument_asof_source_account_key  ← UNIQUE INDEX, sin constraint que lo respalde
[alembic_version] 068_strategy_verifications
```

**Hecho medido en una BD recién creada y migrada solo por alembic** (`bolsa_v1_adr050_scratch`, head `068`):

```
[constraints] …_instrument_asof_source_account_key (u)   ← SÍ existe la constraint única
[drift gate]  1 passed
```

Es decir: **lo que producen las migraciones cumple el contrato; la BD de desarrollo local no.** La
propia migración `041` ya documenta esta asimetría en su `downgrade`
([`041_unique_natural_keys.py`](../../packages/py/infrastructure/alembic/versions/041_unique_natural_keys.py)):
el baseline `003` construye las tablas desde `Base.metadata` y deja esos 8 nombres como **constraint**
en una BD recién migrada, mientras que una **BD antigua** (previa al fix del modelo) los tiene como
**índice plano**; `041` y `067` detectan el objeto existente y lo omiten, así que el estado antiguo
persiste. La reparación es **de la base local** (recrear o reparar el objeto), nunca ampliar la
allowlist ni tocar `067` para que el rojo desaparezca.

Mismo hecho explica el fallo de mantenimiento: el informe declara `warning` porque mide ese drift.

**Nota de método.** El primer intento de baseline contra la BD compartida falló con
`alembic.util.exc.CommandError: Can't locate revision identified by '068_strategy_verifications'`: el
árbol baseline solo conoce `067`. Por eso se usó una BD desechable migrada por el propio baseline. Los
nodos PG que dependen del estado de la BD compartida se acreditan con esa BD **y** con la sonda de
catálogo de arriba, no por comparación directa.

---

## 5 · Los golden de ciclo de vida están rojos desde #116 (hallazgo nuevo)

**Causa raíz, no hipótesis.**

- `price_revalidation_reason` se conectó al caso de uso de confirmación el **2026-11-13**, en
  `153aba34` (`feat(market): dictamen medido por cuenta y rediseno S2-S5 de mercado, asesor y decision (#116)`),
  que añadió además la rama fail-closed `price_unmeasured`.
- La banda sigue en `0.02` desde `c8d58000` (v1.13); no ha cambiado.
- El fixture `apps/api-python/tests/opening_gate_seed.py` siembra **120 barras planas a 10,0**, y
  `test_lifecycle_golden_v191.py:206` comenta «Prices aligned with opening_gate_seed flat bars @ 10.0
  (±2 %)» mientras usa `target1 = 10.5` y `structuralStop = 9.5`, que están a **±5 %**.
- Sonda directa en la revalidación durante la corrida:
  `[PROBE] suggested_price=10.5 last_close=10.0` ⇒ `5 % > 2 %` ⇒ `stale_price`, determinista.

**Reproducido sin ADR-050.** En el worktree limpio en `ca0dcfe9`, con base desechable migrada por el
propio baseline (head `067`), los tres golden fallan con **el mismo** `stale_price` y el mismo
instrumento sintético (`inst-g191-*`, barras a 10,0).

**Por qué no se vio antes.** `python-ci.yml` los excluye explícitamente (`--ignore` en las líneas 446–448).
El único sitio que los ejecuta es el step de `lifecycle-pg` de `release-tag-ci.yml` (líneas 1653–1655),
y los dos últimos `Release tag CI` son **anteriores** a #116: en
[run `42983709708`](https://github.com/jvelasca/Bolsa_V1/actions/runs/42983709708) (2026-11-11) ese step
dio **231 passed**, y en el último, [run `43169810570`](https://github.com/jvelasca/Bolsa_V1/actions/runs/43169810570)
(2026-11-12), el rojo fue del job `shared`, no de `lifecycle-pg`. La rotura introducida **entre tags** es
**invisible** hasta el siguiente tag. Ese es el hueco de certificación, y es de proceso, no de ADR-050.

**Consecuencia para el sello.** El próximo `Release tag CI` pondría `lifecycle-pg` en rojo por estos tres
nodos. Era un **bloqueante de sello abierto**, ajeno a ADR-050.

### 5.1 Cómo se cerró (2026-11-15)

Decisión del propietario: **re-anclar los precios del fixture dentro de la banda**, en este mismo árbol.
La banda se aplica a **apertura y cierre**, y la geometría ±5 % no cabe en ninguna de las dos, así que
se comprimió el escenario completo en vez de tocar el motor o la banda:

| Campo | Antes | Ahora | Desvío sobre 10,0 |
| --- | --- | --- | --- |
| `structuralStop` / `signedStop` | 9,5 | **9,82** | 1,80 % |
| `target1` / reduce T1 | 10,5 | **10,12** | 1,20 % |
| `target2` / reduce T2 (`v196`) | 11,0 | **10,19** | 1,90 % |
| `exit_hint` | 10,8 (`v191`/`v195`), 11,2 (`v196`) | **10,16** | 1,60 % |
| `riskAmount` | 5,0 | **1,8** | derivado de `(10,0 − 9,82) × 10` |

Se mantiene la **semántica de cada golden** (el stop sigue por debajo de la entrada y T1 < T2, con el
`riskAmount` coherente con la distancia al stop), y cada fichero lleva un comentario que explica la
banda y por qué un precio a ±5 % se rechaza con `stale_price` antes de llegar al gate certificado.
`v196` es el caso estricto: **T2 también es un precio confirmado** (`_reduce_rec(price=…)`), por eso
sube a 10,19 y no a 10,39.

**Medido:** los tres ficheros **`3 passed` en 34,55 s**, y `ruff check` **`All checks passed!`**. No se
tocó `PRICE_REVALIDATION_MAX_REL_DEVIATION`, ni `opening_gate_seed` (lo comparten 8 ficheros de
integración), ni la semántica del producto.

**Lo que este cierre NO demuestra.** Que los precios del golden sean realistas: son un escenario
sintético plano a 10,0. El golden certifica el ciclo de vida y la integridad del enlace, no un
resultado de mercado. `ruff format` no se exige en CI y estos ficheros ya estaban sin formatear en
`ca0dcfe9`; no se reformatearon para no mezclar ruido en el diff.

---

## 6 · Fronteras que este expediente mantiene

1. **`chaos/live_a7` verde en aislamiento no acredita convivencia.** Con `-c apps/api-python/pyproject.toml`
   son 12 passed; el verde de la batería completa es el job `a7-gate` con BD dedicada, y la convivencia
   con el stack vivo sobre la BD compartida no queda certificada aquí.
2. **Un fallo preexistente no se convierte en verde por declararlo.** Los seis siguen rojos salvo §5, que
   se cerró re-anclando el escenario del golden —no relajando la banda—; el expediente explica cada uno
   y no los maquilla.
3. **Verificación ≠ rentabilidad.** ADR-050 es descriptivo. `insufficient_sample` sigue siendo el veredicto
   con la muestra actual.
4. **`AUTO` sigue OFF.** `activationAllowed = false` es efectivo en perfil, veredicto y rutas HTTP. Nada
   de este expediente autoriza operar.
5. **No se ha tocado** la `067`, la allowlist de `schema_contract`, los umbrales del perfil, ni
   `retries`/`timeout` de ninguna suite.

---

## 7 · Checklist de sello — **no ejecutada**

Se documenta lo que falta. Ningún paso de esta lista se ha ejecutado en esta sesión.

| Paso | Estado | Nota |
| --- | --- | --- |
| Guardián de bump | **pasado** (3 passed) | `test_dia_d_bump_guard.py` |
| `contract:check` | **pasado** | `openapi.json` y `schema.d.ts` coinciden |
| `alembic heads` = `068_strategy_verifications` | **pasado** | |
| `pnpm window:pin` (re-anclaje) | **pendiente** | re-ancla `commit`/`appsHash`/`packagesHash` |
| `pnpm window:freeze` | **pendiente** | fail-closed; exige pin que case con el árbol del tag |
| CI de etiqueta: `shared`, `a7-gate`, `lifecycle-pg`, `replay-repro` | **pendiente** | `lifecycle-pg` ya no depende de §5, que está cerrado |
| Cerrar §5 (re-anclar los golden a la banda) | **hecho** (2026-11-15) | `3 passed`; sin tocar banda ni motor |
| Contrato del dinero del ciclo (ADR-051) | **implementado** (2026-11-15) | `libro − pnl = 0`; reemisión `v2_103` con dry-run/apply; **sin sello** |
| Tag anotado **unsigned** sobre el commit del pin | **pendiente** | |
| Cita POST-TAG del `Release tag CI` | **pendiente** | |

**Regla.** El sello se certifica con el CI de etiqueta, y ese CI incluye `lifecycle-pg`, que ejecuta los
tres golden de ciclo de vida. §5 está cerrado, así que ese bloqueante ya no aplica; quedan los pasos de
re-anclaje, tag y cita. El recuento de la suite (6 failed) se cita como está: el sello no exige verde
local, pero ningún fallo nuevo debe quedar sin atribución.

### 7.1 Dictamen de auditoría recibido (2026-11-15) — sin cambio de estado

Valoración externa sobre el informe de este expediente, recibida sin ejecución independiente:

| Objeto | Dictamen |
| --- | --- |
| ADR-050 | Implementación focalizada **satisfactoria** |
| Goldens `v191`/`v195`/`v196` | Bloqueante de sello **cerrado** (3/3 PASS) |
| Identidad/contabilidad | Defecto **reproducible**, pendiente de su mantenedor (§3.1) |
| Otros cinco fallos | Permanecen declarados, sin resolución |
| Documentación | Actualizada (este expediente y `CHANGELOG`) |
| Release | **No sellada**: sin `window:pin`, sin `window:freeze`, sin tag |

La auditoría mantiene el árbol **sin sellar** —no porque ADR-050 haya fallado, sino porque la suite
global presenta seis fallos y uno afecta a una aserción de consistencia contable— y descarta abrir una
corrección dentro de ADR-050 o relajar la igualdad exacta sin decisión explícita del responsable de la
cadena de identidad. Este expediente **no** ejecuta `window:pin` ni `window:freeze`: el checklist sigue
sin ejecutarse.

**Residuo sub-céntimo.** Diagnosticado el 2026-11-15 (causa raíz medida y descompuesta fill a
fill en [diagnóstico del residuo sub-céntimo](./diagnostico-residuo-subcentimo-2026-11-15.md)) y
**contratado e implementado** ese mismo día: A1 con `pnlPolicy`, identidad versionada y reemisión
histórica ([ADR-051](../adr/051-dinero-del-ciclo-cuantizacion-por-fill.md)). **La release sigue
NO sellada**: los pasos de §7 no se han ejecutado y este cambio no los ejecuta.

---

## 8 · Referencias

- [ADR-050](../adr/050-verificacion-periodica-estrategia.md)
- [Verificación periódica: método, límites y niveles de evidencia](./verificacion-periodica-estrategia-2026-11-14.md)
- [Verificación independiente del cierre de PR #128](./verificacion-independiente-cierre-pr-128-2026-11-14.md)
- [Cierre de auditoría del DÍA-D as-run](./cierre-auditoria-dia-d-as-run-2026-11-13.md) §5 (incidencia de invocación de `live_a7`)
- [Diagnóstico del residuo sub-céntimo](./diagnostico-residuo-subcentimo-2026-11-15.md) §2–§3 (§3.1 de este expediente)
- Código citado: [`confirm/identity.py`](../../packages/py/application/src/bolsa_application/confirm/identity.py) ·
  [`confirm/actions.py`](../../packages/py/application/src/bolsa_application/confirm/actions.py) ·
  [`opening_gate_seed.py`](../../apps/api-python/tests/opening_gate_seed.py) ·
  [`067_opinion_account_scope.py`](../../packages/py/infrastructure/alembic/versions/067_opinion_account_scope.py) ·
  [`068_strategy_verifications.py`](../../packages/py/infrastructure/alembic/versions/068_strategy_verifications.py)
