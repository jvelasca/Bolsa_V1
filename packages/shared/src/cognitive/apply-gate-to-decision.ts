/**
 * D2.4 — Policy Gate sobre DecisionPackage (TS mirror).
 * Opportunity ≠ Permission: VETO no reescribe `action`.
 */

import type { DecisionMemoryEntryV1 } from './decision-memory.js';
import type { DecisionAction, DecisionPackageV1 } from './decision-package.js';
import { evaluatePolicyGate } from './policy-gate.js';
import type {
  PolicyGateInput,
  PolicyGateResult,
  TradingPolicyV1,
} from './trading-policy.js';

export interface GatedDecisionV1 {
  package: DecisionPackageV1;
  gate: PolicyGateResult | null;
  memory: DecisionMemoryEntryV1;
  executionAllowed: boolean;
}

function memoryId(): string {
  return `MEM-${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;
}

function buildMemory(
  partial: Omit<DecisionMemoryEntryV1, 'artifactType' | 'schemaVersion' | 'memoryId' | 'createdAt'> & {
    memoryId?: string;
  },
): DecisionMemoryEntryV1 {
  return {
    artifactType: 'ART-DECISION-MEMORY',
    schemaVersion: '1.0.0',
    memoryId: partial.memoryId ?? memoryId(),
    decisionId: partial.decisionId,
    instrumentId: partial.instrumentId,
    outcome: partial.outcome,
    reasons: partial.reasons,
    policyRuleIds: partial.policyRuleIds,
    reevaluateWhen: partial.reevaluateWhen,
    opportunityIntact: partial.opportunityIntact,
    policyId: partial.policyId,
    policyVersion: partial.policyVersion,
    createdAt: new Date().toISOString(),
  };
}

const OPENING: DecisionAction[] = ['recommend_long', 'recommend_short'];

export function applyPolicyGateToDecision(
  packageIn: DecisionPackageV1,
  policy: TradingPolicyV1,
  trade: PolicyGateInput['instrument'] &
    PolicyGateInput['proposed'] & {
      context?: PolicyGateInput['context'];
      evidence?: PolicyGateInput['evidence'];
    },
): GatedDecisionV1 {
  const opening = OPENING.includes(packageIn.action);

  if (!opening) {
    const memory = buildMemory({
      decisionId: packageIn.decisionId,
      instrumentId: packageIn.instrumentId,
      outcome: 'deferred',
      reasons: [`action=${packageIn.action}: sin apertura de posición`],
      policyRuleIds: [],
      reevaluateWhen: [],
      opportunityIntact: true,
      policyId: policy.policyId,
      policyVersion: policy.version,
    });
    return {
      package: {
        ...packageIn,
        policyVersion: policy.version,
        complianceCheck: {
          passed: true,
          policyId: policy.policyId,
          policyVersion: policy.version,
          evaluatedRules: [],
          vetoReasons: [],
        },
        memoryRef: memory.memoryId,
        notes: [...(packageIn.notes ?? []), 'Gate: sin apertura — deferred'],
      },
      gate: null,
      memory,
      executionAllowed: false,
    };
  }

  let gate = evaluatePolicyGate({
    policy,
    instrument: {
      symbol: trade.symbol,
      assetClass: trade.assetClass,
      marketCapUSD: trade.marketCapUSD,
      averageDailyVolumeUSD: trade.averageDailyVolumeUSD,
      sector: trade.sector,
      spreadBps: trade.spreadBps,
      atrPct: trade.atrPct,
    },
    proposed: {
      riskPctOfAccount: trade.riskPctOfAccount,
      rewardToRiskRatio: trade.rewardToRiskRatio,
      leverage: trade.leverage,
      hasStopLoss: trade.hasStopLoss,
      openPositionsCount: trade.openPositionsCount,
      portfolioConcentrationPct: trade.portfolioConcentrationPct,
      sectorExposurePct: trade.sectorExposurePct,
    },
    context: trade.context,
    evidence: trade.evidence,
  });

  if (packageIn.action === 'recommend_short' && !policy.universe.allowShorting) {
    gate = {
      ...gate,
      passed: false,
      evaluatedRules: [
        ...gate.evaluatedRules,
        {
          rule: 'AllowShorting',
          limit: 'false',
          actual: 'recommend_short',
          status: 'FAILED',
          message: 'Shorting no permitido por TradingPolicy',
        },
      ],
      vetoReasons: [
        ...gate.vetoReasons,
        'Shorting no permitido por TradingPolicy',
      ],
    };
  }

  const memory = buildMemory({
    decisionId: packageIn.decisionId,
    instrumentId: packageIn.instrumentId,
    outcome: gate.passed ? 'accepted' : 'rejected',
    reasons: gate.passed
      ? [`Policy PASS — action=${packageIn.action}`]
      : [...gate.vetoReasons],
    policyRuleIds: gate.evaluatedRules
      .filter((r) => r.status === (gate.passed ? 'PASSED' : 'FAILED'))
      .map((r) => r.rule),
    reevaluateWhen: gate.passed
      ? []
      : gate.evaluatedRules
          .filter((r) => r.rule.includes('Earnings') || r.rule.includes('Blackout'))
          .map(() => 'after_blackout_clears'),
    opportunityIntact: true,
    policyId: policy.policyId,
    policyVersion: policy.version,
  });

  return {
    package: {
      ...packageIn,
      policyVersion: policy.version,
      complianceCheck: gate,
      memoryRef: memory.memoryId,
      notes: [
        ...(packageIn.notes ?? []),
        gate.passed ? 'Gate: PASS — execution_allowed' : `Gate: VETO — ${gate.vetoReasons.join('; ')}`,
      ],
    },
    gate,
    memory,
    executionAllowed: gate.passed,
  };
}
