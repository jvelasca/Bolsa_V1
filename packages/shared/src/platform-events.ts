/** DTOs API — bus de eventos platform_events (ADR-010). */

import type { PlatformEventType, PlatformEventV1 } from './platform-kernel.js';

export type PlatformEventDto = PlatformEventV1;

export interface PlatformEventsListResponseDto {
  data: PlatformEventDto[];
}

export interface ListPlatformEventsQuery {
  limit?: number;
  type?: PlatformEventType;
  correlationId?: string;
}
