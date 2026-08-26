import { useMemo } from "react";
import {
  buildJournalStudySparklinePath,
  buildJournalStudySparklinePoints,
  type DecisionJournalStudyViewV1,
} from "@bolsa/shared";

export function JournalStudySparkline({
  studies,
  className,
}: {
  studies: DecisionJournalStudyViewV1[];
  className?: string;
}) {
  const width = 240;
  const height = 48;
  const points = useMemo(
    () => buildJournalStudySparklinePoints(studies),
    [studies],
  );
  const { line, dots } = useMemo(
    () => buildJournalStudySparklinePath(points, width, height),
    [points],
  );

  if (points.length === 0) {
    return (
      <p
        className="text-xs text-muted-foreground"
        data-testid="sparkline-empty"
      >
        Sin historial para sparkline.
      </p>
    );
  }

  return (
    <div className={className} data-testid="journal-study-sparkline">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="text-primary"
        aria-hidden
      >
        {line ? (
          <path
            d={line}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            opacity={0.85}
          />
        ) : null}
        {dots.map((dot, index) => (
          <circle
            key={points[index]?.studiedAt ?? index}
            cx={dot.x}
            cy={dot.y}
            r={3}
            className="fill-primary"
          />
        ))}
      </svg>
      <p className="mt-1 text-[10px] text-muted-foreground">
        Fuerza 0–10 · {points.length} estudio{points.length === 1 ? "" : "s"}
      </p>
    </div>
  );
}
