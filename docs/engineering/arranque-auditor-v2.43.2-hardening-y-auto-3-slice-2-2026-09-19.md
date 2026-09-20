# Arranque auditor — v2.43.2: Hardening de contabilidad de posición + Exit Governance (AUTO-3 slice 2) (`1.68.2-beta`)

**Ref a auditar:** el **commit de fase** de este parche (se fija al sellar, §12 del pack). **No** se audita
aquí `v2.43-beta` (slice 1) ni `v2.43.1-beta` (remediación): son refs **anteriores** y **no se mueven**.
**Migración: ninguna** (Alembic head sigue en `042_portfolio_reservations`).

**Punto de entrada del paquete:** [`audit-pack-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md`](./audit-pack-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md).
Después, este documento. El relevo para la fase siguiente está en
[`traspaso-relevo-post-v2-43-2-auto-3-slice-2-2026-09-19.md`](./traspaso-relevo-post-v2-43-2-auto-3-slice-2-2026-09-19.md).

**Aviso de numeración.** El plan de trabajo llamó «v2.44» a la fase de Exit Governance. **La versión de
paquete es `1.68.2-beta`**: el roadmap reserva `V2.44`/`1.69.0-beta` para **AUTO-4 Portfolio Optimizer**, y
esto es el **slice 2 de `AUTO-3`**. Una referencia a «v2.44» en el código es la **etiqueta del plan**, no la
versión.

**ESTADO DE LA MATRIZ (ya medida):** la **matriz de mutaciones del §10 del pack ESTÁ MEDIDA** (sonda
versionada `v2_43_2_mutation_audit.py`, 2026-09-20): **9 de las 13 mutaciones muerden** (M1–M5, M7–M9, M11)
y **4 nacen verdes** (M6, M10, M12, M13), con la causa de cada verde declarada en el §10.1 del pack. Los
**tres agujeros reales** (M6, M12, M13) están **declarados y reproducibles**; **no** se añadió test ni se
tocó código de producción. Un hallazgo del tipo «no mide lo que dice» sigue siendo válido, pero ya no vive
en la matriz.

---

## 1. Orden de lectura (20–30 min)

1. **§0 del pack** — los seis hallazgos del hardening y por qué **H1 y H2 son P0**. Si solo lees una cosa,
   lee esta tabla: los dos P0 son el mismo patrón que la auditoría de `v2.43-beta` ya atacó (un dato
   ininterpretable que se degrada hacia el lado **permisivo**).
2. **§7 del pack** — Exit Governance. Es la fase con **comportamiento nuevo**, así que es donde el
   blast radius es mayor.
3. **§8 del pack** — cambios observables y **breaking declarado**. Contrasta cada fila con el código.
4. **§9.1 del pack** — el delta `+40/+40`. Es la comprobación de que **lo nuevo corre en CI**; si el delta
   no cuadra, hay tests fuera de la red.
5. **§10 del pack** — matriz de mutaciones **medida**, verdes explicadas y límites. **Casi todo lo que se
   te ocurra ya está ahí**: si el hallazgo ya está declarado, no es un hallazgo nuevo, es una confirmación.

---

## 2. Afirmaciones verificables (con su medida)

