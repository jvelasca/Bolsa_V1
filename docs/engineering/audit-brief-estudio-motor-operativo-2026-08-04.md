# Brief de auditoría externa — Motor operativo Estudio → Opinión → Acción

> **AsOf:** 2026-08-04  
> **Estado:** Brief histórico de entrada round 3. **Decisión:** [triage](./audit-ext-round3-triage-estudio-motor-2026-08-04.md) · [ADR-022](../adr/022-estudio-daily-opinion-motor.md) (**O3-C ratificado**).  
> **Repo público:** https://github.com/jvelasca/Bolsa_V1  
> **Padre doc:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md)  
> **Diseño interno previo:** [estudio-daily-opinion-alarms-design-2026-08-04.md](./estudio-daily-opinion-alarms-design-2026-08-04.md)  
> **Freeze vigente:** [post-audit-decision-freeze-2026-08-03.md](./post-audit-decision-freeze-2026-08-03.md)  
> **Destinatarios:** las **3 auditorías externas** ya conocidas del round 2 — **A0** (arquitectura), **N4** (invariantes/mecánica), **Deep** (código/seguridad/rendimiento).  
> **Idioma de respuesta preferido:** español (o bilingüe con resumen ES).

---

## 0. Por qué existe este documento

El producto ha llegado al punto **más crítico** de su vida útil: pasar de “herramientas Lab + SEMI Confirm” a un **motor operativo diario** que diga, para cada valor en **Estudio**, qué hacer (Comprar / Vigilar / Vender…) y dispare avisos o acciones.

El equipo está **con dudas serias** sobre:

1. Si copiar el **modelo mental de 3 pasos** del mercado (Vigilar → Avisar → Actuar).  
2. Si imponer el **pipeline rico** ya esbozado (Estudio → Dictamen → AVISO/ALARMA → Acción → Gate).  
3. O un **híbrido** (UI 3 pasos, motor RFC-008 debajo).

**No vamos a implementar** hasta que A0 / N4 / Deep contrasten mercado + nuestro stack + riesgos y nos den un **veredicto priorizado** (con disensos explícitos si los hay).

### 0.1 Stack real (leer antes de proponer paths)

| Capa | Tecnología real |
|------|-----------------|
| API | **FastAPI** · `apps/api-python` |
| Dominio / Lab / mercado | `packages/py/{application,analytics,market,infrastructure,…}` |
| Web | **React + Vite** · `apps/web` |
| Contratos | `packages/shared` |
| BD | PostgreSQL · Prisma migrations + SQLAlchemy |

**No existen** en este repo: tRPC, Next.js, Drizzle, `packages/engine`, `packages/core`, `packages/market-data`, Alpaca por defecto.  
Si Deep vuelve a citar ese stack, marcar como **N/A** (ver [audit-ext-round2-triage](./audit-ext-round2-triage-2026-08-03.md)).

### 0.2 Freeze que **no** se pide reabrir en esta ronda

| Tema | Estado |
|------|--------|
| Belief → Coach (CORE-A auto-tune) | Congelado |
| `CORE_R_CRON_ENABLED` | `false` |
| `COST_MODEL_V2_ENABLED` | `false` |
| Camino D / AUTO execute / `PAPER_D_EXECUTE` | Congelado (sí queremos **diseño** de cuándo thaw) |
| Strategy Studio / F5 / Fase H (OTel, DuckDB, microservicios) | Fuera |
| Gate C4 / Bollinger “porque faltan” | Cerrado |

Podéis **recomendar condiciones de thaw** de AUTO; no pedir “implementad Camino D ya” como bloqueante.

---

## 1. Misión por auditoría (encargos explícitos)

### 1.1 A0 — Arquitectura global / producto-sistema

**Encargo:** iluminar el **modelo operativo** y la forma del motor.

1. Contrastar el **3 pasos de mercado** vs nuestro pipeline vs híbrido O3 (§5–§6).  
2. Proponer **límites de complejidad documental** (evitar segunda arquitectura).  
3. Decidir qué es **objeto de dominio de primera clase** (`InstrumentDailyOpinion` sí/no/aplazar).  
4. Mapear bounded contexts: ¿dónde vive el dictamen? ¿Trading? ¿Decision Engine? ¿Alerting?  
5. Relación con **RFC-008** (Assessment → Recommendation → Gate → Execution): ¿el dictamen es proyección UI o artefacto nuevo?  
6. Entregar: **opción recomendada O1/O2/O3** (+ variante si hace falta) y **top 5 riesgos arquitectónicos**.

