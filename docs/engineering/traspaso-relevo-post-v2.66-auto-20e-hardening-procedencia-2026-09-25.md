# Traspaso / relevo — cierre de `v2.66-beta` (`AUTO-20E`)

> **AsOf:** 2026-09-25 · **Versión:** `1.91.0-beta` · **Fase:** endurecimiento de procedencia del AUTO
> EVIDENCE REPORT (3 P3 de la auditoría de `v2.65-beta`). **SIN migración.** **Freeze intacto.**

## Qué se ha hecho

Fase **de endurecimiento**, sin producto nuevo: cerrar las tres observaciones **P3** que la auditoría de
`v2.65-beta` dejó abiertas, más la higiene del árbol.

1. **P3-1 — Contrato real.** El test del frontend ya **no** compara una constante TS contra un literal espejo:
   **lee el instrumento Python** (`auto_adaptive_calibration.py`) y extrae las seis `CALIBRATION_QUESTION_*`.
   Se verificó que **falla de verdad** al renombrar una clave. `frontend-ci.yml` añade ese fichero a sus
   filtros de ruta (sin esto la compuerta no correría ante un cambio solo de Python). El render Python gana un
   test que ata sus filas a las claves canónicas.
2. **P3-2 — Sin contradicciones silenciosas.** `materialOrigin` de raíz y de `material` que discrepan ⇒
   `PROCEDENCIA DESCONOCIDA` (nunca `PAPER REAL`) + aviso de integridad.
3. **P3-3 — Ausente ≠ vacío.** Listas de perímetro ausentes ⇒ `NO MEDIDO`; vacías medidas ⇒ `(ninguna)`; en
   **TS y Python a la vez**. Para artefactos reales la salida es **byte-idéntica**.
4. **Higiene.** `governor.json` (artefacto generado huérfano) entra en `.gitignore`; los tres ficheros Python
   que aparecían «modificados» eran **solo CRLF** y se normalizaron (árbol limpio).

## Estado del sello

- **Tag:** `v2.66-beta` → commit del paquete de fase (ver `arranque-auditor`).
- **Base del diff:** `v2.65-beta` = `a077c1c6`.
- **`v2.65-beta` permanece intacta** en `a077c1c6`; sus docs y su deuda P3 no se reescriben salvo por el doc
  de deuda, que se anota como **resuelta** aquí.

## Compuertas (medidas)

| Compuerta | Resultado |
|---|---|
| `pnpm --filter @bolsa/web test` | **1323 passed** (232 ficheros) |
| `pnpm --filter @bolsa/web typecheck` | OK |
| `pnpm --filter @bolsa/web lint` | **0 errores** (23 warnings preexistentes) |
| `pnpm --filter @bolsa/web build` | OK |
| `pnpm --filter @bolsa/web contract:check` | OK |
| `uv run pytest packages/py/analytics -q` | **1208 passed** |
| `uv run ruff check packages/py apps/api-python` | OK |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** |
| Matriz de mutaciones | **M179/M180** muerden (ver audit-pack) |

## Lo que sigue igual (invariantes que NO se tocan)

- PAPER = **100 % VIRTUAL**; `realMoneyAtRisk = false`; `brokerVenue = paper`.
- El reparto **no se mueve**: `auto18-v1` / `auto15-v1`.
- El freeze del gobernador y del adaptativo, intacto. **Sin migración** (`046_fill_reference_mid`).
- La UI **lee y presenta**; nunca recalcula. Un conteo `null` sigue siendo `NO MEDIDO`; un veredicto ausente,
  `INCONCLUSIVE`.

## Pendiente / fuera de alcance

- **La corrida PAPER real** sigue siendo **paso operativo del propietario** (≥32 ciclos medidos por
  estrategia). El bloqueo por material local (`cycle_id` NULL en los fills) **no** es un defecto de la fase.
- **`AUTO-21`**: `P(R>0)`, correlación y current-regime gating.

## Cómo continuar

Ver [`arranque-agente-post-v2.66-auto-20e-hardening-procedencia-2026-09-25.md`](./arranque-agente-post-v2.66-auto-20e-hardening-procedencia-2026-09-25.md).
Para auditar, [`arranque-auditor-v2.66-auto-20e-hardening-procedencia-2026-09-25.md`](./arranque-auditor-v2.66-auto-20e-hardening-procedencia-2026-09-25.md).
