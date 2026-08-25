# Plan — Ciclo 6 Attribution Journal thin (setup snapshot + trail)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §6 (MFE/MAE, attribution, expectancy — parked juntos; **esta** rebanada abre solo Attribution **thin**, no MFE) · [ADR-029](../adr/029-order-proposal-decision-journal.md) · relevo [`traspaso-relevo-ciclo-49-board-session-tradeplan-echo-2026-08-25.md`](./traspaso-relevo-ciclo-49-board-session-tradeplan-echo-2026-08-25.md) §4 · síntesis subagente Attribution 2026-08-25.
> **AsOf:** 2026-08-25 · HEAD **`4a66945`** = `origin/main`; feat **`7de91e5`**.
> **Estado:** **CERRADO en origin** (`7de91e5` vía `4a66945`). D1–D8 OK · batería **117**.
> **Método:** rebanada fina journal; Ranking ≠ BUY; sin Alembic si solo JSONB payload; sin `contract:gen`; sin LLM; **sin** Ciclo 5 PM / MFE-MAE / expectancy.
> **Secuencia:** (1) snapshot setup en payloads journal · (2) higiene trail `human_*` · (3 opcional) puente read-only SessionOutcome en UI.

---

## 0. Objetivo

Journal F1–F3 ya es timeline read-only (`decision_journal_entries`, Alembic `010`). Los writers emiten eventos mínimos **sin** `entrySetup` / TradePlan status → no se puede atribuir por setup desde el journal.

**Attribution thin ≠ motor expectancy.** Cerrar el gap semántico: copiar al `payload` JSONB campos ya vivos en propose/confirm, completar trail humano ADR-029, y (opcional) mostrar outcome de sesión existente sin abrir Position Manager.

### Qué entra vs qué queda fuera

| Incluye (thin Ciclo 6)                                                                                                                       | Excluye (parked)                                                |
| -------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Enriquecer `proposal_recorded` / `executed` (y opcional `gate_evaluated`) con `entrySetup`, `tradePlan.status`, phase/effort etiqueta si hay | MFE/MAE path · expectancy agregada · thesis health · trailing   |
| Cablear `human_confirm` / `human_reject` en confirm (tipos ya en shared/UI)                                                                  | Tabla `order_proposals` · OrderProposal endpoint                |
| SEMI: opcional `gate_evaluated` al pasar `check_opening` (simetría AUTO)                                                                     | Ampliar `mandate_trade_links` a P&L · motor Attribution nuevo   |
| (Opcional UI) por `sessionId`, chip/link a `SessionOutcome` / hit-miss ya existente                                                          | Ciclo 5 PM · Shadow AUTO · dual ExecuteTrade · Wyckoff classify |
| Tests journal writers + UI journal si toca surface                                                                                           | Alembic nueva · `contract:gen` (payload libre)                  |

**Frontera:** Session = foto · Journal = transiciones · Attribution thin = **qué setup/plan** iba en la transición · Learning outcome = **¿acertó la tesis?** (ya existe; no reinventar).

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                 | Propuesta por defecto                                                                                                                                                                                                                    |
| --- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | ¿Alcance de **esta** rebanada?           | **(1)+(2):** snapshot setup en payloads + `human_confirm`/`human_reject`. **(3)** SessionOutcome en UI = **sí thin** (solo lectura si hay outcome; sin fetch pesado). Si solo docs sin código → este plan no aplica (cerrar como brief). |
| D2  | ¿Qué campos en payload?                  | Mínimo: `entrySetup`, `tradePlanStatus` (o `status`). Opcional: `phase`/`effort` del anchor (etiqueta). **Sin** stop/qty/size (evitar PII operativa densa; ya está en sesión).                                                           |
| D3  | ¿Alembic / columnas tipadas?             | **No.** Solo JSONB `payload`. Pedir columnas tipadas o tabla attribution → **parar**.                                                                                                                                                    |
| D4  | ¿`contract:gen` / DTO tipado?            | **No.** Payload sigue `dict` / `Record<string, unknown>`. UI lee campos conocidos con tolerancia.                                                                                                                                        |
| D5  | ¿SEMI `gate_evaluated`?                  | **Sí thin:** un evento al veto/allow de `check_opening` en confirm execute (simetría router), payload `{ allowed, reasons? }` + setup si hay. Sin duplicar risk engine.                                                                  |
| D6  | ¿Interacción con `check_opening` / fill? | **Solo lectura lateral** (journal best-effort). Writers **no** tumban propose/confirm (igual F1).                                                                                                                                        |
| D7  | ¿SessionOutcome bridge?                  | **Sí thin UI:** si entry tiene `sessionId` y el cliente ya puede resolver outcome (o GET existente), mostrar hit/miss compacto. **Sin** nuevo endpoint obligatorio; sin MFE. Si no hay API lista → solo (1)+(2) y aparcar (3).           |
| D8  | ¿Cierre / siguiente?                     | Stamp CURRENT_SYSTEM + ADR-031 nota «Attribution thin Cerrada; MFE/expectancy sigue parked». E1 ≠ Ciclo 5 PM · ≠ Shadow AUTO.                                                                                                            |

