# Diseño — Estudio diario → Opinión → Avisos/Alarmas → Acción (pausa pre-AUTO)

> **AsOf:** 2026-08-04 · **Estado:** **O3-C RATIFICADO** · **D1 CERRADO** (código + Evolución). Siguiente: Operativa → Asesor.  
> **Triage:** [audit-ext-round3-triage-estudio-motor-2026-08-04.md](./audit-ext-round3-triage-estudio-motor-2026-08-04.md) · [ADR-022](../adr/022-estudio-daily-opinion-motor.md).  
> **Auditorías externas (round 3):** brief → [audit-brief-estudio-motor-operativo-2026-08-04.md](./audit-brief-estudio-motor-operativo-2026-08-04.md).  
> **Padres:** [demo-operating-modes-brief-2026-08-03](./demo-operating-modes-brief-2026-08-03.md) · [trading-operativa-panel-2026-08-04](./trading-operativa-panel-2026-08-04.md) · [research-lifecycle](./research-lifecycle.md) · ADR-010/019/020 · RFC-008.  
> **Freeze vigente:** Camino D / `PAPER_D_EXECUTE` · Belief→Coach · `CORE_R_CRON` off · Strategy Studio/F5 · `COST_MODEL_V2`.

---

## 0. Veredicto en una frase

**Estudio** es el universo vigilado; cada sesión **1d** (cierre consolidado) produce un **dictamen** versionado por valor; ese dictamen alimenta **Avisos** (informativos) y **Alarmas** (accionables); en SEMI las Alarmas entran a Confirm (Camino C); AUTO solo reabre Camino D cuando el dictamen + Gate + política de canales estén maduros y medibles.

---

## 1. Premisa de producto (cerrada en esta pausa)

| # | Premisa | Decisión |
|---|---------|----------|
| P1 | Universo del bucle | Solo miembros de **Estudio** (membresía explícita). No ≡ pestañas abiertas. |
| P2 | Granularidad | **Diaria (1d)** por defecto = TF de la cartera DEMO. Otras granularidades = fase posterior. |
| P3 | Momento de evaluación | **Post-cierre** con vela diaria consolidada (no mid-session salvo Aviso soft). |
| P4 | Dirección | **Solo largo (long-only)** en esta fase: operamos cuando el valor **sube / hay setup de compra o salida de largos**. **No cortos.** Documentado abajo §1.1. |
| P5 | Salida humana | Cada valor muestra una **opinión** clara + **calidad ★** + contexto (IO, TOP, mandato, narrativa). |
| P6 | Dos niveles de notificación | **AVISO** ≠ **ALARMA** (taxonomía primera clase). |
| P7 | Acción | Aviso → info. Alarma → según modo: MANUAL=inbox; SEMI=Confirm; AUTO=execute (congelado). |
| P8 | Estrategias | Cada valor en Estudio debe tener TOP/estrategia **viva** y trazable en el tiempo (no snapshot muerto). |
| P9 | Eficacia > teatro | El sistema debe ser auditable: dictamen → motivo → canal → (no)acción. Sin LLM que salte Gate (RFC-008). |

### 1.1 Long-only (política explícita)

- **Producto Estudio / libro DEMO (fase actual):** no se proponen ni ejecutan cortos (`recommend_short` fuera de alcance).
- **Ya alineado en código:** plantillas conservative/moderate de `TradingPolicy` tienen `allowShorting: false`; Gate veta short.
- **Futuro:** cortos solo con mandato de producto + plantilla aggressive + UI explícita; nunca como default silencioso del bucle Estudio.
- **Salidas:** «Vender» / «Reducir» significan **cerrar o aligerar largos**, no abrir short.

---

## 2. Comparativa con apps top del mercado

> Referencias: **TradingView**, **thinkorswim (Schwab)**, **ProRealTime** (inspiración UI), **Stock Alarm Pro** (alertas retail), **Bloomberg** (institucional, techo).  
> Criterio: no “quién tiene más features”, sino **cómo resuelven vigilancia → señal → aviso → acción** y dónde Bolsa V1 puede ser más **eficaz y simple**.

### 2.1 Tabla maestra (capacidad × app × nosotros)

