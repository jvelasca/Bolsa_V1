# Traspaso de relevo — post `v2.43.2` (hardening de posición + AUTO-3 slice 2: Exit Governance) → **sello CERRADO**; siguiente `AUTO-4`

**Fecha:** 2026-09-19 · **Versión:** `1.68.2-beta` · **Punto de partida:** tag `v2.43.1-beta` →
`b27280de` (remediación de la auditoría de `v2.43-beta` cerrada). **Migración: ninguna** (Alembic head sigue
en `042_portfolio_reservations`).
**Sello:** **CERRADO** (§12 del pack). Commit de fase **`ef35e3aa`** (29 ficheros, `+3814/−66`) y tag
anotado **`v2.43.2-beta`** sobre el commit de **sellado** docs-only, siguiendo la convención de
`v2.43-beta`/`v2.43.1-beta` (la ref sellada no cita refs inexistentes). CI real en `main`: `Python CI`
**GREEN 5/5** ([run 35497681654](https://github.com/jvelasca/Bolsa_V1/actions/runs/35497681654)) y
`Gitleaks` **GREEN** ([run 35497681645](https://github.com/jvelasca/Bolsa_V1/actions/runs/35497681645)).

**Punto de entrada obligatorio para quien siga:** el
[audit-pack v2.43.2](./audit-pack-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md) y el
[arranque del auditor](./arranque-auditor-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md). Después, este
documento.

---

## 1. Estado en una frase

`AUTO-3` **cierra su slice 2**: el gobernador ya no gobierna solo las **entradas** — también el **ciclo de
vida** de la posición (`RISK_OFF` ⇒ `RISK_EXIT`, `HALTED` ⇒ `KILL_SWITCH`, exit-only ⇒ `REGIME_EXIT`), con
**productor real** de `HALTED` (`HardKillSwitch`, latcheado y tipificado), **frescura por dimensión** y
**reservas de salida vivas** que impiden re-emitir una orden tras un reinicio en mitad de un `RISK_EXIT`.
En el mismo parche se cierran **seis hallazgos de contabilidad de posición** (dos P0) que la auditoría de
código destapó al leer la cola de `position_ledger.py` y el snapshot de trabajo del tick.

**La matriz de mutaciones (§10 del pack) ya está MEDIDA** (sonda `v2_43_2_mutation_audit.py`, 2026-09-20):
**9 de 13 mutaciones muerden** (M1–M5, M7–M9, M11) y **4 nacen verdes** (M6, M10, M12, M13) con su causa
declarada. Lo que falta para cerrar este parche es el **sello**.

---

## 2. Lo que este parche cierra (y cómo se mide)

| Afirmación                                                             | Evidencia                                                                                     |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `realized_qty` deja de inflarse: es `min(ΣBUY, ΣSELL)`                 | 3 tests de H1 en `test_position_ledger.py` (`73.5 / 100.0 / 26.5`)                            |
| Una venta huérfana **no** se come una compra legítima posterior        | `test_orphan_oversell_never_swallows_a_later_legit_buy` + la misma lectura por `quantities()` |
| El snapshot de trabajo **no** fabrica riesgo medido                    | `test_working_snapshot_never_fabricates_measured_risk` (+ control)                            |
| Un stop del lado equivocado ⇒ `risk_amount is None` (**no** `0.0`)     | `test_build_worker_snapshot_wrong_side_stop_is_unmeasured_risk` (+ control)                   |
| El fold deduplica por `execution_id`                                   | `test_duplicate_execution_id_cannot_double_the_position` (`100`, nunca `200`)                 |
| El libro es por **cuenta**, y una colisión entre cuentas **degrada**   | tests de H5 en `test_position_ledger.py`                                                      |
| Un hecho sin fecha se dobla **al final**                               | `test_facts_without_date_are_folded_last_not_first`                                           |
| `RISK_OFF` ⇒ `RISK_EXIT` con `PORTFOLIO_RISK` secundario               | 8 tests de gobernador en `test_position_manager.py`                                           |
| `EXIT_ONLY` **no** liquida (solo veta aperturas)                       | `test_exit_only_operational_state_does_not_liquidate`                                         |
| `HALTED` ⇒ `KILL_SWITCH` (venta total)                                 | `test_halted_forces_kill_switch_total_sell`                                                   |
| La parada dura es latcheada, tipificada y veta entradas                | 7 tests de `test_hard_kill_switch.py`                                                         |
| Frescura: `market_data` stale veta apertura, **no** salida protectora  | 8 tests de `test_data_freshness.py` + 2 de integración                                        |
| Una salida deja reserva viva y el fill de **venta** la libera          | `test_v2_exit_leaves_a_live_sell_reservation_released_by_fill`                                |
| Un reinicio en mitad de un `RISK_EXIT` no re-emite la `SELL`           | `test_v2_restart_mid_risk_exit_releases_the_dead_sell_reservation_once`                       |
| El día completo `ENTRY → RISK_EXIT → FLAT` cierra limpio con reinicios | `test_v2_golden_day_dynamic_entry_risk_exit_flat_with_restart`                                |
| El gobernador **no se movió**                                          | `git diff` del script **vacío** + **exit 0** de su self-check                                 |
| Los 40 tests nuevos **entran en CI**                                   | `quality` **1991 → 2031** y tag **2002 → 2042** (**+40** en ambos)                            |
| Nada nuevo queda fuera de la red                                       | `ruff` limpio · `mypy` **487** ficheros 0 issues · `lint-imports` **4/0**                     |

---

## 3. Qué queda abierto (deuda declarada, por orden de importancia)

1. **La matriz de mutaciones (§10 del pack).** **MEDIDA** (2026-09-20, sonda
   [`v2_43_2_mutation_audit.py`](../../apps/api-python/scripts/v2_43_2_mutation_audit.py)): **9 de 13
   muerden** (M1–M5, M7–M9, M11) y **4 nacen verdes** (M6, M10, M12, M13) con su causa declarada en el
   §10.1 del pack. **Tres agujeros reales** (M6: el eje cuenta de H5; M12: el neteo de F9; M13: la
   reconciliación de arranque) quedan **declarados y reproducibles**; añadir su sensor es decisión del
   owner (**no** se tocó código de producción ni se añadieron tests en el cierre). **Aviso de método:** una
   mutación verde **no** es automáticamente un agujero de cobertura (puede ser una mutación mal puesta o
   más fuerte que el bug); la lección está medida dos veces en este repo (`v2.42.1` M5/M10/M13, `v2.43`
   M5/M6).
2. **El sello.** Commit de fase + tag `v2.43.2-beta` + CI real en `main` y en la ref del tag
   (`Python CI` 5/5 y `Release tag CI` con `certify`), más `Gitleaks`. Los jobs con **PG real** son donde se
   certifica la durabilidad de las **reservas de salida** (§7.6) — **no** medida en local.
3. **Persistencia de la parada dura.** `HardKillSwitch` vive **en memoria**: un reinicio **olvida** que
   había un halt. Es un límite declarado, pero es el candidato natural a cierre en `AUTO-6`
   (Crash/Recovery): exige decidir **dónde** se persiste (JSONB de `sim_auto_positions` vs tabla propia) y
   **quién** la libera.
4. **Productor real de la liberación del halt.** `release_kill_switch` exige `reconciliation_ok=True` y
   **no tiene emisor automático** en el worker (el emisor de `RECONCILED` sigue sin existir, deuda de
   `AUTO-2`). Hoy un halt se libera por **API explícita**. Coherente con el diseño, pero significa que un
   halt **no se libera solo**.
5. **Productor real de frescura.** Solo `market_data` es un eje **activo**: `atr`/`volume` no tienen quien
   les declare la edad, así que van `unknown` y **no atan**. Poblar esos relojes desde el feed real es
   trabajo de la fase de datos, no de este parche.
6. **`force_protective_exits` sin cablear.** El flag existe con su semántica, pero el camino del worker no
   lo consulta: el default `True` es lo que corre. Si se quiere un **parón manual total** (congelar también
   las salidas) hay que cablearlo.
7. **Flip del gobernador a default ON** (`AUTO_ENGINE_SIM_V2_GOVERNOR=1`): sigue exigiendo el **número
   delante** (días medidos con datos reales) y firma del owner. Con OFF el camino V2 es byte-idéntico sin
   parada dura, así que **no hay prisa**, y lo que falta es de **producto**, no de código.
8. **Calibración de umbrales del gobernador** (deuda de `AUTO-3` slice 1, intacta): `min_liquidity_notional`
   nace en `0,0` (⇒ el eje de liquidez no ata salvo liquidez desconocida) y `restricted_edge_factor` en
   `2,0` (⇒ `ENTRY_RESTRICTED` veta a las candidatas del rango alcanzable).
9. **Deuda viva de `AUTO-2`** (no se toca aquí): el **veto de ATR** sigue OFF, el **productor del nivel de
   invalidación** no está cableado (`TradePlan` no lo manda) y el horizonte es por **plantilla**, no por
   estrategia.
10. **`PositionLedger` sigue siendo read-model sin tabla propia** y el `limit` de `list_applied` sigue
    siendo un **suelo** (deuda de `v2.40.5`, no de este parche).

---

## 4. Trampas medidas (no las repitas)

- **Verificar con una copia a mano de la invocación del CI mide OTRA COSA.** Es la trampa de esta fase, y
  está declarada en el §13 del pack: el primer `ruff` se corrió **sin** `--config pyproject.toml` y
  concluyó «2 avisos, ambos preexistentes en `HEAD`». Con la invocación **de la casa** eran **7 avisos, y
  los 7 eran de ficheros de este parche**. El flag de config cambia la clasificación first-party de `isort`
  y por tanto **qué bloques de imports considera desordenados**.
  **Cómo evitarlo:** medir con la invocación **extraída del YAML** (el runner
  `scripts/verify/offline_ci_run_yaml.py`) o, como mínimo, copiarla **con todos sus flags**. Y para
  distinguir «preexistente» de «introducido», **worktree limpio en `HEAD`** con la misma invocación — no
  `git show` por stdin, que **no** aplica la misma detección de rutas.
- **No confundir `EXIT_ONLY` de estado con `EXIT_ONLY` de banda.** Son **dos ejes con el mismo nombre y
  significado distinto**: el **estado operacional** `EXIT_ONLY` **no** liquida (veta aperturas); la **banda
  de drawdown** `EXIT_ONLY` **sí** liquida (entra por `risk_off`). Está cubierto por
  `test_exit_only_operational_state_does_not_liquidate` y es la pregunta más afilada del arranque del
  auditor (§4.6). **No lo "arregles" sin decidir el contrato primero.**
- **Una venta y una compra vivas del mismo instrumento se NETAN a 0 en `committed_positions()`.** Es
  deliberado (la venta va a cerrar la compra y no hay capital nuevo comprometido), pero significa que **la
  proyección puede ocultar una posición real** mientras la venta está en vuelo. Si la venta no se ejecuta,
  la proyección mentía. Es una pregunta abierta declarada (§4.11 del arranque), no un bug conocido.
- **`str(None or "") == ""` precede a cualquier ISO.** Es la trampa de ordenación de H6 y **sigue viva en
  cualquier otra clave de ordenación del repo**: si comparas fechas con `or ""`, las filas sin fecha se
  ordenan **primeras**, no últimas. Busca el patrón.
- **Un `0.0` "declarado" es la forma que toma un dato ininterpretable cuando pasa por un `max(0.0, …)`.**
  H3 y H2 son la misma trampa en dos sitios distintos. Si ves un `max(0.0, ...)` calculando un **riesgo**,
  sospecha.
- **`ruff --fix` antes de sellar, no después.** Los imports nuevos se acumulan desordenados en los ficheros
  grandes (`auto_simulation_worker.py`, `position_manager.py`, `portfolio_reservation.py`) y sin el fix
  el job `quality` va rojo por `I001`.

---

## 5. Freeze (congelado, no tocar sin motivo)

- **Comportamiento de `AUTO_ENGINE_SIM_V2=0`**: debe seguir siendo `v2.39.x`.
- **Comportamiento de `AUTO_ENGINE_SIM_V2_GOVERNOR=0`**: byte-idéntico a `v2.43.1` **sin parada dura**.
  Cualquier cambio ahí es un hallazgo.
- **`v2_43_governor_evidence.py`**: **byte a byte igual** y su `"bump"` se queda en `1.68.0-beta`. No lo
  "actualices".
- **Tabla del gobernador y sus umbrales** (`operational_governor.py`): **no se tocan** aquí.
- **`v0` del clasificador de régimen** (`discovery_market_regime`): inmutable, etiqueta a etiqueta.
- **`v2.43-beta` y `v2.43.1-beta` no se mueven**: son refs publicadas y auditadas.
- **Sin migración**: todo lo nuevo vive en memoria/JSONB; Alembic head en `042_portfolio_reservations`.
- **Los gates PG** y los ficheros PG en el `--ignore` de los jobs offline: un skip mudo no certifica.

---

## 6. Checklist de verificación antes de tocar la fase siguiente

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"
uv run pytest packages/py/analytics/tests/test_position_ledger.py \
              packages/py/analytics/tests/test_hard_kill_switch.py \
              packages/py/analytics/tests/test_data_freshness.py \
              packages/py/analytics/tests/test_exit_plan.py \
              packages/py/application/tests/test_auto_v2_entry.py \
              packages/py/application/tests/test_position_manager.py \
              apps/api-python/tests/test_auto_v44_exit_governance.py -q
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
```

Los dos bloques offline deben quedar verdes y las cifras deben cuadrar con el **delta `+40`** del §9.1 del
pack (`quality` **2031**, tag **2042**). El script de evidencia del gobernador debe salir **exit 0** y su
`git diff` **vacío**. Si algo cambia sin que nadie haya tocado su código, la primera sospecha es el
**entorno** (PG/DSN), no el test.

---

## 7. Siguiente fase

**Inmediato (cierre de este parche):** la **matriz de mutaciones** del §10 del pack (ya **medida**) y el
**sello** (§12). Es corto y acotado: no cambia código de producción.

**Después:** la línea de `AUTO` continúa con **`AUTO-4` — Portfolio Optimizer** según el
[roadmap](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) §6 (`V2.44` / `1.69.0-beta`): pasar de "TOP
oportunidades" a **mejor combinación de cartera** (el ranking deja de ser la decisión: la cartera elige el
conjunto). Nótese que el plan de trabajo de este parche **reutilizó la etiqueta «v2.44»** para Exit
Governance: si el roadmap se renombra, hazlo **explícito** en el pack de `AUTO-4` para que nadie audite dos
cosas con el mismo nombre — es exactamente la clase de colisión de nombres que este repo ya declaró en
`v2.43` (alias `MacroRegime`/`GovernorMarketRegime`).
