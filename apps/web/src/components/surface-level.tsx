/**
 * UI 6.x (`R-G1`/`RT-02`) — declaración explícita del nivel de una superficie.
 *
 * `R-G1` admite jerga de arquitectura/ingeniería en superficies de nivel 3 (diagnóstico),
 * pero exige que esa profundidad se declare. Este primitivo materializa la declaración en el
 * primer nivel, para que un operador no confunda una consola de diagnóstico con la vista de
 * operación diaria. NO es un mecanismo de profundidad nuevo: el disclosure sigue siendo
 * `TechnicalDetail`.
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md (`R-G1`/`RT-02`)
 */

export const SURFACE_LEVEL_ATTR = "data-surface-level";

export function SurfaceLevelDeclaration({
  level = 3,
  title,
  detail,
  testId,
}: {
  level?: 1 | 2 | 3;
  title: string;
  detail?: string;
  testId?: string;
}) {
  return (
    <section
      data-surface-level={String(level)}
      data-testid={testId}
      className="rounded-md border border-border bg-muted/30 px-3 py-2"
    >
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      {detail ? (
        <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>
      ) : null}
    </section>
  );
}
