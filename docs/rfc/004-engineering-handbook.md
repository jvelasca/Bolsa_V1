---
id: rfc-004
title: Engineering Handbook
status: approved
date: 2026-07-21
audience: development, data, ml, qa, ops
complements:
  - docs/rfc/000-ubiquitous-language.md
  - docs/rfc/001-artifact-catalog.md
  - docs/rfc/002-capability-model.md
  - docs/rfc/003-architecture.md
---

# RFC-004: Engineering Handbook

> **Propósito:** Convertir RFC-000…003 en **reglas de ingeniería obligatorias** y verificables (imports, estructura, tests, DoD, checklist de PR).  
> **Principio:** Si una regla de arquitectura no se puede revisar en PR o automatizar en CI, no existe.  
> **Alcance:** Disciplina de implementación. **No** redefine Domain/Artifact/Capability/Architecture.

---

## 1. Filosofía de ingeniería

| Principio | Implicación |
|-----------|-------------|
| **Domain First** | Nombres y fronteras = RFC-000…002; no “como salga el framework”. |
| **Monolith First** | Un proceso API + workers; no microservicios por dominio. |
| **Registry First** | Definiciones en registries/envelope; storage vía adapters. |
| **Adapter First** | Infra (PG, Redis, broker, Ollama) detrás de Protocol/ABC. |
| **Test First (crítico)** | Caps/ART nuevos o cambios de compute → tests antes o en el mismo PR. |
| **No Framework-Driven Design** | FastAPI/React/Zustand no dictan el modelo de negocio. |
| **Verification > Memory** | Linters/tests > convenciones orales. |

---

## 2. Estructura oficial del repositorio (congelada hoy)

### 2.1 Raíz (obligatoria)

```
apps/
  web/                 # React + Vite (UI)
  api-python/          # FastAPI (orquestación HTTP fina)
packages/
  shared/              # @bolsa/shared — contratos TS
  database/            # Prisma tooling / migraciones
  py/
    domain/            # bolsa_domain
    application/       # bolsa_application
    analytics/         # bolsa_analytics
    market/            # bolsa_market
    infrastructure/    # bolsa_infrastructure
    ai/                # reserva AIGOV (hoy lógica en analytics.research.llm_*)
docs/
  rfc/  adr/  sessions/ …
scripts/
tests/                 # o tests bajo cada package (ambos OK)
```

**Prohibido** como top-level de negocio: `utils/`, `helpers/`, `services/`, `models/` genéricos sin Domain ID.

### 2.2 Mapeo package → capas / caps (actual)

| Package import | Capas / rol | Caps (aprox.) |
|----------------|-------------|-----------------|
| `bolsa_domain` | entidades / VOs | transversal Trading + policies |
| `bolsa_application` | use cases / orquestación CAP | application (único orquestador) |
| `bolsa_analytics` | STRATEGY, RESEARCH, RUNTIME parcial, FEATURE compute/cache | `CAP-STRAT-*`, `CAP-QUANT-*`, `CAP-FEAT-*` parcial |
| `bolsa_market` | DATA ingest | `CAP-DATA-INGEST/SYNC` |
| `bolsa_infrastructure` | INFRA adapters | PG, Redis, queues, HTTP externals |
| `bolsa_api` (`apps/api-python`) | HTTP | no lógica de mercado profunda |
| `@bolsa/shared` | contratos | DTOs / V1 types |
| futuro `ai_governance` / `packages/py/ai` | AIGOV | `CAP-AI-*` (F1) |

### 2.3 Evolución de carpetas (opcional, gradual)

Extraer `execution/`, `feature_registry/`, `ai_governance/` desde analytics/application **está permitido** solo con:

1. Enmienda menor a este RFC (tabla §2.2).
2. Sin big-bang rename del monorepo.
3. Mismas reglas de import.

**No** se exige adoptar árboles ficticios `bolsa_platform/strategy_engine/` en un solo PR.

---

## 3. Reglas de imports (núcleo del handbook)

### 3.1 Matriz (packages Python actuales)

