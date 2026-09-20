# Relevo de cierre — v2.43.2: **matriz de mutaciones + sello** (`1.68.2-beta`)

**Fecha:** 2026-09-20 · **Versión:** `1.68.2-beta` (bump ya aplicado en `package.json`) · **Migración:
ninguna** (Alembic head sigue en `042_portfolio_reservations`).

> **ESTADO (2026-09-20): EJECUTADO.** Sonda versionada
> [`v2_43_2_mutation_audit.py`](../../apps/api-python/scripts/v2_43_2_mutation_audit.py) creada y medida:
> **9 de las 13 mutaciones muerden** (M1–M5, M7–M9, M11) y **4 nacen verdes** (M6, M10, M12, M13), con la
> causa de cada verde declarada en el **§10.1** del pack. **Tres agujeros reales** (M6, M12, M13)
> declarados y reproducibles — **sin** tocar código de producción ni añadir tests. **Sello (§12) ejecutado**;
> ver el pack para la evidencia de CI y la errata del diff.

**Este documento es una ORDEN DE TRABAJO, no un pack.** El pack ya existe; esto es lo que falta para
poder sellar. Padre documental: [Engineering Index](./engineering-index-2026-08-03.md) (nodo de estado, no
una raíz nueva).

**Punto de entrada obligatorio antes de tocar nada:**
[`audit-pack-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md`](./audit-pack-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md) §10,
[`arranque-auditor-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md`](./arranque-auditor-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md)
y [`traspaso-relevo-post-v2-43-2-auto-3-slice-2-2026-09-19.md`](./traspaso-relevo-post-v2-43-2-auto-3-slice-2-2026-09-19.md).

---

## 0. Estado de partida (qué está hecho y qué NO)

**Hecho y verde** (medido, árbol final):

| Comprobación                | Resultado                                                                    |
| --------------------------- | ---------------------------------------------------------------------------- |
| `ruff` (invocación CI)      | `All checks passed!`                                                         |
| `mypy`                      | **487 ficheros, 0 issues**                                                   |
| `lint-imports`              | **4 kept / 0 broken**                                                        |
| Evidencia del gobernador    | **exit 0** (script **byte a byte igual** que `HEAD`)                         |
| `quality` (offline)         | **2031 passed** (`1991` → **+40**)                                           |
| `python` del tag (offline)  | **2042 passed** (`2002` → **+40**)                                           |
| `packages/py/analytics`     | **862 passed**                                                               |
| `packages/py/application`   | **1705 passed, 5 skipped**                                                   |
| Docs (pack/arranque/relevo) | escritos; **65/65 referencias citadas existen** (`a9_doc_refs_probe` exit 0) |

**HECHO en esta pasada** (2026-09-20):

1. **La matriz de mutaciones (§10 del pack).** **MEDIDA**: las 13 mutaciones de §2 aplicadas y revertidas
   con la sonda `v2_43_2_mutation_audit.py`; **9 muerden** (M1–M5, M7–M9, M11) y **4 verdes** (M6, M10,
   M12, M13) con su causa declarada en el §10.1 del pack.
2. **El sello (§12 del pack).** Commit de fase `ef35e3aa` (29 ficheros, `+3814/−66`) + tag anotado
   `v2.43.2-beta` sobre el commit de sellado docs-only + CI real en `main` (`Python CI` `GREEN` 5/5 y
   `Gitleaks` `GREEN`) y en la ref del tag (§12.1).

**Regla de oro de este relevo:** no se cambia **ni una línea de código de producción**. Si una mutación
descubre un agujero de cobertura real, **se declara en el pack** y se decide con el owner; no se "arregla
a escondidas" dentro del cierre.

---

## 1. Herramienta: cómo se mide una mutación en este repo

**No** se muta a mano ni se restaura con `git checkout -- <fichero>`. Existe un patrón ya medido y su
lección escrita:

- `apps/api-python/scripts/v2_40_4_mutation_audit.py` — **el patrón a copiar.** Restaura **desde el texto
  original en memoria** y **verifica que deja el árbol exactamente como lo encontró** (huella de
  `git status --porcelain` de los ficheros tocados, antes y después).
