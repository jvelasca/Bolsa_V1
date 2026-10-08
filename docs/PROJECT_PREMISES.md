# Premisas de proyecto — Bolsa V1

> **AsOf:** 2026-08-22 · **AsOf (operativa §5):** 2026-10-03 · **AsOf (prioridades de producto §6):** 2026-10-08  
> **Qué es:** reglas de producto y de ingeniería que aplican a **todo** el monorepo.  
> **Para quién:** equipo, auditores externos, quien retome el código.  
> No sustituye ADRs: las ADRs deciden arquitectura; estas premisas fijan _cómo se trabaja y se documenta_.

---

## ⭐ PREMISAS ESENCIALES ACTUALES (2026-08-22) — leer primero en TODO trabajo

> **AsOf:** 2026-08-22 · **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) rama **`main`**. SHA vivo = `git fetch && git rev-parse origin/main` → **`5edbcb5`**. Tag **`v1.5.0-beta` → `5e52bd6`** · tag **`v1.3.0` → `b778292`** intacto · **BETA / NO en producción**.
> **Contexto:** R-9 · R-10/v1.2.1 · R-11/v1.3.0 · **R-12 CERRADAS**. Relevo UNO+DOS ejecutados. Ciclo vivo: **R-13** (`docs/engineering/plan-r13-consolidacion-beta-2026-08-22.md`).
> **Ancla anti-alucinación:** `docs/engineering/estado-verificado-auditoria-vs-main-2026-08-21.md`. Una auditoría externa del 2026-08-21 evaluó `75e8c23` (14 commits atrás de `49ecbcd`); una re-auditoría posterior evaluó ~`49ecbcd` y **no ve** Relevo UNO/DOS. El SHA que un agente debe usar es **`origin/main` + `PROJECT_STATE.md` / backlog §0**, no un SHA histórico incrustado en un traspaso.
> **Idea del proyecto (invariante de producto):** embudo backtesting científico → IA gobernada (LLM propone, motor determinista decide) → confirmación humana → paper. Integridad financiera y trazabilidad son el valor central. Se puede refactorizar lo que haga falta **mientras se preserve esa idea**.

### Ciclo R-13 (refuerza E1–E9; no las sustituye)

- **GitHub es la fuente de coordinación.** SHA de partida R-13: **`5edbcb5`**. Verificar `git rev-parse origin/main`. Working tree ≠ estado.
- **Serie por defecto.** Una fase = un subagente. Paralelo solo con ficheros disjuntos y sin pisar estado vivo. Tests en cada fase de código. Coordinador re-verifica file:line + batería (no se fía del reporte).
- **Relevo de chat:** al saturarse, cerrar y abrir otro pegando `traspaso-relevo-r13-apertura-2026-08-22.md` + firma. Documento manda.
- **R-12 CERRADA** (reparación post-auditoría). No repetir gates ni AUTH ya en `main`.
- **Track B producto BLOQUEADO** (god-page / Research→Radar) hasta OK línea a línea.
- **Gates no auto:** purge `pending-delete` (E8 N, ventana V2) · apply F7b prod · tag `v1.6.0-beta` · `PAPER_D_EXECUTE` · gobernanza IA · `contract:gen` salvo fase.

### Ciclo R-12 (histórico — CERRADO 2026-08-22)

R-12 entregó Track A–C, R12-409, EXEC-B-CONC, R12-SCHED, R12-ACCOUNTS, R12-AUTH F1–F10+F8b–F8e, F7b local, F7c, JWT-only. Plan: [`engineering/plan-r12-auditoria-ux-2026-08-21.md`](./engineering/plan-r12-auditoria-ux-2026-08-21.md). Relevo histórico: `traspaso-relevo-r12-apertura-2026-08-21.md`.

### E1. Nada se implementa sin plan aprobado

- Todo cambio de código corre bajo el **plan profundo R-9** (o fase acotada explicitada) aprobado por el **propietario/usuario**.
- **No** se lanza implementación "en caliente"; primero se documenta la fase, el alcance, la batería y el riesgo en `/docs`.
- Cualquier alteración de contrato HTTP / esquema DB / DTO compartido se tramita como **fase propia** (nunca colateral de otra).

