import { HELP_CONTENT_AS_OF } from '@/features/help/help-content-as-of';

export type AiTrackStatus = 'done' | 'partial' | 'next' | 'planned' | 'blocked';

export interface AiTrackItem {
  id: string;
  title: string;
  status: AiTrackStatus;
  /** Cómo lo hacemos (enfoque técnico). */
  how: string;
  /** Qué queda o matiz. */
  note?: string;
  docRef?: string;
}

export const AI_TRACKER_SYNC = {
  /** Debe coincidir con HELP_CONTENT_AS_OF y el encabezado de AI_PLATFORM_SOLUTION.md */
  asOf: HELP_CONTENT_AS_OF,
  solutionDoc: 'docs/AI_PLATFORM_SOLUTION.md',
  rfcIndex: 'docs/rfc/README.md',
  governanceRfc: 'docs/rfc/007-ai-governance.md',
  featureRfc: 'docs/rfc/005-feature-registry.md',
  /** Núcleo cognitivo Decision Engine (D0–D5). */
  cognitiveRfc: 'docs/rfc/008-cognitive-decision-architecture.md',
} as const;

export const AI_PRINCIPLE = {
  title: 'Principio inquebrantable',
  body:
    'El LLM (y cualquier modelo generativo) nunca envía órdenes ni calcula PnL contable. Eso lo hace el motor determinista: DecisionRuntime → Policy Gate → Execution / Backtest. El trading automático y el backtest SÍ operan y miden PnL — pero como stack de decisión/ejecución, no como “el chat que decide”. ML tabular puede aportar Prediction/Evidence; nunca salta el Gate. Evidence ≠ Assessment ≠ Decision (RFC-008 Amendment-2).',
} as const;

/** Flujo canónico — visible en Ayuda → Plataforma IA. */
export const AI_DECISION_PIPELINE = {
  title: 'Arquitectura de decisión (bloqueada)',
  steps: [
    'OHLCV → FeatureSet → Evidence',
    'Assessment[] (Technical / Fundamental / Macro / News / Evidence…)',
    'DecisionRuntime v1.1 (WeightRules) → DecisionPackage + Recommendation',
    'ART-DECISION-SESSION persistido en propose (auditabilidad)',
    'Policy Gate: propose = pasivo · paper_auto = hard VETO',
    'Scan hits → Encolar F3 → cola supervisada (Ayuda → Plataforma IA)',
  ],
  rules: [
    'Ningún Assessment emite BUY/SELL — solo bias, score, facts, warnings.',
    'Solo el DecisionRuntime construye la acción (recommend_* / wait).',
    'El Gate verifica; no reescribe la Recommendation.',
    'Sustituir un motor (p. ej. TA V1→V4) no cambia Runtime ni endpoint propose.',
  ],
  docRef: 'RFC-008 §22 / AI_PLATFORM_SOLUTION §F3',
} as const;

/**
 * Mapa producto: dónde hay “IA” vs ranking local vs Lab determinista.
 * @see docs/engineering/assistant-play-funnel-design-2026-07-29.md §8
 */
export type AiWhereKind = 'local' | 'llm_optional' | 'deterministic' | 'hybrid';

export type AiWhereMapEntry = {
  id: string;
  surface: string;
  kind: AiWhereKind;
  /** Qué es en la práctica (una frase). */
  role: string;
  /** ¿Ordena PnL / TOP / órdenes? */
  rankingOrOrders: string;
};

export const AI_WHERE_KIND_LABEL: Record<AiWhereKind, string> = {
  local: 'Ranking local',
  llm_optional: 'LLM opcional',
  deterministic: 'Determinista',
  hybrid: 'Híbrido',
};

