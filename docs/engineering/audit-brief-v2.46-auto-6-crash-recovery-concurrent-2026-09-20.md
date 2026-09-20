# Brief de auditoría — v2.46: AUTO-6 Crash/Recovery + Concurrent (`1.71.0-beta`) (2026-09-20)

> **Qué es este documento.** Una **guía de ataque** para el auditor externo, no un pack nuevo: el
> contrato y la matriz afirmación→código→test siguen viviendo en el
> [audit-pack](./audit-pack-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md). Aquí solo se ordena
> **qué atacar primero**, con `ruta:línea` **verificada en el árbol** y el **comando exacto** de cada
> medida. No sustituye al pack: lo precede. Si hay contradicción entre este brief y el pack, **manda el
> pack**.

> **Regla de este documento: es de solo lectura para el agente.** No se toca código de producción ni
> tests por él (regla de oro del §0 del
> [relevo de cierre de v2.43.2](./relevo-cierre-v2.43.2-matriz-mutaciones-y-sello-2026-09-20.md)). Un
> hallazgo que exija cambiar código **se declara en el hilo**, no se arregla dentro de la auditoría.

> **Aviso de la fase:** a diferencia de `v2.43.2`, esta fase **SÍ cambia una costura de producción**
> (el camino de reserva del worker). El blast radius es real, pequeño y localizado: §3.1–§3.3 es donde
> está el dinero.

---

## 1. Qué se audita y de dónde

| Dato                       | Valor                                                                                                   |
| -------------------------- | ------------------------------------------------------------------------------------------------------- |
| **Ref a auditar (código)** | commit de fase **`a14b71d7`** (`17` ficheros, `+2869/−25`)                                              |
| **Etiqueta**               | tag anotado **`v2.46-beta`** → **`5eb654b9`** (docs-only, el sello)                                     |
| **Evidencia de CI**        | `main`: `90b7ad4e` (evidencia) + `8cb32721` (arreglo de dos referencias del §9 del pack)                |
| **Base del diff**          | `460df421` (arranque de AUTO-6) → `a14b71d7`                                                            |
| **Versión de paquete**     | `1.71.0-beta` · **sin migración** (Alembic head sigue en `043_exit_identity_and_kill_state`)            |
| **Estado**                 | **SELLADO**; CI real medida en `main` y en la ref del tag (§9.1 y §9.2 del pack, con enlace a cada run) |

- **Punto de entrada:** [`audit-pack-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md`](./audit-pack-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md).
- **Después:** [`arranque-auditor-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md`](./arranque-auditor-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md).
- **Plan de fase** (sus §7.1 son las **desviaciones declaradas**):
  [`plan-v2-46-auto-6-crash-recovery-concurrent-2026-09-20.md`](./plan-v2-46-auto-6-crash-recovery-concurrent-2026-09-20.md).
- **Especificación:** §8 del [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md)
  (`AUTO-6` es **gate de certificación**: «si los dos escenarios no corren, la versión no se pone»).

**Freeze (congelado — tocarlo _es_ hallazgo):**

- `apps/api-python/scripts/v2_43_governor_evidence.py` **byte a byte igual** y `exit 0`, con su
  `"bump"` conservado en **`1.68.0-beta`** (deliberado, `v2.43.1` §8.2).
- **Sin migración** (head `043`): el claim atómico usa la **PK existente** de `portfolio_reservations`.
- **Los tags anteriores no se mueven**: `v2.43*`, `v2.44-beta`, `v2.45-beta` quedan donde están.
- **Byte-identidad con el flag OFF**: `AUTO_ENGINE_SIM_V2_OPTIMIZER=0` no debe cambiar por esta fase.

**Numeración.** «AUTO-6» es la **etiqueta del roadmap**; la **versión de paquete** es `1.71.0-beta`
(`V2.46`). Una referencia a «v2.46» en el código/docs es la etiqueta de la fase.

---

## 2. El gate tal como quedó (lo que el CI **SÍ** corrió)

| Escenario              | Paso dedicado en el tag                                                               | Resultado medido en el run del sello |
| ---------------------- | ------------------------------------------------------------------------------------- | ------------------------------------ |
| **Crash/Recovery Day** | `Pytest Crash/Recovery Day (proceso scheduler matado en sucio + PG, fail if skipped)` | **1 passed in 9,44 s**               |
| **Concurrent AUTO**    | `Pytest Concurrent AUTO (3 sesiones concurrentes + PG, fail if skipped)`              | **1 passed in 1,64 s**               |
| Guard (ambos)          | `Fail on skipped … (no skip silencioso)`                                              | **success**                          |

