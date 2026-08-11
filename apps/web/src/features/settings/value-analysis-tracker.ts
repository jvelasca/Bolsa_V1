/**
 * Tracker pedagógico — Análisis del valor (Facts → Assessments → Session → Gate).
 * Renderizado en Ayuda → Análisis del valor (no confundir con Plataforma IA = fases).
 *
 * Estado FA (2026-08-01): track FIE valoración cerrado (F0–F2.8 + F3/F4 + Paper D) ·
 * CAPM footnote Tarjeta · Beneish distress · Composite v1.1.
 * Fase actual: smoke UI / checklist APP. Ver
 * `docs/engineering/fa-status-and-test-plan-2026-07-31.md` · handoff 2026-08-01.
 */

import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";

export const VALUE_ANALYSIS_SYNC = {
  asOf: HELP_CONTENT_AS_OF,
  docRef: "docs/engineering/fa-status-and-test-plan-2026-07-31.md",
  rfc: "docs/rfc/008-cognitive-decision-architecture.md §22",
  fie: "docs/engineering/fundamental-intelligence-engine-2026-07-30.md",
} as const;

export const VALUE_ANALYSIS_YOU_ARE_HERE = {
  title: "Dónde estás ahora",
  body: "FIE cerrado en código: valoración F0–F2.8 + Composite v1.1 + Screener FA + Paper D + CAPM visibles. Fase actual: smoke UI / checklist APP.",
  steps: [
    "Ayuda → este panel: inventario FA + checklist de prueba.",
    "Tarjeta Valor: refresh Yahoo · Más métricas (CAPM ke=rf+β×ERP · DCF · Composite) · filings.",
    "Screeners: FA whitelist → Paper D (dry-run; execute con env). Verificar: `pnpm test:fa`.",
  ],
  pause:
    "Python calcula; LLM solo explica. Filings fuera de Score_FUND. Execute paper off-by-default.",
} as const;

/** Inventario entregado — para Ayuda y handoff de prueba. */
export const VALUE_ANALYSIS_FA_INVENTORY = [
  {
    id: "f1",
    label: "Tarjeta Valor + chip",
    detail: "fund_card_v1 · scoreDisplay100 · confidence",
  },
  {
    id: "f1b",
    label: "Copiloto",
    detail: "Ollama/heurística; solo facts precalculados",
  },
  {
    id: "f20",
    label: "Gate rico",
    detail: "PE, ROE, D/E, Altman, FCF, márgenes, growth…",
  },
  {
    id: "f21",
    label: "Piotroski",
    detail: "piotroski_f_annual_v1 · null si incompleto",
  },
  { id: "f22", label: "Sector bands", detail: "fund_sector_bands_v1" },
  {
    id: "f23",
    label: "Graham + DCF",
    detail: "graham_number_v1 · dcf_fcf_2stage_wacc_v1",
  },
  {
    id: "f24",
    label: "WACC sector",
    detail: "fund_wacc_sector_v1 (fallback sin beta)",
  },
  {
    id: "f25",
    label: "DCF escenarios",
    detail: "dcf_scenarios_v1 bear/base/bull",
  },
  {
    id: "f26",
    label: "CAPM + ADV",
    detail: "fund_capm_v1 · capmRf/capmErp en Tarjeta · adv_usd_v1 → Composite",
  },
  { id: "f27", label: "ROIC", detail: "roic_nopat_ic_v1 · gate minRoic" },
  {
    id: "f28",
    label: "Beneish M",
    detail:
      "beneish_m_annual_v1 · M>−1.78 → fund.solvency=distress · Score_FUND",
  },
  {
    id: "f2b",
    label: "Filings + SEC + RAG",
    detail: "Disco · EDGAR · TF-IDF ask (≠ Score_FUND)",
  },
  {
    id: "f3",
    label: "Composite",
    detail: "composite_score_v1_1 · etiquetas liquidez UI · paperDUnlocked",
  },
  {
    id: "f4",
    label: "Screener FA",
    detail: "fund_screener_v1 · whitelist snapshot",
  },
  {
    id: "pd",
    label: "Paper D",
    detail: "paper_d_propose_v2 · PAPER_D_EXECUTE",
  },
  {
    id: "cron",
    label: "Cron FA→D",
    detail: "fa_weekly_pipeline_v1 · FA_WEEKLY_CRON_ENABLED",
  },
] as const;

