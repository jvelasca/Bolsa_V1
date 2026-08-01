/**
 * Policy Gate (RFC-008 D1) — evaluación determinista hard.
 * Opportunity ≠ Permission: un veto no altera la oportunidad.
 */

import type {
  PolicyGateInput,
  PolicyGateResult,
  PolicyRuleResult,
} from './trading-policy.js';

function rule(
  name: string,
  limit: string,
  actual: string,
  ok: boolean,
  message?: string,
): PolicyRuleResult {
  return {
    rule: name,
    limit,
    actual,
    status: ok ? 'PASSED' : 'FAILED',
    message,
  };
}

export function evaluatePolicyGate(input: PolicyGateInput): PolicyGateResult {
  const { policy, instrument, proposed, context = {}, evidence = {} } = input;
  const evaluated: PolicyRuleResult[] = [];
  const vetoReasons: string[] = [];

  const push = (r: PolicyRuleResult) => {
    evaluated.push(r);
    if (r.status === 'FAILED') {
      vetoReasons.push(r.message ?? `${r.rule}: ${r.actual} vs ${r.limit}`);
    }
  };

  const u = policy.universe;
  push(
    rule(
      'AssetClass',
      u.allowedAssetClasses.join('|'),
      instrument.assetClass,
      u.allowedAssetClasses.includes(instrument.assetClass),
    ),
  );

  if (instrument.symbol && u.excludedTickers.includes(instrument.symbol.toUpperCase())) {
    push(
      rule(
        'ExcludedTicker',
        'not in blacklist',
        instrument.symbol,
        false,
        `Ticker excluido: ${instrument.symbol}`,
      ),
    );
  }

  if (instrument.sector && u.excludedSectors.includes(instrument.sector)) {
    push(
      rule(
        'ExcludedSector',
        `not in ${u.excludedSectors.join('|')}`,
        instrument.sector,
        false,
      ),
    );
  }

  if (u.minMarketCapUSD != null && instrument.marketCapUSD != null) {
    push(
      rule(
        'MinMarketCap',
        String(u.minMarketCapUSD),
        String(instrument.marketCapUSD),
        instrument.marketCapUSD >= u.minMarketCapUSD,
      ),
    );
  }

  if (instrument.averageDailyVolumeUSD != null) {
    push(
      rule(
        'MinADV',
        String(u.minAverageDailyVolumeUSD),
        String(instrument.averageDailyVolumeUSD),
        instrument.averageDailyVolumeUSD >= u.minAverageDailyVolumeUSD,
      ),
    );
  }

  if (u.maxSpreadBps != null && instrument.spreadBps != null) {
    push(
      rule(
        'MaxSpreadBps',
        String(u.maxSpreadBps),
        String(instrument.spreadBps),
        instrument.spreadBps <= u.maxSpreadBps,
      ),
    );
  }

  const x = policy.exposure;
  push(
    rule(
      'MaxLeverage',
      String(x.maxLeverage),
      String(proposed.leverage),
      proposed.leverage <= x.maxLeverage,
    ),
  );
  push(
    rule(
      'MaxOpenPositions',
      String(x.maxOpenPositions),
      String(proposed.openPositionsCount),
      proposed.openPositionsCount < x.maxOpenPositions,
    ),
  );
  push(
    rule(
      'MaxConcentration',
      `${x.maxPortfolioConcentrationPct}%`,
      `${proposed.portfolioConcentrationPct}%`,
      proposed.portfolioConcentrationPct <= x.maxPortfolioConcentrationPct,
    ),
  );

  const risk = policy.risk;
  push(
    rule(
      'MaxRiskPerTrade',
      `${risk.maxRiskPerTradePct}%`,
      `${proposed.riskPctOfAccount}%`,
      proposed.riskPctOfAccount <= risk.maxRiskPerTradePct,
    ),
  );
  push(
    rule(
      'MinRewardToRisk',
      String(risk.minRewardToRiskRatio),
      String(proposed.rewardToRiskRatio),
      proposed.rewardToRiskRatio >= risk.minRewardToRiskRatio,
    ),
  );
  if (risk.stopLossRequired) {
    push(
      rule(
        'StopLossRequired',
        'true',
        String(proposed.hasStopLoss),
        proposed.hasStopLoss,
        proposed.hasStopLoss ? undefined : 'Stop loss obligatorio',
      ),
    );
  }

  const dd = input.accountDrawdown ?? {};
  if (dd.dailyPct != null) {
    push(
      rule(
        'HardDailyDrawdown',
        `<= ${risk.hardDailyDrawdownLimitPct}%`,
        `${dd.dailyPct}%`,
        dd.dailyPct <= risk.hardDailyDrawdownLimitPct,
        'Circuit breaker: drawdown diario',
      ),
    );
  } else {
    evaluated.push({
      rule: 'HardDailyDrawdown',
      limit: `<= ${risk.hardDailyDrawdownLimitPct}%`,
      actual: 'n/a',
      status: 'SKIPPED',
    });
  }
  if (risk.hardWeeklyDrawdownLimitPct != null) {
    if (dd.weeklyPct != null) {
      push(
        rule(
          'HardWeeklyDrawdown',
          `<= ${risk.hardWeeklyDrawdownLimitPct}%`,
          `${dd.weeklyPct}%`,
          dd.weeklyPct <= risk.hardWeeklyDrawdownLimitPct,
          'Circuit breaker: drawdown semanal',
        ),
      );
    } else {
      evaluated.push({
        rule: 'HardWeeklyDrawdown',
        limit: `<= ${risk.hardWeeklyDrawdownLimitPct}%`,
        actual: 'n/a',
        status: 'SKIPPED',
      });
    }
  }
  if (dd.maxPct != null) {
    push(
      rule(
        'HardMaxDrawdown',
        `<= ${risk.hardMaxDrawdownLimitPct}%`,
        `${dd.maxPct}%`,
        dd.maxPct <= risk.hardMaxDrawdownLimitPct,
        'Circuit breaker: max drawdown',
      ),
    );
  } else {
    evaluated.push({
      rule: 'HardMaxDrawdown',
      limit: `<= ${risk.hardMaxDrawdownLimitPct}%`,
      actual: 'n/a',
      status: 'SKIPPED',
    });
  }

  const b = policy.blackouts;
  if (context.hoursToEarnings != null && context.hoursToEarnings >= 0) {
    push(
      rule(
        'PreEarningsBlackout',
        `>= ${b.blockPreEarningsHours}h clear`,
        `${context.hoursToEarnings}h to earnings`,
        context.hoursToEarnings >= b.blockPreEarningsHours,
        context.hoursToEarnings < b.blockPreEarningsHours
          ? 'Blackout pre-earnings'
          : undefined,
      ),
    );
  }
  if (context.hoursSinceEarnings != null && context.hoursSinceEarnings >= 0) {
    push(
      rule(
        'PostEarningsBlackout',
        `>= ${b.blockPostEarningsHours}h clear`,
        `${context.hoursSinceEarnings}h since earnings`,
        context.hoursSinceEarnings >= b.blockPostEarningsHours,
      ),
    );
  }
  if (b.blockFedFomc && context.fedFomcActive) {
    push(rule('FedFomcBlackout', 'clear', 'active', false, 'FOMC activo'));
  }
  if (b.blockEcb && context.ecbActive) {
    push(rule('EcbBlackout', 'clear', 'active', false, 'ECB activo'));
  }
  if (b.blockHighImpactMacro && context.highImpactMacroActive) {
    push(
      rule(
        'HighImpactMacroBlackout',
        'clear',
        'active',
        false,
        'Macro high-impact activo',
      ),
    );
  }

  const ev = policy.evidence;
  if (evidence.autoLive) {
    if (ev.requireEdgeReportForAutoLive) {
      push(
        rule(
          'EdgeReportRequired',
          'present',
          evidence.edgeReportPresent ? 'present' : 'missing',
          Boolean(evidence.edgeReportPresent),
        ),
      );
    }
    if (evidence.credibility != null) {
      push(
        rule(
          'MinCredibility',
          String(ev.minimumRequiredCredibility),
          String(evidence.credibility),
          evidence.credibility >= ev.minimumRequiredCredibility,
        ),
      );
    }
    if (evidence.walkForwardEfficiency != null) {
      push(
        rule(
          'MinWFE',
          String(ev.minimumWalkForwardEfficiency),
          String(evidence.walkForwardEfficiency),
          evidence.walkForwardEfficiency >= ev.minimumWalkForwardEfficiency,
        ),
      );
    }
    if (evidence.monteCarloPValue != null) {
      push(
        rule(
          'MaxMonteCarloP',
          String(ev.maxMonteCarloPValue),
          String(evidence.monteCarloPValue),
          evidence.monteCarloPValue <= ev.maxMonteCarloPValue,
        ),
      );
    }
  }

  return {
    passed: vetoReasons.length === 0,
    policyId: policy.policyId,
    policyVersion: policy.version,
    evaluatedRules: evaluated,
    vetoReasons,
  };
}