**No pedir:** microservicios, event-bus Redis Pub/Sub obligatorio, reescritura ADR masiva.

### 1.2 N4 — Invariantes / mecánica / datos / operativa

**Encargo:** iluminar el **motor** (cuándo corre, con qué datos, qué es verdad).

1. Diseñar invariantes del **batch EOD 1d** (vela consolidada, idempotencia, fingerprint de alarma).  
2. Definir **única verdad del día** por valor: ¿dictamen > IO > F3 recommendation > tracker hit? Orden de precedencia.  
3. Long-only: cómo se expresa en Gate + producto sin ambigüedad.  
4. Relación Radar (`on_bar_close`) vs dictamen EOD (dos ritmos sin doble verdad).  
5. Estrategia viva en Estudio: TOP caducidad, CORE-R (sin exigir cron on).  
6. Métricas de acierto mínimas antes de thaw AUTO.  
7. Entregar: **máquina de estados** del valor en Estudio + checklist de invariantes testables.

**No pedir:** Kendall Tau ceremonial, “Quarantine Vault” unificado Yahoo+FA, `SELECT FOR UPDATE` de novela sin citar código.

### 1.3 Deep — Código / seguridad / rendimiento / superficie de ataque

**Encargo:** iluminar **implementabilidad y riesgos** del motor en *este* monorepo.

1. Estimar superficie: tablas nuevas, jobs, APIs, colas, canales email.  
2. Seguridad: inyección en reglas de alarma, abuso de email, secretos SMS futuro, auth en job EOD.  
3. Rendimiento: Estudio de N=20–50 vs N=200; batch FA/Composite; no bloquear API.  
4. Fallos Yahoo / vela no consolidada: fail-closed vs fail-open del dictamen.  
5. Separación LAB vs TRADING (ADR-019) en el job: ¿el dictamen escribe solo universo TRADING/DEMO?  
6. Entregar: **amenazas top 10** + **slice D1 mínimo seguro** (si se elige construir) + lo que **no** tocar.

**Obligatorio:** anclar paths al árbol real FastAPI/Vite. Si no encontráis el archivo, decir “no localizado”, no inventar `packages/engine`.

---

## 2. Contexto de producto (para quien no ha seguido el chat)

### 2.1 Qué es Bolsa V1

Plataforma personal de gestión bursátil (inspiración ProRealTime / XTB): **Lab científico** (backtests, Coach, Finalistas, CORE-R) + **Trading DEMO** (listas, gráficos, Operativa, SEMI Confirm F3, mandatos).

Universos (ADR-019): **LAB** ≠ **TRADING**. El libro operativo es la cuenta **DEMO** activa (`simulated`). `paper` = tipo futuro broker, no “paper trading” genérico.

### 2.2 Qué ya funciona (as-is)

| Pieza | Rol | Puntero |
|-------|-----|---------|
| **Estudio** | Lista virtual de membresía explícita | `visualization-store` · `__builtin:visualization__` |
| **IO / Recomendación** | Ranking Composite + distress FA en Operativa | `operativa-index.ts` |
| **Instrumentos hub** | Catálogo + filtros Estudio/Cartera/listas + columna Recom. + narrativa | hub I5 |
| **Demo book** | MANUAL / SEMI / AUTO(grey) | `demo-book-prefs` |
| **SEMI** | Finalistas + Radar → cola Confirm F3 → fill DEMO + tenure | Camino C |
| **Gate / TradingPolicy** | Hard permission; long-only en plantillas conservative/moderate | RFC-008 · `allowShorting: false` |
| **TOP ★** | Calidad estrategia Lab por instrumento | `InstrumentStrategyTop` |
| **Radar inbox** | Hits tracker → aviso / SEMI | ADR-010 |
| **Narrativa** | Nota ≤20 líneas por alcance | `instrument_narratives` |

### 2.3 Qué **no** existe aún (gap del motor)

- Dictamen diario persistido (stance Comprar/Vender/…).  
- Taxonomía producto **AVISO vs ALARMA**.  
- Job EOD Estudio → opinión → canales.  
- AUTO productivo (Camino D congelado).  
- SMS.  
- Una sola bandeja unificada “opiniones de hoy”.

### 2.4 Premisa long-only (fase actual)

Documentada en el diseño interno: **no cortos**.  
“Vender/Reducir” = cerrar o aligerar **largos**.  
`recommend_short` fuera de alcance de producto Estudio hasta mandato explícito.

---

## 3. Estrategia que el equipo *cree* (hipótesis, no ratificada)

### 3.1 Tesis