- `apps/api-python/scripts/a9_mutation_audit.py` — el patrón **antiguo**, que restauraba con
  `git checkout --`. **No lo uses:** en `v2.40.4` eso **descartó trabajo no commiteado** y costó una
  reconstrucción manual de `auto_v2_entry.py`. Está documentado en el docstring del script nuevo.
- `apps/api-python/scripts/a9_restart_mutation.py` — variante para mutaciones que exigen reinicio.

**Crea** `apps/api-python/scripts/v2_43_2_mutation_audit.py` copiando la estructura de
`v2_40_4_mutation_audit.py` (copia en memoria + huella antes/después + `timeout`). El `timeout` **no es
decorativo**: el teardown de `apps/api-python/tests/conftest.py` purga residuos contra PG **sin timeout**,
así que sin PG levantado un run de esa carpeta se queda colgado para siempre. Por eso la sonda debe
devolver `TIMEOUT`, no una sonda muda.

> **Aviso ya medido en este repo:** hay mutaciones que nacen **verdes** y **no** son agujero de cobertura,
> sino mutación **mal puesta** (o más fuerte/débil que el bug). Pasó en `v2.42.1` (M5, M10/M13) y en
> `v2.43` (M5, M6). Si una mutación sale verde, **investiga por qué antes de declarar cobertura**: no
> "añadas cobertura" subiendo un test al azar.

---

## 2. Las 13 mutaciones, con el fragmento EXACTO

`T_LEDGER` = `packages/py/analytics/tests/test_position_ledger.py` ·
`T_ENTRY` = `packages/py/application/tests/test_auto_v2_entry.py` ·
`T_MANAGER` = `packages/py/application/tests/test_position_manager.py` ·
`T_KILL` = `packages/py/analytics/tests/test_hard_kill_switch.py` ·
`T_FRESH` = `packages/py/analytics/tests/test_data_freshness.py` ·
`T_RESV` = `packages/py/analytics/tests/test_portfolio_reservation_ledger.py` ·
`T_V44` = `apps/api-python/tests/test_auto_v44_exit_governance.py`

| #               | Fichero                     | Fragmento **original** → **mutado**                                                                                                                            | Suites             |
| --------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| **M1** (H1)     | `position_ledger.py`        | bloque del fold (abajo) → versión de `HEAD` con `realized_qty += fact.quantity`                                                                                | `T_LEDGER`         |
| **M2** (H2)     | `auto_v2_entry.py`          | `    if has_committed_risk and snapshot.risk_is_complete:` → `    if has_committed_risk:`                                                                      | `T_ENTRY`          |
| **M3** (H2)     | `auto_v2_entry.py`          | `        risk_measurement=snapshot.risk_measurement,` → `        risk_measurement=None,`                                                                       | `T_ENTRY`          |
| **M4** (H3)     | `auto_v2_entry.py`          | bloque `stop_distance(...)` (abajo) → `            risk_amount = max(0.0, (float(entry) - float(stop)) * float(qty))`                                          | `T_ENTRY`          |
| **M5** (H4)     | `position_ledger.py`        | `        if key in seen:` → `        if False:`                                                                                                                | `T_LEDGER`         |
| **M6** (H5)     | `position_ledger.py`        | `        grouped.setdefault((fact.account_id, fact.instrument_id), []).append(fact)` → `        grouped.setdefault(("", fact.instrument_id), []).append(fact)` | `T_LEDGER`         |
| **M7** (H6)     | `position_ledger.py`        | `        0 if fact.applied_at else 1,` → `        0,`                                                                                                          | `T_LEDGER`         |
| **M8** (A13)    | `auto_v2_entry.py`          | `        if cfg.governor_enabled or halted:` → `        if cfg.governor_enabled:`                                                                              | `T_V44`            |
| **M9** (A13)    | `auto_v2_entry.py`          | `                halted=halted,` → `                halted=False,`                                                                                             | `T_V44`            |
| **M10** (A8/A9) | `position_manager.py`       | `    if halted or regime_exit or risk_off:` → `    if regime_exit:`                                                                                            | `T_MANAGER`        |
| **M11** (A14)   | `data_freshness.py`         | `        return reading is None or reading.status != FRESHNESS_FRESH` → `        return False`                                                                 | `T_FRESH`, `T_V44` |
| **M12** (F9)    | `portfolio_reservation.py`  | bloque `bucket = buys if …` (abajo) → versión de `HEAD` que salta las ventas                                                                                   | `T_RESV`, `T_V44`  |
| **M13** (F9)    | `auto_simulation_worker.py` | `            applied.setdefault((fact.instrument_id, fact.side), []).append(` → `            applied.setdefault((fact.instrument_id, "buy"), []).append(`      | `T_V44`            |

