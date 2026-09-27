# Auditoría externa de `v2.78-beta` (`AUTO-MATERIAL-6`: OPERABILITY ACCOUNTING)

> **AsOf:** 2026-09-27 · **Objeto:** tag **anotado** `v2.78-beta` → commit `f8aa3697` ·
> **Versión:** `2.03.0-beta` · **Base (diff):** `v2.77-beta` (`2.02.0-beta`) ·
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**)
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`).
> **Veredicto:** **APROBADO CON OBSERVACIONES — 0 bloqueantes** (1 hallazgo MEDIUM residual, 2 LOW).
> **Método:** pasada **externa y adversaria** sobre un **clon fresco** del tag, con el árbol
> **intacto** antes y después de la matriz (tree id idéntico).

## 1. Identidad del objeto (observada)

| Dato | Valor |
|---|---|
| Tag anotado (objeto) | `7d3a5e91f60c40b4f3c547679eea995722b3fe5f` |
| Commit (`v2.78-beta^{commit}`) | `f8aa3697247d48d9f7f6fc918d3fa3afd1132e53` |
| Tree id ANTES de la matriz | `93d8b8f062010f8b02d0585792124692859d44cd` |
| Tree id DESPUÉS de la matriz | `93d8b8f062010f8b02d0585792124692859d44cd` (**idéntico**) |
| `git status --porcelain` antes/después | vacío / vacío |
| `package.json` | `2.03.0-beta` ✔ |
| Alembic head | `046_fill_reference_mid` ✔ |
| Base `v2.77-beta` | tag `22da1bb0` → commit `ade1df58`, tree `6ec1c4c3`, versión `2.02.0-beta` |

El tag es **anotado**. La pasada corrió en un clon temporal; **nada** se escribió en el árbol de
trabajo ni en el historial del clon (sin commits).

## 2. Compuertas reproducidas (medidas, no heredadas)

| Compuerta | Comando | Resultado observado |
|---|---|---|
| `ruff` | `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| import-linter | `uv run --no-sync lint-imports --config packages/py/.importlinter` | `Contracts: 4 kept, 0 broken` (636 ficheros, 3441 dependencias) |
| `mypy` | `uv run --no-sync python -m mypy … --follow-imports=silent` | `Success: no issues found in 505 source files` |
| `alembic` | `uv run --no-sync alembic heads` (en `packages/py/infrastructure`) | `046_fill_reference_mid (head)` |
| puros | `uv run --no-sync python -m pytest packages/py/application/tests/test_market_operability.py -q` | `37 passed` |
| matriz | `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` | **213/213**, restauración byte a byte ×213, árbol intacto |

**Desviación declarada.** Los shims de consola `pytest`/`mypy` fueron bloqueados por el control de
aplicaciones de Windows (`os error 4551`); ambas compuertas se corrieron vía `python -m …` con los
mismos intérpretes/paquetes y los mismos resultados. `ruff`/`lint-imports` corrieron tal cual.

**Mordida de las mutaciones nuevas.** `M211` enrojece `test_operated_day_accounts_only_pure_vetoes`,
`test_render_declares_the_non_vetoes_of_an_operated_day`, `test_split_journal_reasons_*`; `M212`
enrojece los cuatro casos de ausencia (`test_state_unknown_*`, `test_a_truncated_payload_*`); `M213`
enrojece el cuadre del día operado y el canal publicado. La mordida es **genuina** (no tautológica):
`M211` elimina la rama `if code in NON_VETO_REASON_CODES`, `M212` elimina los dos guardias de
ausencia y `M213` sustituye la acumulación del no-veto por un `continue`; el diff de la sonda es
`+30/−0` y ninguna otra mutación cambió.

## 3. Diff `v2.77-beta..v2.78-beta` (20 ficheros)

