# RELEVO / TRASPASO — Escalón 3/D1 CERRADO (VETO cesta en confirm SEMI) → apertura fase siguiente

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** de la **siguiente fase**. La Fase 0 Decision Spine queda **COMPLETA** y tanto **D2** (DecisionPackage = contrato en confirm SEMI, `f7b1f6c`) como **Escalón 3/D1** (VETO de cesta+kill-switch en confirm SEMI, `7530556`) quedan **CERRADOS y pusheados a `main`**. La fase siguiente **la decide el propietario** a partir del backlog (deuda diferida del confirm). Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **F0.1–F0.4 docs COMPLETOS** · **F0.5b PortfolioFit CERRADA** (`3670a09`) · **F0.6 Decision Board COMPLETA** (backend `8df8a65` + UI `672e88f`) · **D1 aceptada** · **D2 CERRADA con código** (`f7b1f6c`) · **Escalón 3/D1 CERRADA con código** (`7530556`)
> **SHA al cerrar este hilo:** `git log -1 --format=%H` = `0768a70` (docs cierre Escalón 3/D1 `docs(d1)` sobre `7530556`). Working tree limpio, sincronizado con `origin/main`.

---

## 1. Qué está hecho (no reabrir)

- **F0.1 AS-IS · F0.2 TO-BE · F0.3 Mapping · F0.4 Descarga** — docs COMPLETOS (verificado VERDE). **D1** aceptada: risk de cesta SEMI=AUTO sin override.
- **F0.5a** — métrica de encaje **decidida** = concentración de cesta por activo y por sector, VETO (fail-closed), sector desde DB.
- **F0.5b — PortfolioFit v1 CERRADO (`3670a09`):** `compute_portfolio_fit` (as-if fill) · `Position.sector` · regla `MaxSectorExposure` + `MaxConcentration` a nivel cesta · cableado `execution_router`→`check_opening`.
- **F0.6b — Decision Board v1 (backend) CERRADO (`8df8a65`):** use-case `GetDecisionBoard` (solo lectura) + endpoint `GET /accounts/{id}/decision-board`.
- **F0.6-UI — Decision Board web CERRADA (`672e88f`):** página `/decision-board` solo lectura.
- **D2 — DecisionPackage = contrato CERRADA (`f7b1f6c`):** en el confirm SEMI con `execute=True`, el package de la sesión `propose` es la fuente de verdad → fail-closed si la identidad (acción+instrumento) diverge; `contract` (present_verified/absent) si no hay sesión. No exige `session_id`, no toca sizing humano.
- **Escalón 3/D1 — VETO cesta en confirm SEMI CERRADA (`7530556`):** en `ConfirmRecommendationIntent` (`confirm_recommendation.py`), con `execute=True` y acción de **apertura** (`recommend_long`/`recommend_short`), se re-ejecuta `check_opening` con `portfolio_summary` (read-only, `profile=None`) **antes del fill**; si la cesta (`MaxSectorExposure`/`MaxConcentration`) o el kill-switch vetan → `rejected_by_gate`/`risk_veto` + `intent.status=rejected_by_gate` (mismo patrón D2, la UI retira el ítem). `exit_hint`/`reduce` quedan fuera (no abren cesta). `portfolio_summary=None` conserva el comportamiento previo. Inyección: `dependencies.py:get_confirm_intent_use_case`. **Sin cambio de contrato HTTP** (no toca `contract:gen`). Batería: ruff 0 · mypy 0 · confirm 16/16 (4 nuevos) · risk/fit/router 8 · application 323/325 (**1 fail pre-existente ajeno `test_list_account_summaries_one_summary_per_account`**, fake repo sin `owner_user_id`) · verificador read-only APROBADO.
- **Fase 0 Decision Spine COMPLETA + D2 + Escalón 3/D1** — todo pusheado a `main`.

## 2. Decisiones tomadas / pendientes

| Id           | Decisión                                                                                                                                                                                                                                                                                                             | Estado                                  |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| **D1**       | Risk de cesta (`check_opening`) aplica **igual** en SEMI y AUTO, **sin override** humano.                                                                                                                                                                                                                            | ✅ **ACEPTADA** (2026-08-24)            |
| **D2**       | Autoridad = **`DecisionPackage`** (contrato) vs `Recommendation` (cara operativa). **CERRADA con código**: en el confirm SEMI con `execute=True`, el package de la sesión `propose` es la fuente de verdad → fail-closed si la identidad diverge; `contract` (present_verified/absent) sin sesión. Commit `f7b1f6c`. | ✅ **CERRADA** (2026-08-24) **f7b1f6c** |
| **Esc.3/D1** | Re-evaluar gate & risk de cesta en confirm SEMI (**VETO fail-closed**). **CERRADA con código** (`7530556`): aperturas re-ejecutan `check_opening` (cesta+kill-switch, `profile=None`) antes del fill; veta → `rejected_by_gate`/`risk_veto`. `exit_hint`/`reduce` fuera. Sin re-sizing.                              | ✅ **CERRADA** (2026-08-24) **7530556** |
| **D3**       | Lab/Radar **fuera** del spine (ADR-019). **CONFIRMADA (a) por el propietario (2026-08-24)**: el Lab/Radar quedan FUERA del spine (universo laboratorio); el spine gobierna solo el universo TRADING. Registrada en [F0.4 §3](../fase0-decision-spine-descarga-2026-08-24.md).                                        | ✅ **CONFIRMADA** (2026-08-24)          |

