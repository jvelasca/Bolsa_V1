# Auditoría externa de `v2.79-beta` (`AUTO-MATERIAL-7`: OPERABILITY CENSUS)

> **AsOf:** 2026-09-27 · **Objeto:** tag **anotado** `v2.79-beta` (`e68d45dc`) → commit `0314199c` ·
> **Versión:** `2.04.0-beta` · **Base (diff):** `v2.78-beta` (`f8aa3697`, `2.03.0-beta`) ·
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) ·
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`).
> **Veredicto:** **APROBADO CON OBSERVACIONES — 0 bloqueantes** (1 hallazgo NUEVO: `H-4` LOW).
> **Método:** pasada **externa y adversaria** sobre un **clon temporal** del tag
> (`$env:TEMP\audit-v279`, **reutilizado** de un intento previo interrumpido por el proveedor),
> con el árbol **intacto** antes y después de la matriz de mutaciones (tree id **idéntico**).

## 1. Identidad del objeto (observada)

| Dato | Valor |
|---|---|
| Tag anotado (objeto) | `e68d45dc6d5b4737aa9f7100f4c975e9d1a3a88e` |
| Commit (`v2.79-beta^{commit}`) | `0314199c4f063583eb76c8dfafe23247ae373a38` |
| Tree id ANTES de la matriz | `df8fed61a82b35fddbef8d4095fda4141480355f` |
| Tree id DESPUÉS de la matriz | `df8fed61a82b35fddbef8d4095fda4141480355f` (**idéntico**) |
| `git status --porcelain` antes/después | vacío / vacío |
| `package.json` | `2.04.0-beta` ✔ |
| Alembic head | `046_fill_reference_mid` ✔ |
| Base `v2.78-beta` | tag `7d3a5e91` → commit `f8aa3697`, versión `2.03.0-beta` |
| Commit post-tag `96f52eba` (cita del CI) | **NO** es ancestro del tag (`merge-base --is-ancestor` → exit 1); **SÍ** es ancestro de `origin/main` (exit 0) |

El tag es **anotado**. La pasada corrió en un clon temporal; **nada** se escribió en el árbol de
trabajo ni en el historial (sin commits; sin ficheros nuevos en el repo del clon). El commit con la
cita del CI (`96f52eba`) vive **fuera** del tag, solo en `main`, como **declara** el proyecto (patrón
`v2.74`–`v2.78`): su workflow (`release-tag-ci.yml`) solo corre al empujar el tag, por lo que la cita
no puede habitar el commit del sello. **No es ocultación.**

## 2. Compuertas reproducidas (medidas, no heredadas)

| Compuerta | Comando | Resultado observado |
|---|---|---|
| `ruff` | `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| import-linter | `uv run --no-sync lint-imports --config packages/py/.importlinter` | `Contracts: 4 kept, 0 broken` (636 ficheros, 3441 dependencias) |
| `mypy` | `uv run --no-sync mypy … --follow-imports=silent` | `Success: no issues found in 505 source files` |
| `alembic` | `uv run --no-sync alembic heads` (en `packages/py/infrastructure`) | `046_fill_reference_mid (head)` |
| puros | `uv run --no-sync python -m pytest packages/py/application/tests/test_market_operability.py -q` | `48 passed` |
| matriz | `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` | **219/219**, restauración byte a byte, árbol intacto |

Las cinco compuertas **coinciden** con lo declarado. Los shims de consola no fallaron en esta pasada
(`ruff`/`lint-imports`/`mypy`/`pytest` corrieron tal cual); no hubo que recurrir a `python -m …`.

## 3. Diff `v2.78-beta..v2.79-beta` (20 ficheros)

```
CHANGELOG.md
apps/api-python/scripts/v2_44_mutation_audit.py
apps/api-python/scripts/v2_76_forward_market_material.py
docs/engineering/PROJECT_STATE.md
docs/engineering/arranque-agente-v2-79-…md
docs/engineering/arranque-auditor-v2-79-…md
docs/engineering/audit-pack-v2-79-…md
docs/engineering/auditoria-v2-78-…md
docs/engineering/deuda-p3-post-auditoria-v2.70-2026-09-26.md
docs/engineering/engineering-index-2026-08-03.md
docs/engineering/evidencia-auditoria-v2.78-2026-09-27.txt
docs/engineering/evidencia-ci-tag-v2.78-2026-09-27.txt
docs/engineering/evidencia-matriz-mutaciones-v2.79-219-2026-09-27.txt
docs/engineering/plan-v2-79-…md
docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md
package.json
packages/py/application/src/bolsa_application/auto_reason_codes.py
packages/py/application/src/bolsa_application/market_operability.py
packages/py/application/tests/test_market_operability.py
```

