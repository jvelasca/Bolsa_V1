/**
 * Poller: dictámenes Estudio → toast cuando aparecen Alarmas nuevas.
 * Montado en PlatformShell (junto al Radar inbox poller).
 */

import { useEffect, useMemo, useRef } from "react";
import {
  INSTRUMENT_DAILY_OPINION_STANCE_LABELS,
  mapOpinionToChannel,
} from "@bolsa/shared";
import { useInstrumentDailyOpinions } from "@/features/trading/use-instrument-daily-opinions";
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";
import { useAlertsStore } from "@/stores/alerts-store";
import { useNotificationPrefsStore } from "@/stores/notification-prefs-store";

const SEEN_KEY = "bolsa-estudio-alarma-seen-v1";
const POLL_MS = 60_000;

function loadSeen(): Set<string> {
  try {
    const raw = sessionStorage.getItem(SEEN_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return new Set();
    return new Set(arr.filter((x): x is string => typeof x === "string"));
  } catch {
    return new Set();
  }
}

function saveSeen(seen: Set<string>): void {
  try {
    sessionStorage.setItem(SEEN_KEY, JSON.stringify([...seen].slice(-200)));
  } catch {
    /* ignore */
  }
}

function fingerprint(
  instrumentId: string,
  asOf: string,
  stance: string,
  stars: number,
): string {
  return `${instrumentId}|${asOf}|${stance}|${stars}`;
}

export function EstudioOpinionAlarmPoller() {
  // Selector estable: no devolver .map() desde Zustand (rompe Object.is → loop).
  const entries = useEstudioMembershipStore((s) => s.members);
  const studyIds = useMemo(() => entries.map((e) => e.instrumentId), [entries]);
  const pushToast = useAlertsStore((s) => s.pushToast);
  const alarmaToastEnabled = useNotificationPrefsStore(
    (s) => s.alarmaToastEnabled,
  );
  const seenRef = useRef<Set<string> | null>(null);
  const primedRef = useRef(false);

  const opinionsQuery = useInstrumentDailyOpinions(studyIds, [], {
    enabled: studyIds.length > 0 && alarmaToastEnabled,
    refetchInterval: alarmaToastEnabled ? POLL_MS : false,
  });

  useEffect(() => {
    if (!alarmaToastEnabled) return;
    if (seenRef.current == null) seenRef.current = loadSeen();
    const data = opinionsQuery.data;
    if (!data?.length) return;

    const symbolById = new Map(entries.map((e) => [e.instrumentId, e.symbol]));
    const seen = seenRef.current;
    const fresh: Array<{
      symbol: string;
      stance: string;
      stars: number;
      key: string;
    }> = [];

    for (const op of data) {
      if (mapOpinionToChannel(op) !== "alarma") continue;
      const key = fingerprint(
        op.instrumentId,
        op.asOfBarDate,
        op.stance,
        op.dictamenStars,
      );
      if (seen.has(key)) continue;
      fresh.push({
        key,
        symbol: symbolById.get(op.instrumentId) ?? op.instrumentId.slice(0, 8),
        stance: INSTRUMENT_DAILY_OPINION_STANCE_LABELS[op.stance] ?? op.stance,
        stars: op.dictamenStars,
      });
    }

    if (!primedRef.current) {
      // Primera pasada: marcar como vistas (no spamear al abrir la app).
      for (const f of fresh) seen.add(f.key);
      saveSeen(seen);
      primedRef.current = true;
      return;
    }

    if (fresh.length === 0) return;

    for (const f of fresh) seen.add(f.key);
    saveSeen(seen);

    const head = fresh
      .slice(0, 3)
      .map((f) => `${f.symbol} ${f.stance} ★${f.stars}`)
      .join(" · ");
    const more = fresh.length > 3 ? ` (+${fresh.length - 3})` : "";
    pushToast(
      `Asesor · ${fresh.length} alarma${fresh.length === 1 ? "" : "s"}: ${head}${more}`,
      {
        action: { type: "open_asesor_opiniones", label: "Ver Opiniones" },
      },
    );
  }, [alarmaToastEnabled, opinionsQuery.data, entries, pushToast]);

  return null;
}
