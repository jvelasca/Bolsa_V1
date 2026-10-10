/**
 * AUTO · TOP 3 OPORTUNIDADES — panel de presentación.
 *
 * Fija dos invariantes de primer nivel:
 * - `ranking ≠ decisión` (`UI5-12`) se declara UNA sola vez por superficie: la vista completa
 *   (Operar) lo lleva en su panel; el resumen compacto (HOME) lo deja a «Decisión de cartera».
 * - Un activo repetido en el espejo durable nunca se pinta dos veces (`UI5-04`, sin duplicidades).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AutoTop3Panel } from "@/features/auto/auto-top3-panel";
import {
  AUTO_TOP3_RANK_NOTE,
  buildAutoTop3View,
  type AutoTop3DtoV1,
} from "@/features/auto/auto-top3-opportunities";

const DTO: AutoTop3DtoV1 = {
  runId: "top3-run-1",
  items: [
    {
      rank: 1,
      assetId: "MSFT",
      score: 0.87,
      reasons: [],
      createdAt: "2026-10-07T09:00:00Z",
    },
    {
      rank: 2,
      assetId: "ITX",
      score: 0.74,
      reasons: [],
      createdAt: "2026-10-07T09:00:00Z",
    },
  ],
};

afterEach(cleanup);

describe("AutoTop3Panel", () => {
  it("la vista completa (Operar) declara `ranking ≠ decisión` en el propio panel", () => {
    render(<AutoTop3Panel view={buildAutoTop3View(DTO)} />);
    expect(screen.getByTestId("auto-top3").textContent).toContain(
      AUTO_TOP3_RANK_NOTE,
    );
  });

  it("el resumen compacto (HOME) no repite la nota: la declara la sección Decisión", () => {
    render(<AutoTop3Panel view={buildAutoTop3View(DTO)} compact />);
    expect(screen.getByTestId("auto-top3").textContent).not.toContain(
      AUTO_TOP3_RANK_NOTE,
    );
  });

  it("un activo repetido en el espejo durable se pinta una sola vez", () => {
    const view = buildAutoTop3View({
      ...DTO,
      items: [
        { ...DTO.items![0]!, rank: 1, assetId: "MSFT" },
        { ...DTO.items![0]!, rank: 2, assetId: "MSFT" },
      ],
    });
    render(<AutoTop3Panel view={view} />);
    expect(screen.getAllByTestId("auto-top3-slot")).toHaveLength(1);
  });
});