| Capacidad | TradingView | thinkorswim | ProRealTime | Stock Alarm Pro | Bloomberg Terminal | **Bolsa V1 (objetivo)** |
|-----------|-------------|-------------|-------------|-----------------|--------------------|-------------------------|
| **Universo vigilado** | Watchlists + alert-on-list | Watchlists + scan/watchlist columns | ProScreener / listas / Top Movers | Watchlists de alertas | Launchpad / monitors institucionales | **Estudio** (membresía explícita, no ≡ tabs) |
| **Qué “dice” del valor** | Condición técnica/precio (Pine); sin stance de cartera unificado | thinkScript / conditional; workstation, no “opinión de libro” | Screener hit o señal de sistema ProOrder | Precio / % / RSI / MA / earnings | Analytics + rules + OMS | **Dictamen EOD**: Comprar / Vigilar / Sobrecomprado / Reducir / Vender / Sin operar / Revisar estrategia |
| **Calidad / confianza** | Implícita (tú interpretas el chart) | Probabilidades opciones; no ★ de dictamen diario | Reportes de sistema; no ★ de opinión diaria | Umbrales fijos | Risk/analytics pre-trade | **★ Dictamen** (día) **≠** **★ Estrategia** (TOP Lab) |
| **Momento de evaluación** | RT / por barra / alerta continua | RT + scans | RT o cierre de barra (screener); ProOrder server-side | RT / umbral | Continuous + rules | **Post-cierre 1d consolidado** (batch Estudio) + Radar on_bar como complemento |
| **Jerarquía notificaciones** | Alertas (volumen alto; freemium limita nº) | Conditional alerts + notificaciones broker | Alertas + beep screener; órdenes ≠ screener | Push/email (producto = alerta) | Rules / OMS / compliance | **AVISO** (info) vs **ALARMA** (accionable) — primera clase |
| **Canales** | App / email / webhook | App / email (Schwab) | App / email; ProOrder en servidor | Push + email | Terminal + API + EMS | Inbox + toast + email; SMS fase 2 |
| **Puente a ejecución** | Trade-from-chart / brokers conectados (separado de la alerta) | Nativo broker (OCO/OTO/condicional) | **ProScreener no opera**; **ProOrder** sí (sistema distinto) | No ejecución | Pricing → liquidity → execution | **Misma opinión** → MANUAL aviso · SEMI Confirm · AUTO execute (D congelado) |
| **Humano en el loop** | Tú decides al ver la alerta | Conditional orders / tú | ProOrder = auto; alert-order limitado | Solo aviso | Desk + rules | **SEMI primero** (H≠M en Confirm); AUTO solo tras métricas |
| **Estrategia en el tiempo** | Pine/script suelto; backtest aparte | thinkScript + papel | ProBacktest → ProOrder | N/A | Strategy/analytics desk | **TOP vivo + mandato + CORE-R review** ligados al valor Estudio |
| **FA + TA juntos** | Principalmente TA; fundamentals aparte | Fuerte opciones/TA; fundamentals broker | TA-first | TA/precio | Multi-asset research | **Composite/IO + FA distress** en el dictamen |
| **Long-only de producto** | Tú eliges long/short | Long/short/options | Long/short según sistema | N/A | Según mandato desk | **Long-only explícito** en fase Estudio (no cortos) |
| **Auditoría “por qué”** | Débil (alerta disparó) | Mejor en órdenes; no dictamen diario | Logs ProOrder | Mínima | Fuerte (compliance) | `InstrumentDailyOpinion` versionado + Gate snapshot + narrativa |
| **Simplicidad** | Potente pero ruido/alerta-fatigue | Workstation densa | Potente; **screener ≠ autotrade** confunde | Muy simple, poco “opinión” | Cara / compleja | **Una opinión/día/valor** que el usuario lee en 2 s |

### 2.2 Lectura por competidor (qué copiamos / qué evitamos)

