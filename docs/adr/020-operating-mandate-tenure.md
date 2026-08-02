# ADR 020: Mandato operativo — tenure de estrategia por instrumento (TRADING)

## Estado

**Aceptado e implementado (M0–M3 cliente + M1b BD)** — 2026-08-02  
**Tipo:** decisión de producto / modelo de puente LAB→TRADING.  
**Depende de:** [ADR-019](./019-dual-universes-lab-vs-trading.md), [ADR-015](./015-scientific-domain-vs-trading-domain.md), [ADR-008](./008-investment-accounts-and-ledger.md).  
**Diseño padre:** [dual-universes-lab-trading-design-2026-08-02.md](../engineering/dual-universes-lab-trading-design-2026-08-02.md) §5.1 / §11 (fases **M***).

**Código:** `operating-mandate.ts` · `operating-mandate-sync.ts` · `strategy-adoption.ts` · `mandate-timeline-panel.tsx` · API `GET|PUT /api/accounts/{id}/mandates` · tablas `mandate_tenures` / `mandate_trade_links`.

---

## 1. Contexto

En TRADING, un instrumento puede **adoptar** una Finalista/TOP y, más adelante, **cambiar** a otra (usuario, Coach, CORE-R). Hoy `bolsa-strategy-adoption-v1` guarda solo el **snapshot** vigente (`candidata` / `adoptada` / …), no **cuánto tiempo** estuvo cada estrategia al mando ni **quién** la cambió.

Eso impide:

- saber qué playbook gobernaba VIS entre dos fechas,
- atribuir PnL / trades al mandato correcto,
- analizar churn humano vs IA (diferencial vs journals retail que solo taguean *setup* por trade).

### 1.1 Vocabulario de mercado (referencia, no copy UI)

| Mundo | Término cercano | Gap vs nosotros |
|-------|-----------------|-----------------|
| Journals (Edgewonk, Trademetria) | *Setup* / performance by setup·instrument | Tag por **trade**, no tenure del playbook |
| QuantConnect | *Live deployment* (`deployId`) | Redeploy de algoritmo, no mandato por ticker en desk |
| Institucional | *Mandate* / *sleeve* / *style drift* | Capital y compliance, no UX retail |
| Gobernanza IA | *Promotion gate* / policy version | Quién promovió el cambio |

Bolsa necesita un objeto de producto explícito: **mandato operativo con tenure**.

---

## 2. Decisión

### 2.1 Nombre canónico

| ES (UI / docs) | EN (código / IDs) |
|----------------|-------------------|
| **Mandato operativo** | `OperatingMandate` |
| **Historial de mandato** / tenure | `MandateTenure` |
| **Cambio de mandato** | `MandateChange` (evento) |

**No** confundir con:

| Término | Universo | Rol |
|---------|----------|-----|
| **Finalistas / TOP** | LAB | Candidatas de estudio |
| **Adopción** (estados) | Puente | Vista de **estado** del mandato vigente |
| **Orden / trade** | TRADING | Ejecución bajo un mandato |

### 2.2 Modelo mínimo

```text
MandateTenure
  id
  accountId
  instrumentId
  timeframe?                 # opcional; default TF de la adopción
  strategyDefinitionId
  strategyLabelSnapshot      # por si se borra la definición
  effectiveFrom              # ISO
  effectiveTo                # null = vigente
  actor: user | coach | core_r | system
  reason: adopt | switch | propose_accepted | obsolete | manual
  sourceTopId? / sourceTopVersion?
  evidenceLevel?             # in_sample_only | lab_validated
```

**Invariantes**

1. Como máximo **un** tenure abierto (`effectiveTo = null`) por `(accountId, instrumentId)` (± timeframe si se modela).  
2. Un **cambio** cierra el tenure anterior (`effectiveTo = now`) y abre uno nuevo.  
3. La adopción UI (`bolsa-strategy-adoption-v1` o sucesor BD) es **proyección** del tenure abierto — no una segunda fuente de verdad tras M1.  
4. Trades DEMO futuros (M2) pueden llevar `mandateTenureId` opcional para atribución.

### 2.3 Relación con Adopción (U4)

| Hoy (U4) | Mañana (M1+) |
|----------|----------------|
| `setAdoption(...)` pisa el registro | `setAdoption` = cerrar tenure + abrir tenure + proyectar estado |
| Sin historial | Timeline consultable en rail Coach / Checklist |
| localStorage | M1 puede seguir en cliente append-only; M1b → BD si multi-dispositivo |

### 2.4 Fases de implementación

| Fase | Objetivo | Criterio de hecho |
|------|----------|-------------------|
| **M0** | Este ADR + glosario + enlace diseño | ✅ 2026-08-02 |
| **M1** | Persistencia tenures + UI timeline (rail Coach) | ✅ 2026-08-02 |
| **M2** | Órdenes/fills DEMO enlazan `mandateTenureId` (cliente) | ✅ 2026-08-02 |
| **M3** | Analítica churn user vs Coach/CORE-R (resumen en rail) | ✅ 2026-08-02 |
| **M1b** | Persistencia BD multi-dispositivo (tenures + links) | ✅ 2026-08-02 |

**Pendiente (no bloquea):** informe PnL contable / MTM por mandato (lots ledger).

### 2.5 Qué no es este ADR

- Auto-cambio de mandato por LLM sin Gate / confirmación.  
- Sustituir Finalistas LAB por el historial TRADING.  
- Multi-mandato paralelo en el mismo instrumento (un playbook a la vez).  
- Broker Paper/Live (cuando llegue, el mismo modelo de tenure aplica).

---

## 3. Consecuencias

**Positivas**

- Auditabilidad humana vs IA.  
- Base para atribución y “style drift” de producto.  
- Diferencial claro frente a journals que solo hacen *Performance by setup*.

**Costes**

- Migración: proyección Adopción ← tenures.  
- UI timeline y copy (“Mandato” / “Vigente desde…”).  
- Decidir persistencia cliente vs BD en M1.

**Riesgos**

- Sobre-diseñar M3 antes de tener datos → mitigar: M1 solo append + lista.

---

## 4. Ratificación

- [x] Nombre **Mandato operativo** / `OperatingMandate`  
- [x] Tenure con actor + reason + intervalos  
- [x] Un mandato abierto por instrumento×cuenta  
- [x] Adopción = proyección del tenure vigente  
- [x] Fases M0–M3 (cliente)  
- [x] Informe flujo enlazado por tenure (cliente v1 · ventas−compras; no MTM)  
- [x] Persistencia BD multi-dispositivo (M1b)  
- [ ] Informe PnL contable / mark-to-market por mandato (post ledger lots)

---

## 5. Referencias

- Código: `apps/web/src/features/platform/operating-mandate.ts` · `operating-mandate-sync.ts`  
- Adopción (proyección): `apps/web/src/features/platform/strategy-adoption.ts`  
- UI: `apps/web/src/features/trading/mandate-timeline-panel.tsx`  
- API: `apps/api-python/.../routes/mandates.py`  
- Migración: `packages/database/prisma/migrations/20260802160000_mandate_tenures/`  
- Auditoría etapa: [stage-audit-lab-dia-d-mandate-2026-08-02.md](../engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md)  
- ADR-019 §2.3 puente por instrumento  
- Ayuda → Trading · [HELP.md](../HELP.md)
