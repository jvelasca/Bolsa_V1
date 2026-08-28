# Estudio — Operativa AUTO y operativa sobre el gráfico

> **AsOf:** 2026-08-28 · **Estado:** **ESTUDIO ABIERTO** — ronda de contraste entre auditorías; **no es implementación**.
> **Repo:** https://github.com/jvelasca/Bolsa_V1 · **Ruta:** `docs/engineering/estudio-operativa-auto-y-grafico-2026-08-28.md`
> **Arranque auditor (copiar en chat):** [`arranque-auditor-estudio-operativa-auto-grafico-2026-08-28.md`](./arranque-auditor-estudio-operativa-auto-grafico-2026-08-28.md)
> **Padre:** [`analisis-vs-apps-top-operative-flow-2026-08-28.md`](./analisis-vs-apps-top-operative-flow-2026-08-28.md) · [`diseno-mercado-2-0-cockpit-2026-08-27.md`](./diseno-mercado-2-0-cockpit-2026-08-27.md) · [`traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md`](./traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md) · [ADR-040 §10](../adr/040-user-information-architecture.md) · [ADR-023](../adr/023-camino-d-thaw.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Destinatarios:** auditorías externas (**A0** arquitectura/producto · **N4** invariantes/mecánica · **Deep** código/seguridad) + owner producto.
> **Idioma de respuesta preferido:** español (o bilingüe con resumen ES).
> **Regla:** hasta **acuerdo de diseño explícito** en §8, no abrir código de drag gráfico ni ampliar AUTO más allá del thaw BETA-D ya aceptado.

---

## Para auditorías externas (GitHub)

**Qué es:** brief de diseño para acordar **(A)** operativa AUTO en la mesa y **(B)** operativa editable sobre el gráfico, **antes** de V1.27.

**Qué pedimos:** una respuesta por auditoría con la plantilla §7.2 (opciones A-α…δ y B-α…δ + disensos).

**Qué no pedimos:** implementar drag · broker live · thaw estricto cerrado · nav L1 nueva · ranking → BUY.

**Orden de lectura recomendado:**

1. [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md`](./traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md)
3. [`analisis-vs-apps-top-operative-flow-2026-08-28.md`](./analisis-vs-apps-top-operative-flow-2026-08-28.md)
4. [`diseno-mercado-2-0-cockpit-2026-08-27.md`](./diseno-mercado-2-0-cockpit-2026-08-27.md)
5. **Este documento** (§2 invariantes · §3 AUTO · §4 gráfico · plantilla §7.2)
6. [`contrato-confirm-v125-ticket-2026-08-28.md`](./contrato-confirm-v125-ticket-2026-08-28.md) (input obligatorio si se elige drag → Confirm)

**Entrega:** issue/PR comentario o documento `respuesta-auditor-[A0|N4|Deep]-operativa-auto-grafico-*.md` enlazado en §8 de este estudio.

---

## 0. Por qué existe este documento

V1.25 cerró **operational safety** (sizing único, ticket Confirm, what-if, `signedStop`). V1.26 cierra **position lifecycle integrity** (geometría fail-closed, stop firmado en PositionState, nacimiento SEMI → fill).

Quedan **dos frentes operativos grandes** sin diseño consensuado:

| Frente                             | Pregunta de producto                                                           | Riesgo si se improvisa                                                 |
| ---------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| **A — Operativa AUTO**             | ¿Qué significa «operar en AUTO» en la mesa cuando SEMI ya es el camino humano? | Segundo sizing · bypass de Confirm · thaw silencioso · ranking → BUY   |
| **B — Operativa sobre el gráfico** | ¿Qué puede hacer el usuario **desde el gráfico** sin romper Confirm = firma?   | Segundo stop · drag que no pasa RiskGate · trail promovido a autoridad |

Este estudio **no elige implementación**. Ordena el terreno, fija invariantes no negociables, plantea opciones y define **cómo** las auditorías llegan a un acuerdo antes de V1.27+.

---

## 1. Estado real en código (leer antes de proponer)

### 1.1 Shell y flujo humano (congelado)

| Pieza                      | Estado                                          | Evidencia                                     |
| -------------------------- | ----------------------------------------------- | --------------------------------------------- |
| Nav L1                     | Hoy · Mercado · Cartera · Asesor · Laboratorio  | ADR-040                                       |
| Mercado dock               | `LISTAS \| GRÁFICO \| OPERATIVA`                | `trading-layout.tsx`                          |
| Confirm                    | Única firma humana SEMI                         | `confirm_recommendation.py`                   |
| Ranking / IO / Opportunity | ≠ BUY · ≠ Permission                            | ADR-041 · `operativa-index.ts`                |
| Estudio                    | Membresía explícita; abrir gráfico **no** añade | ADR-024                                       |
| Fases UI                   | VIGILAR → … → POSICIÓN                          | `diseno-mercado-2-0-cockpit-2026-08-27.md` §3 |
| Niveles en gráfico         | Proyección read-only (`pointer-events-none`)    | `chart-operational-plan-levels-layer.tsx`     |
| Fuente niveles             | `OperationalPlanView` — un solo plan            | `operational-plan-chart-levels.ts`            |
| Trail en gráfico           | Advisory (ámbar punteado); ≠ stop vigente       | mismo fichero                                 |
| T1 tocado                  | ≠ gestionado (`target1AchievedAt`)              | ADR-041 H2                                    |
| V1.26                      | Geometría + `signedStop` round-trip             | relevo V1.26                                  |

### 1.2 Modos de cuenta (Manual / SEMI / AUTO)

| Modo       | Qué hace hoy                                | Gate                                                                          |
| ---------- | ------------------------------------------- | ----------------------------------------------------------------------------- |
| **MANUAL** | HTTP trade / operaciones manuales           | `check_opening` en buys; `trade_plan_snapshot=None` = HUMAN_MANUAL            |
| **SEMI**   | Propose → Confirm (firma) → fill → Position | Mismo risk de cesta que AUTO; requiere Estudio                                |
| **AUTO**   | UI armable (BETA-D); execute **opt-in**     | `PAPER_D_EXECUTE` default **off** · `ExecutionRouter` · mismo `check_opening` |

Referencias: [`trading-operativa-panel-2026-08-04.md`](./trading-operativa-panel-2026-08-04.md) · [`camino-d-auto-thaw-checklist-2026-08-04.md`](./camino-d-auto-thaw-checklist-2026-08-04.md) · ADR-023 Accepted BETA-D.

### 1.3 Qué **no** existe aún (huecos de diseño)

| Hueco                                              | Notas                                                                      |
| -------------------------------------------------- | -------------------------------------------------------------------------- |
| Drag stop/T1/entrada en gráfico                    | Explícitamente fuera V1.25–V1.26                                           |
| Recálculo what-if **en vivo** al mover línea       | Existe what-if en Confirm ticket (V1.25), no en chart                      |
| Toast DISPARADA / T1 tocado en Listas              | V1.26b candidato                                                           |
| AUTO con TradePlan TRIGGERED como SoT de sizing    | SEMI ya lo exige; AUTO Camino D usa sizing libro — **posible divergencia** |
| Órdenes dibujadas en gráfico (OCO, bracket broker) | Fuera de F4 PAPER · fuera de thin 8.2                                      |
| Web Notifications / push                           | V1.27 candidato                                                            |

---

## 2. Invariantes no negociables (todas las opciones deben cumplirlas)

Estas reglas **no se votan**. Cualquier propuesta que las viole se marca **RECHAZADA** en el registro §8.

1. **Confirm = firma** para aperturas SEMI humanas. AUTO es modalidad distinta, no un atajo que evite gates.
2. **Ranking ≠ BUY · Opportunity ≠ Permission · Calidad ≠ mandato.**
3. **Un solo stop vigente autoritativo** por posición (`currentStop` / `signedStop`). Trail y bracket thin son advisory hasta diseño explícito de promote.
4. **Un solo TradePlan SoT** por decisión TRIGGERED (V1.25/V1.26). Editar niveles implica override + firma o rechazo fail-closed — no sustitución silenciosa.
5. **Estudio gate** en SEMI y AUTO: instrumento fuera de Estudio → no propose AUTO/SEMI de apertura.
6. **`PAPER_D_EXECUTE` default off** · thaw estricto sigue deuda · broker live fuera.
7. **Lab ≠ Trading** · LLM no ejecuta.
8. **Nav L1 y shell Mercado** congelados (ADR-040 §10).
9. **T1 tocado ≠ reducido** hasta fill + sello gestionado.

---

## 3. Frente A — Operativa AUTO

### 3.1 Problema

El producto tiene **tres autorizaciones** sobre el **mismo risk engine**:

```
Misma cesta (check_opening + Fit + DS-05 + DS-03)
  ├─ HUMAN_MANUAL  (HTTP trade, sin TradePlan SEMI)
  ├─ SEMI            (Confirm humano + TradePlan TRIGGERED + signedStop)
  └─ AUTO            (ExecutionRouter, sin Confirm, Camino D)
```

La duda no es «¿AUTO es posible?» — BETA-D ya lo aceptó con condiciones. La duda es **cómo se presenta y continúa** en la mesa junto al flujo Operative Flow ya escrito.

### 3.2 Preguntas de diseño (AUTO)

| ID  | Pregunta                                                                                                      | Por qué importa                                    |
| --- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| A1  | ¿AUTO abre solo desde **dictamen/alarma Estudio** o también desde Radar / scan / cola Hoy?                    | Dos ritmos (EOD vs on_bar) sin doble verdad        |
| A2  | ¿AUTO usa **TradePlan TRIGGERED** como sizing SoT (paridad SEMI) o sizing **libro** (`defaultSizePctOfCash`)? | Contradicción P0 histórica                         |
| A3  | ¿Qué ve el usuario cuando AUTO **DENY** por gate?                                                             | Honestidad vs ruido                                |
| A4  | ¿Dónde vive el CTA «AUTO armado» vs «SEMI Confirm» en Operativa?                                              | Un solo CTA primario por fase                      |
| A5  | ¿AUTO puede **proteger/reducir** posiciones existentes sin Confirm?                                           | ExitPermission asimétrico (H2) ya existe en código |
| A6  | ¿Qué telemetría mínima exige ampliar AUTO antes de thaw estricto?                                             | P1–P5 siguen FAIL                                  |
| A7  | ¿Copy de producto: «Autopilot» / «Automático» / «Libro AUTO»?                                                 | ADR-040: nunca «Compra X» desde IA                 |

### 3.3 Opciones AUTO (para votar)

| Opción                   | Descripción                                                                                | Pros                        | Contras                                  |
| ------------------------ | ------------------------------------------------------------------------------------------ | --------------------------- | ---------------------------------------- |
| **A-α Conservadora**     | AUTO = solo execute backend; UI mínima (badge + log + kill switch). Mesa sigue SEMI-first. | Bajo riesgo · alinea BETA-D | Poca «operativa AUTO» visible            |
| **A-β Paridad SEMI**     | AUTO exige mismo TradePlan TRIGGERED + risk signature que SEMI; solo salta Confirm.        | Un solo sizing · integridad | Menos flex · más CPU en propose          |
| **A-γ Libro clásico**    | AUTO mantiene sizing prefs cuenta (Camino D actual). SEMI usa TradePlan.                   | Ya cableado                 | **Dos verdades de tamaño** — choca V1.25 |
| **A-δ Híbrido por fase** | PREPARADA/DISPARADA = SEMI only; AUTO solo en job batch nocturno / cola Actuar.            | Separa inbox vs autopilot   | Complejidad UX                           |

**Pre-recomendación interna (no decisión):** descartar **A-γ** salvo waiver explícito; priorizar contraste **A-α** vs **A-β**.

### 3.4 Encargo por auditoría (AUTO)

| Auditor  | Entregar                                                                                                                         |
| -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **A0**   | Opción recomendada A-α…δ · mapa bounded contexts · top 5 riesgos producto · relación con Operative Flow §5                       |
| **N4**   | Precedencia dictamen vs TradePlan vs gate · máquina estados valor en AUTO · invariantes testables · criterios thaw estricto      |
| **Deep** | Superficie código AUTO actual (`execution_router.py`, idempotencia, kill switch) · amenazas bypass Confirm · slice mínimo seguro |

**No pedir:** broker live · thaw estricto cerrado sin evidencia · ranking como trigger AUTO.

---

## 4. Frente B — Operativa sobre el gráfico

### 4.1 Problema

El gráfico ya es **centro visual** del cockpit (Mercado 2.0 §2). Hoy es **read-only** para niveles operativos. TradingView/IBKR ganan en **editar desde la línea**; nosotros ganamos en **honestidad de riesgo** (V1.25 Confirm ticket).

La pregunta no es «¿añadimos drag?» a ciegas. Es **qué ediciones gráficas reescriben qué artefacto** y **cuándo sigue siendo obligatorio Confirm**.

### 4.2 Espectro de interacción (gráfico)

| Nivel  | Interacción                                     | Artefacto mutado       | ¿Confirm?            | Estado                     |
| ------ | ----------------------------------------------- | ---------------------- | -------------------- | -------------------------- |
| **G0** | Ver niveles plan                                | ninguno                | —                    | **CÓDIGO** V1.23           |
| **G1** | Hover / crosshair explica ATR, R, soporte       | ninguno                | —                    | Parcial (crosshair existe) |
| **G2** | Toast / badge fase en lista (DISPARADA, T1)     | ninguno                | —                    | **V1.26b** candidato       |
| **G3** | Drag **solo visual** (ghost) + what-if local    | ninguno durable        | —                    | Sandbox UX                 |
| **G4** | Drag stop → **pre-fill Confirm** (`signedStop`) | intent Confirm         | **Sí**               | Candidato V1.27            |
| **G5** | Drag stop → **muta Position** protect           | PositionRevision       | Según ExitPermission | Post-V1.27                 |
| **G6** | Drag T1/T2 / bracket OCO broker                 | ExecutionPlan / broker | TBD                  | **Fuera** F4 PAPER         |

### 4.3 Preguntas de diseño (gráfico)

| ID  | Pregunta                                                                   | Por qué importa            |
| --- | -------------------------------------------------------------------------- | -------------------------- |
| B1  | ¿Qué líneas son **draggables**? (stop vigente · entrada · T1 · T2 · trail) | Trail ≠ autoridad          |
| B2  | ¿Drag en **ARMED/PREPARADA** vs solo en **POSICIÓN**?                      | Riesgo de inventar plan    |
| B3  | ¿El drag abre Confirm drawer o inline ticket?                              | Paridad V1.25 override     |
| B4  | ¿Recálculo en vivo (€, R, %, scenario Antes→Después) mientras arrastra?    | thinkorswim-like           |
| B5  | ¿Qué pasa si geometría inválida (`stop_wrong_side`, `stop_invalid`)?       | V1.26 DENY codes           |
| B6  | ¿Sincronización con panel Operativa bidireccional?                         | Una sola verdad            |
| B7  | ¿Fuera de Estudio el gráfico permite editar niveles?                       | ADR-024 · solo Descubierto |

### 4.4 Opciones gráfico (para votar)

| Opción                        | Descripción                                | Pros                                      | Contras                           |
| ----------------------------- | ------------------------------------------ | ----------------------------------------- | --------------------------------- |
| **B-α Solo lectura + toasts** | G0+G2; sin drag en V1.27                   | Entrega rápida · cero riesgo segundo stop | No compite en «línea editable»    |
| **B-β Drag → Confirm only**   | G4; toda edición durable pasa ticket V1.25 | Alineado integridad                       | Fricción extra                    |
| **B-γ Sandbox + Confirm**     | G3 preview + commit vía G4                 | UX fluida · fail-closed al commit         | Más UI                            |
| **B-δ Protect drag**          | G5 para posición; G4 para apertura         | IBKR-like en gestión                      | Dos reglas; fácil confundir trail |

**Pre-recomendación interna (no decisión):** secuencia **B-α (V1.26b) → B-γ (V1.27)**; posponer B-δ hasta ExitPermission UX clara.

### 4.5 Encargo por auditoría (gráfico)

| Auditor  | Entregar                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------- |
| **A0**   | Opción B-α…δ · mapa estados × interacciones · coherencia con Operative Flow Nivel 1/2                               |
| **N4**   | Qué drag muta qué campo (`initialStop` vs `currentStop` vs `signedStop`) · idempotencia protect · tests invariantes |
| **Deep** | Integración lightweight-charts / capas actuales · performance · accesibilidad pointer-events · riesgo XSS en labels |

**No pedir:** OCO broker · promover trail a stop vigente sin ADR · nueva puerta L1.

---

## 5. Cruce A × B (donde suelen chocar)

| Escenario                                    | Tensión                                             | Pregunta de acuerdo |
| -------------------------------------------- | --------------------------------------------------- | ------------------- |
| DISPARADA + AUTO armado                      | ¿AUTO ejecuta sin pasar por gráfico/Confirm?        | A2 + fase DISPARADA |
| Usuario arrastra stop en gráfico con AUTO on | ¿AUTO respeta `signedStop` humano posterior?        | Orden de autoridad  |
| T1 tocado toast + drag T1                    | ¿Toast es solo informar o CTA reduce?               | H2 + ExitPermission |
| Manual HTTP + niveles gráfico                | HUMAN_MANUAL ignora plan — ¿gráfico oculta niveles? | Honestidad G0       |

**Regla propuesta:** en caso de empate, gana **integridad V1.26** (geometría + firma) sobre comodidad gráfica.

---

## 6. Roadmap propuesto (sujeto a acuerdo §8)

| Epic       | Frente      | Entregables diseño                                         | Fuera                        |
| ---------- | ----------- | ---------------------------------------------------------- | ---------------------------- |
| **V1.26b** | B (parcial) | Toast DISPARADA/T1 · fase en Listas · copy Operativa       | Drag · AUTO ampliado         |
| **V1.27**  | B           | Drag → Confirm (B-γ) · what-if vivo · strip Hoy enlace     | OCO · móvil Mercado completo |
| **V1.28**  | UX          | Palette · hotkeys · densidad                               | Motores                      |
| **V1.29+** | A           | AUTO paridad SEMI (si acordado) · telemetría thaw estricto | Broker live                  |

Secuencia **recomendada:** cerrar tag `v1.26-beta` → acuerdo este estudio → V1.26b → V1.27 gráfico.

---

## 7. Proceso de acuerdo entre auditorías

### 7.1 Fases

```text
R0 Lectura     →  este doc + CURRENT_SYSTEM + relevo V1.26 + contrato Confirm V1.25
R1 Respuestas  →  cada auditoría: plantilla §7.2 ( plazo sugerido: 1 ronda escrita )
R2 Contraste   →  owner publica matriz acuerdo/disenso §8
R3 Resolución  →  owner elige opción + disensos archivados; ADR o enmienda ADR-040 §11 si aplica
R4 Diseño      →  doc hijo `diseno-operativa-auto-grafico-ACORDADO-YYYY-MM-DD.md`
R5 Implement   →  solo tras R4 + CI plan
```

### 7.2 Plantilla de respuesta (copiar por auditoría)

```markdown
## Respuesta — [A0 | N4 | Deep] — Operativa AUTO + Gráfico

**Fecha:** YYYY-MM-DD
**Lector:** …

### AUTO

- Opción elegida: A-α | A-β | A-γ | A-δ | otra: …
- Disensos: …
- Invariantes §2 violadas (si alguna): ninguna | …
- Top 3 riesgos: 1 … 2 … 3 …

### Gráfico

- Opción elegida: B-α | B-β | B-γ | B-δ | otra: …
- Líneas draggables (si aplica): …
- Disensos: …

### Cruce A×B

- …

### Condiciones de implementación

- Tests exigidos: …
- Fuera de alcance explícito: …
```

### 7.3 Criterio de consenso

| Resultado               | Regla                                                                         |
| ----------------------- | ----------------------------------------------------------------------------- |
| **ACUERDO**             | ≥2/3 auditorías eligen la misma opción **y** ninguna marca invariante §2 rota |
| **ACUERDO CON DISENSO** | Mayoría clara + disensos escritos + owner decide en §8                        |
| **SIN ACUERDO**         | Owner aplaza implementación; solo V1.26b (B-α) permitido                      |

---

## 8. Registro de acuerdo (rellenar tras R2)

| Tema                | Opción acordada | Fecha | Disensos archivados | Siguiente doc |
| ------------------- | --------------- | ----- | ------------------- | ------------- |
| AUTO modalidad      | _pendiente_     | —     | —                   | —             |
| AUTO sizing SoT     | _pendiente_     | —     | —                   | —             |
| Gráfico interacción | _pendiente_     | —     | —                   | —             |
| Gráfico → Confirm   | _pendiente_     | —     | —                   | —             |
| V1.26b alcance      | _pendiente_     | —     | —                   | —             |

---

## 9. Anexo — mapa de archivos (Deep)

| Área              | Path                                                                   |
| ----------------- | ---------------------------------------------------------------------- |
| Layout Mercado    | `apps/web/src/components/layout/trading-layout.tsx`                    |
| Operativa cockpit | `apps/web/src/features/trading/operativa-cockpit-card.tsx`             |
| Niveles gráfico   | `apps/web/src/features/charts/operational-plan-chart-levels.ts`        |
| Capa chart        | `apps/web/src/features/charts/chart-operational-plan-levels-layer.tsx` |
| Confirm ticket    | `apps/web/src/features/settings/supervised-f3-panel.tsx`               |
| Risk signature UI | `apps/web/src/features/trading/f3-risk-signature-block.tsx`            |
| Plan view shared  | `packages/shared/src/cognitive/operational-plan-view.ts`               |
| Geometría niveles | `packages/shared/src/cognitive/operational-levels.ts`                  |
| Confirm gate PY   | `packages/py/application/src/bolsa_application/confirm/risk_gate.py`   |
| AUTO execute      | `packages/py/application/src/bolsa_application/execution_router.py`    |
| Modo cuenta UI    | `apps/web/src/features/accounts/demo-book-mode-panel.tsx`              |
| Toasts            | `apps/web/src/features/alerts/alert-toasts.tsx`                        |

---

## 10. Criterio de hecho de **este** estudio

1. Las tres auditorías han respondido con la plantilla §7.2 **o** el owner ha registrado explícitamente «auditoría X declina».
2. §8 tiene filas rellenas con opciones elegidas o «aplazado» justificado.
3. Existe (o está calendarizado) el doc **`diseno-operativa-auto-grafico-ACORDADO-*`** antes de cualquier PR de drag o AUTO ampliado.
4. Ningún participante propone reabrir sizing paralelo `% caja` en SEMI TRIGGERED sin waiver ADR.

---

## 11. Referencias cruzadas

| Doc                                                                                                            | Relación                                          |
| -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| [`contrato-confirm-v125-ticket-2026-08-28.md`](./contrato-confirm-v125-ticket-2026-08-28.md)                   | Norma del ticket — input obligatorio para B-β/B-γ |
| [`audit-brief-estudio-motor-operativo-2026-08-04.md`](./audit-brief-estudio-motor-operativo-2026-08-04.md)     | Precedente de brief multi-auditor                 |
| [`audit-ext-round3-triage-estudio-motor-2026-08-04.md`](./audit-ext-round3-triage-estudio-motor-2026-08-04.md) | Modelo de cierre por triage                       |
| [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md)                     | AUTO estricto sigue abierto                       |
| [`plan-ciclo-a3-wire-auto-arm-ui-2026-08-25.md`](./plan-ciclo-a3-wire-auto-arm-ui-2026-08-25.md)               | Armado AUTO actual                                |
