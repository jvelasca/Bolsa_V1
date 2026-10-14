# Evidencia read-only de la cadena AUTO y la ventana PAPER (`v2.88.132-beta`) — 2026-10-14

> **Alcance:** evidencia de **OPERACIÓN** leída de la base durable mediante los instrumentos
> read-only ya existentes (`v2_99` y `v2_98`). **No** se modifica motor, decisión, umbrales ni
> material durable; **no** se ejecuta la ventana real; **no** se re-ejecuta CI. Todo lo que aquí
> se afirma sale de una lectura real de PostgreSQL el **2026-10-14**, salvo lo que se cita de la
> documentación del sello (marcado como tal).
>
> **Veredicto de una línea:** el **sello técnico** de `v2.88.132-beta` sigue en pie (lo verificado
> antes no se revisa aquí), pero la **certificación de la operativa AUTO diaria** sigue **pendiente**:
> el material durable **no contiene ni un solo fill atado a un ciclo** (`cycle_id`), la cuenta de
> ventana declarada **no existe** y la cadena por valor de ESTUDIO no tiene ciclos. Los
> instrumentos read-only se comportan de forma **honesta** (declaran el hueco, no lo rellenan).

---

## 0. Contexto de identidad (lo citado del repo, no re-verificado aquí)

| Elemento | Valor |
| --- | --- |
| Sello auditado | `v2.88.132-beta` (tag lightweight, unsigned) |
| Commit del sello | `49f578408dc094a3db8b29459195032b6eb82f8b` |
| Versión monorepo | `2.11.132-beta` (`package.json`) |
| `HEAD` de esta sesión | `1ec674166f13bdeeb63067d9d4fee3fc209139a5` (**POST-TAG** de la evidencia) |
| Alembic head medido | `053_dia_d_cycle_verifications` (**sin migración**) |
| Cuenta de ventana declarada | `1484e253d2d54645945a6b1d7` (`scripts/lib/window-forward.mjs:259`) |

No se re-ejecutó el `Release tag CI` `38602858232`; su veredicto se toma de la documentación del
sello (marcado como tal, no re-medido).

---

## 1. Descubrimiento read-only (qué material AUTO existe)

Consultas `SELECT` (sin escritura) sobre PostgreSQL, con `uv run --no-sync`.

### 1.1 Hecho decisivo: **cero fills atados a un ciclo en toda la base**

```text
SELECT count(*) FROM sim_fill_finance_context WHERE cycle_id IS NOT NULL;   → 0
```

No es un cero «sin mirar»: la lectura completó. Es un **cero medido**: **no hay ninguna fila de
fill con `cycle_id`** en toda la base. Como el paso `FILL` del monitor se deriva de los fills
agrupados por `cycle_id` (`auto_operational_monitor.py:1403-1407`, `:863`, `_fill_step` `:554`),
**ningún ciclo puede cerrarse** desde hechos durables (y `cycles_from_fills` descarta el ciclo sin
`cycle_id`: `auto_self_evaluation_feed.py:177-219`).

### 1.2 Material agregado medido

| Fuente | Medición (2026-10-14) |
| --- | --- |
| `sim_fill_finance_context` con `cycle_id` | **0** |
| `portfolio_reservations` con `cycle_id` | **31** ciclos distintos en **19 cuentas** (12 cuentas × 2 ciclos + 7 × 1) |
| `top3_opportunities` | **31** filas |
| `dia_d_cycle_verifications` | **2** |
| `auto_engine_runs` | múltiples motores; los `auto-estchain-*` en `RUNNING`/`ANALYZING` con `proposals=0` |
| Universo **ESTUDIO** | `status=ok`, **35** valores (`v2_99`) |

- Los 31 ciclos con `cycle_id` son **material sembrado de test**: instrumentos `inst-gd2-*`
  (familia de fixture), estados `RELEASED_BY_FILL`/`RELEASED_BY_CANCEL`, `reserved_risk` 1000 → 0.
- El universo **ESTUDIO real** son ~35 instrumentos `cmtzslag*`/`cmtzslah*`, **distintos** de los
  `inst-gd2-*`. Es decir: los ciclos que existen **no pertenecen al ESTUDIO**.
- La cuenta de ventana declarada **`1484e253d2d54645945a6b1d7` no tiene fila en `investment_accounts`**
  (0 reservas, 0 fills, 0 journal, 0 top3, 0 DÍA-D). La ventana forward **nunca corrió** en esta base.

---

## 2. `v2_99` — cadena AUTO por valor de ESTUDIO (read-only)

### 2.1 Run A — cuenta de ventana declarada (el objetivo operativo)

