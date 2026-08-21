/**
 * Catálogo de superficies LLM / copiloto para el botón informativo «IA».
 * @see docs/engineering/pending-delete/NEXT-IA-BUTTON.md
 * @see docs/engineering/research-radar-unification-2026-07-31.md §1.6
 */

export type AiInfoSurfaceId =
  | "fa_copilot"
  | "fa_filings"
  | "backtest_coach"
  | "strategy_draft"
  | "chart_propose"
  | "lab_optimize";

export type AiInfoSurface = {
  id: AiInfoSurfaceId;
  title: string;
  /** Qué hace esta IA en esta superficie. */
  does: string;
  /** Qué no hace (límites de gobernanza). */
  doesNot: string;
  /** Motor / proveedor típico. */
  engineHint: string;
  /** `supervised-f3` → `/confirm`; sin panel → Ayuda → Plataforma IA. */
  helpPanel?: "supervised-f3" | null;
};

export const AI_INFO_SURFACES: Record<AiInfoSurfaceId, AiInfoSurface> = {
  fa_copilot: {
    id: "fa_copilot",
    title: "Copiloto fundamental",
    does: "Explica Score_FUND, pilares y facts ya calculados (narrativa). Puede usar Ollama o heurística local.",
    doesNot:
      "No recalcula ratios, Piotroski, DCF ni Score_FUND. No escribe en BD ni envía órdenes.",
    engineHint:
      "Proxy First → Ollama / heurística · scoreVersion fund_score_v1",
  },
  fa_filings: {
    id: "fa_filings",
    title: "Filings · resumir / preguntar",
    does: "Resume o responde sobre documentos 10-K/u.o. con RAG local (TF-IDF) + narrativa opcional.",
    doesNot:
      "No altera Score_FUND, Composite ni el gate FA. No es asesoramiento legal.",
    engineHint:
      "Filings en disco · summarize/ask · sin embedding cloud obligatorio",
  },
  backtest_coach: {
    id: "backtest_coach",
    title: "Coach de backtesting",
    does: "El ranking TOP ★ es local y determinista. El LLM (si está activo) solo narra o audita en adversario; no sustituye el TOP.",
    doesNot:
      "No calcula PnL, no guarda Finalistas solo, no ejecuta paper. Lab Optimize es determinista (no LLM).",
    engineHint:
      "rankTechnicalRecommendations local · LLM opcional (prefs Coach)",
  },
  strategy_draft: {
    id: "strategy_draft",
    title: "Borrador de estrategia (prompt)",
    does: "Interpreta lenguaje natural → borrador de StrategyDefinition para revisar y guardar.",
    doesNot:
      "No lanza backtests ni paper solos. Tú confirmas el guardado y el rastreador.",
    engineHint: "POST /api/strategies/draft-from-prompt · governance",
  },
  chart_propose: {
    id: "chart_propose",
    title: "Estudio IA del valor (gráfico)",
    does: "Propose determinista (DecisionRuntime) con assessments TA/FA/… → cola Supervisado F3. Humano confirma.",
    doesNot:
      "No es chat libre. No firma órdenes. Camino C (Supervisado), no Checklist ni Radar auto.",
    engineHint: "POST propose · Gate propose=pasivo",
    helpPanel: "supervised-f3",
  },
  lab_optimize: {
    id: "lab_optimize",
    title: "Lab · optimizar",
    does: "Barridos de parámetros y OOS deterministas sobre la estrategia candidata.",
    doesNot:
      "No usa LLM para puntuar. No escribe Finalistas (vuelve el Coach²).",
    engineHint: "Optimize grids · sin modelo generativo",
  },
};
