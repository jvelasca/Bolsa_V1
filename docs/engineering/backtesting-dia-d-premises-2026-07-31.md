# Premisas — Backtesting DÍA D (2026-07-31)

> Decisiones de producto **bloqueadas** + guía de arranque.  
> Complementa [research-lifecycle.md](./research-lifecycle.md), [UI_PREFS_LOCALSTORAGE.md](../UI_PREFS_LOCALSTORAGE.md), [account-premises-demo-vs-paper-2026-07-31.md](./account-premises-demo-vs-paper-2026-07-31.md), [HELP.md](../HELP.md), [operativa-test-plan-2026-07-31.md](./operativa-test-plan-2026-07-31.md).  
> **Ayuda en app:** (?) → Backtesting → tarjeta «Backtesting DÍA D».

**AsOf:** 2026-07-31 · Investigación: **Backtesting DÍA D** · Operación: **Trading MODO DÍA D** · Producto: **v0.11 operable**

---

## 0. Cómo arrancar (usuario)

Estado actual: **v0.11 operable** (DÍA D v1 cerrado en producto; mejoras opcionales aparte).

1. Abre **Backtesting** → pestaña **Probar estrategia**.  
2. En el bloque **Backtesting DÍA D** (debajo del selector de valor), elige una **fecha pasada**.  
3. Elige un valor con histórico → **Play** (ciclo completo) hasta **Finalistas**.  
4. En Finalistas, fila **#1** → botón **Simular D→hoy**.  
5. Entras en **Trading** con banner **MODO DÍA D** + **película** + modos **Manual / Semi / Auto**.  
6. Opcional: **Pantalla completa** · **Narrar con IA** · **Guardar Evidence**.  
7. **Salir DÍA D** en el banner cierra el sandbox (no escribe la DEMO live).

| Si no ves… | Causa habitual |
|------------|----------------|
| Bloque DÍA D | Estás en otra pestaña (Biblioteca / Historial), no en Probar |
| Botón Simular D→hoy | Fecha DÍA D = hoy, o no hay #1 con `strategyDefinitionId` |
| Película en Trading | No pulsaste Simular (solo cambiaste de ruta a /trading) |
| Guardar → Fase 2 | API sin reiniciar tras pull (`POST /api/research/dia-d-session-evidence`) |

**Offline:** `pnpm test:operativa` · checklist UI: [operativa-test-plan-2026-07-31.md](./operativa-test-plan-2026-07-31.md).

---

## 1. Qué es

Simular que «hoy» es una fecha pasada **D**, construir el embudo (Probar → Coach → Lab → Finalistas) **solo con información ≤ D**, y luego **verificar** qué habría pasado operando desde D hasta el presente.

| Fase | Nombre interno | Pregunta | Datos |
|------|----------------|----------|-------|
| **A** | As-of | ¿Qué sé el día D? | Todo point-in-time ≤ D |
| **B** | Embudo ≤ D | ¿TOP / Coach / Lab? | Solo ≤ D (mismo Play actual) |
| **C** | Replay D→hoy | ¿Y si hubiera operado? | Barras D→hoy · reglas **fijadas** en B |

Default de D = **hoy** → comportamiento actual de Backtesting (sin cambio percibido).

---

## 2. Decisiones bloqueadas

| # | Tema | Decisión |
|---|------|----------|
| 1 | **Nombre UI (investigación)** | **Backtesting DÍA D** |
| 2 | **Replay opera** | Solo la estrategia **#1** (mejor Finalista / slot activo #1), no las 3 en paralelo |
| 3 | **Re-Lab en C** | **Prohibido en v1.** Params y definición de #1 quedan **congelados** el día D |
| 4 | **FA / Composite / scores** | **También cortados a D** (point-in-time; sin trampas) |
| 5 | **Arquitectura UI** | **Híbrido:** A+B en Backtesting · C en **Trading MODO DÍA D** |
| 6 | **Película** | Embebida por defecto · **pantalla completa** opcional (banner / toolbar) |
| 7 | **Modos de mesa (C)** | Exactamente **tres:** **Manual** · **Semi** · **Auto** (contrato §3c). Selector obligatorio al entrar en Trading DÍA D |