```text
uv run --no-sync python apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py \
  --account-id 1484e253d2d54645945a6b1d7 --engine-id auto-sim --limit 100 \
  --out operability_runs/estudio-chain/estudio-chain.json
```

Salida real (resumen):

```text
cuenta 1484e253d2d54645945a6b1d7 · ESTUDIO ok (35 valores) · asOf 2026-10-14T17:58:47Z
valores medidos 0/35 · cadenas completas 0/35 · ciclos 0 (completos 0) · mejor puntuada NO (hueco)
```

Los 35 valores de ESTUDIO declaran `cycles: []`, `measured: false`, `unmeasured: ["no_cycles_for_value"]`.

### 2.2 Run B — cuenta con material sembrado (contraste)

```text
uv run --no-sync python apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py \
  --account-id 34569c24bcbf40eea99a6c8ec --engine-id auto-estchain-e8a81464 --limit 100 \
  --out operability_runs/estudio-chain/estudio-chain-test-acct.json
```

Salida real (resumen):

```text
valores medidos 0/35 · cadenas completas 0/35 · ciclos 2 (completos 0) · mejor puntuada sí
```

Detalle de los 2 ciclos (leen en `cyclesOutsideEstudio`, **fuera del universo ESTUDIO**):

| Campo | Valor medido |
| --- | --- |
| `chain.reached` | **`[RESERVATION, ORDER]`** (2/9) |
| `chain.notReached` | `FILL`/`CYCLE_CLOSED` = `pending`; `RISK`/`PROTECTION`/`SETTLEMENT`/`SIGNAL`/`TOP_N` = `unknown` |
| `executed` | `strategyPresetKey`/`strategyVersion`/`rank`/`score` = **`null`** (`measurement=UNKNOWN`) |
| `executedVsBest` | `executedIsTopRanked=null`; `executedIsBestScoredAsset=true|false`; `presetMatch=null` |
| `diaD` | `null`; `executedVsDiaD.matches = null` |
| `pnl.reconciled` | `null` |
| `notes` del ciclo | `signal_not_durable`, `top_n_not_durable`, `risk_not_durable`, `protection_not_durable`, `settlement_not_durable` |
| `monitor.notes` | `decision_journal_not_durable`, `reconciliation_not_durable`, `claim_audit_not_durable`, `owner_session_not_durable` |

Drill-down del ciclo `cyc-6b71666ec471`: mismo resultado (1 ciclo, fuera de ESTUDIO).

### 2.3 Lectura de las nueve etapas

El lector **no fabrica**: cada etapa sin traza durable viaja `None`. Para el material existente,
la cadena **no pasa de `RESERVATION` + `ORDER`**; `FILL` queda `pending` (`no_fills`) porque **no
hay fills atados al ciclo** (§1.1). La identidad de estrategia ejecutada también es un hueco
declarado (nunca se infiere del ranking) y el eslabón DÍA-D de ciclo es `null`.

---

## 3. `v2_98` — certificación de la ventana PAPER (read-only)

```text
uv run --no-sync python apps/api-python/scripts/v2_98_paper_window_certification.py \
  --account-id 1484e253d2d54645945a6b1d7 \
  --strategy-version v283-window-a --strategy-version v283-window-b \
  --out operability_runs/paper-window-certification/cert.json
```

Salida real:

```text
fills leidos 0 · ciclos 0 · entradas de journal 0
dias=0/4  episodios=0/2  ciclos=0/32  =>  INCONCLUSIVE
criterios faltantes: days, episodes, measurable_cycles
```

**Delta honesto frente al plan de arranque:** el documento
`plan-ventana-paper-arranque-operativo-2026-10-14.md` §A cita una salida previa
`dias=42/4 episodios=0/2 ciclos=0/32`. La medición **de hoy** para la cuenta declarada es
`dias=0/4` (lectura completada, material vacío: `entradas de journal 0`). Se declara la diferencia;
no se reinterpreta el número anterior.

El certificado declara `readOnly=true`, `substitutesRealWindow=false` y `verdict=INCONCLUSIVE`: es
un **cero medido**, no una certificación.

---

## 4. DÍA-D — verificaciones existentes y su enlace

Las **2** filas de `dia_d_cycle_verifications`:

| Cuenta | `cycle_id` | Instrumento | Modo | Preset | Banda | Creado |
| --- | --- | --- | --- | --- | --- | --- |
| `d272c8cde4aa4af5889ea4461` | `cyc-ui-fda7886b202f` | `cmtzslah50007xn9c7ftx7y4l` (**ACS**) | `auto` | `sma_crossover` | `favorable` | 2026-10-13 |
| `34d02b0146fd451b853c4dd45` | `cyc-ui-8510e2611bf6` | `cmtzslah50007xn9c7ftx7y4l` (**ACS**) | `auto` | `sma_crossover` | `favorable` | 2026-10-13 |