**Ningún** fichero de `.github/workflows/` cambia. **Ningún** fichero congelado cambia (ver §4).

## 4. Los 12 puntos del arranque del auditor

| # | Punto | Resultado | Evidencia |
|---|---|---|---|
| 1 | El freeze no se toca | **PASS** | `git diff --name-only v2.78..v2.79 -- auto_simulation_worker.py portfolio_decision_engine.py opportunity_ranker.py market_regime_gate.py paper_material_readiness.py` → **vacío**; `DATA_GATE_POLICY_VERSION == "auto15-v1"`; `ADAPTIVE_POLICY_VERSION == "auto18-v1"`; `TOP_N` default `5`; `aggregate_trial_regime` en fichero no tocado; umbrales `min cycles 32`, `folds 3`, `min_is 8`, `min_oos 4`, `min_episodes 2` en ficheros **fuera del diff** |
| 2 | `H-1` censo de ENTRADA | **PASS** | `collect_journal_reasons(entries, *, events)` es la **única puerta**; el runner la llama con `{ENTRY_DECISION_EVENT}` (`auto_entry_decision`); `_AUDIT_REVERSAL_DAY` → `vetoCounted == vetoes == 2`, `other` **vacía** (re-derivado, §6) |
| 3 | `H-1` canal de posición publicado | **PASS** | `positionEventByCode`/`positionEventCounted` en la fila; el render añade `eventos/posicion: … (NO son vetos)` **solo si existe**; re-derivado: `protect_requested=1` publicado y fuera del histograma de vetos |
| 4 | `H-1` compatibilidad legacy | **PASS** | Fila legacy mezclada: `vetoCounted == 2`, `other` vacía, `nonVetoByCode` incluye `protect_requested` (vía `NON_VETO_REASON_CODES ⊇ POSITION_ATTRIBUTION_REASONS`) |
| 5 | `H-2` contrato exhaustivo de TODOS los dueños | **PARCIAL** | El test recorre los 10 dueños listados y pasa; **pero** el vocabulario de rechazo pre-ranqueo de `auto_v2_entry` (`signal_duplicate`, `signal_stale`, `signal_identity_missing`, `signal_superseded_by_candidate`, `signal_distinct_strategy_not_representable`) alimenta eventos `auto_entry_decision` (población del censo) y **no** está declarado → cae en `other` e infla `vetoCounted`. **H-4** |
| 6 | `H-3` disjunción | **PASS** | `VETO_BUCKET_BY_REASON ∩ NON_VETO_REASON_CODES == ∅` (re-derivado `True`); `POSITION_ATTRIBUTION_REASONS` **excluye** `reservation_failed`/`reservation_unmeasurable`/`reservation_already_live`, que siguen siendo VETO con familia `risk` |
| 7 | Contrato de eventos pined | **PASS** | `test_position_event_constants_match_the_producer_payloads`: `ENTRY_DECISION_EVENT == EVENT_ENTRY_DECISION`, los dos eventos de posición en `POSITION_JOURNAL_EVENTS`, y un `build_position_management_journal_entry` real emite un evento del conjunto; el **lector no edita** al productor (productor no está en el diff) |
| 8 | Sin migración y sin umbrales movidos | **PASS** | `alembic heads = 046_fill_reference_mid`; `min cycles 32`, `folds 3`, `min_is 8`, `min_oos 4`, `min_episodes 2` en ficheros no tocados; `DATA_GATE_POLICY_VERSION = auto15-v1` |
| 9 | Mutaciones `M214`–`M219` muerden/restauran | **PASS** | Re-ejecutada la matriz completa: **219/219**, `M214`–`M219` **muerden** (rojos en los tests citados) y restauran **byte a byte**; tree id idéntico; `git status --porcelain` vacío |
| 10 | CI sin huecos nuevos | **PASS** | `test_market_operability.py` **explícito** en el job `quality` de `python-ci.yml` (línea 327) y en el job `python` de `release-tag-ci.yml` (línea 534); **ningún** workflow en el diff; job `python` del tag sube **+11** (2960 → 2971) con skips **sin moverse** (37=37); `quality` 2949 → 2960 con skips 40=40 |
| 11 | Sonda I/O read-only | **PASS** | `v2_77_market_operability.py` **no** está en el diff; sin imports de `psycopg`/`asyncpg`/`postgres`/`create_engine`/`sqlalchemy`; su docstring declara "read-only, sin PostgreSQL" |
| 12 | El runner no escribe material por su cuenta | **PASS** | `_journal_reasons`/`_journal_position_reasons` solo **leen** `worker._v2_journal` en memoria; el único `open(..., "w")` es `--out` (línea 810); `--preflight-only` retorna antes de sembrar cuenta / commitear |