> **Queda (deuda diferida del confirm SEMI, candidata a la siguiente fase):**
>
> 1. `wait` confirmado **sin sesión** → hoy ejecutaría un **sell default** (la tesis `wait` no debería abrir/cerrar nada).
> 2. `reduce`/`exit_hint` **no distinguen cerrar de abrir short** → un `reduce`/`exit_hint` de un short podría tratarse como sell de apertura.
>    La **siguiente fase** del proyecto la decide el propietario (ver §4).

## ⚠️ Instrucción para el nuevo chat (no repetir el tropiezo)

**La siguiente fase está SIN aprobar.** El agente NO debe abrir código ni lanzar subagentes de implementación hasta que el propietario **apruebe la fase** (premisa E1) y **defina el alcance/decisiones bloqueantes**. Nota 2026-08-24: **D3 ya CONFIRMADA** (Lab/Radar fuera del spine, ver tabla); la deuda diferida del confirm SEMI (`wait`-sin-sesión · `reduce`/`exit_hint`) quedó CERRADA en la fase posterior (`traspaso-relevo-cierre-deuda-confirm-semi-siguiente-2026-08-24.md`). PASO 0 siempre: **read-first** del `backlog §0` + `PROJECT_STATE §3` + `PROJECT_PREMISES ⭐§0`, presentar opciones ancladas al código, esperar decisión. NO reabrir F0.5/F0.6/D2/Escalón 3/D1/Cierre deuda confirm SEMI (cerradas y pusheadas).

## 3. Qué NO tocar (freeze)

- Motor money / ledger / `ExecuteTrade` internals.
- Belief / gobernanza IA · `contract:gen` salvo fase pactada · Track B B1–B12.
- `pending-delete` · no `regen_full`. Purge storage E8 N.
- F0.5b · F0.6 (backend+UI) · D2 · Escalón 3/D1 ya cerrados y pusheados: NO reescribir salvo fase pactada que exponga un hueco real.

## 4. Tarea del siguiente chat (fase nueva — SIN aprobar)

**PASO 0 (obligatorio, sin código):** que el propietario decida **qué fase sigue** y apruebe (con decisiones bloqueantes D3 / prioridad `wait`-vs-`reduce` resueltas). El agente solo presenta opciones ancladas al backlog y espera decisión. NO abrir código antes.

Candidatos registrados (deuda diferida del confirm SEMI):

1. **`wait` sin sesión → sell default** — corregir para que una tesis `wait` sin sesión NO ejecute una venta default.
2. **`reduce`/`exit_hint` vs abrir short** — semántica: distinguir cerrar una posición (short) de abrir una nueva.

**Después (con fase aprobada):** implementar la rebanada acordada, una a la vez, path:line verificado, batería, aprobación antes de commit.

## 5. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO: Fase 0 Decision Spine COMPLETA + D2 CERRADA (f7b1f6c, DecisionPackage=contrato
en confirm SEMI) + Escalón 3/D1 CERRADA y PUSHEADO a main:
  · 7530556 feat(confirm): veto fail-closed de cesta+kill-switch en confirm SEMI
  · 0768a70 docs(d1): cierre documental Escalón 3/D1 (backlog §0 + PROJECT_STATE §3)
HEAD = 0768a70 (sincronizado origin/main, working tree limpio).
Escalón 3/D1: en confirm SEMI, aperturas (recommend_long/recommend_short) re-ejecutan
check_opening (cesta MaxSectorExposure/MaxConcentration + kill-switch, profile=None)
antes del fill; si veta → rejected_by_gate/risk_veto + intent.status=rejected_by_gate.
exit_hint/reduce fuera. portfolio_summary=None conserva comportamiento previo.
Sin cambio de contrato HTTP. Batería: ruff 0, mypy 0, 16/16 confirm, risk/fit/router 8,
application 323/325 (1 fail pre-existente ajeno test_list_account_summaries).
LEE (read-first, obligatorio): backlog §0 + PROJECT_STATE §3 + PROJECT_PREMISES ⭐§0.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.

TAREA: PRIMERO → el propietario decide QUÉ FASE SIGUE y la aprueba (E1). Candidatas
registradas (deuda diferida del confirm SEMI): (1) corregir `wait` sin sesión → hoy
ejecutaría un sell default; (2) `reduce`/`exit_hint` no distinguen cerrar de abrir short.
Además D3 (Lab/Radar fuera del spine, ADR-019) pendiente de confirmar. NO lanzo agentes
ni código hasta aprobar la fase y su alcance.
DESPUÉS → rebanada acotada, path:line verificado, batería, verificador read-only
(alcance disjunto), aprobación del propietario antes de commit.

NO TOCAR: money/ledger/ExecuteTrade internals, gobernanza IA, contract:gen salvo fase
pactada, Track B B1–B12 (cerrado), pending-delete (E8 N), regen_full sin decisión.
NO REABRIR: F0.5/F0.6/F0.6-UI/D2/Escalón 3/D1 (cerradas y pusheadas a main).
Backlog §4 activo (fuera de repo, no bloquea código): secret scanning UI, TRUSTED_PROXIES
prod, corregir BP/.L→BP.L en BD, limpiar logs/dev.

Protocolo: subagente acotado + verificador read-only, alcance disjunto, batería,
aprobación del propietario antes de commit.
```
