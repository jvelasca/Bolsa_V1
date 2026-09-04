# RELEVO / ARRANQUE — post-V1.99 · planificar cierre PAPER AUTO (2026-09-04)

> **Padre:** [`engineering-index`](./engineering-index-2026-08-03.md) §68 · [`spec-v199`](./spec-v199-position-management-certification-2026-09-04.md) · [`traspaso-relevo-v1-99`](./traspaso-relevo-v1-99-position-management-certification-2026-09-04.md).  
> **Para quién:** el **siguiente agente de ingeniería** (Plan Mode). **No** es arranque de auditor externo.  
> **Partida tip:** [`v1.99-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.99-beta) → [`bf57899b`](https://github.com/jvelasca/Bolsa_V1/commit/bf57899b) · pre-release publicada · Release-tag CI en curso ([run 33847460567](https://github.com/jvelasca/Bolsa_V1/actions/runs/33847460567)) · push CI Python/Frontend GREEN en el tag.  
> **Auditoría vigente:** el usuario mantiene la **auditoría externa actual** (V1.99 tip). Este relevo **no** abre implementación; pide un **plan** del resto para finalizar PAPER AUTO.

---

## 0. Por qué cambiar de chat

V1.94→V1.99 cerró el arco de **integridad + T2 + trail coexistencia + certificación de gestión de posición**.

El motor ya puede representar y certificar:

```text
OPEN → STOP nacimiento → T1 → TRAIL×N ⇄ T2 → TRAIL → EXIT
```

con log = verdad, stage derivado, lineagePath last-wins, `initialRisk` inmutable.

Lo que **falta para finalizar la parte PAPER AUTO** ya **no** es otra capa FSM. Es decidir y planificar:

1. ENGINE FREEZE (cuando tip V1.99 + auditor PASS)
2. DEMO execute operable (sin default-on)
3. **V2.0 Operational UX / AUTO Desk en MERCADO**

Este documento es el **brief de planificación**. El siguiente agente debe producir un **plan** (spec/plan borrador o plan Cursor), **sin** implementar código todavía salvo que el usuario lo pida después.

---

## 1. Copia esto en el chat nuevo (agente planificador)

```text
Eres el siguiente agente de ingeniería de Bolsa V1.

MISIÓN: elaborar un PLAN (no implementar aún) de lo que queda para FINALIZAR
la parte PAPER AUTO / operativa diaria, partiendo del tip v1.99-beta → bf57899b.

Contexto sellado:
- V1.98: trail + T2 coexistence (FSM alineado con ExitPolicy)
- V1.99: Position Management Certification G1–G8 (solo tests + docs; 0 cambios TRANSITIONS)
- Freeze vigente: NO LIVE · PAPER_D_EXECUTE off · no bump 1.35.0-beta · no Alembic · no unificar ledger
- El usuario mantiene la auditoría externa actual; no inventes PASS de auditor

Lee OBLIGATORIO:
1. docs/CURRENT_SYSTEM.md
2. docs/engineering/traspaso-relevo-post-v199-plan-cierre-paper-auto-2026-09-04.md  (este relevo)
3. docs/engineering/spec-v199-position-management-certification-2026-09-04.md
4. docs/engineering/arranque-auditor-v1-99-position-management-certification-2026-09-04.md
5. docs/adr/043-position-automation.md
6. docs/adr/023-camino-d-thaw.md (PAPER_D_EXECUTE)
7. packages/shared/src/cognitive/mercado-cockpit-phase.ts
8. packages/py/application/src/bolsa_application/paper_desk_cycle.py
9. packages/py/application/src/bolsa_application/execute_position_policy_auto.py
10. docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md (baseline UX MERCADO)

ENTREGABLE:
- Un plan por fases (recomendado numerar V2.0.x o F1–Fn), con:
  · objetivo de cada fase
  · IN / OUT explícitos
  · dependencias (tip CI GREEN, auditor PASS, ENGINE FREEZE)
  · archivos/áreas tocadas (aprox.)
  · criterio de cierre medible
  · riesgos / no-regresión (FSM, outbox, integrity)
- Preguntas de producto SOLO si bloquean el plan (máx. 1–2)
- NO escribir código · NO abrir LIVE · NO proponer rediseño del lifecycle kernel
- NO pedir otra certificación FSM salvo residuales documentados

Verdad de producto a preservar:
  event log = verdad · stage = derivado · lineagePath ≠ historia
  Una sola autoridad de salida (ExitPolicy → lifecycle), sin motor paralelo
  MERCADO = centro operativo (candidato → entrada → stop → T1 → T2 → trail → salida)
```

---

## 2. Estado real (qué ya está “hecho” vs qué no)

### 2.1 Motor PAPER AUTO — HECHO (certificado / certificable)

| Capa                                      | Estado | SoT                 |
| ----------------------------------------- | ------ | ------------------- |
| ExitPolicy T1/T2/trail_width              | DONE   | `exit_policy` TS/Py |
| Position AUTO execute (policy→JIT→Router) | DONE   | ADR-043             |
| PaperDeskCycle + Golden Session           | DONE   | V1.53–V1.55         |
| Lifecycle event store + outbox + worker   | DONE   | V1.86–V1.93         |
| Financial integrity + opening veto        | DONE   | V1.94–V1.96         |
| T2 atomicity crash/retry                  | DONE   | V1.97 = V1.99 G7    |
| Trail ⇄ T2 coexistence                    | DONE   | V1.98               |
| Position management goldens G1–G8         | DONE   | V1.99 `bf57899b`    |

### 2.2 Producto PAPER AUTO — NO FINALIZADO

| Hueco                              | Por qué bloquea “acabado”                                                                                                     |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **MERCADO UX AUTO Desk**           | Fases cockpit siguen SEMI (`descubierto…confirmada…posicion`); no muestran el journey entry→stop→T1→T2→trail→“qué hago ahora” |
| **`PAPER_D_EXECUTE` off**          | Correcto en repo; falta camino DEMO local documentado/probado **fuera de pytest** sin fingir LIVE                             |
| **Sin DeskRunner**                 | Un ciclo de sesión, no scheduler multi-día (aceptado; no reabrir salvo producto)                                              |
| **SEMI protect → `TRAIL_APPLIED`** | Residual: Confirm protect solo PositionRevision; SEMI y AUTO no cuentan la misma historia de trail en el log                  |
| **Tip ritual V1.99**               | Tag + release hechos; Release-tag CI en curso; stamp tip + PASS auditor **pendientes**                                        |

### 2.3 OUT consciente (NO meter en el plan como P0)

- LIVE / thaw estricto Accept / bump package
- `open` → TRAIL / T2 antes de T1
- LineagePath → flags `has_trail`+`has_t2`
- Persistir cuarteto Initial/Current/Realized/Remaining Risk (salvo como **derivado UX** de datos ya existentes)
- Unificar lifecycle accounting ↔ cash ledger
- Auto-heal · E2E browser obligatorio · HTTP golden de 8 ratchets vía Confirm

---

## 3. Mapa objetivo que el plan debe servir

Visión auditor / producto (post-ENGINE FREEZE):

```text
MERCADO (centro)
│
├── Listas / candidatos     ¿qué puedo comprar hoy?
├── Gráfico                 entrada · stop · T1 · T2 · trail visibles
├── Operativa AUTO          arm · dryRun · kill switch · estado honesto
└── Posición viva
       ├── Entrada / Initial Stop / Initial Risk (inmutable)
       ├── T1 (trigger · qty% · executed)
       ├── T2 (trigger · qty% · executed)
       ├── Trailing (activation · anchor · distance · ratchet)
       └── Salida / remaining / “qué hacer ahora”
```

Respuestas en ~5 s sin saltar a Asesor / Hoy / Consola / Decision Spine.

**Regla de arquitectura:** leer del **event log + PositionState + ExitPolicy**; no inventar un segundo FSM en frontend.

---

## 4. Fases candidatas (borrador para que el plan refine)

El planificador debe **aceptar, partir o reordenar**; esto es punto de partida, no spec.

| ID     | Nombre                           | Objetivo                                                                                                                                            | Dependencia          |
| ------ | -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| **P0** | Tip V1.99 + ENGINE FREEZE        | Release-tag GREEN · stamp docs · (auditor PASS si aplica) · congelar FSM/outbox/integrity                                                           | CI run tip           |
| **P1** | Honesty DEMO execute             | Runbook local `PAPER_D_EXECUTE=1` + arm + un ciclo paper-desk real · copy arm≠execute · kill switch visible                                         | P0                   |
| **P2** | AUTO Desk surface (MERCADO)      | Modelo de fase posición viva (entry/stop/T1/T2/trail/exit) · HUD/panel que conteste las 5–9 preguntas · fuente = snapshot lifecycle + PositionState | P0                   |
| **P3** | Wire residual SEMI protect→TRAIL | Opcional pero integrity-adjacent si SEMI+AUTO comparten mesa                                                                                        | P0; puede ir tras P2 |
| **P4** | Risk readout UX                  | Mostrar Initial vs Current protected vs Realized **derivado** (sin schema nuevo si se puede)                                                        | P2                   |
| **Px** | Explicit OUT                     | LIVE · scheduler · lineage flags · ledger unify · bump                                                                                              | —                    |

---

## 5. Preguntas de producto que el plan puede necesitar (máx. 2)

Si el planificador pregunta, priorizar:

1. **¿V2.0 empieza por UX MERCADO (P2) o por DEMO execute runbook (P1)?**  
   Recomendación default: P0 freeze → P2 UX (diferencial) en paralelo a P1 runbook corto.
2. **¿SEMI protect→TRAIL es P3 de esta fase o residual post-V2.0?**  
   Recomendación default: P3 pequeño tras P2 si no ensucia el freeze del kernel.

No preguntar LIVE, bump, ni rediseño FSM.

---

## 6. Pre-flight tip (para el planificador / stamp)

```bash
# Tip
git rev-parse v1.99-beta^{commit}   # expect bf57899b…

# Cert domain
uv run pytest packages/py/domain/tests/test_lifecycle_position_management_v199.py \
  packages/py/analytics/tests/test_position_state.py::test_v199_trail_and_reduce_preserve_initial_risk \
  packages/py/application/tests/test_lifecycle_position_management_v199_g7.py -q

# Mirror TS
cd apps/web && npx vitest run e2e/helpers/lifecycle-fsm.test.ts
```

Release-tag: https://github.com/jvelasca/Bolsa_V1/actions/runs/33847460567  
Pre-release: https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.99-beta

Tras GREEN: stamp `CURRENT_SYSTEM` + `traspaso-relevo-tag-v1-99-beta-*.md` (mismo ritual que V1.98). **Eso puede ser P0 del plan o un commit docs inmediato en otro chat.**

---

## 7. Freeze que el plan debe repetir

- Confirm = firma (SEMI) · AUTO no sustituye honestidad dryRun
- `PAPER_D_EXECUTE` **default off** en repo
- **NO LIVE** · sin bump `1.35.0-beta`
- **No** cambiar `TRANSITIONS` salvo residual documentado y acotado (P3)
- **No** unificar ledger · **no** auto-heal · **no** motor paralelo de salida

---

## 8. Criterio de éxito del PLAN (no de la implementación)

El plan está bien si al leerlo se entiende:

1. Qué falta exactamente para decir “PAPER AUTO operativa finalizada”
2. Qué queda **fuera** (LIVE, scheduler, etc.)
3. Orden de fases con dependencias tip/auditor/freeze
4. Que MERCADO/AUTO Desk es el centro, no otra consola
5. Que el kernel V1.98/V1.99 no se reabre

---

## 9. Next inmediato

1. **Este chat / agente:** Plan Mode → plan V2.0 / cierre PAPER AUTO (usando §1).
2. En paralelo o justo antes: esperar Release-tag **GREEN** del tip y stamp docs V1.99.
3. Auditoría externa: seguir con arranque V1.99; **no** mezclar V2.0 en la respuesta del auditor.
4. **Implementación:** solo tras plan aprobado por el usuario.

---

## 10. Índice de archivos clave

| Rol            | Path                                                                                                      |
| -------------- | --------------------------------------------------------------------------------------------------------- |
| SoT corto      | `docs/CURRENT_SYSTEM.md`                                                                                  |
| Cert V1.99     | `docs/engineering/spec-v199-*.md` · `packages/py/domain/tests/test_lifecycle_position_management_v199.py` |
| FSM kernel     | `packages/py/domain/src/bolsa_domain/lifecycle/__init__.py`                                               |
| AUTO execute   | `packages/py/application/src/bolsa_application/execute_position_policy_auto.py`                           |
| Desk cycle     | `packages/py/application/src/bolsa_application/paper_desk_cycle.py`                                       |
| Gate execute   | `packages/py/application/src/bolsa_application/paper_d_propose.py` · `paper_auto_http_gate.py`            |
| Cockpit phases | `packages/shared/src/cognitive/mercado-cockpit-phase.ts`                                                  |
| Diseño MERCADO | `docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md`                                               |
| ADR AUTO       | `docs/adr/043-position-automation.md`                                                                     |
| Este relevo    | `docs/engineering/traspaso-relevo-post-v199-plan-cierre-paper-auto-2026-09-04.md`                         |
