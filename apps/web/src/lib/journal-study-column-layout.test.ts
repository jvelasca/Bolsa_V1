import { describe, expect, it } from "vitest";
import {
  DEFAULT_JOURNAL_STUDY_LAYOUT,
  buildJournalStudyGridTemplate,
  fitJournalStudyColumnsToContent,
  journalStudyGridMinWidth,
  reorderJournalStudyColumns,
  toggleJournalStudyColumn,
} from "@/lib/journal-study-column-layout";

describe("journal-study-column-layout", () => {
  it("does not allow hiding the symbol column", () => {
    const next = toggleJournalStudyColumn(
      DEFAULT_JOURNAL_STUDY_LAYOUT,
      "symbol",
    );
    expect(next.find((c) => c.id === "symbol")?.visible).toBe(true);
  });

  it("toggles optional columns", () => {
    const next = toggleJournalStudyColumn(
      DEFAULT_JOURNAL_STUDY_LAYOUT,
      "entry",
    );
    expect(next.find((c) => c.id === "entry")?.visible).toBe(true);
  });

  it("reorders columns without dropping ids", () => {
    const next = reorderJournalStudyColumns(
      DEFAULT_JOURNAL_STUDY_LAYOUT,
      "opinion",
      "status",
    );
    expect(next.map((c) => c.id)).toHaveLength(
      DEFAULT_JOURNAL_STUDY_LAYOUT.length,
    );
  });

  it("builds fixed px grid template aligned with column widths", () => {
    const visible = DEFAULT_JOURNAL_STUDY_LAYOUT.filter((c) => c.visible);
    expect(buildJournalStudyGridTemplate(visible)).toBe(
      visible.map((c) => `${c.width}px`).join(" "),
    );
    expect(journalStudyGridMinWidth(visible)).toBe(
      visible.reduce((sum, column) => sum + column.width, 0),
    );
  });

  it("fits columns to content samples", () => {
    const next = fitJournalStudyColumnsToContent(DEFAULT_JOURNAL_STUDY_LAYOUT, {
      symbol: ["AAPL", "MSFT"],
      status: ["Objetivo activo"],
    });
    expect(next.find((c) => c.id === "symbol")!.width).toBeGreaterThanOrEqual(
      56,
    );
    expect(next.find((c) => c.id === "actions")!.width).toBeLessThanOrEqual(
      100,
    );
  });
});