/** Checklist corta en Ayuda; detalle en fa-status-and-test-plan. */
export const VALUE_ANALYSIS_TEST_CHECKLIST = [
  "Refresh Yahoo (US + EU): cobertura Piotroski / ROIC / Beneish / beta",
  "Tarjeta Valor → Más métricas: footnote CAPM ke=rf+β×ERP (si fund_capm_v1) · DCF escenarios · Composite",
  "Beneish distress: M > −1.78 refleja solvency/Score_FUND (tras refresh)",
  "Composite: etiquetas liquidez (adv_mega / adv_very_high…) · ver=composite_score_v1_1",
  "Filings: upload · SEC (US) · Preguntar",
  "Screener FA → whitelist → Paper D dry-run",
  "Execute paper solo con PAPER_D_EXECUTE=1 + política paper_auto",
  "Regresión: Backtesting abre (accounts array); API con python-multipart",
] as const;

export const VALUE_ANALYSIS_PRINCIPLE = {
  title: "Qué decide y qué no",
  body: "Los hechos (PE, RSI, VIX, noticias) no son órdenes. Los Assessments son lecturas tipadas (score/facts). Solo el DecisionRuntime fusiona con WeightRules y propone. El Gate permite o veta. El LLM no pondera ni compra ni calcula ratios.",
} as const;

export const VALUE_ANALYSIS_LAYERS = [
  {
    id: "facts",
    title: "Capa 1 — Hechos",
    body: "OHLCV + snapshot Yahoo (PE, ROE, márgenes, D/E, FCF, beta, volumen…) y derived (Altman, Piotroski, Graham, DCF/CAPM, ROIC, Beneish, ADV). JSONB en profile_snapshot. El `?` explica el dato, no el peso.",
  },
  {
    id: "assessments",
    title: "Capa 2 — Assessments",
    body: "Technical / Fundamental / Macro / News / Evidence. Prediction se fotografía pero no vota. FUND: Score_FUND pilares value|quality|growth|risk + confidence. Ver FIE.",
  },
  {
    id: "fusion",
    title: "Capa 3 — Fusión (WeightContext)",
    body: "Pesos por horizonte+régimen (ruleVersion). Composite fusiona TA+FUND+régimen+liquidez+perfil. Distress FUND puede invalidar un long.",
  },
  {
    id: "session",
    title: "ART-DECISION-SESSION + Replay",
    body: "Fotografía del propose en decision_sessions. Decision Replay proyecta la timeline sin re-ejecutar motores.",
  },
  {
    id: "outcome",
    title: "Outcome + Learning v1",
    body: "Cierra la Session con hit/miss/neutral midiendo el close en la barra D1 +N del horizonte. Distinto del outcome del Gate (Memory).",
  },
  {
    id: "gate",
    title: "Gate y ejecución",
    body: "Propose = pasivo. Paper D execute = paper_auto + env. live_auto = dry-run (sin broker). Filings nunca entran al gate numérico.",
  },
] as const;

export const VALUE_ANALYSIS_WEIGHT_TABLE = [
  { horizon: "Intraday", ta: "88%", fund: "2%", macro: "8%", news: "2%" },
  { horizon: "Swing", ta: "52%", fund: "30%", macro: "13%", news: "5%" },
  { horizon: "Position", ta: "38%", fund: "42%", macro: "15%", news: "5%" },
  { horizon: "Long term", ta: "28%", fund: "52%", macro: "15%", news: "5%" },
] as const;

export const VALUE_ANALYSIS_DB = [
  {
    what: "Hechos Yahoo / derived FA",
    where: "instruments.profile_snapshot.fundamentals",
  },
  {
    what: "Filings (fuera de Score_FUND)",
    where: "data/filings/{instrumentId}/",
  },
  { what: "Whitelist FA", where: "instrument_lists kind=snapshot" },
  {
    what: "DecisionSession (razonamiento)",
    where: "decision_sessions.payload",
  },
  { what: "Decision Memory (Gate)", where: "decision_memory" },
  { what: "Edge / Evidence", where: "edge_reports" },
  { what: "DD day/week marks", where: "settings_json.equityMarks" },
  {
    what: "Prediction (en Session)",
    where: "decision_sessions.payload.predictions",
  },
] as const;

export const VALUE_ANALYSIS_NEXT = [
  "Smoke UI humano: operativa-test-plan D1–D12 + R1–R9",
  "Probar checklist FA en APP (refresh · Tarjeta · Screener · Paper D dry-run)",
  "Hecho 2026-08-01: CAPM rf/ERP visibles en Tarjeta (capmRf/capmErp; no live)",
  "Opcional futuro: Moat/Management · rf/ERP live (Treasury/Damodaran)",
  "Hecho 2026-08-01: Beneish distress · densificación · timeseries · ROIC balance · Composite v1.1 + etiquetas UI",
] as const;