| App | Fortaleza a respetar | Debilidad / hueco | Cómo lo mejoramos |
|-----|----------------------|-------------------|-------------------|
| **TradingView** | Alertas flexibles (Pine), watchlist alerts, webhooks | Señal ≠ decisión de cartera; fatiga; freemium limita | Dictamen semántico + cupo de Alarmas por ★; webhook/email después |
| **thinkorswim** | Ejecución + condicionales + profundidad US | Pesado; atado a broker; no “libro DEMO + Lab” unificado | Workstation ligera + DEMO/SEMI sin amarrar broker aún |
| **ProRealTime** | UI profesional; ProOrder server-side; ProScreener potente | **Screener no dispara trade**; hay que vivir en dos mundos | Un solo pipeline: Estudio → dictamen → aviso/alarma → Confirm/AUTO |
| **Stock Alarm Pro** | Entrega móvil fiable, setup en segundos | Sin estrategia Lab ni Gate ni sizing | Misma facilidad de canales, encima de Lab+Gate+libro |
| **Bloomberg** | Ciclo pricing→risk→execution auditado | Inalcanzable en coste/UX personal | Tomar la idea de **reglas + auditoría**, no el terminal |

### 2.3 Tesis competitiva (una línea)

Las tops **separan** (o confunden) *condición técnica*, *alerta* y *ejecución*. Bolsa V1 apuesta por **una opinión diaria auditable por valor de Estudio** que alimenta a la vez la UI, los Avisos/Alarmas y —cuando toque— SEMI/AUTO, con estrategias Lab vivas y **long-only** claro.

No competimos en “más alertas”. Competimos en **acierto percibido + claridad + acción controlada**.

---

## 2.4 Estudio profundo — operativa de 3 pasos (ellas) vs la nuestra

> **AsOf:** 2026-08-04 · **Estado:** análisis previo a D1 — **sin implementar**.  
> Pregunta: ¿copiamos el modelo mental de 3 pasos del mercado, el pipeline rico que ya tenemos (RFC-008 + caminos), o un híbrido?

### A) El modelo de 3 pasos del mercado (canónico)

Casi todas las apps retail/pro “sencillas” reducen la operativa a:

```text
1. VIGILAR     →  2. AVISAR        →  3. ACTUAR
   (watch/scan)      (alert/push)        (orden manual o auto)
```

| Paso | TradingView | thinkorswim | ProRealTime | Stock Alarm |
|------|-------------|-------------|-------------|-------------|
| 1 Vigilar | Watchlist + condiciones Pine | Watchlist + scans | ProScreener / listas | Lista + umbrales |
| 2 Avisar | Alert (app/email/webhook) | Conditional alert | Alert / beep | Push / email |
| 3 Actuar | Tú o broker conectado | Orden / condicional nativo | **ProOrder** (otro módulo) o tú | No actúa |

**Pros del 3 pasos de mercado**

| Pro | Por qué importa |
|-----|-----------------|
| Modelo mental inmediato | “Me avisa → yo miro → opero” — curva de aprendizaje baja |
| Bajo acoplamiento | Fallar una alerta no rompe el broker |
| Probado en fatiga real | La gente ya sabe filtrar ruido (mal, pero sabe) |
| Fácil de vender | Feature list clara: alerts, screens, trade |
| Implementación incremental | Empiezas por paso 2 sin tener Decision Engine |

**Contras del 3 pasos de mercado**

| Contra | Efecto |
|--------|--------|
| El paso 2 es **condición**, no **opinión** | “RSI < 30” ≠ “Comprar con ★4 para tu libro DEMO” |
| Paso 1 y 3 a menudo desconectados | PRT: screener ≠ ProOrder; TV: alerta ≠ sizing/Gate |
| Sin gobierno de cartera | No maxOpen, no mandato, no long-only de producto |
| Sin auditoría de decisión | Difícil responder “¿por qué compramos SAN ayer?” |
| Auto = script opaco | ProOrder/Pine auto ejecuta sin Confirm humano tipado |
| Ruido estructural | Más alertas ≠ más aciertos |
| No hay Lab científico unido al trade | Backtest y alerta viven en mundos distintos |

**Veredicto A:** excelente como **UX de superficie**; insuficiente como **sistema de decisión de cartera** (que es lo que Bolsa V1 ya aspiró a ser en RFC-008).

---

### B) El modelo nuestro propuesto en este brief (Estudio → Dictamen → Aviso/Alarma → Acción)

