import { useEffect, useMemo, useRef, useState } from 'react';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';

import { inputClassName } from '@/components/ui/dialog';
import { IconButton } from '@/components/ui/icon-button';
import {
  MONTH_LABELS_ES,
  WEEKDAY_LABELS_ES,
  addMonths,
  buildMonthGrid,
  formatDateInputValue,
  parseDateInputValue,
  type DateParts,
  type YearMonth,
} from '@/lib/datetime-input';
import { cn } from '@/lib/utils';

interface ExpiryDateTimeFieldProps {
  date: string;
  time: string;
  onDateChange: (value: string) => void;
  onTimeChange: (value: string) => void;
}

function isSameDay(a: DateParts | null, year: number, month: number, day: number): boolean {
  return Boolean(a && a.year === year && a.month === month && a.day === day);
}

function isToday(year: number, month: number, day: number): boolean {
  const now = new Date();
  return (
    now.getFullYear() === year && now.getMonth() === month && now.getDate() === day
  );
}

export function ExpiryDateTimeField({
  date,
  time,
  onDateChange,
  onTimeChange,
}: ExpiryDateTimeFieldProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const selected = parseDateInputValue(date);
  const [view, setView] = useState<YearMonth>(() => {
    const now = new Date();
    return selected
      ? { year: selected.year, month: selected.month }
      : { year: now.getFullYear(), month: now.getMonth() };
  });

  const grid = useMemo(() => buildMonthGrid(view.year, view.month), [view.month, view.year]);

  useEffect(() => {
    if (!calendarOpen) return;
    function onPointerDown(event: MouseEvent) {
      if (containerRef.current?.contains(event.target as Node)) return;
      setCalendarOpen(false);
    }
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [calendarOpen]);

  useEffect(() => {
    const parts = parseDateInputValue(date);
    if (!parts) return;
    setView({ year: parts.year, month: parts.month });
  }, [date]);

  function selectDay(day: number) {
    onDateChange(formatDateInputValue(new Date(view.year, view.month, day)));
    setCalendarOpen(false);
  }

  return (
    <div ref={containerRef} className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div className="flex min-w-0 items-center gap-1">
          <input
            type="date"
            className={cn(inputClassName, 'min-w-0 flex-1')}
            value={date}
            onChange={(event) => onDateChange(event.target.value)}
          />
          <IconButton
            icon={Calendar}
            title="Elegir fecha en calendario"
            active={calendarOpen}
            onClick={() => setCalendarOpen((open) => !open)}
          />
        </div>
        <input
          type="time"
          className={inputClassName}
          value={time}
          onChange={(event) => onTimeChange(event.target.value)}
        />
      </div>

      {calendarOpen && (
        <div className="rounded-md border border-border bg-muted/20 p-2">
          <div className="mb-2 flex items-center justify-between gap-1">
            <IconButton
              icon={ChevronLeft}
              title="Mes anterior"
              onClick={() => setView((current) => addMonths(current, -1))}
            />
            <span className="text-xs font-medium">
              {MONTH_LABELS_ES[view.month]} {view.year}
            </span>
            <IconButton
              icon={ChevronRight}
              title="Mes siguiente"
              onClick={() => setView((current) => addMonths(current, 1))}
            />
          </div>

          <div className="grid grid-cols-7 gap-0.5 text-center text-[10px] text-muted-foreground">
            {WEEKDAY_LABELS_ES.map((label) => (
              <span key={label} className="py-0.5 font-medium">
                {label}
              </span>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-0.5">
            {grid.map((day, index) =>
              day == null ? (
                <span key={`empty-${index}`} />
              ) : (
                <button
                  key={`${view.year}-${view.month}-${day}`}
                  type="button"
                  onClick={() => selectDay(day)}
                  className={cn(
                    'rounded py-1 text-[11px] tabular-nums transition-colors',
                    'hover:bg-accent hover:text-foreground',
                    isSameDay(selected, view.year, view.month, day) &&
                      'bg-primary text-primary-foreground hover:bg-primary',
                    !isSameDay(selected, view.year, view.month, day) &&
                      isToday(view.year, view.month, day) &&
                      'ring-1 ring-primary/50',
                  )}
                >
                  {day}
                </button>
              ),
            )}
          </div>
        </div>
      )}
    </div>
  );
}