export const AI_WHERE_MAP: AiWhereMapEntry[] = [
  {
    id: 'coach-stars',
    surface: 'Coach ★ (embudo Backtesting)',
    kind: 'local',
    role: 'Selección TOP-3 / Finalistas por score ★ (horizonte·riesgo del perfil).',
    rankingOrOrders: 'Ranking = local. LLM no escribe TOP.',
  },
  {
    id: 'coach-llm',
    surface: 'Narración / dual-audit Coach',
    kind: 'llm_optional',
    role: 'Texto y veto/adversario opcionales; confianza Consenso/Discrepancia/Débil.',
    rankingOrOrders: 'No sustituye el ranking ★.',
  },
  {
    id: 'lab-optimize',
    surface: 'Lab / Optimizar',
    kind: 'deterministic',
    role: 'Grids H0/VBT/Optuna + OOS/WF; memoria adopción CORE-B; familia por horizonte.',
    rankingOrOrders: 'No es LLM. Mejora params, no narra.',
  },
  {
    id: 'list-auto',
    surface: 'Lista AUTO + CORE-R',
    kind: 'deterministic',
    role: 'Embudo × valor; Omitido si fresco (v1.3); Monitor CORE-R v1.8 (cola/cron shell).',
    rankingOrOrders: 'Orquestación local; no pisa TOP solo; sin chat.',
  },
  {
    id: 'strategy-draft',
    surface: 'Crear estrategias / indicadores',
    kind: 'llm_optional',
    role: 'LLM → borrador JSON (governance); el compute sigue en analytics.',
    rankingOrOrders: 'No ordena ni hace PnL.',
  },
  {
    id: 'supervised-f3',
    surface: 'Supervisado F3',
    kind: 'hybrid',
    role: 'Assessments + DecisionRuntime; LLM opcional en narración; humano confirma.',
    rankingOrOrders: 'Gate hard/pasivo; no auto-órdenes.',
  },
  {
    id: 'paper-auto-b',
    surface: 'Radar paper_auto (B)',
    kind: 'deterministic',
    role: 'Policy Gate + evidencias; paper etiquetado B.',
    rankingOrOrders: 'Sin checklist Lab. Auto D congelado.',
  },
  {
    id: 'value-analysis',
    surface: 'Análisis del valor',
    kind: 'hybrid',
    role: 'WeightContext / DecisionSession (FA + perfil).',
    rankingOrOrders: 'Distinto del Coach AT del embudo.',
  },
];

/** Capacidades de producto que queremos conseguir. */
export const AI_PRODUCT_GOALS: AiTrackItem[] = [
  {
    id: 'goal-coach-at',
    title: 'Coach AT (embudo Backtesting)',
    status: 'done',
    how: 'Ranking ★ local + dual-audit; LLM solo narra (toggle CORE A). Lista AUTO frescura v1.3 + keep-alive.',
    note: 'Hecho operativo. Congelado: Belief → Coach (aprendizaje outcomes).',
    docRef: 'docs/engineering/assistant-play-funnel-design-2026-07-29.md §6',
  },
  {
    id: 'goal-lab-at',
    title: 'Lab AT (mejora de estrategias)',
    status: 'done',
    how: 'Grids SMA/RSI/MACD + OOS/WF; memoria CORE-B v0.2 (meseta→espacio · resolveDefaultLabFamily).',
    note: 'Hecho operativo. Congelado: Lab UI P3–P9 / Discovery.',
    docRef: 'docs/engineering/assistant-play-funnel-design-2026-07-29.md §6',
  },
  {
    id: 'goal-core-r',
    title: 'Reevaluación continua (CORE-R)',
    status: 'done',
    how: 'v1.12: juicio + cola Monitor + OOS/PnL + narración + cron shell + chip/toast + Hecho todos + BD multi-dispositivo + cron servidor (off) + toast remoto.',
    note: 'LS=cache · BD=SoT. Congelado: auto-paper D · activar CORE_R_CRON sin decisión ops.',
    docRef: 'docs/engineering/list-auto-ops-2026-07-29.md · ISSUES CORE-R',
  },
  {
    id: 'goal-profile-coach',
    title: 'Perfil cuenta ↔ Coach/Lab (CORE-P)',
    status: 'done',
    how: 'Gate Lab, stamp, techo DD, rail, familias/horizonte, mismatch, soft-bias + E2E live API smoke.',
    note: 'Offline en test:coach · live `pnpm test:coach:smoke`. BETA1: vigilar simulaciones multi-perfil.',
    docRef: 'docs/engineering/profile-coach-lab-binding.md',
  },
  {
    id: 'goal-ai-map',
    title: 'Mapa IA (Ayuda / Config)',
    status: 'done',
    how: 'Tabla «Dónde usamos IA» + objetivos hechos/parciales + NEXT/congelados en Ayuda → Plataforma IA.',
    note: 'Narrador Coach ON/OFF en rail del Asistente; ranking siempre local.',
    docRef: 'docs/engineering/assistant-play-funnel-design-2026-07-29.md §8',
  },
  {
    id: 'goal-indicators',
    title: 'Indicadores generados por IA',
    status: 'partial',
    how: 'Prompt → Draft JSON (catálogo) vía AIGovernanceProxy; compute determinista.',
    note: 'Pendiente: DSL/Pine completo y sandbox.',
    docRef: 'AI_PLATFORM_SOLUTION §1',
  },
  {
    id: 'goal-supervised',
    title: 'Trading supervisado (Decision Engine)',
    status: 'done',
    how: 'Assessment[] → Runtime → Recommendation → humano. Cola scan→F3. Propose → DecisionSession.',
    note: 'Operativo en Ayuda → Plataforma IA / Finalistas Proponer.',
    docRef: 'RFC-008 §22',
  },
  {
    id: 'goal-auto-paper',
    title: 'Trading IA automático (paper)',
    status: 'partial',
    how: 'paper_auto + Gate hard; EquityMarkBook; manifests; live_auto dry-run.',
    note: 'Camino B Radar OK. Congelado: auto-paper D execute (`PAPER_D_EXECUTE`).',
    docRef: 'Roadmap F4',
  },
  {
    id: 'goal-screeners',
    title: 'Rastreadores con IA',
    status: 'partial',
    how: 'Gate de reglas + Prediction + ranking; scan con IFeaturePort.',
    note: 'Hybrid trackers MVP. Pendiente: modelos binarios PG/S3.',
    docRef: 'AI_PLATFORM_SOLUTION §1',
  },
  {
    id: 'goal-backtest-ai',
    title: 'Backtesting por IA',
    status: 'planned',
    how: 'NL → estrategia validada → mismo motor BT (walk-forward con gates).',
    note: 'F5 — draft de estrategia ya existe; orquestación BT-by-IA no.',
    docRef: 'Roadmap F5',
  },
  {
    id: 'goal-live',
    title: 'Live automático (opcional)',
    status: 'partial',
    how: 'live_auto = dry-run Gate+auto_live+manifest; broker = F6.',
    note: 'PASS no envía órdenes. Requiere EdgeReport + adapter broker.',
    docRef: 'Roadmap F6',
  },
];

