# ADR 019: Dos universos de producto — LAB (Backtesting) vs TRADING

## Estado

**Aceptado** — 2026-08-02  
**Tipo:** decisión de producto / bounded contexts de **experiencia de usuario** (complementa, no sustituye, [ADR-015](./015-scientific-domain-vs-trading-domain.md)).  
**Depende de:** ADR-015, [ADR-008](./008-investment-accounts-and-ledger.md), [ADR-009](./009-backtesting-research-platform-h0.md), [ADR-010](./010-platform-kernel-radar-execution.md), premisas [DÍA D](../engineering/backtesting-dia-d-premises-2026-07-31.md), [cuentas DEMO/Paper](../engineering/account-premises-demo-vs-paper-2026-07-31.md).  
**Diseño detallado (UI, objetos, fases):** [dual-universes-lab-trading-design-2026-08-02.md](../engineering/dual-universes-lab-trading-design-2026-08-02.md).

> **Implementación:** pendiente (salto de producto). Hasta migrar código/UI, el as-is sigue el híbrido DÍA D → Trading MODO DÍA D (v0.11). Este ADR **congela el to-be**.

---

## 1. Contexto

ADR-015 separa **Scientific Domain** (objetos de conocimiento) de **Trading Domain** (órdenes, posiciones, ledger). Eso es correcto a nivel de modelo de datos.

A nivel de **producto UI**, la app aún mezclaba dos películas parecidas:

| Película | Pregunta | Dónde vive hoy (as-is) |
|----------|----------|------------------------|
| **Ver** (replay IS) | ¿Qué hizo el run terminado? | Backtesting → Análisis técnico |
| **Simular D→hoy** | ¿Qué habría pasado operando #1 desde D? | **Trading** MODO DÍA D |

El usuario percibe Trading a la vez como **mesa de inversión diaria** y como **laboratorio de verificación**. Eso contamina:

- la narrativa de la cuenta **DEMO** (patrimonio “de verdad” simulado),
- el vocabulario (Simular / Operar / Adoptar),
- y el fin último: usar el Lab para **enseñar** la operativa conveniente por instrumento y **usarla** en Trading sin mezclar carteras.

### 1.1 Fin último (producto)

> Por cada **instrumento**: el universo LAB descubre, verifica y mantiene la operativa más conveniente (Coach / Lab / Finalistas / DÍA D / CORE-R); el universo TRADING la **adopta** y opera el día a día (DEMO → futuro Paper/Live). Ambos conviven **en paralelo** sobre el mismo valor, con vínculo explícito — **coach profundo en vivo**, no un backtest aislado ni un Trading que hace de laboratorio.

---

## 2. Decisión

### 2.1 Modo A (bloqueado)

| Universo | Responsabilidad | **No** es |
|----------|-----------------|-----------|
| **LAB / Backtesting** | Investigación histórica, embudo, simulaciones, verificación D→hoy, Evidence de sesión C, coach/Lab/Finalistas, frescura CORE-R | Inversión diaria ni ledger DEMO |
| **TRADING** | Operativa diaria simulada (DEMO) y, en el futuro, Paper/Live vía broker | Replay de research ni “mesa DÍA D” |

**Consecuencia directa:** la fase C de DÍA D (**Verificar D→hoy**, Manual/Semi/Auto, película, Guardar Evidence) **pertenece al universo LAB**, no a Trading. El híbrido «C en Trading» de las premisas 2026-07-31 queda **superseded** por este ADR (ver enmienda en el doc de premisas).

### 2.2 Dos carteras / ledgers conceptuales

| Cartera | Universo | Rol | Escribe DEMO activa |
|---------|----------|-----|---------------------|
| **Cartera LAB** | Backtesting | Cash/posiciones **virtuales** de simulación (Play, Ver, Verificar D→hoy). Puede ser ledger ligero o runs+equity efímero | **Nunca** |
| **Cartera TRADING** | Trading | Cuenta **activa** DEMO (hoy) → Paper/Live (futuro). Caminos A/B/C/D | Solo vía Adoptar / Desplegar / Proponer / execute |

No hace falta duplicar todo el DDL el día 1: lo crítico es que **UI + reglas** etiqueten siempre LAB vs TRADING y que Lab no mute el ledger operativo salvo acciones de **puente** explícitas.

