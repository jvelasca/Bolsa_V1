RELEVO / TRASPASO — D3 Lab/Radar fuera del spine (ADR-019) CONFIRMADA → apertura fase siguiente

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT**. La decisión **D3** (`Lab/Radar fuera del spine`, ADR-019) queda **CONFIRMADA y registrada en la documentación de estado** (docs-only, sin código), ya **commiteada** (`ea0c93f`). La fase siguiente **la decide el propietario** a partir del backlog. Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **Fase 0 Decision Spine — TODAS las decisiones CERRADAS** (D1 · D2 `f7b1f6c` · Escalón 3/D1 `7530556` · **D3 CONFIRMADA**) · **Cierre deuda confirm SEMI CERRADA y pushada** (`2281903` + `a264b60`) · Track B B0–B12 cerrado.
> **SHA al cerrar este hilo:** commits sobre `origin/main` en este hilo = **`ea0c93f`** (docs D3). Partida al cerrar = `origin/main == HEAD == ea0c93f`, working tree **limpio**. (**Nota:** `ea0c93f` está **sin pushear** — pendiente decisión del propietario de push a `main`.)

---

## 1. Qué está hecho (alcance de esta rebanada — CLI-COMMITTED)

El propietario confirmó la fase = **D3**, opción **(a)** `Lab/Radar fuera del spine` (ADR-019), como rebanada **docs-only** (sin código, sin `contract:gen`, sin mover componentes).

### Decisión confirmada

> **D3: Lab/Radar quedan FUERA del spine (ADR-019).** El Decision Spine gobierna **solo el universo TRADING** (Dato→Evidencia→DecisionPackage→Gate/Risk→fill). Lab/Radar (Laboratorio `/backtests` → `BacktestsRouteSlot`, Research, Radar/Señales `/screeners`) son **universo paralelo que recomiendan** (evidencia/oportunidad) y **no** entran en la columna autoritativa de decisión.

### Deltas verificados (docs, `git diff`)

- **`docs/engineering/fase0-decision-spine-descarga-2026-08-24.md`** §3 — fila **D3**: `⏳ recomendada (a) — pendiente confirmación` → `✅ ACEPTADA (a) — Lab/Radar FUERA del spine` (decisión propietario, 2026-08-24). Nota infra-D1 actualizada: D2 y D3 ya no bloquean; F0.5/F0.6 CERRADAS (F0.5b `3670a09` · F0.6b `8df8a65` · F0.6-UI `672e88f`).
- **`docs/engineering/traspaso-relevo-escalon-3-d1-cierre-apertura-siguiente-2026-08-24.md`** — tabla de decisiones: fila **D3** ⏳ → `✅ CONFIRMADA (a)`. Nota §38 «instrucción para el nuevo chat» actualizada (D3 ya confirmada; deuda confirm SEMI cerrada; no reabrir F0.5/F0.6/D2/Esc.3/D1/Cierre deuda confirm SEMI).
- **`docs/engineering/engineering-index-2026-08-03.md`** — línea F0.4: `D2/D3 pendientes` → `D2 CERRADA con código (f7b1f6c) · D3 CONFIRMADA (a: Lab/Radar fuera del spine)` (se corrigió de paso un mojibake `SÍMI`→`SEMI`).
- **`docs/engineering/PROJECT_STATE.md`** — bloque estado general (actualiza `main` → `a264b60`, añade D3 CONFIRMADA y cierre deuda confirm SEMI commitado) + **nuevo bloque «D3 CONFIRMADA (docs-only)»** junto a D2/Esc.3/D1, que cierra con «las decisiones de la Fase 0 Decision Spine (D1, D2, Esc.3/D1, D3) quedan todas cerradas».

> El hook pre-commit (`lint-staged` → prettier) reformateó ligeramente la tabla de la descarga durante el commit; el contenido de la decisión quedó intacto.

## 2. Batería / verificación

| Check                                                                 | Resultado                                           |
| --------------------------------------------------------------------- | --------------------------------------------------- |
| Rebanada **docs-only** (0 código, 0 contrato, 0 migración)            | ✅                                                  |
| `git diff` revisado por el coordinador (4 archivos)                   | ✅ 12 ins / 11 del (prettier)                       |
| Lints (4 archivos editados)                                           | **0**                                               |
| Coherencia con ADR-019 / AS-IS F0.1 (Lab/Backtests = fuera del spine) | ✅ sin editar ADR (decisión, no nueva arquitectura) |
| Commit                                                                | `ea0c93f` — **pendiente push**                      |

