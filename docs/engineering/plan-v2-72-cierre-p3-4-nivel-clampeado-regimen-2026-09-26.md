# Plan de fase — `V2.72` · cierre de `P3-4` (el `level` de la lectura del régimen es el clampeado)

> **AsOf:** 2026-09-26 · **Versión de partida:** `1.96.0-beta` (`v2.71-beta` = `a310fbc5`, `main` = `0a9a91a8`)
> **Versión objetivo:** `1.97.0-beta` · **SIN migración** (Alembic head sigue en `046_fill_reference_mid`)
> **Origen:** observación **P3-4** de la auditoría externa de `v2.71-beta` (2026-09-26), la **única**
> que levantó el auditor, declarada **preexistente** y **ajena a las 15 tesis** de esa fase.
> **Alcance:** fase **corta y quirúrgica** de corrección del instrumento. **No** produce estadística
> nueva, **no** toca el reparto ni el freeze y **no** ejecuta la corrida PAPER (ver §4).

## 1. El defecto (medido, no supuesto)

`build_current_regime_evidence` (`auto_adaptive_regime_evidence.py`) publicaba el `level` **crudo**
del llamante:

```python
resolved_level = level  # sin clampar
```

…mientras el bootstrap aguas abajo (`build_adaptive_uncertainty`) **sí** lo clampea a
`[ADAPTIVE_INTERVAL_LEVEL_MIN, ADAPTIVE_INTERVAL_LEVEL_MAX] = [0.5, 0.99]`. La consecuencia: con un
`level` no default, la **lectura publicada contradice al número que la produjo**.

Medición del auditor (sonda `G4`): `build_current_regime_evidence(big, level=0.0)` publicaba
`level=0.0`, pero `build_adaptive_uncertainty(big, level=0.0)` medía con `interval.level=0.5`.

Es **la misma clase** de defecto que **H3**, que `v2.71` cerró **solo** en `build_replay_report`
(protegido por `M196`). `P3-4` es exactamente ese cierre, en el **otro** productor que publica un
nivel.

**Por qué es P3.** La evidencia del régimen es **read-only**: `AUTO-21`/`AUTO-23` no mueven sizing,
plan, reserva ni rotación (`auto18-v1`/`auto15-v1` congelados). El defecto solo es observable con un
`level` fuera de rango, que **ningún llamante de producción usa** (todos usan el default `0.90`, ya
dentro del rango). No publica un número falso: publica un **nivel** incoherente con su propia
medición.

**Atribución.** Preexistente: `git show v2.70-beta:.../auto_adaptive_regime_evidence.py` contiene el
mismo `resolved_level = level`; el diff `v2.70 → v2.71` no lo toca.

## 2. La corrección

1. **Clamp en el productor.** `build_current_regime_evidence` calcula
   `resolved_level = min(max(float(level), MIN), MAX)` **antes** de publicarlo, igual que
   `build_replay_report` y `CalibrationReport`. El `level` publicado pasa a ser, por construcción, el
   que usó el bootstrap.
2. **Sello subido.** `CURRENT_REGIME_EVIDENCE_METHOD` `current_regime_evidence_v2` → **`v3`**: la
   lectura cambia (el campo `level` puede diferir del crudo), así que el sello lo declara. **No hay
   consumidor que lo fije**: era el único sitio del repo que nombraba la constante (el grep del
   repo entero no encuentra otro punto que la afirme).
3. **Sonda que lo muerde.** `M198` muta el clamp a `float(level)` y debe enrojecer
   `test_the_interval_level_is_clamped_and_published`.

**Lo que NO cambia:** la aritmética del bootstrap, la `P(R>0)` por ciclos, la `P(edge>0)`, el
`byStrategy`, los `notes`, el régimen seleccionado ni el reparto. Con el `level` default (`0.90`) el
payload es **idéntico salvo el sello `method`** (`current_regime_evidence_v2` → `v3`, que sube por
diseño): la corrección solo se manifiesta con un `level` fuera de rango.