La premisa «una sola cuenta operativa» ([account-premises](../engineering/account-premises-demo-vs-paper-2026-07-31.md)) **sigue válida para TRADING**. La Cartera LAB **no** es una segunda «cuenta activa» de inversión: es un **sandbox de research** (universo paralelo).

### 2.3 Puente por instrumento (único vínculo permitido)

```text
Instrumento (p.ej. TEF)
        │
        ├─ LAB: TOP / #1 / frescura / Evidence DÍA D / Lab params
        │         │
        │         ▼  Adoptar | Vigilar | Proponer | Abrir estudio
        │
        └─ TRADING: posición / órdenes / Checklist / Radar / Supervisado
```

Estados de adopción (producto): `candidata` → `adoptada` → `obsoleta` (CORE-R / decaimiento).  
Lab **recomienda**; Trading **ejecuta** tras Gate / confirmación humana según camino.  
**Tenure / historial** de qué estrategia gobernó cada periodo: [ADR-020](./020-operating-mandate-tenure.md) (Mandato operativo; M1+).

### 2.4 Glosario de verbos (una acción = un verbo)

| Verbo | Universo | Significado |
|-------|----------|-------------|
| **Ver** | LAB | Replay del run IS (≤ D o ventana del trial) |
| **Verificar** | LAB | Sesión D→hoy con #1 congelada (antes «Simular D→hoy» en Trading) |
| **Adoptar** | Puente → TRADING | Ligar TOP/#1 a operativa DEMO (Checklist / deploy) |
| **Proponer** | Puente → TRADING | Camino Supervisado F3 |
| **Operar** | TRADING | Órdenes / fills en cuenta activa |
| **Abrir estudio** | TRADING → LAB | Mismo instrumento, contexto Lab / DÍA D / Finalistas |

Prohibido: que «Simular» abra la mesa de inversión diaria.

### 2.5 Coach en vivo (paralelo)

En Trading, por instrumento abierto, un **rail Coach** (compacto) muestra: TOP actual · frescura · CTAs **Abrir estudio** / **Verificar D→hoy** (saltan a LAB, no reutilizan el ledger DEMO). Cumple el fin: operativa + estudio profundo en paralelo.

---

## 3. Relación con ADR-015

| Capa | Qué separa |
|------|------------|
| **ADR-015** | Objetos Scientific ≠ Trading (Hypothesis ≠ Strategy, Evidence ≠ Position) |
| **ADR-019** | Experiencia de producto: **pantallas, carteras, verbos** LAB ≠ TRADING |

El puente científico Reasoning → DecisionPackage sigue siendo el único camino de autorización cognitiva. El puente de producto Adoptar/Proponer es la **UX** de ese handoff.

---

## 4. Consecuencias

**Positivas**

- Trading limpio para DEMO → Paper/Live.  
- Research (incl. DÍA D C) coherente con «laboratorio».  
- Narrativa clara para enseñar IA / TOP por instrumento.  
- Diferencial vs apps top: coach profundo **explícito** en paralelo al desk.

**Costes**

- Migración UI: sacar sesión DÍA D de `/trading` hacia Backtesting (Análisis técnico / subvista Verificar).  
- Posible entidad Cartera LAB (o sesión sandbox tipada) en persistencia.  
- Actualizar Ayuda, smoke D1–D12, copy y trackers.  
- Hasta migrar: doble verdad temporal (docs to-be vs código as-is) — marcada en HELP y premisas.

**No implica (aún)**

- Multi-cuenta operativa Trading.  
- Broker Paper/Live.  
- Auto-paper D (`PAPER_D_EXECUTE`) on-by-default.  
- Re-Lab durante Verificar.

---

## 5. Ratificación

- [x] Modo A: LAB = research/sims/verificación · TRADING = inversión diaria  
- [x] Dos carteras conceptuales (LAB sandbox ≠ DEMO)  
- [x] Fase C DÍA D → universo LAB (supersede híbrido C en Trading)  
- [x] Puente por instrumento + glosario de verbos  
- [x] Coach rail en Trading (paralelo, no mesa DÍA D)  
- [x] Diseño detallado en engineering doc  
- [ ] Implementación (fuera de este ADR; ver fases en el diseño)

**Código:** U1–U5 implementados 2026-08-02 — chip, Verificar en LAB, Coach rail, adopción, `universe: lab`.