Las apps top separan **condición técnica**, **alerta** y **ejecución**.  
Bolsa V1 quiere una **opinión diaria auditable por valor de Estudio** que alimente UI + notificaciones + SEMI/AUTO, con estrategias Lab vivas y gobierno (Gate, mandato, maxOpen, long-only).

### 3.2 Capas internas propuestas (motor)

```text
L0 Estudio (universo)
L1 Datos cierre 1d + scores
L2 Estrategia viva (TOP / tracker / CORE-R hint)
L3 Dictamen EOD (stance + ★ dictamen)
L4 Enrutado AVISO | ALARMA → canales
L5 Acción MANUAL / SEMI Confirm / AUTO
L6 Gobierno Gate + mandato + sizing
```

### 3.3 Stance propuesto (UI)

`buy` · `hold_watch` · `overbought` · `reduce` · `sell/exit` · `no_trade` · `review_strategy`  
(+ ★ Dictamen 1–5 distinta de ★ Estrategia TOP)

### 3.4 Fases tentativas (D0…D7)

Ver diseño interno §10. Resumen: D0 ratificar → D1 artefacto/job flag-off → D2 UI → D3 avisos/alarmas → D4 SEMI → D5 strategy health → D6 métricas → D7 thaw AUTO.

**El equipo duda si D1 es prematuro.**

---

## 4. Comparativa de mercado (base; pedimos ampliación)

Referencias: TradingView, thinkorswim, ProRealTime, Stock Alarm Pro, Bloomberg.

| Capacidad | Mercado típico | Hipótesis Bolsa |
|-----------|----------------|-----------------|
| Universo | Watchlist / screener | Estudio membresía |
| Señal | Condición (Pine/RSI/precio) | Dictamen semántico |
| Aviso | Alert flood | AVISO vs ALARMA |
| Acción | Manual o ProOrder/broker | Modo libro + Gate |
| Estrategia | Script suelto | TOP + mandato |
| Auditoría | Débil retail | Opinion versionada |

**Encargo a las 3 auditorías:** ampliar/corregir esta tabla con **al menos 2 referencias adicionales** que consideréis mejores para *daily portfolio opinion + alerts + supervised automation* (pueden ser apps EU, brokers, o sistemas tipo “trade journal + rules”). Indicar fuentes.

Tabla extendida ya en [diseño §2](./estudio-daily-opinion-alarms-design-2026-08-04.md).

---

## 5. Operativa de 3 pasos (mercado) — pros / contras

```text
1 VIGILAR → 2 AVISAR → 3 ACTUAR
```

### Pros
- Modelo mental universal.  
- Bajo acoplamiento alerta/broker.  
- Incremental.  
- Familiar para usuarios de TV/PRT.

### Contras
- Paso 2 = condición, no opinión de cartera.  
- Screener ≠ autotrade (PRT).  
- Sin Gate/mandato/maxOpen.  
- Fatiga de alertas.  
- Poca auditoría “por qué compramos”.  
- Lab científico desconectado del trade.

**Pregunta a A0/N4:** ¿este modelo debe ser la **única** cara al usuario aunque el motor sea más rico?

---

## 6. Nuestras opciones de diseño (O1 / O2 / O3)

| Opción | Resumen | Pros | Contras |
|--------|---------|------|---------|
| **O1 Copiar mercado** | Vigilar→Alertar→Actuar | Rápido, familiar | Pierde diferenciación; subutiliza Lab/Gate |
| **O2 Pipeline completo en UI** | Estudio→Dictamen→AVISO/ALARMA→Acción | Máxima potencia/auditoría | Complejidad cognitiva alta |
| **O3 Híbrido** | **UI 3 pasos**; motor rico debajo | Familiar + potente | Requiere disciplina de producto |

### O3 (candidato interno provisional)

```text
UI:  1 Vigilar=Estudio  →  2 Opinar=Dictamen  →  3 Actuar=modo libro
Motor: TOP · IO · Gate · Radar M · severidad aviso|alarma · canales
```

AVISO/ALARMA = **enrutado** del paso 2→3, no un 4º paso mental.

**Pregunta central a las 3 auditorías:** ¿Ratificáis O3, preferís O1/O2, o proponéis **O4**? Justificad con riesgos y esfuerzo.

Análisis extenso: diseño interno §2.4.

---

## 7. Tensiones abiertas (dudas del equipo)

Cada ítem pide **voto A0 / N4 / Deep** + comentario.

