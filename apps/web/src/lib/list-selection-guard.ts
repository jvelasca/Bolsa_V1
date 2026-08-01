/**
 * Guard compartido: selección manual de lista (hub Listas o carrusel Valores)
 * no debe ser sobrescrita por chartListContext hasta cambiar de gráfico.
 */

let manualListId: string | null = null;
let chartIdWhenSet: string | null = null;

export function setManualListSelection(listId: string, chartId: string | null | undefined) {
  manualListId = listId;
  chartIdWhenSet = chartId ?? null;
}

/** Al cambiar de pestaña de gráfico, liberar el override. */
export function clearManualListSelectionIfChartChanged(chartId: string | null | undefined) {
  const next = chartId ?? null;
  if (next !== chartIdWhenSet) {
    manualListId = null;
    chartIdWhenSet = null;
  }
}

export function getManualListSelection(): string | null {
  return manualListId;
}
