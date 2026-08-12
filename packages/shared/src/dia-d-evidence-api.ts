/**
 * DTOs Evidence sesión DÍA D (Fase 2 research_evidence, source=dia_d_session).
 *
 * El wire (`DiaDSessionEvidencePersistRequestDto.evidence`, blob opaco) no
 * cambia; este DTO declara la *forma concreta* del informe para que
 * `trading-dia-d-replay-panel.tsx` serialice sin `as unknown as`.
 */

export type DiaDEvidenceBandDto =
  | "favorable"
  | "mixed"
  | "adverse"
  | "incomplete";

export type DiaDSessionEvidenceV1Dto = {
  schemaVersion: "dia_d_session_evidence_v1";
  band: DiaDEvidenceBandDto;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  claims: string[];
  warnings: string[];
  metrics: {
    mode: string;
    returnPct: number;
    maxDrawdownPct: number;
    tradeCount: number;
    finalEquity: number;
    autoReturnPct: number;
    returnDeltaVsAutoPct: number;
    accepted: number;
    rejected: number;
  };
  paragraphs: [string, string, string];
  disclaimer: string;
};
