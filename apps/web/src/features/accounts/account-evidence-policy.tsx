/**
 * Política de evidencia de rentabilidad por cuenta.
 *
 * Los umbrales se fijan ANTES de medir un backtest DÍA D; si se escogen mirando el resultado
 * la prueba no vale. Sin fila guardada rigen los valores estrictos por defecto.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { inputClassName } from "@/components/ui/dialog";
import { api } from "@/lib/api";

type FieldKey =
  | "minWindows"
  | "minTradesTotal"
  | "minPositiveWindowPct"
  | "minNetReturnPct"
  | "maxDrawdownPct"
  | "minExcessVsBuyHoldPct"
  | "holdoutPct"
  | "minCommissionBps"
  | "minSlippageBps"
  | "minSpreadBps";

const FIELDS: ReadonlyArray<{
  key: FieldKey;
  label: string;
  hint: string;
  step: number;
}> = [
  { key: "minWindows", label: "Fechas D mínimas", hint: "5–1000", step: 1 },
  {
    key: "minTradesTotal",
    label: "Operaciones mínimas (total)",
    hint: "30–100000",
    step: 1,
  },
  {
    key: "minPositiveWindowPct",
    label: "% de ventanas positivas",
    hint: "50–100",
    step: 1,
  },
  {
    key: "minNetReturnPct",
    label: "Retorno neto mínimo (%)",
    hint: "0–1000",
    step: 0.1,
  },
  {
    key: "maxDrawdownPct",
    label: "Drawdown máximo (%)",
    hint: "1–50",
    step: 0.5,
  },
  {
    key: "minExcessVsBuyHoldPct",
    label: "Exceso mínimo sobre comprar y mantener (%)",
    hint: "0–1000",
    step: 0.1,
  },
  {
    key: "holdoutPct",
    label: "Reserva fuera de muestra (%)",
    hint: "20–60",
    step: 1,
  },
  {
    key: "minCommissionBps",
    label: "Comisión mínima por lado (bps)",
    hint: "1–200",
    step: 0.5,
  },
  {
    key: "minSlippageBps",
    label: "Slippage mínimo por lado (bps)",
    hint: "1–200",
    step: 0.5,
  },
  {
    key: "minSpreadBps",
    label: "Spread mínimo (bps)",
    hint: "0–200",
    step: 0.5,
  },
];

type Draft = Record<FieldKey, string>;

function toDraft(policy: Record<FieldKey, number>): Draft {
  return Object.fromEntries(
    FIELDS.map((f) => [f.key, String(policy[f.key])]),
  ) as Draft;
}

export function AccountEvidencePolicy({ accountId }: { accountId: string }) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["account-evidence-policy", accountId],
    queryFn: () => api.getAccountEvidencePolicy(accountId),
    staleTime: 15_000,
  });
  const [draft, setDraft] = useState<Draft | null>(null);

  useEffect(() => {
    if (query.data) setDraft(toDraft(query.data));
  }, [query.data]);

  const mut = useMutation({
    mutationFn: (values: Draft) =>
      api.putAccountEvidencePolicy(
        accountId,
        Object.fromEntries(FIELDS.map((f) => [f.key, Number(values[f.key])])),
      ),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ["account-evidence-policy", accountId],
      }),
  });

  const policy = query.data;
  const invalid =
    draft !== null &&
    FIELDS.some(
      (f) =>
        draft[f.key].trim() === "" || !Number.isFinite(Number(draft[f.key])),
    );

  return (
    <div
      className="space-y-3 rounded-lg border border-border p-3"
      data-testid="account-evidence-policy"
    >
      <div>
        <p className="text-sm font-medium">
          Evidencia de rentabilidad (cuenta)
        </p>
        <p className="text-xs text-muted-foreground">
          Umbrales que un backtest DÍA D debe superar para contar como prueba.
          Fíjalos antes de medir: no sirven si se ajustan viendo el resultado.
          Los costes son mínimos obligatorios (un backtest sin costes no
          cuenta).
        </p>
      </div>

      {query.isError ? (
        <p className="text-xs text-destructive" role="alert">
          No se pudo cargar la política de evidencia.
        </p>
      ) : null}

      {draft ? (
        <>
          <div className="grid gap-2 sm:grid-cols-2">
            {FIELDS.map((f) => (
              <label key={f.key} className="space-y-1 text-xs">
                <span className="font-medium">{f.label}</span>
                <input
                  type="number"
                  step={f.step}
                  className={inputClassName}
                  value={draft[f.key]}
                  data-testid={`evidence-policy-${f.key}`}
                  onChange={(e) =>
                    setDraft({ ...draft, [f.key]: e.target.value })
                  }
                />
                <span className="text-muted-foreground">{f.hint}</span>
              </label>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="rounded border border-primary/50 bg-primary/10 px-3 py-1 text-xs font-medium disabled:opacity-50"
              disabled={mut.isPending || invalid}
              data-testid="evidence-policy-save"
              onClick={() => mut.mutate(draft)}
            >
              Guardar umbrales
            </button>
            <span className="text-[11px] text-muted-foreground">
              {policy?.isDefault
                ? "Valores por defecto (aún no guardados)"
                : `Versión ${policy?.version ?? "—"}`}
              {policy
                ? ` · coste mínimo ida y vuelta: ${policy.minRoundTripCostBps} bps`
                : ""}
            </span>
          </div>
        </>
      ) : null}

      {mut.isError ? (
        <p className="text-xs text-destructive" role="alert">
          {mut.error instanceof Error
            ? mut.error.message
            : "No se pudo guardar la política."}
        </p>
      ) : null}
    </div>
  );
}
