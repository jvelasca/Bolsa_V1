# ADR 021: Reconciliación DÍA D — F-hoy · F-D · V-D→hoy

## Estado

**Aceptado** — 2026-08-02 · **Implementación: cliente v1 (este ADR)**  
**Tipo:** decisión de producto / metodología de validación (LAB).  
**Depende de:** [ADR-019](./019-dual-universes-lab-vs-trading.md), premisas [DÍA D](../engineering/backtesting-dia-d-premises-2026-07-31.md), [ADR-020](./020-operating-mandate-tenure.md) (confianza del mandato).

---

## 1. Contexto

DÍA D ya tiene tres fases (A as-of · B embudo ≤ D · C replay D→hoy). En código, el Play con D **pisaba** el único TOP Finalistas: se perdía la Finalista operativa “de hoy” y **no** existía un juicio explícito:

> ¿La estrategia que habría elegido el día D (y que verifico D→hoy) es **igual o distinta** a la Finalista #1 que propongo ahora?

Eso es el diferencial vs TradingView (walk-forward manual), QuantConnect (reconciliation misma estrategia) y journals (tags por trade).

---

## 2. Decisión

### 2.1 Tres artefactos (nombres canónicos)

| Artefacto | ES | Pregunta | Persistencia v1 |
|-----------|-----|----------|-----------------|
| **F-hoy** | Finalistas operativos | ¿Qué TOP propongo **ahora**? | BD `instrument_strategy_tops` (sin cambio) |
| **F-D** | TOP experimento DÍA D | ¿Qué habría elegido el embudo **el día D**? | Cliente `bolsa-dia-d-experiment-top-v1` |
| **V** | Verificar D→hoy | ¿Cómo habría ido **F-D#1 congelada** hasta hoy? | Sesión + Evidence (ya existe) |

### 2.2 Reglas de escritura

1. Play / auto-save Finalistas con **DÍA D en el pasado** → escribe **F-D**, **no** pisa F-hoy.  
2. Play con D = hoy (o sin D) → escribe **F-hoy** como hasta ahora.  
3. Verificar C usa **F-D#1** si hay experimento para ese `(instrumento, TF, D)`; si no, fallback al TOP visible + aviso.  
4. En C: **sin** re-Lab / re-Coach (premisas §2).

### 2.3 Informe de reconciliación (post-V)

Comparar identidad **F-D#1** ↔ **F-hoy#1** + calidad OOS de V (band Evidence):

| Código | Condición (v1) |
|--------|----------------|
| `SAME_CONFIRMED` | Misma estrategia (o misma familia preset) + band favorable |
| `SAME_FAILED` | Misma + band adverse |
| `SAME_MIXED` | Misma + mixed |
| `DRIFT_BETTER` | Distinta + favorable |
| `DRIFT_WORSE` | Distinta + adverse |
| `INCONCLUSIVE` | incomplete / sin F-hoy / sin datos |

- El veredicto es **determinista** (código).  
- La narración IA es **opcional** y no cambia el código.  
- No auto-reescribe F-hoy ni el Mandato; CTAs humanos: «Revisar Finalistas» / «Mantener F-hoy».

### 2.4 Identidad “misma”

Orden de igualdad:

1. Mismo `strategyDefinitionId` → misma.  
2. Si no: mismo `strategyType` / preset de slot → **misma familia** (cuenta como SAME_*).  
3. Si no → DRIFT_*.

### 2.5 Fuera de v1 / diferido

- TOP experimento en BD / multi-dispositivo.  
- ~~Verificar en paralelo F-hoy#1 en el mismo tramo D→hoy (contrafactual).~~ **Hecho v1.1 (cliente).**  
- Walk-forward multi-ventana automático.  
- Auto-obsolescencia del Mandato (ADR-020) sin confirmación.

### 2.6 Contrafactual v1.1

Tras V (F-D#1), si F-hoy#1 existe y es distinta: mismo lookback+ventana D→hoy, métricas OOS en panel (retorno, ops, Δ pp). Si misma #1 → `skipped_same`.

---

## 3. Consecuencias

**Positivas**

- Finalistas operativas protegidas durante experimentos.  
- Pregunta de producto respondible en UI.  
- Base para confianza del Mandato / CORE-R.

**Costes**

- Dos lecturas en Finalistas (operativo vs experimento).  
- Copy Ayuda / CTA Verificar.

---

## 4. Ratificación

- [x] F-hoy ≠ F-D (no pisar)  
- [x] V congela F-D#1  
- [x] Veredictos SAME_* / DRIFT_* / INCONCLUSIVE  
- [x] IA solo narra  
- [ ] BD multi-dispositivo (futuro)

---

## 5. Código

- `apps/web/src/features/backtests/dia-d-experiment-top.ts`  
- `apps/web/src/features/backtests/dia-d-reconciliation.ts`  
- Wire save Explore · panel Verify · Ayuda / HELP
