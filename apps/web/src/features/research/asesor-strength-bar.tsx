/**
 * Fuerza de tendencia (`Fuerza`) de una fila de Cartera — slice A3·b.
 *
 * El rótulo (`Fuerza 7,5 / 10`) y la barra forman una unidad: la barra solo es
 * accesible si el número que la explica está a la vista. Sin valor medido no se
 * dibuja barra; el rótulo sí se pinta, porque lo declara la fila.
 */

export function AsesorStrengthBar({
  value,
  label,
}: {
  value: number | null;
  label: string;
}) {
  return (
    <>
      <p className="tabular-nums">{label}</p>
      {value == null ? null : (
        <div
          className="mt-1 h-1.5 w-16 overflow-hidden rounded-full bg-muted"
          role="img"
          aria-label={label}
        >
          <div
            className="h-full rounded-full bg-sky-600 dark:bg-sky-400"
            style={{ width: `${Math.max(0, Math.min(10, value)) * 10}%` }}
          />
        </div>
      )}
    </>
  );
}