Run del tag: [`35535111995`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35535111995) (8m5s,
`certify` en `success`). Cableado verificado en el árbol:

- `lifecycle-pg` del tag: gates en `env:` del job (`.github/workflows/release-tag-ci.yml:531-532`),
  paso del crash `:695` + guard `:702`, paso del concurrente `:718` + guard `:725`.
- Los dos gemelos PG al `--ignore` de **ambos** jobs offline
  (`.github/workflows/python-ci.yml:225-226` y `.github/workflows/release-tag-ci.yml:444-445`): sin
  ese `--ignore` **skipean en mudo** y el verde sería fantasma.

---

## 3. P0 — atacar primero

### 3.1 P0-1 · Claim atómico de la reserva (la costura de producción nueva)

**Afirmación:** dos workers/procesos que evalúan la **misma señal de la misma barra** para la **misma
cuenta** derivan la **misma** identidad de decisión y, por tanto, la **misma** reserva; la PK de
`portfolio_reservations` arbitra la carrera **sin locks extra**, y el que pierde **veta su emisión**.

**Código:**

- `packages/py/application/src/bolsa_application/auto_v2_entry.py:1447` (`entry_decision_id`), con el
  cuerpo en `:1462-1468`: `signal_id` vacío ⇒ identidad **aleatoria** histórica (`dec-<uuid4 hex12>`);
  con `signal_id` ⇒ `dec-<sha256("cuenta␟signal_id")[:12]>`.
- `packages/py/application/src/bolsa_application/reservation_store.py:100` (protocolo `save_claim`),
  `:346` (`InMemory`), `:454` (`Postgres`: `INSERT … ON CONFLICT DO NOTHING … RETURNING` en `:474-483`
  y `UPDATE` **condicional** con `RETURNING` en `:484-496`).
- `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:2106`
  (`_v2_persist_tick_reservations`), consumo en `:2144` (`claimed_ok = await store.save_claim(...)`) y
  veto del perdedor en `:2155-2165` (motivo ya existente `reservation_already_live`).

```474:496:packages/py/application/src/bolsa_application/reservation_store.py
        insert_statement = (
            pg_insert(PortfolioReservationRow)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["reservation_id"])
            .returning(PortfolioReservationRow.reservation_id)
        )
        claimed = (await self._session.execute(insert_statement)).scalars().first() is not None
        if not claimed:
            taken_over = await self._session.execute(
                sa.update(PortfolioReservationRow)
                .where(
                    PortfolioReservationRow.reservation_id == reservation.reservation_id,
                    sa.or_(
                        PortfolioReservationRow.status != RESERVATION_OPEN,
                        PortfolioReservationRow.remaining_qty <= 0,
                    ),
                )
                .values(**{name: values[name] for name in _WRITABLE_COLUMNS})
                .returning(PortfolioReservationRow.reservation_id)
            )
            claimed = taken_over.scalars().first() is not None
```

**Cómo se falsifica:** mutación **M5** (identidad aleatoria en `entry_decision_id`) ⇒ debe poner en
rojo **2** tests herméticos; mutación **M6** (`if False:` en el veto del perdedor) ⇒ **1** rojo. Sonda
medida: `apps/api-python/scripts/v2_46_mutation_audit.py` (lista `MUTATIONS` en `:66`), **6/6 muerden**
con la huella `sha256` del árbol intacta. Comando en §7.

**Dónde se mide:**

- `apps/api-python/tests/test_auto_v46_concurrent.py:233`
  (`test_concurrent_auto_three_workers_claim_one_signal_one_order`) — una sola orden, un solo worker
  abre, y **cada perdedor declara motivo** (nunca veto silencioso): `:245`, `:249`, `:258`, `:268-274`,
  `:279-283`.
- `apps/api-python/tests/test_auto_v46_concurrent.py:287`
  (`test_concurrent_auto_second_wave_adds_nothing`) — **segunda oleada** que no añade ni una orden.
- `apps/api-python/tests/test_concurrent_auto_pg.py:236` — el gemelo PG: **1 INTENT** entre 3 sesiones
  (`:276-279`), **una** instancia abre (`:282-288`), perdedores con motivo tipificado (`:292-303`).

> **El interleaving hermético es real, no decorativo.** El test envuelve los stores en `_YieldingStore`
> (`test_auto_v46_concurrent.py:102`) para que los `await` **cedan el control**, y corre los turnos con
> `asyncio.gather` (`:209`). Atacarlo: **¿algún camino del tick puede completarse sin suspender** (⇒ la
> carrera sería serial de facto y el test no probaría nada)? Nota honesta del propio fichero (`:11`).