```text
0 Estudio (universo)
1 Datos + estrategia viva (TOP / tracker / CORE-R)
2 Dictamen EOD (stance + ★)
3 Mapa → AVISO | ALARMA
4 Acción según modo (MANUAL / SEMI Confirm / AUTO)
5 Gate + mandato + sizing (gobierno transversal)
```

Es **más de 3 pasos**. Internamente se parece a RFC-008 (Evidence → Recommendation → Gate → Execution), con un artefacto nuevo de producto (dictamen) y taxonomía AVISO/ALARMA.

**Pros de nuestro pipeline**

| Pro | Por qué importa |
|-----|-----------------|
| Opinión legible | Usuario ve “Comprar ★4”, no “condición #47” |
| Unifica Lab y libro | TOP/mandato alimentan el mismo valor en Estudio |
| SEMI natural | Alarma → Confirm encaja con Camino C ya construido |
| Auditable | `InstrumentDailyOpinion` + Gate snapshot |
| Long-only / riesgo de producto | Gobierno explícito, no “el script hizo short” |
| Métrica de acierto posible | Dictamen del día T vs resultado T+N |
| Diferenciación real vs TV/PRT | Ellos no tienen este objeto |

**Contras de nuestro pipeline**

| Contra | Riesgo |
|--------|--------|
| **Complejidad cognitiva** | 6 capas en docs vs 3 en la cabeza del usuario |
| **Sobre-ingeniería pre-uso** | Dictamen + job EOD + mapa canales antes de validar SEMI diario |
| **Dos estrellas** | ★ Estrategia vs ★ Dictamen puede confundir si la UI no es brutalmente clara |
| **AVISO vs ALARMA** como producto | Puede ser un paso de más si bastaba “severidad” en una sola bandeja |
| **Retraso EOD** | Pierde setups intradía que TV/ToS capturan (mitigable con Radar, pero son 2 ritmos) |
| **Coste de mantenimiento** | Job, idempotencia, frescor de vela, falsos positivos |
| **Solapa con lo existente** | IO, F3 Recommendation, tracker inbox, ExecutionPolicy — riesgo de 4 “verdades” |
| **AUTO tarda más** | Bien por freeze; mal si esperábamos atajos |

**Veredicto B:** correcto como **arquitectura interna a medio plazo**; peligroso si lo **exponemos entero** en UI antes de probar el bucle SEMI.

---

### C) Lo que ya tenemos construido (sin el dictamen nuevo)

```text
Lab/TOP ★  →  (Adopt / Tracker / Propose)
Estudio + IO ranking  →  Operativa
Radar hit / Finalista  →  Inbox  →  SEMI Confirm (Camino C)  →  Fill + Mandato
```

| Pro | Contra |
|-----|--------|
| Ya funciona SEMI | No hay “Comprar” estable post-cierre por valor |
| Caminos A≠B≠C≠D claros | Usuario no percibe un ritual diario simple |
| Gate + long-only defaults | IO ≠ opinión de trading |
| Freeze protege de AUTO precipitado | Varias bandejas (inbox Radar, F3, signal alerts) |

**Veredicto C:** base sólida; le falta el **paso 2 de producto** (opinión) que el mercado resuelve con “alerta” y nosotros queremos resolver mejor.

---

### D) Tres opciones de diseño (elige antes de código)

| Opción | Modelo | Pasos que ve el usuario | Pros | Contras | Cuándo |
|--------|--------|-------------------------|------|---------|--------|
| **O1 — Copiar mercado** | Vigilar → Alertar → Actuar | 3 | Rápido, familiar | Pierde diferenciación; no usa Gate/Lab bien | Si priorizamos velocidad UX |
| **O2 — Pipeline brief completo** | Estudio→Dictamen→AVISO/ALARMA→Acción→Gate | 4–5 visibles | Máxima auditoría y potencia | Riesgo de producto denso / lento | Si priorizamos compliance-like |
| **O3 — Híbrido (recomendada para seguir pensando)** | **UI en 3 pasos**; motor rico debajo | **3** | Familiar + potente | Hay que disciplinar el mapeo | Mejor equilibrio |

#### O3 en detalle — UI de 3 pasos, motor RFC debajo