### Qué significaba «re-Lab» (punto 3)

Re-optimizar params *mientras* avanza D→hoy. **No en v1:** el día D eliges #1 y no la tocas.

---

## 3. UI — híbrido bloqueado

```text
Backtesting (DÍA D)                 Trading (MODO DÍA D)
  fecha D · embudo ≤ D         →      banner MODO DÍA D
  Finalistas → #1              →      Manual | Semi | Auto  (determinan la mesa)
  CTA «Simular operación D→hoy» →     sandbox ≠ DEMO live
                                   →  película embebida (motor movie) + informe
```

| Pieza | Dónde | Notas |
|-------|--------|-------|
| Control fecha **DÍA D** | Backtesting · Probar | Default = hoy |
| Embudo Play/Coach/Lab/Finalistas | Backtesting | Sin look-ahead &gt; D |
| CTA tras #1 | Backtesting → Trading | Handoff: instrumentId, #1, D, end=hoy |
| Selector Manual / Semi / Auto | Trading DÍA D | Lo que más cambia la UX de C |
| Órdenes / posiciones / alertas | Trading DÍA D | Mesa operativa en tiempo simulado |
| Película (scrubber / play / HUD) | Embebida o **pantalla completa** | Misma familia que `backtest-replay-chart` · toggle banner |
| Prefs UI | `localStorage` | [UI_PREFS_LOCALSTORAGE](../UI_PREFS_LOCALSTORAGE.md) |

**No** mover Coach/Lab/Finalistas a Trading.  
**No** escribir el ledger DEMO “de verdad”: sesión **sandbox** aislada; al salir, DEMO live intacta.

### 3c. Contrato Manual · Semi · Auto (bloqueado)

Misma #1, mismo D→hoy, mismo sandbox. Solo cambia **quién decide** y **cómo avanza el reloj / la película**.

| | **Manual** | **Semi** | **Auto** |
|---|------------|----------|----------|
| **Analogía viva** | Mesa + Checklist (tú operas) | Supervisado F3 (proponen, tú confirmas) | Radar / auto demo (sin clic) |
| **Señal de #1** | Aviso / alarma en mesa | Propuesta de orden (entrada/salida) | Orden → fill simulado solo |
| **Fill** | Solo si el usuario coloca / confirma la orden | Solo tras **Aceptar** (o rechazo explícito) | Automático según reglas de #1 |
| **Rechazo / skip** | Ignorar señal; seguir | **Rechazar** descarta esa señal | N/A (no hay gate humano) |
| **Reloj simulado** | Avanza con *Siguiente barra/día*, play lento, o tras operar | **Pausa** en cada propuesta; reanuda al decidir o *Saltar* | Continuo (play película) |
| **Película embebida** | Usuario manda el avance; HUD al cursor | Se detiene en forks de decisión | Play continuo + scrubber libre |
| **v1 implementación** | Tras Auto | Tras Auto | **Primero** (camino feliz de verificación) |

**Común a los tres**

- Estrategia **#1 congelada** (sin re-Lab).  
- Datos / FA visibles en mesa: solo ≤ reloj simulado (sigue point-in-time).  
- Costes / slippage: misma política que backtest DEMO (a fijar en spec técnica).  
- Salida: informe de sesión C **por modo** (no mezclar Manual y Auto en un solo equity).  
- Cambiar de modo = **nueva sesión** (o reinicio explícito); no mutar a mitad un equity a otro modo.

**No es**

