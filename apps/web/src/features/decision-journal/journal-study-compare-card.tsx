import {
  JOURNAL_STUDY_DELTA_BUCKET_LABELS,
  buildRelevantJournalDelta,
  type DecisionJournalStudyViewV1,
  type JournalStudyDeltaBucket,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";

function bucketClass(bucket: JournalStudyDeltaBucket): string {
  switch (bucket) {
    case "motor":
      return "border-sky-500/30 bg-sky-500/5";
    case "plan":
      return "border-emerald-500/30 bg-emerald-500/5";
    case "health":
      return "border-amber-500/30 bg-amber-500/5";
    default:
      return "border-border/60 bg-muted/20";
  }
}

export function JournalStudyCompareCard({
  prev,
  next,
}: {
  prev: DecisionJournalStudyViewV1 | null;
  next: DecisionJournalStudyViewV1;
}) {
  const delta = buildRelevantJournalDelta(next, prev);

  return (
    <div
      className="rounded-lg border border-border/70 bg-card p-3"
      data-testid="journal-study-compare"
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        ¿Por qué cambió?
      </p>
      <p className="mt-1 text-xs font-medium text-foreground/90">
        {delta.conclusion}
      </p>
      {!delta.hasRelevantChange ? null : (
        <ul className="mt-2 space-y-1.5">
          {delta.relevantFields.map((field) => (
            <li
              key={`${field.bucket}-${field.label}`}
              className={cn(
                "rounded-md border px-2 py-1.5 text-xs",
                bucketClass(field.bucket),
              )}
            >
              <p className="font-medium">
                {field.label}
                <span className="ml-1 text-[10px] font-normal text-muted-foreground">
                  ({JOURNAL_STUDY_DELTA_BUCKET_LABELS[field.bucket]})
                </span>
              </p>
              <p className="text-muted-foreground">
                {field.before} → {field.after}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
