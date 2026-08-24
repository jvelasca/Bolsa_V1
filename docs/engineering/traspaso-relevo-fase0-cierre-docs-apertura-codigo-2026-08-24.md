# RELEVO / TRASPASO — Fase 0 Decision Spine · cierre tramo docs (F0.1–F0.4) → apertura CÓDIGO (F0.5/F0.6)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** de **F0.5 (PortfolioFit)**, fase de código **APROBADA** por el propietario (2026-08-24) para abrir. Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **Tramo docs: COMPLETO.** **F0.5 aprobada para abrir; aún NO ejecutada.** F0.6 (Daily vista) sigue sin aprobar.
> **SHA al cerrar este hilo:** `git fetch; git rev-parse origin/main` = `f69a7b0`. Working tree puede tener **docs Fase 0 sin commit**.

---

## 1. Qué está hecho (no reabrir)

- **Tramo docs Fase 0 COMPLETO**, todos verificado **VERDE** por subagentes read-only + relectura del coordinador:
  - **F0.1 AS-IS** `fase0-decision-spine-asis-2026-08-24.md` — inventario file:line, NOT FOUND.
  - **F0.2 TO-BE** `fase0-decision-spine-tobe-2026-08-24.md` — tres colas → `DecisionPackage` → gate/risk → fill; Daily = vista; Fit = único create.
  - **F0.3 Mapping** `fase0-decision-spine-mapping-2026-08-24.md` — carta conservar/adaptar/crear/no-op por ítem.
  - **F0.4 Descarga** `fase0-decision-spine-descarga-2026-08-24.md` — orden de gates; **D1 ACEPTADA**.
  - **Roadmap** `fase0-decision-spine-roadmap-2026-08-24.md`.
  - **Plan código** `fase0-decision-spine-implementacion-plan-2026-08-24.md` — F0.5/F0.6, PENDIENTE aprobación.

## 2. Decisiones tomadas / pendientes

| Id          | Decisión                                                                                                       | Estado                                              |
| ----------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **D1**      | Risk de cesta (`check_opening`) aplica **igual** en SEMI y AUTO, **sin override humano** en papel.             | ✅ **ACEPTADA** (2026-08-24)                        |
| **D2**      | Autoridad = `DecisionPackage` (contrato) vs `Recommendation` (cara operativa).                                 | ⏳ recomendada (a) — confirmar                      |
| **D3**      | Lab/Radar **fuera** del spine (ADR-019).                                                                       | ⏳ recomendada (a) — confirmar                      |
| **D0-fase** | **F0.5 (Fit código) APROBADA para abrir** · F0.6 (Daily vista) NO.                                             | ✅ F0.5 aprobada · F0.6 ⏳                          |
| **F0.5a**   | **Definir la MÉTRICA de encaje de cartera** — decisión product del propietario; no puede inventarla el código. | **⏳ BLOQUEANTE, es el primer paso del nuevo chat** |

## ⚠️ Instrucción para el nuevo chat (evita repetir el tropiezo)

**F0.5a (métrica de encaje) es una decisión del PROPIETARIO, NO del agente.** El agente NO debe lanzar agentes ni escribir código hasta que el propietario decida la métrica. Opciones ya planteadas (para confirmar en el nuevo chat): concentración (límite peso por activo/sector vs policy `max_*`) · correlación ticker×cartera · gap vs mandato/policy (`MandateTenureRow` `tables.py:1295`) · esbozo del stub sin puntuar.

## 3. Qué NO tocar (freeze)

- Motor money / ledger / `ExecuteTrade` internals.
- Belief / gobernanza IA · `contract:gen` salvo fase pactada · purge E8 N · Track B.
- `pending-delete` · no `regen_full` · no reabrir Track B B1–B12.

## 4. Tarea del siguiente chat (F0.5 — aprobada)

**PASO 0 (obligatorio, sin código):** que el propietario decida **F0.5a — la métrica de encaje**. El agente solo presenta opciones ancladas al código y espera decisión. NO lanzar agentes ni escribir código antes.

**Después (con métrica aprobada): implementar F0.5b (PortfolioFit):**

- Elevar el stub `composite_score.py:325-330` a un encaje de cesta consumido por el Risk de cesta (D1).
- Cada fase: 1 subagente de implementación + 1 verificador read-only, alcance disjunto (E2/E3/E4), batería obligatoria, aprobación del propietario antes de commit.
- Leer primero este relevo + F0.1–F0.4 (docs) + backlog §0 + PROJECT_STATE §2b.

## 5. Texto de arranque (pegar en el chat nuevo de F0.5)

```
CONTEXTO: Fase 0 Decision Spine. Tramo docs CERRADO. F0.5 (PortfolioFit) APROBADA para abrir.
LEE: docs/engineering/backlog §0 + PROJECT_STATE §2b + PROJECT_PREMISES ⭐§0
+ docs/engineering/fase0-decision-spine-implementacion-plan-2026-08-24.md
+ fase0-decision-spine-roadmap-2026-08-24.md + fase0-decision-spine-tobe-2026-08-24.md
+ fase0-decision-spine-mapping-2026-08-24.md + fase0-decision-spine-descarga-2026-08-24.md.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.
D1 aceptada: risk de cesta SEMI=AUTO, sin override. D2/D3 a confirmar si aplican.

TAREA: PRIMERO → decisión del propietario de la MÉTRICA de encaje (F0.5a).
NO lanzo agentes ni código hasta que el propietario decida la métrica.
DESPUÉS → F0.5b implementar Fit (una rebanada, path:line verificado, batería, aprobación antes de commit).
NO TOCAR: money, IA, contract:gen, Track B, pending-delete, ExecuteTrade internals.
Protocolo: subagente acotado + verificador read-only, batería, aprobación propietario antes de commit.
```
