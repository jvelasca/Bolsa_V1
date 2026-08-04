# Triage — Auditorías externas round 3 (Motor Estudio) — 2026-08-04

> **Propósito:** unificar los **3 informes** recibidos sobre el motor Estudio → Opinión → Acción; resolver disensos; **ratificar O3-C**; corregir errata de stack; fijar qué se implementa en D1 y qué sigue congelado.  
> **Entrada:** [audit-brief-estudio-motor-operativo-2026-08-04.md](./audit-brief-estudio-motor-operativo-2026-08-04.md)  
> **Diseño previo:** [estudio-daily-opinion-alarms-design-2026-08-04.md](./estudio-daily-opinion-alarms-design-2026-08-04.md)  
> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md)  
> **ADR de decisión:** [ADR-022](../adr/022-estudio-daily-opinion-motor.md)  
> **AsOf:** 2026-08-04 · **Estado:** **RATIFICADO** · **D1 CERRADO** · siguiente **Operativa** → **Asesor** (Camino D AUTO execute freeze).

---

## 0. Resumen ejecutivo

| Informe | Naturaleza | Veredicto triage |
|---------|------------|------------------|
| **Auditoría 1** — Dictamen unificado A0·N4·Deep | Decisorio motor + slice D1 | **Aceptado en espíritu** · O3 · opinion persistida · on-demand · freeze AUTO |
| **Auditoría 2** — Informe A0·N4·Deep (O3-C) | Decisorio motor + invariantes + thaw | **Aceptado** · variante **O3-C** (más conservadora en D1) · precede |
| **Auditoría 3** — Valoración global proyecto | Madurez / docs / no solo motor | **Aceptado como health-check** · no redefine motor · sí refuerza disciplina documental |

### Veredicto de producto (ratificado)

1. **Modelo:** **O3-C** — UI `Vigilar → Opinar → Actuar`; motor RFC-008 debajo; **sin cron EOD en D1**.  
2. **Artefacto:** `InstrumentDailyOpinion` **sí desde D1**, `source=on_demand` primero; `eod_batch` flag-off después.  
3. **UI verdad:** una proyección **Dictamen**; IO/TOP/Radar/F3 son inputs o detalle — no 4 bandejas.  
4. **Freeze:** Camino D / `PAPER_D_EXECUTE` y `CORE_R_CRON` **siguen off**; thaw solo con checklist §7.  
5. **Long-only fase 1:** `TradingPolicy.allowShorting=false` (flag, no hardcode eterno).  
6. **SMS:** aparcado; email / push web después.  
7. **Implementación:** **no automática** — este triage cierra diseño; D1 arranca solo con OK de producto.

---

## 1. Consensos (las tres / 1+2)

| Tema | Consenso |
|------|----------|
| O3 / O3-C vs O1/O2 | **O3-C** (híbrido; D1 sin job desatendido) |
| Dictamen persistido | **Sí** |
| Cálculo inicial | **On-demand + caché por `asOfBarDate`** |
| Job EOD | **Flag-off** hasta validar datos |
| ★ Dictamen ≠ ★ Estrategia | **Separar** |
| AVISO/ALARMA | **Severidad / enrutado**, no 4º paso mental UI |
| AUTO | **Congelado** hasta métricas |
| Bounded context | Cálculo en **application** (Decision), no en analytics puro ni en React |
| Fail-closed | Sin vela EOD / Gate VETO → `no_trade` / no compra |

---

## 2. Disensos resueltos (arbitraje producto)

### 2.1 Precedencia — dos ejes distintos (no mezclar)

Las auditorías 1 y 2 mezclaban **precedencia de cálculo de stance** con **precedencia H≠M en Confirm**. Se separan:

| Eje | Orden ratificado | Uso |
|-----|------------------|-----|
| **A · Stance engine (N4)** | `Gate VETO` → `TOP stale` → `FA distress` → reglas IO/posición → default `hold_watch` | Cómo se **calcula** el dictamen |
| **B · Confirm H≠M (SEMI)** | Humano elige en Confirm; etiquetas de origen: **Finalista (H)** · **Dictamen EOD** · **Radar (M)** · IO solo diagnóstico | Cómo se **actúa** cuando hay conflicto |

