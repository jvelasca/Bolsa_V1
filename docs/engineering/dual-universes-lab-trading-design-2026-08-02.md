# Diseño — Dos universos LAB vs TRADING (2026-08-02)

> **Fuente de verdad del to-be de producto.**  
> ADR: [019-dual-universes-lab-vs-trading.md](../adr/019-dual-universes-lab-vs-trading.md).  
> Complementa: [ADR-015](../adr/015-scientific-domain-vs-trading-domain.md), [backtesting-dia-d-premises](./backtesting-dia-d-premises-2026-07-31.md), [account-premises](./account-premises-demo-vs-paper-2026-07-31.md), [research-lifecycle](./research-lifecycle.md), [domain-language](../domain-language.md), [HELP](../HELP.md).

**AsOf decisión:** 2026-08-02 · **Estado implementación:** pendiente (as-is = híbrido DÍA D → Trading v0.11).

---

## 0. Resumen ejecutivo

Bolsa V1 pasa de un híbrido confuso («verificación histórica dentro de Trading») a **dos universos paralelos** claramente etiquetados:

1. **LAB (Backtesting)** — estudiar, simular, verificar, enseñar al sistema qué operativa conviene por instrumento.  
2. **TRADING** — invertir el día a día (DEMO ahora; Paper/Live después) usando lo que el Lab recomienda vía un **puente explícito**.

El fin último: **mismo instrumento, dos contextos** — mesa operativa + coach profundo en vivo — sin mezclar dinero ni narrativa.

---

## 1. Fin último (definición operativa)

```text
Para cada instrumento I:

  LAB(I)  = embudo + TOP + verificación DÍA D + CORE-R + Evidence
            → responde: «¿cuál es la operativa más conveniente *hoy* para I?»

  TRADING(I) = posiciones / órdenes / Checklist / Radar / Supervisado
            → responde: «¿qué hago *ahora* con I en mi cuenta DEMO/Paper?»

  Puente(I) = Adoptar | Vigilar | Proponer | Abrir estudio
            → LAB no escribe DEMO; TRADING no reescribe TOP
```

Éxito de producto = el usuario puede **operar I en Trading** y, sin abandonar la idea de I, **abrir el estudio** (Lab) o ver el **estado del coach** (rail) en paralelo.

---

## 2. Por qué dos carteras (el problema de fondo)

### 2.1 Síntoma

| Confusión | Causa |
|-----------|--------|
| «¿Estoy estudiando o invirtiendo?» | Misma chrome de gráfico + modos Manual/Semi/Auto en Trading |
| «¿Este PnL es mío?» | Sandbox DÍA D vive visualmente en la mesa DEMO |
| «Simular» vs «Operar» | Un CTA de research navegaba a `/trading` |
| Coach / Finalistas vs Desk | Sin chip de universo; una sola narrativa de cartera |

### 2.2 Diagnóstico

Una sola cartera operativa absorbiendo research **rompe** la metáfora mental. Las apps top no usan el ledger paper/live como motor de backtest; nosotros tampoco debemos usar DEMO como escenario D→hoy.

### 2.3 Decisión

| Entidad | Universo | Persistencia (to-be) | Mutación DEMO |
|---------|----------|----------------------|---------------|
| **Cartera LAB** | LAB | Sesiones / equity de simulación / archivo Evidence; opcional ledger virtual ligero | Nunca |
| **Cartera TRADING** | TRADING | `InvestmentAccount` activa (`simulated` hoy) | Solo caminos A/B/C/D y trades manuales |

**Día 1 de implementación (mínimo viable conceptual):**

- No hace falta crear `InvestmentAccount type=lab` si complica.  
- Basta: (a) sesión sandbox tipada `universe=lab`, (b) chip UI, (c) reglas duras de no escritura DEMO, (d) store distinto del active-account trading.

**Día 2+ (si aporta):** cuenta/ledger LAB explícito para historial de verificaciones multi-sesión y fiscalidad de laboratorio (opcional).

---

## 3. Cómo lo hacen las apps top (y cómo las mejoramos)

