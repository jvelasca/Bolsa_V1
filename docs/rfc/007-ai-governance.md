---
id: rfc-007
title: AI Governance (Proxy, Prompt Registry, Guardrails)
status: approved
date: 2026-07-21
audience: development, ai, product, compliance, security
complements:
  - docs/rfc/000-ubiquitous-language.md
  - docs/rfc/001-artifact-catalog.md
  - docs/rfc/002-capability-model.md
  - docs/rfc/003-architecture.md
  - docs/rfc/004-engineering-handbook.md
  - docs/rfc/005-feature-registry.md
  - docs/rfc/006-data-contracts-and-lineage.md
---

# RFC-007: AI Governance

> **Propósito:** Gobernar toda interacción con LLMs: **AIGovernanceProxy** (único entrypoint), **Prompt Registry** (`ART-PROMPT`), **DraftV1**, **LLMCall** audit, guardrails, costes y aislamiento del hot path.  
> **Principio:** La IA **authoring / explanation** — nunca decide ni envía órdenes. Consume contratos RFC-006; no los redefine.  
> **Alcance:** Capa 7 (`AIGOV`), caps `CAP-AI-PROXY`, `CAP-AI-AUTH`, `CAP-AI-EXPLAIN`. ML tabular (LightGBM) queda fuera (RUNTIME/RESEARCH).

---

## 1. Principios

| Principio | Regla |
|-----------|--------|
| **Proxy First** | Ningún módulo importa `openai`/`ollama` SDK fuera del proxy/adapters AIGOV |
| **Execution Path Isolation** | Salida LLM ≠ Order/Intent/OMS; máximo → Draft → humano/policy determinista |
| **Structured Enclosure** | Authoring emite JSON tipado (schema); texto libre solo explanation UI |
| **Prompt as Artifact** | Prompts = `ART-PROMPT` versionados + checksum; no strings sueltos en prod |
| **Audit Every Call** | Cada invocación → `ART-LLM-CALL` (append-only) |
| **Fallback Always** | Heurística local (`none` / prompt_catalog) si LLM falla o presupuesto agotado |
| **Cost & Safety Controlled** | Budget, timeout, rate limit, PII mask, injection defense |
| **Lineage Injection** | Toda respuesta propaga `traceId`, `promptId`, provider, modelName |

---

## 2. AIGovernanceProxy

Única puerta de entrada/salida para modelos generativos.

```
Caller (RESEARCH / UI / application authoring)
        │ Prompt + variables + response_schema_ref
        ▼
┌─────────────────────────────────────────────┐
│ AIGovernanceProxy                           │
│ 1. Resolve ART-PROMPT (registry)            │
│ 2. Input guardrails (injection, PII, topic) │
│ 3. Inject traceId + lineage AI fields       │
│ 4. Route provider (ollama \| openai \| none)│
│ 5. Output guardrails (JSON schema + retry)  │
│ 6. Persist ART-LLM-CALL                     │
└───────────────┬─────────────┬───────────────┘
                ▼             ▼
         OllamaAdapter   OpenAIAdapter
                │
                ▼ (none)
         HeuristicFallback
```

### 2.1 Interfaz pública (Python)

```python
class AIGovernanceProxy(Protocol):
    def generate_structured_spec(
        self,
        *,
        prompt_template_id: str,
        variables: dict[str, Any],
        response_schema: dict[str, Any] | type,  # JSON Schema o modelo Pydantic
        timeout_seconds: int = 30,
        max_cost_usd: float = 0.01,
        trace_id: str | None = None,
        allow_cloud: bool = False,
    ) -> DraftV1: ...

    def generate_explanation(
        self,
        *,
        artifact_ref: str,  # predictionId / recommendationId
        context: dict[str, Any],
        prompt_template_id: str,
        timeout_seconds: int = 15,
        trace_id: str | None = None,
    ) -> str: ...

    def get_status(self) -> dict[str, Any]: ...
```

