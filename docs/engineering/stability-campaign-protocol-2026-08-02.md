# Protocolo de estabilidad temporal (Q1.2 / Q1.3)

> **AsOf:** 2026-08-03 · Gate C4 sigue cerrado hasta informe + hipótesis escrita.

## Objetivo

Repetir un protocolo **C3-like** (mismas familias, mismos costes, mismo universo) en **≥2 ventanas** temporales y documentar si el ranking de activos (fuertes/débiles) se mantiene o deriva.

## Ventanas sugeridas (IBEX35 diario)

| Ventana | dataset_start | dataset_end | Notas |
|---------|---------------|-------------|--------|
| A (referencia C*) | ~2020-01-01 | ~2023-12-31 | Alinear con campaigns históricas si hay datos |
| B | ~2022-01-01 | ~2025-12-31 | Solape parcial OK; no es hold-out puro |

Ajustar a disponibilidad real de OHLCV; registrar `bar_count` en `campaign_manifest_v0`.

## Pasos

1. Escribir manifest por ventana (`research/campaigns/<id>.json`) con `git_commit`, costes, TF.
2. Correr battery/RSI/MACD **sin** nueva familia (`scripts/research/run_ibex35_*`).
3. Tag `params.campaign` + `manifest_ref` vía `CampaignManifestV0.to_manifest_ref()`.
4. Ledger-only: `cross_family_consolidation.py --campaign <id>` por ventana.
5. Informe Δ: `python scripts/research/stability_ranking_delta.py --campaign-a <A> --campaign-b <B> --write-md research/observations/...`.
6. Gate cierre: `python scripts/research/campaign_close_gate.py --campaign <id> --manifest ...`  
   (incluye warm-up OK vía `check_manifest_warmup` / Q1.6).

## Smoke vs IBEX completo

```bash
# Smoke (3 símbolos) — CI / diagnóstico local
python scripts/research/stability_windows_smoke.py --limit 3

# IBEX completo (ops; API/DB + OHLCV listos)
python scripts/research/stability_windows_smoke.py --full
```

Observaciones: `research/observations/2026-08-02-stability-delta-smoke.md` (smoke) ·
`2026-08-03-stability-delta-ibex.md` (corrida `--full`).

## Anti-objetivos

- No abrir Bollinger/C4 aquí.
- No reescribir K de C1–C3.
- No usar Sharpe mediano cross-family como “verdad” sin caveat tradeCount/Calmar.