`T_KILL` **no** muerde ninguna de las 13: sus tests son **unitarios puros** de `HardKillSwitch` (latch,
tipificación, liberación) y no pasan por código mutado. Repórtalo así si sale verde en todas, y **no**
inventes una mutación para él dentro de este cierre (su contrato ya está medido por su propia suite).

### Fragmentos multilínea (exactos, con su indentación)

**M1** — `position_ledger.py`, original (13 líneas, dentro de `_fold_instrument`):

```python
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

mutado (comportamiento de `HEAD`: sin `sold_qty`, el exceso y el huérfano inflan la cantidad cerrada):

```python
        avg_entry = (cost_basis / quantity) if quantity > _QTY_EPS else None
        sellable = quantity - realized_qty
        if sellable <= _QTY_EPS:
            violations.append(f"oversell_without_position:{fact.execution_id}")
            realized_qty += fact.quantity
            continue
        matched = min(fact.quantity, sellable)
        if avg_entry is not None:
            realized_pnl += matched * (fact.price - avg_entry)
            cost_basis -= matched * avg_entry
        if fact.quantity > matched + _QTY_EPS:
            violations.append(f"oversell_above_position:{fact.execution_id}")
        realized_qty += fact.quantity
```

**M4** — `auto_v2_entry.py`, original (5 líneas, el bloque de `H3`):

```python
            distance = stop_distance(
                entry=float(entry), stop=float(stop), direction="long"
            )
            if distance is not None:
                risk_amount = distance * float(qty)
```

mutado (la línea exacta de `HEAD`: sin `stop_distance`, con el `max(0.0, …)` que convierte "stop mal
puesto" en riesgo medido a cero):

```python
            risk_amount = max(0.0, (float(entry) - float(stop)) * float(qty))
```

**M12** — `portfolio_reservation.py`, original (2 líneas, en `committed_positions`):

```python
            bucket = buys if reservation.is_buy else sells
            bucket.setdefault(reservation.instrument_id, []).append(reservation)
```

mutado (comportamiento de `HEAD`: la reserva de venta se **ignora**):

```python
            if reservation.is_sell:
                continue
            buys.setdefault(reservation.instrument_id, []).append(reservation)