### 3.2 P0-2 · El defecto semántico que se destapó (y su fix): `save` vs `save_claim`

**Afirmación:** `save` responde «¿la fila existía?» (idempotencia de **replay**); `save_claim` responde
«¿soy el dueño del compromiso **vivo**?». Leer `save` como claim vetaba **para siempre** la re-entrada
sobre una identidad ya **liberada**.

**Código:** los tres `save_claim` (`reservation_store.py:100`, `:346`, `:454`) frente a los `save`
(protocolo e implementaciones, mismo fichero); el consumidor cambió en
`auto_simulation_worker.py:2144`.

**Cómo se falsifica (el ángulo bueno):** la `UPDATE` condicional
(`status != OPEN OR remaining_qty <= 0`) es lo que permite **re-comprometer** una identidad liberada.
Falsifica en **las dos direcciones**:

1. quitar el `OR remaining_qty <= 0` ⇒ ¿muere algún test? (¿o el caso «OPEN con `remaining_qty <= 0`»
   no está cubierto?);
2. quitar la condición entera (volver a un `UPDATE` ciego) ⇒ ¿algún test distingue «replay» de
   «re-clamo»?

**Pregunta afilada (§5.2).** `_WRITABLE_COLUMNS` reescribe la fila liberada y la devuelve a `OPEN`,
pero **no** consta un productor que emita el evento de la re-apertura. ¿Necesita el negocio que la
re-compromisión quede **auditada** (contador/motivo), o es aceptable que sea invisible salvo por el
estado de la fila?

### 3.3 P0-3 · Crash sin doble efecto (dedupe durable + reconciliación)

**Afirmación:** la RAM se pierde de verdad, el reinicio **reconstruye** y converge: nada duplicado,
nada perdido.

**Código:**

- `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:753` (`readopt_positions`),
  `:2405` (`_v2_reconcile_reservations(startup=True)`), `:2674` (`_v2_mark_signal_consumed`),
  `:926` (`_openings_vetoed`).
- Dedupe de señal consumida: `packages/py/application/src/bolsa_application/auto_v2_entry.py:949`
  (`consumed = {str(x).strip() for x in consumed_signal_ids …}`).
- Idempotencia financiera: `packages/py/application/src/bolsa_application/execution_event.py:1068`
  (`apply_execution_financial_once`) con el atajo `row.status == "APPLIED"` en `:1104-1105` (y un
  segundo `already_applied` en `:1154`).

**Cómo se falsifica:** **M1** (`consumed = set()`) ⇒ **2** rojos; **M2** (`if False:` en la liberación
por fill) ⇒ **1** rojo; **M3** (lo divergente no veta aperturas) ⇒ **1** rojo; **M4** (el `APPLIED` no
se ataja) ⇒ **1** rojo.

**Dónde se mide:**

- `apps/api-python/tests/test_auto_v46_crash_recovery.py:264`
  (`test_crash_recovery_day_partial_fill_survives_kill_and_restart`) — worker **NUEVO** sobre los
  **mismos** espejos durables, reconciliación convergente, `POSITION == Σ APPLIED BUY − Σ APPLIED SELL`,
  sin doble efecto, libro plano, reservas vivas a 0.
- `apps/api-python/tests/test_auto_v46_crash_recovery.py:396`
  (`test_crash_recovery_releases_the_unfilled_tail_of_the_partial_reservation`) — aísla la **liberación
  de la cola NO llenada**.

---

## 4. La capa real del tag — qué certifica y qué **no**

`apps/api-python/tests/test_crash_recovery_day_process_pg.py:221`: proceso real
`python -m bolsa_api.workers.scheduler_worker` sobre PG real, **muerte sucia** (`proc.kill()` en `:182`
y `proc.terminate()` de reserva en `:186`), reinicio sobre la misma BD y cierre limpio por el **seam
durable** (`holdingDeadlineAt` vencido). El escenario es un **gate fail-if-skipped** con presupuestos
por fase y `_proc_failure` con diagnóstico (no un `assert` desnudo); invariantes en `:280` (`fills >
orders`), `:289` (cola viva), `:297` (al menos una trancha materializada), `:305` (techo vencido),
`:387` (**cero publicaciones al bridge LIVE**).

**Lo que NO prueba, declarado antes de que lo reportes como hallazgo:**

1. **Interrupción «en mitad del fill» no es observable en vivo**: el venue SIM aplica el **schedule
   completo** de una orden **dentro del mismo tick**, así que una muerte en vuelo es **imposible por
   construcción** del simulador. Lo que el test certifica es el **estado durable** del parcial (orden
   cortada con cola viva + reserva viva, producido por el propio proceso, **sin sembrar nada**) y su
   cierre contable tras la muerte.
