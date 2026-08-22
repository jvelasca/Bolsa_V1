# Premisas de proyecto — Bolsa V1

> **AsOf:** 2026-08-22  
> **Qué es:** reglas de producto y de ingeniería que aplican a **todo** el monorepo.  
> **Para quién:** equipo, auditores externos, quien retome el código.  
> No sustituye ADRs: las ADRs deciden arquitectura; estas premisas fijan _cómo se trabaja y se documenta_.

---

## ⭐ PREMISAS ESENCIALES ACTUALES (2026-08-22) — leer primero en TODO trabajo

> **AsOf:** 2026-08-22 · **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) rama **`main`**. SHA vivo = `git fetch && git rev-parse origin/main` → **`478e504`**. Tag **`v1.5.0-beta` → `5e52bd6`** · tag **`v1.3.0` → `b778292`** intacto · **BETA / NO en producción**.
> **Contexto:** R-9 · R-10/v1.2.1 · R-11/v1.3.0 **CERRADAS**. Relevo UNO+DOS del plan post-v1.3.0 **EJECUTADOS** (`f7a4ab0`, `f7a86cc`). Ciclo vivo: **R-12** (`docs/engineering/plan-r12-auditoria-ux-2026-08-21.md`).
> **Ancla anti-alucinación:** `docs/engineering/estado-verificado-auditoria-vs-main-2026-08-21.md`. Una auditoría externa del 2026-08-21 evaluó `75e8c23` (14 commits atrás de `49ecbcd`); una re-auditoría posterior evaluó ~`49ecbcd` y **no ve** Relevo UNO/DOS. El SHA que un agente debe usar es **`origin/main` + `PROJECT_STATE.md` / backlog §0**, no un SHA histórico incrustado en un traspaso.
> **Idea del proyecto (invariante de producto):** embudo backtesting científico → IA gobernada (LLM propone, motor determinista decide) → confirmación humana → paper. Integridad financiera y trazabilidad son el valor central. Se puede refactorizar lo que haga falta **mientras se preserve esa idea**.

### Ciclo R-12 (refuerza E1–E9; no las sustituye)

- **GitHub es la fuente de coordinación.** Un cambio no existe para el equipo hasta estar en `origin/main`. Working tree local ≠ estado. Tras cada push: actualizar firma en `PROJECT_STATE.md` y backlog §0; verificar `git rev-parse origin/main`.
- **Subagentes para todo cambio de código.** El coordinador no implementa fases enteras en un hilo saturado. Máx. ~3 subagentes en paralelo, alcances **disjuntos**.
- **Relevo de chat:** al saturarse, cerrar y abrir otro pegando el `traspaso-relevo-*` + firma (HEAD GitHub, rama, árbol, tag, batería, deuda no-regresión). Riesgo de alucinación objetivo: 0 (documento manda).
- **Higiene E8 continua:** residuos de test/dev se eliminan por path canónico; módulos/docs obsoletos se archivan o se marcan históricos; no se purga `pending-delete` de riesgo alto sin decisión.
- **Track B APROBADO** (2026-08-21, línea a línea). Track C: plan [`engineering/plan-r12-track-c-frontend-2026-08-21.md`](./engineering/plan-r12-track-c-frontend-2026-08-21.md). **C1–C5** (`0eb8976`) + leftover CORE-R **`8dd3caf`** + copy E8 **`ce601c9`**. Gates: **R12-409** `eb24608` · **EXEC-B-CONC** `ca60d0a` · **R12-SCHED** `5e52bd6` · **R12-ACCOUNTS** `3c958f1` · **R12-AUTH F1–F10 + F8b** (`5e7c67b` · `2cd20b0` · `837ec85`) · ADR-027 **Aceptado**.
- **Gates no auto-abiertos:** purge `pending-delete` ventana métricas (E8 sigue N) — plan [`plan-r12-pending-delete-v2-purge-2026-08-22.md`](./engineering/plan-r12-pending-delete-v2-purge-2026-08-22.md). (R12-AUTH **F1–F10 + F8b** **cerrados en `main`** — no reabrir sin fase.)

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

_Premisas vivas: al añadir una regla transversal, enlázala en §0 y anúnciala en [HELP.md](./HELP.md) / [README.md](./README.md)._