| ID | Duda | Opciones típicas |
|----|------|------------------|
| **T1** | ¿Modelo UI? | O1 / O2 / O3 / O4(…) |
| **T2** | ¿`InstrumentDailyOpinion` persistido desde D1? | Sí ya / Solo on-demand UI primero / No |
| **T3** | ¿Ritual EOD 1d como verdad oficial? | Sí / Continuo como TV / Híbrido EOD+Radar |
| **T4** | ¿AVISO vs ALARMA producto o severidad? | Dos conceptos UI / Una bandeja + filtro / Solo “alerta” |
| **T5** | ¿IO vs Dictamen? | Dictamen sustituye IO / Conviven / IO muere |
| **T6** | ¿Una verdad ante H≠M (Finalista vs Radar vs Dictamen)? | Precedencia fija / Confirm siempre elige / Dictamen gana EOD |
| **T7** | ¿Long-only forever en Estudio o flag de política? | Forever fase 1 / Flag TradingPolicy only |
| **T8** | ¿Job servidor `ESTUDIO_EOD_OPINION` flag-off? | Sí D1 / Solo cuando UI abierta / Cron distinto de CORE-R |
| **T9** | ¿Cuándo thaw AUTO? | Tras D6 métricas / Nunca en DEMO / Criterios vuestros |
| **T10** | ¿SMS en roadmap? | Fase 2 / No / Sustituir por push web |
| **T11** | ¿★ Dictamen ≠ ★ Estrategia? | Sí separar / Una sola ★ / Estrellas solo Lab |
| **T12** | ¿Riesgo de 4 verdades (IO, F3, tracker, dictamen)? | Cómo consolidar sin big-bang |

---

## 8. Motor — preguntas técnicas específicas (N4 + Deep + A0)

### 8.1 Contrato del dictamen

¿Campos mínimos correctos?

- `stance`, `dictamenStars`, `strategyStars?`  
- `io`, `fa`, `ta`, `distress`  
- `reasons[]` códigos estables  
- `gateSnapshot`  
- `topId`/`version`, `mandateTenureId?`, `narrativeId?`  
- `asOfBarDate`, `computedAt`, `engineVersion`  
- `source`: eod_batch | manual | on_demand  

¿Falta `accountId`? ¿Universe scope? ¿Idempotency key?

### 8.2 Algoritmo de stance (v0)

Hoy no hay especificación formal. Hipótesis débil:

```text
si Gate VETO → no_trade
si sin TOP / TOP stale → review_strategy (o bajar ★)
si distress FA → techo ★ y/o overbought/no_trade según reglas
si recommend_long + ★ alta → buy
si posición abierta + recommend reduce/exit → reduce/sell
else hold_watch / no_trade
```

**Pedimos:** pseudocódigo v0 **conservador** (falsos positivos de compra peores que falsos negativos) y tests de invariante.

### 8.3 Job EOD

- ¿Trigger? (cron EU close / manual / hook tras sync)  
- ¿Qué pasa si `lastBarDate < asOf`?  
- ¿Recompute intraday permitido?  
- ¿Dónde vive? (`apps/api-python` worker vs script `packages/py`)  

### 8.4 Canales y seguridad

- Reutilizar signal-alerts email vs tabla nueva  
- Rate limit por cuenta  
- No filtrar PII en logs de opinión  
- SMS: ¿Twilio futuro o aparcar?

### 8.5 LAB vs TRADING

¿El dictamen es **solo TRADING/DEMO**?  
¿Lab puede generar “opiniones” de research sin alarmas de cartera?

---

## 9. Relación con caminos A/B/C/D (no unificar)

| Camino | Hoy | Rol respecto al motor |
|--------|-----|------------------------|
| A Checklist | Lab → paper checklist | No es el ritual Estudio diario |
| B Radar paper_auto | Tracker + ExecutionPolicy | Momento M; no dictamen EOD |
| C Confirm F3 | SEMI productivo | **Consumidor** natural de Alarmas |
| D AUTO execute | Freeze | Thaw solo con métricas |

**Pregunta A0:** ¿el dictamen es una **fuente más** hacia C (como Finalista/Radar) o un **bus central** que los sustituye?

---

## 10. Criterios de éxito (propuesta; validar)

| Horizonte | Éxito |
|-----------|--------|
| 2 semanas post-D2 | Usuario entiende Vigilar→Opinar→Actuar sin leer RFC |
| 1 mes SEMI+D4 | ≥80% Alarmas `buy` pasan Gate; Confirm usable |
| Pre-AUTO | Métrica: precisión/recall proxy del stance vs outcome 5–20d |
| No-éxito | Segunda arquitectura documental; 4 inboxes; AUTO sin métrica |

---