| Patrón de mercado | Ejemplos | Qué copiamos | Qué mejoramos (diferencial Bolsa) |
|-------------------|----------|--------------|-----------------------------------|
| Research ≠ Brokerage | QuantConnect, Portfolio123 | Sandbox de backtest ≠ cuenta live/paper | Coach + Finalistas + DÍA D en el mismo producto, no solo “deploy strategy” |
| Paper ≠ Backtest replay | Thinkorswim, IBKR | Reloj de mercado en paper; motor histórico aparte | Verificar D→hoy con Manual/Semi/Auto **dentro de LAB**, no disfrazado de desk |
| Strategy library ↔ symbol ↔ account | TradingView strategies + broker | Adoptar por instrumento | Estado de adopción + frescura CORE-R + Evidence Fase 2 |
| Coach paralelo (raro) | Pocos | — | **Rail Coach** en Trading por instrumento = estudio profundo en vivo |

Conclusión: no inventamos la separación research/trading; inventamos el **vínculo continuo y explícito** por instrumento (coach en vivo).

---

## 4. Arquitectura de universos

```text
┌──────────────────────────────────┐         puente          ┌──────────────────────────────────┐
│  UNIVERSO LAB (Backtesting)      │  Adoptar / Vigilar /    │  UNIVERSO TRADING                 │
│                                  │  Proponer / Abrir estudio│                                  │
│  • Cartera LAB (sandbox)         │ ───────────────────────►│  • Cartera TRADING (DEMO→Paper)  │
│  • Probar / Coach / Lab / TOP    │                         │  • Órdenes, posiciones, ledger   │
│  • Análisis técnico: Ver         │◄────────────────────────│  • Reloj de mercado (live)        │
│  • Análisis técnico: Verificar   │   Abrir estudio         │  • Rail Coach (compacto)         │
│    D→hoy (Manual/Semi/Auto)      │                         │  • Checklist / Radar / Supervisado│
│  • CORE-R / Monitor Finalistas   │                         │  • Sin película DÍA D             │
│  • Evidence sesión C             │                         │                                  │
│  • No escribe DEMO               │                         │  • No reescribe TOP / Lab params  │
└──────────────────────────────────┘                         └──────────────────────────────────┘
                    ▲                                                     │
                    │              mismo INSTRUMENTO                      │
                    └──────────── coach profundo en paralelo ─────────────┘
```

### 4.1 Chip de universo (UI global o de zona)

Siempre visible en contextos ambiguos:

- `LAB · simulación`  
- `TRADING · DEMO` (luego `· PAPER` / `· LIVE`)

Regla: si al quitar el chip el usuario no sabe en qué universo está, el diseño falla.

---

## 5. Mapa de objetos de producto

| Objeto | Universo | Definición | Persistencia (orientativa) |
|--------|----------|------------|----------------------------|
| **Instrumento** | Compartido | Ticker / id canónico | BD instrumentos |
| **Trial / BacktestRun** | LAB (Scientific) | Experimento H0 | `backtest_runs`, `research_trials` |
| **TOP / Finalista #1** | LAB | Estrategia recomendada vigente para I | Monitor + bindings |
| **Sesión Verificar (C)** | LAB | Replay D→hoy con #1 congelada | Store sesión + Evidence archive + Fase 2 |
| **Cartera LAB** | LAB | Equity/cash virtual de simulación | Cliente + opcional API |
| **Adopción** | Puente | Ligadura TOP → cuenta TRADING (proyección del mandato vigente) | `bolsa-strategy-adoption-v1` → sucesor tenures |
| **Mandato operativo** | TRADING (+ puente) | Playbook vigente + historial de tenures por I×cuenta | [ADR-020](../adr/020-operating-mandate-tenure.md) · M1+ |
| **Cuenta activa DEMO** | TRADING | Ledger operativo | `InvestmentAccount` |
| **Orden / Position** | TRADING | Ejecución | Ledger / orders |
| **Rail Coach snapshot** | Puente (vista) | Resumen TOP+frescura en desk | Lectura desde Monitor/TOP |

### 5.1 Estados de adopción (por instrumento × cuenta)

