import type { StatisticalSuiteResult, WfeSource } from './evidence-engine.js';
import { computeCredibility } from './evidence-engine.js';

export type { WfeSource };

/** Compact lab WFE carried in research_trials.blocks.labEvidence / WF / CPCV. */
export type LabWfeSnapshot = {
  walkForwardEfficiency: number;
  wfeSource: WfeSource;
  mode: 'walkforward' | 'cpcv' | 'holdout';
};

export function pickLabWalkForwardEfficiency(input: {
  walkForwardEfficiency?: number | null;
  meanOosScore?: number | null;
  meanIsScore?: number | null;
}): number | null {
  if (
    input.walkForwardEfficiency != null &&
    Number.isFinite(input.walkForwardEfficiency)
  ) {
    return input.walkForwardEfficiency;
  }
  const meanOos = input.meanOosScore;
  const meanIs = input.meanIsScore;
  if (
    meanOos != null &&
    meanIs != null &&
    Number.isFinite(meanOos) &&
    Number.isFinite(meanIs) &&
    meanIs > 1e-9
  ) {
    return Math.round((meanOos / meanIs) * 10000) / 10000;
  }
  return null;
}

/** Merge lab WFE into a statistical suite (does not invent MC/DSR). */
export function applyLabWfeToSuite(
  suite: StatisticalSuiteResult,
  wfe: number,
  source: WfeSource = 'lab_score',
): StatisticalSuiteResult {
  return {
    ...suite,
    walkForwardEfficiency: wfe,
    wfeSource: source,
  };
}

/** Credibility hint when only lab WFE is available (other suite fields empty). */
export function credibilityHintFromLabWfe(
  wfe: number,
  trialsN = 1,
): { credibility: number; edgeScore: number; band: string; note: string } {
  const suite = applyLabWfeToSuite({ trialsN }, wfe, 'lab_score');
  const { credibility, edgeScore, band } = computeCredibility(suite);
  return {
    credibility,
    edgeScore,
    band,
    note: 'Hint con solo WFE lab (score); no es EdgeReport completo ni Sharpe WFE.',
  };
}
