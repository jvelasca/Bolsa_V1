# Checklist thaw — Camino D / AUTO execute (2026-08-04)

> **Estado:** **PREP** · `PAPER_D_EXECUTE` sigue **off** · no hay ADR de thaw todavía.  
> **AsOf:** 2026-08-04  
> **Padres:** [triage §2.3](./audit-ext-round3-triage-estudio-motor-2026-08-04.md) · [freeze](./post-audit-decision-freeze-2026-08-03.md) · [audit pack canales](./audit-pack-estudio-asesor-canales-2026-08-04.md) · diseño §9  
> **Regla:** ningún commit activa execute AUTO sin filas ✅ abajo + amend explícito del freeze + ADR thaw.

---

## 0. Qué es «ir a AUTO» aquí

| Es | No es |
|----|-------|
| Libro DEMO en modo **AUTO** (UI) + Camino D propose→execute gated | Activar broker live |
| Misma Alarma Estudio / Gate / mandato que SEMI, **sin** Confirm | Bypass Gate / long-only / maxOpen |
| Evidencia medible + kill switch | Flip silencioso de `.env` |

Secuencia producto acordada: **SEMI primero** (ya cerrado) → **auditoría de la cadena** → **este checklist** → solo entonces código Camino D + flags.

---

## 1. Prerrequisitos de producto (gate duro)

| # | Criterio (triage §2.3) | Cómo medir | Estado |
|---|------------------------|------------|--------|
| P1 | ≥ **60 días** DEMO con dictámenes estables | Conteos `instrument_daily_opinions` por día laborable | ☐ |
| P2 | ≥ **50** operaciones SEMI Confirm (fills DEMO) | Outcomes / DecisionSession / ledger DEMO | ☐ |
| P3 | Precisión BUY proxy 5d **≥ 70%** | Dictamen `buy` alarma vs retorno/forward 5d | ☐ |
| P4 | Recall **≥ 55%** | Cobertura de moves relevantes vs alarmas | ☐ |
| P5 | MaxDD DEMO **≤ min(10%, 1.2× MaxDD Lab)** | Cuenta DEMO equity curve | ☐ |
| P6 | **0** violaciones Gate en cualquier execute de prueba | Logs Gate + tests | ☐ |
| P7 | Kill switch **&lt; 1 s** (UI + flag server) | Runbook + prueba | ☐ |
| P8 | Confirmación doble UI para activar AUTO | Diseño UX + flag | ☐ |
| P9 | ADR de thaw con evidencia adjunta | `docs/adr/0xx-camino-d-thaw.md` | ☐ |
| P10 | Amend freeze: Camino D **thaw parcial / condicionado** | [freeze](./post-audit-decision-freeze-2026-08-03.md) | ☐ |

> Si P1–P5 no se pueden medir aún: **implementar telemetría (D6 métricas)** antes de execute. No inventar % a ojo.

---

## 2. Prerrequisitos técnicos (Camino D)

| # | Ítem | Notas | Estado |
|---|------|-------|--------|
| T1 | Política `paper_auto` solo en cuenta DEMO | No mezclar con broker | ☐ |
| T2 | Execute lee **misma** Alarma/dictamen + Gate PASS | Origen `asesor_alarma` / EOD etiquetado | ☐ |
| T3 | Sizing = Libro DEMO (`defaultSizePctOfCash`, maxOpen) | Reusar prefs SEMI | ☐ |
| T4 | Idempotencia execute (no doble fill mismo asOf+stance) | Clave por opinión/día | ☐ |
| T5 | `PAPER_D_EXECUTE=0` default; opt-in documentado | `.env.example` + HELP | ☐ |
| T6 | Observabilidad: cada fill AUTO → DecisionSession + reason codes | Auditable | ☐ |
| T7 | Tests: gate bloquea; flag off no ejecuta; happy path DEMO | `test:semi` + nuevos | ☐ |
| T8 | Radar paper_auto ≠ Estudio AUTO | Copy UI paths A/B/C/D intacto | ☐ |

---

## 3. Fases de implementación (solo tras auditoría OK)

| Fase | Entrega | Depende |
|------|---------|---------|
| **A0** | Telemetría acierto dictamen (D6 diseño) — dash mínimo | Canales cerrado |
| **A1** | Libro UI modo AUTO (disabled hasta flags) + copy riesgos | A0 o paralelo |
| **A2** | Camino D: Alarma → propose→execute **detrás** `PAPER_D_EXECUTE` | P6–P8 diseño |
| **A3** | Kill switch + confirmación doble | A2 |
| **A4** | ADR thaw + freeze amend + ayuda HELP | Evidencia P1–P5 |
| **A5** | Opt-in DEMO controlado (1 cuenta) | A4 |

**Congelado hasta A4:** Belief, `CORE_R_CRON`, Strategy Studio, `COST_MODEL_V2`, SMS.

---

## 4. Decisión inmediata (2026-08-04)

Tras cerrar Canales y el [audit pack](./audit-pack-estudio-asesor-canales-2026-08-04.md):

1. **Auditar** la cadena (pack §1).  
2. Empezar **A0 telemetría** (sin execute).  
3. **No** poner `PAPER_D_EXECUTE=1` en demo compartida.

Cualquier “vamos con AUTO” en chat = **entrar en esta checklist**, no thaw automático.