2. **Muerte sucia = `terminate()` en Windows / `kill()` en POSIX.** El `SIGKILL` real es el del CI
   Linux; no se finge equivalencia.
3. **Tres sesiones, no tres procesos** en el gemelo concurrente (`test_concurrent_auto_pg.py:236`,
   tres `AutoSimRuntime` con `asyncio.gather` en `:271`): lo que se prueba es la **serialización por
   la base**, no el reparto de RAM entre procesos. Tres procesos reales quedaron como **plan B
   declarado** (plan §7.1 (d)).
4. **Identidad del instrumento elegida por barrida pura** (`_partial_fill_instrument_id`,
   `test_auto_v46_concurrent.py:79`; `_partial_buy_instrument_id`, `test_concurrent_auto_pg.py:105`;
   prefijos `inst-v46conc-` en el gemelo PG y `inst-v46crash-` en el crash) para garantizar BUY parcial
   con ≥2 tranchas y SELL completo: **no** hay sorteo, pero tampoco hay teorema; si el ruido del
   simulador cambiara, el helper dejaría de encontrar id y el test **fallaría con nombre**, no pasaría
   en falso (es el patrón que `v2.43.3` §4 dejó medido).

> **Pregunta §5.4 (afilar):** ¿la fase 2 del test PG podría pasar **sin** que el reinicio haya
> reconciliado nada (p. ej. si el proceso nuevo no readopta porque el estado durable ya era plano)? El
> test afirma `remaining_before > 0` **antes** del reinicio (`:357`), que es la guarda contra ese falso
> verde. Verifica que esa guarda es suficiente y no un consuelo.

---

## 5. Preguntas afiladas (donde yo no tengo respuesta, y lo digo)

### 5.1 ¿El claim atómico depende del **nivel de aislamiento**?

`save_claim` (`reservation_store.py:454`) confía en que, bajo dos `UPDATE` concurrentes a la **misma**
fila, el segundo reevalúe su `WHERE` y **no** devuelva `RETURNING`. Con `READ COMMITTED` (el default
del repo) eso es así; con `REPEATABLE READ`/`SERIALIZABLE` el perdedor **no** recibe «no casa» sino un
**error de serialización**. Decide: ¿es un supuesto declarable (default) o un hallazgo de robustez
(falta tratamiento del error)?

### 5.2 `dec-<sha256(...)[:12]>` ⇒ ¿48 bits basta?

Una **colisión** haría que dos señales **distintas** compartieran reserva. Analiza la **dirección** del
fallo antes de decidir severidad: la segunda recibiría `claimed_ok = False` y **vetaría su emisión**
(oportunidad perdida, fail-closed) — **no** un doble compromiso. Es sizing declarado, no un bug de
dinero; si crees que la dirección es la contraria, ese **sí** es P0. Y comprueba que `signal_id`
**incluye la barra** (se construye con `timeframe` + `moment` en `auto_simulation_worker.py:1729-1732`,
de donde sale `identity.signal_id`): si no la incluyera, una reserva antigua podría vetar la barra
nueva para siempre.

### 5.3 Sin identidad de señal, el camino vuelve a ser **la lotería**

`auto_v2_entry.py:1462-1466`: sin `signal_id` devuelve un `dec-<uuid4>` aleatorio ⇒ **no** hay claim
compartido y dos workers pueden volver a apilar dos compromisos sobre la misma oportunidad. Está
**declarado** (docstring) como «fail-open al azar de siempre». Decide si eso es aceptable hoy o si el
camino sin `signal_id` debería **vetar** en vez de sortear.

### 5.4 ¿Quién libera una reserva OPEN que nadie llenó?

`_v2_reconcile_reservations` corre **en el arranque** (`startup=True`). Dentro de un proceso **largo**,
una reserva `OPEN` con `remaining_qty > 0` bloquea la re-compromisión de la **misma** identidad. Como la
identidad incluye la barra, la barra siguiente no queda bloqueada — pero **verifica esa cadena
completa** (`signal_id` → `entry_decision_id` → `reservation_id`) por ti mismo y decide si el
comportamiento intra-barra es el que quieres (anti-churn) o una pérdida de oportunidad.

### 5.5 El `38 skipped` del CI frente al `0` del runner local