/** Próximos pasos accionables (no congelados). Visible en Ayuda → Plataforma IA. */
export const AI_PRODUCT_NEXT = [
  'BETA1: runbook docs/engineering/beta1-simulation-runbook.md · bloques A–E',
  'Smoke UI: D1–D12 + R1–R9 · FA APP · Lista AUTO live (issues cortas si falla)',
  'Indicadores IA: DSL/Pine + sandbox (cuando producto priorice)',
  'F2 Predictions: persistencia binarios modelo (PG/S3)',
  'F5 Backtest-by-IA (orquestación NL→BT) — planificado',
] as const;

/** Tracks congelados hasta decisión explícita. */
export const AI_PRODUCT_FROZEN = [
  'Belief UI / Belief → Coach (CORE A ciclo 2)',
  'Lab UI P3–P9 / Discovery',
  'Auto-paper D execute (PAPER_D_EXECUTE off-by-default)',
  'CORE-R cron multi-dispositivo (cola servidor)',
  'Broker live real (F6 adapter)',
] as const;
/** Núcleo cognitivo RFC-008 (Decision Engine; no “la IA”). */
export const AI_COGNITIVE_PHASES: AiTrackItem[] = [
  {
    id: 'd0',
    title: 'D0 — RFC-008 Cognitive Decision Architecture',
    status: 'done',
    how: 'Approved: pipeline jerárquico Opportunity→Context→Evidence→Policy; Declared≠Observed; 1 LLM explicador.',
    docRef: 'docs/rfc/008-cognitive-decision-architecture.md',
  },
  {
    id: 'd1',
    title: 'D1 — Profile + TradingPolicy + catálogo UI',
    status: 'done',
    how: 'Schemas + 3 plantillas; tabla investor_profiles + active_profile_id; CRUD/assign API; Configuración → Perfil inversor.',
    note: 'Obsoleto: settings_json.investorProfile (migrado 20260723020000). Observed en D7 (solo lectura).',
    docRef: 'RFC-008 §6 / §17',
  },
  {
    id: 'd2',
    title: 'D2 — Knowledge + DecisionPackage + Gate',
    status: 'done',
    how: 'Facts→Assessments→DecisionRuntime→DecisionPackage + gate_decision_package (PASS/VETO + Memory).',
    note: 'Runtime v1.1 fusiona TA/FUND/MACRO; Gate hot path en paper_auto (D4).',
    docRef: 'RFC-008 §17 / §22',
  },
  {
    id: 'd3',
    title: 'D3 — Evidence Engine v1',
    status: 'done',
    how: 'WFE + MC + PSR/DSR + TrialsLog + ART-EDGE-REPORT + EvidenceAssessment + check_auto_live.',
    note: 'EvidenceAssessment modula confianza (no dirección). Panel Efectividad D7; TrialsLog PG pendiente.',
    docRef: 'RFC-008 §8 / §17 / §22',
  },
  {
    id: 'd4',
    title: 'D4 — MarketEvents + Gate hot path',
    status: 'done',
    how: 'ART-MARKET-EVENT + decay + blackouts; ExecutionRouter paper_auto → enforce_cognitive_policy_for_opening.',
    note: 'Calendario compartido + YahooNewsEventPort (search news + earnings). Sentiment = keywords título.',
    docRef: 'RFC-008 §17',
  },
  {
    id: 'd5',
    title: 'D5 — Fundamental + Opportunity',
    status: 'done',
    how: 'FundamentalAssessment + Opportunity→Runtime (WeightRules). Ya no construye action en Opportunity.',
    note: 'Yahoo v3: PE/mcap + ROE/márgenes/growth/D/E + Altman Z (balance sheet). EBIT preferido; fallback EBITDA documentado.',
    docRef: 'RFC-008 §17 / §22',
  },
  {
    id: 'd6',
    title: 'D6 — Macro + WeightRules + Market State',
    status: 'done',
    how: 'MacroAssessment + Market State→régimen; WeightRules (+w_news); Opportunity multimodal vía Runtime; feed Yahoo live en propose.',
    note: 'Curva = proxy 10Y−5Y (^TNX−^FVX). Crédito/breadth aún no.',
    docRef: 'RFC-008 §17 / §21.1 / §22',
  },
  {
    id: 'd7',
    title: 'D7 — Confidence Lifecycle + Observed + Efectividad',
    status: 'done',
    how: 'ART-CONFIDENCE-STATE; observe_investor_profile; build_effectiveness_summary; GET /api/ai/effectiveness; panel Ayuda.',
    note: 'Declared nunca se reescribe. Persistencia PG: decision_memory / trial_records / confidence_states / edge_reports.',
    docRef: 'RFC-008 §12 / §17',
  },
  {
    id: 'd7-pg',
    title: 'D7+ — Persistencia PG cognitiva',
    status: 'done',
    how: 'Tablas Prisma + SqlAlchemyCognitiveRepository + LoadEffectivenessFromStore; POST memory/trials/edge; GET effectiveness desde PG.',
    note: 'Migración 20260723010000. paper_auto Gate → append decision_memory (PASS/VETO).',
    docRef: 'packages/database/prisma/migrations/20260723010000_cognitive_persistence',
  },
  {
    id: 'd7-obs',
    title: 'D7++ — Observed persistido + Efectividad',
    status: 'done',
    how: 'refresh-observed → observed_json; effectiveness hidrata Observed; samples desde Decision Memory.',
    note: 'Declared nunca se reescribe. POST /api/investor-profiles/{id}/refresh-observed.',
    docRef: 'RFC-008 §6 / §12',
  },
  {
    id: 'd1-default',
    title: 'D1++ — Perfil por defecto al crear cuenta',
    status: 'done',
    how: 'POST /accounts: investorProfile | activeProfileId | EnsureDefault(moderate). Wizard Nueva demo incluye paso Perfil.',
    docRef: 'RFC-008 §6',
  },
];

