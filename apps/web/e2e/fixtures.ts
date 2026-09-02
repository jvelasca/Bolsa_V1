/**
 * V1.82 — E2E fixtures barrel (public API for specs).
 * Implementations live in `e2e/helpers/e2e-mock-*` (same pattern as `integration.ts`).
 */
export {
  e2eEnabled,
  E2E_SKIP_REASON,
  setMercadoMockWorkspaceDocument,
  resetE2eMockRuntimeFlags,
  setE2eMockDataFreshness,
  setE2eMockReconStatus,
  setE2eMockUnknownOrder,
  setE2eMockDeskMode,
  setE2eMockPositionStage,
  emitE2eMockLifecycleEvent,
  getE2eMockLifecycleEvents,
} from "./helpers/e2e-mock-runtime";

export {
  installApiMocks,
  installMercadoApiMocks,
  installMercadoMultiApiMocks,
  installSessionReliabilityMocks,
  installGoldenSessionMocks,
  installStatefulLifecycleMocks,
  installHoyPaperDayApiMocks,
  installHoyStaleNoExecuteMocks,
  installUnknownOrderMocks,
} from "./helpers/e2e-mock-installers";