```

### Esqueleto de la sonda

Copia `apps/api-python/scripts/v2_40_4_mutation_audit.py` y sustituye su `MUTATIONS` por:

```python
MUTATIONS: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    ("M1 realized_qty vuelve a inflarse (H1)", LEDGER, "<bloque original>", "<bloque HEAD>", (T_LEDGER,)),
    ("M2 working_snapshot suma riesgo sobre base no medida (H2)", ENTRY,
     "    if has_committed_risk and snapshot.risk_is_complete:\n",
     "    if has_committed_risk:\n", (T_ENTRY,)),
    ("M3 el rebuild re-deriva la medicion (H2)", ENTRY,
     "        risk_measurement=snapshot.risk_measurement,\n",
     "        risk_measurement=None,\n", (T_ENTRY,)),
    ("M4 stop del lado equivocado vuelve a publicar 0.0 (H3)", ENTRY, "<bloque original>", "<linea HEAD>", (T_ENTRY,)),
    ("M5 sin dedupe por execution_id (H4)", LEDGER,
     "        if key in seen:\n", "        if False:\n", (T_LEDGER,)),
    ("M6 el fold funde cuentas (H5)", LEDGER,
     "        grouped.setdefault((fact.account_id, fact.instrument_id), []).append(fact)\n",
     '        grouped.setdefault(("", fact.instrument_id), []).append(fact)\n', (T_LEDGER,)),
    ("M7 un hecho sin fecha se ordena primero (H6)", LEDGER,
     "        0 if fact.applied_at else 1,\n", "        0,\n", (T_LEDGER,)),
    ("M8 la parada dura no evalua la tabla con el gobernador OFF", ENTRY,
     "        if cfg.governor_enabled or halted:\n", "        if cfg.governor_enabled:\n", (T_V44,)),
    ("M9 halted nunca llega a la tabla", ENTRY,
     "                halted=halted,\n", "                halted=False,\n", (T_V44,)),
    ("M10 sin reafirmacion defensiva de venta total", MANAGER,
     "    if halted or regime_exit or risk_off:\n", "    if regime_exit:\n", (T_MANAGER,)),
    ("M11 blocks_new_entry siempre False", FRESH,
     "        return reading is None or reading.status != FRESHNESS_FRESH\n",
     "        return False\n", (T_FRESH, T_V44)),
    ("M12 committed_positions ignora las reservas sell (F9)", RESV, "<bloque original>", "<bloque HEAD>", (T_RESV, T_V44)),
    ("M13 la reconciliacion casa por instrumento y no por lado (F9)", WORKER,
     "            applied.setdefault((fact.instrument_id, fact.side), []).append(\n",
     '            applied.setdefault((fact.instrument_id, "buy"), []).append(\n', (T_V44,)),
]
```

**Advertencia sobre M9:** `                halted=halted,` aparece **una sola vez** en `auto_v2_entry.py`
(la llamada a `assess_from_measurements`). Si en el momento de medir hubiera más de una, el
`.replace(old, new, 1)` mutaría la primera y la sonda **mentiría**: compruébalo con
`Select-String -Path … -Pattern 'halted=halted'`.

**Advertencia sobre M13:** si sale **verde**, mira **cómo** se libera la reserva en el test. Puede
liberarse por la rama de "muerta" (`RELEASED_BY_RESTART`) en vez de por fill, y entonces la mutación no
está midiendo el contrato que crees. Es la trampa de `v2.42.1` M10/M13 (dos sensores tapándose entre sí).

---

## 3. Qué existe y qué NO existe (dato medido, para que no pierdas tiempo)

**No hay test hermético en `packages/py/application/tests/test_auto_v2_entry.py` que pase `halted=True` a
`plan_v2_tick`** (verificado: 0 coincidencias de `halt`/`kill` en el fichero). El único camino medido del
`or halted` y de `halted=halted` es el de **integración**:
`apps/api-python/tests/test_auto_v44_exit_governance.py::test_v2_hard_kill_switch_vetoes_entry_with_governor_halted`.
Por eso M8/M9 apuntan ahí y **no** a `T_ENTRY`.

Si M8/M9 salen **verdes**, es un agujero de cobertura legítimo y hay que **declararlo** (el fix no tiene
sensor hermético que lo muerda); la decisión de añadir un test **unitario** de `plan_v2_tick(halted=True)`
la toma el owner, porque añadir un test **después** de medir una mutación verde es exactamente lo que el
pack de `v2.43` desaconseja hacer a la ligera.

---

## 4. Comandos (invocaciones EXACTAS de la casa)

```bash
# la sonda (escribe el script primero; ver §1)
uv run --no-sync python apps/api-python/scripts/v2_43_2_mutation_audit.py

# y la huella debe quedar INTACTA al terminar (la propia sonda lo comprueba, exit 0)
git status --porcelain -- packages/py apps/api-python
```

**Antes y después de la sonda**, el árbol tiene que estar **exactamente igual**: la sonda de `v2.40.4`
devuelve `exit 1` si la huella cambia. Si toca medir una mutación sola (para aislar M1, que es un bloque
grande), se hace con el mismo patrón, **nunca** con `git checkout --`.

Re-verificación final antes de sellar (las cinco de siempre):

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
```

Cifras que deben salir **exactamente** (`quality` **2031**, tag **2042**, `0 failed / 0 skipped`) y
`exit 0` del gobernador con su `git diff` **vacío**.

