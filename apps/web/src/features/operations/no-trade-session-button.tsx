/**
 * P4 — «No operar hoy» → Journal session_verdict (sin fill).
 */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

type NoTradeSessionButtonProps = {
  className?: string;
};

export function NoTradeSessionButton({ className }: NoTradeSessionButtonProps) {
  const { effectiveAccountId } = useActiveAccount();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: async () => {
      if (!effectiveAccountId) throw new Error("Selecciona una cuenta activa.");
      return api.recordSessionVerdict(effectiveAccountId, {
        verdict: "no_trade",
        note: note.trim() || undefined,
      });
    },
    onSuccess: () => {
      setFeedback("Veredicto registrado en el Journal.");
      void qc.invalidateQueries({
        queryKey: ["decision-journal", effectiveAccountId],
      });
      setOpen(false);
      setNote("");
    },
    onError: (e: Error) => setFeedback(e.message),
  });

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className={className}
        disabled={!effectiveAccountId}
        onClick={() => {
          setFeedback(null);
          setOpen(true);
        }}
        data-testid="no-trade-session-button"
      >
        No operar hoy
      </Button>
      {feedback && !open && (
        <p className="text-[10px] text-muted-foreground">{feedback}</p>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>No operar hoy</DialogTitle>
            <DialogDescription>
              Registra un veredicto explícito de sesión en el Decision Journal.
              No ejecuta órdenes ni inventa BUY — 0 operaciones puede ser un día
              excelente.
            </DialogDescription>
          </DialogHeader>
          <label className="block space-y-1 text-sm">
            <span className="text-muted-foreground">Nota (opcional)</span>
            <textarea
              className="min-h-[72px] w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Ej. mercado sin edge, esperar confirmación macro…"
            />
          </label>
          {mutation.isError && (
            <p className="text-sm text-destructive">
              {(mutation.error as Error).message}
            </p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setOpen(false)}
            >
              Cancelar
            </Button>
            <Button
              type="button"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Registrando…" : "Registrar veredicto"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
