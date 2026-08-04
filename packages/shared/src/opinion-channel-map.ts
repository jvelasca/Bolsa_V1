/**
 * Mapa Dictamen → AVISO | ALARMA (O3-C / diseño §5.2).
 * Atributo de canal del dictamen — no es un segundo inbox mental.
 * Batch EOD / email: D2 scaffold (`ESTUDIO_OPINION_EMAIL_*`); toast UI en PlatformShell.
 */

import type { InstrumentDailyOpinionStance, InstrumentDailyOpinionV1 } from './instrument-daily-opinion.js';

export const OPINION_CHANNEL_LEVELS = ['silent', 'aviso', 'alarma'] as const;
export type OpinionChannelLevel = (typeof OPINION_CHANNEL_LEVELS)[number];

export const OPINION_CHANNEL_LEVEL_LABELS: Record<OpinionChannelLevel, string> = {
  silent: 'Silencio',
  aviso: 'Aviso',
  alarma: 'Alarma',
};

/** Regla producto por defecto (§5.2). */
export function mapOpinionToChannel(input: {
  stance: InstrumentDailyOpinionStance;
  dictamenStars: number;
}): OpinionChannelLevel {
  const stars = Math.min(5, Math.max(1, Math.round(input.dictamenStars)));
  switch (input.stance) {
    case 'buy':
      return stars >= 4 ? 'alarma' : stars >= 2 ? 'aviso' : 'silent';
    case 'sell_exit':
    case 'reduce':
      return stars >= 3 ? 'alarma' : 'aviso';
    case 'overbought':
    case 'review_strategy':
      return 'aviso';
    case 'hold_watch':
    case 'no_trade':
    default:
      return 'silent';
  }
}

export type OpinionChannelItemV1 = {
  instrumentId: string;
  symbol: string;
  level: Exclude<OpinionChannelLevel, 'silent'>;
  stance: InstrumentDailyOpinionStance;
  dictamenStars: number;
  strategyStars: number | null;
  ioScore: number | null;
  reasons: string[];
  asOfBarDate: string;
  opinionId: string;
  /** SEMI puede encolar Confirm desde Alarma. */
  actionable: boolean;
};

export function buildOpinionChannelItems(
  rows: Array<{
    opinion: InstrumentDailyOpinionV1;
    symbol: string;
  }>,
): OpinionChannelItemV1[] {
  const out: OpinionChannelItemV1[] = [];
  for (const { opinion, symbol } of rows) {
    const level = mapOpinionToChannel({
      stance: opinion.stance,
      dictamenStars: opinion.dictamenStars,
    });
    if (level === 'silent') continue;
    out.push({
      instrumentId: opinion.instrumentId,
      symbol,
      level,
      stance: opinion.stance,
      dictamenStars: opinion.dictamenStars,
      strategyStars: opinion.strategyStars,
      ioScore: opinion.ioScore,
      reasons: [...opinion.reasons],
      asOfBarDate: opinion.asOfBarDate,
      opinionId: opinion.id,
      actionable: level === 'alarma',
    });
  }
  const rank = (level: OpinionChannelItemV1['level']) => (level === 'alarma' ? 0 : 1);
  const stanceRank = (s: InstrumentDailyOpinionStance) => {
    if (s === 'buy') return 0;
    if (s === 'sell_exit' || s === 'reduce') return 1;
    return 2;
  };
  return out.sort(
    (a, b) =>
      rank(a.level) - rank(b.level) ||
      stanceRank(a.stance) - stanceRank(b.stance) ||
      b.dictamenStars - a.dictamenStars ||
      a.symbol.localeCompare(b.symbol),
  );
}
