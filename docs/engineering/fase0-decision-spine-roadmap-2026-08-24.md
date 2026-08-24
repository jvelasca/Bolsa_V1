# Fase 0 — Decision Spine · esquema maestro (roadmap de gestión)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **AsOf:** 2026-08-24. **Fase 0 COMPLETA** (docs F0.1–F0.4 + código F0.5/F0.6 + D1–D3). Prove Spine S0–S3 + H5 en `76679d2`.
> **HEAD/anchas:** `main == origin/main == 76679d2` · verificado `git fetch; git rev-parse origin/main`.
> **Documento de gestión del ORQUESTADOR.** No reabrir F0.5/F0.6. Siguiente = UX mesa (Ayuda/S/R/firma).

---

## 0. Tesis competitiva (ya pactada — texto de paso)

- **Identidad de producto (congelada):** doble cara — **QROS** (Lab) + **Investment OS** (mesa), unidos por el **Decision Spine**. No rebrand que mate ADR-011.
- **No copiar TV/IBKR/QC.** La diferenciación es el **Decision Package** (unificación de evidencias → una decisión auditable) + **tres colas de entrada** + **SEMI paper** como integración humana.
- **Diagnóstico AS-IS (F0.1):** hay **motores reales** pero **no hay una columna ordenada**. Ranking, dictamen, F3 SEMI y Radar/Paper D son **carriles paralelos** que convergen tarde (o nunca) en `ExecuteTrade`.
- **Objetivo TO-BE:** un **spine ordenado** que unifica los carriles **antes** de `ExecuteTrade`, de modo que SEMI y AUTO sean «el mismo motor con otra policy» (no dos cajas).

---

## 1. Rebanadas del esquema (cada una = un artefacto)

| Slice    | Nombre                    | Entregable                                                                                                | Naturaleza                             | Depende de        |
| -------- | ------------------------- | --------------------------------------------------------------------------------------------------------- | -------------------------------------- | ----------------- |
| **F0.1** | AS-IS                     | Inventario file:line, NOT FOUND                                                                           | docs-only                              | —                 |
| **F0.2** | **TO-BE**                 | Arquitectura objetivo del spine (un markdown)                                                             | docs-only                              | F0.1 + RFC-008    |
| **F0.3** | **Mapping**               | Conservar / adaptar / crear por ítem del AS-IS                                                            | docs-only                              | F0.2              |
| **F0.4** | **Descargue de decisión** | Cómo los carriles convergen en un Decision Package; orden de gates; D1 aceptada (risk de cesta SEMI=AUTO) | docs-only                              | F0.3              |
| **F0.5** | **Fit (PortfolioFit)**    | Único _create_ neto a medio plazo; encaje de cartera                                                      | **código (fase pactada + aprobación)** | F0.4 + decisión   |
| **F0.6** | **Daily Decision Board**  | Daily como **vista** (No nuovo orquestador)                                                               | **código (vista)**                     | F0.4 + aprobación |

> **Estado 2026-08-24:** F0.1–F0.4 ✅ docs · **F0.5b CERRADA** (`3670a09`) · **F0.6 COMPLETA** (backend `8df8a65` + UI `672e88f`) · D1/D2/Esc.3/deuda SEMI/D3 ✅. Plan: `fase0-decision-spine-implementacion-plan-2026-08-24.md` (CERRADO).

> **Regla:** Daily es **vista**, no orquestador. **Fit es el único create neto a medio plazo.** El resto del spine es _adaptar/conservar_ módulos existentes.

---

## 2. F0.2 TO-BE — alcance y criterios de parada (heredados del relevo)

- Alimentado por: **F0.1 AS-IS** + **tesis competitiva** (él apartado §0) + **RFC-008** (constitución: Assessment→DecisionRuntime→DecisionPackage→PolicyGate→Execution).
- **No inventa módulos** que F0.1 no marcara como NOT FOUND o stub. Los existentes se _ordenan_, no se crean.
- El spine TO-BE **converge antes de `ExecuteTrade`**: un solo Decision + Fit + Risk de cesta.
- Cita `path:line` del AS-IS en toda afirmación sobre código (no memoria).
- **No tocar:** money/ledger `ExecuteTrade` internals, Belief, gobernanza IA, `contract:gen` salvo fase pactada, purge E8 N.

---

## 3. Protocolo de gestión (anti-saturación / anti-alucinación)

1. **Una rebanada = un artefacto.** Nunca abrir F0.3 en el mismo paso que F0.2 si el contexto se satura.
2. **Máx. ~1 subagente verificador por rebanada docs-only** (alcance disjunto: solo `docs/engineering/`), con brief que inyecte el mapa ya verificado; el orquestador relee y contrasta (premisa E2/E3).
3. **El orquestador no se fía del subagente:** relee cada cita `file:line` contra el código antes de citarla.
4. **Cero commits** salvo petición explícita del propietario (premisa E4). Estos docs quedan para revisión.
5. **Working tree ≠ estado:** el ancla viva es `origin/main` + `PROJECT_STATE.md` + `backlog §0`, no un SHA incrustado.

---

## 4. Estado de la agenda (log del orquestador)

| Slice               | Estado     | Fecha      | Nota                                                                              |
| ------------------- | ---------- | ---------- | --------------------------------------------------------------------------------- |
| F0.1                | ✅ CERRADO | 2026-08-24 | `fase0-decision-spine-asis-2026-08-24.md`                                         |
| F0.2                | ✅ CERRADO | 2026-08-24 | `fase0-decision-spine-tobe-2026-08-24.md`                                         |
| F0.3                | ✅ CERRADO | 2026-08-24 | `fase0-decision-spine-mapping-2026-08-24.md`                                      |
| F0.4                | ✅ CERRADO | 2026-08-24 | `fase0-decision-spine-descarga-2026-08-24.md` · D1/D2/D3                          |
| F0.5                | ✅ CERRADO | 2026-08-24 | PortfolioFit v1 `3670a09`                                                         |
| F0.6                | ✅ CERRADO | 2026-08-24 | Decision Board backend `8df8a65` + UI `672e88f`                                   |
| Audit H1/H2 + Prove | ✅ CERRADO | 2026-08-24 | `5e81350` · `pnpm test:decision-spine`                                            |
| H5                  | ✅ CERRADO | 2026-08-24 | `76679d2` (código `f56af2f`) · SEMI profile → check_opening · siguiente = UX mesa |
