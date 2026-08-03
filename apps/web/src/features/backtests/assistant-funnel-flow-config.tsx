/**
 * Configuración del Asistente como diagrama de flujo (⋯).
 *
 * 1 Probar genéricas → 2 Coach (ACK¹) → 3 Lab → 4 Revalidar (ACK final) → 5 Finalistas
 *
 * Los checks viven en las ramas; el layout explica el contrato del ciclo.
 */

import type { ReactNode } from 'react';
import type { AssistantPrefs } from '@/features/backtests/backtest-assistant-prefs';
import { cn } from '@/lib/utils';

type Props = {
  prefs: AssistantPrefs;
  onPrefsChange: (next: AssistantPrefs) => void;
};

function FlowCheck({
  checked,
  label,
  hint,
  onChange,
  muted,
}: {
  checked: boolean;
  label: string;
  hint?: string;
  onChange?: (next: boolean) => void;
  /** Rama fija de producto (no editable) */
  muted?: boolean;
}) {
  return (
    <label
      className={cn(
        'flex items-start gap-2 rounded-md px-1.5 py-1 text-[11px] leading-snug',
        muted
          ? 'cursor-default text-muted-foreground'
          : 'cursor-pointer text-foreground hover:bg-accent/60',
      )}
      title={hint}
    >
      <input
        type="checkbox"
        className="mt-0.5 shrink-0"
        checked={checked}
        disabled={muted || !onChange}
        onChange={onChange ? (e) => onChange(e.target.checked) : undefined}
      />
      <span>
        <span className="font-medium">{label}</span>
        {hint ? (
          <span className="mt-0.5 block text-[10px] font-normal text-muted-foreground">
            {hint}
          </span>
        ) : null}
      </span>
    </label>
  );
}