| Estado | Significado |
|--------|-------------|
| `none` | Sin TOP adoptado |
| `candidata` | Hay Finalista / TOP; aún no en DEMO |
| `adoptada` | Checklist / deploy activo en cuenta TRADING |
| `propuesta` | En Inbox Supervisado / propose |
| `obsoleta` | CORE-R / usuario marcó decaimiento; operar con cautela |

Transiciones solo por acciones de puente (nunca por play de película LAB).

**Evolución (ADR-020 · hecho M1–M3 cliente):** la adopción es la **vista vigente** de un historial `MandateTenure` (actor user|coach|core_r, `effectiveFrom`/`effectiveTo`). Timeline en rail Coach; trades DEMO enlazados en `bolsa-mandate-trade-links-v1`.

---

## 6. UI — pantallas y zonas

### 6.1 Backtesting (universo LAB)

| Zona | Contenido to-be |
|------|-----------------|
| Probar estrategia | Embudo · fecha **Backtesting DÍA D** · Play |
| Coach / Lab / Finalistas | Sin cambio de rol; CTA **Verificar D→hoy** (ya no navega a Trading) |
| **Análisis técnico** | Dos modos (toggle o subtabs): **Ver** (IS) · **Verificar D→hoy** (fase C) |
| Monitor Finalistas / CORE-R | Frescura; CTAs Abrir Lab / Adoptar |
| Ayuda Backtesting | Guías DÍA D + universos |

**Análisis técnico — contrato**

| Modo | Datos | Controles |
|------|-------|-----------|
| **Ver** | Barras del run / ≤ D del trial | Scrubber replay existente (`BacktestReplayChart`) |
| **Verificar** | Barras D→hoy · #1 congelada | Manual / Semi / Auto · película · Informe · Guardar Evidence · Salir verificación |

Misma familia visual de gráfico; **distinto store** y chip `LAB · verificación`.

### 6.2 Trading (universo TRADING)

| Zona | Contenido to-be |
|------|-----------------|
| Mesa / gráfico | Reloj live · watchlist · Operaciones |
| Banner | Solo modos operativos reales (no MODO DÍA D) |
| **Rail Coach** | Por instrumento: TOP · frescura · Adoptar/Proponer · **Abrir estudio** · **Verificar** (deep-link LAB) |
| Caminos A/B/C/D | Sobre cuenta activa DEMO |

**Eliminar del to-be Trading:** `trading-dia-d-banner`, `trading-dia-d-replay-panel` como mesa principal, full-bleed película DÍA D en `/trading`.

### 6.3 Wire conceptual — Lab Verificar

```text
[Chip LAB · verificación]  TEF  ·  #1 SMA…  ·  D=2025-01-15 → hoy
[Manual | Semi | Auto]  [▶ película]  [Informe]  [Guardar Evidence]  [Salir]
┌─────────────────────────────────────────────────────────────┐
│  Gráfico replay D→hoy (misma familia BacktestReplayChart)   │
└─────────────────────────────────────────────────────────────┘
│ Equity sandbox LAB │ Ops sesión │ Evidence preview │
```

### 6.4 Wire conceptual — Trading + Coach

```text
[Chip TRADING · DEMO]  TEF
┌──────────────── chart live ────────────────┐  ┌─ Coach ──────────┐
│                                            │  │ TOP #1 · fresco  │
│                                            │  │ Adoptar · Proponer│
│                                            │  │ Abrir estudio →  │
│                                            │  │ Verificar D→hoy →│
└────────────────────────────────────────────┘  └──────────────────┘
│ Operaciones / Checklist / Radar …
```

---

## 7. Glosario UI (canónico)

| Término UI | Universo | Definición corta |
|------------|----------|------------------|
| **Backtesting / Lab** | LAB | Espacio de investigación y simulación |
| **Trading** | TRADING | Espacio de inversión diaria |
| **Cartera LAB** | LAB | Dinero virtual de estudios; no es tu DEMO |
| **Cuenta DEMO** | TRADING | Única cuenta operativa hoy |
| **DÍA D** | LAB | Fecha as-of del embudo (fases A+B) |
| **Ver** | LAB | Replay del experimento IS |
| **Verificar (D→hoy)** | LAB | Sesión C con #1 congelada |
| **Adoptar** | Puente | Usar TOP en DEMO |
| **Proponer** | Puente | Supervisado F3 |
| **Operar** | TRADING | Ejecutar en cuenta activa |
| **Abrir estudio** | Puente | Ir al Lab del mismo instrumento |
| **Coach en vivo** | Puente | Rail de estado Lab sobre el desk |

