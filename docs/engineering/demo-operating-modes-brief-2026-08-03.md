# Brief — Modos operativos DEMO (MANUAL / SEMI / AUTO)

> **AsOf:** 2026-08-03 · **Estado:** decisiones **cerradas** · SEMI slice 1+1.1 en **main** · slice 1.2 cola F3→BD en curso.  
> **Padre:** [research-lifecycle.md](./research-lifecycle.md) § caminos A–E · [account-premises-demo-vs-paper-2026-07-31.md](./account-premises-demo-vs-paper-2026-07-31.md) · ADR-019/020/010.  
> **Freeze:** Belief→Coach · `CORE_R_CRON` off · Camino D / `PAPER_D_EXECUTE` · Strategy Studio / F5 · SCI─X─►TRD.

## Premisa de producto

Operar la **cuenta DEMO activa** con capital inicial, máx. **N posiciones abiertas** (configurable), sizing ~**10 % del cash disponible** por operación (ajustable), lista de vigilancia, TF **1d**, y tres modalidades:

| Modo | Comportamiento |
|------|----------------|
| **MANUAL** | Vigilancia + aviso. Sin fill DEMO salvo orden humana explícita. |
| **SEMI** | App propone (timing + pesos TA/FA + Gate + preferencias diversificación); **humano decide en Confirm** (puede discrepancia H≠M). |
| **AUTO** | App propone y ejecuta. **Fuera de slice 1** (Camino D congelado). |

Pruebas empiezan por **SEMI**.

## Veredicto

No hace falta un motor paper nuevo. El **canal de ejecución SEMI** es **Camino C** (cola F3 → Confirm → DEMO). El **modo operativo de cartera** es el interruptor de producto que decide *quién* puede rellenar esa cola (Finalistas, Radar/alarmas) y *cómo* se dimensiona/diversifica.

---

## Decisiones (2026-08-03 · usuario + defaults agente)

### 1. ¿Qué es SEMI? — **decisión agente (explicada)**

Hay dos capas distintas:

| Capa | Significado |
|------|-------------|
| **Modo de cartera** (MANUAL / SEMI / AUTO) | Política del *libro*: ¿solo aviso, Confirm, o auto-ejecutar? |
| **Canal de ejecución** | Cómo llega el fill a DEMO: hoy Camino C = Confirm F3 |

**Decisión:** SEMI = **modo de cartera** que:

- deja que **Finalistas (H)** y **Radar/alarmas (M)** alimenten la **misma cola de Confirm (Camino C)**;
- **nunca** ejecuta sin Confirm;
- MANUAL = mismas fuentes pero solo aviso (inbox/toast), sin encolar execute;
- AUTO (futuro) = mismas fuentes → execute sin Confirm (Camino D / `paper_auto`, freeze).

Así no inventamos un cuarto motor: un modo, un Confirm, varias fuentes.

### 2. Conflicto H (Finalista) ≠ M (momento)

**Cerrado:** se elige en **Confirm**. La UI debe mostrar ambos y dejar aceptar H, M, o rechazar.

### 3. Capacidad y sizing

**Cerrado:**

- Límite = **solo posiciones abiertas** (`maxOpenPositions`, configurable; p. ej. 10).
- Watchlist puede ser más larga (vigilancia); no cuenta como “ocupación” del tope.
- **Sizing por defecto ≈ 10 % del cash disponible** en la cuenta DEMO en el momento de la propuesta (ej. 20 000 → ~2 000 €/op).
- Editable en Confirm antes de ejecutar.
- Si el equity baja → menos operaciones / tickets más pequeños; si sube → más room bajo el mismo % y el mismo N.

### 4. Diversificación país + sector

**Cerrado (preferencia suave, no veto duro):**

1. Primero: candidatos en **punto óptimo** de inversión (H+M / rating+FA).  
2. Entre óptimos: preferir **mismo país** que la cartera / domicilio operativo.  
3. Luego **Europa**.  
4. Luego **mundial**.  

Motivo: menos FX y fricción broker. Si no hay óptimo local, **no bloquear** — invertir en el mejor óptimo disponible.

Sector: reutilizar `maxSectorExposurePct` del Gate; país = **scoring de preferencia** en el ranker de propuestas (slice 1+), no hard-fail v1.

### 5. «Aprender» — **todo, pero por fases (freeze)**

