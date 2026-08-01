# bolsa-analytics

Capa de **scores, gates y conocimiento** (FIE / RFC-008).

## FA / FIE (estado 2026-07-31)

| Módulo | Rol |
|--------|-----|
| `knowledge/score_fund.py` | Score_FUND `fund_score_v1` — pilares value/quality/growth/risk |
| `knowledge/fundamental_card.py` | DTO tarjeta (`fund_card_v1`, `scoreDisplay100`) |
| `knowledge/composite_score.py` | Composite F3 (TA+FUND+régimen+liquidez ADV/mcap) |
| `knowledge/fundamental_copilot.py` | Explicación LLM/heurística (no calcula) |
| `signals/fundamental_gate.py` | Gate FA (métricas + sector bands) |
| `signals/fundamental_screener.py` | Screener FA puro (F4) |
| `knowledge/dia_d_session_evidence.py` | Evidence sandbox DÍA D (heurística; LLM solo narra) |
| `knowledge/core_r_review_evidence.py` | Evidence cola CORE-R (heurística; LLM solo narra) |

**Regla:** Python calcula; LLM solo explica. Filings no entran aquí.

Docs: `docs/engineering/fa-status-and-test-plan-2026-07-31.md` · DÍA D/CORE-R: `docs/engineering/operativa-test-plan-2026-07-31.md`  
Verificar: `pnpm test:fa` · `pnpm test:operativa`