### E2. Ejecución por subagentes acotados (control de contexto y saturación)

- **Una fase = un subagente acotado** con brief explícito (contexto, archivos exactos, qué **NO** tocar, batería esperada, obligación de escribir el resultado en backlog/traspaso).
- **Máx. ~3 subagentes en paralelo por chat** y con **alcances disjuntos** (ficheros distintos). Inyectar en cada brief el **mapa de consumidores/llamadas ya verificado** para que no re-descubran call-sites ni alucinen.
- El coordinador (agente principal) **nunca** se fía del reporte de un subagente: contrasta cada diff/resultado contra el código y la batería reales antes de proponer commit.
- Si el contexto de un chat se satura, **cerrar el hilo** y abrir otro **pegando el texto de relevo** (doc + bloque de estado verificado), nunca adivinar el estado de memoria.

### E3. Anti-alucinación / anti-pérdida de contexto

- Todo hallazgo, commit, test o resultado afirmado por un subagente se **verifica contra código/datos reales (file:line)**. Sin evidencia reproducible → se rechaza y se re-pide.
- En cada relevo de chat se genera un **texto de paso** con **estado verificado** (HEAD, rama, árbol, CI) para que el siguiente chat arranque sin asumir.
- **Documento manda**: si un subagente reporta algo que contradice el backlog/PROJECT_STATE, el **documento** es fuente de verdad y se reconsidera antes de tocar código.

### E4. Aprobación del usuario por commit

- No auto-commitear ni auto-pushear. Cada commit se propone y se espera aprobación explícita del propietario.
- Rama `main` **protegida**: push requiere aprobación nativa.

### E5. Documentación y DOCSTRINGS obligatorios

- Todo cambio relevante se documenta en la capa que corresponde: `docs/` para producto/decisión/auditoría/ADR; **docstring de módulo + símbolos públicos** al crear/tocar código (norma del [code-documentation-standard](./engineering/code-documentation-standard-2026-08-03.md)).
- Medirlos con `python scripts/research/docstring_coverage_report.py` cuando se toque una zona.
- Los cambios de contrato HTTP se reflejan en schemas + OpenAPI y, si aplica, en `API_REFERENCE.md`.

### E6. Tests / scripts de verificación en cada fase

- **Toda corrección lleva su TEST o SCRIPT de verificación**, no solo "el código compila". Especialmente para: idempotencia, concurrencia/locking, rollback, invariantes de ledger, migración desde DB limpia y desde DB existente, arranque multi-worker, aislamiento entre cuentas.
- La batería mínima por fase (§4 de este archivo) es **obligatoria** y la re-verifica el coordinador.

### E7. La integridad financiera y la separación de cuentas son el objetivo inmediato

- Antes de ampliar ML/IA o features nuevas se cierra el núcleo financiero determinista (R-9): idempotencia aislada por cuenta, request-fingerprint, orden de custody-commit, invariantes DB, validación estricta de DTOs.
- **No tocar salvo decisión explícita:** gobernanza IA · `pending-delete` de riesgo alto. (**R-8C.2 / R12-SCHED** cerrado `5e52bd6` — no reabrir layout de workers sin fase.)

### E8. Limpieza de código/doc obsoleto (criterio §4 de este archivo)

- Solo se elimina lo que cumple: **0 imports** en `apps/`+`packages/` (excl. tests que validan el alias) · **no depende de storage/localStorage** por nombre · battery/typecheck verdes tras quitar.
- Código/documentos obsoletos se mueven/marcan (no se pierde evidencia) y se revisan los que ya no reflejan la realidad (p. ej. deuda ya resuelta).

### E9. Backlog como fuente de verdad del "trabajo por delante"

- `docs/engineering/backlog-trabajo-2026-08-20.md` **es** la única fuente de verdad del estado de fases. Leer antes de abrir (read-first) y actualizar al cerrar (update-last). Igual para `PROJECT_STATE.md`.

---

## 0. Índice de premisas