/** Fases de ejecución (post-constitución). */
export const AI_EXECUTION_PHASES: AiTrackItem[] = [
  {
    id: 'f0',
    title: 'F0 — Constitución',
    status: 'done',
    how: 'RFC-000…008 aprobados (constitución + núcleo cognitivo Decision Engine).',
    docRef: 'docs/rfc/',
  },
  {
    id: 'f1',
    title: 'F1 / F1+ — Authoring + Governance',
    status: 'done',
    how: 'AIGovernanceProxy, Prompt Registry, Ollama/OpenAI/heurística, draft estrategia/indicador, audit JSONL + PG (`llm_calls`), compose Ollama, import-linter.',
    note: 'Ollama live opcional por entorno; migración llm_calls en cada deploy.',
    docRef: 'RFC-007',
  },
  {
    id: 'f2',
    title: 'F2 — Feature Registry (+ Predictions)',
    status: 'partial',
    how: 'IFeaturePort + HTTP features; PredictionV1 + registry in-memory; heuristic + lgbm_direction_v1 (LightGBM opcional / numpy fallback).',
    note: 'Endpoints /api/predictions/*. Propose + HTTP persisten en PG (model_artifacts / predictions). Binarios = pendiente.',
    docRef: 'RFC-005 / RFC-006 §7.4',
  },
  {
    id: 'f3',
    title: 'F3 — Supervisado (Recommendation → Intent)',
    status: 'done',
    how: 'Endpoint propose: TA+FUND+Macro live+Evidence+News → Runtime v1.1. Scan → Encolar F3 → cola Ayuda.',
    note: 'News = Yahoo search + heuristic sentiment + earnings. Propose → DecisionSession en PG.',
    docRef: 'RFC-008 §22 / AI_PLATFORM_SOLUTION §F3',
  },
  {
    id: 'f4',
    title: 'F4 — Paper auto',
    status: 'done',
    how: 'paper_auto + Gate hard; EquityMarkBook; manifests; live_auto dry-run; DecisionSession + Memory en Gate.',
    note: 'Broker real = F6 (fuera freeze IA).',
    docRef: 'AI_PLATFORM_SOLUTION §8',
  },
  {
    id: 'f5',
    title: 'F5 — Backtest-by-IA',
    status: 'planned',
    how: 'Prompt → strategy → walk-forward con gates en el motor BT existente.',
    docRef: 'AI_PLATFORM_SOLUTION §8',
  },
  {
    id: 'f6',
    title: 'F6 — Live (opcional)',
    status: 'partial',
    how: 'Camino live_auto endurecido (dry-run). Falta adapter broker.',
    note: 'No órdenes reales hasta broker + paper estable.',
    docRef: 'AI_PLATFORM_SOLUTION §8',
  },
];

