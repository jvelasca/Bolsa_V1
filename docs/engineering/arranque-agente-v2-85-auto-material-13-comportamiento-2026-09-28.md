# Arranque del agente siguiente — post `AUTO-MATERIAL-13` (docs-only)

> **Punto de entrada** para el siguiente chat/agente. **AsOf:** 2026-09-28 · **Estado:** entrega
> **docs-only** (SIN bump, SIN tag), base `v2.84-beta` (`2.09.0-beta`, `fd3859e3`), `main` = `d7a4924d`.
> **Alembic head:** `046_fill_reference_mid`. **Freeze intacto:** `980c7b6e…` / `ffe36fd2…`.

## 1. Qué acaba de pasar

Fase de **solo `docs/engineering/`** que ejecuta el **cambio de estrategia** que pidió la auditoría
externa de `v2.84-beta` (`APROBADO`, 0 bloqueantes): pasar de **auditar el instrumento** a **auditar el
COMPORTAMIENTO** del AUTO sobre material real.

- Nuevo **protocolo de auditoría de COMPORTAMIENTO** (10 escalones + tabla de patrones de atasco +
  reglas `n/d ≠ 0` + veredicto honesto).
- **`OBS-10` (LOW)** registrada y **aplazada**: `stateCounts` debe recorrer `measured_rows`. **No** se
  corrige ahora porque **una ventana PAPER viva prohíbe mover `packages/`**.
- **Cita del CI de `v2.84`** cerrada formalmente (vive POST-TAG: `1f2638aa`/`434f058d`).
- **Plan de la fase de código** `v2.85`/`AUTO-MATERIAL-13`.
- Detalle en el [relevo](./traspaso-relevo-post-v2-85-auto-material-13-comportamiento-2026-09-28.md).

**No** se tocó ni una línea de `packages/` ni `apps/` (por eso el freeze sigue intacto).

## 2. Estado de la deuda

| Deuda | Estado |
|---|---|
| `OBS-10` (LOW, `stateCounts`) | 🟡 **ABIERTA y APLAZADA** a `v2.85` (semántica decidida: `measured_rows`) |
| `P3-2` / `P3-3` | 🔴 **ABIERTAS** — exigen ventana PAPER ≥4 días **real** |
| `H-4` (LOW) | 🟡 ABIERTO — visible vía `warnings: reason_contract` |
| `OBS-9` (doc-only) | 🟡 ABIERTA y declarada |
| `P3-5`, `OBS-5` | 🟡 declaradas |
| `OBS-6` / `OBS-7` / `OBS-8` | 🟢 CERRADAS en `v2.84` |

## 3. Camino natural (ESTE orden, no se puede invertir)

1. **OPERACIÓN (bloqueante real, tiempo de mercado):** esperar que **cierre D1** (PID `34492`, fin
   ≈11:40) → correr **D2, D3, D4** con cuenta/versión **fijas** → **cierre** con `v2_80 --days 4
   --render` → `v2_83_window_audit.py --render` → gate `--level evidence` → **auditoría de
   comportamiento** con el [protocolo](./protocolo-auditoria-comportamiento-auto-2026-09-28.md).
2. **CÓDIGO `v2.85` (solo DESPUÉS de cerrar la ventana):** fix de `OBS-10` + test + **`M233`** (232 →
   233), etiqueta de `unresolvedRate`, endurecimiento de `ops_seed_window_pair.py`, compuertas
   completas, **re-sellado** (`2.10.0-beta`, tag `v2.85-beta`) y auditoría de comportamiento sobre el
   material real.

> **Restricción dura:** el punto 2 **toca `packages/`** ⇒ **jamás** con la ventana viva.

## 4. Reglas duras

Freeze del worker y del gobernador intactos; `TOP_N=5` y umbrales intactos; **sin migración**
(`046_fill_reference_mid`); reparto `auto18-v1`/`auto15-v1`; `ALLOCATION = none`; **forward, no replay**;
capturador y auditor **read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está
degenerada; **no** se cierra deuda por documentación: primero datos, después evidencia. **No** se añade
ninguna capa nueva de observabilidad.

## 5. Comandos de verificación rápida

```powershell
git log -1 --oneline                                    # d7a4924d
git rev-parse "HEAD:apps" "HEAD:packages"               # 980c7b6e… / ffe36fd2…  (ventana intacta)
Get-Content logs/dev/forward-d1.out.log -Tail 4         # progreso de D1
uv run --no-sync pytest packages/py/application/tests/test_operability_audit.py -q   # 18 passed
```
