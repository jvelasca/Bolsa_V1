# Brief de auditoría — v2.43.2: Hardening de contabilidad de posición + Exit Governance (AUTO-3 slice 2) (`1.68.2-beta`) (2026-09-20)

> **Qué es este documento.** Una **guía de ataque** para el auditor externo, no un pack nuevo: el
> contrato y la matriz afirmación→código→test siguen viviendo en el
> [audit-pack](./audit-pack-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md). Aquí solo se ordena **qué
> atacar primero**, con `ruta:línea` **verificada en el árbol** y el **comando exacto** de cada medida.
> No sustituye al pack: lo precede. Si hay contradicción entre este brief y el pack, **manda el pack**.

> **Regla de este documento: es de solo lectura para el agente.** No se toca código de producción ni
> tests por él (regla de oro del §0 del
> [relevo de cierre](./relevo-cierre-v2.43.2-matriz-mutaciones-y-sello-2026-09-20.md)). Un hallazgo que
> exija cambiar código **se declara en el hilo**, no se arregla dentro de la auditoría.

---

## 1. Qué se audita y de dónde

| Dato                       | Valor                                                                                  |
| -------------------------- | -------------------------------------------------------------------------------------- |
| **Ref a auditar (código)** | commit de fase **`ef35e3aa`**                                                          |
| **Etiqueta**               | tag anotado **`v2.43.2-beta`** → `13b54ceb` (**docs-only**, el sello)                  |
| **Base del diff**          | `7a192481` (sello de `v2.43.1`) → **29 ficheros, `+3814 / −66`**                       |
| **Versión de paquete**     | `1.68.2-beta` · **sin migración** (Alembic head sigue en `042_portfolio_reservations`) |
| **Estado**                 | **SELLADO**; CI real medida en `main` y en la ref del tag (§12 y §12.1 del pack)       |

- **Punto de entrada:** [`audit-pack-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md`](./audit-pack-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md).
- **Después:** [`arranque-auditor-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md`](./arranque-auditor-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md).
- **Relevo siguiente:** [`traspaso-relevo-post-v2-43-2-auto-3-slice-2-2026-09-19.md`](./traspaso-relevo-post-v2-43-2-auto-3-slice-2-2026-09-19.md).

**Freeze (congelado — tocarlo _es_ hallazgo):**

- `AUTO_ENGINE_SIM_V2=0` ⇒ comportamiento `v2.39.x`.
- `AUTO_ENGINE_SIM_V2_GOVERNOR=0` **sin parada dura** ⇒ byte-idéntico a `v2.43.1`.
- `apps/api-python/scripts/v2_43_governor_evidence.py` byte a byte igual (su `"bump"` se queda en
  `1.68.0-beta`, deliberado: `v2.43.1` §8.2).

**Aviso de numeración.** El plan de trabajo llamó «v2.44» a la fase 2. La **versión de paquete es
`1.68.2-beta`**: el roadmap reserva `V2.44`/`1.69.0-beta` para `AUTO-4`. Una referencia a «v2.44» en el
código es la **etiqueta del plan**, no la versión.

---

## 2. P0 — atacar primero

### 2.1 P0-1 (H1) · `realized_qty` cuenta lo **casado**, no lo solicitado

**Afirmación:** `realized_qty == min(Σ BUY, Σ SELL)`; el exceso vive en `unmatched_exit_qty`, y `sold_qty`
es Σ ventas **ejecutadas** (el hecho del venue).

**Código:** `packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py:280-292`
(`sold_qty += fact.quantity` → `matched = min(...)` → `realized_qty += matched`); campos nuevos en
`:171-173` (`sold_qty`, `unmatched_exit_qty`, `account_id`); expuestos en `to_dict()` `:196-198`; la
cantidad viva se deriva en `:312` (`remaining_qty = round4(remaining)`, con
`remaining = max(0.0, quantity - realized_qty)`).

```280:292:packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py
        sold_qty += fact.quantity
        avg_entry = (cost_basis / quantity) if quantity > _QTY_EPS else None
        sellable = quantity - realized_qty
        if sellable <= _QTY_EPS:
            violations.append(f"oversell_without_position:{fact.execution_id}")
            continue
        matched = min(fact.quantity, sellable)
        if avg_entry is not None:
            realized_pnl += matched * (fact.price - avg_entry)
            cost_basis -= matched * avg_entry
        if fact.quantity > matched + _QTY_EPS:
            violations.append(f"oversell_above_position:{fact.execution_id}")
        realized_qty += matched
```

**Cómo se falsifica:** revertir a `realized_qty += fact.quantity` ⇒ deben caer **5 rojos** (mutación
**M1**). Comando en §5.

