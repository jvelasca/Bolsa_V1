/**
 * Contrato FE/BE (F5a): torre de control estática DTO(manual) ↔ DTO(OpenAPI).
 *
 * FUENTE DE VERDAD: apps/web/api/openapi.json (dump de FastAPI, ver
 * apps/api-python/scripts/dump_openapi.py) → openapi-typescript → ./schema.
 * Regeneración: `pnpm --filter @bolsa/web contract:gen` · gate de spec:
 * `pnpm --filter @bolsa/web contract:check`.
 *
 * Gate de tipos (este fichero). Para un conjunto *centinela* de DTOs de
 * endpoints de uso intensivo se garantiza en compilación que el FE **nunca
 * declara un campo que el OpenAPI no emite** (toda clave del DTO-FE existe en
 * el contrato). Es el sentido anti-"drift silencioso" del FE: si alguien añade
 * al DTO-FE un campo ausente de OpenAPI, el `typecheck` rompe aquí en vez de en
 * runtime. La *fidelidad de tipos* (p. ej. `manifest?: RunManifest` vs
 * `manifest: object|null`) y la igualdad estricta bidireccional quedan como
 * deuda medida y documentada en docs/engineering/traspaso-f5a-* (ver §findings).
 */
import type { components } from "./schema";

type Contract = components["schemas"];

/** Campo `K` del FE no presente en el contrato → drift prohibido (rompe build). */
type MissingInContract<FE, BE> = Exclude<keyof FE, keyof BE>;

type HasNoMissingKeys<FE, BE> =
  MissingInContract<FE, BE> extends never ? true : false;

// ---------------------------------------------------------------------------
// Centinelas activos (DTO-FE @bolsa/shared ↔ componente BE). Si el FE declara
// una clave ausente del contrato, la guarda materializa un TS2322 en su línea.
// ---------------------------------------------------------------------------
type G1 = HasNoMissingKeys<
  import("@bolsa/shared").BacktestRunDto,
  Contract["BacktestRunDto"]
>;
type G2 = HasNoMissingKeys<
  import("@bolsa/shared").PortfolioSummaryDto,
  Contract["PortfolioSummaryDto"]
>;
type G3 = HasNoMissingKeys<
  import("@bolsa/shared").InvestmentAccountDto,
  Contract["InvestmentAccountDto"]
>;
/** P2.8: CoreR/SupervisedF3 blobs — clave top-level FE ⊆ contrato. */
type G4 = HasNoMissingKeys<
  import("@bolsa/shared").CoreRBundleDto,
  Contract["CoreRBundleDto"]
>;
type G5 = HasNoMissingKeys<
  import("@bolsa/shared").SupervisedF3BundleDto,
  Contract["SupervisedF3BundleDto"]
>;

const _guard1: G1 = true;
const _guard2: G2 = true;
const _guard3: G3 = true;
const _guard4: G4 = true;
const _guard5: G5 = true;

export {};
/** Agregado meramente para que el compilador considere usadas las guardas. */
export const contractContractSentinels = [
  _guard1,
  _guard2,
  _guard3,
  _guard4,
  _guard5,
] as const;
