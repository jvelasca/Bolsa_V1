import type { BacktestStrategyType } from "./types.js";
import type { SignalEventV1, SignalKind } from "./signal-events.js";

/** Canales de entrega SC-6 — toast es cliente; webhook/email en servidor. */
export type AlertChannelType = "toast" | "webhook" | "email";

export const DEFAULT_ALERT_CHANNELS: AlertChannelType[] = ["toast"];

export const ALERT_CHANNEL_LABELS: Record<AlertChannelType, string> = {
  toast: "Toast (app)",
  webhook: "Webhook",
  email: "Email",
};

/** Suscripción a señales de estrategia — SC-3 (paralelo a price_alerts). */
export interface SignalAlertSubscriptionDto {
  id: string;
  instrumentId: string;
  symbol: string;
  strategyDefinitionId?: string | null;
  presetKey?: BacktestStrategyType | null;
  timeframe: string;
  signalKinds: SignalKind[];
  channels?: AlertChannelType[];
  webhookUrl?: string | null;
  emailTo?: string | null;
  isActive: boolean;
  lastTriggeredAt?: string | null;
  lastBarTimestamp?: string | null;
  lastSignalKind?: SignalKind | null;
  lastSignalPrice?: number | null;
  note?: string | null;
  createdAt: string;
}

export interface CreateSignalAlertSubscriptionRequestDto {
  instrumentId: string;
  strategyDefinitionId?: string;
  presetKey?: BacktestStrategyType;
  timeframe?: string;
  signalKinds?: SignalKind[];
  channels?: AlertChannelType[];
  webhookUrl?: string;
  emailTo?: string;
  note?: string;
}

export interface AlertChannelDispatchDto {
  subscriptionId: string;
  channel: AlertChannelType;
  ok: boolean;
  error?: string | null;
}

export interface TriggeredSignalAlertDto {
  subscription: SignalAlertSubscriptionDto;
  signal: SignalEventV1;
  dispatches?: AlertChannelDispatchDto[];
}

export interface SignalAlertSubscriptionsResponseDto {
  data: SignalAlertSubscriptionDto[];
}

export interface SignalAlertSubscriptionResponseDto {
  data: SignalAlertSubscriptionDto;
}

export interface EvaluateSignalAlertsResponseDto {
  data: TriggeredSignalAlertDto[];
  dispatches?: AlertChannelDispatchDto[];
}

export function formatSignalAlertToast(
  hit: TriggeredSignalAlertDto,
  kindLabels: Record<SignalKind, string>,
): string {
  const kind = kindLabels[hit.signal.kind] ?? hit.signal.kind;
  return `${hit.subscription.symbol}: ${kind} @ ${hit.signal.price.toFixed(2)} (estrategia)`;
}