**Dónde se mide:**

- `test_oversell_excess_never_inflates_realized_qty_nor_average_entry` (`test_position_ledger.py:159`) —
  `realized_qty == 73.5`, `sold_qty == 100.0`, `unmatched_exit_qty == 26.5`.
- `test_orphan_oversell_never_swallows_a_later_legit_buy` (`:123`) — **el caso mordido**: una venta
  huérfana seguida de una compra legítima tiene que dejar la compra **viva**.
- `test_orphan_oversell_before_a_legit_buy_keeps_position_via_quantities` — el mismo invariante leído por
  el `quantities()` que alimenta la reconciliación.

**Pregunta abierta (§4.1 del arranque).** Con `realized_qty += matched`, el exceso vive en
`unmatched_exit_qty`. **¿Algún consumidor que antes leía `realized_qty` como "lo vendido" y ahora lee "lo
casado" está peor, no mejor?** Busca lectores de `realized_qty` en el repo y decide si alguno necesitaba
`sold_qty` y no se actualizó. Ese es el ángulo donde este fix puede dejar a alguien **peor**.

### 2.2 P0-2 (H2) · El snapshot de trabajo **no** fabrica riesgo medido

**Afirmación:** con base no medible, sumar riesgo reservado está prohibido; `risk_measurement` **no** se
re-deriva en el rebuild.

**Código:**

- `packages/py/application/src/bolsa_application/auto_v2_entry.py:1173` —
  `if has_committed_risk and snapshot.risk_is_complete:`; y `:1196` —
  `risk_measurement=snapshot.risk_measurement`.
- `packages/py/analytics/src/bolsa_analytics/cognitive/auto_portfolio_snapshot.py:436` —
  `if used is None and declared and asserted_measurement in (None, MEASUREMENT_COMPLETE):`; y `:449` —
  `resolved_measurement = asserted_measurement or derived_measurement`.

**Cómo se falsifica:**

- **M2** — `if has_committed_risk:` sin `and snapshot.risk_is_complete` ⇒ **1 rojo**.
- **M3** — `risk_measurement=None` en el rebuild ⇒ **1 rojo**.

Ambas las muerde `test_working_snapshot_never_fabricates_measured_risk`
(`packages/py/application/tests/test_auto_v2_entry.py:603`); el **control** es
`test_working_snapshot_adds_committed_risk_when_base_is_measured`.

**Trampa de lectura declarada (no leer el fix al revés).** El `risk_used=None` del snapshot tiene **dos**
significados legítimos: _cartera vacía_ y _riesgo no medido_. `v2.43.1` tradujo el primero a `0.0`
**solo** cuando no hay posiciones sin medir, y este parche **no** deshace esa traducción (la conserva en
`_risk_state_for`): lo que prohíbe es **sumar riesgo reservado a una base no medible**. Las dos
afirmaciones conviven porque son casos distintos: «cero **medido**» vs «**no medido**».

---

## 3. P1 — los otros cuatro hallazgos del hardening

| ID     | Afirmación                                                                                                               | `ruta:línea`                                                                                                                      | Mordida por                                                                                            |
| ------ | ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **H3** | stop del lado equivocado ⇒ `risk_amount is None` (**no** `0.0`) y el motor **veta**                                      | `auto_v2_entry.py:599-611` (usa `stop_distance`); autoridad única en `portfolio_reservation.py:248` (`def stop_distance`)         | **M4** → `test_build_worker_snapshot_wrong_side_stop_is_unmeasured_risk` (`test_auto_v2_entry.py:542`) |
| **H4** | el fold **deduplica** por `execution_id`: `BUY 100@10`×2 ⇒ `100`, nunca `200`                                            | `position_ledger.py:359-372` (dedupe); violación `:393`; `unvalued` `:394`; `facts_rejected` `:399`                               | **M5** → `test_duplicate_execution_id_cannot_double_the_position` (`:180`)                             |
| **H5** | el libro es **por cuenta**: agrupa por `(account_id, instrument_id)` y la colisión entre cuentas **degrada** la medición | `position_ledger.py:98` (`account_id` en el hecho), `:375` (agrupación), `:382-394` (colisión); poblado en `applied_fills.py:217` | **M6 nace VERDE** ⚠️ (agujero declarado, §4)                                                           |
| **H6** | un hecho **sin fecha** se dobla **al final**, no como el más antiguo                                                     | `position_ledger.py:320-336` (`_fold_sort_key`), usado en `:359`                                                                  | **M7** → `test_facts_without_date_are_folded_last_not_first` (`:200`)                                  |

