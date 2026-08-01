# Asistente Play · embudo 1-Play (diseño 2026-07-29)

> **Estado:** decisiones cerradas · **Play A–D + CORE-P v1 implementados** (2026-07-29).  
> Complementa [`research-lifecycle.md`](./research-lifecycle.md) § Embudo D · Lista AUTO  
> y [`backtesting-funnel-handoff-2026-07-29.md`](./backtesting-funnel-handoff-2026-07-29.md).  
> Binding: [`profile-coach-lab-binding.md`](./profile-coach-lab-binding.md).  
> **No descongela** auto-paper D.

### Implementado en código

| Pieza | Código |
|-------|--------|
| Pref `includeFinalistsInBattery` (default ON) | `backtest-assistant-prefs.ts` + rail |
| Pref **`labEvenIfWeak`** (default OFF) | Check rail «Si Coach débil → pasar a Lab» · manda el gate |
| Lote Genéricas ∪ Finalistas valor | `mergeUniverseTargetIds` / `finalistMatrixRowIds` → `runExploreValue` |
| Reset embudo al cambiar instrumento | `selectInstrument` |
| Gate Coach¹→Lab × perfil (CORE-P) | `coach-profile-policy.ts` · `shouldAdvanceToLab` |
| Débil + perfil no agresivo → `skip_lab` → Lista next | mismo efecto + `settleFullCycle` |
| Stamp perfil + techo DD Lab + rail + invalidate | CORE-P v1 · `profile-coach-lab-binding.md` |
| `requireRunId` al guardar Finalistas post-Lab | `buildCoachTopSlots` · explore panel |
| Fix race 2º Play (universeDone stale) | `withUniverseDone` + `progress` en `executeAssistantStep` · settle autosave tras mutate |

Pendiente: CORE-R auto/scheduler · CORE A/B ciclo 2. **Mapa IA** + CORE-P/A/B/R v0 hechos.

---

## 0. Decisiones cerradas (usuario)

| # | Pregunta | Decisión |
|---|----------|----------|
| 1 | Gate “débil → Lab?” | **No es un check suelto.** Debe alinearse con el **perfil de la cuenta activa** (horizonte / riesgo / plantilla). Ver §3 CORE-P. |
| 2 | Lote reanálisis | Genéricas ∪ **solo Finalistas de ese valor** (no biblioteca global). |
| 3 | Débil en Lista AUTO | **Sí:** settle `skip_lab` y **pasar al siguiente** instrumento (no bloquear la campaña). |
| 4 | ¿Play primero o deep Coach? | **Primero que Play funcione de punta a punta**; después mejorar el soft del Coach (CORE A) de forma iterativa. |

---

## 1. Veredicto

Embudo correcto. Prioridad de entrega:

1. **Play 1-instrumento + Lista AUTO** serial, reset limpio, lote Genéricas∪Finalistas-valor, gate débil **según perfil**, settle + next.
2. **Mapa IA** en Configuración / Ayuda (dónde hay LLM vs ranking local vs Lab) — aclaración de producto ya (§8).
3. **CORE-P Perfil↔Coach** — estudio + módulo en profundidad **cuanto antes** (vinculación hoy es parcial).
4. **CORE A Coach soft** — tras Play estable.
5. **CORE B Lab IA** — deep-dive posterior.

---

## 2. Flujo objetivo (1 instrumento · 1 Play)

```text
[Play]  (+ cuenta activa con perfil de inversor)
   │
   ▼
① RESET + LOTE
   · Reinicia progreso Asistente (✓ de pasada)
   · Selecciona TODAS las Genéricas
   · ∪ Finalistas del instrumentId actual (si hay TOP)
   · NO incluye Mis estrategias globales (includeMine sigue OFF por defecto)
   │
   ▼  wait: matriz 100%
② SIMULACIÓN → TABLA (periodReturns)
   │
   ▼  wait: rank + dual-audit
③ COACH¹  ← CORE A  (contexto = perfil cuenta activa)
   · Ranking local + horizonte/riesgo del perfil
   · Dual-audit → Consenso | Discrepancia | Débil
   · TOP-3
   · Gate débil ← política del PERFIL (no check suelto):
        · perfil conservador / low risk → NO Lab si débil → settle skip_lab → (Lista: next)
        · perfil agresivo / high → puede permitir Lab aunque débil
        · (detalle en CORE-P)
   │
   ▼  wait: Lab 3 zonas
④ LAB  ← CORE B
   │
   ▼  wait: Coach²
⑤ COACH² → FINALISTAS (runId obligatorio)
   · save solo con mejora Lab + canSave; no pisar active sin mejora
   │
   ▼
⑥ SETTLE → fin | Lista AUTO next → ①
```

### Secuencia (contrato duro)

