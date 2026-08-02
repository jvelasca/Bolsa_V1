# Auditoría de etapa — Universos LAB/TRADING · DÍA D · Mandato (2026-08-02)

> **Propósito:** documento **único** para auditoría externa / cierre de etapa.  
> **No sustituye** ADRs ni premisas: las referencia y resume el *qué quedó hecho*, *cómo probarlo* y *qué queda fuera*.  
> **AsOf código + docs:** 2026-08-02 · `HELP_CONTENT_AS_OF`  
> **Repo:** `https://github.com/jvelasca/Bolsa_V1` (privado)

---

## 0. Resumen ejecutivo (una página)

Esta etapa cierra el puente **estudio → verificación temporal → operativa** en Bolsa V1:

| Pieza | Pregunta de producto | Estado |
|-------|----------------------|--------|
| **ADR-019** Universos | ¿Dónde estudio vs dónde invierto? | LAB = Backtesting/Verificar · TRADING = DEMO + Coach |
| **ADR-021** Reconciliación DÍA D | ¿La #1 que habría elegido en D es la misma que hoy? | F-hoy / F-D / V + SAME_*/DRIFT_* + **contrafactual** F-hoy#1 |
| **Verify continuidad** | ¿Por qué ACS D→hoy salía a 0 ops? | Lookback 3y + carry de posición (ya no arranque en frío) |
| **Higiene Finalistas** | ¿Por qué #1 decía SuperTrend siendo SMA? | `strategyType` = preset de la **definición** |
| **ADR-020** Mandato | ¿Qué playbook gobernaba el ticker y cuándo? | Tenure + trades + churn + **flujo enlazado** + **BD M1b** |

**Cómo auditar en 30 min**

1. Leer este doc §1–§3.  
2. Smoke UI: [operativa-test-plan-2026-07-31.md](./operativa-test-plan-2026-07-31.md) + ACS DÍA D.  
3. Scripts: `python scripts/research/diagnose_dia_d_acs_ops.py --symbol ACS --dia-d 2025-08-01`.  
4. Tests: `pnpm test:operativa` · vitest mandate / dia-d / continuity.  
5. API: migrar `mandate_tenures` · reiniciar api-python · `GET/PUT /api/accounts/{id}/mandates`.

---

## 1. Contexto y decisiones (ADRs)

### 1.1 ADR-019 — Dos universos

- **LAB:** Play, Coach, Lab, Finalistas, **Verificar D→hoy** (Cartera LAB / sandbox).  
- **TRADING:** DEMO, órdenes, rail Coach (lectura + Adoptar), **Mandato**.  
- Doc: [adr/019-dual-universes-lab-vs-trading.md](../adr/019-dual-universes-lab-vs-trading.md) · [dual-universes-lab-trading-design-2026-08-02.md](./dual-universes-lab-trading-design-2026-08-02.md).

### 1.2 ADR-021 — Reconciliación DÍA D

Artefactos:

| Artefacto | Persistencia | Rol |
|-----------|--------------|-----|
| **F-hoy** | BD `instrument_strategy_tops` | Finalistas operativos |
| **F-D** | `localStorage` `bolsa-dia-d-experiment-top-v1` | TOP experimento as-of D (no pisa F-hoy) |
| **V** | Sesión + Evidence | Replay D→hoy con #1 congelada |

Veredictos deterministas: `SAME_CONFIRMED|FAILED|MIXED`, `DRIFT_BETTER|WORSE`, `INCONCLUSIVE`.

**v1.1 contrafactual:** si F-hoy#1 ≠ F-D#1, segundo backtest misma ventana; panel muestra OOS ambas + Δ pp.

Doc: [adr/021-dia-d-reconciliation.md](../adr/021-dia-d-reconciliation.md).

### 1.3 ADR-020 — Mandato operativo

Tenure por `(accountId, instrumentId)` con actor/reason; adopción = proyección del abierto.

| Fase | Hecho |
|------|-------|
| M0–M3 cliente | Timeline, links trades, churn |
| Flujo enlazado | ventas − compras de fills ligados (no MTM) |
| **M1b BD** | Tablas + `GET/PUT /api/accounts/{id}/mandates` + hydrate/push |

Doc: [adr/020-operating-mandate-tenure.md](../adr/020-operating-mandate-tenure.md).

---

## 2. Inventario de código (auditoría por archivo)

### 2.1 DÍA D — Verify continuidad (fix 0 ops)