Lectura honesta:
- **Sí** hay una verificación DÍA-D de un instrumento del ESTUDIO (**ACS**), lanzada en modo `auto`
  — evidencia de que el flujo **es alcanzable** (prefijo `cyc-ui-` sugiere lanzamiento desde UI).
- **Pero** esos `cycle_id` (`cyc-ui-*`) **no son ciclos AUTO** y sus cuentas **no** son las que
  ejercita la cadena por valor de ESTUDIO. No hay **enlace** verificación↔ciclo-AUTO demostrado:
  `executedVsDiaD.matches = null` en todos los ciclos leídos. El eslabón DÍA-D de la cadena AUTO
  sigue siendo un **hueco declarado**.

---

## 5. Clasificación de los huecos (sin convertirlos en éxito)

| Hueco | Clase | Base de la clasificación |
| --- | --- | --- |
| `v2_98` cuenta 1484: `dias=0/... episodios=0/... ciclos=0/...` | **Cero MEDIDO** | La lectura completó; el material está vacío (`entradas de journal 0`). |
| `v2_99` Run A: 0/35 valores medidos | **Cero MEDIDO** (por valor) | Cada valor declara `no_cycles_for_value`; no se rellena con `0`. |
| Sin ventana en la cuenta declarada | **FALTA DE OPERACIÓN** | La cuenta `1484e253…` no tiene fila ni material; la ventana forward nunca corrió. |
| Sin fills con `cycle_id` en toda la base | **FALTA DE OPERACIÓN** | Coincide con el plan §B.0: los fills sin `cycle_id` vienen de lanes manual/legacy; el pipeline V2 no ha corrido en una cuenta real. |
| Reservas `inst-gd2-*` `RELEASED_BY_FILL` sin fila en `sim_fill_finance_context` | **Artefacto de TEST (explicado)** | Forense (§11.1): son residuos huérfanos de 4 tests PG cuyo `finally` borra los fills pero **no** las reservas, y la purga de sesión borra las cuentas (sin FK en `portfolio_reservations.account_id`) y los instrumentos `inst-%`. **No es bug de producto.** |
| Carril `inst-v46*` que llega a `SETTLEMENT` sin fill financiero | **Artefacto de TEST (explicado)** | Forense (§11.2): ese carril lo emiten `test_crash_recovery_day_process_pg.py` / `test_auto_v46_*`, que **también borran** `SimFillFinanceContextRow` en teardown. No se observó ninguna ruta de producción que libere una reserva sin persistir el contexto. |
| DÍA-D no enlazado a ciclo AUTO | **Hueco DECLARADO** | Existen verificaciones `cyc-ui-*` pero sin enlace de identidad con un ciclo AUTO del ESTUDIO. |
| ¿Alguna cadena llegó a `CYCLE_CLOSED` con `cycle_id`? | **NUNCA (0/3425 fills)** | Forense (§11.2): ningún carril llegó a cerrar un ciclo con `cycle_id` en fills. |

**No se identificó ningún «hueco de software»** en el material durable: los dos huecos «sospechosos»
resultaron **artefactos de teardown de tests** (fills borrados, reservas huérfanas por ausencia de FK).
El límite honesto que queda es **de evidencia, no de producto**: como **ningún ciclo real corrió**,
no se puede *probar* desde datos que un ciclo real selle `cycle_id` en `sim_fill_finance_context`; se
puede afirmar que el **código** lo escribe durable-antes-de-mover-dinero (`simulated_settlement.py:213-229`)
y que el camino de producción **no** libera una reserva `BY_FILL` sin contexto (`applied_fills.py:189-190`).

---

## 6. Veredicto (separación sello técnico ↔ certificación operativa)

- **Sello técnico `v2.88.132-beta`:** los cambios declarados (aislamiento XTB `G3`/`G4`/`G6`, gate
  `axe` integrado, tests herméticos) no se revisan aquí y **no se ven afectados** por esta evidencia.
- **Certificación de la operativa AUTO diaria:** **NO alcanzada**. La cadena durable por valor de
  ESTUDIO **no tiene ciclos reales**; la ventana PAPER está **INCONCLUSIVE** con material vacío; el
  material que existe (31 ciclos sembrados, `inst-gd2-*`) **no pertenece al ESTUDIO** y llega solo a
  2/9 etapas.
