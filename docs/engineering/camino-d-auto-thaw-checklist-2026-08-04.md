# Checklist thaw — Camino D / AUTO execute (2026-08-04)

> **Estado:** **PREP** · `PAPER_D_EXECUTE` sigue **off** · no hay ADR de thaw todavía.  
> **AsOf:** 2026-08-04  
> **Padres:** [triage §2.3](./audit-ext-round3-triage-estudio-motor-2026-08-04.md) · [freeze](./post-audit-decision-freeze-2026-08-03.md) · [audit pack canales](./audit-pack-estudio-asesor-canales-2026-08-04.md) · diseño §9  
> **Regla:** ningún commit activa execute AUTO sin filas ✅ abajo + amend explícito del freeze + ADR thaw.

---

## 0. Qué es «ir a AUTO» aquí

| Es                                                                | No es                             |
| ----------------------------------------------------------------- | --------------------------------- |
| Libro DEMO en modo **AUTO** (UI) + Camino D propose→execute gated | Activar broker live               |
| Misma Alarma Estudio / Gate / mandato que SEMI, **sin** Confirm   | Bypass Gate / long-only / maxOpen |
| Evidencia medible + kill switch                                   | Flip silencioso de `.env`         |

Secuencia producto acordada: **SEMI primero** (ya cerrado) → **auditoría de la cadena** → **este checklist** → solo entonces código Camino D + flags.

---

## 1. Prerrequisitos de producto (gate duro)

| #   | Criterio (triage §2.3)                                 | Cómo medir                                            | Estado                                                 |
| --- | ------------------------------------------------------ | ----------------------------------------------------- | ------------------------------------------------------ |
| P1  | ≥ **60 días** DEMO con dictámenes estables             | Conteos `instrument_daily_opinions` por día laborable | ❌ 28d (medición 2026-08-25)                           |
| P2  | ≥ **50** operaciones SEMI Confirm (fills DEMO)         | Outcomes / DecisionSession / ledger DEMO              | ❌ 0 fills                                             |
| P3  | Precisión BUY proxy 5d **≥ 70%**                       | Dictamen `buy` alarma vs retorno/forward 5d           | ❌ null (0 buy-alarma)                                 |
| P4  | Recall **≥ 55%**                                       | Cobertura de moves relevantes vs alarmas              | ❌ 0%                                                  |
| P5  | MaxDD DEMO **≤ min(10%, 1.2× MaxDD Lab)**              | Cuenta DEMO equity curve                              | ⚠ 0.2% cash proxy / 0 trades                           |
| P6  | **0** violaciones Gate en cualquier execute de prueba  | Logs Gate + tests                                     | ☐                                                      |
| P7  | Kill switch **&lt; 1 s** (UI + flag server)            | Runbook + prueba                                      | **Prep** · UI Operativa + `POST /api/risk/kill-switch` |
| P8  | Confirmación doble UI para activar AUTO                | Diseño UX + flag                                      | **Prep** · armado local; pill sigue off                |
| P9  | ADR de thaw con evidencia adjunta                      | `docs/adr/023-camino-d-thaw.md`                       | **Proposed** · evidencia ☐                             |
| P10 | Amend freeze: Camino D **thaw parcial / condicionado** | [freeze](./post-audit-decision-freeze-2026-08-03.md)  | **Nota prep** · no Accepted                            |

> Si P1–P5 no se pueden medir aún: **implementar telemetría (D6 métricas)** antes de execute. No inventar % a ojo.

---

## 2. Prerrequisitos técnicos (Camino D)

| #   | Ítem                                                            | Notas                                   | Estado                 |
| --- | --------------------------------------------------------------- | --------------------------------------- | ---------------------- |
| T1  | Política `paper_auto` solo en cuenta DEMO                       | No mezclar con broker                   | ☐                      |
| T2  | Execute lee **misma** Alarma/dictamen + Gate PASS               | Origen `asesor_alarma` / EOD etiquetado | ☐                      |
| T3  | Sizing = Libro DEMO (`defaultSizePctOfCash`, maxOpen)           | Reusar prefs SEMI                       | ☐                      |
| T4  | Idempotencia execute (no doble fill mismo asOf+stance)          | Clave `instrument\|asOf\|policy\|kind`  | **Prep**               |
| T5  | `PAPER_D_EXECUTE=0` default; opt-in documentado                 | `.env.example` + HELP                   | **Hecho**              |
| T6  | Observabilidad: cada fill AUTO → DecisionSession + reason codes | Auditable                               | **Prep** (DENY + fill) |
| T7  | Tests: gate bloquea; flag off no ejecuta; happy path DEMO       | `test:semi` + nuevos                    | Parcial                |
| T8  | Radar paper_auto ≠ Estudio AUTO                                 | Copy UI paths A/B/C/D intacto           | **Hecho** (copy)       |

