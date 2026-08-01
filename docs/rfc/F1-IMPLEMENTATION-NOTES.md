# F1 — Notas de implementación (AI Governance)

> Constitución RFC-000…007 cerrada. Este documento es operativo, no un RFC fundacional.

## Decisión de arranque

**Opción C + A:** esqueleto del paquete + heurística primero; Ollama/OpenAI detrás del Proxy.

## Entregado

| Pieza | Ubicación |
|-------|-----------|
| Paquete `bolsa-ai` | `packages/py/ai` → import `bolsa_ai` |
| Proxy | `bolsa_ai.proxy.AIGovernanceProxy` |
| Prompts | `bolsa_ai/prompts/prompt_*_authoring_v1.json` |
| Adapters | `adapters/ollama_adapter.py`, `openai_adapter.py` |
| Wrap strategy | `bolsa_analytics.research.llm_draft` |
| Wrap indicator | `bolsa_analytics.research.llm_indicator_draft` |
| Audit JSONL | `bolsa_ai.audit_sink.JsonlAuditSink` (`BOLSA_LLM_AUDIT_PATH`) |
| Golden + ollama | `packages/py/ai/tests/golden/`, `@pytest.mark.ollama` |
| Compose Ollama | `docker-compose.ollama.yml` (separado del core) |
| Tests unit | `packages/py/ai/tests/` |

## Env mínimo para CI / local sin LLM

```bash
BOLSA_LLM_PROVIDER=none
```

## Persistencia ART-LLM-CALL (F1+)

```bash
BOLSA_LLM_AUDIT_PATH=logs/llm_calls.jsonl
```

JSONL append-only; sin dependencia de PG. Tabla SQLAlchemy/Prisma → cuando el baseline de migraciones esté listo.

## Ollama opcional

```bash
docker compose -f docker-compose.ollama.yml up -d
docker exec -it bolsa-ollama ollama pull qwen2.5-coder:14b
BOLSA_LLM_PROVIDER=ollama pytest packages/py/ai/tests -m ollama
```

## Persistencia PG

```bash
# aplicar migración Prisma
npx prisma migrate deploy --schema packages/database/prisma/schema.prisma
# o: npm run db:migrate (si existe en package.json)

BOLSA_LLM_AUDIT_BACKEND=both
BOLSA_LLM_AUDIT_PATH=logs/llm_calls.jsonl
```

## Estado

**F1 / F1+ cerrados.** Tabla `llm_calls` aplicada en PG local (2026-07-22). import-linter activo.

## Pendiente posterior

1. Cost accounting real OpenAI (tokens → USD).
2. Ollama live / `@pytest.mark.ollama` en CI opcional.

## Fuera de alcance

EXECUTION / OMS, Signal→Order, agentes, LangGraph, fine-tune, RFC-008+ prematuros.
