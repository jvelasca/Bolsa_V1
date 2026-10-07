/**
 * AUTO UI REFACTOR 4.0 (P3) — hook read-only del TOP 3 oportunidades.
 *
 * Una sola query sobre el DTO canónico; el view-model puro (`auto-top3-opportunities.ts`) añade
 * etiquetas y tonos SIN reinterpretar. La UI no re-deriva el score.
 *
 * @see docs/engineering/spec-auto-ui-definitiva-2026-10-07.md §7 (T2)
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  buildAutoTop3View,
  type AutoTop3DtoV1,
  type AutoTop3ViewV1,
} from "@/features/auto/auto-top3-opportunities";

export function useAutoTop3Opportunities(input?: { enabled?: boolean }) {
  const query = useQuery({
    queryKey: ["auto-top3-opportunities", "latest"],
    queryFn: () => api.getLatestTop3Opportunities(),
    enabled: input?.enabled ?? true,
    staleTime: 15_000,
    retry: false,
  });

  const view: AutoTop3ViewV1 | null = useMemo(
    () =>
      query.data
        ? buildAutoTop3View(query.data as unknown as AutoTop3DtoV1)
        : null,
    [query.data],
  );

  return { ...query, view };
}
