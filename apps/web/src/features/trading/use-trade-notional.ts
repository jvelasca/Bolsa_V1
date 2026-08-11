import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

function formatFxRate(rate: number) {
  return rate.toLocaleString("es-ES", {
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  });
}

export function useTradeNotional(
  instrumentCurrency: string,
  accountCurrency: string,
  quantity: number,
  price: number,
) {
  const needsFx = instrumentCurrency !== accountCurrency;

  const fxQuery = useQuery({
    queryKey: ["fx", instrumentCurrency, accountCurrency],
    queryFn: () => api.getFxRate(instrumentCurrency, accountCurrency),
    enabled: needsFx && quantity > 0 && price > 0,
    staleTime: 60_000,
    refetchInterval: 120_000,
  });

  const fxRate = needsFx ? (fxQuery.data?.data.rate ?? null) : 1;
  const notionalInstrument = quantity * price;
  const notionalAccount =
    fxRate != null && Number.isFinite(notionalInstrument)
      ? notionalInstrument * fxRate
      : needsFx
        ? null
        : notionalInstrument;

  const fxLabel =
    fxRate != null
      ? `1 ${instrumentCurrency} = ${formatFxRate(fxRate)} ${accountCurrency}`
      : fxQuery.isLoading
        ? "Cargando…"
        : "—";

  return {
    needsFx,
    fxRate,
    fxLabel,
    notionalInstrument,
    notionalAccount,
    isFxLoading: needsFx && fxQuery.isLoading,
    yahooSymbol: fxQuery.data?.data.yahooSymbol,
  };
}
