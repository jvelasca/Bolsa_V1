/** Lab WFE / stability helpers (P3.I). Not CPCV or production edge. */

export const WFE_ACCEPTABLE = 0.7;
export const WFE_FRAGILE = 0.5;
/** Warn when fold OOS CV exceeds this (std / |mean|). */
export const OOS_CV_UNSTABLE = 1.0;
/** Warn when fewer than this share of folds have OOS ≥ 0. */
export const POSITIVE_FOLD_SHARE_MIN = 0.5;

export type WfeBand = "acceptable" | "fragile" | "weak" | "undefined";

export function classifyWfe(wfe: number | null | undefined): WfeBand {
  if (wfe == null || !Number.isFinite(wfe)) return "undefined";
  if (wfe >= WFE_ACCEPTABLE) return "acceptable";
  if (wfe >= WFE_FRAGILE) return "fragile";
  return "weak";
}

export function wfeBandLabel(band: WfeBand): string {
  switch (band) {
    case "acceptable":
      return "aceptable";
    case "fragile":
      return "frágil";
    case "weak":
      return "débil";
    default:
      return "n/d";
  }
}

export function formatWfe(wfe: number | null | undefined): string {
  if (wfe == null || !Number.isFinite(wfe)) return "n/d";
  return wfe.toFixed(2);
}

export function formatPositiveFoldShare(
  share: number | null | undefined,
  nFolds?: number,
): string {
  if (share == null || !Number.isFinite(share)) return "—";
  if (nFolds != null && Number.isFinite(nFolds) && nFolds > 0) {
    const positive = Math.round(share * nFolds);
    return `${positive}/${nFolds} pliegues OOS≥0`;
  }
  return `${Math.round(share * 100)}% OOS≥0`;
}

export type WfStabilityFlags = {
  weakWfe: boolean;
  unstableCv: boolean;
  fewPositiveFolds: boolean;
};

export function walkForwardStabilityFlags(input: {
  walkForwardEfficiency?: number | null;
  oosCv?: number | null;
  positiveOosFoldShare?: number | null;
}): WfStabilityFlags {
  const band = classifyWfe(input.walkForwardEfficiency);
  return {
    weakWfe: band === "weak",
    unstableCv:
      input.oosCv != null &&
      Number.isFinite(input.oosCv) &&
      input.oosCv > OOS_CV_UNSTABLE,
    fewPositiveFolds:
      input.positiveOosFoldShare != null &&
      Number.isFinite(input.positiveOosFoldShare) &&
      input.positiveOosFoldShare < POSITIVE_FOLD_SHARE_MIN,
  };
}