Si D1 incluye MFE/expectancy, D3 = Alembic, D4 = `contract:gen`, o «attribution = P&L por setup»: **parar y replanificar**.

---

## 2. Alcance (sí / no)

### Sí

| Pieza      | Regla                                                                                                                                                        |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Propose    | `proposal_recorded` payload: `{ status, entrySetup?, tradePlanStatus?, phase?, effort? }` desde TradePlan/anchor ya calculados                               |
| Confirm    | `human_confirm` cuando execute autorizado; `human_reject` / no-execute path según flujo actual; `executed` payload con mismos campos setup + `transactionId` |
| AUTO       | `gate_evaluated` / `executed` pueden añadir setup si el router tiene plan a mano (sin forzar rebuild)                                                        |
| UI Journal | Renderizar setup en payload expandido (copy mínima); labels human\_\* ya tipados                                                                             |
| Tests      | Writers unit/integration; journal page vitest si surface                                                                                                     |

### No

- MFE/MAE · expectancy · Position Manager · thesis health
- Alembic · Prisma · `contract:gen` · OrderProposal tabla
- Cambiar `check_opening` semántica · broker · `PAPER_D_EXECUTE`
- Wyckoff classify / Board echo (4.9 cerrado)

---

## 3. Diseño (borrador)

```text
# propose (ya tiene trade_plan_dict + wyckoff_anchor)
append_journal_event(..., payload={
  "status": "open",
  "entrySetup": trade_plan.get("entrySetup"),
  "tradePlanStatus": trade_plan.get("status"),
  "phase": anchor.get("phase") if anchor else None,
  "effort": anchor.get("effort") if anchor else None,
})

# confirm
# - human_confirm / human_reject en puntos de firma / rechazo
# - executed: + setup snapshot + transactionId
# - opcional gate_evaluated SEMI tras check_opening

# UI
payload.entrySetup · tradePlanStatus · phase · effort  (si presentes)
```

**Ancla código:**

- `propose_recommendation.py` · `confirm_recommendation.py` · `execution_router.py` (thin)
- `journal_writer.py` (sin cambio contrato si firma ya acepta payload)
- `apps/web/.../decision-journal-*` (+ helpers/test)
- Docs: CURRENT_SYSTEM · ADR-031 §6 · ADR-029 nota thin · relevo Ciclo 6 · index

**Invariant:** Journal ≠ Session. Attribution thin ≠ expectancy. Best-effort ≠ fail fill. Setup etiqueta ≠ gate.

---

## 4. Batería pactada

- ruff touched Python
- tests journal / propose / confirm tocados (+ spine si se añaden al battery)
- vitest decision-journal si UI
- Diff `check_opening` vacío

---

## 5. Criterio de cierre

1. Nuevos `proposal_recorded` / `executed` traen setup cuando el plan existe.
2. `human_confirm` / `human_reject` aparecen en trail SEMI.
3. Sin Alembic · sin `contract:gen` · sin MFE.
4. Docs: Attribution thin cerrada; MFE/expectancy parked.
5. Commit/push solo con OK propietario.

---

## 6. Texto de arranque (tras OK D1–D8)

```text
Implementar Ciclo 6 Attribution Journal thin según plan-ciclo-6-attribution-journal-thin-2026-08-25.md.
D1=(1)+(2)+Outcome UI thin · D2=entrySetup+tradePlanStatus(+phase/effort) · D3=sin Alembic · D4=sin contract:gen · D5=SEMI gate_evaluated thin · D6=journal best-effort · D7=SessionOutcome read-only si hay · D8=stamp; E1≠PM/MFE.
No check_opening change · no MFE · no expectancy · no Shadow AUTO · no Ciclo 5 · no Wyckoff.
```

---

## 7. Fuera (no aquí)

- Expectancy por setup · MFE/MAE series
- Ciclo 5 PM · dual ExecuteTrade · Actionability/IO server
- Shadow AUTO / broker / F9-B / purge