```text
UI (lo que el usuario aprende):
  1. VIGILAR     = Estudio (+ estrategias vivas en segundo plano)
  2. OPINAR      = Dictamen del día (stance + ★)  ← aquí “mejoramos el mercado”
  3. ACTUAR      = según modo: ver / Confirm / (futuro) AUTO

Motor (invisible o en “detalle”):
  TOP ★ · IO · Gate · mandato · Radar M · mapa severidad (aviso|alarma) · canales
```

| | O3 Pros | O3 Contras |
|-|---------|------------|
| | Misma frase que TV/PRT (“3 pasos”) | Hay que resistir meter AVISO/ALARMA como 4º paso de UI |
| | Dictamen sustituye a “alerta cruda” como centro del paso 2 | Sigue haciendo falta el artefacto EOD (no es gratis) |
| | AVISO/ALARMA = **atributo/canal** del dictamen, no capa mental nueva | Disciplina de producto: no reinventar 4 inboxes |
| | SEMI = paso 3 con humano | No resuelve solo la fatiga: hacen falta umbrales ★ |
| | Respeta RFC-008 sin enseñar el RFC al usuario | Requiere copy impecable en Operativa |

**Mapa O3 ↔ mercado**

| Paso mercado | Paso O3 Bolsa | Mejora |
|--------------|---------------|--------|
| 1 Watch/Scan | 1 Estudio | Membresía + Lab TOP ligado |
| 2 Alert (condición) | 2 Opinión (stance+★) | Semántica + auditoría |
| 3 Trade | 3 Actuar (modo libro) | Gate + SEMI Confirm + long-only |

**Mapa O3 ↔ AVISO/ALARMA**

No son el paso 2. Son el **enrutado** del paso 2→3:

- Opinión débil / informativa → **aviso** (paso 3 = “solo enterarte”)
- Opinión fuerte / accionable → **alarma** (paso 3 = Confirm o AUTO)

---

### E) Tensiones que hay que decidir (aún sin código)

1. **¿El ritual es EOD o continuo?**  
   - Mercado: continuo.  
   - Brief: EOD como fuente de verdad del dictamen.  
   - Híbrido sano: **dictamen EOD = opinión oficial**; Radar = avisos de momento (etiqueta M), sin sustituir el dictamen.

2. **¿Cuántas “verdades” por valor?**  
   Riesgo actual: IO + F3 recommendation + tracker hit + (nuevo) dictamen.  
   Regla O3: **dictamen es la verdad de producto del día**; lo demás es evidencia o momento.

3. **¿Merece la pena el artefacto nuevo antes de medir SEMI?**  
   Contra: quizás basta mejorar copy de Operativa con stance derivado on-demand (sin job).  
   A favor: sin persistir no hay métrica de acierto ni alarmas idempotentes.

4. **¿AVISO/ALARMA como producto o como severidad?**  
   Recomendación de esta pausa: **severidad + bandejas filtrables**, no dos apps mentales. El panel “Alarmas” configura el mapa; el usuario vive “Opiniones de hoy” + filtros.

---

### F) Conclusión de esta sub-pausa (no es aún ratificación de D1)

| Pregunta | Respuesta provisional |
|----------|----------------------|
| ¿El 3 pasos del mercado es malo? | No — es el mejor **modelo mental**. |
| ¿Nuestro pipeline largo es malo? | No — es el mejor **motor**. |
| ¿Qué no hacer? | Exponer 6 capas al usuario el día 1. |
| ¿Qué sí plantear? | **O3 híbrido**: UI 3 pasos (Vigilar → Opinar → Actuar); dictamen como centro del paso 2; AVISO/ALARMA como enrutado; SEMI como paso 3. |
| ¿Código ahora? | **No.** Falta elegir O1 / O2 / O3 (o variante) y responder §2.4.E. |

---

## 3. Capas y responsabilidades (reparto claro)

