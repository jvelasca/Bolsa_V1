/**
 * C-1 (auditoría .161) — hint de posición en TRI-ESTADO para el dictamen diario.
 *
 * El motor de dictamen ya distingue tres estados (`position_open: bool | None`): `None`
 * significa «la cartera no se midió» y el servidor falla cerrado (`position_unmeasured`,
 * sin recomendar compra). Tres clientes web afirmaban `positionOpen=false` sin saberlo
 * (`false` constante, o `?? []` sobre una cartera que aún carga), de modo que la
 * ausencia de dato se convertía en «no tienes el valor»: un valor que SÍ se tiene podía
 * recibir dictamen de compra.
 *
 * Este módulo es la única traducción cartera → hint. PURA: no lee red ni reloj, y toma
 * SOLO valores estables (posiciones + «medida») para que un `queryKey`/`useMemo` no
 * dependa de la identidad del objeto de react-query. Un estado distinto de «cartera
 * leída» devuelve `null` (no medido), nunca `false`.
 */

import type { PositionDto } from "@bolsa/shared";

/** Forma mínima de la query de cartera que necesita el hint (react-query es compatible). */
export type PortfolioQueryLike = {
  data?: { data: { positions: readonly PositionDto[] } } | undefined;
  isLoading?: boolean;
  isError?: boolean;
};

function hasQuantity(position: PositionDto): boolean {
  return Math.abs(Number(position.quantity ?? 0)) > 0;
}

/**
 * ¿La cartera se LEYÓ? `false` mientras carga, si la consulta falló o si no hay dato.
 * Un `false` aquí NO significa «sin posición»: significa «no medido».
 */
export function portfolioMeasured(
  query: PortfolioQueryLike | null | undefined,
): boolean {
  if (!query || query.isLoading || query.isError) return false;
  return Boolean(query.data?.data && Array.isArray(query.data.data.positions));
}

/**
 * `true` = posición abierta medida, `false` = cartera leída y sin posición,
 * `null` = cartera NO medida (cargando, error o sin dato).
 *
 * Un símbolo ausente de una cartera SÍ leída es una medición: `false`.
 */
export function positionOpenHintFor(
  positions: readonly PositionDto[] | null | undefined,
  measured: boolean,
  instrumentId: string | null | undefined,
): boolean | null {
  const id = String(instrumentId ?? "").trim();
  if (!id) return null;
  if (!measured || !Array.isArray(positions)) return null;
  return positions.some(
    (position) => position.instrumentId === id && hasQuantity(position),
  );
}

/**
 * `queryKey` de `useInstrumentDailyOpinions`: un `null` (no medido) NO puede colapsar con
 * `false` (sin posición). Si colapsan, la caché de una medición anterior se sirve para un
 * estado que el servidor debe tratar de forma distinta (fail-closed).
 */
export function positionOpenHintKey(
  value: boolean | null | undefined,
): "1" | "0" | "u" {
  if (value === true) return "1";
  if (value === false) return "0";
  return "u";
}
