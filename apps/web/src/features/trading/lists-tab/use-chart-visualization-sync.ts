/**
 * ADR-024: abrir/enfocar gráfico NO modifica la membresía de Estudio.
 * Hook conservado (montado desde trading-layout) por si se añade telemetría de vistas.
 *
 * @see docs/adr/024-estudio-supervision-universe.md
 */

export function useChartVisualizationSync() {
  // no-op: membresía Estudio solo vía «A Estudio» / API canónica
}