- **Los instrumentos read-only se comportan de forma honesta:** declaran `UNKNOWN`/`no_cycles_for_value`
  donde falta el hecho, sin colapsar a `0` ni inventar coincidencias (`executedVsBest`/`executedVsDiaD`
  en `null` cuando no hay término de comparación).
- **DÍA-D:** alcanzable (verificación `auto` de ACS), pero **sin enlace** demostrado con un ciclo AUTO.
  La auditoría de UI (§12) confirma que el lanzador manual **existe y es honesto** (identidad exacta,
  fail-closed, `UNKNOWN ≠ 0`, sin fabricar enlaces), pero **no es simple ni descubrible** desde la
  superficie AUTO y puede **deshabilitarse solo** en ciclos comunes.
- **Forense de los dos carriles durables (§11):** ningún material AUTO de esta base es operación real;
  son fixtures de test/semilla. Ninguna cuenta cerró jamás un ciclo con `cycle_id`.

---

## 7. Reproducibilidad y falsabilidad

**Comandos (read-only) ejecutados:** §2.1, §2.2, §2.3 y los descubrimientos
(`operability_runs/_discovery/discover*.py`, `SELECT` puro). Artefactos en
`operability_runs/estudio-chain/` y `operability_runs/paper-window-certification/` (carpeta
**gitignored**, `.gitignore:102`).

**Cómo se falsa cada afirmación:**
- «No hay fills con `cycle_id`» → `SELECT count(*) FROM sim_fill_finance_context WHERE cycle_id IS NOT NULL;` ≠ 0.
- «La cadena no pasa de 2/9» → re-ejecutar `v2_99` sobre esa cuenta: aparecerían `FILL`/`SETTLEMENT` en `chain.reached`.
- «La ventana es INCONCLUSIVE con material vacío» → re-ejecutar `v2_98`; `dias/episodios/ciclos` > 0 lo falsaría.
- «La cuenta 1484 no existe» → `SELECT * FROM investment_accounts WHERE id='1484e253…';` con filas lo falsaría.

---

## 8. Límites declarados (lo que esta evidencia NO demuestra)

1. **No certifica la operativa real ni la rentabilidad** (la ventana ≥4 días es OPERACIÓN).
2. **No re-ejecuta CI ni re-verifica el sello**; la identidad del tag se cita del repo.
3. **`v2_99` invoca `ensure_migrated()`** antes de leer (ruta de esquema); con head ya en
   `053_dia_d_cycle_verifications` es no-op, pero se declara. El resto de lecturas son `SELECT`.
4. **Sí se atribuye la causa** del hueco de `FILL` en los ciclos sembrados (§5.3): la forense dirigida
   (§11) la clasifica como **artefacto de teardown de tests**, no como fallo de persistencia durable.
   Lo que **no** se puede *probar* desde datos es el sellado de `cycle_id` en una corrida real (no
   existe ninguna): esto es un límite de evidencia, no un defecto detectado.
5. **Un exit code `0` de los CLIs no es certificación**: declaran el hueco y salen `0` por diseño.
6. **La auditoría de UI (§12) es estática** (lectura de código); no ejecuta la app ni valida
   comportamiento en runtime ni accesibilidad medida por `axe`.

---

## 9. Siguiente paso recomendado (OPERACIÓN, fuera de esta nota)

1. Correr la ventana forward real (§`plan-ventana-paper-arranque-operativo-2026-10-14.md` §C):
   re-anclar el pin (`TREE_MOVED`) y `window:run-day` en días de mercado operables y distintos.
2. Re-ejecutar `v2_99`/`v2_98` por día y conservar los artefactos hasta ≥4 días / ≥2 regímenes /
   ≥32 ciclos medibles con `cycle_id`.
3. **Añadir a la ventana real una comprobación explícita de sellado**, el único punto que los datos no
   resolvieron: tras el **primer** ciclo real, verificar que su fila en `sim_fill_finance_context`
   lleva `cycle_id` no nulo y que `auto_position_materialized.execution_id` tiene contrapartida
   financiera (falsación §11.2 punto 4). Un solo ciclo real separa «falta de operación» de un hueco
   real de sellado. *(La causa del hueco `inst-gd2-*` ya está atribuida en §11.1: artefacto de test.)*
4. **Cerrar los huecos de operativa diaria de UI** (§12) antes de dar por «simple» la operación:
   CTA de lanzamiento DÍA-D descubrible desde la superficie AUTO, enlace verificación↔ciclo
   **automático** (no solo al «Guardar Evidence»), y navegación por teclado en el toolbar DÍA-AUTO.

---

## 10. Ficheros producidos