## 3. Qué NO tocar (freeze)

- Motor money / ledger / `ExecuteTrade` internals.
- Belief / gobernanza IA · `contract:gen` salvo fase pactada · Track B B1–B12.
- `pending-delete` · no `regen_full`. Purge storage E8 N.
- Fase 0 Decision Spine (F0.5b · F0.6 backend+UI · D2 · Escalón 3/D1) · **Cierre deuda confirm SEMI** · **D3**: ya cerrados y verificados; NO reescribir salvo fase pactada que exponga un hueco real.
- `order_intent.py` (mapping default `exit_hint`/`reduce`→`sell`): corregirlo ahí sería una fase separada con auditoría de call-sites.

## 4. Tarea del siguiente chat (fase nueva — SIN aprobar)

**PASO 0 (obligatorio, sin código):** el propietario decide (a) si **pushea** `ea0c93f` a `main` (si no lo hizo) y (b) **qué fase sigue**. El agente solo presenta opciones ancladas al backlog y espera decisión. NO abrir código antes.

Candidatos registrados (a partir del backlog §0, PROJECT_STATE §3 y DEUDA §4):

- **Ops (backlog §4, FUERA de repo, no bloquea código):** activar **GitHub secret scanning** nativo · definir **`TRUSTED_PROXIES` prod** (bloqueado por IPs reales del usuario) · corregir en BD **`BP/.L`→`BP.L`** (dato corrupto, F-WORKER-1) · limpiar **`logs/dev`** locales.
- **Deuda diferida por freeze/decisión:** `pending-delete` de **riesgo alto** (no tocar hasta `purge storage` E8 N) · gobernanza IA · **F9/V2** (requiere ADR + diseño + decisión explícita del propietario).
- **Otros (a decidir):** **Unificación Research→Radar** (`plan-unificacion-research-radar-2026-08-21.md`, DRAFT/APARCADO — requiere decisión para abrir fases de código; enlaza con D3: Lab/Radar fuera del spine confirma que son universo laboratorio) · F-IND-1 residual (causalidad indicadores; NOTA en F2) · limpieza residuos históricos dev (`m7-win-*`, `M2 *`).

**Después (con fase aprobada):** implementar la rebanada acordada, una a la vez, path:line verificado, batería, verificador read-only (alcance disjunto), aprobación del propietario antes de commit.

## 5. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO: Fase 0 Decision Spine — TODAS las decisiones CERRADAS (D1 risk cesta SEMI=AUTO
sin override; D2 f7b1f6c DecisionPackage=contrato; Escalón 3/D1 7530556 VETO cesta
fail-closed; D3 CONFIRMADA Lab/Radar FUERA del spine ADR-019). Cierre deuda confirm SEMI
CERRADA y pusheada (2281903 + a264b60: Bug1 wait sin sell default, Bug2 side de exit/reduce
desde package). Rebanada docs D3 commiteada localmente = ea0c93f (PENDIENTE de push a main).
Working tree limpio a excepción de que ea0c93f sigue sin pushear.
LEE (read-first, obligatorio): backlog §0 + PROJECT_STATE §3 + PROJECT_PREMISES ⭐§0.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.

TAREA: PRIMERO -> el propietario decide (a) si pusheo ea0c93f a main y (b) QUÉ FASE SIGUE (E1).
Candidatas registradas: ops backlog §4 (secret scanning UI, TRUSTED_PROXIES prod, BP/.L->BP.L
en BD, limpiar logs/dev — fuera de repo, no bloquea código); deuda diferida (pending-delete alto
hasta purge storage, gobernanza IA, F9/V2 con ADR+decisión); Unificación Research->Radar
(plan DRAFT/APARCADO, requiere decisión). NO lanzo agentes ni código hasta aprobar la fase y su
alcance.
DESPUÉS -> rebanada acotada, path:line verificado, batería, verificador read-only
(alcance disjunto), aprobación del propietario antes de commit.

NO TOCAR: money/ledger/ExecuteTrade internals, gobernanza IA, contract:gen salvo fase pactada,
Track B B1-B12 (cerrado), pending-delete (E8 N), regen_full sin decisión,
order_intent.py (mapping default exit/reduce->sell, fase dedicada con auditoría de call-sites).
NO REABRIR: Fase 0 Decision Spine (F0.5/F0.6/F0.6-UI/D2/Escalón 3/D1) ni Cierre deuda
confirm SEMI (todas cerradas).

Protocolo: subagente acotado + verificador read-only, alcance disjunto, batería,
aprobación del propietario antes de commit.
```