```
M  CHANGELOG.md
M  apps/api-python/scripts/v2_44_mutation_audit.py
M  docs/engineering/PROJECT_STATE.md
A  docs/engineering/arranque-agente-v2-78-…md
M  docs/engineering/arranque-auditor-v2-77-…md
A  docs/engineering/arranque-auditor-v2-78-…md
M  docs/engineering/audit-pack-v2-77-…md
A  docs/engineering/audit-pack-v2-78-…md
M  docs/engineering/deuda-p3-post-auditoria-v2.70-2026-09-26.md
M  docs/engineering/engineering-index-2026-08-03.md
A  docs/engineering/evidencia-ci-tag-v2.77-2026-09-26.txt
A  docs/engineering/evidencia-matriz-mutaciones-v2.78-213-2026-09-27.txt
A  docs/engineering/evidencia-operabilidad-v2.78-2026-09-27.txt
A  docs/engineering/plan-v2-78-…md
M  docs/engineering/traspaso-relevo-post-v2-77-…md
A  docs/engineering/traspaso-relevo-post-v2-78-…md
M  package.json
M  packages/py/application/src/bolsa_application/auto_reason_codes.py   (+7/−0)
M  packages/py/application/src/bolsa_application/market_operability.py  (+68/−7)
M  packages/py/application/tests/test_market_operability.py             (+123/−6)
```

**Ningún** fichero de `.github/workflows/` cambia. **Ningún** fichero congelado cambia.

## 4. Los 12 puntos del arranque del auditor

| # | Punto | Resultado | Evidencia |
|---|---|---|---|
| 1 | El freeze no se toca | **PASS** | `git diff --name-only v2.77..v2.78 -- auto_simulation_worker.py paper_material_readiness.py portfolio_decision_engine.py opportunity_ranker.py market_regime_gate.py` → vacío; `DATA_GATE_POLICY_VERSION == "auto15-v1"`; `TOP_N`/`aggregate_trial_regime` intactos (sus ficheros no están en el diff) |
| 2 | `P3-6` contabilidad de vetos puros | **PARCIAL** | El cuadre y `other` vacía se sostienen en el fixture `_OPERATED_DAY`; **pero** otros motivos de gestión de posición siguen cayendo en `other` → **H-1** |
| 3 | El no-veto no se pierde; desconocido se cuenta | **PASS** | `nonVetoByCode`/`nonVetoCounted` publicados; `test_unknown_reason_is_counted_in_other_and_never_dropped`; `M207` muerde |
| 4 | `P3-7` ausencia fail-closed | **PASS** | `operability_state` comprueba la ausencia primero; `{}`→`unknown`, sin `turnTotals`→`measured=False`→`unknown`, sin `proposals`/`vetoes`→`unknown`; `M212` muerde 4 tests |
| 5 | Contrato del dueño exhaustivo | **PARCIAL** | Exhaustivo y exclusivo **sobre `DecisionReasonCode`** (26 literales; ninguno sin declarar ni en ambos), pero **no** sobre el resto de dueños que alimentan el mismo `journalReasons` → **H-2** |
| 6 | Compatibilidad de lectura (filas legacy) | **PASS** | `measured` ausente ⇒ `True`; los casos legacy siguen dando `no_signal`/`vetoed`/`operated` (inferido del código, no ejercitado contra un journal real) |
| 7 | El render declara lo que no es veto | **PASS** | `_non_veto_summary` devuelve `""` si no hay no-vetos; el render solo añade la línea si existe |
| 8 | Sin migración y sin umbrales movidos | **PASS** | head `046_fill_reference_mid`; `min cycles 32`, `folds/min_is/min_oos/min_episodes` en ficheros no tocados; `DATA_GATE_POLICY_VERSION = auto15-v1` |
| 9 | Mutaciones `M211`–`M213` muerden y restauran | **PASS** | 213/213, byte a byte, tree id idéntico |
| 10 | CI sin huecos nuevos | **PASS** | `test_market_operability.py` sigue **explícito** en `python-ci.yml` (job `quality`) y `release-tag-ci.yml` (job `python`); ningún workflow en el diff; 25 → 37 (+12) |
| 11 | La sonda I/O sigue read-only | **PASS** | `v2_77_market_operability.py` no está en el diff; sin imports de `psycopg`/`postgres`/`asyncpg`/`create_engine` |
| 12 | Rango del diff es solo de la fase | **PASS** | 20 ficheros `feat`/`docs`/versión/sonda; sin arrastre post-tag (a diferencia de `v2.77`) |

## 5. Hallazgos nuevos

### H-1 — MEDIUM — `P3-6` solo está **parcialmente** cerrado: los motivos de gestión de posición siguen inflando `vetoCounted` y cayendo en `other`

`NON_VETO_REASON_CODES` (`market_operability.py`) declara solo `approved` ∪ `DAY_EXIT_REASONS` ∪
`POSITION_SKIP_REASONS`. Pero el lector consume `journalReasons`, que el runner agrega sobre
**todas** las entradas del journal (`_journal_reasons`, `v2_76_forward_market_material.py`), y
`_journal_position_event` (`auto_simulation_worker.py`, **congelado**) anexa eventos de gestión con
su propio `payload["reasonCodes"]` (evento `auto_position_management`).

