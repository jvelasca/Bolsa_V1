/**
 * Tip vacío del panel de optimización: aparece cuando aún no hay prueba origen.
 * Data-only, sin props ni lógica de negocio.
 */
export function OptimizeEmptyTip() {
  return (
    <p
      className="rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground"
      title="Consejo: ve a Probar estrategia, lanza una prueba y en el resultado pulsa Optimizar. Así se rellenan solo valor, estrategia y métricas."
    >
      Tip: primero prueba una estrategia; en el resultado pulsa{" "}
      <strong>Optimizar</strong> para cargar aquí la prueba origen.
    </p>
  );
}
