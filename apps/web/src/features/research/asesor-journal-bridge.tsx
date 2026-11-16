/**
 * Asesor → Journal · tarjeta puente — slice A3.
 *
 * `?tab=journal` ya no es una pestaña visible: monta esta tarjeta que explica
 * dónde vive el diario de decisiones y enlaza a `/decision-journal`. El Journal
 * no es la mesa operativa — firmar sigue en Confirm.
 */

import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { SectionTitle } from "@/features/research/asesor-ui";

export function AsesorJournalBridge() {
  return (
    <Card data-testid="asesor-journal-bridge">
      <CardHeader className="pb-2">
        <SectionTitle>Journal de decisiones</SectionTitle>
        <CardDescription>
          ¿Qué decidimos, por qué, qué ocurrió? No es la mesa operativa — firmar
          sigue en Confirm.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Link
          to="/decision-journal"
          className={cn(buttonVariants({ variant: "default", size: "sm" }))}
        >
          Abrir Journal
        </Link>
      </CardContent>
    </Card>
  );
}
