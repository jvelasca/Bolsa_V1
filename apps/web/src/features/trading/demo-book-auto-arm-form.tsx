/**
 * V2.39 — formulario A3 compartido (Cuentas + AUTO Desk).
 * Frase exacta → tryArmAuto. Arm ≠ execute. No panel nuevo de Mercado.
 */

import { useCallback, useEffect, useState } from "react";
import { PAPER_AUTO_ARMED_EXEC_OFF } from "@bolsa/shared";

import { cn } from "@/lib/utils";
import {
  AUTO_ARM_CONFIRM_PHRASE,
  loadAutoArm,
  tryArmAuto,
  type DemoBookAutoArm,
} from "@/features/trading/demo-book-auto-arm";

export function useAutoArmState(): DemoBookAutoArm {
  const [arm, setArm] = useState<DemoBookAutoArm>(() => loadAutoArm());
  const refresh = useCallback(() => setArm(loadAutoArm()), []);
  useEffect(() => {
    const onArm = () => refresh();
    window.addEventListener("bolsa-demo-book-auto-arm", onArm);
    return () => window.removeEventListener("bolsa-demo-book-auto-arm", onArm);
  }, [refresh]);
  return arm;
}

type DemoBookAutoArmFormProps = {
  onArmed: () => void;
  onCancel: () => void;
  className?: string;
};

export function DemoBookAutoArmForm({
  onArmed,
  onCancel,
  className,
}: DemoBookAutoArmFormProps) {
  const [phrase, setPhrase] = useState("");
  const [armError, setArmError] = useState<string | null>(null);

  function confirmArm() {
    const result = tryArmAuto(phrase);
    if (!result.ok) {
      setArmError(result.error);
      return;
    }
    setPhrase("");
    setArmError(null);
    onArmed();
  }

  return (
    <div
      className={cn(
        "space-y-1.5 rounded border border-amber-500/40 bg-amber-500/10 p-2",
        className,
      )}
      data-testid="demo-book-auto-arm-form"
    >
      <p className="text-[10px] leading-snug text-foreground">
        Armar AUTO (doble confirmación). Escribe exactamente{" "}
        <span className="font-semibold">{AUTO_ARM_CONFIRM_PHRASE}</span>. Arm ≠
        execute — con env off verás «{PAPER_AUTO_ARMED_EXEC_OFF}».
      </p>
      <input
        type="text"
        value={phrase}
        onChange={(e) => setPhrase(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") confirmArm();
        }}
        placeholder={AUTO_ARM_CONFIRM_PHRASE}
        autoComplete="off"
        data-testid="demo-book-auto-arm-phrase"
        className="w-full rounded border border-border bg-background px-1.5 py-1 text-foreground"
      />
      {armError ? (
        <p
          className="text-[10px] text-red-700 dark:text-red-300"
          data-testid="demo-book-auto-arm-error"
        >
          {armError}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-1">
        <button
          type="button"
          data-testid="demo-book-auto-arm-confirm"
          onClick={() => confirmArm()}
          className="rounded border border-emerald-500/60 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-800 dark:text-emerald-300"
        >
          Confirmar armado
        </button>
        <button
          type="button"
          data-testid="demo-book-auto-arm-cancel"
          onClick={() => {
            setPhrase("");
            setArmError(null);
            onCancel();
          }}
          className="rounded border border-border px-2 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}