| Regla | Motivo |
|-------|--------|
| Serial estricto | Lab/matriz lentos |
| ↻ cancela ciclo + Lista AUTO | Control humano |
| Soft cap 40 | Paridad Monitor / Fase C |
| Sin mejora Lab → no pisar `active` | Política ya vigente |
| Débil + perfil no permite Lab → next ticker | Campaña IBEX no se atasca |

---

## 3. CORE-P — Perfil de cuenta ↔ Coach / Lab (**URGENTE · estudio profundo**)

### Por qué importa

El usuario elige una **cuenta de inversión** con **perfil declarado** (horizonte, riesgo, plantilla).
Las estrategias que propone el Coach **deben ser coherentes con ese perfil**.
Si no, el embudo selecciona “mejores” en abstracto — no “mejores *para este inversor*”.

### Qué hay hoy (parcial → v1)

| Pieza | Estado |
|-------|--------|
| Cuenta activa (`useActiveAccount`) | Sí |
| Perfil activo de cuenta (`getAccountActiveProfile`) | Sí — Coach + Lab + rail |
| Score Coach usa horizonte/riesgo (+ techo DD policy) | Sí |
| Gate débil / “¿pasar a Lab?” según perfil | **Sí** (`shouldAdvanceToLab` + check Asistente) |
| Lab respeta techo DD del perfil | **Sí** (`labImprovedRespectingProfileDd`) |
| Finalistas stamp `profileId` / `policyVersion` | **Sí** |
| Cambio de cuenta a mitad de Play | **Sí** — abort + mensaje |

### Qué debe ser el módulo (deep-dive cuanto antes)

Documento / ADR dedicado (siguiente): `docs/engineering/profile-coach-lab-binding.md` (pendiente de redactar en la pasada CORE-P).

Alcance:

1. **Contrato de contexto:** Account → ActiveProfile → `CoachProfilePolicy` (umbrales weak, `allowLabIfWeak`, techos DD, familias preferidas, `futureWeight` sugerido).
2. **UI:** rail Asistente muestra “Perfil: Swing · riesgo moderate · cuenta X”; si no hay perfil → bloquear Play o usar defaults explícitos + warning.
3. **Gate Coach¹:** `shouldAdvanceToLab(audit, policy)` — sustituye el check suelto `labEvenIfWeak`.
4. **Lab:** semillas y stop-rules conscientes de riesgo (no adoptar Mejor que rompa perfil).
5. **Coach² / Finalistas:** stamp de `profileId` / `ruleVersion` en TOP o facts (auditabilidad).
6. **Tests:** mismo lote + dos perfiles → TOP o gate distintos.
7. **Ayuda / Config IA:** sección “Perfil guía al Coach”.

> **Anotación de prioridad:** CORE-P **antes o en paralelo temprano** al pulido del soft Coach; sin esto el embudo “funciona” pero no está *coordinado con el inversor*.

### Prefs Asistente (ajustadas)

| Pref | Default | Rol |
|------|---------|-----|
| `fullCycleOnPlay` | ON | Un Play = embudo |
| `universe.selectAllGenerics` | ON | Lote base |
| **`universe.includeFinalistsInBattery`** | **ON** | Genéricas ∪ Finalistas **del valor** |
| `universe.includeMineStrategies` | OFF | No meter biblioteca global |
| **`coach.labEvenIfWeak`** | **OFF** | Check Asistente: si Coach¹ débil → ¿pasar a Lab? (**manda** sobre perfil) |
| `coach.futureWeight` | 0.42 (o override perfil) | Sesgo tramo reciente |

**Fallback:** sin check explícito en llamada a gate → usa `policy.allowLabIfWeak` (perfil). En UI el check siempre se pasa.

---

## 4. Gap vs implementación actual

| # | Requisito | Hoy | Gap |
|---|-----------|-----|-----|
| 1 | Reset + Genéricas∪Finalistas-valor | Parcial | Reset forzoso + inyección Finalistas del TOP |
| 2 | Matriz → Coach serial | Casi | Guards explícitos en ciclo |
| 3 | Gate débil × perfil | Solo horizon/risk en score | CORE-P + `shouldAdvanceToLab` |
| 4 | Lab / Coach² / runId | Auto save + issue AENA | runId obligatorio |
| 5 | Lista AUTO next si débil | Settle genérico | `skip_lab` + advance |
| 6 | Mapa IA en Config/Ayuda | **Hecho** — Ayuda → Plataforma IA «Dónde usamos IA» | `ai-platform-tracker.ts` · `AI_WHERE_MAP` |

---

## 5. Genéricas ∪ Finalistas del valor

**Cerrado:** solo Finalistas de ese `instrumentId`.

- Genéricas = descubrimiento de familias.
- Finalistas = stress-test del status quo del valor.
- Dedupe por `strategyType`; preferir def con `strategyDefinitionId` del valor.

---

## 6. CORE A / B (tras Play estable)

### CORE A — Coach soft (iterativo)