- `docs/engineering/evidencia-readonly-auto-paper-2026-10-14.md` (este documento).
- Artefactos (gitignored): `operability_runs/estudio-chain/estudio-chain.json`,
  `operability_runs/estudio-chain/estudio-chain-test-acct.json`,
  `operability_runs/estudio-chain/drilldown-cyc-6b71666ec471.json`,
  `operability_runs/paper-window-certification/cert.json`, y las salidas crudas `*.txt`/`*.json`
  de `operability_runs/_discovery/` (incl. `anomaly_probe*.py`, `forensic_auto_chain*.py`).

---

## 11. Forense de los dos carriles durables (subagentes, read-only)

Objetivo: decidir si el material con `cycle_id` describe operación real o fixtures, y si algún
hueco es de software. Consultas `SELECT` puras (helpers en `operability_runs/_discovery/`,
gitignored); head Alembic `053_dia_d_cycle_verifications` confirmado.

### 11.1 El hueco «`RELEASED_BY_FILL` sin fill» es **artefacto de test** — clasificación (a)

- En **producción** las dos escrituras van en el mismo tick y en orden correcto: el contexto
  financiero se persiste **antes** de mover dinero (`simulated_settlement.py:213-229`) y la reserva
  se libera después (`auto_simulation_worker.py:3596-3600`, `:6354`, `:6388`). La reconciliación de
  arranque **descarta** cualquier fill cuyo contexto falte (`applied_fills.py:189-190`). Por tanto,
  en producción **no** puede quedar `RELEASED_BY_FILL` sin contexto.
- Las 62 reservas (`31` ciclos, `19` cuentas, `inst-gd2-*`) son residuos de **4 tests PG**
  (`test_golden_day_v2_process_pg.py`, `test_auto_estudio_chain_evidence_pg.py`,
  `test_auto_dia_d_trace_pg.py` ×2) cuyo `finally` borra `SimFillFinanceContextRow`/`ExecutionEventRow`
  pero **nunca** `portfolio_reservations`; la purga de sesión (`conftest.py:48-60`) borra las cuentas
  y los instrumentos `inst-%`. `portfolio_reservations.account_id` **no tiene FK**
  (`tables.py:2685`; DB: `fk_on_reservations = []`), así que las reservas **sobreviven huérfanas**.
- Evidencia DB: las 19 cuentas **no existen** en `investment_accounts`; no hay instrumentos
  `inst-gd2-%`; `sim_fill_finance_context WHERE cycle_id IS NOT NULL` = **0**; prefijos de engine
  exclusivos del arnés (`auto-gd2*`, `auto-estchain*`, `auto-diad*`). No hay `DELETE` de reservas
  ni FK `ON DELETE CASCADE` en el repo.
- **Veredicto: (a) fixture parcial, NO bug de producto.** *Residual:* una asimetría latente
  (modo estructural «sin dinero», `context_store is None`) podría liberar `BY_FILL` sin contexto; no
  operó aquí; merece un test dirigido.

### 11.2 El carril `inst-v46*` también es fixture — y **ninguna cadena cerró jamás**

- Tipos de evento `auto%` globales: `auto_cycle_regime` (1452), `auto_entry_decision` (565),
  `auto_reservation_reconciliation` (265), `auto_reservation_claim` (264),
  `auto_protection_event` (131), `auto_entry_order` (110), `auto_position_materialized` (25),
  `auto_cycle_settlement` (22). **No existe** `auto_paper_evidence_snapshot` (0) ni un evento
  `auto_cycle_closed`: `CYCLE_CLOSED` se **reconstruye desde fills**, de modo que sin `cycle_id` en
  fills no puede existir.
- **Carril A (journal, `inst-v46*`)**: llega de verdad a `SETTLEMENT` para **22 ciclos**
  (`exitReason: time_exit`, `pnlMeasurement: COMPLETE`, `pnl`), pero sus instrumentos son sintéticos
  (`inst-v46conc`, `inst-v46crash`, `inst-v46mp`, `inst-a11`) y los emiten `test_crash_recovery_day_process_pg.py`
  / `test_auto_v46_*` — que **borran su `SimFillFinanceContextRow` en teardown**
  (`test_crash_recovery_day_process_pg.py:550`). El `auto_position_materialized.executionId` sin
  contrapartida financiera (§C del subagente) es, por tanto, **el mismo mecanismo de teardown**.
- **Carril B (reservas/TOP3, `inst-gd2-*`)**: 62 filas / 31 ciclos, **0** fills, **0** eventos de
  ejecución, cuentas ausentes de `investment_accounts`. Llega solo a `TOP_N` + `RESERVATION`.
