# Triage — Auditoría externa post-tag v1.8.1-beta (2026-08-25)

> **Padre:** [engineering-index](./engineering-index-2026-08-03.md) §5 · pack interno [`audit-pack-estado-global-2026-08-25-v181.md`](./audit-pack-estado-global-2026-08-25-v181.md).
> **Entrada:** informe externo sobre tag **`v1.8.1-beta` → `e78fbb9`** (9 commits por delante de `v1.8.0-beta` → `8c8b789`).
> **AsOf:** 2026-08-25. **Estado:** **RATIFICADO.** Consolidación v1.8.1 **CERRADA**. **No** otra ronda de limpieza. Siguiente = diseño Operational Core v1.9 (ADR-032), no código.
> **Hijos:** [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md) · [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md) · relevo [`traspaso-relevo-audit-ext-v181-cierre-apertura-v19-2026-08-25.md`](./traspaso-relevo-audit-ext-v181-cierre-apertura-v19-2026-08-25.md).

---

## 0. Veredicto producto (ratificado)

La auditoría confirma que v1.8.1 hizo **exactamente** la consolidación pedida en v1.8.0 (C1–C6). No hay un P0 que justifique otra iteración de honesty/cleanup.

| Área                   | Auditor v1.8.0 | Auditor v1.8.1 | Arbitraje Bolsa                                           |
| ---------------------- | -------------- | -------------- | --------------------------------------------------------- |
| Hoy honesty            | 🟠             | 🟢             | **Cerrado** C1                                            |
| BUY sin TradePlan      | 🔴             | 🟢             | **Cerrado** C1                                            |
| ActionQueue            | 🟡             | 🟢             | **Cerrado** C3                                            |
| Top-N vs cola completa | 🟠             | 🟢             | **Cerrado** C3                                            |
| Shape drift            | 🟠             | 🟢/🟡          | **C4 cerrado** como consolidación; contrato formal = v1.9 |
| MFE/MAE honesty        | 🟡             | 🟢             | **Cerrado** C5                                            |
| Expectancy sample      | 🟠             | 🟢             | **Cerrado** C5                                            |
| Alembic authority      | 🟠             | 🟢             | **Cerrado** C2                                            |
| HELP                   | 🟡             | 🟢             | **Cerrado** C1                                            |
| Arquitectura futura    | 🟢             | 🟢             | ADR-032 docs-only **correcto**                            |
| PositionState          | —              | 🟡             | **Correctamente no implementado**                         |
| ExecutionPlan          | —              | 🟡             | **Correctamente no implementado**                         |
| AUTO                   | 🟠             | 🟠             | Sigue BETA-D                                              |
| Broker real            | 🔴             | 🔴             | **Correctamente NO**                                      |
| Thaw estricto          | 🔴             | 🔴             | **Correctamente pendiente**                               |
| Tests (conteo)         | 🟢             | 🟢             | 161 spine + 84 shared **locales**; ver §4 CI              |
| Producción             | 🔴             | 🔴             | **Correctamente NO**                                      |

**Fase:** `v1.7` Decision Spine → `v1.8` operativa advisory → `v1.8.1` **CONSOLIDACIÓN** → `v1.9` **operación modelada**.

---

## 1. Cerrado de verdad (C1–C6)

Aceptado. El auditor contrastó commits, no solo el pack.

| Slice  | Qué deja de mentir                                                                       | SHA               |
| ------ | ---------------------------------------------------------------------------------------- | ----------------- |
| **C1** | Sin TradePlan → WATCH · `planSource=projection` · `whyNot=legacy_projection` · nunca BUY | `659e6c4`         |
| **C2** | Prisma público fail-closed · bootstrap `ensure_migrated`                                 | `952b115`         |
| **C3** | Cola completa ordenada **antes** del slice · Hoy = top-8                                 | `420ad37`         |
| **C4** | `readCanonicalTradePlan` · legacy identificado, no borrado                               | `96d1148`         |
| **C5** | MFE `source` bars\|close_proxy\|none · expectancy `sampleQuality` · `ready` ≠ útil       | `4e245f7`         |
| **C6** | Stamp / tag / pack                                                                       | tag `v1.8.1-beta` |