**No** adoptar “Finalista > Dictamen” como regla automática de overwrite del stance: Finalista alimenta Confirm; el dictamen EOD sigue siendo la verdad de **Opinar** en UI Estudio/Operativa.

### 2.2 Long-only

| Informe 1 | Informe 2 | **Arbitraje** |
|-----------|-----------|---------------|
| Hardcoded Phase 1 | Flag `allowShorting` | **Flag** (ya existe) + **default false** en plantillas conservative/moderate + stance long-only en engine v0. Sin cortos silenciosos. |

### 2.3 Thaw AUTO — umbrales

| Informe 1 | Informe 2 | **Arbitraje (estricto compuesto)** |
|-----------|-----------|-----------------------------------|
| 60d · Prec≥75% · Rec≥60% · DD≤1.2× Lab | 30d · Prec≥60%/55% · Rec≥50% · DD&lt;10% · kill switch | **Mínimo 60 días DEMO** · **≥50 ops SEMI** · Precisión BUY **≥70%** (proxy 5d) · Recall **≥55%** · MaxDD DEMO **≤ min(10%, 1.2× MaxDD Lab)** · **0 violaciones Gate en execute** · **kill switch &lt;1s** · `PAPER_D_EXECUTE` + confirmación doble UI · ADR de thaw con evidencia |

### 2.4 Paths de implementación (errata de stack)

Ambos informes 1–2 proponen rutas que **no existen** tal cual. Equivalentes reales:

| Citado en informes | Realidad Bolsa_V1 |
|--------------------|-------------------|
| `packages/py/domain/...` | No hay paquete `domain` separado → tipos en `packages/shared` + lógica en `packages/py/application` + rows en `packages/py/infrastructure/.../models` |
| `apps/api-python/alembic/...` | Migraciones **Prisma**: `packages/database/prisma/migrations/` |
| `apps/api-python/src/routers/...` | `apps/api-python/src/bolsa_api/api/v1/routes/` |
| BullMQ / workers Node | No; jobs Python / scripts / flags env |
| Zod en backend | Pydantic en API; Zod solo si se usa en web |

**Slice D1 paths reales (cuando se autorice):**

```text
packages/database/prisma/schema.prisma + migrations/
packages/py/infrastructure/.../models/tables.py + repository
packages/py/application/.../daily_opinion (o instrument_opinions)
apps/api-python/.../routes/ (opinion / estudio)
packages/shared/src/instrument-daily-opinion.ts (o cognitive/)
apps/web/src/features/trading|instruments/ (hooks + columna / bandeja)
tests: pytest invariantes + vitest UI mínima
```

**Prohibido en D1 (consenso):** tocar analytics/market core · activar cron · Camino D · Lab backtests · Belief.

---

## 3. Auditoría 3 — qué entra / qué no

| Hallazgo A3 | Acción |
|-------------|--------|
| Arquitectura / Lab≠Trading / freeze / ADR elogiados | **Mantener** disciplina |
| “Un mapa de dominio enorme” | Backlog doc: ampliar Engineering Index / catálogo; **no bloquea** D1 motor |
| Diagramas de secuencia | Backlog; añadir 1 diagrama secuencia Opinion on-demand en ADR-022 |
| Eventos tipo Kafka | **No** abrir bus de eventos ahora (freeze Fase H) |
| Dashboard calidad / P50 latencias | Horizonte observabilidad; no bloquea O3-C |
| Riesgo: demasiada documentación | **Sí relevante** — este triage + ADR-022 son la **fuente de verdad** del motor; brief de auditoría queda histórico |

---

## 4. Matriz T1–T12 ratificada

