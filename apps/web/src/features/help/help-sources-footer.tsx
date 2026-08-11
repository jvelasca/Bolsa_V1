import {
  HELP_CONTENT_AS_OF,
  helpSectionMeta,
  type HelpRegistrySectionId,
} from "@/features/help/help-registry";

const ROLE_LABEL = {
  tracker: "Tracker",
  doc: "Doc",
  adr: "ADR",
  rfc: "RFC",
  code: "Código",
} as const;

/** Pie de fuentes — mantiene visible la coordinación Ayuda ↔ ficheros. */
export function HelpSourcesFooter({
  sectionId,
}: {
  sectionId: HelpRegistrySectionId;
}) {
  const meta = helpSectionMeta(sectionId);
  return (
    <div className="mt-6 rounded-md border border-dashed border-border bg-muted/20 px-3 py-2 text-[11px] text-muted-foreground">
      <p className="font-medium text-foreground/80">
        Fuentes · sync {HELP_CONTENT_AS_OF}
        {meta.kind === "tracking" ? " · sección alimentada por tracker" : ""}
      </p>
      <ul className="mt-1.5 space-y-0.5">
        {meta.sources.map((src) => (
          <li key={src.path} className="font-mono break-all">
            <span className="text-muted-foreground/70">
              [{ROLE_LABEL[src.role]}]
            </span>{" "}
            {src.path}
            {src.note ? (
              <span className="font-sans text-muted-foreground">
                {" "}
                — {src.note}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