- **A ∩ B = ∅**: ningún `cycle_id` aparece a la vez en reservas y en un fill/evento ejecutado.
- **Cuentas reales**: `investment_accounts` = 17 (1 semilla + 16 `e2e-v167/v168-*` de hoy). Solo
  `default-account-seed` tiene material AUTO (3 eventos, 0 órdenes, 0 settlements, 2 fills con
  `cycle_id` **NULL**). **Ninguna cuenta real pasó de `SIGNAL`.**
- **Veredicto: NINGUNA cuenta cerró jamás un ciclo con `cycle_id` (0/3425 fills).** Coincide con la
  hipótesis de **falta de operación**. *Contrario honesto:* el carril A demuestra que
  `SIGNAL → … → SETTLEMENT` **sí** funciona; el único punto que los datos **no** pueden separar es el
  sellado `executionId → sim_fill_finance_context.cycle_id` en una corrida **real** (§9.3).

---

## 12. Auditoría de UI — lanzamiento manual de DÍA-D y claridad de la operativa diaria (subagente)

Auditoría **estática** (lectura de código; la app no se ejecutó).

**Verdicto:** el lanzamiento manual **existe** y es **honesto** (identidad por coincidencia exacta,
fail-closed, `UNKNOWN ≠ 0`, jamás fabrica el enlace), pero **no es simple ni descubrible** desde la
superficie AUTO y **puede auto-deshabilitarse** en ciclos comunes.

**Hallazgos (con evidencia `path:line`):**
- **Descubribilidad (Alto).** El único control vive en la tarjeta «Estrategia que sustenta la señal»
  (`auto-operation-strategy-card.tsx:189-208`), dentro del panel de historia
  (`auto-operation-story-panel.tsx:466-472`), alcanzable en `/auto/operar/operacion/:cycleId`
  (`auto-operacion-page.tsx:77`) o `/auto-monitor?mode=operation` (`auto-monitor-page.tsx:101`).
  Camino típico ≥3 clics. **No hay CTA** en `/auto` ni en `/auto/operar`; el enlace DÍA-D del HOME
  (`auto-home-page.tsx:405-408`) es el **sandbox read-only** (`dia-d-auto-panel.tsx:148-159`).
- **Fail-closed sin alternativa (Alto).** El hook no navega sin `instrumentId`/`strategyDefinitionId`
  (`use-dia-d-verify-launch.ts:64-66`). `verifyTarget` exige que la estrategia ejecutada resuelva por
  coincidencia de cadena exacta contra un slot de Finalistas (`auto-operation-strategy.ts:236-253`,
  `:339-373`); si el ciclo no declara `strategyPresetKey` o el slot no es `#1`, la CTA queda
  deshabilitada (`auto-operation-strategy-card.tsx:44-49`) **sin ruta alterna** en AUTO.
- **Enlace ciclo↔verificación best-effort (Alto).** Se persiste **solo** al pulsar «Guardar Evidence»
  y con errores tragados (`trading-dia-d-replay-panel.tsx:641-668`); por eso la tabla de ciclos puede
  mostrar «Sin verificación» aunque el usuario **sí** verificara
  (`dia-d-auto-feedback-cycles.tsx:55-120`).
- **Tres identidades de estrategia en una tarjeta (Medio)** — mejor disponible / declarada por el
  ciclo / ejecutada-resuelta (`auto-operation-strategy-card.tsx:70-169`), con etiquetas técnicas y una
  nota larga de coincidencia exacta; el `dt` de la referencia **cambia según el rango** (`:70-77`).
  Los tres conceptos (mejor puntuada / ejecutada / cerrada) están **honestamente etiquetados pero
  repartidos** entre superficies.
- **«Operación cerrada» no es concepto de primer nivel (Medio)**: solo aparece como peldaño
  `"Posición cerrada"` (`auto-operation-ladder.ts:44-49`) y como figura de cuenta
  (`auto-account-figures.ts:37-41`). El sandbox DÍA-D no se puede lanzar in-app (solo imprime comando
  CLI, `dia-d-auto-panel.tsx:90-114`).
- **Accesibilidad (Alto/Medio).** `AutoMonitorModeToolbar` usa `role="tablist"/"tab"`/`aria-selected`
  **sin** `aria-controls`/`tabpanel` **ni** navegación por flechas (`dia-d-auto-toolbar.tsx:21-52`),
  a diferencia de sus toolbars hermanos. El motivo de la CTA deshabilitada va en `title`
  (`auto-operation-strategy-card.tsx:197-203`). Texto a `10–11px` en varios paneles DÍA-D.