Renombres de copy respecto al as-is:

| Antes (as-is) | Después (to-be) |
|---------------|-----------------|
| Simular D→hoy → Trading MODO DÍA D | **Verificar D→hoy** (se queda en Backtesting) |
| MODO DÍA D (Trading) | Eliminado; chip **LAB · verificación** |
| Sandbox ≠ DEMO (ya existía) | Se mantiene; además chip + Cartera LAB |

---

## 8. Reglas duras

1. Lab **nunca** escribe el ledger de la cuenta activa DEMO salvo acciones de puente (Adoptar / Desplegar / Proponer / execute).  
2. Trading **nunca** reescribe params TOP / Lab ni lanza re-Lab.  
3. Verificar D→hoy: #1 **congelada**; sin re-Lab; point-in-time ≤ reloj simulado.  
4. Dos informes distintos: métricas embudo (≤ D) ≠ métricas sesión Verificar (D→hoy) ≠ PnL DEMO.  
5. Cambiar Manual/Semi/Auto = nueva sesión o reinicio explícito.  
6. Auto Verificar ≠ Camino D live (`PAPER_D_EXECUTE`).  
7. Una cuenta **operativa** Trading (premisa DEMO); Cartera LAB no compite como «Activa».  
8. Todo deep-link Trading→Lab preserva `instrumentId` (+ opcional `strategyDefinitionId`, `diaD`).

---

## 9. Flujos end-to-end (to-be)

### 9.1 Descubrir y verificar (solo LAB)

```text
Probar → fecha D pasada → Play → Finalistas #1
  → Verificar D→hoy (Análisis técnico)
  → Manual/Semi/Auto → Guardar Evidence
  → Salir verificación (sigue en Backtesting)
```

### 9.2 Adoptar y operar (puente + TRADING)

```text
Finalistas / Monitor → Adoptar (Checklist demo)
  → Trading: operar I en DEMO
  → Rail Coach: frescura · Abrir estudio si duda
```

### 9.3 Coach en paralelo (día a día)

```text
Trading abre I
  → Rail: TOP + frescura
  → usuario Opera en DEMO
  → en paralelo puede Abrir estudio / Verificar sin tocar DEMO
```

### 9.4 CORE-R

```text
Monitor encola revisión → usuario abre Lab (estudio)
  → no pisa TOP automáticamente
  → tras estudio: Adoptar de nuevo o marcar obsoleta
```

---

## 10. Mapa as-is → to-be (migración)

| Pieza as-is | Path / nota | Destino to-be |
|-------------|-------------|---------------|
| CTA Finalistas «Simular D→hoy» | Backtesting → `/trading` | CTA **Verificar** → Análisis técnico LAB |
| `dia-d-trading-session-store` | Trading | Renombrar/mover a dominio LAB (`dia-d-verify-session-store` o similar) |
| `trading-dia-d-banner` / `trading-dia-d-replay-panel` | Trading layout | Panel en Backtesting Análisis técnico |
| Manual/Semi/Auto contrato | Premisas §3c | **Se conserva** íntegro; solo cambia de universo |
| Evidence archive / POST dia-d | Ya research | Sin cambio de dominio científico |
| Smoke D1–D12 | operativa-test-plan | Reescribir pasos: no esperar Trading |
| HELP DÍA D | HELP.md | Actualizar cuando se implemente; hasta entonces marcar as-is + enlace ADR-019 |
| Premisa híbrida §2 #5 / §3 | dia-d-premises | Superseded → Modo A (este doc + ADR-019) |

### 10.1 Qué no migrar

- Embudo Play/Coach/Lab/Finalistas (ya en Backtesting).  
- Caminos A/B/C/D sobre DEMO.  
- CORE-R cola localStorage.  
- Motor replay / gate equity / Evidence heurística (reubicar UI, no reescribir ciencia).

---

## 11. Fases de implementación (propuesta)

