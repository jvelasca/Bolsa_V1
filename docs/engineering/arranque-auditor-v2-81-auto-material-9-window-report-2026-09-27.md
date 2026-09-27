# Arranque del auditor — `v2.81-beta` / `AUTO-MATERIAL-9`: REAL WINDOW EXECUTION (informe de ventana)

> **Objeto:** tag anotado `v2.81-beta` (`2.06.0-beta`) · **Base:** `v2.80-beta` · **AsOf:** 2026-09-27 ·
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**).

## 1. Puntos de entrada (por este orden)

1. **Identidad.** `package.json` = `2.06.0-beta`; tag **anotado** al commit del sello; `git status --porcelain`
   vacío antes/después de la matriz.
2. **Compuertas medidas.** ruff / import-linter (`4 kept, 0 broken`) / mypy (`0 issues`, 506 fuentes) /
   alembic (`046_fill_reference_mid`); `test_operability_window.py` **23 passed**;
   `test_market_operability.py` **58 passed**; matriz **230/230**.
3. **Funnel.** Sin `--forward`: `universe`/`marketData`/`regimeAllowed`/`orders` en `None` (declarado, no
   `0`); `signals`→`reservation` por aritmética del censo; día no medido ⇒ todo `None`. Con `--forward`:
   `universe=watchSize`, `marketData` = live+close, `regimeAllowed=symbols_operable`, `orders=turnTotals.orders`.
4. **`unresolved_age`.** Sólo `approved`; referencia = último instante durable del día; cubos
   `lt1m`/`1to5m`/`5to20m`/`gt20m`/`unknown`; sin timestamps ⇒ no medido; `resolutionJoined=false`.
5. **HTML.** `render_window_html` determinista, escapado, sin recursos externos; publica el veredicto del
   gate y la alerta de contrato.
6. **Capturador read-only.** `--forward`/`--html`; escritura sólo en `operability_runs/`; `exit 2` sin días;
   sin tocar el journal durable ni `evidence_runs/`/`evidence_validations/`.
7. **Registro en CI.** `test_operability_window.py` explícito en `python-ci.yml` (job `quality`) y en
   `release-tag-ci.yml` (job `python`).
8. **Freeze / reparto / migración.** El diff no toca el worker ni el gobernador, `TOP_N` ni umbrales;
   `auto15-v1`/`auto18-v1`; `ALLOCATION = none`; sin migración.
9. **Mutaciones `M226`–`M230`** muerden y restauran byte a byte; matriz `230/230`; árbol intacto.
10. **CI del tag** `v2.81-beta` verde en primera pasada, con los jobs PG intactos.

## 2. Qué NO se puede reproducir sin material real

La **ventana ≥4 días** (`P3-2`/`P3-3`) no se certifica con fixtures: `operability_runs/` está gitignoreado y
la tabla/funnel se re-derivan con fixtures deterministas. El auditor debe **declarar** esa limitación, no
leerla como cierre. `H-4` (LOW) sigue **ABIERTO**.

## 3. Cita del CI del tag

El workflow `Release tag CI` sólo corre al **empujar** el tag: la cita de su resultado vive en
`evidencia-ci-tag-v2.81-2026-09-27.txt` (commit POST-TAG). Dentro del tag, el auditor lo reproduce con los
comandos de §1.