```text
┌─────────────────────────────────────────────────────────────────┐
│ L0  UNIVERSO          Estudio (membership) + TF cartera (1d)    │
├─────────────────────────────────────────────────────────────────┤
│ L1  DATOS             Sync OHLCV cierre · FA/Composite frescos  │
├─────────────────────────────────────────────────────────────────┤
│ L2  ESTRATEGIA VIVA   InstrumentStrategyTop + Trackers + CORE-R │
│                       (calidad Lab ★ — no es aún la opinión)    │
├─────────────────────────────────────────────────────────────────┤
│ L3  DICTAMEN EOD      InstrumentDailyOpinion (nuevo artefacto)  │
│                       stance + stars + reasons + IO + gate snap │
├─────────────────────────────────────────────────────────────────┤
│ L4  CANALES           Mapa Opinión → AVISO | ALARMA → toast/    │
│                       inbox/email/(SMS futuro)                  │
├─────────────────────────────────────────────────────────────────┤
│ L5  ACCIÓN            MANUAL: solo L4                           │
│                       SEMI: Alarma → cola F3 Confirm (Camino C) │
│                       AUTO: Alarma → execute (Camino D · freeze)│
├─────────────────────────────────────────────────────────────────┤
│ L6  GOBIERNO          TradingPolicy Gate · Mandate · PositionPol│
│                       · sizing/maxOpen · long-only              │
└─────────────────────────────────────────────────────────────────┘
```

### Qué NO mezclar

| Concepto | Es | No es |
|----------|----|-------|
| **IO / Recomendación (hoy)** | Ranking relativo en Estudio | Dictamen Comprar/Vender |
| **TOP ★** | Calidad de estrategia Lab | Opinión de trading del día |
| **Hybrid tracker rating** | Gatillo de scan Radar | Dictamen de cartera |
| **DecisionPackage action** | Motor cognitivo (long/short/wait…) | UI de producto (puede mapearse) |
| **ExecutionPolicy inform/alert/paper_auto** | Kernel Radar (ADR-010) | Modo libro MANUAL/SEMI/AUTO |
| **AVISO / ALARMA** | Producto de notificación | Sustituto del Gate |

---

## 4. Artefacto central — `InstrumentDailyOpinion` (propuesta)

Persistir **un dictamen por (instrumentId × accountId × asOfDate × timeframe)** tras el cierre.

### 4.1 Stance (opinión de producto — long-only)

| Stance | Significado para el usuario | Acción típica SEMI |
|--------|-----------------------------|--------------------|
| `buy` | Comprar / abrir o aumentar largo | Proponer Confirm compra |
| `hold_watch` | Mantener vigilancia; sin urgencia | Solo AVISO opcional |
| `overbought` / `stretched` | Sobrecomprado / extendido — no perseguir | AVISO; no compra |
| `reduce` | Reducir exposición (parcial) | Proponer reduce |
| `sell` / `exit` | Salir del largo | Proponer venta/cierre |
| `no_trade` | Sin setup / datos insuficientes / Gate veto | Silencio o AVISO soft |
| `review_strategy` | Estrategia degradada — revisar Lab/TOP | AVISO → link Coach/Lab |

> Nombres UI en español: Comprar · Vigilar · Sobrecomprado · Reducir · Vender · Sin operar · Revisar estrategia.

**Fuera de fase:** `short` / `cover` — no en enum de producto hasta reabrir cortos.

### 4.2 Calidad ★ (1–5)

Separar dos estrellas (evitar confusión):

| Estrella | Mide | Fuente |
|----------|------|--------|
| **★ Estrategia** | Calidad del TOP/evidencia Lab | `InstrumentStrategyTop.slots[].stars` |
| **★ Dictamen** | Confianza del stance de hoy | Composite IO + freshness + Gate PASS + alineación tracker/TOP + (opcional) narrativa fresca |

UI: mostrar ambas; la que “detona” alarmas de compra es **★ Dictamen** con umbral configurable.

### 4.3 Campos mínimos del artefacto

- `stance`, `dictamenStars` (1–5), `strategyStars` (nullable)
- `io`, `fa`, `ta`, `distress`
- `reasons[]` (códigos estables + texto corto)
- `gateSnapshot` (PASS/VETO + rules)
- `topId` / `topVersion` / `mandateTenureId` (si hay)
- `narrativeId` (si hay nota fresca)
- `asOfBarDate`, `computedAt`, `engineVersion`
- `source`: `eod_batch` | `manual_refresh` | `on_demand`

Regla: **regenerable**. El dictamen no es verdad eterna; se versiona por día.

---

## 5. AVISOS vs ALARMAS