/** Piezas técnicas / registries. */
export const AI_TECH_BUILDING_BLOCKS: AiTrackItem[] = [
  {
    id: 'proxy',
    title: 'AIGovernanceProxy (único camino LLM)',
    status: 'done',
    how: 'packages/py/ai — adapters Ollama/OpenAI/none, guardrails, audit sink.',
    docRef: 'RFC-007',
  },
  {
    id: 'prompt-registry',
    title: 'Prompt Registry',
    status: 'done',
    how: 'Plantillas versionadas JSON para authoring.',
    docRef: 'RFC-007',
  },
  {
    id: 'feature-registry',
    title: 'Feature Registry + IFeaturePort',
    status: 'partial',
    how: 'Catálogo bootstrap + online adapter; HTTP /api/features/*; scan opcional.',
    note: 'Model/Prediction/Policy registries completos aún no.',
    docRef: 'RFC-005',
  },
  {
    id: 'draft-apis',
    title: 'Draft estrategia / indicador (HTTP)',
    status: 'done',
    how: 'APIs draft-from-prompt sin cambiar contrato externo; proxy por debajo.',
  },
  {
    id: 'audit',
    title: 'Auditoría LLM (JSONL / PG)',
    status: 'done',
    how: 'BOLSA_LLM_AUDIT_PATH + tabla llm_calls (backend pg|both).',
  },
  {
    id: 'prediction',
    title: 'Prediction formal + LightGBM',
    status: 'partial',
    how: 'PredictionV1 + ModelArtifact; PredictionService; /api/predictions/*; lgbm_direction_v1 (extra ml) o numpy_fallback.',
    note: 'No LLM. Persistencia binarios PG/S3 pendiente.',
  },
  {
    id: 'package-split',
    title: 'Partición ai_governance / authoring / prediction / explanation',
    status: 'partial',
    how: 'Hoy bolsa_ai unificado con proxy; partición lógica adoptada en constitución.',
    note: 'Refactor de paquetes cuando el código lo exija (no bloquear F2).',
  },
];

export const AI_OUT_OF_SCOPE = [
  'Kubernetes / Kafka / microservicios reales',
  'Feast / Ray / Spark / LangGraph',
  'Agentes autónomos o RL',
  'Fine-tune LLM en v1',
  'LLM en hot path de scan u órdenes',
] as const;

export const AI_STACK_SUMMARY = [
  { layer: 'LLM authoring', choice: 'Ollama local (Qwen2.5-Coder) + OpenAI opcional + fallback heurístico' },
  { layer: 'ML ranking', choice: 'LightGBM (primario); CatBoost solo research' },
  { layer: 'Fine-tune LLM', choice: 'No en v1 (RAG + constrained decoding)' },
  { layer: 'DL / RL', choice: 'Aplazado (F6+)' },
] as const;

export const AI_STATUS_LABEL: Record<AiTrackStatus, string> = {
  done: 'Hecho',
  partial: 'Parcial',
  next: 'Siguiente',
  planned: 'Planificado',
  blocked: 'Bloqueado',
};