| Premisa                                               | Documento                                                                                                                                               |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **PREMISAS ESENCIALES ACTUALES (E1–E9 + ciclo R-12)** | ⭐§0-este-archivo · [plan R-12](./engineering/plan-r12-auditoria-ux-2026-08-21.md) · [plan R-9](./engineering/plan-r9-refactor-hardening-2026-08-20.md) |
| **Documentar todo** (docs + código)                   | §1 de este archivo · [code-documentation-standard](./engineering/code-documentation-standard-2026-08-03.md)                                             |
| UI configurable → `localStorage`                      | [UI_PREFS_LOCALSTORAGE.md](./UI_PREFS_LOCALSTORAGE.md)                                                                                                  |
| Responsive (chart / trading)                          | [RESPONSIVE_PREMISES.md](./RESPONSIVE_PREMISES.md)                                                                                                      |
| Cuentas DEMO vs Paper                                 | [account-premises-demo-vs-paper-2026-07-31.md](./engineering/account-premises-demo-vs-paper-2026-07-31.md)                                              |
| Backtesting DÍA D                                     | [backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md)                                                      |
| LAB ≠ TRADING                                         | [ADR-019](./adr/019-dual-universes-lab-vs-trading.md) · [diseño](./engineering/dual-universes-lab-trading-design-2026-08-02.md)                         |
| Freeze post-auditorías                                | [post-audit-decision-freeze-2026-08-03.md](./engineering/post-audit-decision-freeze-2026-08-03.md)                                                      |
| Orquestación / relevo / anti-alucinación (R-8)        | §4 de este archivo · [plan R-8](./engineering/plan-r8-prevencion-riesgo-2026-08-20.md)                                                                  |
| **Operativa AUTO/PAPER (ventana forward + `DÍA-D AUTO`)** | §5 de este archivo · [runbook de la ventana](./engineering/runbook-ventana-forward-v2.78-2026-09-27.md) · [criterio de salida `-beta`](./engineering/criterio-salida-beta-2026-10-01.md)                                                       |
| **Prioridades de producto (operativa diaria · entrada/salida · estrategia/indicadores · DÍA-D)** | §6 de este archivo · [auditoría operativa diaria](./engineering/auditoria-operativa-auto-fase-2-2026-10-08.md)                                           |

Entrada auditoría: [audit-pack-post-audits-2026-08-03.md](./engineering/audit-pack-post-audits-2026-08-03.md).  
Índice ingeniería (docs): [engineering-index-2026-08-03.md](./engineering/engineering-index-2026-08-03.md).  
Round 2 externas: [audit-ext-round2-triage-2026-08-03.md](./engineering/audit-ext-round2-triage-2026-08-03.md).  
**Round 3 — motor Estudio (ratificado O3-C):** [audit-ext-round3-triage-estudio-motor-2026-08-04.md](./engineering/audit-ext-round3-triage-estudio-motor-2026-08-04.md) · [ADR-022](./adr/022-estudio-daily-opinion-motor.md).  
Brief de entrada (histórico): [audit-brief-estudio-motor-operativo-2026-08-04.md](./engineering/audit-brief-estudio-motor-operativo-2026-08-04.md).  
Respuesta auditoría 1 (gaps A/B): [audit1-response-ingest-fie-2026-08-03.md](./engineering/audit1-response-ingest-fie-2026-08-03.md).

---

## 1. Premisa — Documentar todo (producto **y** código)

### Regla

**Todo cambio relevante se documenta en la capa que corresponde.** No se considera “hecho” un feature o fix de dominio si solo existe el código.

| Capa                            | Obligatorio                                                | Dónde                                                                                                       |
| ------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Producto / decisión / auditoría | Sí, si cambia comportamiento visible, contratos o política | `docs/` · HELP · trackers · ADR si aplica                                                                   |
| Contrato HTTP                   | Sí (schemas + OpenAPI)                                     | `bolsa_api/schemas/*` · [API_REFERENCE.md](./API_REFERENCE.md) si el endpoint es público                    |
| Comportamiento interno          | Sí (forward-only)                                          | **Docstrings** de módulo y símbolos públicos · JSDoc en exports de `@bolsa/shared` / helpers de dominio     |
| Ops / flags                     | Sí                                                         | [github-credentials-and-ops.md](./engineering/github-credentials-and-ops.md) §9 · freeze si cambia política |