| Origen | Puede importar | **Prohibido** |
|--------|----------------|---------------|
| `bolsa_domain` | stdlib, typing; **cero** I/O | `bolsa_infrastructure`, `bolsa_analytics`, `bolsa_application`, `bolsa_api`, SDKs LLM, LightGBM/torch en domain |
| `bolsa_market` | `bolsa_domain`, infra **solo vía** application/infra patterns ya usados; preferir no acoplar OMS | `bolsa_application` execution paths, LLM SDKs |
| `bolsa_analytics` | `bolsa_domain`, libs numéricas | `openai`/`ollama` SDK en módulos de **signals/execution**; preferir puerto AIGOV. **No** importar brokers live |
| `bolsa_application` | domain, analytics, market, infrastructure (orquestación) | Decidir trades llamando LLM; no saltar Policy Gate |
| `bolsa_infrastructure` | drivers externos | reglas de trading / `bolsa_analytics.signals` como dueño de negocio |
| `bolsa_api` | application, schemas, shared contracts | reimplementar backtest/OMS en routers |
| módulos `ai_*` / `llm_*` (AIGOV) | schemas/DTOs, infra HTTP | **cualquier** camino a `PendingOrder` / OMS / Intent approval |

### 3.2 Reglas absolutas (CI)

1. **Kernel / Execution path ↛ AI:** código que emite órdenes o evalúa Intent **no** importa `openai`, `ollama`, ni `bolsa_analytics.research.llm_*`.
2. **Signal ↛ Order:** ningún módulo crea `PendingOrder` desde un `SignalEvent` sin Recommendation + Intent (aunque sea orquestado en application).
3. **Feature compute ↛ OMS.**
4. **UI (`apps/web`)** no calcula PnL/backtest canónico; consume API.

### 3.3 Contrato import-linter (target)

Archivo objetivo: `packages/py/.importlinter` (o raíz). Ejemplo:

```ini
[importlinter]
root_packages =
    bolsa_domain
    bolsa_application
    bolsa_analytics
    bolsa_market
    bolsa_infrastructure

[importlinter:contract:domain-purity]
name = domain no importa infra ni analytics
type = forbidden
source_modules =
    bolsa_domain
forbidden_modules =
    bolsa_infrastructure
    bolsa_analytics
    bolsa_application
    openai
    ollama

[importlinter:contract:no-ai-in-hot-path]
name = application execution paths no importan LLM
type = forbidden
source_modules =
    bolsa_application
forbidden_modules =
    openai
    ollama
# Nota: excluir/acotar módulos llm_* cuando se muevan a ai_governance;
# hasta F1, prohibir openai/ollama en application y domain.
```

Hasta existir el linter en CI: **checklist PR §12** es la puerta.

---

## 4. Puertos y adapters (obligatorio para I/O nuevo)

Nuevas dependencias externas → `typing.Protocol` o `abc.ABC` en borde de dominio/application; implementación en `bolsa_infrastructure` (o adapter dedicado).

| Puerto | CAP / capa | Implementaciones |
|--------|------------|------------------|
| `IFeaturePort` | FEATURE | Redis/PG/Parquet adapters (`FeatureCache` → online adapter) |
| `IPredictionPort` | RUNTIME | heurística rating; LightGBM futuro |
| `IBrokerAdapter` | EXECUTION | Paper / Live / mock XTB |
| `AIGovernanceProxy` | AIGOV | Ollama / OpenAI / none+heurística |

**Regla:** el dominio no instancia el cliente Redis/HTTP; recibe el puerto.

---

## 5. Convenciones de nombres

| Elemento | Convención | Ejemplo |
|----------|------------|---------|
| Packages | `bolsa_*` | `bolsa_domain` |
| Domain IDs / CAP / ART | mayúsculas estables RFC | `CAP-STRAT-EVAL`, `ART-SIGNAL` |
| DTOs shared | `*Dto`, `*V1` | `SignalEventV1` |
| Events | Past participle / Raised | `SignalRaised`, `IntentApproved` |
| Use cases | `Run*`, `Enqueue*`, `Create*` | `RunSmaGridOptimize` |
| Repositories | `*Repository` Protocol | `OhlcvRepository` |
| Adapters | `*Adapter` | `RedisFeatureAdapter` |
| Status lifecycle | RFC-001 inglés | `Production` no `ACTIVE` en código **nuevo** |

