import type { IndicatorDefinition } from '@bolsa/shared';
import { normalizeParameters } from '@bolsa/shared';
import { inputClassName } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

export function IndicatorParametersForm({
  definition,
  values,
  onChange,
  className,
}: {
  definition: IndicatorDefinition;
  values: Record<string, number | boolean | string>;
  onChange: (next: Record<string, number | boolean | string>) => void;
  className?: string;
}) {
  if (definition.parameters.length === 0) {
    return (
      <p className={cn('text-xs text-muted-foreground', className)}>
        Este indicador no tiene parámetros configurables.
      </p>
    );
  }

  const grouped = new Map<string, typeof definition.parameters>();
  for (const param of definition.parameters) {
    const group = param.group ?? '';
    const list = grouped.get(group) ?? [];
    list.push(param);
    grouped.set(group, list);
  }

  function patchField(id: string, raw: unknown) {
    const next = normalizeParameters(definition, { ...values, [id]: raw });
    onChange(next);
  }

  return (
    <div className={cn('space-y-4', className)}>
      {[...grouped.entries()].map(([group, params]) => (
        <div key={group || 'default'} className="space-y-3">
          {group && (
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              {group}
            </p>
          )}
          {params.map((param) => (
            <label key={param.id} className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">{param.label}</span>
              {param.description && (
                <span className="text-[11px] text-muted-foreground/80">{param.description}</span>
              )}
              {param.type === 'number' && (
                <input
                  type="number"
                  min={param.min}
                  max={param.max}
                  step={param.step ?? 1}
                  className={inputClassName}
                  value={String(values[param.id] ?? param.default)}
                  onChange={(e) => patchField(param.id, e.target.value)}
                />
              )}
              {param.type === 'boolean' && (
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border accent-primary"
                  checked={Boolean(values[param.id] ?? param.default)}
                  onChange={(e) => patchField(param.id, e.target.checked)}
                />
              )}
              {param.type === 'color' && (
                <input
                  type="color"
                  className="h-9 w-full cursor-pointer rounded border border-border bg-background"
                  value={String(values[param.id] ?? param.default)}
                  onChange={(e) => patchField(param.id, e.target.value)}
                />
              )}
              {param.type === 'select' && (
                <select
                  className={inputClassName}
                  value={String(values[param.id] ?? param.default)}
                  onChange={(e) => patchField(param.id, e.target.value)}
                >
                  {(param.options ?? []).map((option) => (
                    <option key={String(option.value)} value={String(option.value)}>
                      {option.label}
                    </option>
                  ))}
                </select>
              )}
            </label>
          ))}
        </div>
      ))}
    </div>
  );
}