| #   | Afirmación                                                                                             | Dónde se mide                                                                                                                                        |
| --- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | `realized_qty` es `min(ΣBUY, ΣSELL)` y `sold_qty`/`unmatched_exit_qty` son explícitos y aditivos       | `test_position_ledger.py` (M1 pone **5** rojos, §10)                                                                                                 |
| A2  | Una venta huérfana **no** se come una compra legítima posterior                                        | `test_orphan_oversell_never_swallows_a_later_legit_buy` + la misma lectura por `quantities()`                                                        |
| A3  | El snapshot de trabajo **no** fabrica un riesgo medido cuando la base no es medible                    | `test_working_snapshot_never_fabricates_measured_risk` (+ su control)                                                                                |
| A4  | Un stop del lado equivocado da `risk_amount is None` (**no** `0.0`) y el motor **veta**                | `test_build_worker_snapshot_wrong_side_stop_is_unmeasured_risk` (+ control)                                                                          |
| A5  | El fold deduplica por `execution_id`: `BUY 100@10` ×2 ⇒ `100`, nunca `200`                             | `test_duplicate_execution_id_cannot_double_the_position`                                                                                             |
| A6  | El libro agrupa por `(account_id, instrument_id)` y una **colisión entre cuentas degrada la medición** | `test_position_ledger.py` (H5)                                                                                                                       |
| A7  | Un hecho **sin fecha** se dobla **al final**, no como el más antiguo                                   | `test_facts_without_date_are_folded_last_not_first`                                                                                                  |
| A8  | `RISK_OFF` ⇒ `RISK_EXIT` (venta **total**) con `PORTFOLIO_RISK` como **secundario**                    | `test_risk_off_forces_full_risk_exit`, `test_risk_off_beats_take_profit`, `test_position_manager.py`                                                 |
| A9  | `HALTED` ⇒ `KILL_SWITCH` (venta total) y **`EXIT_ONLY` NO liquida**                                    | `test_halted_forces_kill_switch_total_sell`, `test_exit_only_operational_state_does_not_liquidate`                                                   |
| A10 | Un `risk_regime`/banda/estado **no reconocido** no es permisivo (`UNKNOWN`)                            | `test_unknown_risk_regime_is_not_permissive`                                                                                                         |
| A11 | La parada dura **bloquea entradas siempre** y **no congela** las salidas protectoras                   | `test_blocks_new_entry_but_allows_protective_exits_by_default`, `test_v2_halt_forces_protective_exit_not_congelation`                                |
| A12 | La parada dura es **latcheada**, **tipificada** y solo se libera con **reconciliación explícita**      | `test_latch_is_not_self_released_and_counts_reengagements`, `test_non_canonical_reason_is_rejected`, `test_release_requires_explicit_reconciliation` |
| A13 | La parada dura se evalúa **aunque el gobernador esté OFF**                                             | `test_halt_overrides_a_benign_governor_reading` + `or halted` en `auto_v2_entry.py:820`                                                              |
| A14 | `market_data` stale **veta la apertura** pero **permite la salida protectora**                         | `test_data_freshness.py` + `test_v2_stale_market_data_vetoes_entry_but_allows_protective_exit`                                                       |
| A15 | Un instante ininterpretable es `unknown`, **nunca epoch 0**                                            | `test_unparseable_timestamp_is_unknown_not_epoch_zero`                                                                                               |
| A16 | Una salida deja reserva viva **durable antes de emitir** y el fill de **venta** la libera              | `test_v2_exit_leaves_a_live_sell_reservation_released_by_fill`                                                                                       |
| A17 | Un reinicio en mitad de un `RISK_EXIT` **no puede** re-emitir la misma `SELL`                          | `test_v2_restart_mid_risk_exit_releases_the_dead_sell_reservation_once`                                                                              |
| A18 | El día completo `ENTRY → RISK_EXIT → FLAT` cierra con `position=0, reservation=0, pending=0`           | `test_v2_golden_day_dynamic_entry_risk_exit_flat_with_restart`                                                                                       |
| A19 | El gobernador **no se movió**: su evidencia es byte a byte igual y sigue **exit 0**                    | `git diff -- apps/api-python/scripts/v2_43_governor_evidence.py` (vacío) + el script                                                                 |
| A20 | Los **40 tests nuevos entran en CI** por las listas existentes                                         | delta `1991 → 2031` y `2002 → 2042` (**+40** en ambos)                                                                                               |

---

## 3. Comandos listos

```bash
# estático, tipos y fronteras (invocación EXACTA de CI)
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

# bloques offline de CI tal cual están en el YAML (+ verificación de rutas y medición por JUnit XML)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
```

**Runner de CI:** usa `scripts/verify/offline_ci_run_yaml.py`, **no** una copia a mano de la lista. El
propio §13 del pack declara que en esta fase una verificación hecha **sin** el flag `--config
pyproject.toml` midió **otra cosa** (2 avisos «preexistentes» que en realidad eran **7 avisos nuevos**).

---

## 4. Preguntas abiertas que deberías intentar romper

Cada una es un sitio donde este parche **puede** estar equivocado. Ninguna está resuelta por declaración.

1. **¿H1 dejó el oversell peor contabilizado que antes?** Con `realized_qty += matched`, el exceso vive en
   `unmatched_exit_qty`. **¿Algún consumidor que antes leía `realized_qty` como "lo vendido" y ahora lee
   "lo casado" está peor, no mejor?** Busca lectores de `realized_qty` en el repo y decide si alguno
   necesitaba `sold_qty` y no se actualizó.
2. **¿`remaining_qty` puede crecer por encima de `quantity` por algún camino?** La fórmula es
   `max(0.0, quantity - realized_qty)` y `realized_qty <= quantity` por construcción del `matched`. ¿Hay
   algún camino que rompa esa cota (p. ej. compras después de ventas, que es el caso de
   `test_orphan_oversell_never_swallows_a_later_legit_buy`)?
3. **¿La agrupación por `(account_id, instrument_id)` rompe algún consumidor que esperaba una entrada por
   instrumento?** `LedgerPosition.account_id` es nuevo: ¿alguien indexa por `instrument_id` y asume
   unicidad? La **colisión entre cuentas** se declara degradando la medición — **¿es suficiente, o hay un
   camino que lee `quantities()` antes de mirar la medición?**
4. **¿`_fold_sort_key` con hechos sin fecha es determinista si hay dos sin fecha y sin `execution_id`?**
   El tipo garantiza `execution_id` no vacío, pero **compruébalo**: si se pudiera construir uno vacío, el
   orden entre dos filas sin fecha dependería del orden de llegada.
5. **¿La reafirmación defensiva del manager es alcanzable?** Si `full_exit` ya garantiza la venta total,
   esa rama puede ser **código muerto** (y entonces hay que declararlo) o puede ser **la única** que
   sostiene el invariante en algún camino (recon, fracción de T2, ratchet). **Decide cuál de las dos y
   dilo.**
