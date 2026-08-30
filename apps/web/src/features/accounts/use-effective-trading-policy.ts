/**
 * Perfil activo → EffectiveTradingPolicy (V1.30 encaje vs cartera).
 */

import { useQuery } from "@tanstack/react-query";
import { resolveEffectiveTradingPolicy } from "@bolsa/shared";
import { api } from "@/lib/api";
import { useActiveAccount } from "./use-active-account";

export function useEffectiveTradingPolicy() {
  const { effectiveAccountId } = useActiveAccount();
  const query = useQuery({
    queryKey: ["account-active-profile", effectiveAccountId],
    queryFn: () => api.getAccountActiveProfile(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
  });
  const templateId = query.data?.data?.selectedPolicyTemplateId ?? null;
  const policy = resolveEffectiveTradingPolicy(templateId);
  return {
    policy,
    templateId: policy.templateId,
    maxSectorExposurePct: policy.exposure.maxSectorExposurePct,
    maxPortfolioConcentrationPct: policy.exposure.maxPortfolioConcentrationPct,
    isLoading: query.isLoading,
  };
}
