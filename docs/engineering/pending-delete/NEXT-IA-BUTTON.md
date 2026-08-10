# Botón «IA» contextual

## Estado: implementado (2026-07-31)

En superficies LLM / copiloto / propose hay un botón pequeño **IA** que abre un diálogo:

1. Qué hace esa IA
2. Qué **no** hace (gobernanza)
3. Motor / proveedor tip
4. Enlace a **Ayuda → Plataforma IA**

### Código

- Catálogo: `apps/web/src/features/ai/ai-info-catalog.ts`
- UI: `apps/web/src/features/ai/ai-info-button.tsx`

### Superficies cableadas

| Surface id | Dónde |
|------------|--------|
| `fa_copilot` | Tarjeta Valor · Copiloto (+ tab FA Backtesting) |
| `fa_filings` | Tarjeta Valor · Docs USA |
| `backtest_coach` | Panel Coach + tab Coach |
| `lab_optimize` | Tab Lab (info: Lab es determinista) |
| `strategy_draft` | Screeners · Asistente IA (draft-from-prompt) |
| `chart_propose` | Barra gráfico · estudio IA |

Relacionado: [research-radar-unification-2026-07-31.md](../research-radar-unification-2026-07-31.md).