---

## 6. Convenciones Artifact (RFC-001)

- Envelope común al serializar a registry/manifest.
- `checksum` = SHA-256 del payload canónico (JSON ordenado / bytes del modelo).
- Versión: SemVer para defs (`StrategyDefinition`, FeatureDef, Prompt); content-hash OK para snapshots.
- Lifecycle: solo estados RFC-001; flag `disabled` para kill-switch.
- Nuevo `ART-*` → enmienda RFC-001 **en el mismo PR** (o PR previo).

---

## 7. Convenciones Event (RFC-003)

- Envelope §6.2 de RFC-003 (`eventId`, `eventType`, `domain`, `capability`, `traceId`, `payload`, `artifactRefs`).
- Naming: `*Raised` / `*Created` / `*Approved` / `*Filled` / `*Completed`.
- Idempotencia: consumidores toleran reentrega (`eventId` único).
- Persistencia: proyectar a `PlatformEvent` cuando exista tipo; mapear legacy sin rename forzado.

---

## 8. Convenciones API

| Tema | Regla |
|------|-------|
| Estilo | REST + OpenAPI (FastAPI) |
| Envelope respuesta | Preferir `{ "data": ... }` existente |
| Errores | HTTP status + body estable; no filtrar stack al cliente en prod |
| Paginación | `limit`/`cursor` o page ya usados; documentar en OpenAPI |
| Auth | middleware existente; rutas públicas mínimas (`/api/health`) |
| No | Endpoints que ejecuten LLM y disparen órdenes en la misma request |

---

## 9. Testing

### 9.1 Pirámide

| Nivel | Qué | Velocidad | I/O |
|-------|-----|-----------|-----|
| **Unit** | domain, rules, sizing, policy puro | &lt; 50 ms | no red/disco |
| **Golden** | indicadores, señales, backtest snippets, authoring JSON | media | fixtures |
| **Integration** | adapters PG/Redis, API routes | &lt; 2 s típico | test DB / mocks |
| **Contract** | shared TS ↔ Python schemas | CI | — |
| **E2E / Paper** | Signal→…→Paper fill | suite &lt; 30 s–minutos | staging |
| **Performance** | chart-perf / scans | bajo demanda | — |

### 9.2 Golden tests (prioridad)

Obligatorios al tocar:

- compute de indicadores / features
- `SignalEvent` / rules engine
- backtest determinista
- draft authoring (heurística + schema LLM)

### 9.3 Cobertura orientativa

- Lógica pura de dominio/analytics crítica: **≥ 80%** líneas tocadas en el PR (no exigir 80% global inmediato).
- Frontend: tests en componentes críticos cuando cambie contrato shared.

**Regla:** PR que añade `CAP-*` o muta `ART-*` de producción → unit/golden en el mismo PR.

---

## 10. Calidad y herramientas

| Herramienta | Uso |
|-------------|-----|
| **ruff** | lint/format Python |
| **mypy** | tipado (strict en domain) |
| **pytest** | tests Python |
| **tsc** | `@bolsa/shared`, `@bolsa/web` |
| **pre-commit** (recomendado) | ruff + typecheck selectivo |
| **import-linter** (F1+) | §3.3 |
| **scripts/lint_semantic.py** (futuro) | anti-sinónimos RFC-000, lifecycle `ACTIVE`→`Production` |

Umbrales: CI rojo = no merge. Coverage gate global opcional hasta estabilizar.

---

## 11. Releases y promoción

Alineado al lifecycle de artefactos (RFC-001):

```
feature branch → review → Validated (CI) → Production (merge/release)
```

| Cambio | SemVer (cuando versionemos releases) |
|--------|--------------------------------------|
| Rompe contrato API/evento | MAJOR |
| Nueva CAP/endpoint compatible | MINOR |
| Fix | PATCH |

