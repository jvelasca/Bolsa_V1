/**
 * P1-01 — declaración visual del hueco de lectura de una colección.
 *
 * No renderiza nada cuando la colección se ha leído (vacía o llena): el vacío
 * medido lo pinta la superficie con su propia prosa. Aquí solo vive la
 * ausencia: error, sin dato y carga.
 */
import { cn } from "@/lib/utils";
import {
  collectionAbsenceCopy,
  type CollectionReadState,
} from "@/components/query-absence";

export function CollectionAbsence({
  state,
  subject,
  testId,
  className,
}: {
  state: CollectionReadState;
  /** Sujeto con artículo, en minúscula: `el historial de movimientos`. */
  subject: string;
  testId?: string;
  className?: string;
}) {
  const copy = collectionAbsenceCopy(state, subject);
  if (copy === null) return null;
  return (
    <p
      data-testid={testId}
      data-absence-state={state}
      role={state === "error" ? "alert" : undefined}
      className={cn(
        "p-3 text-xs text-muted-foreground",
        state === "error" && "text-destructive",
        className,
      )}
    >
      {copy}
    </p>
  );
}