| Fase | Objetivo | Criterio de hecho |
|------|----------|-------------------|
| **U0** | Docs + ADR + glosario (este paquete) | ✅ 2026-08-02 |
| **U1** | Chip universo + copy verbos (sin mover película) | ✅ 2026-08-02 |
| **U2** | Mover Verificar D→hoy a Backtesting Análisis técnico | ✅ 2026-08-02 |
| **U3** | Rail Coach en Trading (lectura TOP/frescura + deep-links) | ✅ 2026-08-02 |
| **U4** | Modelo Adopción explícito (estados) en Monitor/Checklist | ✅ 2026-08-02 (`bolsa-strategy-adoption-v1`) |
| **U5** | Cartera LAB tipada en sesión (`universe: lab`; sin DDL) | ✅ 2026-08-02 |
| **M0** | ADR Mandato operativo + glosario | ✅ 2026-08-02 ([ADR-020](../adr/020-operating-mandate-tenure.md)) |
| **M1** | Tenures + timeline UI (rail Coach) | ✅ 2026-08-02 |
| **M2** | Trades DEMO ↔ `mandateTenureId` (cliente) | ✅ 2026-08-02 |
| **M3** | Analítica churn user vs IA (resumen rail) | ✅ 2026-08-02 |

Congelados intactos: Belief UI, Lab P3–P9 Discovery, `PAPER_D_EXECUTE` off, CORE-R multi-device cron, broker live.

---

## 12. Criterios de aceptación de producto

1. Un usuario nuevo, sin leer docs, identifica en &lt;5 s si está en LAB o TRADING.  
2. Completar Verificar D→hoy **sin** visitar `/trading`.  
3. Completar un trade DEMO **sin** ver banner MODO DÍA D.  
4. Desde Trading en I, llegar al Lab de I en un clic (Abrir estudio).  
5. PnL de verificación y PnL DEMO no aparecen en el mismo widget.  
6. Ayuda y `HELP_CONTENT_AS_OF` alineados tras U2.  
7. `pnpm test:operativa` verde con escenarios to-be.

---

## 13. Preguntas abiertas (no bloquean U0–U2)

| # | Pregunta | Opciones | Default provisional |
|---|----------|----------|---------------------|
| Q1 | ¿Ver y Verificar son subtabs o un toggle? | Subtabs / Toggle / Dos rutas | Toggle en Análisis técnico |
| Q2 | ¿Cartera LAB como `InvestmentAccount`? | Sí / No (solo sesión) | No hasta U5 |
| Q3 | ¿Manual/Semi en Verificar desde día 1 de U2? | Portar los tres / solo Auto primero | Portar los tres (ya existen) |
| Q4 | ¿Rail Coach en móvil? | Dock inferior / hoja | Hoja «Coach» |
| Q5 | ¿Rename IDs `dia-d-trading-*`? | Big bang / alias | Alias en U2; rename en U3 |

---

## 14. Índice de documentos tocados por esta decisión

| Doc | Cambio |
|-----|--------|
| [ADR-019](../adr/019-dual-universes-lab-vs-trading.md) | Decisión formal |
| Este archivo | Diseño detallado |
| [dia-d-premises](./backtesting-dia-d-premises-2026-07-31.md) | Enmienda Modo A |
| [account-premises](./account-premises-demo-vs-paper-2026-07-31.md) | Cartera LAB ≠ segunda Activa |
| [domain-language](../domain-language.md) | Términos LAB/TRADING producto |
| [HELP](../HELP.md) / [README](../README.md) | Índice + nota as-is/to-be |
| [research-lifecycle](./research-lifecycle.md) | Flujo DÍA D to-be |
| [PORTFOLIO_AND_CASH](../PORTFOLIO_AND_CASH.md) | Nota Cartera LAB |

---

## 15. Ratificación de diseño

- [x] Fin último articulado  
- [x] Dos universos + dos carteras conceptuales  
- [x] Puente y glosario de verbos  
- [x] UI Lab / Trading / wires  
- [x] Comparativa apps top + diferencial  
- [x] Migración as-is→to-be + fases U0–U5  
- [x] Implementación U1–U5 (2026-08-02)
+ [x] Implementación U1–U5 (2026-08-02)
