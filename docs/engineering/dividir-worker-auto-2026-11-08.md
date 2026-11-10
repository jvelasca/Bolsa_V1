# Dividir `auto_simulation_worker.py` — 2026-11-08

Cierre de `p2-worker` (Fase 2.1 del plan de remediación). El objetivo era mover el worker de
un fichero de 10.593 líneas con una clase de ~7.600 a módulos por tema **sin cambiar el
motor** (`Δ motor = 0`), con `window:freeze` y la batería completa como red.

## Resultado

| Módulo | Líneas | Contenido |
|---|---:|---|
| `auto_simulation_worker.py` (facade) | 2.813 | superficie pública + clase ensamblada + 18 métodos anclados |
| `auto_worker_shared.py` | 1.023 | constantes, DTOs, helpers puros y `logger` |
| `auto_worker_price.py` (`_PriceMixin`) | 696 | precio, barras, régimen, ATR, coste |
| `auto_worker_state.py` (`_StateMixin`) | 1.448 | estado durable, journal, auditoría, proyecciones |
| `auto_worker_safety.py` (`_SafetyMixin`) | 1.881 | kill switch, reconciliación, reservas, gates |
| `auto_worker_execution.py` (`_ExecutionMixin`) | 1.855 | fills, stops, gaps, adopción, plan de tick |
| `auto_worker_runtime.py` | 1.944 | composición de fuentes/sinks, arranque y loop |

`AutoSimulationWorker(_PriceMixin, _StateMixin, _SafetyMixin, _ExecutionMixin)` conserva
`__init__`, `auto_turn`, `real_turn`, `persistent_turn`, `run_until_flat` y 13 métodos más.
**Fichero 10.593 → 2.813 líneas** (objetivo `< 3.000` cumplido).

## Cómo se garantiza `Δ motor = 0`

- El split **resuelve 185 métodos por el MRO** del facade (18 propios + 33 `_PriceMixin` + 47
  `_StateMixin` + 50 `_SafetyMixin` + 37 `_ExecutionMixin`), **sin colisiones** de nombre. Frente a los
  **183** métodos del fichero único previo: **0 ausentes**, **3** con el cambio declarado y **2** nuevos
  (ver errata al final). La comprobación reproducible es una **comparación AST** por nombre y cuerpo
  normalizado; el antiguo verificador de `inspect.getsource` fue **temporal y no está versionado**.
- Los helpers de módulo, dataclasses y constantes también se movieron a `auto_worker_shared` sin
  reescritura, comprobados con el mismo script temporal que la errata describe.
- El único cambio de código en la cola de runtime es el import local de
  `AutoSimulationWorker` en su único punto de construcción, para evitar el ciclo de import
  (el facade importa el runtime para re-exportarlo).
- `logger` conserva el nombre `bolsa_api.background.auto_simulation_worker`, así el filtrado
  de logs por nombre no cambia.
- El facade mantiene la **superficie pública completa** (`# ruff: noqa: F401`): cualquier
  `from bolsa_api.background.auto_simulation_worker import <nombre>` sigue funcionando, y
  `monkeypatch.setattr(worker_module, "<seam>", ...)` sigue funcionando para los seams del
  motor (ver más abajo).

## Anclajes deliberados en el facade

Los tests de caracterización parchean globals **a través del módulo worker** y luego esperan
que el camino productivo los use. Si el método que lee ese global se muda, el parche deja de
verse. Por eso quedan en el facade los métodos que leen:

`submit_simulated_order`, `make_closed_bar_loader`, `assess_data_gate`,
`build_adaptive_plan`, `protection_exit_reason`/`protection_exit_fraction`,
`read_account_book_equity`, `_V2_CYCLE_RISK_READ_LIMIT`, `_POSITION_JOURNAL_RETRY_CAP`,
`_watch_symbols`, `bar_tick`, `last_closed_bar_day`, `plan_v2_tick`.

Eso explica los 18 métodos del facade: es el precio de no reescribir 15 tests de costura.

## Límites declarados

