import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  SURFACE_LEVEL_ATTR,
  SurfaceLevelDeclaration,
} from "@/components/surface-level";

describe("SurfaceLevelDeclaration", () => {
  it("declara el nivel y el copy de una superficie de diagnóstico", () => {
    const title = "Superficie de diagnostico · nivel 3";
    const detail = "Detalle admitido.";
    render(
      <SurfaceLevelDeclaration
        level={3}
        testId="probe-level"
        title={title}
        detail={detail}
      />,
    );
    const node = screen.getByTestId("probe-level");
    expect(node.getAttribute(SURFACE_LEVEL_ATTR)).toBe("3");
    expect(node.textContent).toContain("Superficie de diagnostico");
    expect(node.textContent).toContain(detail);
  });

  it("sin level por defecto declara nivel 3 y sin detail no pinta detalle", () => {
    const title = "Superficie de diagnostico · nivel 3";
    render(<SurfaceLevelDeclaration testId="probe-default" title={title} />);
    const node = screen.getByTestId("probe-default");
    expect(node.getAttribute(SURFACE_LEVEL_ATTR)).toBe("3");
    expect(node.textContent).toBe(title);
  });
});
