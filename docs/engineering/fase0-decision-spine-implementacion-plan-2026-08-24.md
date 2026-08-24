# F0.5/F0.6 — Plan de implementación (código) — PENDIENTE DE APROBACIÓN DE FASE

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **AsOf:** 2026-08-24 · HEAD `f69a7b0` == `origin/main`.
> **Estado:** **PLAN — NO EJECUTADO.** El propietario decidió (`docs_all`, premisa E1) no abrir código de spine aún. Este documento define alcance, archivos, batería y riesgo para que cada fase se apruebe por separado.
> **Base:** [AS-IS F0.1](./fase0-decision-spine-asis-2026-08-24.md) · [TO-BE F0.2](./fase0-decision-spine-tobe-2026-08-24.md) · [Mapping F0.3](./fase0-decision-spine-mapping-2026-08-24.md) · [Descargue F0.4](./fase0-decision-spine-descarga-2026-08-24.md).

---

## 1. ¿Qué se va a implementar (dos fases de código)?

### F0.5 — PortfolioFit (único **create**)

- **Origen:** hoy es **stub** en `composite_score.py:325-330` (`portfolioConstraints` · `status="not_evaluated"` · `note="Stub F3: políticas de cartera no puntúan aún"`).
- **Objetivo:** elevar ese stub a un **encaje de cesta** que el gate/risk de cesta consulte antes del fill.
- **Frontera:** NO toca `ExecuteTrade` internals ni motor money. Es un **nuevo componente de evaluación de cartera** que produce una señal/métrica de encaje, consumida por el Risk de cesta (F0.4 D1).
- **Decisión pendiente que F0.5 necesita:** métrica de "encaje" (concentración, correlación ticker×cartera, gap sobre `max_*` de policy) — requiere definición product.
- **Batería mínima esperada:** tests del nuevo componente (aislado), gate sobre `not_evaluated`→métrica, y una prueba de integración en cesta. Sin `contract:gen` salvo fase que lo declare.

### F0.6 — Daily Decision Board (vista, no orquestador)

- **Origen:** `GetDailyOpsReport` (`daily_ops_report.py:51`) es un **agregador que no decide** (AS-IS §6).
- **Objetivo:** **vista de solo lectura** sobre el spine (estado de colas, paquetes pendientes, gates). **No** introduce orquestador.
- **Frontera:** UI + endpoint de lectura; **no** decide ni muta estado.
- **Decisión pendiente F0.6:** fuentes de la vista (¿qué expone el spine a la UI del diario?).

---

## 2. Orden de implementación (una fase = un subagente, al aprobarse)

| Orden | Fase      | Alcance                                                                | Precondición       |
| ----- | --------- | ---------------------------------------------------------------------- | ------------------ |
| 1     | **F0.5a** | Fit: definir métrica de encaje (requiere definición product)           | decisión métrica   |
| 2     | **F0.5b** | Fit: implementar componente + test aislado + integrar en risk de cesta | F0.5a              |
| 3     | **F0.6a** | Daily: endpoint lectura del spine                                      | base spine estable |
| 4     | **F0.6b** | Daily: UI vista                                                        | F0.6a              |

> **Regla:** cada fase se aprueba por separado (premisa E4). Máx. ~1 subagente de implementación + 1 verificador por fase, alcance disjunto.

---

## 3. Riesgo y anti-objetivos

- **NO** reabrir `ExecuteTrade` internals ni motor money (congelado).
- **NO** `contract:gen` salvo fase pactada explícita.
- **NO** tocar Belief, gobernanza IA, Track B, `pending-delete` E8.
- Fit es el **único create**; el resto del spine es **adaptar** módulos EXISTS (F0.3).
- Todo afirmación de código en la implementación llevará `path:line` verificado (no memoria).

---

## 4. Criterio de parada para abrir F0.5/F0.6

1. Propietario **aprueba la fase** (D1 ya aceptada; D2/D3 aún pendientes — se cierran antes de abrir F0.5).
2. Definición product de la métrica de encaje (F0.5) y de la vista (F0.6) acordada.
3. Se escribe este plan en su correspondiente `plan-f0x-*.md` de fase antes de tocar código.