Ranking local + dual-audit + aprendizaje (Evidence/Belief, outcomes).  
LLM **narra**, no elige el TOP.  
Mejorar soft en ciclos cortos *después* de Play verde.

**Hecho (v0 · 2026-07-29):** pref `coach.llmNarrate` (rail) · honor en Coach UI · tests invariante no-corona-TOP · hint «pasada anterior» desde `coachFacts.dualAudit` (sin modular ★).

**Siguiente ciclo:** modular score con outcomes / Belief (requiere decisión; Belief UI congelada).

### CORE B — Lab IA

Grids OOS/WF + memoria de adopciones; deep-dive propio más adelante.

**Hecho (v0 · 2026-07-29):** `lab-adoption-memory` (localStorage) · espacio guiado al reabrir Lab (misma familia) · hint «Adopción previa» · stamp `coachFacts.labAdoption` al guardar Finalistas post-Lab.

**Siguiente ciclo:** meseta heatmap → rango; familias preferidas por horizonte (CORE-P); sin reabrir P3–P9.

---

## 7. “Garantía 100%”

Operativa (orden, lote, no-pisar, serial) ≠ garantía de alpha.

---

## 8. Mapa de IA en la app (aclarar Configuración / Ayuda)

Hoy la confusión es real: “IA” mezcla **ranking local**, **LLM narrador**, **Lab/optimize**, **DecisionRuntime/F3**, **indicadores por prompt**. Hay que explicitarlo en **Configuración → módulos IA** y/o Ayuda → Plataforma IA.

| Punto de la app | ¿Qué “IA”? | Rol real hoy | Ranking / PnL |
|-----------------|------------|--------------|---------------|
| **Coach ★ (embudo)** | Motor **local** + opcional LLM narrador | Selección TOP-3 / futuro | Ranking = local; LLM no escribe TOP |
| **Dual-audit Coach** | Heurística + opcional LLM veto/adversario | Confianza Consenso/Discrepancia/Débil | Gate de honestidad |
| **Lab / Optimizar** | Grids deterministas (H0/VBT/Optuna) | Mejora params + OOS | No es LLM |
| **Crear estrategias / indicadores** | LLM → draft JSON (governance proxy) | Borrador; compute determinista | No ordena |
| **Supervisado F3** | Assessments + DecisionRuntime + LLM opcional en narración | Propose → humano | Gate hard/pasivo |
| **paper_auto (radar)** | Policy Gate + evidencias | Auto paper etiquetado B | Sin checklist Lab |
| **Análisis del valor** | WeightContext / DecisionSession | FA+perfil | Distinto del Coach AT |

**Principio (inalterable):** el LLM nunca envía órdenes ni calcula PnL contable; no sustituye ranking Coach ni Gate.

**Trabajo de producto (Config IA):**

1. ~~Pantalla/sección “Dónde usamos IA”~~ — **hecho** en Ayuda → Plataforma IA (`AI_WHERE_MAP`).
2. Enlaces a CORE A / CORE B / CORE-P (objetivos del tracker).
3. Toggle claros: ~~“Narración LLM Coach ON/OFF”~~ — **hecho** (`coach.llmNarrate` en rail). Ranking siempre local.

---

## 9. Competencia (resumen)

Otros: chat → backtest → WFA → paper.  
Nosotros: **por valor**, Finalistas vivos, ranking determinista, Lab OOS, Lista AUTO índice, perfil de cuenta como brújula (CORE-P), puertas A/B/C.

---

## 10. Orden de implementación

```text
A. Prefs includeFinalistsInBattery + reset lote + wait serial + skip_lab→next
B. Fallback gate débil conservador (hasta CORE-P)
C. runId en promoción Finalistas
D. Tests + audit IBEX
E. UI mapa IA (Ayuda → Plataforma IA) — **hecho**
F. CORE-P estudio + módulo — **v1 hecho** (iteraciones en binding doc)
G. CORE A soft Coach — **v0 hecho** (toggle LLM + invariantes); Belief→Coach = ciclo 2
H. CORE B Lab IA — **v0 hecho** (memoria + espacio guiado); meseta/familias = ciclo 2
I. **CORE-R reevaluación continua** — **v0 manual hecho**; auto/scheduler = ciclo 2
```

---

## 11. Referencias código

- Prefs: `backtest-assistant-prefs.ts`
- Ciclo / Lista: `backtest-assistant-full-cycle.ts`, `backtest-list-auto.ts`, `backtest-list-auto-board.ts`, `backtests-page.tsx`
- Coach + perfil hoy: `backtest-explore-panel.tsx` (carga perfil), `backtest-deep-coach.ts`
- Dual-audit: `coach-dual-audit.ts`
- IA tracker: `ai-platform-tracker.ts` · `docs/AI_PLATFORM_SOLUTION.md`
- Issues: `research/observations/ISSUES.md` (**CORE-P**, **CORE-R**)
