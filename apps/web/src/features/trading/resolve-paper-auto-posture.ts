/**
 * F8 — derive PAPER AUTO / SEMI posture from demo-book prefs + arm + kill-switch env.
 */

import { buildPaperAutoPosture, type PaperAutoPostureV1 } from "@bolsa/shared";
import { loadAutoArm } from "@/features/trading/demo-book-auto-arm";
import {
  loadDemoBookPrefs,
  type DemoBookMode,
} from "@/features/trading/demo-book-prefs";

export function resolvePaperAutoPosture(input?: {
  bookMode?: DemoBookMode | null;
  autoArmed?: boolean | null;
  paperDExecuteEnv?: boolean | null;
}): PaperAutoPostureV1 {
  const prefs = loadDemoBookPrefs();
  const arm = loadAutoArm();
  return buildPaperAutoPosture({
    bookMode: input?.bookMode ?? prefs.mode,
    autoArmed: input?.autoArmed ?? arm.armed,
    paperDExecuteEnv: input?.paperDExecuteEnv ?? false,
  });
}
