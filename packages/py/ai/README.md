# bolsa-ai — AI Governance (RFC-007 / F1)

Único paquete autorizado para llamadas LLM. **Nunca** en hot path EXECUTION ni OMS.

## Componentes

| Módulo | Rol |
|--------|-----|
| `AIGovernanceProxy` | Entrypoint único (`complete_structured`) |
| `PromptRegistry` | ART-PROMPT (`prompts/*.json`) |
| `OllamaAdapter` / `OpenAIAdapter` | Providers |
| Guardrails | Injection / secrets / timeout |
| `JsonlAuditSink` | Persistencia append-only `ART-LLM-CALL` |
| `LlmCallV1` | Auditoría in-memory + sink |

Heurística de authoring sigue en `bolsa_analytics.research.prompt_*`; el Proxy devuelve `None` y el caller usa fallback.

## Variables de entorno

| Variable | Efecto |
|----------|--------|
| `BOLSA_LLM_PROVIDER` | `ollama` \| `openai` \| `none` (fuerza heurística) |
| `OLLAMA_BASE_URL` | Default `http://127.0.0.1:11434` |
| `BOLSA_OLLAMA_MODEL` | Override del modelo del prompt (p.ej. `qwen2.5-coder:1.5b` smoke / `14b` prod) |
| `OPENAI_API_KEY` | Activa OpenAI si provider no es `none` |
| `BOLSA_LLM_MODEL` | Modelo OpenAI (default `gpt-4o-mini`) |
| `BOLSA_LLM_TIMEOUT_SECONDS` | Timeout por llamada |
| `BOLSA_LLM_MAX_PROMPT_CHARS` | Límite de prompt |
| `BOLSA_LLM_AUDIT_PATH` | Ruta JSONL append-only (ej. `logs/llm_calls.jsonl`). Vacío/`off` = solo memoria |
| `BOLSA_LLM_AUDIT_BACKEND` | `pg` / `both` → insert en tabla `llm_calls` (Prisma migrate) |

## Persistencia ART-LLM-CALL

```powershell
$env:BOLSA_LLM_AUDIT_PATH = "logs/llm_calls.jsonl"
```

Cada invocación añade una línea JSON (`artifactType: ART-LLM-CALL`). Sin purge automático. PG queda para cuando Prisma/Alembic estén listos.

## Ollama (Compose opcional)

```powershell
docker compose -f docker-compose.ollama.yml up -d
docker exec -it bolsa-ollama ollama pull qwen2.5-coder:14b
$env:BOLSA_LLM_PROVIDER = "ollama"
```

## Tests

```powershell
$env:BOLSA_LLM_PROVIDER = "none"
python -m pytest packages/py/ai/tests -q -m "not ollama"
# Live (requiere Ollama):
python -m pytest packages/py/ai/tests -q -m ollama
```

## Uso

```python
from bolsa_ai import get_default_proxy

completion = get_default_proxy().complete_structured(
    prompt_template_id="prompt_strategy_authoring_v1",
    variables={"user_input": "cruce SMA 9/21"},
)
# None → usar draft_strategy_from_prompt (heurística)
```
