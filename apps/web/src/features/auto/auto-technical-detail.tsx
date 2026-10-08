/**
 * UI Contract 5.0 (`RT-04`) — mecanismo único de profundidad.
 * AutoTechnicalDetail delega en el componente compartido para no crear idioms paralelos.
 */

import {
  TECHNICAL_DETAIL_LABEL,
  TechnicalDetail,
} from "@/components/technical-detail";

export function AutoTechnicalDetail({
  children,
  testId = "auto-technical-detail",
  label = TECHNICAL_DETAIL_LABEL,
}: {
  children: React.ReactNode;
  testId?: string;
  label?: string;
}) {
  return (
    <TechnicalDetail testId={testId} label={label}>
      {children}
    </TechnicalDetail>
  );
}
