# Brief de producto — Belief → Coach (borrador)

> **AsOf:** 2026-08-03  
> **Estado:** borrador de diseño · **NO implementa** · freeze vigente ([post-audit-decision-freeze](./post-audit-decision-freeze-2026-08-03.md))  
> **Propósito:** cuando se reabra Belief Fase 2 hacia Coach, este brief es el contrato anti-soberbia.  
> **Depende de:** ADR-011 · ADR-012 · ADR-018 · RFC-008 · [AI learning theory canvas](../../.cursor — ver chat) · Coach v0 actual.

---

## 1. Problema que resuelve

Hoy el Lab **elige** Finalistas con ranking determinista + Coach narrativo honesto (no corona TOP).  
Fase 2 ya puede persistir Evidence/Belief en BD, pero **Belief no entra en Coach** (congelado a propósito).

Sin brief, “conectar Belief” suele degenerar en:

- el LLM lee un número 0.72 y suena a veredicto de inversión;
- Belief de trials IS (nivel C) contamina la #1;
- DÍA D Evidence sin `hypothesis_id` se interpreta como aprendizaje del modelo.

---

## 2. Pregunta única del feature

> **¿Cuánto cree hoy el laboratorio esta hipótesis (familia/preset), con qué muestra y en qué contextos — sin decidir la #1?**

Coach **muestra** Belief; **no** reordena TOP ni emite BUY.

---

## 3. Contrato anti-soberbia (normativo)

| # | Regla | Razón |
|---|-------|-------|
| B1 | Belief **nunca** cambia el orden de Finalistas / semifinal | Ranking = motor determinista |
| B2 | Coach puede citar Belief solo como **contexto** (“n=…, CI=…, nivel Evidence≤…”) | Evita corona narrativa |
| B3 | Sin `hypothesis_id` → **no** update Belief (DÍA D session sigue así) | Evidence huérfana ≠ aprendizaje |
| B4 | Evidence nivel **C** mueve Belief con peso bajo; **no** Consolidation a Knowledge | ADR-012 §3.2 |
| B5 | Evidence **D** / incomplete → no move | Basura fuera |
| B6 | UI: Belief con **n** y CI visibles; 0.72 sin n = anti-patrón | ADR-011 P4 |
| B7 | Copy fija: «Credencia de investigación · no es consejo ni gate de trading» | Separación Scientific ≠ Trading |
| B8 | Reject inference: si conflicto Belief alto vs ranking, Coach **dice el conflicto**, no elige | RFC-008 / ADR-012 |

---

## 4. Unidad canónica

| Concepto | En Coach v1 Belief |
|----------|--------------------|
| Hipótesis | Familia o preset versionado (`strategyType` / `presetKey` + `math_version`) |
| Evidence que alimenta | Trials Lab (WFO/hold-out), EdgeReports, paper outcomes con `hypothesis_id` |
| **No** alimenta (v1) | Evidence DÍA D `source=dia_d_session` sin hipótesis; narraciones LLM; JSON localStorage |

Opcional v1.1: al Guardar Evidence DÍA D, **CTA** «Vincular a hipótesis de la #1» (explícito humano) → entonces sí update.

---

## 5. Superficie UI (mínima)

1. Panel Coach / Finalistas: chip `Belief 0.xx · n=N · CI` por candidata **si** hay hypothesis link.  
2. Tooltip: últimos 3 evidence ids + levels.  
3. Sin chip si n=0.  
4. Ningún botón «aplicar Belief al TOP».

---

## 6. Criterios para **reabrir** el freeze

Todos deben cumplirse:

1. Uso real del embudo Lab (Play / Finalistas / CORE-R) documentado en operativa.  
2. `sessionLearning` / effectiveness revisados al menos una vez (Learning B).  
3. Este brief **ratificado** (casillas §3).  
4. Test: Coach con Belief alto **no** cambia estrellas ni orden vs baseline sin Belief.  
5. Test: Evidence C sola no dispara Consolidation.

---

## 7. Fuera de alcance de este brief

- Fine-tune LLM · RL · Learning v2 auto-pesos.  
- Auto-guardar Evidence DÍA D.  
- Belief → Policy Gate / paper_auto.  
- Knowledge Nodes UI / Discovery Score.

---

## 8. Ratificación

- [ ] B1–B8 aceptados  
- [ ] Unidad hipótesis acordada (familia vs preset)  
- [ ] Freeze Belief→Coach se reabre con fecha  
- [ ] Owner de implementación asignado  

*Hasta ratificar: Belief permanece congelado; Coach v0 sin Belief.*
