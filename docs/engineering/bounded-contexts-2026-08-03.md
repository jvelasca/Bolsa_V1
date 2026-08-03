# Bounded contexts — quién depende de quién (2026-08-03)

> **AsOf:** 2026-08-03 · Respuesta a auditoría externa A0 H2.  
> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md).  
> **Stack real:** `apps/web` · `apps/api-python` · `packages/py/*` · `@bolsa/shared`.  
> No sustituye ADRs; fija **flechas permitidas** entre contextos de producto.

---

## 1. Contextos

| ID | Nombre | Pregunta | Código típico |
|----|--------|----------|---------------|
| **MKT** | Market data | ¿Datos íntegros / frescos? | `bolsa_market`, sync, quarantine, CB Yahoo |
| **RES** | Research Lab | ¿Qué hipótesis / TOP / campaña? | backtests, Lab, Coach, manifests, Observatory |
| **SCI** | Scientific store | ¿Evidence / Belief / Knowledge? | `research_evidence`, belief_engine (Belief→Coach freeze) |
| **DEC** | Decision / AI propose | ¿Recommendation / Session / Gate? | `/api/ai/*`, DecisionSession, WeightRules |
| **TRD** | Trading / ledgers | ¿Paper/DEMO / órdenes / Mandato? | accounts, ledger, Mandato ADR-020, CORE-R |
| **PLAT** | Platform shell | ¿Espacios, prefs, Ayuda? | workspace, localStorage prefs, HELP |

---

## 2. Flechas permitidas

```text
MKT ──► RES ──► SCI (Evidence append; Belief update solo con hypothesis_id)
         │
         ├──► TRD   (Finalistas / Mandato / CORE-R; Verify DÍA D = sandbox LAB ≠ DEMO)
         └──► DEC   (propose usa Assessments; no escribe research_trials)

DEC ──► TRD   (Intent / paper_auto vía Policy Gate)
TRD ─X─► RES  (prohibido: operativa no re-Lab ni reescribe K científico)
SCI ─X─► TRD  (prohibido: Belief no es fill; no auto-paper)
PLAT ──► *    (shell; sin lógica de edge)
```

`─X─►` = **nunca** (rompe diseño A0 H2).

---

## 3. Anti-ciclos explícitos

| Ciclo prohibido | Por qué |
|-----------------|---------|
| Coach → Research ranking → Coach score | CORE-A no corona TOP (invariante) |
| CORE-R → Lab re-opt → CORE-R | Monitor observa; no investiga |
| DÍA D Evidence → Belief automático → Coach → TOP | Freeze + brief B1–B8 |
| Trading DEMO ← sandbox Verify | ADR-019 |

---

## 4. Justificar dependencia nueva

En el PR, una línea:

`Dep: RES→SCI porque emit_evidence_for_trial al cerrar grid (append-only).`

Si no cabe en una línea, probablemente es acoplamiento indebido.
