/**
 * Drawer de oportunidad — composición de datos ya presentes (ADR-040 E).
 * Ranking ≠ BUY. Continuidad: Ver en Mercado · Preparar orden.
 */

import { useNavigate } from "react-router-dom";
import type {
  MesaCandidateRowV1,
  OpportunityRankRowV1,
  PortfolioPositionRiskInput,
  PortfolioRiskSnapshotV1,
} from "@bolsa/shared";
import {
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  NO_OPERATIONAL_PLAN_COPY,
  OPPORTUNITY_CATEGORY_LABEL,
  buildOperationalPlanFromStudy,
} from "@bolsa/shared";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { MesaWhatIfPanel } from "@/features/mesa/mesa-what-if-panel";
import { OperationalPlanView } from "@/features/mesa/operational-plan-view";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import { openHitInTrading } from "@/features/screeners/open-hit-in-trading";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";

type OpportunityDrawerProps = {
  open: boolean;
  onClose: () => void;
  rankRow: OpportunityRankRowV1 | null;
  portfolioRisk: PortfolioRiskSnapshotV1 | null;
  positions?: ReadonlyArray<PortfolioPositionRiskInput>;
  equity: number | null;
  cash: number | null;
  sectorByInstrumentId?: Record<string, string | null | undefined>;
};

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground">{value}</dd>
    </div>
  );
}

export function OpportunityDrawer({
  open,
  onClose,
  rankRow,
  portfolioRisk,
  positions = [],
  equity,
  cash,
  sectorByInstrumentId,
}: OpportunityDrawerProps) {
  const navigate = useNavigate();
  const openChartTab = useWorkspaceStore((s) => s.openChartTab);
  const updateChartTimeframe = useWorkspaceStore((s) => s.updateChartTimeframe);
  const focusInstrumentFromList = useWorkspaceStore(
    (s) => s.focusInstrumentFromList,
  );

  if (!rankRow) return null;
  const row: MesaCandidateRowV1 = rankRow.candidate;
  const study = row.study;
  const opinion =
    study?.opinion != null ? JOURNAL_STUDY_OPINION_LABELS[study.opinion] : "—";
  const sector = row.instrumentId
    ? (sectorByInstrumentId?.[row.instrumentId] ?? null)
    : null;

  function handleVerEnMercado() {
    if (!row.instrumentId) return;
    openHitInTrading(
      navigate,
      { openChartTab, updateChartTimeframe, focusInstrumentFromList },
      { instrumentId: row.instrumentId, symbol: row.symbol },
    );
    onClose();
  }

  function handlePrepararOrden() {
    openConfirmDrawer();
    navigate(CONFIRM_PATH);
    onClose();
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`${row.symbol} · Opportunity ${rankRow.quality}/100`}
      description={`${OPPORTUNITY_CATEGORY_LABEL[rankRow.category]} · ${rankRow.qualityLabel} · ranking ≠ permiso ≠ BUY`}
      className="max-w-lg"
    >
      <div className="space-y-4" data-testid="opportunity-drawer">
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <Field label="Tesis / opinión" value={opinion} />
          <Field
            label="Vigencia"
            value={
              study?.vigencia
                ? JOURNAL_STUDY_VIGENCIA_LABELS[study.vigencia]
                : "—"
            }
          />
          <Field
            label="Estado"
            value={`${row.statusLabel} · Gate ${row.gate}`}
          />
          <Field
            label="Portfolio Fit"
            value={`${rankRow.suitability} / Operability ${rankRow.operability}`}
          />
          {study?.hasOperationalPlan ? (
            <div className="sm:col-span-2">
              <OperationalPlanView
                plan={buildOperationalPlanFromStudy(study)}
                testId={`operational-plan-drawer-${row.symbol}`}
              />
            </div>
          ) : (
            <div className="sm:col-span-2 text-sm text-muted-foreground">
              {NO_OPERATIONAL_PLAN_COPY}
            </div>
          )}
          <Field label="Sector" value={sector?.trim() || "—"} />
        </dl>

        <MesaWhatIfPanel
          row={row}
          portfolioRisk={portfolioRisk}
          positions={positions}
          candidateSector={sector}
          equity={equity}
          cash={cash}
        />

        <div className="flex flex-wrap gap-2 border-t border-border pt-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!row.instrumentId}
            onClick={handleVerEnMercado}
            data-testid="opportunity-drawer-trading"
          >
            Ver en Mercado
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handlePrepararOrden}
            data-testid="opportunity-drawer-prepare"
          >
            Preparar orden
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cerrar
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
