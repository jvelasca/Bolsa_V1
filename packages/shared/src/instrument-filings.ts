/**
 * FIE F2b / F2b+ / F2b++ — filings (manual, SEC EDGAR) + RAG TF-IDF local.
 *
 * Bytes en disco (`data/filings/…`); chunks `{id}.chunks.json`.
 * No viven en `profileSnapshot.fundamentals` ni alimentan Score_FUND / gate.
 *
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 */

export const FILING_STORE_VERSION = 'instrument_filings_v1' as const;
export const FILING_RAG_VERSION = 'filing_rag_tfidf_v1' as const;

export type InstrumentFilingKindV1 = '10-K' | '10-Q' | 'annual-report' | 'other';

export type InstrumentFilingSourceV1 = 'upload' | 'sec_edgar';

export type InstrumentFilingExtractStatusV1 =
  | 'ok'
  | 'empty'
  | 'skipped'
  | 'unavailable'
  | 'error';

export interface InstrumentFilingMetaV1 {
  id: string;
  instrumentId: string;
  kind: InstrumentFilingKindV1;
  originalName: string;
  contentType: string;
  byteSize: number;
  sha256: string;
  uploadedAt: string;
  extractStatus: InstrumentFilingExtractStatusV1;
  charCount: number;
  /** Chunks TF-IDF indexados (F2b++). */
  chunkCount?: number;
  /** Origen del archivo (manual vs EDGAR). */
  source?: InstrumentFilingSourceV1 | string;
  cik?: string | null;
  accessionNumber?: string | null;
  filingDate?: string | null;
  documentUrl?: string | null;
  /** Resumen narrativo opcional (no ratios; no Score_FUND). */
  lastSummary?: {
    engine: string;
    paragraphs: string[];
    disclaimer: string;
    summarizedAt: string;
    provider?: string | null;
    model?: string | null;
  } | null;
}

export interface InstrumentFilingListResponseV1 {
  data: InstrumentFilingMetaV1[];
  storeVersion: typeof FILING_STORE_VERSION | string;
}

export interface InstrumentFilingUploadResponseV1 {
  data: InstrumentFilingMetaV1;
  /** True si el accession EDGAR ya estaba en el almacén. */
  deduped?: boolean;
}

export interface InstrumentFilingSecFetchRequestV1 {
  kind?: Extract<InstrumentFilingKindV1, '10-K' | '10-Q'>;
}

export interface InstrumentFilingSummarizeRequestV1 {
  instrumentId: string;
  filingId: string;
}

export interface InstrumentFilingSummaryPayloadV1 {
  paragraphs: string[];
  disclaimer: string;
}

export interface InstrumentFilingSummarizeResponseV1 {
  engine: string;
  payload: InstrumentFilingSummaryPayloadV1 | null;
  provider: string | null;
  model: string | null;
  filing: InstrumentFilingMetaV1;
}

export interface InstrumentFilingAskRequestV1 {
  instrumentId: string;
  filingId: string;
  question: string;
  topK?: number;
}

export interface InstrumentFilingAskHitV1 {
  id?: string | null;
  label?: string | null;
  start?: number | null;
  end?: number | null;
  score: number;
  text: string;
}

export interface InstrumentFilingAskPayloadV1 {
  answer: string;
  disclaimer: string;
}

export interface InstrumentFilingAskResponseV1 {
  engine: string;
  indexVersion: typeof FILING_RAG_VERSION | string;
  payload: InstrumentFilingAskPayloadV1 | null;
  provider: string | null;
  model: string | null;
  hits: InstrumentFilingAskHitV1[];
  filing: InstrumentFilingMetaV1;
  question: string;
}
