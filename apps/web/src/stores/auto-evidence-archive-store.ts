/**
 * AUTO-20D — archivo local del artefacto AUTO EVIDENCE REPORT importado (manual).
 *
 * Persiste el último/los últimos artefactos `auto20c_evidence_artifact_v1` que el propietario
 * importa (fichero o pegado) para poder verlos en la cabina sin backend ni migración. NO mide
 * nada: guarda el artefacto tal cual y su etiqueta de procedencia.
 *
 * @see features/operational-console/auto-evidence-report.ts
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AutoEvidenceArtifact } from "@/features/operational-console/auto-evidence-report";

export const AUTO_EVIDENCE_ARCHIVE_KEY = "bolsa-auto-evidence-archive-v1";
export const AUTO_EVIDENCE_ARCHIVE_MAX = 10;

export type AutoEvidenceArchiveItem = {
  id: string;
  savedAt: string;
  /** Etiqueta legible: origen del fichero o nombre del fichero importado. */
  label: string;
  schema: string;
  materialOrigin: string | null;
  fingerprint: string | null;
  artifact: AutoEvidenceArtifact;
};

type AutoEvidenceArchiveState = {
  items: AutoEvidenceArchiveItem[];
  saveArtifact: (
    artifact: AutoEvidenceArtifact,
    options?: { id?: string; savedAt?: string; label?: string },
  ) => AutoEvidenceArchiveItem;
  remove: (id: string) => void;
  latest: () => AutoEvidenceArchiveItem | null;
  clear: () => void;
};

function dedupeKey(artifact: AutoEvidenceArtifact): string {
  const origin =
    artifact.materialOrigin ?? artifact.material?.materialOrigin ?? "";
  const fingerprint = artifact.material?.fingerprint ?? "";
  return `${artifact.schema}|${origin}|${fingerprint}`;
}

export const useAutoEvidenceArchiveStore = create<AutoEvidenceArchiveState>()(
  persist(
    (set, get) => ({
      items: [],
      saveArtifact: (artifact, options) => {
        const savedAt = options?.savedAt ?? new Date().toISOString();
        const id =
          options?.id ??
          `aee-${Date.now().toString(36)}-${Math.random()
            .toString(36)
            .slice(2, 8)}`;
        const item: AutoEvidenceArchiveItem = {
          id,
          savedAt,
          label: options?.label ?? "artefacto AUTO-20C",
          schema: artifact.schema,
          materialOrigin:
            artifact.materialOrigin ??
            artifact.material?.materialOrigin ??
            null,
          fingerprint: artifact.material?.fingerprint ?? null,
          artifact,
        };
        const key = dedupeKey(artifact);
        set((state) => {
          const filtered = state.items.filter(
            (existing) => dedupeKey(existing.artifact) !== key,
          );
          return {
            items: [item, ...filtered].slice(0, AUTO_EVIDENCE_ARCHIVE_MAX),
          };
        });
        return item;
      },
      remove: (id) =>
        set((state) => ({
          items: state.items.filter((item) => item.id !== id),
        })),
      latest: () => get().items[0] ?? null,
      clear: () => set({ items: [] }),
    }),
    { name: AUTO_EVIDENCE_ARCHIVE_KEY },
  ),
);
