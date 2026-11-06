# Dictamen de aceptación — `v2.88.175-beta`

> **AsOf:** 2026-11-01 · **Objeto:** tag `v2.88.175-beta` (objeto de tag `3144661f`, **anotado** → commit
> `de5c94245953bba9cc3f34b4f2345894f1f43d44`) · **Versión:** `2.11.175-beta`.
> **Naturaleza:** **registro de aceptación**. No es una re-auditoría ni una re-medición: no modifica código,
> tests, CI, guarda, migraciones, `package.json`, `CHANGELOG` ni tags.
> **Veredicto:** se acepta el **cierre técnico** de `v2.88.175-beta` con los hallazgos `P-1b` y `N-1`…`N-4`
> (más `Obs. 1` y `Obs. 2`), el gate A7 duro y la purga condicionada por esquema, **y se acepta con el límite
> permanente `L-175-1` de §4.1**: la convivencia de `chaos/live_a7` con el stack sobre la BD compartida
> `bolsa_v1` **no está certificada y queda fuera de alcance por decisión**.

---

## 0. Qué añade este documento

El sello ya tiene evidencia propia ([`evidence/v2.88.175/README.md`](./evidence/v2.88.175/README.md)) y un
expediente de cierre hallazgo por hallazgo
([`cierre-hallazgos-auditoria-v2.88.174-2026-11-01.md`](./cierre-hallazgos-auditoria-v2.88.174-2026-11-01.md)).
Lo que faltaba es el **acto de aceptación**: qué se da por bueno, con qué ancla, cuál es el alcance exacto de
la evidencia y —sobre todo— **qué no se acepta como cerrado** al aceptarlo. Ese es el contenido de §2, §3 y §4.

Este dictamen **no re-mide** las suites: cita la medición publicada y la contrasta con el objeto publicado.
Lo que sí se contrasta aquí de primera mano es la **identidad del objeto** y el **resultado del CI del tag**
(§1.1), porque el dictamen que motiva este registro declaró expresamente no haber consultado GitHub.
Donde la evidencia no existe (rentabilidad, ventana PAPER, suites completas sobre este árbol), lo dice en vez
de inferirlo del CI verde.

---

## 1. Identidad y CI del objeto aceptado

| Elemento | Valor |
| --- | --- |
| Tag | **anotado** (unsigned), objeto `3144661f…`, `taggername jvelasca`, `2026-11-01T19:39:37+01:00` |
| Commit apuntado | `de5c9424` (`docs(evidence): evidencia del sello v2.88.175-beta`) |
| Base anterior | `v2.88.174-beta` → `17ab0ef9` (**inmóvil**: se auditó tal cual se publicó y no se reescribe) |
| `Release tag CI` | [run `41337773491`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41337773491) — **`success`** |
| Jobs | **12 `success`** + `certify` `success`; único `skipped` = `playwright (integrated E2E, opt-in)` |
| Artefacto `release-tag-ci-summary` | `id 13096850913` · `status: "GREEN"` · `"a7-gate": "success"` · `asOf 2026-11-01T18:55:25Z` |
| Deltas | `Δ motor = 0` · `Δ decisión = 0` · contrato HTTP **aditivo** · sin migración (`head` `062_sync_settings_check_backfill`) |

### 1.1 Contraste independiente (hecho en este acto, 2026-11-01)

No se hereda del expediente: se vuelve a leer del objeto publicado.

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Tipo de tag y destino | `git for-each-ref refs/tags/v2.88.175-beta` | `tag` → `de5c9424…`, tagger `2026-11-01T19:39:37+01:00` |
| Base inmóvil | `git rev-parse 'v2.88.174-beta^{commit}'` | `17ab0ef9…` — **sin cambios** |
| Run del tag | `gh run view 41337773491` | `completed` / `success`, `sha de5c9424…` |
| Job A7 | `gh run view 41337773491` (jobs) | `a7-gate (A7 C3 chaos live_a7 · dedicated real-PG)` **`success`** |
| Log del job A7 | `gh run view --job 124941143119 --log` | step de pytest con `LIVE_A7_PG_REQUIRED: 1` y `DB_NAME: bolsa_v1_a7` ⇒ **`19 passed in 14.57s`** |
| Artefacto | `gh run download 41337773491 -n release-tag-ci-summary` | `tag: "v2.88.175-beta"`, `sha: "de5c9424…"`, `ref: "refs/tags/v2.88.175-beta"`, `status: "GREEN"`, **`"a7-gate": "success"`** |

