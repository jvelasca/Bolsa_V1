# bolsa-market

Ingesta y **cálculo determinista** de mercado / fundamentales (FIE).

## FA snapshot (`instrument_fundamentals`)

Yahoo `quoteSummary` → `profile_snapshot.fundamentals`:

- Facts: PE, ROE, márgenes, D/E, FCF, beta, volumen…
- Derived: Altman, Piotroski, Graham, DCF (+ escenarios), WACC/CAPM, ROIC, Beneish, ADV

Módulos clave: `valuation.py`, `wacc.py`, `capm.py`, `roic.py`, `beneish.py`, `piotroski.py`, `filing_*`.

**Regla:** este paquete calcula; `bolsa_ai` / copiloto solo explican.

Docs: `docs/engineering/fa-status-and-test-plan-2026-07-31.md`  
Verificar: `pnpm test:fa`
