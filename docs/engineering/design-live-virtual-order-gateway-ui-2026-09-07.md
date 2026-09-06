# Diseño UI — Pasarela LIVE VIRTUAL de órdenes (híbrido)

> **AsOf:** 2026-09-07 · **Tip:** [`v2.10.1-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.10.1-beta) → [`a060af37`](https://github.com/jvelasca/Bolsa_V1/commit/a060af37) · package `1.39.1-beta`.  
> **Padre:** [audit pack LIVE](./audit-pack-live-venue-thaw-design-2026-09-06.md) · [runbook gates](./runbook-live-venue-thaw-gates-2026-09-06.md) · [arranque](./arranque-agente-pista-a-estricto-2026-09-07.md) · [cierre sesión](./traspaso-relevo-cierre-sesion-pista-a-2026-09-06.md).  
> **Veredicto:** modelo **híbrido** (telegrama + por qué) **documentado** · **UI Confirm implementada** (excepción freeze owner 2026-09-07 · sin mesa nueva) · **NO** tip/bump · **NO** flips capital · settlement real **PARKED** · ≠ Accept LIVE.

---

## 0. Honestidad / freeze

| Afirmar                                                 | No afirmar                                                      |
| ------------------------------------------------------- | --------------------------------------------------------------- |
| Concepto UI de pasarela **híbrido** cerrado en este doc | Que LIVE capital / thaw / Accept LIVE están listos              |
| UI híbrida **dentro de Confirm** (venue=live)           | Que mock FILL = settlement XTB real                             |
| LIVE de estudio = **VIRTUAL / SIMULADO** (meses)        | Que este diseño autoriza flip `brokerVenue` / `PAPER_D_EXECUTE` |
| Confirm = firma · Arm ≠ Execute · Ranking ≠ BUY         | Arquitectura de pasarela de settlement real                     |
| Escalera `submitted ≠ filled ≠ executed`                | Que APP está 100% probada                                       |

Freeze: NO LIVE capital · LIVE solo **VIRTUAL** hasta APP 100% · `PAPER_D_EXECUTE` default off · Confirm = firma · Arm ≠ Execute · Ranking ≠ BUY · **NO MÁS PANELES** · **PRODUCT FREEZE** · package `1.39.1-beta`.

### Premisas owner (heredadas)

1. **LIVE VIRTUAL** hasta APP **100% probada**.
2. Destino conceptual = pasarela **VISUAL** de órdenes al broker — **concepto UI** = este doc; **implementación producto** = futura; **settlement real** = no especificado aquí.
3. Estudio / diseño ≠ thaw · ≠ Accept LIVE · ≠ flip venue/execute.

---

## 1. Decisión canónica (owner 2026-09-07)

Modelo **híbrido** (no solo telegrama, no chat social):

| Zona         | Rol                                                                       |
| ------------ | ------------------------------------------------------------------------- |
| Banner       | **LIVE VIRTUAL · SIMULADO · no capital real** — siempre visible           |
| Columna izq. | **Telegrama al broker** — despacho estructurado (qué se envía)            |
| Columna der. | **Para ti (por qué)** — narrativa humana (por qué valor / tamaño / orden) |
| Pie          | Escalera de estados + CTA Confirm = firma                                 |

Fuera de modelo: burbujas tipo mensajería social; mesa/panel nuevo; one-click sin firma.

---

## 2. Benchmark apps top

Patrón de industria (todas): **ticket → review → firma → lifecycle**.

| App          | Qué                                       | Firma                   | Post-envío                              | ¿Por qué la orden?                                |
| ------------ | ----------------------------------------- | ----------------------- | --------------------------------------- | ------------------------------------------------- |
| Robinhood    | Resumen limpio (lado, qty/importe, coste) | Swipe up                | Toast / estado simple                   | Casi nada                                         |
| thinkorswim  | Ticket denso + Confirm and Send           | Botón Confirm and Send  | Submitting → Accepted → Filled/Rejected | Riesgo/P&L en opciones; sin narrativa de decisión |
| IBKR TWS     | Ticket pro (bid/ask, costes, routing)     | Submit                  | Blotter / order status                  | Datos, no explicación humana                      |
| XTB xStation | Deal ticket + popup Confirm               | Yes / one-click opt-out | Terminal posiciones                     | Calculadora de impacto; no “por qué comprar”      |

**Gap común:** ninguna pone el **por qué** (valor, tamaño, stop, ahora) en primer plano junto al ticket.

**Bolsa (objetivo diseño):** igual en mecánica (ticket + review + firma + estados) + **mejor** en narrativa (columna Por qué) + sello **VIRTUAL/SIMULADO** imposible de malinterpretar.

---

## 3. Layout canónico (wireframe)

```text
┌─────────────────────────────────────────────────────────────┐
│  LIVE VIRTUAL · SIMULADO · no capital real                  │
│  Respuesta del broker = simulada · submitted ≠ fill real    │
├──────────────────────────┬──────────────────────────────────┤
│  TELEGRAMA AL BROKER     │  PARA TI (POR QUÉ)               │
│                          │                                  │
│  DE:  Mesa Bolsa         │  Por qué este valor              │
│  A:   Broker (VIRTUAL)   │  · … (DecisionExplain / dictamen)│
│  REF: proposalId / F3    │                                  │
│                          │  Por qué este tamaño / precio    │
│  BUY  AAPL  10 @ 192.40  │  · … (TradePlan / risk / notional)│
│  TIPO LIMIT · TIF DAY    │                                  │
│  STOP plan: 188.20       │  Por qué se realiza esta orden   │
│  NOTIONAL ~ … · fees ~ … │  · … (fase operativa / mandato)  │
│                          │                                  │
│  ─────────────────       │  Qué NO implica                  │
│  ESTADO (escalera):      │  · Ranking ≠ BUY                 │
│  proposed                │  · Arm ≠ Execute                 │
│  → signed                │  · VIRTUAL ≠ capital real        │
│  → submitted             │                                  │
│  → filled* | rejected    │  Fuentes: TradePlan · DECISIÓN   │
│     | not_wired          │  · risk blocks Confirm (existentes)│
│  *respuesta SIMULADA     │                                  │
├──────────────────────────┴──────────────────────────────────┤
│  [ Firmar · Ejecutar en LIVE VIRTUAL (simulado) ]           │
│  Confirm = firma humana · nunca se envía sola               │
└─────────────────────────────────────────────────────────────┘
```

### Campos mínimos — Telegrama

| Campo                | Contenido                                  |
| -------------------- | ------------------------------------------ |
| DE / A               | Mesa → Broker (VIRTUAL)                    |
| REF                  | `proposalId` / id F3                       |
| Lado + símbolo + qty | BUY/SELL · ticker · shares                 |
| Precio / tipo / TIF  | limit/market · DAY/GTC…                    |
| Stop / plan          | nivel del TradePlan si aplica              |
| Notional / fees      | estimación (igual espíritu ticket preview) |
| Estado               | un paso de la escalera + nota simulado     |

### Bloques mínimos — Por qué

| Bloque             | Pregunta                    | Fuente de datos (existente; no inventar motor) |
| ------------------ | --------------------------- | ---------------------------------------------- |
| Valor              | ¿Por qué este ticker ahora? | DecisionExplain / dictamen / fase operativa    |
| Tamaño-precio      | ¿Por qué este qty / precio? | TradePlan · ticket preview · risk signature    |
| Orden              | ¿Por qué firmar esta orden? | Plan de entrada / protect / mandato SEMI       |
| Anti-implicaciones | ¿Qué no autoriza esto?      | Ranking ≠ BUY · Arm ≠ Execute · VIRTUAL        |

Si falta dato: mostrar hueco honesto («sin explicación disponible») — **no** inventar texto de PASS.

---

## 4. Escalera de estados (honestidad)

```text
proposed → signed → submitted → filled* | rejected | not_wired
                              ↘ unknown (boom / sin ledger)
```

| Estado      | Significado UI            | Copy obligatorio                      |
| ----------- | ------------------------- | ------------------------------------- |
| `proposed`  | App propone; aún no firma | «Propuesta · sin firma»               |
| `signed`    | Humano firmó CTA          | «Firmado · envío VIRTUAL»             |
| `submitted` | Bridge aceptó envío mock  | «Enviada (simulado) · no fill»        |
| `filled*`   | Mock FILL                 | «Fill SIMULADO · ≠ settlement real»   |
| `rejected`  | Mock/policy deny          | «Rechazada (simulado o policy)»       |
| `not_wired` | Sin bridge URL / adapter  | «Broker no cableado»                  |
| `unknown`   | Boom / ledger no OK       | «Estado desconocido · no asumir fill» |

Alineado con runbook: `not_wired → rejected → submitted → filled → executed` (executed solo si filled + `execute_trade` OK; en VIRTUAL no afirmar capital).

---

## 5. Copy rules (anti-confusión)

### Obligatorio en superficie LIVE VIRTUAL

- «LIVE VIRTUAL»
- «SIMULADO» / «respuesta del broker simulada»
- «no capital real» (banner o CTA)

### CTA permitida

- «Firmar · Ejecutar en LIVE VIRTUAL (simulado)»
- «Confirmar Intent» (inspección; sin execute) — reutilizar semántica Confirm actual

### Prohibido

- «Orden enviada al mercado real»
- «Fill XTB real» / «settlement broker»
- «LIVE listo» / «Accept LIVE» / «thaw»
- Tratar `LIVE_EXPERIMENTAL` como Accepted
- CTA «Ejecutar en LIVE» **sin** cualificar VIRTUAL/simulado en esta fase de diseño
- «Ranking autoriza compra» / confundir Arm con Execute

### Paper vs LIVE VIRTUAL (vocabulario)

| Venue de estudio   | Copy UI (diseño)                                |
| ------------------ | ----------------------------------------------- |
| paper              | PAPER / demo paths (existente)                  |
| live (fase actual) | **LIVE VIRTUAL · SIMULADO** — no “LIVE capital” |

---

## 6. Mapeo a lo existente (sin implementar)

Contenedor futuro **conceptual**: extensión de Confirm (drawer `/confirm` + `supervised-f3-panel`) — **no** mesa nueva · **no** panel paralelo bajo freeze.

| Zona diseño      | Origen actual (producto hoy)                                                                                                      |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Telegrama campos | `f3-ticket-preview-block` / `f3-ticket-preview.ts`                                                                                |
| Por qué          | `decision-explain-panel` / DecisionExplain · TradePlan · `f3-trade-plan-risk-*` · `f3-risk-signature-block` · exit/protect blocks |
| CTA firma        | SupervisedF3: Confirmar Intent / Ejecutar en PAPER\|LIVE                                                                          |
| Badge venue      | Hoy: `confirm-live-venue-badge` («LIVE experimental…») → **diseño:** sustituir mentalmente por **LIVE VIRTUAL · SIMULADO**        |
| Escalera         | Runbook gates + estados adapter (`not_wired` / `rejected` / `submitted` / `filled`)                                               |
| Help language    | `operating-desk-help.ts` — alinear cuando se implemente UI (fuera de esta sesión)                                                 |

**No tocar en esta sesión:** `apps/web/**` · tip/bump · env flips · W+5.

---

## 7. Relación con thaw / Accept (ortogonal)

| Cadena                      | Estado                                                                                                                |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Este diseño UI VIRTUAL      | Documentado · no shipped                                                                                              |
| Scorecard L1–L10 thaw venue | **no PASS** ([audit pack](./audit-pack-live-venue-thaw-design-2026-09-06.md))                                         |
| Accept estricto Camino D    | **W+5** **0/5** · gates planos · **NO** Accept · [remeasure](./traspaso-relevo-thaw-estricto-remeasure-2026-09-07.md) |
| Money path XTB real         | PARKED                                                                                                                |
| Owner word thaw LIVE        | **NO**                                                                                                                |

Implementar el wireframe en producto **no** autoriza flip `brokerVenue=live` ni `PAPER_D_EXECUTE`.

---

## 8. Qué NO afirmar

- Pasarela UI **Accepted** o certificada en cabina.
- UI producto ya shipped / paneles nuevos entregados.
- Thaw venue · Accept LIVE · capital prod.
- VIRTUAL / mock FILL = dinero real.
- Arquitectura detallada de settlement / pasarela API broker real.
- Que “diseño cerrado” = “APP 100% probada”.
- PASS de gates P1–P5 / Accept estricto (W+5 = sello **0/5**, no progreso).

---

## 9. Siguiente (fuera de este doc)

1. ~~Implementar híbrido dentro de Confirm~~ → **hecho** (`apps/web/src/features/confirm/live-virtual-*` + `supervised-f3-panel`) bajo excepción freeze owner.
2. ~~E2E Confirm venue=live (mock)~~ → **PASS** `gp-e2e-live-virtual-confirm-mock` (`E2E_RUN=1 pnpm e2e -- gp-e2e-live-virtual-confirm-mock`).
3. Settlement real / pasarela API = sesión + ADR dedicados tras APP 100% + palabra owner.

Relevo diseño: [traspaso-relevo-design-live-virtual-ui-2026-09-07](./traspaso-relevo-design-live-virtual-ui-2026-09-07.md).  
Pista A: [W+5 remasure](./traspaso-relevo-thaw-estricto-remeasure-2026-09-07.md) · probe histórico [NO W+5](./traspaso-relevo-pista-a-probe-no-w5-2026-09-07.md).

---

## 10. Freeze (copiar)

NO LIVE capital · LIVE solo **VIRTUAL** hasta APP 100% · respuesta broker **SIMULADA** · `PAPER_D_EXECUTE` default off · Confirm = firma · Ranking ≠ BUY · Arm ≠ Execute · **NO MÁS PANELES** · **PRODUCT FREEZE** · package `1.39.1-beta` · DESIGN_ONLY · UI concepto documentado ≠ UI shipped ≠ thaw.