Pedido: auditoría + tenure + pesos. Con freeze Belief→Coach:

| Fase | Qué | ¿Cuándo? |
|------|-----|----------|
| **5a · SEMI slice 1** | DecisionSession + learning-summary (auditoría) + **tenure Mandato** al Confirm | Ahora |
| **5b** | Revisar tenures / outcomes en Coach rail (humano decide cambios) | Justo después |
| **5c** | Auto-ajuste WeightRules / Belief→Coach | **Solo al levantar freeze** |

No mentimos: “aprender” empieza como **memoria auditable + mandato**; el piloto automático de pesos espera el deshielo.

### 6. Cola F3 ¿navegador o base de datos? — **explicación**

Hoy la cola Supervised F3 vive en **sessionStorage del navegador** (Zustand persist):

- Cierras la pestaña / otro PC / otro navegador → **se pierde** la cola de propuestas pendientes.
- En el **mismo** navegador/sesión de pruebas SEMI → funciona.

**Decisión slice 1:** sessionStorage **OK** para pruebas en un puesto.  
**Decisión slice 1.2:** persistir cola en BD ligada a `accountId` (multi-dispositivo / no perder Confirm) — tabla `supervised_f3_account_state` + hydrate/push.

### 7. Confirm lote vs por valor — **default agente**

**Híbrido:** pantalla de lote (todas las propuestas del ciclo) con **checks por valor** + «Confirmar seleccionadas». Un clic puede aceptar N; también se puede ir una a una.

### 8. Capital — **default agente**

**Solo cash DEMO** (depósito / equity disponible). No hay “risk budget” paralelo en v1: el 10 % se calcula sobre cash (o equity libre según Gate). Risk budget aparte = v2 si hace falta.

---

## Responsabilidades (sin cambio)

| Contexto | Dueño | No hace |
|----------|--------|---------|
| **LAB** | Embudo, Finalistas, DÍA D Verify, CORE-R lectura | Fills DEMO |
| **TRADING** | DEMO ledger, Gate, Mandato, F3 Confirm, OrderIntent, modo cartera | Re-lab / crowning científico |
| **Radar** | Listas, trackers, hybrid + FA, alarmas → cola SEMI | Coronar Finalistas sin Lab |
| **Cognición** | WeightContext / WeightRules, DecisionSession | Auto-Belief (freeze) |

## Dual estrategia

| Capa | Fuente | Rol SEMI |
|------|--------|----------|
| **H · Histórico** | Finalistas TOP | Playbook / tenure propuesto |
| **M · Momento** | Tracker / hybrid + FA | Timing / alternativa en Confirm |
| **Pesos** | WeightRules 1d | Explicar Confirm (read-only slice 1) |

## Slice 1 — SEMI (actualizado)

1. Interruptor de modo cartera DEMO: MANUAL | SEMI (AUTO disabled/grey).  
2. Libro v0: `maxOpenPositions` + sizing default 10 % cash + lista vigilancia.  
3. Fuentes → cola F3: Finalistas Proponer + (si SEMI) alarmas Radar elegibles.  
4. Confirm híbrido: lote + checks; mostrar H vs M si discrepan; sizing editable.  
5. Execute → DEMO + tenure Mandato + DecisionSession.  
6. Ranker suave: óptimo primero; preferencia país→EU→mundo (sin veto).  
7. **Fuera:** AUTO, Belief/WeightRules auto, cola BD (salvo dolor), country hard-cap.

**Éxito:** con DEMO 20k / N=10 / SEMI ON → propuestas ~2k € → Confirm (eligiendo H o M si hace falta) → posiciones + tenures visibles.

## Freezes (no reabrir en slice 1)

Belief→Coach · `CORE_R_CRON` · AUTO / `PAPER_D_EXECUTE` · Strategy Studio / F5 · SCI─X─►TRD fills.

## Referencias

- `paper-paths-copy.ts` · `supervised-f3-panel.tsx` · `finalist-propose-supervised.ts` · `supervised-f3-queue-store.ts`  
- `trading-policy.ts` (`maxOpenPositions`) · WeightRules · OrderIntent · DecisionSession  
- `docs/HYBRID_TRACKERS.md` · ADR-010 · ADR-019 · ADR-020  

## Siguiente paso

**Go** del usuario → brief de implementación SEMI slice 1 (tareas + checklist de prueba en DEMO) · **sin** AUTO ni Belief auto-tune.
