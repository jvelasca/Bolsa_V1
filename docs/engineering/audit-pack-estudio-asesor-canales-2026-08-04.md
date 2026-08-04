# Paquete de auditoría — Estudio → Operativa → Asesor → Canales (2026-08-04)

> **Propósito:** documento **único** para auditar el cierre de la secuencia producto post-O3-C antes de thaw AUTO.  
> **AsOf:** 2026-08-04 · branch `stage/estudio-membership-operativa-2026-08-04` · repo `jvelasca/Bolsa_V1`  
> **Padre:** [triage round 3](./audit-ext-round3-triage-estudio-motor-2026-08-04.md) · [ADR-022](../adr/022-estudio-daily-opinion-motor.md) · [freeze](./post-audit-decision-freeze-2026-08-03.md)  
> **Siguiente:** [checklist thaw Camino D / AUTO](./camino-d-auto-thaw-checklist-2026-08-04.md) — **sin flip** `PAPER_D_EXECUTE` hasta evidencia.

---

## 0. Resumen ejecutivo

| Bloque | Pregunta | Estado |
|--------|----------|--------|
| **D1 motor** | ¿`InstrumentDailyOpinion` on-demand + caché + API + invariantes? | **Cerrado** |
| **Operativa** | ¿Mesa SEMI: dictamen del valor, Proponer F3, Outcomes, mandato? | **Cerrado** |
| **Asesor** | ¿Label + tab Opiniones + badge alarmas? | **Cerrado** |
| **Canales** | ¿Mapa AVISO/ALARMA + bandeja + toast + prefs email UI + EOD force? | **Cerrado** |
| **Notificaciones** | ¿Menú usuario → correo Alarmas (pre-multiusuario)? | **Cerrado** |
| **Cron EOD real** | ¿Worker con universo servidor? | **No** — flag off, noop |
| **AUTO / Camino D** | ¿Execute sin Confirm? | **Freeze** — ver checklist thaw |

**Veredicto para auditorías:** la cadena Estudio→dictamen→canal→SEMI Confirm (+ prefs notificación) está **listable y auditable**. No hay luz verde de producto para `PAPER_D_EXECUTE` hasta cumplir umbrales del triage §2.3 / checklist thaw.

---

## 1. Cómo auditar (30–40 min)

1. Leer este §0–§2 y [triage §11](./audit-ext-round3-triage-estudio-motor-2026-08-04.md).  
2. ADR: [022](../adr/022-estudio-daily-opinion-motor.md).  
3. Tests offline:  
   - `pnpm exec pytest packages/py/application/tests/test_daily_opinion_stance.py -q`  
   - `pnpm exec pytest packages/py/infrastructure/tests/test_estudio_opinion_email*.py -q`  
   - Vitest: `notification-prefs.test.ts`  
   - `pnpm test:semi` (si el entorno lo tiene).  
4. Smoke UI (Docker + `pnpm dev`):  
   - Estudio con ≥1 valor → Operativa muestra dictamen del **activo** (no lista global).  
   - Asesor → Opiniones: filtros Todas / Alarmas / Avisos · **Mapa canales**.  
   - SEMI: Alarma → **Proponer F3** → cola Confirm (origen Asesor).  
   - Icono **usuario** → Notificaciones: correo + toast on/off.  
   - Toast: Alarmas nuevas (respeta pref toast); sin spam al primer load.  
   - EOD force: pasa `notifyEmail` desde prefs; toast con `emailNotify.skippedReason` si SMTP off.  
5. Freeze: confirmar `PAPER_D_EXECUTE` / `ESTUDIO_EOD_OPINION_ENABLED` en off. SMTP opcional en demo.

---

## 2. Mapa de código (paths reales)

| Capacidad | Path |
|-----------|------|
| Stance / invariantes | `packages/py/application/.../daily_opinion_stance.py` · `daily_opinion_service.py` |
| Persistencia | Prisma `instrument_daily_opinions` · SQLAlchemy repo |
| API | `apps/api-python/.../routes/instrument_daily_opinions.py` |
| Shared contrato | `packages/shared/src/instrument-daily-opinion.ts` · `opinion-channel-map.ts` |
| Operativa | `trading-operativa-panel.tsx` · `operativa-dictamen.tsx` · `propose-instrument-supervised.ts` |
| Asesor | `research-page.tsx` · `asesor-opiniones-panel.tsx` · `use-asesor-alarma-badge.ts` |
| Toast Alarmas | `estudio-opinion-alarm-poller.tsx` · `alert-toasts.tsx` |
| Prefs notificación | `notification-prefs.ts` · `notifications-settings-panel.tsx` · menú Sesión |
| Email scaffold | `estudio_opinion_email.py` · eod-batch `notifyEmail*` · SMTP servidor |
| EOD | `eod-batch` + `estudio_eod_opinion_worker.py` (noop) |

---

## 3. Invariantes / disciplina (checklist)