Legacy **marcado**, no `DELETE EVERYTHING`: estrategia de migración **aceptada**. Thin 5.x/8.x **congelados**. No PositionState / ExecutionPlan en código: **aceptado**.

---

## 2. No cerrado (correcto; no es bug)

1. Position lifecycle (`TradePlan` → `PositionState` → `ExitPlan`)
2. Ejecución real (`ExecutionPlan` → broker)
3. Exit engine real (Exit Radar sigue advisory)
4. Trail real (no muta stops)
5. Bracket real (no OCO)
6. Expectancy histórica (no motor estadístico completo)
7. Thaw estricto
8. Broker live

Nada de esto se «arregla» con un mapper thin más.

---

## 3. Decisiones adoptadas (no código en este triage)

| #   | Decisión                                                                                                   | Cuándo                      |
| --- | ---------------------------------------------------------------------------------------------------------- | --------------------------- |
| 1   | **No** otra ronda de refactor menor / honesty.                                                             | Ya                          |
| 2   | **No** programar v1.9 hasta congelar diseño (auditoría de ADR-032).                                        | Este relevo                 |
| 3   | Prioridad arquitectónica v1.9 = **PositionState** (describir «qué ocurre ya abierta»).                     | Tras TradePlan v1 identidad |
| 4   | Secuencia: TradePlan v1 → PositionState → ExitPlan → ExecutionPlan **PAPER** → Journal/Replay → broker     | Roadmap v1.9                |
| 5   | **No** ActionabilityScore predictivo. Sigue ordinal de preparación.                                        | Hasta Operational Core viva |
| 6   | Dedup Hoy por `symbol` **no se toca ahora**. v1.9: `ActionIdentity` = instrument + positionId + actionType | Parked                      |
| 7   | Prioridad futura: riesgo de posición abierta **antes** de nueva entrada (Portfolio Operating Layer)        | Parked, no Hoy v1.8.1       |
| 8   | UX destino = Daily Operating Console (claridad 10s). **No** más dashboards ahora.                          | Parked                      |
| 9   | Consistencia de 4 puntos en conceptos críticos: **CODE + TEST + HELP + ADR**.                              | Disciplina vigente          |
| 10  | Tests = cobertura de **invariantes**, no el número 161→200.                                                | Disciplina vigente          |
| 11  | **Una** mejora de infra en backlog **antes de v1.9-beta**: CI reproducible por tag/release.                | Infra; no bloquea diseño    |

---

## 4. Hallazgo CI (única deuda de infra a anotar ya)

El auditor no pudo certificar desde GitHub que 161+84 corrieran **sobre** `e78fbb9`: `statuses: []`, sin workflow runs en ese commit.

**Causa raíz en repo (no ausencia de CI):** C6 es stamp documental. `python-ci.yml` y `frontend-ci.yml` filtran por paths de código (`apps/`, `packages/`, …) y **no** incluyen `docs/**`. Un tag sobre commit docs-only no dispara Actions. El pack documenta batería **local**.

Backlog (antes de un futuro `v1.9-beta`): tag `v*` → gates sin path-filter (lint, typecheck, pytest, vitest, `test:decision-spine`, shared, contract, security) → GREEN → artefacto. **CERRADO 2026-08-25:** [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) · plan [`plan-infra-ci-by-tag-2026-08-25.md`](./plan-infra-ci-by-tag-2026-08-25.md).

---

## 5. Puntuación externa (contexto; no KPI interno)

Arquitectura 9 · Decision Spine 9 · SEMI/AUTO 8.5 · Operativa diaria 7.5 · **Gestión de posiciones 5.5** (esperado: aún no hay PositionState) · Lab 8.5 · Observabilidad 7.5 · Contratos 7 · UX operativa 8 (techo 9.5 con Operational Core).

No convertir estas notas en objetivos de sprint.

---

## 6. Qué no hacer

- No Ciclo 8.3 / TargetPlan / PositionPlan / LiquidityPlan / ExitHint2.
- No Actionability = 93.
- No ExecutionPlan directo a broker.
- No thaw estricto / broker live / producción.
- No optimizar el modelo con DEMO.
- No inflar la batería por conteo.