**H5 es el P1 más interesante.** La mutación **rompe comportamiento pero ninguna suite la muerde**:
`test_position_ledger.py` **nunca** construye un libro con dos `account_id` para el mismo instrumento
(**0 apariciones** de `account_id` en el fichero). Pregunta §4.3 del arranque: `quantities()`
(`position_ledger.py:224-230`) devuelve `instrument_id → remaining_qty`; con colisión se degrada a
`unvalued`, pero **¿hay un camino que lee `quantities()` antes de mirar la medición?**

---

## 4. P1 — Exit Governance (comportamiento nuevo: aquí está el blast radius)

### 4.1 Taxonomía y precedencia

`ExitReason` gana `KILL_SWITCH`/`REGIME_EXIT`/`RISK_EXIT` (`exit_plan.py:20-22`), insertados en la
`EXIT_REASON_PRECEDENCE` **que ya existía** (`:44-56`), con el orden final aplicado en `:208`. La
atribución múltiple vive en `PositionDecision.secondary_reasons` (`position_decision.py:242-245`,
`:370-373`) y se publica en `position_manager.py:120-143`. Lo relevante **no** es que haya tres razones
nuevas, sino que **`REGIME_EXIT` deja de ser un override post-hoc fuera del `Literal`**: antes el manager
hacía `exit_reasons.append(REGIME_EXIT)` a mano (fuera de la taxonomía, sin competir por precedencia) y
ahora nace en el `ExitPlan` (`_collect_reasons`, `exit_plan.py:168-173`).

### 4.2 El gobernador gobierna el ciclo de vida

`position_manager.py:282-285` (`halted`/`band`/`risk_off`/`regime_exit`), `:323` (motivos derivados de la
decisión), `:328-333` (reafirmación defensiva).

| Lectura del gobernador                           | Motivo decisorio | Efecto          |
| ------------------------------------------------ | ---------------- | --------------- |
| `OperationalState == HALTED`                     | `KILL_SWITCH`    | venta **total** |
| régimen de mercado exit-only                     | `REGIME_EXIT`    | venta **total** |
| `RiskRegime == RISK_OFF` **o banda `EXIT_ONLY`** | `RISK_EXIT`      | venta **total** |

> **Pregunta más afilada (§4.6 del arranque).** La **banda** de drawdown `EXIT_ONLY` **SÍ** liquida
> (`risk_off = ... or band == "EXIT_ONLY"`, `position_manager.py:284`) mientras que el **estado
> operacional** `EXIT_ONLY` **NO** (test `test_exit_only_operational_state_does_not_liquidate`,
> `test_position_manager.py:283`). Son **dos ejes con el mismo nombre y semántica distinta**. Decide si es
> coherente con el contrato del roadmap o es un hallazgo.

**M10 nace verde** porque la reafirmación `:328` es **redundante** con la decisión (sin sensor propio): es
declarado, **no** agujero.

### 4.3 `HardKillSwitch` latcheado por encima del gobernador

`packages/py/analytics/src/bolsa_analytics/cognitive/hard_kill_switch.py:67` (clase), `:83-98` (`engage`,
`ValueError` para motivo no canónico, `reengagements`), `:105` (`release` exige `reconciliation_ok`),
`:119` (`blocks_new_entry`). En el motor: `auto_v2_entry.py:820` (`if cfg.governor_enabled or halted:`).
En el worker: `engage_kill_switch`/`release_kill_switch` (`auto_simulation_worker.py:1227-1237`).

**Cómo se falsifica:** **M8** (quitar `or halted`) y **M9** (`halted=False` fijo en la llamada a
`assess_from_measurements`) ⇒ **1 rojo cada una**, ambas
`test_v2_hard_kill_switch_vetoes_entry_with_governor_halted` (`test_auto_v44_exit_governance.py:132`).

**Preguntas abiertas:**

- **§4.7:** ¿la parada dura se puede quedar **pegada para siempre**? Es latcheada y `release_kill_switch`
  **no tiene productor automático** (§10.2 del pack). Decide: **límite aceptable declarado** o
  **hallazgo** (el sistema podría quedar sin aperturas por un halt que nadie libera).
- **§4.8:** ¿`hard_kill_switch.py` es de verdad **puro**? El docstring lo afirma (sin I/O, sin reloj).
  Un `datetime.now()` escondido convertiría `engaged_at` en no determinista.

### 4.4 Frescura por dimensión

`data_freshness.py:36` (las 4 dimensiones), `:48` (`max_market_data_age_s = 300.0`), `:103`
(`blocks_new_entry`), `:132` (`_epoch` devuelve `None`, **nunca** epoch 0).