**No fabricación confirmada:** sin `cycleId` → `unknown` («Sin dato todavía»,
`dia-d-cycle-verification-status.ts:25`); error de lectura → `unknown`; coincidencia no comparable →
`unknown`, nunca `same` (`auto-operation-strategy.ts:222-225`).

---

## 13. Addendum — estado de la deuda tras la forense

- El caso §5.3 («hueco declarado, causa no determinada») **pasa a EXPLICADO**: artefacto de test
  (§11.1). No se promueve a bug de software.
- Nuevo hecho duro: **ninguna cadena AUTO cerró nunca con `cycle_id`** (§11.2), lo que refuerza
  «falta de operación» sobre «software roto».
- **Deuda operativa abierta** (no bloquea el sello técnico): (1) observar el **primer ciclo real**
  para cerrar el único punto que los datos no resuelven (§9.3); (2) cerrar los huecos de UI de
  operativa diaria (§12) para poder certificar la operación diaria como **simple**.

---

## 14. Ejecución (a)(b)(c) con subagentes — 2026-10-14 (post-auditoría)

Se ejecutaron, **en orden** `(a) → (b) → (c)`, los tres frentes siguientes. Todo con subagentes. Nada
se commiteó/etiquetó/empujó.

### 14.a Ventana PAPER real — pin re-anclado; día `NO_MEDIDO_REGIMEN`

- **Pin re-anclado** (edición de `scripts/lib/window-forward.mjs`, fuera del pin de motor): de la
  tupla `9b8e4904 / apps 79fb2685… / packages f80b2285…` a `1ec67416 / apps 04226aba… /
  packages d48ac37b…`. `node scripts/window-forward-runner.mjs --dry-run run-day` → **`freeze OK`**.
  Legitimidad (§G.1 del plan): el pin anterior **nunca midió un día** ⇒ mover el pin no invalida nada.
  Honestidad declarada en el comentario: este salto (`9b8e4904..1ec67416`) **no** reclama `Δ motor = 0`.
- `pnpm run window:preflight` → régimen de HOY `BEAR_TREND`, **LONG vetadas** (exit declarado).
- `pnpm run window:run-day` → **día `20261014` registrado `NO_MEDIDO_REGIMEN`** (`reason: regime_invalid`);
  el veto de régimen **no lanzó** el forward. **Ningún día medible**.
- `pnpm run window:status` → `medidos=0 veto=1 declarados=0 duros=0`, gate `NO_MEDIDO`.
- `v2_98` (re-ejecutado) → **`INCONCLUSIVE`** (`dias 0/4, episodios 0/2, ciclos 0/32`).
  **Delta declarado** frente al plan §A (`dias=42/4 → 0`): el material de «42 días de journal» **no
  aparece** en esta lectura (`journalEntriesRead=0`, `fillsRead=0`, `reservationsRead=0`). Se declara;
  no se reinterpreta.
- **Conclusión de (a):** la ventana quedó **abierta y operativa** (freeze OK) pero **sin días medibles**;
  hoy el mercado vetó LONG. Sigue `INCONCLUSIVE`.

### 14.b Sellado `executionId → sim_fill_finance_context.cycle_id` — PROBADO con test hermético

- **Nuevo test** `apps/api-python/tests/test_auto_fill_cycle_seal_pg.py` (**4 passed**; +36 en las suites
  durable afines; +5 en la de reservas). `ruff` limpio. **Sin cambio de producción.**
- Se confirma el sellado **durable-first, antes de mover dinero**: `simulated_settlement.py:213-229` →
  `sim_finance_context.py:76-91` → `sim_durable_store.py:525-545` → columna `tables.py:2327`; y la
  liberación `RELEASED_BY_FILL` **dirigida por el contexto persistido** vía `applied_fills.py:187-191`.
  El test **negativo** prueba que un fill sin contexto **no** produce una liberación `BY_FILL` fabricada.
- La **asimetría del modo estructural** (`context_store is None`, `auto_simulation_worker.py:1831-1834`)
  es real en código pero **NO alcanzable** por la composición de producción (`_compose_real_stores`
  `:6830-6852`, `AutoSimRuntime` `:7626-7706`); se fija con un test como **guardia implícita**.
- **Cierra el único punto que el informe declaraba «no resoluble desde datos» (§9.3)**: ahora está
  cubierto por test **sin** necesitar una corrida real. Límite honesto que permanece: es un test del
  camino de código, **no** una corrida real (§9.3 se atenúa, no se elimina).

### 14.c Huecos de UI de operativa diaria (§12) — implementados P1–P5

