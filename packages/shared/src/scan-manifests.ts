/** DTOs API — manifests de scan (ADR-010 P4). */

import type { ScanManifestV1 } from './platform-kernel.js';

export interface ScanManifestResponseDto {
  data: ScanManifestV1;
}