- **La clase del facade mide 2.376 líneas** (objetivo del plan: `≤ 1.500`). No se alcanza sin
  mover esos 18 métodos anclados, y moverlos rompe los parches por módulo de los tests. Se
  deja declarado en vez de forzar el número.
- Con 4 slices, `_SafetyMixin` (1.705) y `_ExecutionMixin` (1.675) tampoco bajan de 1.500: la
  partición temática del plan agrupa reconciliación y adopción, que son las zonas más densas.
  Para bajar de 1.500 haría falta subdividir en más de cuatro slices.
- `mypy` **no se pudo ejecutar en este entorno** (Application Control bloquea el binario,
  `os error 4551`). Las mixins llevan `# mypy: disable-error-code="attr-defined"` porque los
  atributos de instancia se declaran en el `__init__` del facade; el resto de códigos sigue
  activo cuando el binario esté disponible.
- Tres tests que espiaban la composición (`_compose_price_source`, `_compose_atr_source`,
  `_compose_regime_source`, `_compose_evidence_source`, `make_closed_bar_loader`) ahora
  parchean `auto_worker_runtime`, que es donde viven. El aserto no cambió.

## Verificación ejecutada

- `uv run ruff check packages/py apps/api-python --config pyproject.toml` → limpio.
- `uv run lint-imports --config packages/py/.importlinter` → 4 contratos KEPT.
- `pytest apps/api-python/tests` → **1.805 passed, 7 skipped**.
- `pytest packages/py/{domain,market,application,analytics}/tests` → **5.094 passed, 5 skipped**.
- `pnpm window:freeze` → `freeze OK` (los tree hashes pineados no se mueven con el working tree).
- `pnpm window:test` → 70/70.
- Comparación AST método a método (ver errata): **183 → 185**, **0 ausentes**, **3** cuerpos con el
  cambio declarado, **2** nuevos, **0** colisiones.

## Deuda residual (fuera de este slice)

- Subdividir `_SafetyMixin`/`_ExecutionMixin` si se quiere cumplir `≤ 1.500` por clase.
- Los seams anclados al facade se pueden desanclar cuando los tests parcheen el módulo dueño;
  entonces el facade puede quedarse solo con `__init__` y los cuatro turnos.

## Errata (2026-11-10) — el verificador fue efímero y la cifra «185/185 verbatim» se retira

La auditoría independiente de `v2.88.187-beta` marcó como mayor (`M-1`) que la afirmación «185 métodos
movidos **verbatim**, 0 ausentes, 0 distintos» **no es reproducible desde el árbol**: el script que la
producía comparaba `inspect.getsource` por MRO, se ejecutó una vez y **no se versionó**, así que no corre
en CI ni puede reconstruirse desde el tag.

Medición reproducible sobre los commits del split (`cc1775de^` → `cc1775de`), emparejando por nombre y
cuerpo normalizado:

```text
pre-split AutoSimulationWorker.methods = 183
split facade+mixins resolved by MRO  = 185
by class: AutoSimulationWorker=18, _PriceMixin=33, _StateMixin=47, _SafetyMixin=50, _ExecutionMixin=37
missing = 0 []
different = 3 ['_settle', '_v2_governor_drawdown_pct', '_v2_snapshot']
added = 2 ['_v2_account_drawdowns', '_v2_account_max_drawdown_pct']
name collisions = 0 []
```

Las **3** diferencias son features declaradas del sello —`_settle` añade `created_at=self._time` al fill
y `_v2_governor_drawdown_pct`/`_v2_snapshot` extraen el cálculo a `_v2_account_drawdowns()` para publicar
`max_drawdown_pct`, con el gate **OFF** por defecto—, no un cambio encubierto del motor. Por tanto la
frase correcta es la de «Cómo se garantiza» arriba: **185 métodos resueltos por el MRO, 0 ausentes, 3 con
el cambio declarado y 2 nuevos**, sin usar la palabra «verbatim» ni la cifra «185/185».

Cierre completo: [cierre-auditoria-independiente-v2.88.187-beta-2026-11-10.md](./cierre-auditoria-independiente-v2.88.187-beta-2026-11-10.md)
§4. El tag `.187` **no** se re-etiqueta.