### Docstrings / JSDoc

Detalle normativo: [code-documentation-standard-2026-08-03.md](./engineering/code-documentation-standard-2026-08-03.md).

Resumen:

1. Al **crear o tocar** código público: docstring de módulo + de clase/función pública (Python); JSDoc breve en exports de dominio (TS).
2. **Forward-only:** no reescribir histórico solo por docs (misma filosofía que no reescribir \(K\)).
3. Lotes 1–4 de cobertura Lab/API/application **cerrados** (2026-08-03); lo nuevo sigue la regla al tocarse.
4. Medición: `python scripts/research/docstring_coverage_report.py`.

### Qué no exige esta premisa

- Docstring en cada getter trivial, test o componente UI puramente presentacional.
- Duplicar un ADR dentro del código (el docstring dice _qué hace_; el ADR _por qué del sistema_).
- Documentar secretos, tokens o `.env` reales en el repo.

### Consecuencia para PRs

Un PR que introduce API, use-case, indicador o ruta nueva **incluye** docs de producto/HELP si cambia la experiencia, **y** docstrings/JSDoc en los símbolos públicos tocados.

---

## 2. Otras reglas globales (recordatorio)

- Identificadores de código/commits en **inglés**; UI y docs de producto en **español**.
- Decisiones de arquitectura → ADR en `docs/adr/`.
- BD = fuente de verdad de mercado/ledger; Yahoo/XTB solo actualizan.
- API por defecto: Python `:8000`.
- Preferencias UI → `localStorage` ([premisa](./UI_PREFS_LOCALSTORAGE.md)).

---

## 3. Visibilidad del repositorio

Repo GitHub: `https://github.com/jvelasca/Bolsa_V1` — **público** (2026-08-03) para que auditorías externas lean código + `docs/` sin invitación.

Secretos (`.env`, tokens, `.secrets/`) **nunca** van al remoto. Ver [github-credentials-and-ops.md](./engineering/github-credentials-and-ops.md).

---

## 4. Premisa — Orquestación, relevo de chat y anti-alucinación (ratificada R-8, 2026-08-20)

> Norma transversal para **toda** ejecución multi-fase con subagentes. Ratifica protocolos ya dispersos
> (`backlog-trabajo-*.md §5`, `PROJECT_STATE.md §5`, `engineering-index` protocolo recurrente) como premisa única
> de proyecto. Detalle y fases: [`engineering/plan-r8-prevencion-riesgo-2026-08-20.md`](./engineering/plan-r8-prevencion-riesgo-2026-08-20.md).

### Reglas

1. **Read-first obligatorio.** Cada chat/subagente lee `engineering/backlog-trabajo-2026-08-20.md` §0 y §1 antes de tocar nada. Si no coincide con el repo → **parar y re-leer**; nunca seguir por inercia.
2. **Una fase = un subagente acotado** + brief explícito (contexto, archivos exactos, alcance/qué NO tocar, batería esperada, órden de escribir el resultado en el backlog/traspaso al terminar).
3. **El subagente no se auto-aprueba.** El coordinador revisa diff + batería antes de proponer commit al usuario.
4. **Aprobación del usuario por commit.** No auto-commitear sin aprobación.
5. **Batería mínima por fase:** py → `ruff check packages/py apps/api-python --config pyproject.toml` (0) · mypy de ficheros en gate CI · pytest de la zona · `git status` acotado; web → `pnpm --filter @bolsa/web typecheck`+`lint`+`build` (+`test` si toca FE); global → `pnpm test` + CI + `contract:check` si se toca contrato.
6. **Control de saturación:** máx. ~3 subagentes en paralelo por chat. Si el contexto se llena, **cerrar el hilo** y abrir otro pegando el texto de relevo del traspaso + backlog.
7. **Verificación adversarial anti-alucinación:** cualquier afirmación de un subagente (file:line, commit, test, resultado) se contrasta **contra código/datos reales** antes de aceptarla. Sin evidencia reproducible → se rechaza.
8. **Firma de estado en cada relevo:** todo texto de traspaso incluye bloque "estado verificado" (HEAD, rama, árbol, CI) para que el siguiente chat arranque sin adivinar.