## 3. Entregables

| # | Entregable | Dónde |
|---|---|---|
| 1 | Clamp de `resolved_level` | `auto_adaptive_regime_evidence.py` |
| 2 | Sello `current_regime_evidence_v3` | ídem |
| 3 | `test_the_interval_level_is_clamped_and_published` + `test_the_clamped_level_travels_even_without_cycles` + `test_the_regime_evidence_seal_is_v3` | `test_auto_adaptive_regime_evidence.py` |
| 4 | `M198` | `apps/api-python/scripts/v2_44_mutation_audit.py` |
| 5 | Re-medición de la matriz completa (**198/198**) | `evidencia-matriz-mutaciones-v2.72-198-2026-09-26.txt` |
| 6 | Bump `1.96.0-beta` → `1.97.0-beta` | `package.json`, `CHANGELOG.md` |

## 4. El primer RUN PAPER real: declarado BLOQUEADO por material

La fase **intenta** el primer RUN (`AUTO-22`) contra el PostgreSQL local y lo declara **BLOQUEADO**
con la evidencia del propio instrumento. **No se baja ningún umbral** (`min cycles`, `min R`,
`folds`, `min_episodes`) para forzarlo: es la regla dura del
[protocolo del primer RUN](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md).

Medición (PostgreSQL `bolsa-postgres`, 2026-09-26):

| Hecho medido | Valor | Consecuencia |
|---|---|---|
| Fills durables | **761** | hay actividad |
| Fills con `cycle_id` | **0** | ningún ciclo identificado (migración 044 sin poblar) |
| Lados | **751 `buy` / 10 `sell`** | casi todo son **entradas abiertas**: sin salida no hay ciclo cerrado ni resultado |
| Filas de `portfolio_reservations` | **0** | sin `reserved_risk` ⇒ **sin R medible**, aunque hubiera cierre |
| Fills por versión (máx.) | **4** | muy por debajo de los **≥32 ciclos medidos** del walk-forward |
| `venue` de los fills | `simulated` | la guarda **app-level** (`BROKER_VENUE=paper`) sí pasó; la venue de fila es del carril SIM |

Las dos salidas del instrumento, con su código de bloqueo:

- `paper_cycles_export.py` → `# BLOQUEADO: no hay ciclos cerrados con fill durable para esas versiones/cuenta` (**exit 2**).
- `auto_evidence_run.py` → `# BLOQUEADO: sin ciclos con R medible: no se publica un bundle vacío como si fuera una medición` (**exit 2**), **sin crear** `evidence_runs/` (fail-closed verificado).

**Conclusión honesta:** el instrumento está listo y se comporta como debe; lo que falta es
**material**, y no en un sentido vago: faltan **cierres** (751 compras frente a 10 ventas) y faltan
**reservas** (`portfolio_reservations` vacía) — dos causas independientes, cada una suficiente para
bloquear. El primer RUN sigue siendo el **paso operativo del propietario**.

## 5. Reglas duras de la fase

- **No** se toca ningún fichero del freeze (`portfolio_optimizer.py`, `portfolio_reservation.py`,
  `auto_adaptive.py`, `auto_simulation_worker.py`, `auto_adaptive_journal.py`).
- **No** se mueve el reparto: `auto18-v1` / `auto15-v1`.
- **No** hay migración.
- **No** se escribe en `evidence_runs` / `evidence_validations` (el RUN bloqueado no crea carpeta).
- **No** se toca `governor.json`.

## 6. Criterio de cierre

1. `M198` muerde; matriz **198/198** con restauración **byte a byte** y `git status` limpio antes y después.
2. Compuertas en verde: `ruff` · `import-linter` · `mypy` · `analytics` · costuras `api-python`.
3. Sello `current_regime_evidence_v3` publicado y fijado por test.
4. Tag anotado `v2.72-beta` con `Release tag CI` **GREEN**, y el paquete de auditoría listo para que
   un auditor externo lo verifique **desde GitHub** (sin acceso al árbol de trabajo).