- Manual ≠ “sin estrategia” (sigue habiendo #1 como guía/alerta).  
- Semi ≠ reabrir el embudo Coach/Lab.  
- Auto DÍA D ≠ Camino D live (`PAPER_D_EXECUTE`); es sandbox histórico.

---

## 4. Reglas duras

1. **Point-in-time:** precios, FA, composite, Coach, Lab y Finalistas de B solo ven ≤ D.
2. **Congelar #1 en C:** sin re-opt / re-Lab / re-Coach que use barras &gt; D.
3. **Dos informes:** métricas embudo (≤ D) ≠ métricas sesión Trading DÍA D (D→hoy).
4. **TOP-3 en B** sigue existiendo; **C solo ejecuta #1**.
5. **Sandbox ≠ DEMO live.**

---

## 5. Fuera de v1 (explícito)

- Re-Lab / re-opt periódico durante C  
- Operar las 3 Finalistas en paralelo en C  
- Cron CORE-R multi-dispositivo (cola hoy en localStorage; shell cron v1.4 cubre app abierta)  
- App/ruta “Verificación” separada del shell Trading  
- Sync cross-device de prefs (sigue localStorage)

---

## 6. Siguiente paso (cuando se retome)

**Hecho (v0 UI · 2026-07-31):** campo DÍA D en Probar · corte `dateTo` en ventana BT · sello/CTA Finalistas · handoff Trading banner + modos.

**Hecho (v0.2 · 2026-07-31):** película desde el inicio · **Semi** pausa en cada señal (Aceptar/Rechazar → log; equity sigue Auto) · **Informe** lateral · Manual = avance manual (▶).

**Hecho (v0.6 · 2026-07-31):** Informe Evidence sesión C — band/claims/párrafos deterministas + `POST /api/ai/dia-d/session-evidence` (LLM opcional; sin FA/Coach).

**Hecho (v0.7 · 2026-07-31):** **Guardar Evidence** — archivo local `bolsa-dia-d-evidence-archive-v1` + persist Fase 2 `POST /api/research/dia-d-session-evidence` (`source=dia_d_session`, sin Belief).

**Hecho (v0.8 · 2026-07-31):** Película **pantalla completa** (`fullBleedMovie` en sesión · oculta docks Trading).

**Hecho (fix · 2026-08-01):** `fullBleedMovie` **no se persiste** en localStorage. Al recargar siempre vuelven watchlist/gráfico/Operaciones. «Salir DÍA D» cierra la sesión sandbox.

**Hecho (v0.9 · 2026-07-31):** **Archivo Evidence** — lista por símbolo · preview párrafos · export JSON · quitar (`dia-d-evidence-archive-io.ts`).

**Hecho (v0.10 · 2026-07-31):** **Importar JSON** al archivo (mismo `instrumentId`; round-trip `dia_d_evidence_export_v1`).

**Hecho (v0.11 · 2026-07-31):** **Archivo en Ayuda** → Backtesting (`DiaDEvidenceArchiveHelpCard`: preview / JSON / quitar).

**Pendiente:** (ninguno crítico DÍA D v1).

---

## 7. Código + tests (índice)

| Pieza | Path |
|-------|------|
| Sesión / full-bleed | `apps/web/src/stores/dia-d-trading-session-store.ts` |
| Banner / layout | `trading-dia-d-banner.tsx` · `trading-layout.tsx` |
| Replay + Evidence UI | `trading-dia-d-replay-panel.tsx` |
| Gate equity | `dia-d-gate-equity.ts` |
| Evidence heurística web | `dia-d-session-evidence.ts` |
| Archivo local | `dia-d-evidence-archive-store.ts` · `dia-d-evidence-archive-io.ts` |
| Evidence py | `packages/py/analytics/.../dia_d_session_evidence.py` |
| Explain + API | `explain_dia_d_session_evidence.py` · `POST /api/ai/dia-d/session-evidence` |
| Persist Fase 2 | `emit_evidence_for_dia_d_session` · `POST /api/research/dia-d-session-evidence` |
| asOf FA | `fundamentals_as_of.py` · `as_of_cut.py` |

```bash
pnpm test:operativa
pnpm --filter @bolsa/web exec vitest run \
  src/features/trading/dia-d-gate-equity.test.ts \
  src/features/trading/dia-d-session-evidence.test.ts \
  src/stores/dia-d-evidence-archive-store.test.ts \
  src/stores/dia-d-trading-session-store.test.ts
```