Release notes: listar `ART-*`/`CAP-*` tocados y manifests relevantes si hay modelos/policies en Production.

---

## 12. Definition of Done

Una historia está **Done** cuando:

1. Compila / typecheck OK (`shared`, `web`, packages py tocados).
2. Tests relevantes verdes (unit/golden/integration según alcance).
3. Sin violaciones de import (§3) conocidas.
4. Docs: README/sesión solo si hace falta; **RFC/ADR si cambia constitución o decisión**.
5. OpenAPI actualizado si hay endpoint nuevo.
6. No introduce IA en hot path ni rompe Signal→Recommendation→Intent→Order.
7. PR revisado (o auto-review consciente en proyecto individual).

---

## 13. Architecture Decision Checklist (obligatorio en PR)

Responder en la descripción del PR (o marcar N/A):

| # | Pregunta | Si SÍ → |
|---|----------|---------|
| 1 | ¿Nuevo concepto de dominio / palabra? | Enmienda **RFC-000** |
| 2 | ¿Nuevo `ART-*` o lifecycle? | Enmienda **RFC-001** |
| 3 | ¿Nuevo `CAP-*` / cambio de custodia? | Enmienda **RFC-002** |
| 4 | ¿Nuevo plano, evento de dominio o puerto? | Enmienda **RFC-003** |
| 5 | ¿Nueva regla de import / package? | Enmienda **RFC-004** |
| 6 | ¿Rompe deps entre dominios (RFC-002)? | **Bloquear** salvo ADR + enmienda RFC |
| 7 | ¿Nueva dependencia externa significativa? | **ADR** |
| 8 | ¿Nuevo almacenamiento / adapter? | **ADR** (o RFC-005 si Feature) |
| 9 | ¿IA / LLM en hot path (OMS/Intent/Order)? | **Rechazar** |
| 10 | ¿Signal/Prediction → Order directo? | **Rechazar** |
| 11 | ¿Cambia contrato shared? | Actualizar `@bolsa/shared` + consumidores |
| 12 | ¿Golden tests afectados? | Actualizar fixtures / aceptar delta consciente |

---

## 14. Checklist mínimo de PR (copia rápida)

```
[ ] Typecheck / tests verdes
[ ] Imports OK (sin LLM en execution/kernel path)
[ ] Cadena Trading respetada
[ ] Checklist §13 respondido
[ ] RFC/ADR si aplica
[ ] Sin ART-*/CAP-* huérfanos
```

---

## 15. Deprecación

| Etapa | Acción |
|-------|--------|
| Anuncio | `@deprecated` + doc; preferir alias |
| Convivencia | ≥ 1 release menor o 90 días |
| Eliminación | solo con verificación de no consumidores |

No borrar `CAP-*`/`ART-*` en Production sin métricas/logs de no uso.

---

## 16. Criterios de aceptación de este RFC

- [x] Documento en `docs/rfc/004-engineering-handbook.md`
- [x] Estructura **real** del monorepo congelada + evolución gradual
- [x] Matriz de imports + reglas absolutas
- [x] Ports/adapters, naming, artifact/event/API
- [x] Testing (golden) + calidad + releases
- [x] DoD + Architecture Decision Checklist + PR checklist
- [ ] (Posterior) `.importlinter` + `lint_semantic` en CI
- [x] (F1+) `.importlinter` en `packages/py/.importlinter` (domain purity + no openai/ollama fuera de `bolsa_ai`)
- [ ] (Posterior) pre-commit hook opcional

---

## 17. Próximo paso

Con **RFC-000…004** la constitución fundacional de ingeniería está completa.

Siguiente en pirámide: **RFC-005 Feature Registry & IFeatureAdapter**.  
Paralelo suave: **F1** `AIGovernanceProxy` + Ollama (sin tocar EXECUTION).

---

## 18. Enmiendas

Cambios a estructura top-level, matriz de imports o DoD requieren PR a este RFC.

---

*Integra filosofía/checklist A1, isolation/ports/import-linter A2 y testing/releases A3; anclado al monorepo real `packages/py/*` + `apps/*`.*