| Archivo | Rol |
|---------|-----|
| `apps/web/src/features/trading/dia-d-verify-continuity.ts` | `verifyApiDateFrom`, `portfolioJustBeforeDiaD`, `sliceDetailFromDiaD` |
| `apps/web/src/features/trading/dia-d-verify-continuity.test.ts` | Tests lookback / sell OOS con posición pre-D |
| `apps/web/src/features/trading/dia-d-gate-equity.ts` | `initialShares` en gate / equity |
| `apps/web/src/features/trading/trading-dia-d-replay-panel.tsx` | Run con lookback; slice a D; re-run si cache frío |
| `docs/engineering/backtesting-dia-d-premises-2026-07-31.md` | Fase C: lookback + película D→hoy |
| `scripts/research/diagnose_dia_d_acs_ops.py` | Diagnóstico ACS cold vs warm |

**Causa raíz documentada:** `dateFrom=D` sin historial → cartera flat; estrategias ya compradas en D mostraban 0 fills hasta el siguiente cruce.

### 2.2 Reconciliación + contrafactual

| Archivo | Rol |
|---------|-----|
| `apps/web/src/features/backtests/dia-d-reconciliation.ts` | Códigos + `buildCounterfactualOos` |
| `apps/web/src/features/backtests/dia-d-reconciliation.test.ts` | SAME/DRIFT + Δ en summary |
| `apps/web/src/features/backtests/dia-d-experiment-top.ts` | Persistencia F-D |
| `apps/web/src/features/trading/dia-d-reconciliation-panel.tsx` | UI OOS F-D / F-hoy / Δ |
| `trading-dia-d-replay-panel.tsx` | Query contrafactual + wire |

### 2.3 Higiene Finalistas (`strategyType`)

| Archivo | Rol |
|---------|-----|
| `instrument-top-strategy-type.ts` | `resolveExecutableStrategyType` / sanitize |
| `coach-top-save.ts` | Tipo desde `presetKey` de la def |
| `backtest-optimize-panel.ts` | `presetKey` = `definition.presetKey` (no seed proxy) |
| `backtest-explore-panel.tsx` | Sanitize antes de upsert TOP / F-D |
| `instrument-strategy-top-panel.tsx` | Auto-repair al cargar TOP vs biblioteca |

### 2.4 Mandato + M1b

| Archivo | Rol |
|---------|-----|
| `operating-mandate.ts` | Tenures, links, churn; push diferido a BD |
| `operating-mandate-sync.ts` | Hydrate GET / push PUT |
| `mandate-tenure-pnl.ts` | Flujo neto por tenure |
| `mandate-timeline-panel.tsx` | UI rail + hydrate + flujo |
| `packages/shared/src/operating-mandate.ts` | DTOs |
| `packages/database/prisma/migrations/20260802160000_mandate_tenures/` | DDL |
| `bolsa_infrastructure/.../mandate_repository.py` | Sync upsert |
| `bolsa_api/.../routes/mandates.py` | HTTP |
| `apply_mandate_tenures_migration.py` | Apply SQL ops |

**API**

```
GET  /api/accounts/{accountId}/mandates?instrumentId=
PUT  /api/accounts/{accountId}/mandates   # body { tenures, links }
```

**Aplicar migración**

```powershell
python packages/py/infrastructure/scripts/apply_mandate_tenures_migration.py
# o: node scripts/db-ensure.mjs --force-migrate
```

Reiniciar **api-python** tras pull.

### 2.5 Finalistas / embudo (contexto de la etapa)

Bugs y mejoras tocados en la misma racha (referencia):

- Orphan TOP / no-improve skip → first-write Finalistas.  
- Biblioteca filtro por instrumento.  
- Play DÍA D → F-D sin pisar F-hoy.

---

## 3. Persistencia: qué es chrome vs dominio

Regla: [UI_PREFS_LOCALSTORAGE.md](../UI_PREFS_LOCALSTORAGE.md).

| Clave / store | Tipo | Multi-dispositivo |
|---------------|------|------------------|
| `bolsa-backtest-run-context-v1` (diaD) | Chrome/sesión LAB | No |
| `bolsa-dia-d-trading-session-v1` | Sesión Verificar | No (fullBleed no se hidrata) |
| `bolsa-dia-d-experiment-top-v1` | F-D experimento | **No** (v1 local; ADR-021 futuro BD) |
| `bolsa-dia-d-evidence-archive-v1` | Archivo Evidence | Local (+ opcional Fase 2 API) |
| `bolsa-mandate-tenures-v1` | Cache mandato | **Sí vía API M1b** |
| `bolsa-mandate-trade-links-v1` | Cache links | **Sí vía API M1b** |
| `bolsa-strategy-adoption-v1` | Proyección UI | Local (deriva del tenure abierto) |
| `instrument_strategy_tops` | F-hoy | BD |