Caps: `generate_structured_spec` → `CAP-AI-AUTH`; `generate_explanation` → `CAP-AI-EXPLAIN`; routing/audit → `CAP-AI-PROXY`.

### 2.2 Proveedores

| Provider | Env | Rol |
|----------|-----|-----|
| `ollama` | `BOLSA_LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL` | **Preferido** local (F1: Qwen2.5-Coder 14B / Llama 3.1 8B) |
| `openai` | `BOLSA_LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `BOLSA_LLM_MODEL` | Cloud opcional (ya cableado) |
| `none` | `BOLSA_LLM_PROVIDER=none` | Solo heurística |

Default: `ollama` si reachable; si no → `none`. Cloud solo si `allow_cloud` y clave presente.

---

## 3. Prompt Registry (`ART-PROMPT`)

Envelope RFC-001 + payload:

| Campo | Descripción |
|-------|-------------|
| `systemPrompt` | instrucciones fijas |
| `userTemplate` | plantilla `{{var}}` |
| `inputVariables` | lista tipada |
| `outputSchemaRef` | ref a schema (`StrategyDefinitionV1`, Indicator draft, …) |
| `modelSettings` | provider default, model, temperature, maxTokens |
| `examples` | few-shot opcionales |
| `schemaVersion` | contrato del prompt payload |

Prompts canónicos iniciales:

| prompt id | Uso | Salida |
|-----------|-----|--------|
| `prompt_strategy_authoring_v1` | NL → estrategia | Draft strategy |
| `prompt_indicator_authoring_v1` | NL → indicador/feature | Draft indicator |
| `prompt_explanation_prediction_v1` | explicar Prediction | texto |
| `prompt_explanation_recommendation_v1` | explicar Recommendation | texto |

Lifecycle: Draft → … → Production (RFC-001). Solo Production (o Experimental en research) usable vía proxy en UI producto.

---

## 4. DraftV1 (`ART-DRAFT`)

| Campo | Descripción |
|-------|-------------|
| `draftId` | |
| `draftType` | `strategy` \| `indicator` \| `feature` |
| `promptId`, `promptVersion` | |
| `provider`, `modelName` | |
| `schemaVersion` | |
| `content` | objeto candidato (StrategyDefinition / IndicatorSpec / FeatureDef) |
| `validationStatus` | `pending` \| `validated` \| `rejected` |
| `validationErrors` | |
| `traceId`, `llmCallId` | |
| `reviewer`, `reviewedAt`, `promotedTo` | post-humano |

### 4.1 Promoción

```
UI prompt → CAP-AI-AUTH → Draft (Draft)
  → humano valida sintaxis/semántica
  → promote → ART-STRATEGY / ART-FEATURE-DEF / Indicator catalog
  → reject → Archived
