/** Modo principal del inspector lateral. */
export type ChartInspectorMode = "data" | "config";

/** Bloques de lectura en modo Datos. */
export type ChartInspectorDataSection =
  | "instrument"
  | "chart"
  | "candle"
  | "database"
  | "alerts";

/** Pestañas internas en modo Config. */
export type ChartInspectorConfigSection =
  | "layers"
  | "series"
  | "objects"
  | "styles"
  | "context";

/** Subsección de capas (overlay / panel inferior). */
export type ChartInspectorLayerSection = "overlay" | "sub";

/** @deprecated Usar ChartInspectorDataSection */
export type ChartInspectorSummarySection = "instrument" | "chart";

/** @deprecated Usar ChartInspectorMode + secciones */
export type ChartInspectorTab =
  | "summary"
  | "candle"
  | "context"
  | "layers"
  | "series"
  | "objects"
  | "styles"
  | "alerts";

export type ChartInspectorNavigateInput =
  | {
      mode: ChartInspectorMode;
      dataSection?: ChartInspectorDataSection;
      configSection?: ChartInspectorConfigSection;
      layerSection?: ChartInspectorLayerSection;
      instanceId?: string;
    }
  | LegacyInspectorNavigateInput;

export interface ChartInspectorNavigateRequest {
  mode: ChartInspectorMode;
  dataSection?: ChartInspectorDataSection;
  configSection?: ChartInspectorConfigSection;
  layerSection?: ChartInspectorLayerSection;
  instanceId?: string;
  nonce: number;
}

type LegacyInspectorNavigateInput = {
  tab: ChartInspectorTab;
  layerSection?: ChartInspectorLayerSection;
  summarySection?: ChartInspectorSummarySection;
  instanceId?: string;
};

function legacyTabToNavigate(
  input: LegacyInspectorNavigateInput,
): Omit<ChartInspectorNavigateRequest, "nonce"> {
  switch (input.tab) {
    case "summary":
      return {
        mode: "data",
        dataSection: input.summarySection === "chart" ? "chart" : "instrument",
        instanceId: input.instanceId,
      };
    case "candle":
      return {
        mode: "data",
        dataSection: "candle",
        instanceId: input.instanceId,
      };
    case "alerts":
      return {
        mode: "data",
        dataSection: "alerts",
        instanceId: input.instanceId,
      };
    case "context":
      return {
        mode: "config",
        configSection: "context",
        instanceId: input.instanceId,
      };
    case "layers":
      return {
        mode: "config",
        configSection: "layers",
        layerSection: input.layerSection,
        instanceId: input.instanceId,
      };
    case "series":
      return {
        mode: "config",
        configSection: "series",
        instanceId: input.instanceId,
      };
    case "objects":
      return {
        mode: "config",
        configSection: "objects",
        instanceId: input.instanceId,
      };
    case "styles":
      return {
        mode: "config",
        configSection: "styles",
        instanceId: input.instanceId,
      };
    default:
      return { mode: "data", dataSection: "instrument" };
  }
}

export type ChartInspectorNavigateTarget = Omit<
  ChartInspectorNavigateRequest,
  "nonce"
>;

export function normalizeInspectorNavigateInput(
  input: ChartInspectorNavigateInput,
): ChartInspectorNavigateTarget {
  if ("mode" in input) {
    return {
      mode: input.mode,
      dataSection: input.dataSection,
      configSection: input.configSection,
      layerSection: input.layerSection,
      instanceId: input.instanceId,
    };
  }
  return legacyTabToNavigate(input);
}

export function inspectorNavigateKey(
  input: ChartInspectorNavigateInput,
): string {
  const nav = normalizeInspectorNavigateInput(input);
  const parts: string[] = [nav.mode];
  if (nav.dataSection) parts.push(nav.dataSection);
  if (nav.configSection) parts.push(nav.configSection);
  if (nav.layerSection) parts.push(nav.layerSection);
  if (nav.instanceId) parts.push(nav.instanceId);
  return parts.join(":");
}

export function inspectorSectionElementId(
  section:
    | ChartInspectorDataSection
    | ChartInspectorConfigSection
    | ChartInspectorLayerSection
    | ChartInspectorSummarySection,
): string {
  switch (section) {
    case "instrument":
      return "inspector-data-instrument";
    case "chart":
      return "inspector-data-chart";
    case "candle":
      return "inspector-data-candle";
    case "database":
      return "inspector-data-database";
    case "alerts":
      return "inspector-data-alerts";
    case "overlay":
      return "inspector-layers-overlay";
    case "sub":
      return "inspector-layers-sub";
    case "layers":
      return "inspector-config-layers";
    case "series":
      return "inspector-config-series";
    case "objects":
      return "inspector-config-objects";
    case "styles":
      return "inspector-config-styles";
    case "context":
      return "inspector-config-context";
    default:
      return `inspector-${section}`;
  }
}

export function createInspectorNavRequest(
  input: ChartInspectorNavigateInput,
): ChartInspectorNavigateRequest {
  const normalized = normalizeInspectorNavigateInput(input);
  return { ...normalized, nonce: Date.now() };
}
