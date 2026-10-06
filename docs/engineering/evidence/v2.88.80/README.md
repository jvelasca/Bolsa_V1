# Evidencia `v2.88.80-beta` — `AUTO · UI`: **sello de la telemetría operacional (P1 + P2 + P3)**

**Producto:** `V2.88.80-beta` · **Package:** `2.11.80-beta` · **AsOf:** 2026-10-06. **Sin migración nueva** (reutiliza `051_auto_engine_activity`). **Contrato HTTP con cambio aditivo** (`currentActivityAt` + `currentActivityAtMeasurement`). **Motor financiero sin cambio.** **Sin tag.**

**Padre de producto:** [`v2.88.79`](../v2.88.79/README.md).

## Qué cambia

Cierra los tres hallazgos de la auditoría de `v2.88.79` para que la telemetría operacional sea
íntegra y comprensible para el usuario básico.

1. **P1 — la medición gobierna la presentación.** La UI ya no traduce `currentActivity` a ciegas:
   `activityLabel` recibe `currentActivityMeasurement` y un dato presente con medición `UNKNOWN`/`PARTIAL`
   se declara «Sin dato todavía». Se rompe el caso `ANALYZING + UNKNOWN → Analizando`.
2. **P2 — frescura de la actividad.** El contrato expone `currentActivityAt` (+ su medición) y la UI
   aplica una política interna de frescura (`AUTO_ACTIVITY_MAX_AGE_SECONDS`, default 300 s): una
   actividad antigua (o sin sello) no se presenta como actual. Sin texto de hora nuevo al usuario.
3. **P3 — fin de `RUNNING + BLOCKED`.** El estado durable del motor pasa a significar «¿está permitida
   la operativa?» y se deriva de la MISMA señal de bloqueo que `derive_activity`
   (`_kill_active() OR _v2_kill_switch_halted()`): kill activo ⇒ `state="BLOCKED"` y `activity="BLOCKED"`.
   Nunca más «Funcionando» + «Bloqueado» simultáneos.

## Semántica oficial del estado (tres conceptos, no tres sinónimos)

- `lastHeartbeatAt` = **¿está vivo el proceso?** (latido; no es fase ni decisión).
- `state` = **¿está permitida la operativa?** (`RUNNING` / `BLOCKED`).
- `currentActivity` = **¿qué hizo el último tick?** (fase operacional, con su medición y su sello `currentActivityAt`).

## Invariantes de honestidad (no negociables)

- Dato presente ≠ dato medido: `currentActivity` con medición no `COMPLETE` es «Sin dato todavía».
- Actividad sin sello o antigua es «Sin dato todavía» (fail-closed).
- `state=BLOCKED` implica `activity=BLOCKED` (misma señal de bloqueo; nunca divergen).
- `currentActivity` no contamina `lastDecisionAt`/`nextDecisionAt`.
- Δ motor financiero = 0: `ExecuteTrade`, ledger, posiciones y settlement intactos.

## Qué no cambia

Núcleo financiero. El criterio de operación en curso, «Orden pendiente»/«Ejecución parcial»/
«Precio aplicado», el banner `SIMULACIÓN — DINERO VIRTUAL` y la separación latido/decisión de
`v2.88.78`. El tag `v2.88.76-beta` permanece.

## Verificación

- Python: `derive_activity` (sin cambio), `_header` expone `currentActivityAt` + medición,
  `persistent_turn` emite `state=BLOCKED` con kill activo y `RUNNING` sin kill.
- TS: `activityLabel(value, measurement)` (medición gobernante), `isActivityStale`, `buildAutoHomeSummary`
  y `buildAutoBasicHome` (frescura), páginas HOME y Sistema.
- Contrato: `contract:gen` + `contract:check` verdes (cambio aditivo).

## Cita POST-TAG

No hay tag de `v2.88.80-beta`. No se inventa un veredicto de `Release tag CI`.
