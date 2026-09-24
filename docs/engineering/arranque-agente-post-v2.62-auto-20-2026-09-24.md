# Arranque del AGENTE — post `v2.62-beta` (`AUTO-20`)

Bienvenido. `v2.62-beta` (`1.87.0-beta`) está **sellada**. **Lee primero el
[relevo](./traspaso-relevo-post-v2.62-auto-20-2026-09-24.md)**: tiene el estado, los huecos
declarados y los comandos de re-verificación. El [plan](./plan-v2-62-auto-20-material-paper-real-2026-09-24.md)
y el [audit-pack](./audit-pack-v2-62-auto-20-material-paper-real-2026-09-24.md) completan el paquete.

## 1. Qué ha cambiado respecto a `v2.61-beta`

* El instrumento de calibración **declara** el material sin R medible (**O1 cerrado**).
* Su walk-forward **no mezcla** muestras distintas y publica cuatro conteos (**O2 cerrado**).
* El sello del instrumento sube a **`walk_forward_calibration_v2`**.
* Existe una **costura pública** (`adaptive_instrument_cycles`) y un **exportador**
  (`paper_cycles_export.py`) para llevar el riesgo de los ciclos reales hasta el JSON del instrumento.

## 2. Lo que está abierto (por orden de valor)

1. **Ejercitar el camino durable del exportador de punta a punta** (con fixture PG que siembre fills
   y reservas). Es la deuda nº 1.
2. **Ejecutar la calibración sobre material PAPER real** y publicar el primer informe `v2` no
   sintético. Es un paso **operativo**: `paper_cycles_export.py` → `auto_replay_battery.py
   --walk-forward`.
3. **`P(R > 0)`, correlación entre estrategias y current-regime gating** (fuera de alcance hoy).

## 3. Reglas de la casa (no negociables)

* **Lo que no se midió se declara.** Un cero o un veredicto inventado es un fallo, no una comodidad.
* **Un solo productor por medida.** No crees un segundo camino que pueda divergir en silencio.
* **Nada de evidencia mueve el reparto.** El sello `auto18-v1` se cambia en una fase propia, no de
  paso.
* **Cada fase:** plan → implementación → tests + mutaciones → documentos → sello → **PR de auditoría**.
  No mezcles fases en un mismo tag.

## 4. Antes de sellar la siguiente versión

Ejecuta las compuertas del §3 del relevo, **añade la mutación** que mate tu cambio, y comprueba que
el **freeze** sigue intacto (`auto_adaptive.py`, `auto_adaptive_data_gate.py`, el worker, el journal
y `governor.json` byte a byte).
