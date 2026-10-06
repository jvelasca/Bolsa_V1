import { describe, expect, it } from "vitest";
import { NO_MEASUREMENT_LABEL } from "@bolsa/shared";
import {
  AUTO_REALITY_BROKER_NO_ORDERS,
  AUTO_REALITY_BROKER_UNKNOWN,
  AUTO_REALITY_MONEY_UNKNOWN,
  AUTO_REALITY_MONEY_VIRTUAL,
  AUTO_REALITY_MODE_DEMO,
  accountTypeRealityLabel,
  buildAutoReality,
} from "./auto-reality";

describe("buildAutoReality", () => {
  it("declara DINERO VIRTUAL para una cuenta demo", () => {
    const r = buildAutoReality({
      accountType: "simulated",
      bookMode: "semi",
      autoArmed: false,
      paperDExecuteEnv: false,
    });
    expect(r.tone).toBe("virtual");
    expect(r.isVirtual).toBe(true);
    expect(r.moneyLabel).toBe(AUTO_REALITY_MONEY_VIRTUAL);
    expect(r.modeLabel).toBe(AUTO_REALITY_MODE_DEMO);
    expect(r.brokerLabel).toBe(AUTO_REALITY_BROKER_NO_ORDERS);
    expect(r.accountTypeLabel).toBe("Cuenta demo");
    expect(r.autoActive).toBe(false);
    expect(r.autoLabel).toBe("Inactivo");
  });

  it("declara AUTO activo sólo cuando el libro AUTO está armado", () => {
    const off = buildAutoReality({
      accountType: "simulated",
      bookMode: "auto",
      autoArmed: false,
      paperDExecuteEnv: true,
    });
    expect(off.autoActive).toBe(false);

    const on = buildAutoReality({
      accountType: "simulated",
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: true,
    });
    expect(on.autoActive).toBe(true);
    expect(on.autoLabel).toBe("Activo");
  });

  it("un tipo de cuenta ausente se declara NO MEDIDO con tono neutro (nunca virtual)", () => {
    const r = buildAutoReality({
      accountType: null,
      bookMode: "semi",
      autoArmed: null,
      paperDExecuteEnv: null,
    });
    expect(r.tone).toBe("unknown");
    expect(r.isVirtual).toBeNull();
    expect(r.moneyLabel).toBe(AUTO_REALITY_MONEY_UNKNOWN);
    expect(r.brokerLabel).toBe(AUTO_REALITY_BROKER_UNKNOWN);
    expect(r.accountTypeLabel).toBe(NO_MEASUREMENT_LABEL);
    expect(r.notes).toContain("Tipo de cuenta NO MEDIDO");
  });

  it("declara la ejecución paper NO MEDIDA mientras el eco no llega, sin colapsarla a false", () => {
    const r = buildAutoReality({
      accountType: "simulated",
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: null,
    });
    expect(r.tone).toBe("virtual");
    expect(r.notes).toContain("Ejecución paper NO MEDIDA");
  });

  it("sólo `live` reclama dinero real (reservado)", () => {
    const r = buildAutoReality({ accountType: "live" });
    expect(r.tone).toBe("real");
    expect(r.isVirtual).toBe(false);
    expect(r.moneyLabel).toBe("DINERO REAL");
  });
});

describe("accountTypeRealityLabel", () => {
  it("traduce cada tipo y degrada el ausente a NO MEDIDO", () => {
    expect(accountTypeRealityLabel("simulated")).toBe("Cuenta demo");
    expect(accountTypeRealityLabel("paper")).toBe("Paper (broker futuro)");
    expect(accountTypeRealityLabel("live")).toBe("Cuenta real");
    expect(accountTypeRealityLabel(null)).toBe(NO_MEASUREMENT_LABEL);
    expect(accountTypeRealityLabel(undefined)).toBe(NO_MEASUREMENT_LABEL);
  });
});