**Cómo se falsifica:** **M11** (`blocks_new_entry` → `return False`) ⇒ **4 rojos**:
`test_stale_market_data_blocks_new_entry`, `test_unknown_market_data_is_not_fresh`,
`test_v2_stale_data_blocks_new_entry`, `test_v2_stale_market_data_vetoes_entry_but_allows_protective_exit`.

> **Tensión real (§4.9).** El pack dice que `unknown` **bloquea** para `market_data`
> (`blocks_new_entry` es `status != fresh`; §7.5). ¿Es lo que quieres, o `unknown` debería ser «no mido
> esta dimensión» —lo que `FreshnessPolicy` dice de un umbral `None`—? **Hay una frase contra otra**;
> decídete y dilo.

### 4.5 Reservas de SALIDA vivas (F9)

`portfolio_reservation.py:847` (`committed_positions`), neteo `:875-876` (`net_qty = buy_qty - sell_qty`,
nunca negativo), publicación `:895`. Worker: `_v2_reserve_exit` (`auto_simulation_worker.py:1887`,
`side=SIDE_SELL` en `:1920`), release por lado (`:1946` y `:3283`), `_v2_reconcile_reservations` (`:2018`),
clave por `(instrumento, side)` (`:2066`, `applied: dict[tuple[str, str], ...]`), cableado de arranque en
`:3445`.

**M12 y M13 nacen VERDES** ⚠️ (agujeros declarados, §4.6). Preguntas §4.10 y §4.11 del arranque:

- **§4.10:** ¿la reserva de venta puede **duplicarse**? Dos salidas del mismo instrumento en el **mismo
  tick**, o un reinicio **entre** la reserva y la orden (el test cubre el reinicio **después** de emitir,
  ¿y **antes**?).
- **§4.11:** ¿`committed_positions()` puede publicar un `net_qty` que **oculte una posición real**? Si hay
  compra viva de 100 y venta viva de 100, el neto es 0 y la posición **desaparece de la proyección**.
  ¿Es correcto (la venta la cerrará) o peligroso (si la venta no se ejecuta, la proyección mentía)?

### 4.6 Delta `+40/+40` (que lo nuevo corra en CI)

`quality` `1991 → 2031`; job `python` del tag `2002 → 2042`; reparto: `test_position_ledger` 5,
`test_auto_v2_entry` 4, `test_position_manager` 8, `test_hard_kill_switch` 7 (**nuevo**), `test_data_freshness`
8 (**nuevo**), `test_auto_v44_exit_governance` 8 (**nuevo**) = **40**.

> **§4.13:** comprueba que **ninguno** de los 40 está _gated_ por un flag o pasó a `skip`. Los bloques
> miden `0 skipped`, así que un test oculto sería el hallazgo.

---

## 5. Los 3 agujeros **ya declarados** (atacarlos es _confirmación_, no hallazgo nuevo)

| Mutación | Qué rompe                                                                  | Por qué nace verde (§10.1 del pack)                                                                                                                                                     |
| -------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **M6**   | agrupar por `("", instrument_id)` en vez de `(account_id, instrument_id)`  | Ninguna suite construye dos `account_id` para el mismo instrumento (**0 apariciones** en `test_position_ledger.py`)                                                                     |
| **M12**  | saltar (`continue`) las reservas `sell` en `committed_positions`           | El único test (`test_portfolio_reservation_ledger.py:393`, `test_committed_positions_projects_live_buys_only`) reserva compra y venta en **instrumentos distintos** (`AAA`/`BBB`)       |
| **M13**  | casar fills por `(instrument_id, "buy")` en vez de `(instrument_id, side)` | Vive en `_v2_reconcile_reservations` (`:2018`), que **solo corre en el arranque** (`:3445`); el test de reinicio libera por la rama **«muerta»** (`RELEASED_BY_RESTART`, `filled == 0`) |

**M10** también nace verde pero **no es agujero de comportamiento**: es una línea redundante con la
decisión (§4.2).

**Nota de método (de las trampas ya medidas en el repo, §4 del relevo de `v2.43`).** Antes de «añadir
cobertura» a una mutación verde: comprobar que la mutación **rompe comportamiento** y no otro motivo; y
si un test sigue verde con la mutación, **no** es automáticamente agujero de cobertura — hay que
descartar que el mutante sea más fuerte (o más débil) que el bug real. El cierre de esta fase **no
cambia una línea de código de producción ni añade tests** (regla de oro del §0 del relevo): añadir el
sensor que falta a M6/M12/M13 es **decisión del owner**, no un «arreglo a escondidas» dentro del sello.