## 5. Hallazgos nuevos

### H-4 — LOW — El contrato exhaustivo de dueños (`H-2`) no cubre el vocabulario de rechazo de señal pre-ranqueo de `auto_v2_entry`

**Qué.** `plan_v2_tick` (`packages/py/application/src/bolsa_application/auto_v2_entry.py`) journaliza
rechazos **antes** del ranking y de la decisión con el **mismo** evento de entrada
(`"event": "auto_entry_decision"`) que consume el censo:

* `_signal_rejection` → `signal_identity_missing`, `signal_duplicate`, `signal_stale` (líneas ~2030-2058);
* `_superseded_candidate_entry` → `signal_superseded_by_candidate` (línea ~2023);
* colisión de estrategias distintas → `signal_distinct_strategy_not_representable` en `decision.reason_codes` (líneas ~1410-1414, cast a `DecisionReasonCode`).

Estas entradas se incorporan a `plan.journal_entries` (`*superseded_entries`, `*blocked`, `*journal`) y
de ahí a `worker._v2_journal`, que es exactamente lo que el runner agrega con
`collect_journal_reasons(..., events={ENTRY_DECISION_EVENT})`.

**Por qué importa.** El plan `v2.79` afirma (corolario 3) que la partición
`VETO_BUCKET_BY_REASON ∪ NON_VETO_REASON_CODES` es **exhaustiva sobre TODO el vocabulario que puede
llegar a `reasonCodes`**. Estos cinco códigos llegan y **no** están declarados: caen en `BUCKET_OTHER`
y **suman a `vetoCounted`**. Re-derivado en el clon:

```
VETO_BUCKET_BY_REASON ∩ {los 5 signal_*} == ∅  y  NON_VETO_REASON_CODES ∩ {los 5} == ∅
build_operability_record({"journalReasons": ["signal_duplicate:2", …],
                          "turnTotals": {"vetoes": 0, …}})  →  vetoCounted == 10, other no vacía
```

`test_every_owner_reason_code_is_declared_exactly_once` construye su conjunto `_OWNER_JOURNAL_CODES`
**a mano** (no lo descubre de los productores), y ese conjunto omite estas constantes; por eso el test
**pasa** aunque la partición no sea exhaustiva sobre el vocabulario real. Es el **mismo tipo de defecto**
que `H-1`/`H-2` (lectura, no decisión), pero de menor alcance: el fallback (`other`, **contado**) mantiene
el dato **visible**, ningún conteo se descarta y el cuadre `vetoCounted == vetoes` de los fixtures no se
ve afectado porque estos códigos no aparecen en ellos.

**Impacto.** En un día con rechazos pre-ranqueo (p. ej. `signal_duplicate`, frecuente cuando el worker
re-emite barra), `vetoCounted` puede exceder `vetoes` y `other` deja de estar vacía. **No** invalida el
sello: es lectura. **No** hay pérdida de dato ni cambio de decisión.

**Estado del hallazgo.** `H-2` **tal como quedó acotado en la auditoría de `v2.78`** (los dueños allí
nombrados) queda cerrado; lo que **no** queda cerrado es la invariante más fuerte que la propia fase
`v2.79` declara (exhaustividad sobre todo el vocabulario). Se registra como hallazgo **nuevo** `H-4`,
severidad **LOW**, para la fase siguiente.

## 6. Re-derivación independiente (no confiada a la evidencia persistida)

Ejecutada en el clon (`build_operability_record` con las fixtures reconstruidas a mano):

```
[H-1 reversal] vetoes=2 vetoCounted=2 other={} nonVetoCounted=4 positionEventCounted=1
               positionEventByCode={'protect_requested': 1}
[H-1 render ] eventos/posicion: protect_requested=1 (NO son vetos)
[H-1 legacy ] vetoCounted=2 other={} nonVetoByCode={'approved':3, 'protect_requested':1}
[H-3 disjoint] True
[point5      ] los 5 signal_* : (en VETO_BUCKET=False, en NON_VETO=False) → other / contados
```

El **día operado** (no el smoke) demuestra `H-1`: `vetoCounted == vetoes == 2` y `other` vacía. La
`other` vacía del smoke **no** prueba nada (trampa conocida, correctamente declarada por el proyecto).

