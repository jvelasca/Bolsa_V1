# Premisas de proyecto — Bolsa V1

> **AsOf:** 2026-08-03  
> **Qué es:** reglas de producto y de ingeniería que aplican a **todo** el monorepo.  
> **Para quién:** equipo, auditores externos, quien retome el código.  
> No sustituye ADRs: las ADRs deciden arquitectura; estas premisas fijan _cómo se trabaja y se documenta_.

---

## 0. Índice de premisas

| Premisa                                        | Documento                                                                                                                       |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Documentar todo** (docs + código)            | §1 de este archivo · [code-documentation-standard](./engineering/code-documentation-standard-2026-08-03.md)                     |
| UI configurable → `localStorage`               | [UI_PREFS_LOCALSTORAGE.md](./UI_PREFS_LOCALSTORAGE.md)                                                                          |
| Responsive (chart / trading)                   | [RESPONSIVE_PREMISES.md](./RESPONSIVE_PREMISES.md)                                                                              |
| Cuentas DEMO vs Paper                          | [account-premises-demo-vs-paper-2026-07-31.md](./engineering/account-premises-demo-vs-paper-2026-07-31.md)                      |
| Backtesting DÍA D                              | [backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md)                              |
| LAB ≠ TRADING                                  | [ADR-019](./adr/019-dual-universes-lab-vs-trading.md) · [diseño](./engineering/dual-universes-lab-trading-design-2026-08-02.md) |
| Freeze post-auditorías                         | [post-audit-decision-freeze-2026-08-03.md](./engineering/post-audit-decision-freeze-2026-08-03.md)                              |
| Orquestación / relevo / anti-alucinación (R-8) | §4 de este archivo · [plan R-8](./engineering/plan-r8-prevencion-riesgo-2026-08-20.md)                                          |

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
