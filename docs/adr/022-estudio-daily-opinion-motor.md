# ADR-022 — Motor de opinión diaria Estudio (O3-C)

- **Status:** Accepted  
- **Date:** 2026-08-04  
- **Deciders:** Producto Bolsa_V1 + auditorías externas round 3 (A0 · N4 · Deep)  
- **Padre:** [engineering-index](../engineering/engineering-index-2026-08-03.md)  
- **Triage:** [audit-ext-round3-triage-estudio-motor-2026-08-04](../engineering/audit-ext-round3-triage-estudio-motor-2026-08-04.md)  
- **Brief:** [audit-brief-estudio-motor-operativo-2026-08-04](../engineering/audit-brief-estudio-motor-operativo-2026-08-04.md)

## Context

Bolsa_V1 tiene Lab (TOP, CORE-R), Estudio, IO, SEMI Confirm (Camino C) y Gate long-only por defecto, pero **no** un objeto de producto que diga «Comprar / Vigilar / Vender» por valor y día. El mercado resuelve esto con alertas de condición (TV/PRT); nosotros necesitamos una **opinión de cartera** auditable sin precipitar AUTO (Camino D congelado).

## Decision

1. Adoptar **O3-C**: UI en 3 pasos **Vigilar → Opinar → Actuar**; motor interno alineado con RFC-008.  
2. Introducir artefacto de dominio **`InstrumentDailyOpinion`** (persistido).  
3. **D1:** cálculo **on-demand** + caché por vela EOD; **sin** cron/job desatendido. **Estado 2026-08-04: D1 implementado y cerrado** (ver triage §11).  
4. Batch EOD solo con flag `ESTUDIO_EOD_OPINION_ENABLED=false` por defecto (fase posterior).  
5. UI: el Dictamen es la proyección principal; IO/TOP/Radar/F3 no compiten como “verdades” de bandeja.  
6. ★ Dictamen ≠ ★ Estrategia (TOP).  
7. Long-only vía `TradingPolicy.allowShorting` (default false) + reglas de stance.  
8. AUTO: freeze hasta checklist de thaw del triage round 3.  
9. Implementación: `packages/py/application` + Prisma + routes FastAPI + React consumer — **no** analytics puro ni workers inventados.

## Consequences

### Positive
- Modelo mental familiar + potencia Lab/Gate.  
- Auditable y medible antes de AUTO.  
- Reduce riesgo de alertas fantasma (on-demand primero).

### Negative / risks
- Complejidad de producto si la UI no consolida.  
- On-demand puede ser lento sin bulk prefetch (mitigar en D1).  
- Dos ★ pueden confundir si el copy es pobre.

### Neutral
- Camino C (SEMI) sigue siendo el canal de acción humana.  
- Radar sigue siendo momento (M), no pisa stance EOD oficial.

## Sequence (on-demand D1)

```text
Usuario abre Estudio / Opinar
  → GET/POST opinion (instrumentIds, asOf?)
  → Application DailyOpinionService
  → Prefetch bars/FA/TOP/positions/policy
  → StanceEngine (invariantes)
  → Upsert instrument_daily_opinions (idempotent)
  → UI render stance + ★
```

## Links

- Diseño: [estudio-daily-opinion-alarms-design-2026-08-04](../engineering/estudio-daily-opinion-alarms-design-2026-08-04.md)  
- Freeze: [post-audit-decision-freeze-2026-08-03](../engineering/post-audit-decision-freeze-2026-08-03.md)  
- Cierre D1 + secuencia Op → Asesor: [triage §11](../engineering/audit-ext-round3-triage-estudio-motor-2026-08-04.md)  
- RFC-008, ADR-010, ADR-019, ADR-020