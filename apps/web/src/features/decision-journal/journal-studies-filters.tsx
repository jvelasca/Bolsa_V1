import type {
  JournalStudyOpinion,
  JournalStudyPeriod,
  JournalStudyStrengthBand,
  JournalStudyUserStatus,
} from "@bolsa/shared";
import {
  ESTUDIO_LIST_ID,
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_PERIOD_LABELS,
  JOURNAL_STUDY_STATUS_LABELS,
  JOURNAL_STUDY_STRENGTH_BAND_LABELS,
  VIRTUAL_LIST_PORTFOLIO,
} from "@bolsa/shared";

export type JournalStudyFilters = {
  listId: string;
  q: string;
  period: "all" | JournalStudyPeriod;
  opinion: "all" | JournalStudyOpinion;
  status: "all" | JournalStudyUserStatus;
  strengthBand: "all" | JournalStudyStrengthBand;
  dateFrom: string;
  dateTo: string;
};

export const DEFAULT_JOURNAL_STUDY_FILTERS: JournalStudyFilters = {
  listId: ESTUDIO_LIST_ID,
  q: "",
  period: "all",
  opinion: "all",
  status: "all",
  strengthBand: "all",
  dateFrom: "",
  dateTo: "",
};

const SELECT_CLASS =
  "h-8 rounded-md border border-border bg-card px-2 text-xs text-foreground";

export function JournalStudiesFilters({
  value,
  onChange,
  lists,
}: {
  value: JournalStudyFilters;
  onChange: (next: JournalStudyFilters) => void;
  lists: Array<{ id: string; name: string }>;
}) {
  const set = <K extends keyof JournalStudyFilters>(
    key: K,
    next: JournalStudyFilters[K],
  ) => onChange({ ...value, [key]: next });

  return (
    <div
      className="flex flex-wrap items-end gap-2 rounded-xl border border-border bg-card/60 px-3 py-2"
      data-testid="journal-study-filters"
    >
      <label className="flex flex-col gap-0.5 text-[10px] text-muted-foreground">
        Lista
        <select
          className={SELECT_CLASS}
          value={value.listId}
          onChange={(e) => set("listId", e.target.value)}
          data-testid="filter-list"
        >
          <option value="todas">Todas</option>
          <option value={ESTUDIO_LIST_ID}>Estudio</option>
          <option value={VIRTUAL_LIST_PORTFOLIO}>En cartera</option>
          {lists
            .filter((item) => item.id !== ESTUDIO_LIST_ID)
            .map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
        </select>
      </label>
      <label className="flex min-w-[10rem] flex-1 flex-col gap-0.5 text-[10px] text-muted-foreground">
        Buscar
        <input
          type="search"
          className={SELECT_CLASS}
          placeholder="Ticker o nombre…"
          value={value.q}
          onChange={(e) => set("q", e.target.value)}
          data-testid="filter-search"
        />
      </label>
      <label className="flex flex-col gap-0.5 text-[10px] text-muted-foreground">
        Periodo
        <select
          className={SELECT_CLASS}
          value={value.period}
          onChange={(e) =>
            set("period", e.target.value as JournalStudyFilters["period"])
          }
        >
          <option value="all">Todos</option>
          {(
            Object.keys(JOURNAL_STUDY_PERIOD_LABELS) as JournalStudyPeriod[]
          ).map((id) => (
            <option key={id} value={id}>
              {JOURNAL_STUDY_PERIOD_LABELS[id]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-0.5 text-[10px] text-muted-foreground">
        Opinión
        <select
          className={SELECT_CLASS}
          value={value.opinion}
          onChange={(e) =>
            set("opinion", e.target.value as JournalStudyFilters["opinion"])
          }
        >
          <option value="all">Todas</option>
          {(
            Object.keys(JOURNAL_STUDY_OPINION_LABELS) as JournalStudyOpinion[]
          ).map((id) => (
            <option key={id} value={id}>
              {JOURNAL_STUDY_OPINION_LABELS[id]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-0.5 text-[10px] text-muted-foreground">
        Estado
        <select
          className={SELECT_CLASS}
          value={value.status}
          onChange={(e) =>
            set("status", e.target.value as JournalStudyFilters["status"])
          }
          data-testid="filter-status"
        >
          <option value="all">Todos</option>
          {(
            Object.keys(JOURNAL_STUDY_STATUS_LABELS) as JournalStudyUserStatus[]
          ).map((id) => (
            <option key={id} value={id}>
              {JOURNAL_STUDY_STATUS_LABELS[id]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-0.5 text-[10px] text-muted-foreground">
        Fuerza
        <select
          className={SELECT_CLASS}
          value={value.strengthBand}
          onChange={(e) =>
            set(
              "strengthBand",
              e.target.value as JournalStudyFilters["strengthBand"],
            )
          }
        >
          <option value="all">Todas</option>
          {(
            Object.keys(
              JOURNAL_STUDY_STRENGTH_BAND_LABELS,
            ) as JournalStudyStrengthBand[]
          ).map((id) => (
            <option key={id} value={id}>
              {JOURNAL_STUDY_STRENGTH_BAND_LABELS[id]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-0.5 text-[10px] text-muted-foreground">
        Desde
        <input
          type="date"
          className={SELECT_CLASS}
          value={value.dateFrom}
          onChange={(e) => set("dateFrom", e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-0.5 text-[10px] text-muted-foreground">
        Hasta
        <input
          type="date"
          className={SELECT_CLASS}
          value={value.dateTo}
          onChange={(e) => set("dateTo", e.target.value)}
        />
      </label>
    </div>
  );
}
