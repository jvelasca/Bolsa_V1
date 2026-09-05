/**
 * V2.39 — formulario A3 compartido (Cuentas + AUTO Desk).
 * V2.42 — CABIN_TOUCH_TARGET + CABIN_TYPE + focus ring (mismo estándar que cabina).
 * V2.43 — jerarquía ESTADO / ACCIÓN / CONFIRMACIÓN / RESULTADO · Arm ≠ autorización.
 * Frase exacta → tryArmAuto. Arm ≠ execute. No panel nuevo de Mercado.
 */

import { useCallback, useEffect, useState } from "react";
import {
  PAPER_AUTO_ARM_PERMISSION_LINE,
  PAPER_AUTO_ARM_STATE_DISARMED,
  PAPER_AUTO_EXECUTION_VENUE,
  PAPER_AUTO_ARMED_EXEC_OFF,
} from "@bolsa/shared";

import { cn } from "@/lib/utils";
import {
  AUTO_ARM_CONFIRM_PHRASE,
  loadAutoArm,
  tryArmAuto,
  type DemoBookAutoArm,
} from "@/features/trading/demo-book-auto-arm";
import {
  CABIN_TOUCH_TARGET,
  CABIN_TYPE,
} from "@/features/trading/cabin-visual";
import { CABIN_FOCUS_RING } from "@/features/trading/operator-cabin-ui";

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
        "space-y-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3",
        className,
      )}
      data-testid="demo-book-auto-arm-form"
    >
      <div className="space-y-1" data-testid="demo-book-auto-arm-hierarchy">
        <p className={cn(CABIN_TYPE.eyebrow, "text-foreground")}>Estado</p>
        <p
          className={cn(CABIN_TYPE.operativa, "font-semibold text-foreground")}
          data-testid="demo-book-auto-arm-estado"
        >
          {PAPER_AUTO_ARM_STATE_DISARMED}
        </p>
        <p className={cn(CABIN_TYPE.eyebrow, "pt-1 text-foreground")}>Acción</p>
        <p
          className={cn(CABIN_TYPE.operativa, "text-foreground")}
          data-testid="demo-book-auto-arm-accion"
        >
          Solicitar armado
        </p>
        <p className={cn(CABIN_TYPE.eyebrow, "pt-1 text-foreground")}>
          Confirmación
        </p>
        <p className={cn(CABIN_TYPE.meta, "leading-snug text-foreground")}>
          Escribe exactamente{" "}
          <span className="font-semibold text-foreground">
            {AUTO_ARM_CONFIRM_PHRASE}
          </span>
          .
        </p>
        <p className={cn(CABIN_TYPE.eyebrow, "pt-1 text-foreground")}>
          Resultado
        </p>
        <p
          className={cn(CABIN_TYPE.operativa, "font-semibold text-foreground")}
          data-testid="demo-book-auto-arm-resultado"
        >
          AUTO ARMADO — {PAPER_AUTO_EXECUTION_VENUE}
        </p>
        <p
          className={cn(CABIN_TYPE.meta, "leading-snug")}
          data-testid="demo-book-auto-arm-permission"
        >
          {PAPER_AUTO_ARM_PERMISSION_LINE}
        </p>
        <p
          className={cn(CABIN_TYPE.meta, "leading-snug text-muted-foreground")}
        >
          Arm ≠ execute — con env off verás «{PAPER_AUTO_ARMED_EXEC_OFF}».
        </p>
      </div>
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
        className={cn(
          CABIN_TOUCH_TARGET,
          CABIN_FOCUS_RING,
          CABIN_TYPE.operativa,
          "w-full justify-start rounded-md border border-border bg-background px-3 text-foreground",
        )}
      />
      {armError ? (
        <p
          className={cn(CABIN_TYPE.meta, "text-red-700 dark:text-red-300")}
          data-testid="demo-book-auto-arm-error"
        >
          {armError}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          data-testid="demo-book-auto-arm-confirm"
          onClick={() => confirmArm()}
          className={cn(
            CABIN_TOUCH_TARGET,
            CABIN_FOCUS_RING,
            CABIN_TYPE.meta,
            "rounded-md border border-emerald-500/60 bg-emerald-500/15 px-3 font-medium text-emerald-800 dark:text-emerald-300",
          )}
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
          className={cn(
            CABIN_TOUCH_TARGET,
            CABIN_FOCUS_RING,
            CABIN_TYPE.meta,
            "rounded-md border border-border px-3 text-muted-foreground hover:text-foreground",
          )}
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}