```

**Nunca** Draft → Intent/Order.

---

## 5. LLMCall (`ART-LLM-CALL`)

Append-only. Campos: `provider`, `model`, `promptTemplateId`, `promptRendered` (redactado si PII), `responseRaw`/`responseParsed`, `validationPassed`, `elapsedMs`, `costUsd`, `status`, `error`, `traceId`, `causationId?`, `producer.version`, `timestamp`.

No se borran; retención según política ops (mínimo: no purge automático en F1).

---

## 6. Guardrails

### 6.1 Input (pre)

- Prompt injection / override de system prompt  
- PII / secrets masking (API keys, credenciales broker)  
- Temas prohibidos (manipulación, etc.) — lista configurable  
- Rate limit  
- No enviar posiciones/cuentas reales a cloud salvo flag explícito futuro  

### 6.2 Output (post)

- Validación JSON Schema / Pydantic  
- Self-correction loop: máx. **2** reintentos con error de parseo  
- Tras fallo → `AIGovernanceValidationError` + fallback heurístico (authoring) o error claro (no inventar Draft inválido)

### 6.3 Costes (defaults)

| Parámetro | Default | Env |
|-----------|---------|-----|
| Max cost / call | 0.01 USD | `BOLSA_LLM_MAX_COST_USD` |
| Daily budget | 1.00 USD | `BOLSA_LLM_DAILY_BUDGET_USD` |
| Timeout | 30 s | `BOLSA_LLM_TIMEOUT_SECONDS` |

Budget excedido → modo `none` hasta reset diario.

---

## 7. Aislamiento (refuerzo RFC-002/004)

| Prohibido | Permitido |
|-----------|-----------|
| `execution` / OMS importar AIGOV | application authoring → Proxy |
| LLM en scan hot loop | Authoring on-demand; explanation post-hoc |
| LLM → Order | Draft → humano → Strategy → Kernel |
| Strategy Kernel import openai | solo Protocol/DTO de Draft |

---

## 8. Lineage AI (extiende RFC-006)

En `LineageBlock` / LLMCall / Draft:

```yaml
promptId: string
promptVersion: string
llmCallId: string
llmProvider: ollama|openai|none
llmModelName: string
```

Events opcionales: `DraftCreated`, `LlmCallCompleted` (fuera hot path).

---

## 9. Migración desde código actual

| Hoy | Target |
|-----|--------|
| `bolsa_analytics.research.llm_draft` / `llm_indicator_draft` | adapters detrás del Proxy |
| `OPENAI_API_KEY` + `BOLSA_LLM_MODEL` | provider `openai` |
| Heurística `prompt_catalog_*` | Fallback `none` |
| APIs `draft-from-prompt` | orquestación application → Proxy (misma API externa OK) |
| `packages/py/ai` (`bolsa_ai`) | **implementado** — Proxy, registry, adapters, audit |

F1 no requiere Feature Registry runtime completo; authoring valida contra catálogo de indicadores/estrategias **existente**.

---

## 10. Fase F1 (implementación)

1. Paquete/módulo `ai_governance` (o `packages/py/ai`) con Proxy + PromptRegistry (YAML/PG bootstrap).  
2. `OllamaAdapter` + `OpenAIAdapter` + `HeuristicFallback`.  
3. Envolver endpoints draft existentes.  
4. Persistir `ART-LLM-CALL` (tabla o log estructurado mínimo).  
5. Tests: unit (schema/guardrails) + `@pytest.mark.ollama` opcional + golden JSON authoring.  
6. Docker Compose opcional para Ollama (no contaminar API core).

**Fuera de F1:** explanation UI, Anthropic, agentes autónomos, LangGraph, fine-tune.

---

## 11. Criterios de aceptación

- [x] RFC en `docs/rfc/007-ai-governance.md`
- [x] Proxy, Prompt, Draft, LLMCall, guardrails, costes, isolation
- [x] Migración + hoja F1
- [x] (F1) código Proxy + Ollama/OpenAI adapters + Prompt Registry (`packages/py/ai`)
- [x] (F1) wrap draft APIs (`llm_draft` / `llm_indicator_draft` → Proxy + heurística)
- [x] (F1) unit tests Proxy + heurística (`BOLSA_LLM_PROVIDER=none`)
- [x] (F1+) persistencia ART-LLM-CALL (JSONL via `BOLSA_LLM_AUDIT_PATH`)
- [x] (F1+) `@pytest.mark.ollama` + golden JSON authoring
- [x] (F1+) Compose opcional `docker-compose.ollama.yml`
- [x] (post-F1) tabla PG `llm_calls` + sink `BOLSA_LLM_AUDIT_BACKEND=pg|both`
- [x] (post-F1) import-linter LLM SDKs fuera de `bolsa_ai` (`packages/py/.importlinter`)

---

## 12. Próximo paso

**Pirámide constitucional COMPLETA (000–007). F1 / F1+ implementación cerrada en esqueleto.**

Siguiente: Ollama live opcional; F2 shared types / offline adapters. RFC-008+ solo si el código lo exige.

---

## 13. Enmiendas

Nuevos prompts Production, cambios de guardrails/budget o nuevos providers → PR a este RFC.

---

*Cierra la constitución. A1: IA aislada sobre contratos; A2: Proxy pipeline + Draft/Prompt; A3: APIs, costes, migración llm_*.*
