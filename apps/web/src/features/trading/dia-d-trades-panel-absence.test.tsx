/**
 * P1-01 — DÍA-D · Operaciones (replay): un run no leído no es «sin operaciones».
 *
 * Falsable: con `detail: null` y estado `error`, la tabla antes decía «Sin
 * operaciones en este tramo» y el contador pintaba `0`.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DiaDTradesPanel } from "@/features/trading/dia-d-trades-panel";

afterEach(cleanup);

const noop = () => {};

describe("DÍA-D · Operaciones", () => {
  it("con el run ilegible declara «No disponible» y no «Sin operaciones»", () => {
    render(
      <DiaDTradesPanel
        detail={null}
        state="error"
        replayCursor={null}
        focusTimestamp={null}
        onFocusTimestamp={noop}
      />,
    );

    expect(screen.getByTestId("dia-d-trades-absence")).toHaveTextContent(
      "No disponible",
    );
    expect(screen.queryByText(/Sin operaciones en este tramo/)).toBeNull();
    expect(screen.queryByText("0")).toBeNull();
  });

  it("mientras carga no adelanta un vacío", () => {
    render(
      <DiaDTradesPanel
        detail={null}
        state="loading"
        replayCursor={null}
        focusTimestamp={null}
        onFocusTimestamp={noop}
      />,
    );

    expect(screen.getByTestId("dia-d-trades-absence")).toHaveTextContent(
      "Cargando operaciones…",
    );
    expect(screen.queryByText(/Sin operaciones en este tramo/)).toBeNull();
  });

  it("con el run leído y sin trades sí dice «Sin operaciones en este tramo»", () => {
    render(
      <DiaDTradesPanel
        detail={{ tradeCount: 0, trades: [] } as never}
        state="ready"
        replayCursor={null}
        focusTimestamp={null}
        onFocusTimestamp={noop}
      />,
    );

    expect(screen.getByText(/Sin operaciones en este tramo/)).toBeTruthy();
    expect(screen.queryByTestId("dia-d-trades-absence")).toBeNull();
  });
});
