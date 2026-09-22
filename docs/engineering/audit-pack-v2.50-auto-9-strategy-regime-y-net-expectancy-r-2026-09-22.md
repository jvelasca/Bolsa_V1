# Audit-pack `AUTO-9` Strategy × Regime y net expectancy_R — `1.75.0-beta` (2026-09-22)

**Fase:** `AUTO-9` (línea AUTO) · **Bump:** `1.74.0-beta` → **`1.75.0-beta`** · **Migración:** **NO**
(Alembic head sigue en `044_auto_cycle_trace`) · **SHORT:** no · **UI nueva:** no · **Backfill:** no.
**Plan de la fase:**
[`plan-v2-50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md`](./plan-v2-50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md)
· **Relevo:** [`traspaso-relevo-post-v2.50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md`](./traspaso-relevo-post-v2.50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md)
**Sello:** commit de **código** `df2002e7` (25 ficheros, `+3775/−266`) + commit de **documentos de
fase** (este pack, el relevo y el índice). **Tag anotado** `v2.50-beta` → commit de documentos: los
tres documentos de fase viajan **dentro** del tag, como en `v2.47`, `v2.48` y `v2.49`.
`package.json` → **`1.75.0-beta`**. **CI real: 10/10 `success`** sobre el commit de código (§7).

---

## 0. Resumen: qué instala esta pasada

| #   | Deuda / premisa de partida                                                         | Estado        | Evidencia (medida)                                                  |
| --- | ---------------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------- |
| 1   | El `r_multiple` de un ciclo era un `None` **permanente**: nadie emitía denominador | CERRADO       | `cycle_risk.py` (M28/M29/M30)                                       |
| 2   | El coste no era un dato medible del informe                                        | CERRADO       | `cost_measurement` + `net_r_multiple` (M31)                         |
| 3   | «El régimen por ciclo está en el journal» (§4.3 del plan)                          | **CORREGIDO** | El journal del worker es **en memoria** ⇒ `regime_not_durable` (§4) |
| 4   | La asignación no podía pesar con R medido sin mezclar unidades                     | CERRADO       | eje por **POOL** + `auto9-v1` (§3)                                  |
| 5   | `strategy × regime` sin agregación (el cruce se inventaba o se ignoraba)           | CERRADO       | `by_regime` + `declared_regime` (§2)                                |
| 6   | El fail-closed podía confundir «no pude leer» con «la muestra no es decisoria»     | CERRADO       | degradación declarada (M32/M33) (§1)                                |
| 7   | `net_expectancy_R` y `regime` sin mapear en `StrategyHealth`                       | CERRADO       | `net_r_measurement` + régimen derivado del cruce (§3)               |

**Lo que esta pasada NO promete** (y quedó declarado, no escondido): el **régimen por ciclo sigue sin
ser durable**, porque el productor de ciclos escribe su journal en memoria. El hueco se **publica**
(`regime_not_durable`, y `cycles_without_regime` en el informe) y la costura (`regime_by_cycle`) ya está
lista para el día que exista productor durable.

---

## 1. El invariante: **medir o declarar, nunca inventar**

El módulo nuevo es `packages/py/application/src/bolsa_application/cycle_risk.py` (read-only, puro en el
ensamblado): ata por `cycle_id` el **denominador** de R y el **coste estimado**, que son exactamente los
dos datos que el informe `AUTO-7` no podía medir.

Cuatro reglas duras, **cada una con test**, y cada una con su mutación:

1. **Denominador UNO** (`cycle_risk.py:131`, `:144`). La reserva de **ENTRADA** (`side='buy'`) **más
   antigua** con `reserved_risk > 0`. Con varias candidatas se elige la más antigua y se **declaran**
   (`entryReservations`, nota `cycle_with_multiple_reservations`): se prohíbe repartir el riesgo entre
   varias, porque R es una razón contra **un** denominador, no una media de denominadores. → **M28** (2
   rojos).
2. **Las reservas LIBERADAS cuentan** (`cycle_risk.py:175`). Cuando un ciclo se cierra, su reserva de
   entrada ya no está viva: filtrar por `is_live` dejaría el denominador en `None` justo en los ciclos que
   **sí** tienen resultado. El llamante usa `list_by_cycle_ids` (vivas y liberadas). → test in-memory +
   **M29** (3 rojos).
3. **La ausencia se declara** (`CycleRisk.risk_amount = None` + nota `cycle_without_risk`). Nunca un `0`:
   el R de un riesgo cero es `inf`, no `0`. Y todo ciclo **pedido** aparece en el mapa, aunque no tenga
   reservas: una ausencia silenciosa sería «no lo miré», no «no lo hay». → **M30** (4 rojos).