El job `quality` publica **2091 passed, 38 skipped** y el runner local por JUnit da
`{'tests': 2091, 'passed': 2091, 'skipped': 0}` para el **mismo** comando. Es la **misma divergencia
estable** de `v2.45-beta` (`2087/38` en CI vs `2087/0` local) y el pack **declara que no se le atribuye
causa medida**. Si crees que esos 38 pueden ocultar algo de esta fase, ese es un ángulo legítimo:
`gh run view --job <quality> --log | rg 'SKIPPED|skipped'`.

---

## 6. Qué NO es un hallazgo (declarado **antes** de que lo encuentres)

Confirmarlo es útil; reportarlo como hallazgo nuevo, no. Todo esto ya está en el pack (§7), el plan
(§7.1) y `PROJECT_STATE.md`:

- **La matriz de mutaciones ya está medida** (**6/6 muerden**, huella intacta). Un hallazgo sobre la
  **causa** de un verde sigue siendo válido; la matriz **no** es deuda pendiente.
- **La muerte en vuelo no se prueba** y **en Windows la muerte es `terminate()`**: declarado (§4.1/§4.2).
- **Tres sesiones, no tres procesos** en el gemelo concurrente: declarado (§4.3).
- **El cierre real es por seam durable** (`holdingDeadlineAt` vencido + reinicio), porque el precio del
  camino SIM es **plano** y el horizonte de la plantilla es de **21–90 días**: un día V2 no puede
  disparar T1/trailing/régimen dentro del presupuesto de un test. El cierre por **geometría** se
  certifica en la capa hermética.
- **El bucle AUTO SIM no escribe el journal durable**: los agregados post-crash se leen de
  `execution_events` / `sim_*` / `transactions`, **no** del journal (deuda declarada desde `AUTO-5`).
- **No hay productor de economía en el tick** (`p_win`/medias son de `AUTO-7`): el escenario concurrente
  **no** se apoya en el optimizador.
- **`v2_43_governor_evidence.py` conserva `"bump": "1.68.0-beta"`**: deliberado (`v2.43.1` §8.2).
- **El gobernador sigue con default OFF y umbrales sin calibrar**: deuda de la línea AUTO, intacta.
- **`main` va dos commits docs-only por delante del tag** (evidencia + arreglo de dos referencias
  colgantes del §9 del pack): el tag **no** se mueve; es el patrón de `v2.45-beta`.

---

## 7. Comandos listos (invocaciones **exactas** de CI)

```bash
# estático, tipos y fronteras (la invocación DE LA CASA; sin --config la medición es de otra cosa)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# el gobernador NO se movió: esto debe salir VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run --no-sync python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# los DOS escenarios herméticos (sin PG) — es lo que corre `quality` por pase de directorio
uv run pytest apps/api-python/tests/test_auto_v46_crash_recovery.py \
              apps/api-python/tests/test_auto_v46_concurrent.py -q

# los DOS escenarios reales (PG) — los pasos DEDICADOS del tag, con su gate fail-if-skipped
AUTO_CRASH_RECOVERY_PG_REQUIRED=1 AUTO_CONCURRENT_PG_REQUIRED=1 \
  uv run pytest apps/api-python/tests/test_crash_recovery_day_process_pg.py \
                apps/api-python/tests/test_concurrent_auto_pg.py -q -rs
# (NO corras dos sesiones de pytest en paralelo contra la misma base: el purgado de residuos del
#  conftest es de sesión y se borran los datos entre sí. El gate del tag usa pasos dedicados.)

# bloques offline de CI con el runner versionado (targets EXTRAÍDOS del YAML, medida por JUnit XML)
uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores

# reproducir la matriz de 6 mutaciones entera (debe dejar el árbol intacto y salir exit 0)
uv run --no-sync python apps/api-python/scripts/v2_46_mutation_audit.py

# el sello, verificado sin creerme
git show -s --format='%H %s' v2.46-beta
gh run view 35535111995 --log | rg 'Pytest (Crash/Recovery|Concurrent)|Fail on skipped (Crash|Concurrent)'
gh run view 35535111995 --log | rg '[0-9]+ passed'      # python offline 2102 y lifecycle 148 + 45
```

**Runner de CI:** usa `scripts/verify/offline_ci_run_yaml.py`, **no** una copia a mano de la lista.

---

## 8. Formato de un hallazgo

```
P0/P1/P2 · afirmación atacada · ruta:línea · comando exacto · salida observada · ¿el §7/§7.1 ya lo declara?
```

Si el hallazgo **ya está declarado** en el §7 del pack o el §7.1 del plan, cítalo y dilo como
**confirmación**; si **no** lo está, es un hallazgo nuevo y se responde en el hilo de auditoría del
repo (el hilo de `v2.43` vive en [issue #62](https://github.com/jvelasca/Bolsa_V1/issues/62)).
