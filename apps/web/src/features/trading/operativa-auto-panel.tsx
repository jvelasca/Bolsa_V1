/**
 * Bloque AUTO de DECISIÓN.
 *
 * La postura automática del valor vivía dentro de la tarjeta de decisión, donde
 * competía por el espacio con el CTA. Aquí es un asunto propio: qué hará AUTO
 * con este valor y con qué armado. Reutiliza la misma proyección que la cabina
 * (contexto operativo → POV → journey → AUTO); no calcula nada nuevo.
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */

import { AutoDeskPanel } from "@/features/trading/auto-desk-panel";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";
import { useAutoArmArmed } from "@/features/trading/demo-book-auto-arm";
import { resolvePaperAutoPosture } from "@/features/trading/resolve-paper-auto-posture";
import { usePositionJourneyReadout } from "@/features/trading/use-position-journey-readout";
import { usePositionOperationalView } from "@/features/trading/use-position-operational-view";
import {
  portfolioReconStatusFromReport,
  useOpsSelfEval,
} from "@/features/operational-console/use-ops-self-eval";
import type { InstrumentOperationalContextV1 } from "@/features/trading/use-instrument-operational-context";

/** Template de la estrategia que originó la posición o que sigue el valor. */
function resolveTemplateId(
  context: InstrumentOperationalContextV1,
): string | null {
  const { position, study } = context;
  const positionTemplateId = (
    position?.operational as { templateId?: unknown } | undefined
  )?.templateId;
  if (typeof positionTemplateId === "string") return positionTemplateId;
  const studyTemplateId = (study as { templateId?: string } | null)?.templateId;
  return studyTemplateId ?? null;
}

export function OperativaAutoPanel({
  context,
  className,
}: {
  context: InstrumentOperationalContextV1;
  className?: string;
}) {
  const { phase, position } = context;
  const openPosition = phase === "posicion" ? position : null;
  const { paperDExecuteEnv, killOn } = useMesaEntriesBlocked();
  const bookPrefs = useDemoBookPrefs();
  const autoArmed = useAutoArmArmed();
  const autoPosture = resolvePaperAutoPosture({
    bookMode: bookPrefs.mode,
    autoArmed,
    paperDExecuteEnv,
  });
  const opsEval = useOpsSelfEval(context.accountId);
  const reconStatus = portfolioReconStatusFromReport(opsEval.data);
  const povResult = usePositionOperationalView(openPosition, reconStatus);
  const journey = usePositionJourneyReadout({
    position: openPosition,
    view: povResult?.view ?? null,
    autoPosture,
    killOn,
    enabled: phase === "posicion",
  });

  return (
    <div className={className} data-testid="operativa-auto-block">
      <AutoDeskPanel
        templateId={resolveTemplateId(context)}
        journey={journey}
        defaultOpen
      />
    </div>
  );
}