---

## 5. Entregables de este relevo

1. **`apps/api-python/scripts/v2_43_2_mutation_audit.py`** — la sonda versionada (patrón de `v2.40.4`).
2. **§10 del pack actualizado**: sustituir «_NO medida_» por la **tabla medida** (mutación → rojos
   observados, con **nombres de test**), y **retirar** la frase de deuda. Si alguna mutación sale verde,
   se declara **en esa misma tabla** con la explicación de por qué (mutación mal puesta / agujero real).
3. **Sello (§12)**: commit de fase + tag anotado **`v2.43.2-beta`** (apunta al commit de **sellado**
   docs-only, como `v2.43-beta`/`v2.43.1-beta`) + CI real medida en `main` y en la ref del tag, con sus
   **URLs de run**.
4. **Errata del diff** en el §12: ficheros y `+N/−M` **reales** del commit de fase.
5. **Actualizar** `PROJECT_STATE.md` / `engineering-index` §5 entrada **124**: quitar «_Sello PENDIENTE_» y
   «_matriz NO medida_» cuando dejen de ser ciertos. **No** dejes esas frases si ya no aplican: es
   exactamente el tipo de doc que miente y cobra un auditor.

---

## 6. Trampas (todas medidas en este repo; no las repitas)

1. **Verificar con la invocación equivocada mide OTRA COSA.** El §13 del pack declara el error de esta
   fase: `ruff` **sin** `--config pyproject.toml` dijo «2 avisos preexistentes» cuando con la invocación
   de CI eran **7, y los 7 de ficheros míos** (el flag cambia la clasificación first-party de `isort`).
   Para distinguir «preexistente» de «introducido», **worktree limpio en `HEAD`** con la **misma**
   invocación — **no** `git show` por stdin (no aplica la misma detección de rutas).
2. **El `timeout` de la sonda es obligatorio**: el teardown de `apps/api-python/tests/conftest.py` se cuelga
   sin PG. Un run sin `timeout` = sonda muda para siempre.
3. **Mutación verde ≠ agujero de cobertura.** `v2.42.1` M5 y M10/M13, y `v2.43` M5/M6, nacieron verdes y
   **no** eran agujeros: eran mutaciones mal puestas o dos sensores tapándose. Antes de "añadir cobertura",
   comprueba que la mutación rompe **comportamiento**.
4. **Cuidado con el `--ignore` de PG en los jobs offline.** Un `skip` mudo **no certifica nada**. Las
   suites PG (`*_pg*.py`) van al `--ignore` de los bloques offline y corren en sus jobs dedicados con gate
   fail-if-skipped; **ese** es el sitio donde se certifica la durabilidad de las reservas de salida.
5. **PG real no se mide en esta máquina** (el `connect` del DSN se cuelga). No lo intentes: la
   certificación la aporta CI, y el pack ya lo declara.
6. **`ruff --fix` antes de sellar**, no después: los imports nuevos en `auto_simulation_worker.py`,
   `position_manager.py` y `portfolio_reservation.py` son largos y el job `quality` va rojo por `I001`.
7. **Los dos docs de `v2.40.4` aparecen como ` M` sin contenido que sellar** (artefacto de fin de línea
   CRLF): `git diff` sale **vacío**. No los comitees "por si acaso".

---

## 7. Freeze (no tocar en este cierre)

- **Cero cambios en código de producción.** Este relevo mide y sella; si hay que tocar algo, se declara y
  se decide con el owner.
- **`v2_43_governor_evidence.py`**: byte a byte igual; su `"bump"` se queda en **`1.68.0-beta`**.
- **Tabla del gobernador y sus umbrales** (`operational_governor.py`): no se tocan.
- **`v2.43-beta` y `v2.43.1-beta` no se mueven**: refs publicadas y auditadas.
- **Sin migración**: Alembic head en `042_portfolio_reservations`.
- **`AUTO_ENGINE_SIM_V2_GOVERNOR=0` sin parada dura**: byte-idéntico a `v2.43.1`. Cualquier cambio ahí es
  un hallazgo, no un fix.