### 5.1 Definiciones

| Nivel | Definición | Ejemplo |
|-------|------------|---------|
| **AVISO** | Información / atención. **No** encola Confirm ni execute. | «IBE Sobrecomprado ★3» · «TOP degradado — revisar» |
| **ALARMA** | Evento **accionable** según modo de cartera. | «SAN Comprar ★4» → SEMI Confirm · AUTO (futuro) fill |

### 5.2 Mapa configuración (producto — panel Alarmas)

Tabla de reglas (editable por cuenta):

| Stance | ★ mín. | → Nivel | Canales | En SEMI |
|--------|--------|---------|---------|---------|
| `buy` | ≥4 | ALARMA | inbox + toast + email | Encolar Confirm compra |
| `buy` | 2–3 | AVISO | inbox | No |
| `sell` / `exit` | ≥3 | ALARMA | inbox + toast + email | Encolar Confirm venta |
| `overbought` | cualquier | AVISO | inbox | No |
| `review_strategy` | — | AVISO | inbox + email | No |
| `hold_watch` / `no_trade` | — | (silencio) | — | No |

SMS: **fase 2** (hoy solo toast / inbox / email / webhook vía signal-alerts). No bloquear el diseño por SMS.

### 5.3 Relación con sistemas actuales

| Sistema actual | Rol tras el diseño |
|----------------|--------------------|
| Radar inbox (tracker hits) | Sigue siendo fuente **M** (momento); puede **proponer** facts al dictamen o generar Alarma paralela con etiqueta H≠M |
| Signal alerts | Canal técnico; no sustituye dictamen EOD |
| Price alerts | Legacy; no mezclar con dictamen |
| ExecutionPolicy | Kernel Radar; mapear `inform_only`→AVISO, `alert`→ALARMA blanda, `paper_auto`→solo cuando AUTO descongelado |

---

## 6. Bucle diario (secuencia)

```text
1. Sync / asegurar vela 1d consolidada (universo Estudio)
2. Refresh scores FA/Composite (batch)
3. Strategy health (TOP presente? stale? CORE-R hint?) — no corona trade
4. Por cada instrumentId ∈ Estudio:
     DecisionRuntime (opcional) → Gate → map a stance long-only
     + IO + ★ Dictamen + reasons
     Upsert InstrumentDailyOpinion(asOf)
5. Aplicar mapa Opinión→AVISO/ALARMA → emitir eventos
6. Si SEMI && ALARMA && gates libro: proponer F3 (sin execute)
7. UI: Operativa + Instrumentos (Recom./stance) + inbox Alarmas/Avisos
8. (Futuro AUTO) Si AUTO && ALARMA && Gate PASS: Camino D
```

**Idempotencia:** re-ejecutar el batch del mismo `asOfDate` actualiza el dictamen (version++) y no duplica alarmas si fingerprint idéntico.

**Horario:** configurable por mercado (p. ej. post-cierre EU); no depende de tener la UI abierta → implica job servidor (distinto de `CORE_R_CRON` freeze: este job es **nuevo** y debe nombrarse `ESTUDIO_EOD_OPINION` con flag off-by-default hasta slice 1).

---

## 7. Estrategias siempre actualizadas (Estudio)

Problema: TOP/Finalistas viven en Lab; Estudio puede quedar con estrategia obsoleta.

### Política propuesta

| Regla | Comportamiento |
|-------|----------------|
| R1 | Entrar a Estudio **exige** TOP semifinal/active o dispara AVISO `review_strategy` |
| R2 | Caducidad: si TOP `updatedAt` > N días o CORE-R dice `consider_replace` → AVISO + bajar ★ Dictamen |
| R3 | Lista AUTO / embudo Coach **siguen siendo dueños** de regenerar TOP (no Belief auto) |
| R4 | Tracker Finalista#1 = seguimiento **intradía/on_bar_close**; el dictamen EOD **consolida** ese seguimiento |
| R5 | Evolución temporal: historial de TOP versions + historial de dictámenes (gráfica «calidad en el tiempo») — fase UI |

Freeze: no activar `CORE_R_CRON` solo por esto; el batch EOD puede **leer** estado CORE-R ya calculado en cliente/BD sin cron nuevo, o encolar refresh Lab explícito como AVISO.