### Criterio de borrado de código/doc obsoleto (fase R-8D)

1. Cero imports en `apps/` + `packages/` (excl. tests que solo validan el alias).
2. No hay lectura de storage/localStorage que dependa del nombre.
3. Battery / typecheck verdes tras quitar.
   (Patrón: `engineering/pending-delete/README.md`.)

---

## 5. Premisa — Operativa AUTO/PAPER (ventana forward + bucle de realimentación `DÍA-D AUTO`)

> **Ratificada 2026-10-03** (tramo `v2.88.30`…`v2.88.34`). Gobierna **cómo se opera y se mide** el motor
> AUTO en `PAPER` — **sin tocar el motor**. Comandos: [runbook de la ventana](./engineering/runbook-ventana-forward-v2.78-2026-09-27.md) §0/§10/§11 ·
> entorno: [arranque de la ventana PAPER](./engineering/arranque-ventana-paper-operativa-2026-09-27.md).
> Vía a **versión estable**: [criterio de salida de `-beta`](./engineering/criterio-salida-beta-2026-10-01.md) (`G1`–`G7`).

### 5.1 Reglas duras

1. **Operar ≠ programar.** La ventana `PAPER` es una fase **operativa**: **no** se bajan umbrales, **no** se
   fuerza el gobernador, **no** se backdatea `created_at`.
2. **El cubo de calendario sale del reloj de pared.** `sim_fill_finance_context.created_at` es material
   **durable**; un replay/sandbox (reloj inyectado) **no** fabrica cubos ⇒ `≥4 días` / `≥2 episodios` /
   `≥32 ciclos` (`P3-2`/`P3-3`) **solo** se acreditan **operando días reales**.
3. **Freeze por hash, fail-closed.** El runner pinnea el **árbol de código** por hash
   (`git rev-parse "HEAD:apps" "HEAD:packages"`); si el árbol se mueve declara `TREE_MOVED` y **aborta**.
   Re-anclar el freeze es parte de **cada** sello que mueve el árbol.
4. **Un hueco no es un cero.** Un dato no medido viaja `NO MEDIDO`/`None`, **nunca** `0` (`0` = «no pasó
   nada», que **sí** es una medición). Aplica al Monitor AUTO, al `DÍA-D AUTO` y al feedback por valor.
5. **Advisory.** El feedback y los paneles **informan**; el humano decide. No cambian motor, umbrales,
   `TOP_N`, allocation ni pesos A/B. La detección de divergencia de software es **heurística** (pasos
   deterministas), **no** una prueba de bug.
6. **Nada peligroso armado por accidente.** `LIVE_EXECUTION_UNLOCKED` **off** · `PAPER_D_EXECUTE` **off** ·
   thaw **no** · kill switch y `checkExitPermission` con sus suites verdes.
7. **Interruptores solo en el `env` del proceso hijo.** `AUTO_ENGINE_SIM_REAL_PRICE` (**`1`** en la ventana
   PAPER — precio real medido; **`0`** en el sandbox `DÍA-D AUTO` — precio inyectado) y
   `AUTO_OPERATIONAL_AUDIT=1` (hechos durables) se inyectan **solo** en el entorno del proceso; exportarlos
   en la shell contamina las suites PG (precio ausente ⇒ `HOLD` fail-closed ⇒ **falso rojo**).

### 5.2 `DÍA-D AUTO` — bucle de realimentación por valor (advisory, read-only)

El `DÍA-D AUTO` (`v2.88.33`/`v2.88.34`) sitúa el motor en una **ventana `D0..D1`** con reloj/precio
inyectados y stores **en memoria** (cuarentena). Por cada instrumento agrega lo **declarado** (replay
hermético), lo **ejecutado** (hechos durables, leídos read-only) y el **OOS real** posterior, emite un
**veredicto** `CONFIRMED`/`MIXED`/`REFUTED`/`NOT_MEASURED` y un **catálogo de errores**
`SOFTWARE`/`OPERATIONAL`/`DATA` (vocabulario existente de `auto_reason_codes`/`market_operability`), lo
sirve por `GET /api/auto/dia-d-feedback[/{window}]` (read-only) y lo pinta en `/auto-monitor` (sub-vista
**«Feedback por valor»**).