function StageCard({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border/80 bg-muted/20 p-2">
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-foreground">
        <span className="tabular-nums text-muted-foreground">{n}.</span> {title}
      </p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function Branch({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="ml-1 border-l-2 border-border/70 pl-2">
      <p className="mb-0.5 text-[10px] font-medium text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}

function Arrow({ note }: { note?: string }) {
  return (
    <div className="flex items-center gap-2 py-0.5 pl-2 text-[10px] text-muted-foreground">
      <span aria-hidden>↓</span>
      {note ? <span>{note}</span> : null}
    </div>
  );
}

/**
 * Diagrama editable del embudo. Sustituye la lista plana de prefs del ciclo.
 */
export function AssistantFunnelFlowConfig({ prefs, onPrefsChange }: Props) {
  const patchUniverse = (partial: Partial<AssistantPrefs['universe']>) =>
    onPrefsChange({ ...prefs, universe: { ...prefs.universe, ...partial } });
  const patchCoach = (partial: Partial<AssistantPrefs['coach']>) =>
    onPrefsChange({ ...prefs, coach: { ...prefs.coach, ...partial } });
  const patchSemifinal = (partial: Partial<AssistantPrefs['semifinal']>) =>
    onPrefsChange({ ...prefs, semifinal: { ...prefs.semifinal, ...partial } });

  return (
    <div className="max-h-[min(70vh,28rem)] space-y-0 overflow-y-auto px-2.5 py-1.5">
      <p className="mb-1.5 text-[10px] leading-snug text-muted-foreground">
        Marca las ramas del ciclo. Lista AUTO = el mismo diagrama × cada valor.
      </p>

      <FlowCheck
        checked={prefs.fullCycleOnPlay}
        label="Play = ciclo completo"
        hint="OFF → un paso por clic (sin embudo automático)."
        onChange={(v) => onPrefsChange({ ...prefs, fullCycleOnPlay: v })}
      />

      <StageCard n={1} title="Probar genéricas">
        <FlowCheck
          checked={prefs.universe.selectAllGenerics}
          label="Todas las genéricas"
          onChange={(v) => patchUniverse({ selectAllGenerics: v })}
        />
        <FlowCheck
          checked={prefs.universe.includeFinalistsInBattery}
          label="∪ Finalistas del valor"
          hint="Stress-test del TOP actual junto al catálogo."
          onChange={(v) => patchUniverse({ includeFinalistsInBattery: v })}
        />
        <FlowCheck
          checked={prefs.universe.includeOptimizedStrategies}
          label="Incluir Optimizadas"
          hint="Clones / Lab sobre genéricas (origin preset)."
          onChange={(v) => patchUniverse({ includeOptimizedStrategies: v })}
        />
        <FlowCheck
          checked={prefs.universe.includeMineStrategies}
          label="Incluir Mis estrategias"
          hint="Autoría propia (manual, prompt IA, asistida, import)."
          onChange={(v) => patchUniverse({ includeMineStrategies: v })}
        />
        <FlowCheck
          checked={prefs.universe.runCoachOnEnter}
          label="Probar + coach al entrar"
          onChange={(v) => patchUniverse({ runCoachOnEnter: v })}
        />
        <FlowCheck
          checked={prefs.universe.reuseLoteIfUnchanged}
          label="Reutilizar lote si no cambió"
          onChange={(v) => patchUniverse({ reuseLoteIfUnchanged: v })}
        />
        <FlowCheck
          checked={prefs.universe.skipFreshIfUnchanged}
          label="Omitir si Finalistas frescos"
          hint="Lista AUTO: no re-analiza el valor si la huella no cambió."
          onChange={(v) => patchUniverse({ skipFreshIfUnchanged: v })}
        />
      </StageCard>

      <Arrow note="análisis ★ + dual-audit" />

      <StageCard n={2} title="Coach · ACK¹">
        <p className="mb-1 px-1.5 text-[10px] leading-snug text-muted-foreground">
          Analiza el lote. Si hace falta ACK (débil / discrepancia), esa es la puerta al Lab.
        </p>
        <Branch label="Si hace falta ACK¹">
          <FlowCheck
            checked={prefs.coach.requireAckBeforeLab}
            label="Exigir ACK¹ para pasar las 3 al Lab"
            hint="ON (recomendado): sin ACK no hay Lab. Con Auto-ACK se marca solo; con Pausar esperas."
            onChange={(v) => patchCoach({ requireAckBeforeLab: v })}
          />
        </Branch>
        <Branch label="Si Coach¹ es débil">
          <FlowCheck
            checked={prefs.coach.labEvenIfWeak}
            label="Aun así permitir Lab"
            hint="OFF (default): débil → fin de ciclo, Finalistas intactos."
            onChange={(v) => patchCoach({ labEvenIfWeak: v })}
          />
        </Branch>
        <Branch label="Atajo (no predeterminado)">
          <FlowCheck
            checked={prefs.coach.saveSemifinalSkipLab}
            label="Guardar TOP semifinal · sin Lab"
            hint="Tras ACK¹ (o sin necesidad de ACK): escribe semifinal y cierra. No optimiza."
            onChange={(v) => patchCoach({ saveSemifinalSkipLab: v })}
          />
        </Branch>
        <FlowCheck
          checked={prefs.semifinal.optimizeTop3OnEnter}
          label="Pasar TOP-3 al Lab (si no hay atajo)"
          hint="En ciclo Play se fuerza Lab salvo el atajo semifinal."
          onChange={(v) => patchSemifinal({ optimizeTop3OnEnter: v })}
        />
        <FlowCheck
          checked={prefs.coach.llmNarrate}
          label="Narración LLM"
          onChange={(v) => patchCoach({ llmNarrate: v })}
        />
        <div className="flex items-center gap-2 px-1.5 py-1 text-[11px]">
          <span className="text-muted-foreground">Peso reciente ★</span>
          <select
            className="rounded border border-border bg-background px-1.5 py-0.5 text-[11px]"
            value={prefs.coach.futureWeight}
            onChange={(e) =>
              patchCoach({
                futureWeight: Number(e.target.value) as 0.3 | 0.42 | 0.55,
              })
            }
          >
            <option value={0.3}>0.30</option>
            <option value={0.42}>0.42</option>
            <option value={0.55}>0.55</option>
          </select>
        </div>
      </StageCard>

      <Arrow note="solo si ACK¹ OK (o no hacía falta)" />

      <StageCard n={3} title="Lab · optimizar TOP-3">
        <Branch label="Si mejoran (≥1 Mejor ≥ ancla)">
          <FlowCheck
            checked
            muted
            label="→ Revalidar (Coach²)"
            hint="Fijo: hace falta re-evaluar antes de Finalistas active."
          />
        </Branch>
        <Branch label="Si no mejoran">
          <FlowCheck
            checked
            muted
            label="No revalidar · no grabar · Finalistas intactos"
            hint="Política de producto: sin mejora Lab no se pisa el TOP active."
          />
        </Branch>
      </StageCard>

      <Arrow note="solo con mejora Lab" />

      <StageCard n={4} title="Revalidar · ACK final">
        <p className="mb-1 px-1.5 text-[10px] leading-snug text-muted-foreground">
          Coach de nuevo tras Lab. Este check es el único ACK final (no hay otro
          checkbox distinto en la pestaña Coach).
        </p>
        <FlowCheck
          checked={prefs.coach.autoAckOnCycle}
          label="ACK final automático → grabar en BD"
          hint="ON (predeterminado): en Revalidar verás «ACK final = config Asistente» y se escribe el TOP sin confirmar a mano."
          onChange={(v) => patchCoach({ autoAckOnCycle: v })}
        />
        <FlowCheck
          checked={prefs.coach.pauseIfAckNeeded}
          label="Pausar si hace falta ACK (revisión humana)"
          hint="OFF (predeterminado). ON = aparece el checkbox en Coach; el ciclo espera tu marca."
          onChange={(v) => patchCoach({ pauseIfAckNeeded: v })}
        />
        <Branch label="Tras ACK final / ciclo">
          <FlowCheck
            checked={prefs.coach.autoAckOnCycle && !prefs.coach.pauseIfAckNeeded}
            muted
            label="Grabar TOP-3 Finalistas en BD"
            hint="Con mejora Lab, o sin TOP previo (primera escritura). Si hay TOP y Lab no mejora → se conserva."
          />
        </Branch>
      </StageCard>

      <Arrow />

      <StageCard n={5} title="Finalistas">
        <FlowCheck
          checked={prefs.finalists.revalidateCoachOnEnter}
          label="Al abrir Finalistas: revalidar + coach"
          hint="Camino manual aparte del ciclo Play."
          onChange={(v) =>
            onPrefsChange({
              ...prefs,
              finalists: { ...prefs.finalists, revalidateCoachOnEnter: v },
            })
          }
        />
        <p className="px-1.5 pt-0.5 text-[10px] leading-snug text-muted-foreground">
          Checklist = paper (A) · Proponer = Supervisado F3 (C). Auto-paper D congelado.
        </p>
      </StageCard>
    </div>
  );
}