---

## 8. UI — dónde se ve

| Superficie | Qué muestra |
|------------|-------------|
| **Operativa → Recomendación** | Stance del día + ★ Dictamen + rank IO (complementarios) |
| **Instrumentos hub** | Columna Recom. evoluciona: IO **y/o** stance corto (`C ★4`) |
| **Detalle / Evolución** | Narrativa humana + último dictamen + reasons |
| **Panel Alarmas** | Pestañas **Alarmas \| Avisos** + configuración mapa stance→canal |
| **Confirm F3** | Alarma origen = dictamen EOD (etiqueta) vs Radar M vs Finalista H |

---

## 9. Relación con freeze y modos

| Modo | Con dictamen EOD |
|------|------------------|
| **MANUAL** | Calcula dictamen + AVISOS/ALARMAS informativas; **no** Confirm |
| **SEMI** | ALARMA → Confirm (Camino C) — **slice productivo inmediato** |
| **AUTO** | ALARMA → execute — **solo tras thaw Camino D** + métricas de acierto |

No abrir AUTO hasta tener:

1. Dictámenes EOD estables ≥ X sesiones  
2. Mapa AVISO/ALARMA usable  
3. Tasa de falsas Alarmas medible  
4. Gate + long-only + maxOpen sin regresiones  
5. Decisión explícita de thaw en freeze doc

---

## 10. Fases de entrega (propuesta — sin código aún)

| Fase | Entrega | Depende de |
|------|---------|------------|
| **D0** | Este brief ratificado + enum stance + long-only escrito | — |
| **D1** | Artefacto BD + API opinion EOD + job flag-off + cálculo mínimo (IO+Gate→stance) | D0 |
| **D2** | UI Operativa/Instrumentos muestran stance+★ | D1 |
| **D3** | Taxonomía AVISO/ALARMA + panel config + inbox dual | D1 |
| **D4** | SEMI: Alarma `buy`/`sell` → propose F3 con origen `eod_opinion` | D3 + SEMI actual |
| **D5** | Strategy health en Estudio (AVISO review_strategy + links Lab) | D2 |
| **D6** | Métricas acierto (dictamen vs resultado N días) | D4 |
| **D7** | Thaw AUTO / Camino D (separado) | D6 + freeze amend |

**Fuera de D0–D5:** SMS, cortos, Belief, Strategy Studio, unificar caminos A/B/C/D.

---

## 11. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Confundir IO con Comprar | UI: IO = ranking; stance = opinión |
| Alert fatigue | Umbrales ★ + silencio `hold`/`no_trade` |
| Job EOD con velas no consolidadas | Gate de frescor `lastBarDate == asOf` |
| AUTO prematuro | Freeze + fase D7 explícita |
| LLM soberbio | Dictamen rules+scores primero; IA solo redacta reasons/narrativa bajo Gate |

---

## 12. Criterios de ratificación (checklist)

Antes de escribir código de D1, confirmar contigo:

1. ¿Stance set §4.1 OK (sin cortos)?  
2. ¿★ Dictamen separada de ★ Estrategia OK?  
3. ¿AVISO vs ALARMA + tabla §5.2 como default OK?  
4. ¿Job post-cierre 1d con flag off-by-default OK?  
5. ¿SEMI (D4) es el primer “productivo”, AUTO después OK?  
6. ¿Panel Alarmas es el dueño del mapa opinión→canales OK?

---

## 13. Enlaces de estado actual (as-is)

- Estudio + IO: `operativa-index.ts` · `visualization-store.ts` · hub Instrumentos I5  
- SEMI Confirm: `demo-book-prefs.ts` · `supervised-f3-*` · `finalist-propose-supervised.ts`  
- Gate long-only: `trading-policy-templates.ts` · `apply-gate-to-decision.ts`  
- Radar alarms: `tracker-alarm-inbox-*` · ADR-010  
- Narrativa: `instrument_narratives` · `instruments-hub-narrative-2026-08-04.md`  
- Freeze: `post-audit-decision-freeze-2026-08-03.md`

---

*Fin del brief de pausa. Siguiente paso: ratificar §12; luego D1 sin tocar Camino D.*
