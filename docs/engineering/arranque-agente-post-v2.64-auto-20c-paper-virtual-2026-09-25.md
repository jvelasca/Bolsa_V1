# Arranque del AGENTE — post `v2.64-beta` (`AUTO-20C`)

Bienvenido. `v2.64-beta` (`1.89.0-beta`) está **sellada**. **Lee primero el
[relevo](./traspaso-relevo-post-v2.64-auto-20c-paper-virtual-2026-09-25.md)**: tiene el estado, los huecos
declarados y los comandos de re-verificación. El [plan](./plan-v2-64-auto-20c-paper-virtual-2026-09-25.md),
el [audit-pack](./audit-pack-v2-64-auto-20c-paper-virtual-2026-09-25.md) y el
[invariante](./invariante-paper-virtual-2026-09-25.md) completan el paquete.

## 1. Qué ha cambiado respecto a `v2.63.1-beta`

* El **invariante PAPER VIRTUAL** está instalado en toda la cadena: `EXECUTION_REALITY_VIRTUAL_PAPER` como
  fuente única, declarado en manifest, nota del exportador, artefacto y render; y el exportador **se
  bloquea con `2`** si la venue no es `paper`.
* El manifest declara su **perímetro**: versiones **observadas** frente a las pedidas, fills **excluidos**
  sin versión / de otra versión, `regimesPresent` y `materialOrigin`. El universo medido y la huella **no**
  cambian.
* La calibración produce un **artefacto reproducible** (`AUTO20C_REAL_PAPER_REPORT.json`) y un **render**
  legible (`AUTO EVIDENCE REPORT`, punto 30) con `--out`/`--render`, sin alterar stdout.
* El **sello del reparto sigue en `auto18-v1`** (`auto15-v1` el gate): la fase es de **material e
  invariante**, no de asignación. **Sin migración.**

## 2. Lo que está abierto (por orden de valor)

1. **Ejecutar la calibración sobre material PAPER real y conservar el artefacto**: `paper_cycles_export.py`
   → `auto_replay_battery.py --walk-forward --out`. Es un paso **operativo** del propietario (los umbrales
   por defecto exigen ≥32 ciclos medidos por estrategia) y el primer informe `v2` no sintético. Acepta
   `SUPPORTED` / `NOT_SUPPORTED` / `INCONCLUSIVE` **sin tocar umbrales**.
2. **`P(R > 0)`, correlación entre estrategias y current-regime gating** (AUTO-21) — hoy declarados como
   `AUTO-21 (fuera de alcance)` en el render.
3. **UI / observabilidad del material**: el perímetro y la huella se leen en el JSON, el render y por
   stderr; no hay superficie de cabina para comparar dos corridas.

## 3. Reglas de la casa (no negociables)

* **PAPER = dinero VIRTUAL.** Ninguna operación se ejecuta sobre XTB ni plataforma real. La procedencia se
  **importa** de `auto_evidence_report.py`, no se re-declara.
* **Lo que no se midió se declara.** Un cero, un conteo o un veredicto inventado es un fallo, no una
  comodidad.
* **`INCONCLUSIVE` es un resultado**, no un error: no se "arregla" bajando `min_is`/`min_oos`/`folds`.
* **Un solo productor por medida.** No crees un segundo camino que pueda divergir en silencio.
* **Nada de evidencia mueve el reparto.** El sello `auto18-v1` se cambia en una fase propia, no de paso.
* **Cada fase:** plan → implementación → tests + mutaciones → documentos → sello → **PR de auditoría**. No
  mezcles fases en un mismo tag.

## 4. Antes de sellar la siguiente versión

Ejecuta las compuertas del §7 del relevo, **añade la mutación** que mate tu cambio, y comprueba que el
**freeze** sigue intacto (`auto_adaptive.py`, `auto_adaptive_data_gate.py`, el worker, el journal,
`auto_adaptive_replay.py` y `governor.json` byte a byte).