---

## 3. Fases de implementación (solo tras auditoría OK)

| Fase   | Entrega                                                  | Depende                                                                                                       |
| ------ | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **A0** | Telemetría acierto dictamen (D6) — dash Asesor           | **Hecho** · `GET …/telemetry`                                                                                 |
| **A1** | Libro UI modo AUTO (disabled hasta flags) + copy riesgos | **Hecho** · `DemoBookModePanel` + `demo-book-auto-copy`                                                       |
| **A2** | Camino D detrás `PAPER_D_EXECUTE` **vía Risk Engine**    | **Hecho (flag off)** · idempotencia + DecisionSession fill/DENY · [prep](./camino-d-a2-a5-prep-2026-08-04.md) |
| **A3** | Kill switch + confirmación doble                         | **Hecho** · API/UI kill + armado local `ACTIVAR AUTO`                                                         |
| **A4** | ADR thaw + freeze amend + ayuda HELP                     | **Borrador** · [ADR-023](../adr/023-camino-d-thaw.md) Proposed · evidencia P1–P5 ☐                            |
| **A5** | Opt-in DEMO controlado (1 cuenta)                        | **Hecho (doc+gate)** · `PAPER_D_ACCOUNT_ID`                                                                   |

**Congelado hasta A4:** Belief, `CORE_R_CRON`, Strategy Studio, `COST_MODEL_V2`, SMS.

---

## 4. Decisión inmediata (2026-08-04)

Tras cerrar Canales + prefs notificación y el [audit pack](./audit-pack-estudio-asesor-canales-2026-08-04.md):

1. **Auditar** la cadena (pack §1) — **gate previo a AUTO**.
2. Empezar **A0 telemetría** (sin execute).
3. **No** poner `PAPER_D_EXECUTE=1` en demo compartida.

Cualquier “vamos con AUTO” en chat = **entrar en esta checklist**, no thaw automático.

### Gate auditoría previa (2026-08-04)

| Ítem                                            | Estado                                                                                                 |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Pack Estudio/Asesor/Canales + notificaciones UI | Listo para revisar                                                                                     |
| Menú usuario → correo Alarmas                   | Hecho (localStorage; multiusuario después)                                                             |
| Freeze Camino D intacto                         | Sí                                                                                                     |
| Auditorías institucionales 1+2 (CTO/OR)         | [Triage](./audit-ext-institutional-pre-auto-triage-2026-08-04.md) — A0 + OR-lite; catálogo §5 aparcado |
| A0 métricas dictamen                            | **API+UI** `…/telemetry` · medir P1/P3/P4 en Asesor Opiniones                                          |
| A1 Libro AUTO UI                                | **Hecho** — pill «Auto · prep» + riesgos; `DEMO_BOOK_AUTO_UI_ENABLED=false`; coerce auto→semi          |

### OR-lite (antes de A2 execute)

Extraído del triage institucional — no sustituye P1–P10. Detalle: [or-lite-repro-obs](./or-lite-repro-obs-2026-08-04.md).

| ID       | Ítem                                                    | Estado                                             |
| -------- | ------------------------------------------------------- | -------------------------------------------------- |
| OR-S1    | `APP_PASSWORD` obligatorio en demos compartidas         | **Hecho** — docs + health `auth`                   |
| OR-P2    | Decimal en path paper crítico (pre-live)                | **Hecho** — fees / execute_trade / ExecuteTrade    |
| OR-T4/T6 | Idempotencia + DecisionSession en execute (detrás flag) | **Prep A2** — claim Redis/mem + sessions DENY/fill |
| OR-P7    | Kill switch &lt;1s (ya P7)                              | Via `RISK_KILL_SWITCH` + OR-RE                     |
| OR-RE    | Risk Engine façade                                      | **v0 hecho**                                       |
| Repro+   | dataset fingerprint + feature_flags + payload_hash      | **Hecho** — `campaign_manifest.py`                 |
| Obs/CI   | ErrorBoundary + gitleaks + worker heartbeat             | **Hecho**                                          |