4. **El régimen no se inventa** (`cycle_risk.py:60`). Hoy se publica `None` + `regime_not_durable`; el día
   que exista productor durable se pasa por `regime_by_cycle` y el hueco se cierra solo.

**El fail-closed cambia de forma, y se declara.** El plan (§5.1) preveía
`errors=["cycle_risk_read_failed"]` + `decisive = False`. Lo implementado **degrada sin afirmar**: una
lectura rota devuelve `None`, el informe recupera **exactamente** su forma `AUTO-7` y la salud de los
fills sigue mandando. Es más honesto que marcar `decisive = False`, que confundiría «no pude leer el
riesgo» con «la muestra no es decisoria», y no puede estrechar ni rotar a ciegas en ningún caso. Una
lectura **saturada** (tope `_V2_CYCLE_RISK_READ_LIMIT = 2000`, `auto_simulation_worker.py:230`) tampoco
veta: los ciclos que no cupieron quedan **sin** denominador —nunca con el de otro— y se registra un
`warning`. → **M32** (3 rojos) y **M33** (3 rojos).

---

## 2. El cálculo puro y la agregación `strategy × regime`

- `cycle_r(*, pnl, risk_amount, cost)` → `CycleR` (`auto_self_evaluation.py:353`, dataclass en `:326`):
  `r_multiple = pnl / risk_amount` y `net_r_multiple = (pnl − coste) / risk_amount`. Reglas: riesgo
  ausente, `0` o negativo ⇒ `None` (**nunca** `0`, nunca `inf`); coste ausente o incompleto ⇒ neto `None` +
  `cost_unmeasured` (`PARTIAL`); y `pnl = 0` **medido** ⇒ `0.0` (`COMPLETE`). El redondeo es `_round4`.
- `aggregate_by_regime` (`:1150`) agrupa por `(strategy_version, regime)` con la **misma** maquinaria de
  `_dedupe_cycles` (un ciclo repetido cuenta **una vez** y se declara) y `min_trades` **por celda** (90
  ciclos en 3 regímenes son celdas de 30). El régimen **ausente** es un cubo **propio** (`UNKNOWN`, también
  para `unknown`/`Unknown`) que no se reparte ni se suma a otro. Celdas en **orden canónico**, así que el
  cruce no depende del orden de entrada.
- `StrategyRegimeEvaluation` (`:669`) publica `expectancy_r`, `net_expectancy_r`, `win_rate`,
  `cycles_without_risk` y `cycles_without_cost`. **`decisive` NO cubre el R neto** (depende de un coste
  _estimado_): el consumidor exige `netRMeasurement == COMPLETE`.
- `declared_regime` (`:1193`) devuelve el par `(régimen, regime_undetermined)`: una celda decisiva con
  régimen ⇒ ese régimen; **dos** celdas decisivas, una `UNKNOWN` decisiva o ninguna celda ⇒ `UNKNOWN`. No
  se elige régimen a dedo.
- El cruce **no** se apropia del embudo (`funnel_not_dimensioned_by_regime`: el embudo durable no tiene
  dimensión de régimen y sigue en `byStrategy`) ni del R que el productor ya declaró.

---

## 3. El consumo en Adaptive: eje de evidencia **por POOL** y `auto9-v1`

- `StrategyHealth` (`auto_adaptive.py:214`) gana `net_r_measurement` y su `regime` deja de ser un literal:
  lo **deriva** del cruce `strategy × regime` del **mismo** informe (`from_evaluation` acepta
  `regime_cells`, que hilan `build_strategy_health` y `recommend_rotation`). `AdaptivePlan.evidence_for`
  publica `netExpectancyR` / `netRMeasurement` (`:376`).
- `recommend_allocation` elige **eje por POOL y nunca por fila** (`_allocation_weights`, `:495`): pesa con
  `net_expectancy_r` **solo** si está medido (`== COMPLETE` estricto) para **todo** el grupo que compite, y
  cae a `expectancy_currency` (comportamiento histórico) en cualquier otro caso. La razón es aritmética:
  `expectancy_currency` es absoluta y `net_expectancy_r` adimensional, así que mezclar pesos de los dos
  ejes sería un reparto sin sentido. Así un hueco de medición **no** puede sacar a nadie del numerador.
- El eje se **declara** en `AllocationPlan.evidence_axis` y viaja en `as_dict()`, con default histórico
  (un `AllocationPlan` construido a mano sigue significando lo mismo).
- `ADAPTIVE_POLICY_VERSION = "auto9-v1"` (`:107`): el contrato de evidencia cambió, y el sello viaja en
  `AdaptivePlan`, `as_dict()` y journal. La versión anterior (`auto8-v2`) **no** se reescribe.

