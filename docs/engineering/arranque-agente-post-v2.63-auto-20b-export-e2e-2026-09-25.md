# Arranque del AGENTE — post `v2.63-beta` (`AUTO-20B`)

Bienvenido. `v2.63-beta` (`1.88.0-beta`) está **sellada**. **Lee primero el
[relevo](./traspaso-relevo-post-v2.63-auto-20b-export-e2e-2026-09-25.md)**: tiene el estado, los
huecos declarados y los comandos de re-verificación. El [plan](./plan-v2-63-auto-20b-export-e2e-2026-09-25.md)
y el [audit-pack](./audit-pack-v2-63-auto-20b-export-e2e-2026-09-25.md) completan el paquete.

## 1. Qué ha cambiado respecto a `v2.62-beta`

* El **camino durable del exportador está ejercitado end-to-end contra PostgreSQL real**: la deuda nº 1
  de `v2.62` queda cerrada con oráculo independiente y test **same-material** (AUTO-7 vs AUTO-20).
* La lectura de reservas **ya no puede truncarse en silencio**: hay `offset`, el exportador pagina
  hasta agotar y **se bloquea con `2`** si no puede garantizar completitud.
* El JSON del volcado lleva un **`material_manifest`** (conteos + huella `material_fingerprint_v1`), y
  el battery lo propaga al informe como bloque **`material` opcional** (sin él, informe byte-idéntico).
* El **sello del reparto sigue en `auto18-v1`** (`auto15-v1` el gate): la fase es de **material**, no
  de asignación. **Sin migración.**

## 2. Lo que está abierto (por orden de valor)

1. **Ejecutar la calibración sobre material PAPER real** y publicar el primer informe `v2` no
   sintético: `paper_cycles_export.py` → `auto_replay_battery.py --walk-forward`. Es un paso
   **operativo** del propietario (los umbrales por defecto exigen ≥32 ciclos medidos por estrategia).
2. **`P(R > 0)`, correlación entre estrategias y current-regime gating** (AUTO-21).
3. **UI / observabilidad del material**: hoy el manifest y la huella se leen en el JSON y por stderr;
   no hay superficie de cabina para comparar dos corridas.

## 3. Reglas de la casa (no negociables)

* **Lo que no se midió se declara.** Un cero, un conteo o un veredicto inventado es un fallo, no una
  comodidad.
* **Un solo productor por medida.** No crees un segundo camino que pueda divergir en silencio.
* **Nada de evidencia mueve el reparto.** El sello `auto18-v1` se cambia en una fase propia, no de paso.
* **Cadena end-to-end = PG real.** Un camino "cableado sobre costuras ya selladas" no está certificado
  hasta que se recorre con la base de datos de verdad y un oráculo **independiente**.
* **Cada fase:** plan → implementación → tests + mutaciones → documentos → sello → **PR de auditoría**.
  No mezcles fases en un mismo tag.

## 4. Antes de sellar la siguiente versión

Ejecuta las compuertas del §6 del relevo, **añade la mutación** que mate tu cambio, y comprueba que el
**freeze** sigue intacto (`auto_adaptive.py`, `auto_adaptive_data_gate.py`, el worker, el journal,
`auto_adaptive_replay.py` y `governor.json` byte a byte).