**Balance medido (§10 del pack, sonda `v2_43_2_mutation_audit.py`, 2026-09-20):** **9 de 13 muerden**
(M1–M5, M7–M9, M11) y **4 nacen verdes** (M6, M10, M12, M13).

---

## 6. Comandos listos (invocaciones **exactas** de CI)

```bash
# estático, tipos y fronteras
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# el gobernador NO se movió: esto debe salir VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"

# suites que muerden los hallazgos (herméticas)
uv run pytest packages/py/analytics/tests/test_position_ledger.py \
              packages/py/analytics/tests/test_hard_kill_switch.py \
              packages/py/analytics/tests/test_data_freshness.py \
              packages/py/analytics/tests/test_exit_plan.py \
              packages/py/application/tests/test_auto_v2_entry.py \
              packages/py/application/tests/test_position_manager.py -q

# el test de fuego: Golden Day dinámico + reinicio en mitad del RISK_EXIT
uv run pytest apps/api-python/tests/test_auto_v44_exit_governance.py -q

# bloques offline de CI con el runner versionado (targets EXTRAÍDOS del YAML, medida por JUnit XML)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores

# reproducir la matriz de mutaciones entera (debe dejar el árbol intacto y salir exit 0)
uv run --no-sync python apps/api-python/scripts/v2_43_2_mutation_audit.py
```

**Runner de CI:** usa `scripts/verify/offline_ci_run_yaml.py`, **no** una copia a mano de la lista.

**Errata de método declarada (§13 del pack) — léela antes de medir.** La primera verificación de `ruff` de
esta fase se hizo **sin** el flag `--config pyproject.toml` y concluyó «2 avisos, ambos preexistentes en
`HEAD`»; con la invocación **de la casa** el resultado era **7 avisos, y los 7 de ficheros de este
parche** (el flag cambia la clasificación first-party de `isort` y, por tanto, qué bloques de imports
considera desordenados). Se verificó la dirección con un **worktree limpio en `HEAD`** (que sí pasa
`All checks passed!`). **Mide siempre con la invocación del CI** o, mejor, con el runner que la **extrae
del YAML**: un parámetro de configuración ausente convierte una medición en una medición de **otra cosa**.

---

## 7. Qué NO es un hallazgo (declarado **antes** de que lo encuentres)

Confirmarlo es útil; reportarlo como hallazgo nuevo, no. Todo esto ya está declarado en el
§10/§10.2 del pack:

- **La matriz de mutaciones ya está medida** y sus verdes explicadas (§10.1). Un hallazgo sobre la **causa**
  de una verde sigue siendo válido; la matriz **no** es deuda pendiente.
- **PG real NO medido** en la máquina del autor (el `connect` del DSN se cuelga) ⇒ la certificación de
  durabilidad la aporta CI (job `auto-v2-durable-pg`, **fail-if-skipped**).
- **La parada dura es en memoria**: **no** se persiste entre reinicios (un reinicio olvida el halt), y
  **`release_kill_switch` no tiene productor automático** (el emisor de `RECONCILED` sigue sin existir,
  deuda de `AUTO-2`).
- **`force_protective_exits` existe pero el worker no lo consulta**: el default `True` es lo que corre.
- **`atr`/`volume` de la frescura van `unknown`** en la práctica (no hay productor real que les dé edad):
  solo `market_data` es un eje activo hoy.
- **El gobernador sigue con default OFF** y **sus umbrales siguen sin calibrar** (`min_liquidity_notional`
  en `0,0`, `restricted_edge_factor` en `2,0`): deuda de `AUTO-3` slice 1, intacta aquí por diseño.
- **`PositionLedger` es read-model sin tabla propia** y el `limit` de `list_applied` es un suelo: deuda de
  `v2.40.5`.
- **`v2_43_governor_evidence.py` conserva `"bump": "1.68.0-beta"`**: deliberado (`v2.43.1` §8.2).
- **`v2.43-beta` y `v2.43.1-beta` no se mueven**: este parche es una ref nueva y aditiva.

---

## 8. Formato de un hallazgo

```
P0/P1/P2 · afirmación atacada · ruta:línea · comando exacto · salida observada · ¿el §10 del pack ya lo declara?
```

Si el hallazgo **ya está declarado** en el §10/§10.2, cítalo y dilo como **confirmación**; si **no** lo
está, es un hallazgo nuevo y se responde en el hilo del
[issue #62](https://github.com/jvelasca/Bolsa_V1/issues/62) (donde ya vive la auditoría de `v2.43-beta`).