---

## 4. Ayuda en app (sync)

| Superficie | Contenido |
|------------|-----------|
| `HELP_CONTENT_AS_OF` | `2026-08-02` |
| `docs/HELP.md` | Universos · DÍA D · Mandato · Reconciliación · CORE-R |
| `backtesting-tracker.ts` | `BACKTESTING_DIA_D_GUIDE` (+ nota contrafactual) |
| Rail Coach | Mandato timeline + flujo |
| Panel Finalistas | Verificar D→hoy · repair tipos |

---

## 5. Plan de prueba (checklist auditoría)

### 5.1 DÍA D + continuidad (ACS)

- [ ] D ≈ hace 1 año · ACS · Play → F-D sin borrar F-hoy  
- [ ] Verificar D→hoy → ops > 0 si la #1 iba en posición (sell/cross)  
- [ ] Reconciliación: código SAME_* o DRIFT_*  
- [ ] Si F-hoy#1 ≠ F-D#1 → aparece OOS F-hoy + Δ pp  
- [ ] `diagnose_dia_d_acs_ops.py` imprime cold vs warm

### 5.2 Higiene TOP

- [ ] Abrir Finalistas ACS → toast repair si type proxy; GET top muestra `sma_crossover`  
- [ ] Nuevo Lab Mejor desde SuperTrend → slot type = SMA (def)

### 5.3 Mandato M1b

- [ ] Adoptar Finalista → tenure en rail  
- [ ] Orden DEMO → trade enlazado + flujo  
- [ ] Tras migrate + restart API: segundo navegador / clear site data parcial → hydrate recupera tenures  
- [ ] `PUT/GET /api/accounts/{id}/mandates` round-trip

### 5.4 Tests automatizados

```powershell
cd apps/web
npx vitest run src/features/trading/dia-d-verify-continuity.test.ts `
  src/features/backtests/dia-d-reconciliation.test.ts `
  src/features/backtests/instrument-top-strategy-type.test.ts `
  src/features/platform/mandate-tenure-pnl.test.ts `
  src/features/platform/operating-mandate.test.ts
```

---

## 6. Fuera de esta etapa (explícito)

- F-D en BD multi-dispositivo.  
- PnL mark-to-market / lots contables por mandato.  
- Auto-obsolescencia Mandato sin confirmación.  
- Walk-forward multi-ventana automático.  
- `PAPER_D_EXECUTE` / broker live.  
- CORE-R cola multi-dispositivo (sigue localStorage).  
- Belief UI / Lab Discovery P3–P9 ampliados.

---

## 7. GitHub / release

| Ítem | Valor |
|------|--------|
| Remoto | `origin` → `https://github.com/jvelasca/Bolsa_V1.git` |
| Auth PC | `gh` cuenta `jvelasca` |
| Ops credenciales | [github-credentials-and-ops.md](./github-credentials-and-ops.md) |
| Checklist release | [github-v1-release.md](./github-v1-release.md) |

Tras merge de esta etapa: reiniciar API, aplicar migración mandato, smoke §5.

---

## 8. Índice de docs vivos (esta etapa)

1. Este archivo (auditoría).  
2. [adr/019](../adr/019-dual-universes-lab-vs-trading.md) · [adr/020](../adr/020-operating-mandate-tenure.md) · [adr/021](../adr/021-dia-d-reconciliation.md).  
3. [backtesting-dia-d-premises](./backtesting-dia-d-premises-2026-07-31.md).  
4. [dual-universes design](./dual-universes-lab-trading-design-2026-08-02.md).  
5. [HELP.md](../HELP.md) · [UI_PREFS_LOCALSTORAGE.md](../UI_PREFS_LOCALSTORAGE.md).  
6. [operativa-test-plan](./operativa-test-plan-2026-07-31.md).  
7. [session-handoff-2026-08-01](./session-handoff-2026-08-01.md) (racha previa; complementar con este cierre).

---

*Fin del paquete de auditoría. Cualquier desviación entre este doc y el código: prevalece el código + ADR; actualizar este archivo en el mismo PR.*
