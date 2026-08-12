/**
 * Contrato FE/BE (F5a): torre de control estática DTO(manual) ↔ DTO(OpenAPI).
 *
 * FUENTE DE VERDAD: apps/web/api/openapi.json (dump de FastAPI, ver
 * apps/api-python/scripts/dump_openapi.py) → openapi-typescript → ./schema.
 * Regeneración: `pnpm --filter @bolsa/web contract:gen` · gate de spec:
 * `pnpm --filter @bolsa/web contract:check`.
 *
 * Gate de tipos (este fichero). Para un conjunto *centinela* de DTOs de
 * endpoints de uso intensivo se garantiza en compilación la igualdad de CLAVES
 * bidireccional DTO-FE ↔ contrato OpenAPI:
 *   · FE ⊆ contrato: el FE **nunca declara un campo que el OpenAPI no emite**
 *     (si alguien añade al DTO-FE un campo ausente de OpenAPI, el typecheck
 *     rompe aquí en vez de en runtime).
 *   · contrato ⊆ FE: el OpenAPI **nunca emite un campo que el DTO-FE ignore**
 *     (campo nuevo del backbone que el FE desconoce → drift silencioso; F5a §6).
 * La *fidelidad de tipos* del valor (p. ej. `manifest?: RunManifest` vs
 * `manifest: object|null`, `number`↔`integer`) NO se comprueba aquí por diseño:
 * son normalizaciones benignas o mejoras de tipado del FE (no drift TS
 * detectable) y quedan como deuda de fuente de verdad P2.6.
 */
import type { components } from "./schema";

type Contract = components["schemas"];

/** Campo `K` del FE no presente en el contrato → drift prohibido (rompe build). */
type MissingInContract<FE, BE> = Exclude<keyof FE, keyof BE>;

type HasNoMissingKeys<FE, BE> =
  MissingInContract<FE, BE> extends never ? true : false;

/**
 * F5a §6 fidelidad — dirección contrato→FE: campo que el BE emite pero el DTO-FE
 * NO declara → drift silencioso (el FE ignoraría un campo nuevo del backbone).
 * Combinado con HasNoMissingKeys garantiza igualdad de claves bidireccional.
 */
type MissingInFE<BE, FE> = Exclude<keyof BE, keyof FE>;

type CoversContract<BE, FE> = MissingInFE<BE, FE> extends never ? true : false;

// ---------------------------------------------------------------------------
// Centinelas activos (DTO-FE @bolsa/shared ↔ componente BE). Cada sentinela
// combina ambos sentidos de fidelidad de CLAVES:
//   · HasNoMissingKeys<FE,BE>  — el FE NO declara una clave ausente del contrato
//     (drift prohibido FE⊆contrato).
//   · CoversContract<BE,FE>    — el BE NO emite una clave que el DTO-FE ignore
//     (drift en contrato⊆FE, F5a §6: campo nuevo del backbone que el FE no conoce).
// Cuando cualquiera de los dos sentidos tiene drift, la guarda materializa un
// TS2322 en su línea y rompe el typecheck.
// ---------------------------------------------------------------------------
type G1 =
  HasNoMissingKeys<
    import("@bolsa/shared").BacktestRunDto,
    Contract["BacktestRunDto"]
  > extends true
    ? CoversContract<
        Contract["BacktestRunDto"],
        import("@bolsa/shared").BacktestRunDto
      >
    : false;
type G2 =
  HasNoMissingKeys<
    import("@bolsa/shared").PortfolioSummaryDto,
    Contract["PortfolioSummaryDto"]
  > extends true
    ? CoversContract<
        Contract["PortfolioSummaryDto"],
        import("@bolsa/shared").PortfolioSummaryDto
      >
    : false;
type G3 =
  HasNoMissingKeys<
    import("@bolsa/shared").InvestmentAccountDto,
    Contract["InvestmentAccountDto"]
  > extends true
    ? CoversContract<
        Contract["InvestmentAccountDto"],
        import("@bolsa/shared").InvestmentAccountDto
      >
    : false;
/** P2.8: CoreR/SupervisedF3 blobs — claves top-level bidireccionales. */
type G4 =
  HasNoMissingKeys<
    import("@bolsa/shared").CoreRBundleDto,
    Contract["CoreRBundleDto"]
  > extends true
    ? CoversContract<
        Contract["CoreRBundleDto"],
        import("@bolsa/shared").CoreRBundleDto
      >
    : false;
type G5 =
  HasNoMissingKeys<
    import("@bolsa/shared").SupervisedF3BundleDto,
    Contract["SupervisedF3BundleDto"]
  > extends true
    ? CoversContract<
        Contract["SupervisedF3BundleDto"],
        import("@bolsa/shared").SupervisedF3BundleDto
      >
    : false;
/** F5a §6: sentinelas adicionales de endpoints de uso intensivo en la UI. */
type G6 =
  HasNoMissingKeys<
    import("@bolsa/shared").InstrumentDto,
    Contract["InstrumentDto"]
  > extends true
    ? CoversContract<
        Contract["InstrumentDto"],
        import("@bolsa/shared").InstrumentDto
      >
    : false;
type G7 =
  HasNoMissingKeys<
    import("@bolsa/shared").OhlcvBarDto,
    Contract["OhlcvBarDto"]
  > extends true
    ? CoversContract<
        Contract["OhlcvBarDto"],
        import("@bolsa/shared").OhlcvBarDto
      >
    : false;
type G8 =
  HasNoMissingKeys<
    import("@bolsa/shared").PortfolioDto,
    Contract["PortfolioDto"]
  > extends true
    ? CoversContract<
        Contract["PortfolioDto"],
        import("@bolsa/shared").PortfolioDto
      >
    : false;
type G9 =
  HasNoMissingKeys<
    import("@bolsa/shared").PositionDto,
    Contract["PositionDto"]
  > extends true
    ? CoversContract<
        Contract["PositionDto"],
        import("@bolsa/shared").PositionDto
      >
    : false;
type G10 =
  HasNoMissingKeys<
    import("@bolsa/shared").InvestmentPortfolioDto,
    Contract["InvestmentPortfolioDto"]
  > extends true
    ? CoversContract<
        Contract["InvestmentPortfolioDto"],
        import("@bolsa/shared").InvestmentPortfolioDto
      >
    : false;
type G11 =
  HasNoMissingKeys<
    import("@bolsa/shared").AccountSummaryDto,
    Contract["AccountSummaryDto"]
  > extends true
    ? CoversContract<
        Contract["AccountSummaryDto"],
        import("@bolsa/shared").AccountSummaryDto
      >
    : false;

const _guard1: G1 = true;
const _guard2: G2 = true;
const _guard3: G3 = true;
const _guard4: G4 = true;
const _guard5: G5 = true;
const _guard6: G6 = true;
const _guard7: G7 = true;
const _guard8: G8 = true;
const _guard9: G9 = true;
const _guard10: G10 = true;
const _guard11: G11 = true;

export {};
/** Agregado meramente para que el compilador considere usadas las guardas. */
export const contractContractSentinels = [
  _guard1,
  _guard2,
  _guard3,
  _guard4,
  _guard5,
  _guard6,
  _guard7,
  _guard8,
  _guard9,
  _guard10,
  _guard11,
] as const;