Tres precisiones sobre lo anterior, para que el ancla no diga más de lo que mide:

* **El artefacto certifica el commit del tag, no otro.** Declara `sha: "de5c9424…"` y
  `ref: "refs/tags/v2.88.175-beta"`, que es exactamente lo apuntado por el tag.
* **`status: "GREEN"` es un literal, no un cálculo** (`.github/workflows/release-tag-ci.yml`, step
  `Write summary artifact`). Lo que le da valor probatorio es que su step **no** se ejecuta si el step
  anterior —`Fail if any required job failed`, con `needs.a7-gate.result != 'success'` entre las condiciones y
  `exit 1`— ha fallado. Es decir: un artefacto con `GREEN` implica que todos los jobs obligatorios fueron
  `success`, y un skip en `a7-gate` deja el sello sin artefacto y con `certify` en rojo.
* **`19 passed` sin skips no se deduce del verde**: se lee del log del step, que además declara las dos
  variables que hacen del skip un fallo.

---

## 2. Qué se acepta

### 2.1 Los tres riesgos anteriores

| Riesgo | Resultado | Dictamen |
| --- | --- | --- |
| Skips verdes que ocultaban falta de ejecución | `a7-gate`: **19 passed, 0 skipped** (log del step), `LIVE_A7_PG_REQUIRED=1` | **Cerrado** |
| Aviso de purga inexacto con esquema sin migrar | 3 tests + comprobación sobre BD vacía recreada, sin `relation "investment_accounts" does not exist` | **Cerrado** |
| Confundir stack activo con BD compartida | `bolsa_v1_a7` con stack vivo: **19/19** | **Cerrado para BD dedicada**; la BD compartida queda en `L-175-1` (§4.1) |

El tercero está bien delimitado y así se acepta: queda demostrada la ejecución con el stack vivo **cuando se
usa una BD dedicada**. La convivencia segura sobre `bolsa_v1` compartida **no** queda demostrada, y este
dictamen no la presume.

### 2.2 El gate A7 en el CI

