# Rastreadores híbridos — Guía de implementación

> Estado: **jul 2026** — P10–P13 completados en MVP.  
> Diseño original: [AI_TRACKER_STRATEGY.md](./AI_TRACKER_STRATEGY.md)

## Resumen

Un rastreador **híbrido** combina:

1. **Gate técnico** — preset del catálogo (`strategy-presets.json`) evaluado en la última barra.
2. **Gate fundamental** (opcional, P12) — PER, capitalización, sector desde Yahoo sync.
3. **Rating técnico v1.1** — score 0–100 explicable (tendencia, momentum, volatilidad, reversión, **patrón**).
4. **Ranking** — candidatos ordenados por score, truncados a `maxResults`.

El LLM **no** corre en runtime de scan; solo en authoring (`draft-from-prompt`).

---

## Contratos shared

| Tipo | Archivo |
|------|---------|
| `HybridStrategyConfigV1` | `packages/shared/src/hybrid-strategy.ts` |
| `FundamentalGateV1` | `packages/shared/src/fundamentals-gate.ts` |
| `ScanHitDto.aiScore` | `packages/shared/src/scan-api.ts` |
| `ScanManifestV1` (+ observabilidad) | `packages/shared/src/platform-kernel.ts` |

### Rating v1.1 — pesos

| Componente | Peso | Fuente |
|------------|------|--------|
| Tendencia | 38% | SMA 20/50/200, precio vs SMA200 |
| Momentum | 28% | RSI, MACD |
| Volatilidad | 14% | BB, ATR |
| Reversión | 14% | Stoch, CCI |
| Patrón (P13) | 6% | `pattern_uptrend_v1` (HH/HL) |

Versión: `TECHNICAL_RATING_V1_VERSION = 1.1.0`

---

## Backend Python

| Módulo | Responsabilidad |
|--------|-----------------|
| `bolsa_analytics.signals.hybrid_scan` | Gate + rating por instrumento |
| `bolsa_analytics.signals.technical_rating_v1` | Scorer determinista |
| `bolsa_analytics.signals.fundamental_gate` | Filtro PER/cap/sector |
| `bolsa_analytics.signals.pattern_uptrend_v1` | Estructura alcista |
| `bolsa_analytics.research.hybrid_definition` | Builder `strategy_definition_from_hybrid` |
| `bolsa_analytics.research.prompt_draft` | NL → estrategia (heurístico) |
| `bolsa_analytics.research.llm_draft` | Authoring vía `AIGovernanceProxy` (Ollama/OpenAI/none) |
| `bolsa_application.refresh_instrument_fundamentals` | Batch Yahoo pre-scan (P14) |
| `bolsa_application.scans.RunScan` | Orquestación sync |
| `bolsa_market.instrument_fundamentals` | Extracción numérica Yahoo |

### Fundamentales

En cada sync Yahoo, `profile_snapshot.fundamentals` guarda:

```json
{
  "marketCap": 1234567890,
  "trailingPe": 18.5,
  "forwardPe": 16.2,
  "sector": "Financial Services",
  "fetchedAt": "2026-07-12T...",
  "sourceVersion": "yahoo_quote_summary_v3"
}
```

Requisito histórico: sincronizar instrumentos antes de scans con gate fundamental.

**P14 (jul 2026):** `RunScan` refresca en batch desde Yahoo los fundamentales **obsoletos o ausentes** (`maxAgeDays`, default 30) antes de evaluar el gate. Concurrencia 4. Campo de respuesta: `fundamentalsRefreshedCount`.

### Scan manifest (observabilidad)

Campos persistidos además del baseline P4:

- `scanMode`, `scorerId`, `scorerVersion`
- `gateRuleHash`, `fundamentalsVersion`

---

## UI

| Pantalla | Funcionalidad |
|----------|---------------|
| `/screeners` — formulario | Modo Clásico / Híbrido, gate, rating, PER, cap. |
| `/screeners` — Asistente IA | Prompt → borrador validado → guardar / usar en rastreo |
| Hub listas — rastreadores | Crear híbrido persistente por lista |
| Resultados scan | Columna Rating + tooltip breakdown |

Helpers centralizados:

- `scanRequestFromConfig`, `strategyUpsertFromScanConfig` — `scan-runner-form.tsx`
- `scanFieldsFromFundamentalGate` — round-trip gate ↔ UI

---

## API

| Endpoint | Uso |
|----------|-----|
| `POST /api/scans/run` | Scan inline (classic o hybrid via `definition`) |
| `POST /api/strategies/draft-from-prompt` | Asistente IA estrategias |
| `POST /api/indicators/draft-from-prompt` | Asistente IA indicadores |
| `POST /api/strategies` | Persistir estrategia híbrida |
| `PATCH /api/strategies/{id}` | Editar estrategia (cliente: `api.updateStrategy`) |
| `POST /api/trackers` | Vincular estrategia a lista |
| `GET /api/scans/manifests/{scanId}` | Trazabilidad reproducible |

---

## Tests

```bash
cd packages/py/analytics && python -m pytest tests/test_hybrid_scan.py tests/test_technical_rating_v1.py tests/test_fundamental_gate.py tests/test_prompt_draft.py -q
pnpm --filter @bolsa/web typecheck
```

---

## Variables de entorno (LLM authoring)

Authoring pasa por `AIGovernanceProxy` ([RFC-007](./rfc/007-ai-governance.md), paquete `bolsa_ai`). Detalle: [packages/py/ai/README.md](../packages/py/ai/README.md).

| Variable | Default | Efecto |
|----------|---------|--------|
| `BOLSA_LLM_PROVIDER` | `ollama` (o `openai` si hay key) | `ollama` \| `openai` \| `none` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama local |
| `OPENAI_API_KEY` | — | Provider cloud opcional |
| `BOLSA_LLM_MODEL` | `gpt-4o-mini` | Modelo OpenAI |
| `BOLSA_LLM_AUDIT_PATH` | — | JSONL append-only |
| `BOLSA_LLM_AUDIT_BACKEND` | — | `pg` \| `both` → tabla `llm_calls` |

`BOLSA_LLM_PROVIDER=none` o sin provider disponible → heurística `prompt_catalog_*` (sin coste).
