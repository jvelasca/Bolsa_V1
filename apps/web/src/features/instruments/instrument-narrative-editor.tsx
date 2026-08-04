/**
 * Editor de narrativa de evolución (≤20 líneas) en detalle Instrumentos.
 */

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  INSTRUMENT_NARRATIVE_MAX_CHARS,
  INSTRUMENT_NARRATIVE_MAX_LINES,
  countNarrativeLines,
  isInstrumentNarrativeFresh,
  validateInstrumentNarrativeBody,
  type InstrumentNarrativeScope,
  type InstrumentNarrativeSource,
} from '@bolsa/shared';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const SCOPE_OPTIONS: Array<{ id: InstrumentNarrativeScope; label: string }> = [
  { id: 'estudio', label: 'Estudio' },
  { id: 'trading', label: 'Trading' },
  { id: 'global', label: 'Global' },
];

export function InstrumentNarrativeEditor({
  instrumentId,
  className,
}: {
  instrumentId: string;
  className?: string;
}) {
  const qc = useQueryClient();
  const [scope, setScope] = useState<InstrumentNarrativeScope>('estudio');
  const [body, setBody] = useState('');
  const [source, setSource] = useState<InstrumentNarrativeSource>('user');
  const [dirty, setDirty] = useState(false);

  const query = useQuery({
    queryKey: ['instrument-narrative', instrumentId, scope],
    queryFn: () => api.getInstrumentNarrative(instrumentId, scope),
    staleTime: 30_000,
  });

  useEffect(() => {
    if (dirty) return;
    const data = query.data?.data;
    setBody(data?.body ?? '');
    setSource(data?.source ?? 'user');
  }, [query.data, dirty]);

  useEffect(() => {
    setDirty(false);
  }, [instrumentId, scope]);

  const save = useMutation({
    mutationFn: () =>
      api.upsertInstrumentNarrative(instrumentId, { scope, body, source }),
    onSuccess: (res) => {
      qc.setQueryData(['instrument-narrative', instrumentId, scope], res);
      setDirty(false);
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteInstrumentNarrative(instrumentId, scope),
    onSuccess: () => {
      qc.setQueryData(['instrument-narrative', instrumentId, scope], { data: null });
      setBody('');
      setDirty(false);
    },
  });

  const validation = validateInstrumentNarrativeBody(body);
  const lines = countNarrativeLines(body);
  const saved = query.data?.data;
  const fresh = saved ? isInstrumentNarrativeFresh(saved.updatedAt) : false;

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex flex-wrap items-center gap-1">
        {SCOPE_OPTIONS.map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => setScope(opt.id)}
            className={cn(
              'rounded-md border px-2 py-0.5 text-[10px] font-medium transition-colors',
              scope === opt.id
                ? 'border-primary/50 bg-primary/10 text-primary'
                : 'border-border text-muted-foreground hover:bg-accent',
            )}
          >
            {opt.label}
          </button>
        ))}
        <select
          value={source}
          onChange={(e) => {
            setSource(e.target.value as InstrumentNarrativeSource);
            setDirty(true);
          }}
          className="ml-auto rounded border border-border bg-background px-1.5 py-0.5 text-[10px]"
          title="Origen de la nota"
        >
          <option value="user">Usuario</option>
          <option value="ai">IA</option>
          <option value="system">Sistema</option>
        </select>
      </div>

      <textarea
        value={body}
        onChange={(e) => {
          setBody(e.target.value);
          setDirty(true);
        }}
        rows={8}
        placeholder="Resumen corto de la evolución (máx. 20 líneas). Útil para ti y como contexto a la IA."
        className="w-full resize-y rounded-md border border-border bg-background px-2 py-1.5 text-[11px] leading-relaxed outline-none ring-primary focus:ring-1"
        aria-label="Narrativa de evolución"
      />

      <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
        <span
          className={cn(
            !validation.ok && 'text-destructive',
            validation.ok && lines >= INSTRUMENT_NARRATIVE_MAX_LINES - 2 && 'text-amber-700',
          )}
        >
          {lines}/{INSTRUMENT_NARRATIVE_MAX_LINES} líneas · {body.length}/
          {INSTRUMENT_NARRATIVE_MAX_CHARS} chars
        </span>
        {saved ? (
          <span title={saved.updatedAt}>
            v{saved.version}
            {fresh ? ' · fresco' : ' · caduco p/ IA'}
          </span>
        ) : (
          <span>Sin nota guardada</span>
        )}
        {validation.error ? (
          <span className="text-destructive">{validation.error}</span>
        ) : null}
        {save.isError ? (
          <span className="text-destructive">No se pudo guardar</span>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Button
          type="button"
          size="sm"
          className="h-7 text-[11px]"
          disabled={!dirty || !validation.ok || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? 'Guardando…' : 'Guardar'}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[11px]"
          disabled={!saved || remove.isPending}
          onClick={() => remove.mutate()}
        >
          Borrar
        </Button>
      </div>
    </div>
  );
}