- **P1 (a11y, Alto)** toolbar DÍA-AUTO con patrón WAI-ARIA completo (`aria-controls`/`tabpanel` +
  flechas/Home/End + roving tabindex): `dia-d-auto-toolbar.tsx`, `auto-monitor-page.tsx` + test nuevo.
- **P2 (descubribilidad, Alto)** CTA de verificación descubrible en `/auto/operar`
  (`auto-operar-verify-action.tsx`) reutilizando `useDiaDVerifyLaunch` (sin duplicar lógica);
  fail-closed, declara el hueco cuando no resuelve, sin caer al `#1`.
- **P3 (a11y, Alto)** motivo de CTA deshabilitada asociado con `aria-describedby` (+`aria-disabled`).
- **P4 (integridad, Alto)** el enlace ciclo↔verificación **persiste dentro del flujo de verificación**
  y **deja de tragarse errores** (`role="alert"`); tri-estado `linked|not-verified|unknown` intacto.
- **P5 (vocabulario, Medio)** token L1 `DÍA-D` → `D→hoy` en 4 superficies AUTO + test de vocabulario.
- **Verde:** **2217/2217** tests unit; `tsc` OK; `eslint` **0 errores**; gates e2e mockeados con `axe`
  **14/14** (AUTO) y **44/44** (nav + puente DÍA-D + rutas tocadas).

### 14.d Integridad del freeze vs cambios de código (nota **importante**)

El orden `a → b → c` **no dañó la ventana**, por dos razones verificadas:

1. El día de `(a)` fue **`NO_MEDIDO_REGIMEN`** (no `MEDIDO`) ⇒ **no había ningún día medido que
   invalidar**.
2. Los cambios de `(b)`/`(c)` están **SIN COMMITEAR**, y el freeze lee el **árbol de `HEAD`
   (commits)**, no el working tree: `git rev-parse HEAD:apps` sigue `= 04226aba…` ⇒ **el pin re-anclado
   SIGUE VÁLIDO** y `run-day` sigue pasando el freeze.

**Regla a respetar de aquí en adelante:** al **commitear** los cambios de `(b)`/`(c)`, `HEAD` avanzará
y `apps`/`packages` cambiarán ⇒ habrá que **re-anclar** otra vez; y si para entonces existiera algún día
`MEDIDO` bajo `1ec67416`, ese día caería a `STALE`. Por tanto, **los días que certifican la ventana
deben correrse DESPUÉS de landear los cambios de código**, con un re-anclaje final por delante.

**Árbol de trabajo hoy:** 12 ficheros modificados (11 `apps/web/**` + `scripts/lib/window-forward.mjs`)
y 8 nuevos (1 test Python + 7 de `apps/web/**`), todos **sin commitear**. `packages/**` **no** cambia.

### 14.e Veredicto tras (a)(b)(c)

- **Sello técnico `v2.88.132-beta`:** sin regresión; el sellado de `cycle_id` queda además **probado por
  test** (§14.b) y la UI de operativa diaria queda **endurecida** (§14.c).
- **Certificación de la operativa AUTO:** **sigue NO alcanzada** — por **falta de operación**, no de
  software. El pin está listo (`freeze OK`); falta correr la ventana en **≥4 fechas operables reales**
  y dejar que AUTO **cierre** ciclos con `cycle_id` (§14.a).

### 14.f Cierre — commits y re-anclaje final (realizado)

Se ejecutó el cierre pedido (**commitear (b)/(c) + re-anclar el pin**), todo **local, sin push**:

| Commit | Contenido |
| --- | --- |
| `73d99147` | `(b)` test hermético del sellado `executionId → cycle_id` (`apps/api-python/tests/test_auto_fill_cycle_seal_pg.py`) |
| `d3313def` | `(c)` huecos de UI de operativa diaria P1–P5 (`apps/web/**`) — lint-staged (prettier+eslint) OK |
| `05dc2d5b` | docs: esta nota de evidencia |
| `9e6e18df` | ops: re-anclaje del pin al árbol tras landear `(b)/(c)` |

- **Pin final:** commit `05dc2d5b`, `apps 5696698e…`, `packages d48ac37b…` (`packages` **no** cambió).
  `node scripts/window-forward-runner.mjs --dry-run run-day` → **`freeze OK`** verificado en
  `HEAD = 9e6e18df` (`HEAD:apps` sigue `5696698e…` porque `scripts/` no participa del pin).
- El día `20261014` (`NO_MEDIDO_REGIMEN`) queda registrado; **no se invalidó ningún día medido**
  (ninguno existía).
- **Estado:** árbol de trabajo **limpio**; la ventana queda **lista** (`freeze OK`), pendiente solo de
  **días de mercado operables reales** (§14.a). Verificación final: `git status` vacío.
