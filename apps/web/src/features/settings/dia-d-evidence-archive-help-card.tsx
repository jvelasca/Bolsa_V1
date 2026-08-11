/**
 * Ayuda → Backtesting — últimos Evidence DÍA D del archivo local (v0.11).
 * Solo lectura + export JSON. No Belief · no DEMO.
 */

import { useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  downloadDiaDEvidenceJson,
  formatDiaDArchiveRowLabel,
} from "@/features/trading/dia-d-evidence-archive-io";
import { DIA_D_EVIDENCE_BAND_LABELS } from "@/features/trading/dia-d-session-evidence";
import {
  useDiaDEvidenceArchiveStore,
  type DiaDEvidenceArchiveItem,
} from "@/stores/dia-d-evidence-archive-store";
import { cn } from "@/lib/utils";

const HELP_ARCHIVE_MAX = 8;

export function DiaDEvidenceArchiveHelpCard() {
  const items = useDiaDEvidenceArchiveStore((s) => s.items);
  const remove = useDiaDEvidenceArchiveStore((s) => s.remove);
  const recent = useMemo(() => items.slice(0, HELP_ARCHIVE_MAX), [items]);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const preview = useMemo(
    () => recent.find((i) => i.id === previewId) ?? null,
    [recent, previewId],
  );

  return (
    <Card className="border-border/70">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Archivo Evidence DÍA D</CardTitle>
        <CardDescription>
          localStorage · últimos {HELP_ARCHIVE_MAX} · export JSON · sandbox ≠
          DEMO
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {recent.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Vacío. En LAB Verificar D→hoy → Guardar Evidence o Importar JSON.
          </p>
        ) : (
          <>
            <ul className="max-h-40 space-y-1 overflow-auto text-xs">
              {recent.map((item) => (
                <ArchiveRow
                  key={item.id}
                  item={item}
                  active={item.id === previewId}
                  onPreview={() =>
                    setPreviewId((cur) => (cur === item.id ? null : item.id))
                  }
                  onExport={() => downloadDiaDEvidenceJson(item)}
                  onRemove={() => {
                    if (previewId === item.id) setPreviewId(null);
                    remove(item.id);
                  }}
                />
              ))}
            </ul>
            {preview ? (
              <div className="space-y-0.5 rounded border border-border/50 bg-muted/20 px-2 py-1.5 text-[11px] leading-snug text-muted-foreground">
                <p className="font-medium text-foreground">
                  {preview.symbol} ·{" "}
                  {DIA_D_EVIDENCE_BAND_LABELS[preview.evidence.band]}
                  {preview.researchEvidenceId
                    ? ` · Fase 2 ${preview.researchEvidenceId.slice(0, 8)}…`
                    : " · solo local"}
                </p>
                {(
                  preview.narrativeParagraphs ?? preview.evidence.paragraphs
                ).map((p, idx) => (
                  <p key={`${preview.id}-hp${idx}`}>{p}</p>
                ))}
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ArchiveRow({
  item,
  active,
  onPreview,
  onExport,
  onRemove,
}: {
  item: DiaDEvidenceArchiveItem;
  active: boolean;
  onPreview: () => void;
  onExport: () => void;
  onRemove: () => void;
}) {
  return (
    <li className="flex items-center gap-1">
      <button
        type="button"
        className={cn(
          "min-w-0 flex-1 truncate rounded px-1 py-0.5 text-left hover:bg-accent",
          active && "bg-accent font-medium text-foreground",
        )}
        title="Preview"
        onClick={onPreview}
      >
        <span className="font-medium text-foreground">{item.symbol}</span>
        <span className="text-muted-foreground">
          {" "}
          · {formatDiaDArchiveRowLabel(item)}
        </span>
      </button>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="h-6 shrink-0 px-1.5 text-[10px]"
        onClick={onExport}
      >
        JSON
      </Button>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="h-6 shrink-0 px-1.5 text-[10px] text-muted-foreground"
        title="Quitar"
        onClick={onRemove}
      >
        ×
      </Button>
    </li>
  );
}