| ID | Decisión final |
|----|----------------|
| T1 | **O3-C** |
| T2 | Opinion **persistida** D1; `on_demand` primero |
| T3 | **EOD vela** = verdad oficial del stance; Radar = momento, no pisa EOD |
| T4 | Severidad aviso/alarma en motor; UI puede filtrar dos vistas |
| T5 | Dictamen **absorbe** IO en UI; IO sigue como input L1 |
| T6 | Ver §2.1 (dos ejes) |
| T7 | Flag `allowShorting` + default false + engine long-only |
| T8 | Sin cron D1; flag `ESTUDIO_EOD_OPINION_ENABLED=false` cuando exista batch |
| T9 | Checklist §2.3 (estricto compuesto) |
| T10 | SMS no; email/push después |
| T11 | ★ separadas |
| T12 | Una bandeja «Opiniones de hoy» / columna Dictamen; resto diagnóstico |

---

## 5. Invariantes mínimos (adoptar en D1)

Del informe 2 §5.1 (N4), adoptados:

1. Un dictamen por `(instrumentId, asOfBarDate)` [+ accountId si multi-cuenta].  
2. Stance nunca null.  
3. Gate VETO → `no_trade`.  
4. TOP stale (>30d) → `review_strategy` (o hold con ★ baja — v0: `review_strategy`).  
5. `sell`/`reduce` solo con largo abierto.  
6. FA distress → nunca `buy`; techo ★ dictamen ≤3.  
7. Reasons códigos estables.  
8. Idempotencia por clave.  
9. Fail-closed si datos EOD no consolidados.  
10. Tests de invariante en CI (pytest) antes de UI rica.

---

## 6. Mercado — aportes retenidos

| Fuente | Aporte retenido |
|--------|-----------------|
| IB Risk / rebalance EOD | Postura EOD estable; no perseguir intradía |
| Koyfin / MarketSmith | Etiqueta semántica + color; números en detalle |
| Zacks-like rank | Dictamen = objeto de dominio |
| eToro copy | SEMI antes de AUTO |
| TV / PRT (ya en brief) | No confundir alerta con opinión |

---

## 7. Plan post-ratificación (sin código hasta OK)

| Paso | Qué | Estado |
|------|-----|--------|
| R0 | Este triage + ADR-022 | **Hecho** |
| R1 | Usuario OK explícito «implementar D1» | **Hecho** (2026-08-04) |
| D1 | Tabla + service on-demand + API + UI mínima Estudio/Operativa | **Cerrado** (`3b5d954`+) |
| D1b | Tests invariante | **Hecho** (pytest stance) |
| D1c | Evolución: historial + sparkline ★ dictamen | **Hecho** (`f385a39`) |
| D1d | Operativa: solo dictamen del valor (lista global → Asesor) | **Hecho** (`bc3fd95`) |
| **Op** | **Operativa vital** (mesa TRADING / SEMI / mandato / pulso) — clave de app | **Cerrado** (SEMI desk + Outcomes 2026-08-04) |
| **Asesor** | Research → Asesor + bandeja «opiniones de hoy» (datos ya en motor) | **Cerrado** (`e898b95` · tab Opiniones) |
| D2 | Batch EOD flag-off + canales | **Cerrado** — toast + prefs email UI + mapa + EOD force |
| D3+ | Métricas / thaw Camino D AUTO execute | [Checklist thaw](./camino-d-auto-thaw-checklist-2026-08-04.md) — **sigue freeze** |

---

## 8. Actualizaciones de docs hechas / pendientes

| Doc | Acción |
|-----|--------|
| Este triage | **Creado** |
| [ADR-022](../adr/022-estudio-daily-opinion-motor.md) | **Creado** |
| Freeze | + sección motor Estudio / thaw AUTO |
| audit-pack / Engineering Index / brief | Enlaces round 3 |
| Diseño opinion alarms | Marcar O3-C ratificado |

---

## 9. Mensaje a las auditorías

Gracias. **O3-C** queda ratificado. Corregimos paths al monorepo real (Prisma + `bolsa_application` + routes FastAPI). Separaremos precedencia de **cálculo** vs **Confirm**. No abriremos AUTO ni cron EOD en D1. La Auditoría 3 refuerza: el riesgo ahora es **disciplina documental**, no “más features” — el ADR-022 es la ancla.

---

## 10. Cierre final round 3+ (informes de confirmación 2026-08-04)

Tres informes adicionales tras el triage:

| Informe | Foco | Acción |
|---------|------|--------|
| **Confirmación A** (madurez plataforma / Lab) | Documentation Pyramid, Domain Map, versionado científico, Decision Log, KPIs Lab, deprecación, UI vs backend | **Backlog gobernanza Lab** — **no bloquea D1** (ver §10.1) |
| **Confirmación B** (cierre motor O3-C) | Ratifica triage + ADR-022; paths reales; pide OK producto para D1 | **Aceptado** |
| **Confirmación C** (auditoría final motor) | Verifica alineación 000, invariantes 10/10, seguridad, plan D1 detallado; «Adelante con D1» tras OK | **Aceptado** · checklist docs §9 de C ya cubierto en triage/ADR/freeze/index |

### 10.1 Backlog gobernanza Lab (Confirmación A — no D1)

| Ítem | Prioridad | Nota |
|------|-----------|------|
| Documentation Pyramid / taxonomía docs | P2 | Engineering Index ya es padre; reforzar pirámide en Index §0 |
| DOMAIN MAP 1 página | P2 | Diagrama entidades Research+Trading |
| Research Architecture Book | P3 | Libro único para nuevos devs |
| Versionado científico en trials (engine/indicators/costs/adapters) | P2 | Extiende CampaignManifest (A0 H4 previo) |
| Research Snapshot / hash estado Lab | P3 | |
| Decision Log (≠ ADR) | P2 | Freeze ya registra no-hacer; log append-only opcional |
| Data Provider Interface v2 | P3 | Yahoo SPOF conocido; no Alpaca ahora |
| KPIs del laboratorio (coverage, reproducibility…) | P2 | Junto Lab Health |
| Política Experimental→Supported→Deprecated→Removed | P2 | |
| Elevar UX producto al nivel del backend | P1 producto (paralelo a D1 opinión) | Motor Opinión es parte de ese salto |

### 10.2 Luz verde técnica D1

Confirmaciones B+C: diseño **listo**. Código D1 **solo** con frase explícita de producto («implementa D1» / «OK D1»).

### 10.3 Checklist docs Confirmación C §9

| Doc | Estado |
|-----|--------|
| engineering-index + triage + ADR-022 | Hecho |
| freeze + motor / thaw | Hecho |
| audit-pack round 3 | Hecho |
| diseño opinion O3-C ratificado | Hecho |
| docs/README enlace ADR-022 | **Hecho** |

---

*Fin cierre confirmaciones. Esperando OK producto para código D1.*

---

## 11. Cierre D1 (2026-08-04) — secuencia producto

**D1 motor O3-C cerrado en código.** Artefacto `InstrumentDailyOpinion` on-demand + caché; Evolución con serie; Operativa con dictamen del activo.

### Secuencia acordada (producto)

| # | Foco | Incluye | No incluye |
|---|------|---------|------------|
| 1 | ~~D1 motor~~ | Dictamen, API, Evolución, invariantes | — |
| 2 | **Operativa** (vital) | Mesa TRADING, SEMI/Confirm, mandato, pulso IO+TOP+dictamen del valor | **Camino D AUTO execute** (sigue freeze) |
| 3 | ~~**Asesor**~~ | Renombrar/integrar Research; bandeja opiniones Estudio; UI de datos **ya** calculables | Cron EOD batch real (flag off); thaw AUTO |
| 4 | ~~**Canales**~~ | Toast Alarmas + email prefs UI + mapa leyenda + EOD force | SMS; thaw AUTO |
| 5 | **AUTO** (prep) | Telemetría + checklist thaw Camino D | Flip `PAPER_D_EXECUTE` sin evidencia |

**Nota AUTO:** entrar por [camino-d-auto-thaw-checklist](./camino-d-auto-thaw-checklist-2026-08-04.md). Auditar primero: [audit-pack-estudio-asesor-canales](./audit-pack-estudio-asesor-canales-2026-08-04.md).

**Nota Asesor:** los inputs (IO, FA, TOP, dictámenes, narrative) ya existen vía APIs D1; Asesor es **presentación + orquestación**, no un segundo motor.