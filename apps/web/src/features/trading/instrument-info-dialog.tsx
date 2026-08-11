import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type {
  InstrumentProfileSectionDto,
  InstrumentProfileTabDto,
} from "@bolsa/shared";
import { Dialog, DialogTabs } from "@/components/ui/dialog";
import { formatPrice } from "@/features/charts/chart-utils";
import { InstrumentAnalysisSummary } from "@/features/trading/instrument-analysis-summary";
import { InstrumentDbTab } from "@/features/trading/instrument-db-tab";
import { api } from "@/lib/api";
import { useTradingUiStore } from "@/stores/trading-ui-store";

type InfoTabId = "basic" | "analysis" | "dividends" | "financials" | "database";

const DEFAULT_INFO_TAB: InfoTabId = "basic";

function ProfileSection({ section }: { section: InstrumentProfileSectionDto }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {section.title}
      </p>
      {section.text ? (
        <p className="text-xs leading-relaxed text-foreground/90">
          {section.text}
        </p>
      ) : (
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          {(section.fields ?? []).map((field) => (
            <div key={`${section.title}-${field.label}`} className="contents">
              <dt className="text-muted-foreground">{field.label}</dt>
              <dd className="text-right tabular-nums">{field.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

function ProfileTabContent({
  tab,
}: {
  tab: InstrumentProfileTabDto | undefined;
}) {
  if (!tab?.sections?.length) {
    return (
      <p className="text-xs text-muted-foreground">
        No hay datos disponibles todavía. Se actualizarán en la próxima
        sincronización.
      </p>
    );
  }

  return (
    <div className="max-h-[50vh] space-y-4 overflow-y-auto pr-1">
      {tab.sections.map((section) => (
        <ProfileSection key={section.title} section={section} />
      ))}
      {tab.history && tab.history.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Histórico de dividendos
          </p>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
            {tab.history.map((event) => (
              <div key={event.date} className="contents">
                <dt className="text-muted-foreground">{event.date}</dt>
                <dd className="text-right tabular-nums">
                  {event.amount != null ? formatPrice(event.amount) : "—"}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}

export function InstrumentInfoDialog() {
  const instrument = useTradingUiStore((s) => s.infoInstrument);
  const close = useTradingUiStore((s) => s.closeInfoDialog);
  const [activeTab, setActiveTab] = useState<InfoTabId>(DEFAULT_INFO_TAB);

  useEffect(() => {
    if (instrument?.id) setActiveTab(DEFAULT_INFO_TAB);
  }, [instrument?.id]);

  const statusQuery = useQuery({
    queryKey: ["data-status", instrument?.id],
    queryFn: () => api.getDataStatus(instrument!.id),
    enabled: Boolean(instrument?.id),
  });

  const profileQuery = useQuery({
    queryKey: ["instrument-profile", instrument?.id],
    queryFn: () => api.getInstrumentProfile(instrument!.id),
    enabled: Boolean(instrument?.id),
  });

  const detailQuery = useQuery({
    queryKey: ["instrument-detail", instrument?.id],
    queryFn: () => api.getInstrument(instrument!.id),
    enabled: Boolean(instrument?.id),
    staleTime: 0,
  });

  const profile = profileQuery.data?.data ?? null;
  const dataStatus = statusQuery.data?.data;
  const detail = detailQuery.data?.data;
  const isin = detail?.isin ?? instrument?.isin;
  const sector = detail?.sector ?? instrument?.sector;
  const lastClose =
    detailQuery.data?.meta.priceSummary?.lastClose ??
    instrument?.meta.lastClose;

  if (!instrument) return null;

  return (
    <Dialog
      open
      onClose={close}
      title={instrument.symbol}
      description={instrument.name}
      className="max-w-lg"
    >
      <dl className="mb-4 grid grid-cols-2 gap-2 text-sm">
        <dt className="text-muted-foreground">Exchange</dt>
        <dd>{detail?.exchange ?? instrument.exchange}</dd>
        <dt className="text-muted-foreground">Yahoo</dt>
        <dd>{detail?.yahooSymbol ?? instrument.yahooSymbol}</dd>
        <dt className="text-muted-foreground">ISIN</dt>
        <dd className="font-mono text-xs">
          {detailQuery.isLoading && !isin ? "…" : isin?.trim() || "—"}
        </dd>
        <dt className="text-muted-foreground">Sector</dt>
        <dd>{sector ?? "—"}</dd>
        <dt className="text-muted-foreground">Último cierre</dt>
        <dd>{lastClose != null ? formatPrice(lastClose) : "—"}</dd>
      </dl>
      {!detailQuery.isLoading && !isin?.trim() && (
        <p className="mb-3 text-[10px] text-muted-foreground">
          ISIN aún no está en BD. Impórtalo buscando por ISIN en listas, o se
          guardará al importar el activo desde una búsqueda por código ISIN.
          Yahoo ya no expone el ISIN en su API pública.
        </p>
      )}

      <DialogTabs
        tabs={[
          { id: "basic", label: "Info básica" },
          { id: "analysis", label: "Análisis" },
          { id: "dividends", label: "Dividendos" },
          { id: "financials", label: "Finanzas" },
          { id: "database", label: "Nuestra BD" },
        ]}
        active={activeTab}
        onChange={(id) => setActiveTab(id as InfoTabId)}
      />

      <div className="mt-3">
        {activeTab === "database" && (
          <InstrumentDbTab
            instrumentId={instrument.id}
            dataStatus={dataStatus}
          />
        )}
        {activeTab === "analysis" && (
          <InstrumentAnalysisSummary
            instrumentId={instrument.id}
            symbol={instrument.symbol}
          />
        )}
        {activeTab === "basic" && <ProfileTabContent tab={profile?.basic} />}
        {activeTab === "dividends" && (
          <ProfileTabContent tab={profile?.dividends} />
        )}
        {activeTab === "financials" && (
          <ProfileTabContent tab={profile?.financials} />
        )}
      </div>

      {activeTab !== "database" && activeTab !== "analysis" && (
        <p className="mt-4 text-[10px] text-muted-foreground">
          Datos orientativos desde Yahoo Finance
          {profile?.fetchedAt
            ? ` · actualizado ${new Date(profile.fetchedAt).toLocaleString("es-ES")}`
            : ""}
          .
        </p>
      )}
    </Dialog>
  );
}