## 7. CI en remoto (observada con `gh`)

* **`Release tag CI` `36309108865`** (branch `v2.79-beta`, HEAD `0314199c`): `completed / success`.
  10 jobs `success` (`frontend`, `security (gitleaks)`, `shared`, `playwright (mock E2E)`, `python`,
  `decision-spine`, `dr-verify`, `lifecycle-pg`, `a7-gate`) + `certify` `success`;
  `playwright (integrated E2E, opt-in)` **skipped**.
* Job `python` del tag (`108591476815`): `2971 passed, 37 skipped`; `All checks passed!`;
  `Contracts: 4 kept, 0 broken.`; `Success: no issues found in 505 source files`.
* Sobre el mismo commit/tag: `Python CI` `36309108894` (job `quality` `108591476873`:
  `2960 passed, 40 skipped`, ruff `All checks passed!`, mypy `505`), `Frontend CI` `36309108916`,
  `Optimize lab` `36309108867`, `Fase 2 scientific` `36309108863` — todos `success`.
* En `main`: `Python CI` `36309104906` (`quality` + 4 jobs PG `success`), `Frontend CI` `36309104815`,
  `Optimize lab` `36309104777`, `Fase 2 scientific` `36309104818`, `Gitleaks` `36309104775` — `success`.
* **Skips sin moverse**: tag `37 = 37`; `quality` `40 = 40`. **+11** casos nuevos en ambos
  (`2960 → 2971`; `2949 → 2960`).

## 8. Lo que NO se pudo correr (declarado, nunca asumido)

* **PostgreSQL local**: el entorno no tiene PG y la auditoría **no** lo levantó; las suites
  `lifecycle-pg`/`decision-spine`/`a7-gate`/`dr-verify` se verificaron **por su resultado en CI**
  (success), no reproducidas en local. → **NO REPRODUCIDO EN LOCAL**.
* **Material PAPER real / ventana ≥4 días**: no existe en el clon (`operability_runs/` está
  gitignoreado). La tabla de operabilidad se re-derivó con **fixtures reconstruidas** (día operado,
  reversión, legacy), no desde un journal real. → **NO VERIFICADO** (y **no puede afirmarse** que
  `P3-2`/`P3-3` estén cerradas ni que exista material diverso: **no hubo ventana**).
* La deuda PG pre-existente `apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py`
  (`assert 17 == 26`) se salta en CI sin Postgres y es **ajena al diff** (no está en los 20 ficheros).

## 9. Observaciones de proceso

* **`OBS-5` sigue declarada** (el parser descarta conteos `<= 0` ante un mapping crudo); no es
  regresión de esta fase.
* **Cambio de familia declarado** (`optimizer_*`, `adaptive_strategy_paused`,
  `reservation_unmeasurable`, `reservation_already_live`: `other` → familia real): es mejora de
  lectura, **no** una regresión de `other`.
* **Declarado NO HECHO por el proyecto** (no son hallazgos): la ventana de ≥4 días de calendario
  (`P3-2`/`P3-3` **ABIERTAS**), el prerrequisito de `pairActive` (estrategia `ACTIVE` + `EdgeReport`),
  el pin de `--account-id` y el scheduler de barras.

## 10. Veredicto

**APROBADO CON OBSERVACIONES — 0 bloqueantes.** El núcleo de la fase (`H-1`) queda **demostrado**:
el censo mide **solo** decisiones de entrada, el canal de posición se **publica** (no se descarta),
la compatibilidad legacy se sostiene, y la disjunción veto/no-veto está **guardada** por test. El
freeze está intacto, no hay migración ni umbrales movidos, `M214`–`M219` **muerden** y restauran byte
a byte, y la CI del tag está **GREEN** con los skips **sin moverse**. La única salvedad es `H-4`
(LOW): la invariante de **exhaustividad** del contrato de dueños no cubre el vocabulario de rechazo
pre-ranqueo de `auto_v2_entry`, que cae en `other` y engorda `vetoCounted`. Lo que **no** puede
afirmarse: que `P3-2`/`P3-3` estén cerradas, ni que exista material de mercado diverso (no hubo
ventana).

## 11. Evidencia cruda

[`evidencia-auditoria-v2.79-2026-09-27.txt`](./evidencia-auditoria-v2.79-2026-09-27.txt): identidad
del objeto, salidas de las cinco compuertas, diff, la re-derivación independiente, el resumen de la
matriz **219/219** con la mordida de `M214`–`M219`, tree antes/después, `git status --porcelain` y la
CI remota.