6. **¿`EXIT_ONLY` de verdad no liquida, o se cuela por `drawdown_band == "EXIT_ONLY"`?** El código dice
   `risk_off = coerce_risk_regime(risk_regime) == "RISK_OFF" or band == "EXIT_ONLY"`. **La banda de
   drawdown `EXIT_ONLY` SÍ liquida** mientras que el **estado operacional** `EXIT_ONLY` **no**. ¿Es
   coherente con el contrato del roadmap, o son dos ejes que se llaman igual y significan cosas distintas?
   (Esta es la pregunta más afilada de la lista.)
7. **¿La parada dura se puede quedar pegada para siempre?** Es latcheada y `release_kill_switch` no tiene
   productor automático (§10.2 del pack). ¿El sistema puede quedar **permanentemente sin aperturas** por un
   halt que nadie libera? Decide si es un límite aceptable declarado o un hallazgo.
8. **¿`hard_kill_switch.py` es de verdad puro?** El docstring lo afirma (sin I/O, sin reloj). Compruébalo:
   un `datetime.now()` escondido convertiría `engaged_at` en no determinista.
9. **¿`blocks_new_entry` bloquea también cuando la dimensión `market_data` es `unknown`?** El pack dice que
   sí (`status != fresh`). ¿Es lo que quieres, o `unknown` debería ser "no mido esta dimensión" (que es lo
   que `FreshnessPolicy` dice de un umbral `None`)? **Hay una tensión real entre las dos frases.**
10. **¿La reserva de venta puede duplicarse?** `_v2_reserve_exit` crea una reserva por salida con
    `_v2_exit_seq`. ¿Qué pasa si dos salidas del mismo instrumento se emiten **en el mismo tick**, o si el
    reinicio ocurre **entre** la reserva y la orden? El test cubre el reinicio en mitad del `RISK_EXIT`
    **después** de emitir: **¿y antes?**
11. **¿`committed_positions()` puede publicar un `net_qty` que oculte una posición real?** Si hay una
    compra viva de 100 y una venta viva de 100, el neto es 0 y **la posición desaparece de la proyección**.
    ¿Es correcto (la venta la va a cerrar) o peligroso (si la venta no se ejecuta, la proyección mentía)?
12. **¿La colisión de nombres entre el `REGIME_EXIT` legacy y el nuevo es total?** El manager ya no hace
    `exit_reasons.append(REGIME_EXIT)`; ahora el motivo baja de la decisión. **¿Hay algún consumidor que
    esperaba el `regime_exit` como ÚLTIMO elemento de la lista** y ahora lo encuentra por precedencia?
13. **¿El delta `+40/+40` esconde un test que pasó a `skip`?** Los dos bloques miden `0 skipped` en el
    runner offline, pero comprueba que **ninguno** de los 40 nuevos está gated por un flag.

---

## 5. Qué NO es un hallazgo (declarado antes de que lo encuentres)

Todo esto **ya está declarado** en el §10/§10.2 del pack. Confirmarlo es útil; reportarlo como hallazgo
nuevo, no:

- **La matriz de mutaciones ya está medida** y sus verdes explicadas (§10.1). Un hallazgo sobre la causa de
  una mutación verde sigue siendo válido, pero la matriz **no** es deuda pendiente.
- **PG real no medido** en la máquina del autor (el `connect` del DSN se cuelga). La certificación de
  durabilidad la aporta CI.
- **La parada dura no se persiste entre reinicios** y **`release_kill_switch` no tiene productor
  automático**: un halt no se libera solo. Declarado.
- **`force_protective_exits` existe pero el worker no lo consulta**: el default `True` es lo que corre.
  Declarado.
- **`atr`/`volume` de la frescura van `unknown`** en la práctica (no hay productor real que les dé edad):
  solo `market_data` es un eje activo hoy. Declarado.
- **El gobernador sigue con default OFF** y **sus umbrales siguen sin calibrar**: deuda de `AUTO-3` slice 1,
  intacta aquí por diseño.
- **`PositionLedger` es read-model sin tabla propia** y el `limit` de `list_applied` es un suelo: deuda de
  `v2.40.5`.
- **El emisor de `RECONCILED` sigue sin existir**: deuda de `AUTO-2`.
- **`v2_43_governor_evidence.py` conserva `"bump": "1.68.0-beta"`**: es deliberado (el gobernador no se
  mueve) y ya se declaró en `v2.43.1` §8.2.
- **`v2.43-beta` y `v2.43.1-beta` no se mueven**: este parche es una ref nueva y aditiva.

---

## 6. Formato de un hallazgo

`P0/P1/P2 · afirmación atacada · ruta:línea · comando exacto · salida observada · ¿el §10 del pack ya lo
declara?`

Como en las fases anteriores: si el hallazgo **ya está declarado** en el §10/§10.2, cítalo y di que es una
**confirmación**; si **no** lo está, es un hallazgo nuevo y se responde en el hilo del
[issue #62](https://github.com/jvelasca/Bolsa_V1/issues/62) (donde ya vive la auditoría de `v2.43-beta`).