**Mapear evidencia no mueve decisiones.** Test explícito de que añadir el cruce deja rotación y asignación
idénticas (`test_regime_cells_alone_do_not_move_rotation_or_allocation`), y test del criterio «con R no
medido **nada** cambia» comparando `multipliers` **y** `as_dict()` completos, sin R y con R `PARTIAL`.
Medir R mueve el reparto (`0.5 → 2/3`) y deja la rotación **byte-idéntica**.

---

## 4. Lo que NO se hizo, y por qué

**La premisa §4.3 del plan era falsa, y se corrige escrita (no borrada).** El payload de la decisión **sí**
lleva `cycleId` y las tres dimensiones del gobernador, y `decision_journal_entries` **sí** es durable —
pero **ese** journal es el del camino `plan_v2_tick`; quien ejecuta el ciclo en el motor AUTO simulado
(`auto_simulation_worker`) escribe en `_v2_journal`, que es una **lista en memoria**. Comprobado contra la
base real: no hay ninguna fila de decisión AUTO con `cycleId`, y `portfolio_reservations.cycle_id` /
`sim_fill_finance_context.cycle_id` están a `NULL` en lo ya sembrado.

Consecuencia de alcance, declarada: el **régimen por ciclo no es legible hoy**. Convertir ese journal en el
durable es trabajo del **worker**, no de un adaptador read-only: se declara como **deuda con nombre**, no
se rodea. Mientras tanto la evidencia viaja donde el camino ya la soporta: por **estrategia**
(`adaptiveEvidence`) y por **ciclo** en el informe (`by_regime`, `cycles_without_regime`,
`cycles_without_cost`).

**Tampoco se hizo** (heredado y sin cambio en esta fase): cooldown de pausa **en memoria** (se reinicia con
el proceso), ni UI nueva para el cruce.

---

## 5. Evidencia medida

**Tests nuevos:** `packages/py/application/tests/test_cycle_risk.py` (**21**) y
`apps/api-python/tests/test_auto_v50_auto9_cycle_risk_seam.py` (**7**).

**Bloques offline, con los targets extraídos del YAML** (`--with-pg-ignores`, PostgreSQL local levantado):

| Bloque (targets del YAML)                       | Total | Pasan | Rojos | Delta de la fase |
| ----------------------------------------------- | ----- | ----- | ----- | ---------------- |
| `quality` (50 targets, `python-ci.yml`)         | 2287  | 2287  | **0** | **+69**          |
| job `python` del tag (59, `release-tag-ci.yml`) | 2298  | 2298  | **0** | **+69**          |

El delta es la cuenta exacta de la fase: **+4** (lector `list_by_cycle_ids`) **+8** (cálculo puro) **+13**
(cruce) **+8** (`StrategyHealth`) **+8** (eje de asignación) **+21** (`cycle_risk`) **+7** (costura del
worker) = **69**, sobre las bases `v2.49` de 2218 / 2229. Con esto queda **cerrada** la discontinuidad que
§13.8 del plan dejó declarada: sus 2500/2511 eran el artefacto; con la misma extracción la serie cierra sin
residuo (2243/2254 + 44).

**Compuertas:** `ruff check … --config pyproject.toml` limpio · `mypy` **0 errores / 492 ficheros** ·
`import-linter` **4/4** · `analytics` **975 passed** (sin `test_vectorbt_optuna.py`: la DLL de `numba` está
bloqueada en esta máquina) · suites `application` afectadas **58 passed** · costura **7 passed**.

**Mutaciones: 33/33 muerden**, 0 no detectadas, 0 restauraciones fallidas y huella `git status` de los
ficheros tocados **idéntica** antes y después (`intacto: la sonda no altero el arbol`). Las seis nuevas:

| #   | Qué rompe                                          | Rojos |
| --- | -------------------------------------------------- | ----- |
| M28 | el denominador pasa a ser la reserva **más nueva** | 2     |
| M29 | una **venta** (riesgo `0`) entra como denominador  | 3     |
| M30 | un ciclo sin reservas **desaparece** del mapa      | 4     |
| M31 | el coste ausente se publica como **clave nula**    | 1     |
| M32 | el informe **ignora** la evidencia que le llega    | 3     |
| M33 | el worker **deja de leer** el riesgo por ciclo     | 3     |

**Registro en CI simétrico:** `test_cycle_risk.py` va **explícito** en los dos jobs (vive en
`packages/py/application/tests`, que no tiene pase de directorio en ninguno); la costura entra por el pase
de directorio de `apps/api-python/tests`.

