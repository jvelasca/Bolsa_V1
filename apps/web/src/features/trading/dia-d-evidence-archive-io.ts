/**
 * Helpers archivo Evidence DÍA D — etiquetas + export/import JSON (v0.10).
 *
 * No toca DEMO ni Belief. Round-trip de `bolsa-dia-d-evidence-archive-v1`.
 *
 * @see stores/dia-d-evidence-archive-store.ts
 * @see docs/engineering/backtesting-dia-d-premises-2026-07-31.md
 */

import {
  DIA_D_EVIDENCE_BAND_LABELS,
  type DiaDEvidenceBand,
  type DiaDSessionEvidenceV1,
} from '@/features/trading/dia-d-session-evidence';
import type { DiaDEvidenceArchiveItem } from '@/stores/dia-d-evidence-archive-store';

export type DiaDEvidenceExportV1 = {
  schemaVersion: 'dia_d_evidence_export_v1';
  exportedAt: string;
  item: DiaDEvidenceArchiveItem;
};

export type DiaDEvidenceImportResult =
  | { ok: true; item: DiaDEvidenceArchiveItem }
  | { ok: false; error: string };

const BANDS = new Set(['favorable', 'mixed', 'adverse', 'incomplete']);

/** Fila compacta para la lista del informe lateral. */
export function formatDiaDArchiveRowLabel(item: DiaDEvidenceArchiveItem): string {
  const band =
    DIA_D_EVIDENCE_BAND_LABELS[item.evidence.band as DiaDEvidenceBand] ??
    item.evidence.band;
  const ret = item.evidence.metrics?.returnPct;
  const retStr =
    typeof ret === 'number' && Number.isFinite(ret)
      ? `${ret >= 0 ? '+' : ''}${ret.toFixed(1)}%`
      : '—';
  return `${item.diaD} · ${item.mode} · ${band} · ${retStr}`;
}

export function buildDiaDEvidenceExport(
  item: DiaDEvidenceArchiveItem,
  exportedAt = new Date().toISOString(),
): DiaDEvidenceExportV1 {
  return {
    schemaVersion: 'dia_d_evidence_export_v1',
    exportedAt,
    item,
  };
}

export function diaDEvidenceExportFilename(item: DiaDEvidenceArchiveItem): string {
  const safe = (s: string) => s.replace(/[^\w.-]+/g, '_').slice(0, 40);
  return `dia-d-evidence-${safe(item.symbol)}-${safe(item.diaD)}-${safe(item.mode)}.json`;
}

/** Descarga JSON en el navegador (no-op fuera de DOM). */
export function downloadDiaDEvidenceJson(item: DiaDEvidenceArchiveItem): void {
  if (typeof document === 'undefined') return;
  const payload = buildDiaDEvidenceExport(item);
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = diaDEvidenceExportFilename(item);
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === 'object' && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : null;
}

function parseEvidence(raw: unknown): DiaDSessionEvidenceV1 | null {
  const e = asRecord(raw);
  if (!e) return null;
  const band = String(e.band ?? '');
  if (!BANDS.has(band)) return null;
  const paragraphs = Array.isArray(e.paragraphs)
    ? e.paragraphs.map((p) => String(p))
    : [];
  if (paragraphs.length < 3) return null;
  const metrics = asRecord(e.metrics) ?? {};
  return {
    schemaVersion: 'dia_d_session_evidence_v1',
    band: band as DiaDEvidenceBand,
    confidence:
      e.confidence === 'HIGH' || e.confidence === 'LOW' ? e.confidence : 'MEDIUM',
    claims: Array.isArray(e.claims) ? e.claims.map((c) => String(c)) : [],
    warnings: Array.isArray(e.warnings) ? e.warnings.map((w) => String(w)) : [],
    metrics: {
      mode: String(metrics.mode ?? 'auto'),
      returnPct: Number(metrics.returnPct) || 0,
      maxDrawdownPct: Number(metrics.maxDrawdownPct) || 0,
      tradeCount: Number(metrics.tradeCount) || 0,
      finalEquity: Number(metrics.finalEquity) || 0,
      autoReturnPct: Number(metrics.autoReturnPct) || 0,
      returnDeltaVsAutoPct: Number(metrics.returnDeltaVsAutoPct) || 0,
      accepted: Number(metrics.accepted) || 0,
      rejected: Number(metrics.rejected) || 0,
    },
    paragraphs: [paragraphs[0]!, paragraphs[1]!, paragraphs[2]!],
    disclaimer: String(e.disclaimer ?? 'Sandbox DÍA D ≠ DEMO live.'),
  };
}

/**
 * Acepta envelope `dia_d_evidence_export_v1` o el item plano del archivo.
 * No escribe en el store — el caller llama a `save`.
 */
export function parseDiaDEvidenceImport(raw: unknown): DiaDEvidenceImportResult {
  const root = asRecord(raw);
  if (!root) return { ok: false, error: 'JSON inválido' };

  const itemRaw =
    root.schemaVersion === 'dia_d_evidence_export_v1'
      ? asRecord(root.item)
      : root.evidence
        ? root
        : null;
  if (!itemRaw) {
    return { ok: false, error: 'Falta item / schema dia_d_evidence_export_v1' };
  }

  const instrumentId = String(itemRaw.instrumentId ?? '').trim();
  const symbol = String(itemRaw.symbol ?? '').trim();
  const diaD = String(itemRaw.diaD ?? '').trim();
  const endDate = String(itemRaw.endDate ?? '').trim();
  const mode = String(itemRaw.mode ?? '').trim();
  if (!instrumentId || !symbol || !diaD || !endDate || !mode) {
    return { ok: false, error: 'Faltan instrumentId/symbol/diaD/endDate/mode' };
  }

  const evidence = parseEvidence(itemRaw.evidence);
  if (!evidence) {
    return { ok: false, error: 'Evidence incompleta (band/párrafos)' };
  }

  let narrativeParagraphs: [string, string, string] | null = null;
  if (Array.isArray(itemRaw.narrativeParagraphs) && itemRaw.narrativeParagraphs.length >= 3) {
    narrativeParagraphs = [
      String(itemRaw.narrativeParagraphs[0]),
      String(itemRaw.narrativeParagraphs[1]),
      String(itemRaw.narrativeParagraphs[2]),
    ];
  }

  const item: DiaDEvidenceArchiveItem = {
    id: String(itemRaw.id ?? '').trim() || `dde-import-${Date.now().toString(36)}`,
    instrumentId,
    symbol,
    strategyLabel: String(itemRaw.strategyLabel ?? symbol),
    mode,
    diaD,
    endDate,
    savedAt: String(itemRaw.savedAt ?? new Date().toISOString()),
    researchEvidenceId:
      itemRaw.researchEvidenceId != null && String(itemRaw.researchEvidenceId).trim()
        ? String(itemRaw.researchEvidenceId)
        : null,
    engine: String(itemRaw.engine ?? 'heuristic'),
    evidence,
    narrativeParagraphs,
  };
  return { ok: true, item };
}

export function parseDiaDEvidenceImportText(text: string): DiaDEvidenceImportResult {
  try {
    return parseDiaDEvidenceImport(JSON.parse(text) as unknown);
  } catch {
    return { ok: false, error: 'No es JSON válido' };
  }
}
