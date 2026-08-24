import { Link } from "react-router-dom";
import {
  ASESOR_LABEL,
  LABORATORIO_LABEL,
  SEÑALES_LABEL,
  asesorHistoryHref,
} from "@/features/confirm/daily-nav";
import { ScreenersHub } from "@/features/screeners/screeners-hub";

export function ScreenersPage() {
  return (
    <div className="flex min-h-0 flex-col gap-3 lg:h-[calc(100dvh-3.5rem)] lg:min-h-[560px] lg:overflow-hidden">
      <header className="shrink-0 space-y-1">
        <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
          {SEÑALES_LABEL}
        </h2>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Puerta diaria de señales: escaneo de universo en la última barra, cola
          async y alertas. Clic en un hit o «Gráfico» abre el instrumento en{" "}
          <Link to="/trading" className="text-primary hover:underline">
            Trading
          </Link>
          . Simulaciones históricas en{" "}
          <Link to="/backtests" className="text-primary hover:underline">
            {LABORATORIO_LABEL}
          </Link>
          ; ledger de pruebas en{" "}
          <Link
            to={asesorHistoryHref()}
            className="text-primary hover:underline"
          >
            {ASESOR_LABEL}
          </Link>
          .
        </p>
      </header>
      <div className="min-h-0 flex-1 overflow-auto px-1 sm:px-0 lg:overflow-hidden">
        <ScreenersHub />
      </div>
    </div>
  );
}
