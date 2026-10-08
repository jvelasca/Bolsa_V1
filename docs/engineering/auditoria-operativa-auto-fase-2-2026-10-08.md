# Auditoría FASE 2 — operativa AUTO de extremo a extremo

> **AsOf:** 2026-10-08 · **Base auditada:** `v2.88.94-beta` (tag objeto `0671ae15` → commit `20fd538c`; `Release tag CI` [`37823112083`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37823112083) **VERDE**).
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · **Contrato:** [`spec-ui-contract-5-0-2026-10-08.md`](./spec-ui-contract-5-0-2026-10-08.md).
> **Cierra:** la auditoría previa se da por **🟢 VERDE** (`v2.88.94-beta` cierra los 6 P1 de `v2.88.93-beta`).

## 1. Alcance y método

Se recorre la cadena completa de la operativa AUTO —

```
Oportunidad → Ranking → Decisión → Orden → Ejecución → Posición
→ Resultado → Dinero virtual → Riesgo → Cierre/P&L
```

— preguntando, en cada eslabón: **(a)** ¿hay una superficie de primer nivel en lenguaje de usuario?, **(b)** ¿es honesta con el dato ausente (`UNKNOWN ≠ 0`, «Sin dato todavía»/`NO MEDIDO`)?, **(c)** ¿respeta `ranking ≠ decisión` y la escalera que no salta peldaños?

Método: lectura de los **view-models puros** que alimentan cada superficie (no de las pantallas), más verificación de invariantes por test. No se consulta la documentación como fuente de verdad: la fuente es el código de `v2.88.94-beta`.

## 2. Cadena, eslabón por eslabón

### 2.1 Oportunidad — 🟡 (hueco declarado)
- **Superficie:** `Hoy → Oportunidades` (universo completo) · `AUTO → Operar` TOP3 (subconjunto), con copy que explica la relación (`UI5-07`). `apps/web/src/features/auto/auto-operar-page.tsx`.
- **Honestidad:** la etapa `OPPORTUNITY` de la historia es `CONTEXT`/`NOT_MEASURED` («el watch PIT no se materializa por ciclo», `packages/shared/src/cognitive/auto-operation-story.ts`).
- **Hueco:** un usuario no puede ver **de dónde salió esta oportunidad concreta**. Declarado, no fabricado.

### 2.2 Ranking (Selección · TOP-N) — 🟡 (hueco parcial)
- **Superficie:** `AUTO → Operar` TOP3 + nota «Ranking ≠ decisión» (`OPERATION_LADDER_NOTES.rankingIsNotDecision`).
- **Honestidad:** `SELECTION` se copia del paso `TOP_N`; el **motivo** del ranking se declara `NO MEDIDO` (`auto-operation-story.ts`, contexto `RANKING`).
- **Hueco:** no se explica *por qué* ese activo entró en el TOP3.

### 2.3 Decisión — 🟡 (hueco declarado, deuda de motor)
- **Superficie:** HOME «Decisión de cartera» (`auto-home-page.tsx`) → «Sin dato todavía»; historia `DECISION` = `NOT_MEASURED` («no hay traza durable de decisión de cartera»).
- **Honestidad:** impecable; `decisionLabel` es siempre el hueco (`auto-basic-home.ts`).
- **Hueco (motor):** no existe `PortfolioDecision` durable. La cadena `oportunidad → ranking → (decisión) → orden` tiene el eslabón central vacío.

### 2.4 Orden — 🟢
- **Superficie:** escalera «Orden preparada/enviada» (`auto-operation-ladder.ts`); ranura «Orden» (`Hecho`/`Pendiente`/`No ocurrió`, `auto-operation-card.ts`); actividad «Orden anotada».
- **Honestidad:** fail-closed; sin paso `ORDER` alcanzado, hueco.

### 2.5 Ejecución — 🟢 (ejemplar)
- **Superficie:** escalera «Esperando ejecución / Ejecución parcial / Ejecución completada»; ranura «Ejecución» con `aplicado/pedido`; nota «Precio aplicado ≠ posición creada».
- **Honestidad:** se detiene si la medición no es `COMPLETE`; `applied < requested` ⇒ «Ejecución parcial».

### 2.6 Posición — 🟡 (hueco declarado, deuda de motor)
- **Superficie:** la escalera **se detiene antes de «Posición creada»** (`auto-operation-ladder.ts`), y la ranura «Posición» del ciclo sale de la **cuenta** (`positionsCount`), no de la operación.
- **Honestidad:** no se fabrica el peldaño a partir del fill; «Precio aplicado ≠ posición creada» se declara.
- **Hueco (motor):** una operación concreta **no afirma que creó posición**. Es el eslabón que un usuario básico querría cerrado.

### 2.7 Resultado — 🟡 (superficie densa)
- **Superficie:** etapas `SETTLEMENT` («Liquidación»/«Resultado de la venta») y `RESULT` («Resultado final», paso `CYCLE_CLOSED`), con `story.result.pnl` (`AutoMonitorCycleV1.result`); «Posición cerrada» exige `closedMeasurement === COMPLETE`.
- **Honestidad:** un cierre solo se afirma con medición.
- **Observación:** el resultado por operación vive en la **historia** (`/auto/operar/operacion/:id`), la superficie más densa del espacio.