## 11. Formato de respuesta pedido a cada auditoría

Usad esta plantilla (podéis anexar PDF/MD):

```text
# Informe — [A0|N4|Deep] — Motor Estudio 2026-08-04

## 0. Veredicto en 5 líneas
## 1. Opción O1/O2/O3/O4 recomendada (y por qué)
## 2. Votos T1–T12 (tabla)
## 3. Ampliación mercado (apps + hallazgos)
## 4. Riesgos top 5 (priorizados)
## 5. Invariantes / amenazas (N4 o Deep)
## 6. Slice D1 mínimo (si aplica) — paths reales del repo
## 7. Qué NO hacer
## 8. Condiciones para thaw AUTO (opcionales)
## 9. Disenso con las otras auditorías (si conocéis round 2)
```

**Longitud:** preferimos profundidad a marketing. Citad archivos reales del repo cuando afirméis “ya existe”.

---

## 12. Material de lectura obligatoria (orden)

1. **Este brief** (§0–§11).  
2. [estudio-daily-opinion-alarms-design-2026-08-04.md](./estudio-daily-opinion-alarms-design-2026-08-04.md) (§2 mercado, §2.4 tres pasos, §3–§12).  
3. [demo-operating-modes-brief-2026-08-03.md](./demo-operating-modes-brief-2026-08-03.md).  
4. [trading-operativa-panel-2026-08-04.md](./trading-operativa-panel-2026-08-04.md) + handoff Estudio.  
5. [post-audit-decision-freeze-2026-08-03.md](./post-audit-decision-freeze-2026-08-03.md).  
6. RFC-008 §1–§2 (pipeline decisión) — `docs/rfc/008-cognitive-decision-architecture.md`.  
7. ADR-010 (Radar/policies), ADR-019 (universos), ADR-020 (mandato).  
8. [audit-pack-post-audits-2026-08-03.md](./audit-pack-post-audits-2026-08-03.md) · [audit-ext-round2-triage](./audit-ext-round2-triage-2026-08-03.md) (errata stack).  
9. Código mínimo:  
   - `apps/web/src/features/trading/operativa-index.ts`  
   - `apps/web/src/features/trading/demo-book-prefs.ts`  
   - `apps/web/src/stores/visualization-store.ts`  
   - `packages/shared/src/cognitive/trading-policy-templates.ts`  
   - `packages/shared/src/execution-policies.ts`  

Tests offline útiles: `pnpm test:semi` · `pnpm test:operativa` (sin exigir stack up para el informe de diseño).

---

## 13. Mensaje directo a A0 · N4 · Deep

> Estamos **inseguros** en la decisión más importante del producto: el **motor** que convierte Estudio en opiniones diarias y acciones.  
> No necesitamos otra lista de features ni un rediseño de monorepo.  
> Necesitamos que, con el mercado en una mano y RFC-008 + SEMI en la otra, nos digáis:  
> **(1)** qué modelo operativo adoptar,  
> **(2)** qué artefacto merece existir el día 1,  
> **(3)** qué riesgos nos matan si nos precipitamos a AUTO,  
> **(4)** cómo evitar cuatro verdades y una UI incomprensible.  
> Disentid entre vosotras si hace falta: el disenso documentado nos ayuda más que el consenso vacío.

---

## 14. Qué hará el equipo tras vuestras respuestas

1. Triage unificado (como round 2) → un solo veredicto O*.  
2. Actualizar freeze / brief demo modes si cambia thaw AUTO.  
3. Solo entonces abrir **D1** (o un spike on-demand sin job).  
4. No merge de Camino D sin checklist §10/T9.

---

## 15. Anexos rápidos

### A. Glosario mínimo

| Término | Significado |
|---------|-------------|
| Estudio | Universo vigilado (membresía) |
| IO | Índice Operativo 0–100 (ranking) |
| Dictamen | Opinión de producto del día (propuesto) |
| AVISO | Notificación no accionable |
| ALARMA | Notificación accionable según modo |
| SEMI | Confirm humano (Camino C) |
| AUTO | Execute sin Confirm (Camino D, freeze) |
| TOP ★ | Calidad estrategia Lab |
| Gate | TradingPolicy hard allow/deny |

### B. Anti-objetivos

- No ser “otro TradingView con más alertas”.  
- No unificar caminos A/B/C/D en un solo auto.  
- No LLM que salte Gate.  
- No cortos silenciosos.  
- No segunda arquitectura documental sin padre en Engineering Index.

---

*Fin del brief para auditorías externas. Contacto de producto/eng: vía issues del repo o canal habitual del round 2.*
