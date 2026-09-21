/**
 * V2.47 — copia ÚNICA del valor esperado económico (R + neto en dinero).
 *
 * El `formatMoney` de las superficies de entrada NO sirve para esto: no añade símbolo de
 * moneda ni signo, y un valor esperado sin signo se lee como un precio. Aquí el signo es
 * parte de la información (una oportunidad de valor esperado NEGATIVO no es una
 * oportunidad) y la ausencia de medición se declara con `null`, nunca con un `0 €`
 * inventado: quien no midió no puede afirmar "no deja dinero".
 */

export type ExpectedValueNumbersV1 = {
  expectedR?: number | null;
  netExpectedCurrency?: number | null;
};

function finite(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value;
}

/** `0.80` — la magnitud adimensional tal cual (sin sufijo `R`: el R es la unidad, no el número). */
export function formatExpectedR(
  value: number | null | undefined,
): string | null {
  const number = finite(value);
  if (number === null) return null;
  return number.toFixed(2);
}

/** `+34.00 €` / `−12.50 €` — signo explícito, símbolo explícito (universo EUR). */
export function formatExpectedCurrency(
  value: number | null | undefined,
): string | null {
  const number = finite(value);
  if (number === null) return null;
  const sign = number > 0 ? "+" : number < 0 ? "−" : "";
  return `${sign}${Math.abs(number).toFixed(2)} €`;
}

/**
 * `+34.00 € · R esperado 0.80` — etiqueta de la fila de valor esperado.
 *
 * `null` cuando NO hay nada medido (ni R ni neto): la superficie no renderiza fila en vez
 * de publicar un `0 €` que afirmaría una economía que nadie calculó. Si solo hay R
 * (medición PARTIAL, sin coste cerrado) se publica el R y se OMITE el neto: ese hueco es
 * exactamente el dato que falta.
 */
export function formatExpectedValueLabel(
  values: ExpectedValueNumbersV1,
): string | null {
  const money = formatExpectedCurrency(values.netExpectedCurrency);
  const r = formatExpectedR(values.expectedR);
  if (money === null && r === null) return null;
  const parts = [money, r === null ? null : `R esperado ${r}`].filter(
    (part): part is string => part !== null,
  );
  return parts.join(" · ");
}
