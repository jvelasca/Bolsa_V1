/**
 * S3 · Cartera del Asesor — lista que reúne recomendación, tendencia, fuerza,
 * soportes/resistencias y momento, sin combinarlos.
 *
 * Regla dura: la ÚNICA recomendación es la del dictamen (`marketStanceLabel`).
 * Tendencia, fuerza, niveles y momento son contexto independiente: se muestran
 * en columnas distintas y no se ordenan ni se ponderan por coincidencia. La
 * columna «Estado» es una categoría de presentación, no una señal de compra.
 *
 * No hay CTA de compra: esta pestaña explica. Firmar vive en Confirm y operar en
 * Mercado.
 *
 * «Midmeas» y «ausente» son estados distintos: mientras una fuente carga, la
 * celda dice «Midiendo…», no «Sin dato». Un hueco medido se declara con su
 * causa y nunca se colapsa a 0.
 *
 * Slice A3·b: este módulo se queda con lo que es del contenedor —cabecera,
 * banners de ausencia, totales y tabla—; la fila vive en `asesor-cartera-row`,
 * los filtros en `asesor-cartera-filters` y el nivel 3 en
 * `asesor-cartera-technical-detail`.
 *
 * @see docs/engineering/diseno-asesor-cartera-s3-2026-11-12.md
 * @see docs/engineering/diseno-asesor-backend-ui-2026-11-12.md
 */

import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  DEFAULT_ASESOR_CARTERA_FILTER,
  ESTUDIO_LIST_ID,
  filterAsesorCarteraRows,
  sortAsesorCarteraRows,
  type AsesorCarteraFilterV1,
} from "@bolsa/shared";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { MERCADO_PATH } from "@/features/confirm/daily-nav";
import { focusInstrumentInMercado } from "@/features/trading/focus-instrument-in-mercado";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { cn } from "@/lib/utils";
import { useAsesorCarteraData } from "@/features/research/use-asesor-cartera-data";
import { AsesorCarteraFilters } from "@/features/research/asesor-cartera-filters";
import { CarteraRow } from "@/features/research/asesor-cartera-row";

export function AsesorCarteraPanel({ className }: { className?: string }) {
  const data = useAsesorCarteraData();
  const [filter, setFilter] = useState<AsesorCarteraFilterV1>(
    DEFAULT_ASESOR_CARTERA_FILTER,
  );
  const navigate = useNavigate();
  const openChartTab = useWorkspaceStore((s) => s.openChartTab);
  const focusInstrumentFromList = useWorkspaceStore(
    (s) => s.focusInstrumentFromList,
  );

  const rows = useMemo(
    () => sortAsesorCarteraRows(filterAsesorCarteraRows(data.rows, filter)),
    [data.rows, filter],
  );

  const countByState = data.summary.byState;

  const staleCount = useMemo(
    () => data.rows.filter((row) => row.quote.stale).length,
    [data.rows],
  );

  return (
    <div className={cn("space-y-4", className)} data-testid="asesor-cartera">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle level="h2" className="text-base">
            Cartera del Asesor
          </CardTitle>
          <CardDescription>
            Universo en Estudio y posiciones de la cuenta activa. Cada columna
            mide una cosa distinta: tendencia, fuerza, soportes/resistencias y
            momento informan; la lista no combina señales ni autoriza compras.
            La recomendación es la del dictamen y no sustituye a la firma en
            Confirm.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.empty ? (
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>
                No hay valores en Estudio ni posiciones abiertas. Añade valores
                en Mercado (Listas → Pasar a Estudio).
              </p>
              <Link
                to={MERCADO_PATH}
                className={cn(
                  buttonVariants({ variant: "outline", size: "sm" }),
                )}
              >
                Ir a Mercado
              </Link>
            </div>
          ) : (
            <>
              <p
                className="text-xs text-muted-foreground"
                data-testid="asesor-cartera-totals"
              >
                {data.summary.total} valores · {data.summary.withPosition} con
                posición · {data.summary.unmeasured} sin medir ·{" "}
                {data.summary.withGaps} con huecos declarados
                {data.loading ? " · midiendo…" : ""}
              </p>

              {staleCount > 0 ? (
                <p
                  className="text-xs text-amber-700 dark:text-amber-300"
                  data-testid="asesor-cartera-stale"
                >
                  {staleCount} valor{staleCount === 1 ? "" : "es"} con el cierre
                  desactualizado: el precio y los niveles son de una sesión
                  anterior.
                </p>
              ) : null}

              {data.portfolioError ? (
                <p className="text-xs text-destructive">
                  No se pudo leer la cartera: las filas quedan como «Cartera sin
                  medir». No se afirma que no haya posición.
                </p>
              ) : null}
              {data.studiesError ? (
                <p className="text-xs text-destructive">
                  No se pudo leer el parte diario: tendencia y fuerza se
                  declaran ausentes.
                </p>
              ) : null}
              {data.studiesTruncated ? (
                <p
                  className="text-xs text-muted-foreground"
                  data-testid="asesor-cartera-studies-truncated"
                >
                  El listado del parte diario vino recortado: un valor puede
                  tener plan fuera de la página. No se afirma «sin plan» sobre
                  datos recortados.
                </p>
              ) : null}
              {data.quotesError ? (
                <p className="text-xs text-muted-foreground">
                  Sin cotizaciones en lote: el precio se declara ausente.
                </p>
              ) : null}
              {data.barsFailedIds.length > 0 ? (
                <p
                  className="text-xs text-muted-foreground"
                  data-testid="asesor-cartera-bars-failed"
                >
                  Sin velas para {data.barsFailedIds.length} valor
                  {data.barsFailedIds.length === 1 ? "" : "es"}: sus soportes y
                  resistencias quedan como hueco, no como cero.
                </p>
              ) : null}

              <AsesorCarteraFilters
                filter={filter}
                onChange={setFilter}
                countByState={countByState}
                total={data.summary.total}
              />

              {rows.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Ningún valor en este filtro.
                </p>
              ) : (
                <div className="max-h-[42rem] overflow-auto rounded-md border border-border">
                  <table className="w-full min-w-[72rem] text-left text-xs">
                    <caption className="sr-only">
                      Cartera del Asesor: recomendación del dictamen, tendencia,
                      fuerza, soportes y resistencias, momento y posición. Las
                      columnas no se combinan entre sí.
                    </caption>
                    <thead className="sticky top-0 z-10 bg-muted text-muted-foreground shadow-sm">
                      <tr>
                        <th
                          scope="col"
                          className="sticky left-0 z-20 bg-muted px-2 py-2 font-medium"
                        >
                          Valor
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Precio / Día
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Recomendación
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Tendencia
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Fuerza
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Soportes / Resistencias
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Momento
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Posición
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Estado
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <CarteraRow
                          key={row.instrumentId}
                          row={row}
                          opinion={
                            data.opinionsById.get(row.instrumentId) ?? null
                          }
                          loading={{
                            quotes: data.quotesLoading,
                            bars: data.barsLoading,
                            opinions: data.opinionsLoading,
                          }}
                          onOpenInMercado={() =>
                            focusInstrumentInMercado(
                              navigate,
                              { openChartTab, focusInstrumentFromList },
                              {
                                instrumentId: row.instrumentId,
                                symbol: row.symbol,
                              },
                              { listId: ESTUDIO_LIST_ID },
                            )
                          }
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