Códigos emitidos por esa vía que **no** están declarados y por tanto siguen cayendo en `other` y
sumando a `vetoCounted`: `protect_requested`, `stop_ratchet_applied`, `stop_ratchet_rejected`,
`protection_missing`, `atr_geometry`, `lifecycle_transition_rejected`, `lifecycle_state_unverified`,
`reconciliation_required`, `no_mark_data`, `fill_not_materialized`, `reservation_created`,
`reservation_released_fill`.

Demostración (ejecutada en el clon, sin editar ficheros):

```
journalReasons = ["regime_invalid:2", "approved:3", "risk_exit:1", "protect_requested:1"]
turnTotals     = {"vetoes": 2, "proposals": 3, "fills": 3, "closed": 1}
=> vetoes=2  vetoCounted=3  other={'protect_requested': 1}  nonVeto={'approved':3, 'risk_exit':1}
```

Es **exactamente** el criterio de reversión declarado para `P3-6` en el registro de deuda
(`deuda-p3-…:240`), y es alcanzable en el **caso de uso principal** del instrumento (un día con
posiciones vivas gestionadas). El smoke sellado **no** lo ejercita (0 fills ⇒ sin eventos de
gestión) y el fixture `_OPERATED_DAY` tampoco, de modo que **no puede falsar** —pero tampoco
demostrar— la propiedad general.

**Impacto.** El censo por familias vuelve a leerse como **cota superior** en los días que sí operan,
que es justo cuando el propietario lo lee. **No** invalida el sello: es lectura, no decisión.

### H-2 — LOW — El contrato del dueño es exhaustivo solo sobre `DecisionReasonCode`

`test_every_decision_reason_code_is_declared_exactly_once` recorre `typing.get_args(DecisionReasonCode)`
(26 literales). No cubre los demás dueños que alimentan el mismo `journalReasons`
(`OPTIMIZER_REASONS`, `ADAPTIVE_STRATEGY_PAUSED`, `POSITION_LIFECYCLE_REASONS`,
`MATERIALIZATION_REASONS`, `RESERVATION_REASONS`, `NO_MARK_DATA`, `DAY_EXIT_REASONS`). Añadir un
código en cualquiera de ellos no rompería la compuerta.

### H-3 — LOW — No hay test que exija que las dos familias sean **disjuntas**

`VETO_BUCKET_BY_REASON ∩ NON_VETO_REASON_CODES == ∅` es cierto **hoy**, pero ningún test lo
guarda: un literal de salida/skip que colisionara con una familia de veto se filtraría en silencio
como no-veto (o al revés).

## 6. Lo que NO se pudo correr (declarado, nunca asumido)

- **Reproducción end-to-end con material/PG real** (smoke / día operado / truncado): el journal vive
  en `operability_runs/` (gitignored) y **no** está en el clon, así que **no** se re-derivó la tabla
  desde el JSON crudo. Los tres fixtures solo son reproducibles por los puros (`37 passed`). →
  **NO VERIFICADO**.
- **Suites que dependen de PostgreSQL / E2E**: sin BD configurada; no se intentaron.
- **Shims `pytest`/`mypy`**: bloqueados por Windows Application Control; se usó `python -m …`.

Todo lo demás arriba es **observado**; solo el punto 6 y la alcanzabilidad de H-1 son **inferidos**
del código congelado, corroborados por un snippet ejecutado contra el puro sellado.

## 7. Veredicto

**APROBADO CON OBSERVACIONES — 0 bloqueantes.** Lo que **no** puede afirmarse: que `P3-6` esté
cerrado en su caso de uso principal (queda **H-1**), que el contrato del dueño cubra todos los
dueños (**H-2**) ni que la partición veto/no-veto esté guardada (**H-3**). Los tres hallazgos se
remedian en la fase siguiente (ver [plan `v2.79`](./plan-v2-79-auto-material-7-operability-census-2026-09-27.md)).

## 8. Evidencia cruda

[`evidencia-auditoria-v2.78-2026-09-27.txt`](./evidencia-auditoria-v2.78-2026-09-27.txt): identidad
del objeto, salidas de compuertas, diff y mordida de `M211`–`M213`.