| # | Invariante | Evidencia |
|---|------------|-----------|
| 1 | IO ranking ≠ stance Comprar | UI Operativa / Opiniones etiquetan ★ dictamen vs TOP/IO |
| 2 | Alarma → SEMI Confirm; no execute | `proposeInstrumentSupervised` / libro MANUAL bloquea |
| 3 | AUTO no por dictamen solo | Freeze + flags off |
| 4 | Canal = atributo del dictamen | `mapOpinionToChannel` único TS + espejo PY email |
| 5 | EOD no consolida velas a ciegas | Service valida barra / asOf (stance service) |
| 6 | Email no envía con flag off | `maybe_notify_estudio_alarmas` skip reasons |

---

## 4. Fuera de alcance (no fallar la auditoría por esto)

- Multiusuario / perfiles con buzón en servidor  
- SMS / push nativo  
- Worker EOD con lista Estudio servidor  
- Métricas acierto dictamen vs N días (D6 diseño) — **prerrequisito thaw**, no de este cierre  
- Belief→Coach · Strategy Studio · `COST_MODEL_V2` · `CORE_R_CRON`  
- Flip `PAPER_D_EXECUTE`

---

## 5. Preguntas para la auditoría externa

1. ¿La separación dictamen / canal / Confirm es clara y no inventa un 4º inbox?  
2. ¿El freeze AUTO sigue defendible con toast+email scaffold?  
3. ¿Qué métricas mínimas (además del triage §2.3) exigiríais antes de Camino D?  
4. ¿El mapa §5.2 es demasiado ruidoso (fatiga) o demasiado silencioso?  
5. ¿Hay solape peligroso Radar inbox vs Asesor Alarmas en UX?

---

## 6. Enlaces

- Diseño: [estudio-daily-opinion-alarms-design](./estudio-daily-opinion-alarms-design-2026-08-04.md)  
- Asesor UI: [asesor-ui-2026-08-04](./asesor-ui-2026-08-04.md)  
- Operativa: [trading-operativa-panel](./trading-operativa-panel-2026-08-04.md)  
- Pack previo Lab: [audit-pack-post-audits-2026-08-03](./audit-pack-post-audits-2026-08-03.md)  
- Thaw AUTO: [camino-d-auto-thaw-checklist](./camino-d-auto-thaw-checklist-2026-08-04.md)

---

## 7. Auditoría interna rápida (2026-08-04, Auto)

| Check | Resultado |
|-------|-----------|
| pytest stance + email map + notify prefs | **OK** (suite email) |
| Paths §2 existen (motor, API, Asesor, poller, prefs UI) | **OK** |
| Canales: filtros + Proponer F3 + mapa leyenda | **OK** |
| Menú usuario → Notificaciones (correo + toast) | **OK** |
| Toast poller respeta pref + selector Zustand estable | **OK** |
| eod-batch `notifyEmail*` + SMTP skip reasons | **OK** |
| EOD worker noop / flag off | **OK** |
| `PAPER_D_EXECUTE` / Camino D | **Freeze** — no código thaw execute |
| Telemetría precisión dictamen (D6) | **Falta** — bloqueante P3–P4 thaw |

**Veredicto interno:** cadena SEMI + notificaciones **lista para auditoría previa a AUTO**. Entrada AUTO = fase **A0 telemetría** ([checklist](./camino-d-auto-thaw-checklist-2026-08-04.md)), no flip de execute.

---

## 8. Resultado auditoría ejecutada (2026-08-04)

> Branch: `stage/estudio-membership-operativa-2026-08-04` @ `df3b581`+ · PR [#29](https://github.com/jvelasca/Bolsa_V1/pull/29)

| Check | Resultado |
|-------|-----------|
| `pytest` stance + email map + notify prefs | **17 passed** |
| Vitest notification-prefs + propose SEMI + IO + H≠M | **8 passed** |
| Flags default off (`ESTUDIO_EOD_*`, email env, Camino D freeze docs) | **OK** |
| Paths críticos presentes (motor, API, Asesor, poller, prefs UI) | **OK** |
| Selector Zustand estable (poller + badge) | **OK** (fix loops) |
| Smoke UI manual (toast/email/SEMI Confirm) | **Pendiente operador** (checklist §1.4) |
| Telemetría precisión/recall (P3–P4 thaw) | **No** — bloquea flip AUTO |
| `PAPER_D_EXECUTE` | **Freeze** |

### Veredicto

**PASS condicional para cierre Canales / gate pre-AUTO.**  
Listo para revisión humana / auditoría externa con el pack. **No PASS** para thaw Camino D (falta A0 métricas + P1–P10).

Siguiente: A0 telemetría dictamen · no merge de execute AUTO.

---

## 9. Auditorías institucionales (post pack)

Triage CTO / seguridad / OR: [audit-ext-institutional-pre-auto-triage-2026-08-04.md](./audit-ext-institutional-pre-auto-triage-2026-08-04.md).

- RCE `eval` / Depends-JWT-por-ruta: **no sostenidos** en código actual.  
- Prioridad: A0 → OR-lite → Repro+ · catálogo institutional aparcado (§5 del triage).