---

## 6. Hallazgos operativos del tooling

1. **Una sonda de mutaciones puede dejar el mutante dentro del árbol.** Con `M16` (que muta
   `auto_v2_entry.py`), el `write_bytes` de restauración falló de forma **reproducible** con
   `OSError [Errno 22]` de Windows — con el fichero **limpio** y con el mismo par
   escritura/restauración funcionando aislado —, y **dos corridas abortaron** dejando
   `return best, ()` dentro del árbol (restaurado a mano con `git checkout`). La sonda ya no puede
   hacer eso: `_restore` reintenta con pausa, prueba un reemplazo atómico con `os.replace` y, **solo
   como último recurso**, usa `git checkout`… y **solo si el fichero está limpio en git** (si tuviera
   cambios sin commitear, **aborta declarándolo** en vez de descartar trabajo ajeno). Además admite
   **filtro por rótulo** (`… M28 M29`) para verificar un tramo sin arrastrar la matriz entera.
2. **`ruff format` NO es un invariante del repo.** La compuerta de CI es
   `ruff check … --config pyproject.toml` y `ruff format` no está en ningún job. Formatear en masa con
   la config de la raíz **reescribió 608 ficheros ajenos**. Se revirtió con criterio exacto (reconstruir
   `HEAD`, reformatear con la misma invocación y comparar: **610 analizados → 597 restaurados como ruido,
   13 conservados como míos**), dejando el `git status` de la fase en sus **24 entradas**. Regla: usar
   `ruff format` **solo** sobre los ficheros que uno ha tocado.
3. El mismo entorno (escribir muchos `.py` seguidos ⇒ `OSError [Errno 22]`) obliga a que toda
   restauración masiva vaya con reintento y `os.replace`.

---

## 7. Sello y CI

Commit de **código** **`df2002e7`** — `feat(v2.50): AUTO-9 Strategy x Regime y net expectancy_R (1.75.0-beta)`
—, **25 ficheros**, `+3775/−266` — **más** el commit de **documentos de fase** (este pack, el relevo y el
índice). **Tag anotado** `v2.50-beta` → commit de documentos, para que los tres viajen **dentro** del tag
como en `v2.47`–`v2.49`. Push a `main` en **fast-forward** (`d82d5440` → commit de documentos) y **tag
empujado de uno en uno** (lección de
`v2.49`: no usar `--follow-tags` con tags locales antiguos).

| Ref          | Workflow           | Run                                                                            |
| ------------ | ------------------ | ------------------------------------------------------------------------------ |
| `v2.50-beta` | **Release tag CI** | [`35723747813`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723747813) |
| `v2.50-beta` | Python CI          | [`35723747906`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723747906) |
| `v2.50-beta` | Frontend CI        | [`35723747879`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723747879) |
| `v2.50-beta` | Optimize lab       | [`35723747826`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723747826) |
| `v2.50-beta` | Fase 2 scientific  | [`35723747998`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723747998) |
| `main`       | Python CI          | [`35723745808`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723745808) |
| `main`       | Frontend CI        | [`35723745641`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723745641) |
| `main`       | Optimize lab       | [`35723745606`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723745606) |
| `main`       | Fase 2 scientific  | [`35723745751`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723745751) |
| `main`       | Gitleaks           | [`35723745931`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723745931) |

**10/10 `success`.** En `Release tag CI`, los diez jobs de decisión en verde (`python`
ruff/imports/mypy/pytest offline, `decision-spine`, `lifecycle-pg`, `dr-verify`, `a7-gate`, `frontend` con
`contract:check`, `playwright` mock, `shared`, `security`), con el único job **opt-in** de E2E integrado
omitido, como está diseñado.

---

## 8. Freeze (no tocar sin motivo)

- `AUTO_ENGINE_SIM_V2=0` ⇒ sigue comportándose como `v2.39.x`; `AUTO_ENGINE_SIM_V2_GOVERNOR=0` ⇒
  byte-idéntico a `v2.43.1` sin parada dura.
- `v2_43_governor_evidence.py` ⇒ **byte a byte igual**, `"bump"` en `1.68.0-beta`, exit 0.
- La tabla del gobernador y sus umbrales ⇒ **no** se tocan.
- `v2.49-beta` y anteriores ⇒ **no** se mueven: `auto8-v2` sigue siendo la política de los planes ya
  emitidos (los sellos antiguos siguen siendo auditables con la política que los produjo).
- `RiskAllocator` / `portfolio_decision_engine.py` ⇒ **no** se tocan (el borde `pct == 0.0` se queda como
  se selló en `v2.49`).
- Sin SHORT. Sin migración.
