# Traspaso / relevo — cierre de `v2.72-beta` (cierre de `P3-4`)

> **AsOf:** 2026-09-26 · **Versión:** `1.97.0-beta` · **Tag:** `v2.72-beta` · **Base:** `v2.71-beta`
> **Estado:** fase **CERRADA y elevada**. `P3-4` **cerrada**. **SIN migración**
> (head `046_fill_reference_mid`). **Freeze y reparto intactos** (`auto18-v1` / `auto15-v1`).

## Qué quedó hecho

1. **`P3-4` cerrada.** `build_current_regime_evidence` publica el `level` **clampeado** (el que usó el
   bootstrap), igual que `build_replay_report` (`H3`, `v2.71`) y `CalibrationReport`. Era la **única**
   observación de la auditoría externa de `v2.71-beta`, **preexistente** y **read-only**.
2. **Sello subido** a `current_regime_evidence_v3` (la lectura cambió). Sin consumidor desalineado.
3. **Sonda `M198`** + 3 tests; matriz re-medida **198/198** con restauración **byte a byte**.
4. **Bump** `1.96.0-beta` → **`1.97.0-beta`**.
5. **Primer RUN PAPER intentado y declarado BLOQUEADO por material** (ver abajo). Sin bajar umbrales.

## Lo que NO quedó hecho (y por qué)

- **El primer RUN PAPER real sigue sin ejecutarse: BLOQUEADO por material.** Medido contra
  `bolsa-postgres` (2026-09-26): **761** fills durables, **0** con `cycle_id`, **751 `buy` / 10
  `sell`** (casi todo entradas abiertas ⇒ sin ciclos cerrados) y **0 filas** en
  `portfolio_reservations` (⇒ sin `reserved_risk`, sin R medible). El instrumento devolvió
  `exit 2` en el exportador y en el run, **sin crear** `evidence_runs/`.
  → **No es un defecto de código ni de umbrales: es falta de material, con DOS causas
  independientes** (faltan cierres **y** faltan reservas).
- **`P3-2`** (correlación por cubos) y **`P3-3`** (`P(R>0)` vs N) siguen **abiertas**: requieren el
  primer dataset real, que es justo lo bloqueado.

## Lo que hereda el siguiente

**El bloqueante central sigue siendo MATERIAL, no código.** La secuencia operativa propuesta:

1. **Antes de reintentar el RUN, entender por qué el material no cierra.** Las dos preguntas
   concretas, en orden:
   - **¿Por qué `portfolio_reservations` está vacía?** Sin `reserved_risk` no hay **R** medible aunque
     haya ciclos cerrados. Es la causa que hace inútil cualquier cierre.
   - **¿Por qué 751 compras frente a 10 ventas?** Sin salida no hay ciclo cerrado. Puede ser
     "poco tiempo de simulación" o un camino de salida que no se está ejercitando; **hay que
     medirlo**, no suponerlo.
   Cada una de las dos bloquea por sí sola: arreglar solo una **no** desbloquea el RUN.
2. **Cuando haya ≥32 ciclos medidos por estrategia**, correr el
   [protocolo del primer RUN](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md) **sin tocar los
   umbrales**, y después el harness de validación (`auto_evidence_validate.py`) para cerrar **P3-2** y
   **P3-3**.
3. **Auditoría externa de `v2.72-beta`**: punto de entrada en el
   [arranque del auditor](./arranque-auditor-v2.72-cierre-p3-4-nivel-clampeado-regimen-2026-09-26.md)
   (el tag `v2.72-beta` está publicado para que el auditor trabaje **desde GitHub**).

## Ficheros de la fase

- [Plan](./plan-v2-72-cierre-p3-4-nivel-clampeado-regimen-2026-09-26.md) ·
  [Audit-pack](./audit-pack-v2-72-cierre-p3-4-nivel-clampeado-regimen-2026-09-26.md) ·
  [Auditor](./arranque-auditor-v2.72-cierre-p3-4-nivel-clampeado-regimen-2026-09-26.md) ·
  [Agente](./arranque-agente-post-v2.72-cierre-p3-4-nivel-clampeado-regimen-2026-09-26.md) ·
  [Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
- Evidencia cruda: `evidencia-matriz-mutaciones-v2.72-198-2026-09-26.txt` ·
  `evidencia-run-paper-bloqueado-v2.72-2026-09-26.txt`

## Reglas duras que siguen vigentes

- **No** se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
- **No** se sobrescribe una corrida o validación (`evidence_runs/`, `evidence_validations/`, inmutables).
- **No** se convierte `P(R>0)`, la correlación ni el régimen en `confidence`, sizing, plan, reserva ni
  rotación (`ALLOCATION = none`, `auto18-v1` congelado).
- **No** se toca el freeze. **Sin migración.**
