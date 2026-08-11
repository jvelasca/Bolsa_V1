import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api";

/** Estado vivo de proveedores — operativo en Config; explicación larga en Ayuda. */
export function MarketProvidersStatusCard() {
  const marketQuery = useQuery({
    queryKey: ["market-providers"],
    queryFn: api.getMarketProviders,
    refetchInterval: 60_000,
  });

  const providers = marketQuery.data?.data ?? [];
  const yahoo = providers.find((p) => p.id === "yahoo");
  const xtb = providers.find((p) => p.id === "xtb");

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Yahoo Finance</CardTitle>
          <CardDescription>Histórico OHLCV</CardDescription>
        </CardHeader>
        <CardContent className="text-sm">
          {marketQuery.isLoading && (
            <p className="text-muted-foreground">Comprobando…</p>
          )}
          {yahoo && (
            <div className="space-y-1">
              <p
                className={
                  yahoo.healthy ? "text-emerald-400" : "text-muted-foreground"
                }
              >
                {yahoo.enabled
                  ? yahoo.healthy
                    ? "Disponible"
                    : "Configurado — sin respuesta"
                  : "Deshabilitado"}
              </p>
              <p className="text-muted-foreground">{yahoo.message}</p>
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">XTB Bridge</CardTitle>
          <CardDescription>Cotización en vivo (opcional)</CardDescription>
        </CardHeader>
        <CardContent className="text-sm">
          {marketQuery.isLoading && (
            <p className="text-muted-foreground">Comprobando…</p>
          )}
          {xtb && (
            <div className="space-y-1">
              <p
                className={
                  xtb.healthy ? "text-emerald-400" : "text-muted-foreground"
                }
              >
                {xtb.enabled
                  ? xtb.healthy
                    ? "Bridge conectado"
                    : "Configurado — offline"
                  : "No configurado"}
              </p>
              <p className="text-muted-foreground">{xtb.message}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
