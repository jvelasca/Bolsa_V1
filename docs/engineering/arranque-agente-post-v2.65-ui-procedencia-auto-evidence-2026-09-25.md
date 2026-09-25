# Arranque del AGENTE — post `v2.65-beta` (`AUTO-20D`)

Bienvenido. `v2.65-beta` (`1.90.0-beta`) está **sellada**. **Lee primero el
[relevo](./traspaso-relevo-post-v2.65-ui-procedencia-auto-evidence-2026-09-25.md)**: tiene el estado, los
huecos declarados y los comandos de re-verificación. El [plan](./plan-v2-65-ui-procedencia-auto-evidence-2026-09-25.md)
y el [audit-pack](./audit-pack-v2-65-ui-procedencia-auto-evidence-2026-09-25.md) completan el paquete.

## 1. Qué ha cambiado respecto a `v2.64-beta`
    10|
* Existe una **superficie de cabina** para el AUTO EVIDENCE REPORT: la sección **Evidencia AUTO (AUTO-20D)**
  en la Consola operacional, con **badge de procedencia** (`PAPER REAL` / `FIXTURE SINTÉTICO` /
  `SIN MATERIAL · NO MEDIDO` / `PROCEDENCIA DESCONOCIDA`).
* El artefacto `AUTO20C_REAL_PAPER_REPORT.json` se **importa a mano** (fichero o pegado) y se archiva en
  local (`bolsa-auto-evidence-archive-v1`). La UI **presenta** el informe, **nunca** lo recalcula.
* Un conteo ausente se muestra `NO MEDIDO`, distinto del `0` legítimo; un veredicto ausente es
  `INCONCLUSIVE`. El reparto sigue en `auto18-v1` (`auto15-v1` el gate). **Sin migración ni cambios Python.**

## 2. Lo que está abierto (por orden de valor)
    20|
1. **Ejecutar la corrida PAPER real (AUTO-20D) y conservar el artefacto**: sigue siendo paso **operativo**
   del propietario (≥32 ciclos medidos por estrategia). Hoy el PostgreSQL local **no tiene material**
   (`sim_fill_finance_context` con `cycle_id` NULL en todos) ⇒ la UI muestra `SIN MATERIAL · NO MEDIDO`.
2. **Endpoint read-only del artefacto** (opcional, si se quiere evitar el import manual) — fase propia.
3. **`P(R > 0)`, correlación entre estrategias y current-regime gating** (AUTO-21).

## 3. Reglas de la casa (no negociables)

* **PAPER = dinero VIRTUAL.** Ninguna operación se ejecuta sobre XTB ni plataforma real.
    30|* **Lo que no se midió se declara.** Un cero, un conteo o un veredicto inventado es un fallo.
* **`INCONCLUSIVE` es un resultado**, no un error: no se "arregla" bajando `min_is`/`min_oos`/`folds`.
* **Un solo productor por medida.** La UI presenta el `report` verbatim; no re-deriva métricas.
* **Nada de evidencia mueve el reparto.** El sello `auto18-v1` se cambia en una fase propia.
* **Cada fase:** plan → implementación → tests + mutaciones → documentos → sello → **PR de auditoría**.

## 4. Antes de sellar la siguiente versión

Ejecuta las compuertas del §7 del relevo (`pnpm --filter @bolsa/web test` / `typecheck` / `lint`), **añade el
    40|test** que mate tu cambio, y comprueba que el **freeze** sigue intacto (`auto_adaptive.py`,
`auto_adaptive_data_gate.py`, el worker, el journal, `auto_adaptive_replay.py` y `governor.json`).
