import { cn } from "@/lib/utils";

export function Card({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card text-card-foreground shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col gap-1.5 p-6 pb-4", className)}
      {...props}
    />
  );
}

/**
 * Tags de encabezado admitidos por `CardTitle` (jerarquía documental).
 * Se excluye `h1` a propósito: el `h1` es único por página y se escribe inline en la propia página.
 */
export type CardTitleLevel = "h2" | "h3" | "h4" | "h5" | "h6";

export function CardTitle({
  className,
  /**
   * Nivel del encabezado. Por defecto `h3` (retrocompatible con las superficies
   * existentes, donde la card cuelga de un `h2`). Pásalo a `"h2"` cuando la card
   * sea el primer bloque de una página y su título deba colgar directamente del
   * `h1` (evita el salto `h1 → h3` de la regla `heading-order`).
   */
  level = "h3",
  ...props
}: React.HTMLAttributes<HTMLHeadingElement> & { level?: CardTitleLevel }) {
  const Heading = level;
  return (
    <Heading
      className={cn(
        "text-lg font-semibold leading-none tracking-tight",
        className,
      )}
      {...props}
    />
  );
}

export function CardDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-sm text-muted-foreground", className)} {...props} />
  );
}

export function CardContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6 pt-0", className)} {...props} />;
}
