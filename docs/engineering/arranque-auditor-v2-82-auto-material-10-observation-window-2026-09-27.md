# Arranque del auditor — `v2.82-beta` / `AUTO-MATERIAL-10`: OBSERVATION WINDOW (fase operativa)

> **Objeto:** tag anotado `v2.82-beta` (`2.07.0-beta`) · **Base:** `v2.81-beta` · **AsOf:** 2026-09-27 ·
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**).

## 0. Antes de empezar: este objeto es docs-only

`v2.82` **no** entrega código. `package.json` (`2.06.0-beta → 2.07.0-beta`) es el **único** cambio
no-doc. Todo lo demás son documentos de fase. El auditor **no** debe buscar un diff de comportamiento:
debe verificar que **no hay** diff de comportamiento y que la fase declara honestamente lo que falta.

## 1. Puntos de entrada (por este orden)

1. **Identidad.** `package.json` = `2.07.0-beta`; tag **anotado** al commit del sello;
   `git status --porcelain` vacío antes/después de cualquier sonda.
2. **Diff docs-only.** `git diff v2.81-beta..v2.82-beta --stat` = `package.json` + `docs/engineering/*`
   (+ `CHANGELOG.md`). **Ningún** fichero de motor, instrumento, workflow o migración.
3. **Compuertas medidas.** ruff / import-linter (`4 kept, 0 broken`) / mypy (`0 issues`, 506 fuentes) /
   alembic (`046_fill_reference_mid`); `test_market_operability.py` + `test_operability_window.py`
   = **81 passed** (58 + 23), sin cambios.
4. **Freeze / reparto / migración.** El diff no toca el worker ni el gobernador, `TOP_N` ni umbrales;
   `auto15-v1`/`auto18-v1`; `ALLOCATION = none`; sin migración.
5. **Instrumento intacto.** Funnel + `unresolved_age` + HTML de `v2.81` sin cambios; `None ≠ 0`; veredicto
   honesto `INCONCLUSIVE`.
6. **Sin mutaciones nuevas.** Matriz `230/230` (no hay código que mutar); `M226`–`M230` siguen mordiendo.
7. **CI del tag** `v2.82-beta` verde en primera pasada, con los jobs PG intactos.

## 2. Qué NO se puede reproducir sin material real

La **ventana ≥4 días** (`P3-2`/`P3-3`) no se certifica con fixtures: `operability_runs/` está
gitignoreado y la tabla/funnel se re-derivan con fixtures deterministas. El auditor debe **declarar** esa
limitación, no leerla como cierre. `H-4` (LOW) sigue **ABIERTO** y esta fase **no** lo cierra.

## 3. Cita del CI del tag

El workflow `Release tag CI` sólo corre al **empujar** el tag: la cita de su resultado vive en
`evidencia-ci-tag-v2.82-2026-09-27.txt` (commit POST-TAG). Dentro del tag, el auditor lo reproduce con los
comandos de §1.

## 4. Lo que la fase deja como tarea, no como código

La escalera de éxito (operación, tiempo real) y la lectura `D1..Dn` + funnel + `unresolved_age` están en el
[plan](./plan-v2-82-auto-material-10-observation-window-2026-09-27.md) §4 y en el
[runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md).