Se acepta como la pieza que impide que un run con precondiciones incumplidas se presente como certificación.
Las cuatro garantías están en el workflow y son verificables línea a línea
([`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml)):

| Garantía | Dónde | Qué impide |
| --- | --- | --- |
| `LIVE_A7_PG_REQUIRED: '1'` en el `env` del **job** | job `a7-gate` | que un instrumento del job (incluida la preparación de la BD) quede fuera del gate |
| `LIVE_A7_PG_REQUIRED: '1'` en el `env` del **step** de pytest | step `Pytest A7 chaos live_a7 (dedicated real-PG, fail if skipped)` | que el gate dependa de que nadie mueva el `env` del job |
| `a7-gate` en el `needs` de `certify` + `needs.a7-gate.result != 'success'` ⇒ `exit 1` | job `certify` | que un A7 rojo produzca sello verde |
| `"a7-gate"` en el artefacto resumen | step `Write summary artifact` | que la trazabilidad del sello omita el veredicto de A7 |

Con eso, **un skip en `a7-gate` es rojo y `certify` no puede escribir `GREEN`**. La regla de lectura queda
fijada: el veredicto de A7 en un sello es el resultado del job `a7-gate`, **nunca** un run local con skips.

### 2.3 Hallazgos `P-1b` y `N-1`…`N-4` (más `Obs. 1` y `Obs. 2`)

Se aceptan con la trazabilidad del expediente: cada uno queda vinculado a un nodo de test concreto, en el
commit `12e2c871` y en el árbol del tag.

| # | Qué se acepta | Ancla |
| --- | --- | --- |
| `P-1b` | El placeholder `KILL_STATE_UNREADABLE` **no es una causa**: un motivo real lo sustituye y él nunca degrada un motivo real; el placeholder no se persiste | `test_auto_v2_audit_regressions.py::test_p1b_*` (5 nodos) |
| `N-1` | El interruptor de Yahoo se cierra en el cliente (sin tráfico) y `/market/fx` declara `409 provider_disabled:yahoo` | `test_yahoo_traffic_gate.py` (11), `test_market_fx_provider_gate.py` (3) |
| `N-2` | Precios no finitos o no positivos se rechazan en origen, en la sonda y en FX (directa e inversa) | `test_yahoo_spot_price.py` (10), `test_fx_rates.py` (10), `test_market_providers.py` |
| `N-3` | Una copia sin auditoría se **declara** (`audit_recorded` / `backups_error`), no se silencia | `test_database_backup.py`, `test_database_backup_api.py`, `database-maintenance-panel.test.tsx` |
| `N-4` | «Caducado» se mide contra el proveedor **más viejo** (`min(measured)`) | `test_summary_stale_uses_the_oldest_measurement_not_the_newest`, `test_monitor_is_due_by_the_oldest_provider_measurement` |
| `Obs. 1` | Los dos `purge` exigen `admin` con auth, y el 403 ocurre **antes** de tocar la BD | `test_database_purge_role_gate.py` (4 parametrizados) |
| `Obs. 2` | Se informa el fichero declarado por el script, validado; el delta queda como compatibilidad declarada | `test_backup_runner.py::test_the_declared_file_wins_over_a_foreign_file_in_the_directory` (+2) |

Además se aceptan los dos tripwires que impiden deshacer el cierre en silencio:
`test_release_tag_ci_a7_gate_wiring.py` (5 casos: el YAML no lo ejecuta nadie, así que se ancla con un test)
y `test_residual_purge_schema_guard.py` (3 casos: sin esquema cero `DELETE` y cero aviso; con esquema, la
purga sigue viva).

---

## 3. Alcance exacto de la evidencia

Lo que la evidencia **acredita** es el conjunto de **escenarios y contratos efectivamente cubiertos** por los
nodos citados, ejecutados sobre el objeto publicado. Lo que **no** acredita es una demostración ilimitada de
ausencia de defectos. La distinción no es retórica:

* Un nodo verde acredita que **ese** escenario pasa con **esas** precondiciones. `test_p1b_*` acredita que el
  placeholder no borra una parada real en los caminos que ejercita; no acredita que no exista otro camino que
  escriba el espejo durable.
* `19 passed, 0 skipped` acredita que los **19** casos de `chaos/live_a7` —12 del contrato de la guarda + 7
  real-PG— se ejecutaron y pasaron contra BD dedicada. No acredita la convivencia con el stack sobre la BD
  compartida (§4.1) ni la ausencia de un modo de fallo fuera de esos siete escenarios C3.
* El artefacto `GREEN` acredita que los jobs obligatorios fueron `success` en el commit del tag. No mide si el
  dinero está bien calculado, ni si la estrategia gana, ni si la fuente de datos es legible.

Se acepta, por tanto, **el cierre técnico de los puntos comunicados**, no una garantía general de corrección.

---

## 4. Límites expresos de la aceptación

Aceptar `v2.88.175-beta` significa aceptar estos límites. No se suavizan.

### 4.1 `L-175-1` — la convivencia sobre `bolsa_v1` compartida queda **fuera de alcance por decisión**

**Estado:** límite **permanente y nombrado**. No es una deuda pendiente de un sello futuro ni una medición que
falte por hacer: es una **exclusión deliberada** del alcance de la certificación.

**Qué no está certificado.** La ejecución de `chaos/live_a7` conviviendo con el stack de desarrollo sobre la
BD **compartida** `bolsa_v1`. En esa configuración el `scheduler_worker` de `pnpm dev` drena la fila `UNKNOWN`
sembrada (`claim_unknown_batch` barre toda la tabla, sin filtro de cuenta — correcto en producción) y el
escenario C3-A lee `drained=0 resolved=0`. La guarda lo diagnostica y **salta a propósito**; un
`12 passed, 7 skipped` en verde **no** es un pase y no debe leerse como tal.

**Por qué se excluye y no se persigue.** La única forma de certificarla sería ejecutar los escenarios
**escribiendo** en la BD que usa el entorno de desarrollo, es decir, interferir con él para probar que no se
interfiere. Eso cambia el riesgo en lugar de reducirlo: el resultado dejaría de ser evidencia y pasaría a ser
una manipulación del entorno de trabajo, con residuos (`live_orders`, `execution_events`, purgas de cuentas)
sobre datos que el operador está usando.

**Qué sustituye a esa certificación.** El job `a7-gate` del `Release tag CI`, con BD dedicada `bolsa_v1_a7`
(drop+create) y sin stack: mismo escenario, precondición verificada y skip convertido en `AssertionError`. La
condición dura es la **BD**, no los puertos; y los puertos son contexto informativo, nunca prueba.

**Qué haría falta para abrirlo.** Un mecanismo de verificación **sin escrituras** sobre la BD compartida —por
ejemplo, un diagnóstico de solo lectura que acredite «la guarda detecta y salta» sin ejecutar C3— y una
**decisión explícita** que lo autorice con su propio alcance y su propio sello. **No** se abre con un test más
ni con una ejecución nocturna.

**Consecuencia en el expediente.** El límite se cita con este identificador (`L-175-1`) en el expediente de
cierre y en la evidencia, para que sea enlazable desde fuera y no se reinterprete como un hueco olvidado.

### 4.2 Lo demás que este dictamen no certifica

1. **Rentabilidad ni operativa.** AUTO **OFF**; PAPER **`INCONCLUSIVE`**. Un sello de corrección no añade
   evidencia de resultados.
2. **Las suites completas sobre este árbol.** No se repitieron: las cifras de `.174` (`4 582` / `1 454` /
   `2 677`) **no se heredan**. Aquí solo se midieron los nodos tocados (`81` + `92` + `2` passed, `19/19` A7).
3. **El E2E en la nube.** No se repitió: el diff no toca flujo de UI nuevo (avisos de `N-3` y descripciones
   de `N-1`), y el job `playwright (integrated E2E, opt-in)` está `skipped` por diseño.
4. **La GitHub Release.** No se emite, mismo criterio que `.173` y `.174`.
5. **La guarda como sustituto de la ejecución aislada.** Detecta un worker ajeno **si dejó un claim fresco** en
   la preflight; uno que arranque después no se intercepta. Certifica que la BD es exclusiva, no que el
   escenario se ejecutó en un entorno libre de todo proceso.
6. **El contenido de `.174`.** `.174` no contiene este código: `git cat-file -e "v2.88.174-beta:<ruta>"` falla
   para `_exclusivity_guard.py` y para el documento de cierre. Se acepta el sello `.175`; `.174` **no se
   reabre** y su distinción histórica se conserva.
7. **Los workflows de rama y el estado de `main`.** Este dictamen mira el CI **del tag**; los gates de rama no
   lo sustituyen y no se han re-verificado aquí.

---

## 5. Lo verificado aquí y lo que no

**Verificado de primera mano en este acto:** tipo y destino del tag, inmovilidad de `.174`, resultado del run
`41337773491`, `success` del job `a7-gate`, `19 passed in 14.57s` sin skips en su log con
`LIVE_A7_PG_REQUIRED: 1` y `DB_NAME: bolsa_v1_a7`, contenido del artefacto `release-tag-ci-summary`
(`GREEN`, `a7-gate: success`, `sha`/`ref` del tag) y las cuatro garantías del cableado leídas en
[`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml).

**No verificado aquí:** publicación de la GitHub Release (no existe), estado de los workflows de rama, alineación
de `main`, y reproducibilidad local de las mediciones del §4 de la evidencia (se citan como publicadas, no se
re-ejecutan).

---

## 6. Falsabilidad de esta aceptación

Cada afirmación aceptada se puede **romper**:

| # | Afirmación aceptada | Cómo se rompe |
| --- | --- | --- |
| 1 | El objeto aceptado es el que se certificó | mover o re-anotar `v2.88.175-beta`; el commit cambia y el run `41337773491` deja de corresponderle |
| 2 | Un A7 verde con skips no sella | quitar `LIVE_A7_PG_REQUIRED` del `env` del job o del step, sacar `a7-gate` de `needs`, o borrar el `exit 1` ⇒ **rojo** en `test_release_tag_ci_a7_gate_wiring.py` |
| 3 | Un skip no pasa por verde | con `LIVE_A7_PG_REQUIRED=1` sobre una BD no dedicada ⇒ `AssertionError`, no `skip` (`test_exclusivity_guard.py`) |
| 4 | El placeholder no borra una parada real | volver a liberar por ver el placeholder ⇒ rojo en `test_p1b_a_real_halt_discovered_under_the_placeholder_is_never_released` |
| 5 | La purga no habla de un esquema que no existe | quitar `to_regclass(...)` ⇒ rojo en `test_residual_purge_schema_guard.py` |
| 6 | Con Yahoo apagado no hay tráfico | llamar al cliente sin `_ensure_traffic_allowed` ⇒ rojo en `test_yahoo_traffic_gate.py` |
| 7 | `L-175-1` se mantiene declarado | afirmar en el expediente o en la evidencia que la BD compartida está certificada ⇒ contradice §4.1 y el propio texto del skip |

---

## 7. Alcance de este registro (no-cambios)

* **No** modifica código, tests, contrato, CI, `package.json`, `CHANGELOG`, migraciones ni `.github/`.
* **No** crea, mueve ni anota tags: `v2.88.175-beta` (`3144661f` → `de5c9424`) y `v2.88.174-beta`
  (`17ab0ef9`) quedan **como están**.
* **No** toca la guarda de exclusividad, el cableado de `a7-gate`, el bump ni el pin PAPER
  (`window:freeze` no cambia: solo `apps/` y `packages/` entran en el hash y aquí no se tocan).
* **No** emite GitHub Release.
* **No** reescribe la evidencia ni el expediente: **se añade encima**, y la única modificación en ellos es
  rotular el límite de §4.1 con su identificador `L-175-1`.
* **No** intenta demostrar la convivencia sobre la BD compartida.

---

## 8. Cierre

Se acepta `v2.88.175-beta` como **sello de corrección** posterior a `.174`: `P-1b` y `N-1`…`N-4` (más
`Obs. 1` y `Obs. 2`) cerrados con nodos que **se rompen si el defecto vuelve**; el gate A7 duro con las cuatro
garantías ancladas por test; la purga condicionada por esquema; y el run del tag **GREEN** con `a7-gate` en
`19 passed, 0 skipped` sobre BD dedicada.

Se acepta **con** el límite `L-175-1`: la convivencia sobre `bolsa_v1` compartida **no está certificada y no se
intentará** mediante una ejecución que pueda interferir con el entorno de desarrollo. `.175` queda como
**referencia auditable** —tag inmóvil, CI del tag, evidencia y expediente—; `.174` se conserva intacta y no se
reabre.

Lo aceptado es el **cierre técnico de los puntos comunicados** y el **alcance de la evidencia** que los
respalda. No es una certificación de rentabilidad ni de operativa, y no cierra el límite de la BD compartida:
lo declara.
