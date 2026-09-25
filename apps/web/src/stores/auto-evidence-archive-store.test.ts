/**
 * Tests — archivo local del artefacto AUTO EVIDENCE REPORT.
 */

import { beforeEach, describe, expect, it } from "vitest";
import type { AutoEvidenceArtifact } from "@/features/operational-console/auto-evidence-report";
import {
  AUTO_EVIDENCE_ARCHIVE_KEY,
  AUTO_EVIDENCE_ARCHIVE_MAX,
  useAutoEvidenceArchiveStore,
} from "@/stores/auto-evidence-archive-store";

function artifact(fingerprint: string): AutoEvidenceArtifact {
  return {
    schema: "auto20c_evidence_artifact_v1",
    executionReality: "virtual_paper_only",
    realMoneyAtRisk: false,
    brokerVenue: "paper",
    materialOrigin: "paper_real",
    note: "PAPER VIRTUAL",
    material: { fingerprint, closedCycles: 184 },
    report: {},
  };
}

describe("auto-evidence-archive-store", () => {
  beforeEach(() => {
    localStorage.removeItem(AUTO_EVIDENCE_ARCHIVE_KEY);
    useAutoEvidenceArchiveStore.setState({ items: [] });
  });

  it("saves and exposes the latest artifact", () => {
    const store = useAutoEvidenceArchiveStore.getState();
    store.saveArtifact(artifact("sha256:a"), { label: "corrida A" });
    const latest = useAutoEvidenceArchiveStore.getState().latest();
    expect(latest?.label).toBe("corrida A");
    expect(latest?.fingerprint).toBe("sha256:a");
    expect(latest?.materialOrigin).toBe("paper_real");
  });

  it("dedupes by schema+origin+fingerprint and keeps the newest", () => {
    const store = useAutoEvidenceArchiveStore.getState();
    store.saveArtifact(artifact("sha256:a"), { label: "vieja" });
    useAutoEvidenceArchiveStore
      .getState()
      .saveArtifact(artifact("sha256:a"), { label: "nueva" });
    expect(useAutoEvidenceArchiveStore.getState().items).toHaveLength(1);
    expect(useAutoEvidenceArchiveStore.getState().latest()?.label).toBe(
      "nueva",
    );
  });

  it("caps the archive", () => {
    for (let i = 0; i < AUTO_EVIDENCE_ARCHIVE_MAX + 5; i += 1) {
      useAutoEvidenceArchiveStore
        .getState()
        .saveArtifact(artifact(`sha256:${i}`));
    }
    expect(useAutoEvidenceArchiveStore.getState().items).toHaveLength(
      AUTO_EVIDENCE_ARCHIVE_MAX,
    );
  });

  it("removes by id and clears", () => {
    const item = useAutoEvidenceArchiveStore
      .getState()
      .saveArtifact(artifact("sha256:a"));
    useAutoEvidenceArchiveStore.getState().remove(item.id);
    expect(useAutoEvidenceArchiveStore.getState().items).toHaveLength(0);
    useAutoEvidenceArchiveStore.getState().saveArtifact(artifact("sha256:b"));
    useAutoEvidenceArchiveStore.getState().clear();
    expect(useAutoEvidenceArchiveStore.getState().items).toHaveLength(0);
  });
});
