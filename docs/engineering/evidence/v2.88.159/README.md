# Evidencia `v2.88.159-beta` — el dato de barra no se reutiliza vacío y la posición adoptada recupera su coste

## 1. Qué publica este sello

Cierra **W-158-1**, **W-158-2** y **W-158-3**: dos huecos de cableado del worker SIM y una cura de
proyección. **`Δ motor = 0`**, **`Δ decisión = 0`** con fuentes cargadas y **sin migración** (`head`
sigue `057_top3_opportunity_identity`).

## 2. W-158-1 — el cortocircuito por barra decidía con fuentes VACÍAS

`AutoSimRuntime.run_tick` recompone las fuentes de régimen/ATR en cada tick, pero
`reuse_bar_datum=True` saltaba `_v2_refresh_regime()` porque «el dato de barra ya estaba leído». La
instancia nueva llegaba vacía: `regime_by_symbol = {}` ⇒ todo símbolo caía en `entryRegime=UNKNOWN`
y el ATR real no aparecía nunca con `AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1`.

Medido el **2026-10-21** en `auto-window-1484e253`: **275 de 280** entradas evaluadas vetadas por
`regime_invalid` (mapa presente pero vacío), **0 propuestas y 0 fills** en 17+ ticks, con el
preflight declarando **37** símbolos operables.

**Corrección.** `DiscoveryRegimeSource.loaded()` / `AtrSource.loaded()` (públicas, `bool` sobre el
mapa cacheado) y `AutoSimulationWorker._v2_bar_datum_loaded()`: el turno relee cuando la instancia
delante no está cargada, aunque el dato de barra se reutilice. Una fuente sin sonda se da por
cargada (no se inventa I/O); una sonda que falla fuerza el refresco (fail-closed).

## 3. W-158-2 — la adopción sin proyección previa perdía el precio de entrada

En `_reconcile_before_trusting`, una posición adoptada por un motor estable sin proyección previa
(`prior is None`) heredaba `entry_price=None` (fila escrita **3 ms** antes del primer tick del
2026-10-21). Sin base de coste no hay stop, ni trailing, ni plan de salida: la posición vive y **no
puede cerrarse**.

**Corrección.** La base de coste **no se inventa**: se reconstruye del mismo fold contable que usa la
conciliación (`build_position_ledger` → `average_entry` de lo que queda abierto). Nuevo
`_canonical_entry_prices(events)` que normaliza las **dos** formas en que llegan las trazas
(`_AppliedFill` del libro en RAM y `AppliedFillFact` del lector canónico) con
`coerce_applied_fill_fact`.

## 4. W-158-3 — la proyección `OK` sin coste no se curaba nunca

El camino `REBUILT` solo se ejecuta cuando la **cantidad** diverge; una fila con `entry_price=NULL` y
cantidad correcta quedaba `OK` y nadie la tocaba. Nueva cura en el mismo acto de reconciliar: para
veredictos `OK` con `entry_price is None`, cantidad viva y coste recuperable del libro, se hace
`upsert` conservando protección/plan/atribución. **Sin** fills aplicados no se rellena nada y se
emite un `warning` que nombra la imposibilidad. `DIVERGENT`/`UNKNOWN` siguen vetando aperturas.

## 5. Verificación medida

Declarada en el `CHANGELOG` §`2.11.159-beta`: `apps/api-python/tests -k auto` **733 passed**;
`packages/py/application/tests` (entry/TOP3) + `packages/py/analytics/tests` **1365 passed**; nuevas
pruebas de regresión `test_v2_reused_bar_datum_never_trusts_a_fresh_empty_source`,
`test_v2_canonical_entry_prices_rebuild_adopted_cost_basis`,
`test_projection_without_cost_basis_is_healed_from_applied_fills`.

La verificación **independiente** de este árbol es la del CI del tag (§7) y el `freeze OK` de §6.

## 6. Freeze

| Elemento | Valor |
| --- | --- |
| Commit del tag | `fd8049c6` |
| `apps` | `f37b6da083f18e3b9f604ded4d680b0a53646814` |
| `packages` | `b33bf1e0a8876602b933da8d82b0fdc11298100d` |
| Etiqueta `commit` del pin | `41860d4c` (el freeze real son los dos tree hashes) |

## 7. Publicación

**Nota de honestidad (crítica).** Trabajado el **2026-10-21**, publicado el **2026-10-22** junto con
`.158` y `.160`. Tag **anotado y unsigned**, creado sobre el commit que ya contenía el árbol del
sello; sin reescritura de historia. Publicación diferida, no fabricación.

**Alcance de este documento.** El tag `v2.88.159-beta` apunta a `fd8049c6`, que **no** incluye este
README: se escribió al publicar y vive en el `tip` del árbol (commit `97d61cbc`). Cite este documento
por su ruta en `main`, no por el tag.

**Corrección de una predicción de este sello.** El `CHANGELOG` de `.159` anticipaba que el día
`20261021` cerraría como `HARD_ERROR` por el run detenido. El día se re-ejecutó con `--force` y cerró
**`MEDIDO` / `BLOCKED`**, sin `HARD_ERROR` (ver `evidence/v2.88.160`). La parte que se cumplió es la
que el gate mide: `measurableCycles = 0`.

## 8. Límites declarados

AUTO sigue **OFF**; la ventana sigue **`INCONCLUSIVE`**; `CONFIRMED` no se emite. No se backfillea
ningún día previo y las posiciones huérfanas no se adoptan.

## 9. CI del tag (post-publicación, medido)

Medido el **2026-10-22** sobre el `headSha` del tag, no sobre `main`:

| Workflow | Run | `headSha` | Conclusión |
| --- | --- | --- | --- |
| `Release tag CI` | [39815515824](https://github.com/jvelasca/Bolsa_V1/actions/runs/39815515824) | `fd8049c6` | **`failure`** (job `python`; el agregado `certify` cae en cascada) |

**Por qué falló.** `ruff` emitió `I001 Import block is un-sorted or un-formatted` en
`apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:34`: en el árbol `fd8049c6` el
bloque `position_lifecycle` precedía a `position_ledger`, y el orden lexicográfico exige lo contrario
(`ledger` < `lifecycle`). Los otros doce jobs pasaron, incluidos `lifecycle-pg`, `a7-gate`, `spine` y
`replay-repro`.

**Qué NO se hizo.** No se movió el tag ni se reescribió la historia para «arreglar» el rojo. El
defecto se corrigió **hacia adelante** en `.160` (`4a76d477`), cuyo árbol el CI mide verde
([run 39815515285](https://github.com/jvelasca/Bolsa_V1/actions/runs/39815515285)). La etiqueta
`v2.88.159-beta` sigue apuntando a `fd8049c6` y su run sigue en `failure`: la evidencia válida de
`.159` es su árbol y su freeze, no un CI verde que no existe.