### 2.8 Dinero virtual — 🟢
- **Superficie:** semáforo de realidad `DINERO VIRTUAL · AUTO DEMO · No envía órdenes a XTB` (`auto-reality.ts`, `auto-reality-strip.tsx`); cifras «N posiciones **en la cuenta simulada**», «Efectivo simulado», banner `SIMULACIÓN — DINERO VIRTUAL`.
- **Honestidad:** `buildAutoReality` nunca pinta `DINERO REAL`; una cuenta ausente se declara `NO MEDIDO` sin apagar el banner.

### 2.9 Riesgo — 🟢
- **Superficie:** `/auto/riesgo` con veredicto human-first (`Controlado`/`Atención`/`Bloqueado`/`Sin dato todavía`) y «Riesgo ahora mismo» (`auto-risk-summary.ts`).
- **Honestidad:** riesgo por posición / máxima pérdida / límite diario **no materializados** ⇒ `positionRiskAvailable: false`, declarados y enlazados a Cartera → Riesgo.

### 2.10 Cierre / P&L — 🔴 (hueco relevante)
- **Superficie:** escalera «Posición cerrada» (solo con medición); historia `RESULT`; «Historial de la cuenta» (`/history`); veredicto DÍA-D como aprendizaje.
- **Honestidad:** correcta.
- **Hueco:** el **resultado agregado de primer nivel es solo no realizado** («Resultado de la cuenta» = `totalUnrealizedPnl`, `auto-account-figures.ts`). **No existe** un «esto es lo que AUTO ha ganado/perdido» **realizado/acumulado** a primer nivel; obliga a salir a `/history`.

## 3. La pregunta central

> *¿Puede un usuario básico entender qué está haciendo AUTO, qué ha hecho realmente y qué resultado ha obtenido, sin entrar en pantallas técnicas ni interpretar datos por su cuenta?*

| Pregunta | Veredicto | Base |
|---|---|---|
| Qué **está haciendo** | **Sí** | Insignia de estado humano + línea de actividad (HOME). |
| Qué **ha hecho realmente** | **Casi** | Timeline de actividad + historia por operación; pero *de dónde salió* (Oportunidad/Ranking) y *si creó posición* son huecos declarados, no hechos. |
| Qué **resultado** obtuvo | **Parcial** | Por operación, sí (historia); agregado **realizado**, no (solo no realizado + `/history`). |

**Diagnóstico:** no es un problema de **coherencia** (la UI dice la verdad; cada ausencia se declara). Es un problema de **cobertura**: los eslabones 3, 6 y 10 están vacíos o sesgados a lo no realizado.

## 4. Separación SIM / XTB — 🟢 estricta

- `auto-reality.ts` (puro): AUTO nunca emite `DINERO REAL`; la cuenta activa **no** recolorea el modo de ejecución; un tipo ausente se declara `NO MEDIDO` sin apagar `DINERO VIRTUAL`.
- `live-virtual-banner.tsx`: `LIVE VIRTUAL · SIMULADO · no capital real` + «enviar una orden no significa que se haya ejecutado».
- No se encontró ningún camino por el que AUTO se presente como dinero real.

## 5. Hallazgos

| ID | Hallazgo | Naturaleza | Severidad |
|---|---|---|---|
| `F2-1` | Posición **por operación** no materializada (escalera se detiene en «Ejecución completada») | Deuda de **motor** (declarada) | Media |
| `F2-2` | `PortfolioDecision` durable ausente (Decisión = hueco) | Deuda de **motor** (declarada) | Media |
| `F2-3` | Resultado **realizado/acumulado** de AUTO no existe a primer nivel ni en el read-model de cuenta | Hueco **motor + UI** | **Alta** |
| `F2-4` | Motivo del ranking no materializado por ciclo | Deuda (declarada) | Baja |
| `F2-5` | Vocabulario: reaparece «CARTERA **DEMO**»/«Cuenta demo» frente a la unificación «dinero virtual» de UI 7.0 | Copy | Baja |
| `F2-6` | Dos vocabularios para dinero simulado: AUTO = «DINERO VIRTUAL»; camino manual/XTB = «LIVE VIRTUAL · SIMULADO» | Copy | Baja |

Verificación de `F2-3`: el DTO del monitor expone `result.pnl` por ciclo (`packages/shared/src/cognitive/auto-operational-monitor.ts`), pero el resumen de cuenta expone **solo** `totalUnrealizedPnl` (`apps/web/src/api/schema.d.ts`); el realizado existe a nivel de dominio (`packages/py/domain/.../lifecycle/__init__.py` → `realized_pnl`; `auto_simulation_worker.py` → `_sim_realized_pnl`) pero **no se publica** a la superficie de AUTO.

## 6. Semáforo FASE 2

**🟡 AMARILLO — cadena honesta y sin regresiones, pero no cerrada a primer nivel en Resultado/P&L.**

- **Sin regresiones:** `Δ motor = 0` (`git diff --name-only -- packages/py` vacío), gate de primer nivel intacto, `axe` E2E vigente.
- **Verificación local:** `auto`+`confirm`+`mesa`+`research` → **50 ficheros / 365 tests verdes**.
- **Lo que impide el 🟢:** `F2-3` (resultado agregado) y, si se toca motor, `F2-1`/`F2-2`.

## 7. Deudas que esta auditoría NO resuelve

Se declaran, no se fabrican: `PortfolioDecision` durable (`F2-2`), traza de materialización de posición por ciclo (`F2-1`), agregado de P&L realizado publicado a la superficie de AUTO (`F2-3`), motivo de selección durable por ciclo (`F2-4`).

## 8. Continuación

Plan de cierre (con motor): [`plan-cierre-operativa-auto-2026-10-08.md`](./plan-cierre-operativa-auto-2026-10-08.md).
