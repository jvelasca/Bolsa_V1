import { describe, expect, it } from "vitest";
import {
  DEFAULT_JOURNAL_STUDY_LAYOUT,
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
});