- **`Δ motor = 0`:** no se edita `auto_simulation_worker.py` ni ningún módulo congelado; el barrido los
  **conduce** con stores en memoria.
- **El suelo de muestra se declara, no se relaja** (`MIN_VALUE_CYCLES = 5`): muestras pequeñas ⇒
  `NOT_MEASURED` será **frecuente**.
- **El veredicto se recalcula sin cambiar código** en cuanto la ventana PAPER opere esos `D`.
- **El gate global `window_gate` sigue siendo la autoridad** sobre la ventana; el veredicto por valor es
  un **complemento**, no un sustituto.

---

## 6. Premisa — Prioridades de producto (operativa diaria · entrada/salida · estrategia/indicadores · DÍA-D)

> **Ratificada 2026-10-08** (propietario). Fija **qué es prioritario** en el producto. Complementa §5
> (que gobierna **cómo se opera y se mide** AUTO/PAPER) y no la sustituye. Origen: reorden de la FASE 3
> tras la [auditoría operativa FASE 2](./engineering/auditoria-operativa-auto-fase-2-2026-10-08.md) y su
> [plan (PARKED)](./engineering/plan-cierre-operativa-auto-2026-10-08.md).

El foco de producto son **cuatro prioridades**, por este orden. Toda mejora se juzga por si acerca a
ellas; la completitud contable retrospectiva **no** es el objetivo (es deuda declarada, §6.3).

### 6.1 Las cuatro prioridades

| # | Prioridad | Qué significa | Verificación (falsable) |
| --- | --- | --- | --- |
| **P1** | **Operativa ganadora en rango diario** | La operativa objetivo gana en **timeframe diario**; es la vara de producto. | Existe evidencia con R/expectancy en la ventana diaria, citando su `K` y su intervalo de confianza. |
| **P2** | **Claridad del punto de entrada y salida** | Toda propuesta/posición indica de forma **inequívoca** el punto/zona de **entrada** y el de **salida** (stop y objetivo) en primer nivel, sin que el usuario interprete el gráfico. | La superficie de primer nivel muestra entrada y salida; si falta una, se declara «Sin dato todavía». |
| **P3** | **Estrategia confirmada con los mejores indicadores** | La operativa se apoya en una estrategia **confirmada por evidencia**, y los **indicadores detectados** que la sustentan son visibles como razón. | La superficie declara la estrategia y los indicadores que la sustentan; sin confirmación, se declara. |
| **P4** | **Evaluación DÍA-D** (sobre todo) | La comparación **declarado vs ejecutado vs OOS real** es la comprobación central de que la estrategia se sostiene; ninguna operativa se da por buena sin re-medir DÍA-D. | El veredicto DÍA-D (`CONFIRMED`/`MIXED`/`REFUTED`/`NOT_MEASURED`) se recalcula y se cita con su ventana. |

### 6.2 Invariante preservado (no es prioridad nueva)

La separación estricta **SIM/virtual vs dinero real XTB** (§5.1 · `apps/web/src/features/auto/auto-reality.ts`)
sigue vigente y **no** la relajan estas prioridades.

### 6.3 Qué mueve P1–P4 (y qué no)

- **Mueve:** claridad de entrada/salida a primer nivel, visibilidad de estrategia e indicadores que la
  sustentan, y la **re-medición DÍA-D** como criterio de confianza.
- **No mueve (deuda declarada):** `PortfolioDecision` durable, materialización de posición por operación
  y P&L realizado agregado. El [plan de cierre de motor](./engineering/plan-cierre-operativa-auto-2026-10-08.md)
  queda **PARKED**; se retoma **solo si** un pilar P1–P4 lo exige.
- **Regla dura:** ninguna prioridad se resuelve fabricando datos. Sin medición ⇒ «Sin dato todavía» (§5.1.4).

---

_Premisas vivas: al añadir una regla transversal, enlázala en §0 y anúnciala en [HELP.md](./HELP.md) / [README.md](./README.md)._
