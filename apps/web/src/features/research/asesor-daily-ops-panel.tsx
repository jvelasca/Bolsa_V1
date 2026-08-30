/**
 * Asesor → Diario — resumen operativo del día (R1 preview).
 *
 * @see docs/engineering/daily-ops-report-brief-2026-08-04.md
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { DailyOpsReportV1, DailyOpsWeekDayV1 } from "@bolsa/shared";
import { api } from "@/lib/api";
import { formatPrice } from "@/features/charts/chart-utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { loadDemoBookPrefs } from "@/features/trading/demo-book-prefs";
import {
  isValidEmailLoose,
  notificationEmailReady,
} from "@/features/config/notification-prefs";
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";
import { useNotificationPrefsStore } from "@/stores/notification-prefs-store";
import { useAlertsStore } from "@/stores/alerts-store";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function todayIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function WeekActivityChart({ week }: { week: DailyOpsWeekDayV1[] }) {
  const maxT = Math.max(1, ...week.map((d) => d.tradeCount));
  const bals = week
    .map((d) => d.balanceAfter)
    .filter((v): v is number => v != null);
  const minB = bals.length ? Math.min(...bals) : 0;
  const maxB = bals.length ? Math.max(...bals) : 1;
  const span = Math.max(1e-6, maxB - minB);
  const w = 280;
  const h = 64;
  const pad = 4;
  const pts = week
    .map((d, i) => {
      if (d.balanceAfter == null) return null;
      const x = pad + (i / Math.max(1, week.length - 1)) * (w - pad * 2);
      const y = h - pad - ((d.balanceAfter - minB) / span) * (h - pad * 2);
      return `${x},${y}`;
    })
    .filter(Boolean)
    .join(" ");

  return (
    <div className="space-y-2">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-16 w-full"
        role="img"
        aria-label="Evolución semanal"
      >
        <defs>
          <linearGradient id="opsWeekFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(16 185 129)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="rgb(16 185 129)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {pts ? (
          <>
            <polyline
              fill="none"
              stroke="rgb(16 185 129)"
              strokeWidth="2"
              points={pts}
            />
          </>
        ) : null}
        {week.map((d, i) => {
          const x = pad + (i / Math.max(1, week.length - 1)) * (w - pad * 2);
          const barH = (d.tradeCount / maxT) * (h - 16);
          return (
            <rect
              key={d.date}
              x={x - 4}
              y={h - 8 - barH}
              width={8}
              height={Math.max(2, barH)}
              rx={1}
              className="fill-sky-500/50"
            />
          );
        })}
      </svg>
      <div className="flex justify-between text-[9px] tabular-nums text-muted-foreground">
        {week.map((d) => (
          <span key={d.date} className="w-8 text-center">
            {d.date.slice(8)}
          </span>
        ))}
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "neutral";
}) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 backdrop-blur-sm">
      <p className="text-[10px] uppercase tracking-wide text-white/60">
        {label}
      </p>
      <p
        className={cn(
          "mt-0.5 text-lg font-semibold tabular-nums text-white",
          tone === "pos" && "text-emerald-300",
          tone === "neg" && "text-rose-300",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export function AsesorDailyOpsPanel() {
  const { account, effectiveAccountId } = useActiveAccount();
  const entries = useEstudioMembershipStore((s) => s.members);
  const studyIds = useMemo(() => entries.map((e) => e.instrumentId), [entries]);
  const asOf = todayIso();
  const book = loadDemoBookPrefs();
  const digestEnabled = useNotificationPrefsStore((s) => s.dailyDigestEnabled);
  const digestPdfEnabled = useNotificationPrefsStore(
    (s) => s.dailyDigestPdfEnabled,
  );
  const alarmaEmail = useNotificationPrefsStore((s) => s.alarmaEmail);
  const alarmaEmailEnabled = useNotificationPrefsStore(
    (s) => s.alarmaEmailEnabled,
  );
  const alarmaToastEnabled = useNotificationPrefsStore(
    (s) => s.alarmaToastEnabled,
  );
  const operativaToastEnabled = useNotificationPrefsStore(
    (s) => s.operativaToastEnabled,
  );
  const setPrefs = useNotificationPrefsStore((s) => s.setPrefs);
  const pushToast = useAlertsStore((s) => s.pushToast);
  const [sending, setSending] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const emailReady = notificationEmailReady({
    alarmaToastEnabled,
    operativaToastEnabled,
    alarmaEmailEnabled,
    alarmaEmail,
    dailyDigestEnabled: digestEnabled,
    dailyDigestPdfEnabled: digestPdfEnabled,
  });
  const canSendDigest =
    Boolean(effectiveAccountId) &&
    digestEnabled &&
    isValidEmailLoose(alarmaEmail);

  const reportQuery = useQuery({
    queryKey: [
      "daily-ops-report",
      effectiveAccountId,
      asOf,
      studyIds.join(","),
    ],
    enabled: Boolean(effectiveAccountId),
    queryFn: () =>
      api.getDailyOpsReport(effectiveAccountId!, {
        asOf,
        instrumentIds: studyIds,
      }),
    refetchInterval: 60_000,
  });

  const healthQuery = useQuery({
    queryKey: ["api-health", "smtp"],
    queryFn: api.getHealth,
    staleTime: 60_000,
  });
  const smtpStatus = healthQuery.data?.components?.smtp?.status;
  /** null = aún no sabemos (health cargando / sin dato). */
  const smtpReady =
    smtpStatus == null
      ? null
      : smtpStatus === "configured" || smtpStatus === "ok";
  const smtpMessage = healthQuery.data?.components?.smtp?.message;

  const report: DailyOpsReportV1 | undefined = reportQuery.data?.data;
  const pnl = report?.summary.totalUnrealizedPnl;
  const pnlTone = pnl == null ? "neutral" : pnl >= 0 ? "pos" : "neg";

  return (
    <div className="space-y-4" data-testid="asesor-daily-ops">
      {/* Hero */}
      <section
        className="overflow-hidden rounded-xl border border-border"
        style={{
          background:
            "linear-gradient(135deg, #0f172a 0%, #134e4a 42%, #0c4a6e 78%, #1e1b4b 100%)",
        }}
      >
        <div className="space-y-3 p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-teal-200/80">
                Explica el día · no firma
              </p>
              <h2 className="font-serif text-2xl text-white sm:text-3xl">
                {account?.name ?? "Cuenta DEMO"}
              </h2>
              <p className="mt-1 text-sm text-white/70">
                {asOf} · modo {book.mode.toUpperCase()} · Estudio{" "}
                {report?.estudioCount ?? studyIds.length} valores
              </p>
              {report?.estudioStatus === "unavailable" ? (
                <p
                  className="mt-2 rounded-md border border-rose-400/40 bg-rose-950/40 px-2 py-1.5 text-xs text-rose-100"
                  data-testid="asesor-estudio-unavailable"
                >
                  Estudio no disponible — no se puede generar Daily Ops del
                  universo. Esto no significa «0 oportunidades».
                </p>
              ) : null}
              {report?.estudioStatus === "empty" ? (
                <p
                  className="mt-2 rounded-md border border-amber-400/40 bg-amber-950/40 px-2 py-1.5 text-xs text-amber-100"
                  data-testid="asesor-estudio-empty"
                >
                  Estudio vacío — 0 valores en el universo supervisado.
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Link
                to="/trading"
                className={cn(
                  buttonVariants({ variant: "outline", size: "sm" }),
                  "h-7 border-white/30 bg-transparent text-[11px] text-white hover:bg-white/10",
                )}
              >
                Ver en Mercado
              </Link>
              <Link
                to="/research?tab=opiniones"
                className={cn(
                  buttonVariants({ variant: "outline", size: "sm" }),
                  "h-7 border-white/30 bg-transparent text-[11px] text-white hover:bg-white/10",
                )}
              >
                Opiniones
              </Link>
            </div>
          </div>
          {report ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Kpi
                label="Equity"
                value={formatPrice(report.summary.totalEquity)}
              />
              <Kpi label="Cash" value={formatPrice(report.summary.cash)} />
              <Kpi
                label="P&L latente"
                value={formatPrice(report.summary.totalUnrealizedPnl)}
                tone={pnlTone}
              />
              <Kpi
                label="Posiciones"
                value={String(report.summary.positionsCount)}
              />
            </div>
          ) : (
            <p className="text-sm text-white/70">
              {reportQuery.isLoading
                ? "Generando resumen…"
                : "Selecciona una cuenta DEMO activa."}
            </p>
          )}
        </div>
      </section>

      {reportQuery.isError ? (
        <p className="text-sm text-destructive">
          No se pudo cargar el resumen. Revisa la API.
        </p>
      ) : null}

      {report ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Hoy */}
          <section className="space-y-3 rounded-xl border border-border bg-card p-4">
            <h3 className="text-sm font-semibold text-foreground">
              Actividad del día (lectura)
            </h3>
            <div className="flex flex-wrap gap-3 text-[11px]">
              <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-sky-800 dark:text-sky-200">
                Trades {report.tradesToday.length}
              </span>
              <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">
                Ledger {report.ledgerToday.length}
              </span>
              <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-amber-900 dark:text-amber-200">
                F3 pendiente {report.f3PendingCount}
              </span>
            </div>
            {report.tradesToday.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Sin compras/ventas registradas hoy.
              </p>
            ) : (
              <ul className="max-h-48 space-y-1.5 overflow-y-auto text-[11px]">
                {report.tradesToday.map((t) => (
                  <li
                    key={t.id}
                    className="flex items-center justify-between gap-2 border-b border-border/50 py-1"
                  >
                    <span className="font-medium text-foreground">
                      {t.type.toUpperCase()} {t.symbol ?? t.instrumentId ?? "—"}
                    </span>
                    <span className="tabular-nums text-muted-foreground">
                      {t.quantity != null ? `${t.quantity} × ` : ""}
                      {t.price != null
                        ? formatPrice(t.price)
                        : formatPrice(t.amount)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Canales */}
          <section className="space-y-3 rounded-xl border border-border bg-card p-4">
            <h3 className="text-sm font-semibold text-foreground">
              Canales Estudio
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3">
                <p className="text-[10px] uppercase text-rose-800/80 dark:text-rose-200/80">
                  Alarmas
                </p>
                <p className="text-2xl font-semibold tabular-nums text-rose-700 dark:text-rose-300">
                  {report.channels.alarma}
                </p>
              </div>
              <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-3">
                <p className="text-[10px] uppercase text-sky-800/80 dark:text-sky-200/80">
                  Avisos
                </p>
                <p className="text-2xl font-semibold tabular-nums text-sky-700 dark:text-sky-300">
                  {report.channels.aviso}
                </p>
              </div>
            </div>
            {report.opinions.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Sin dictámenes para el Estudio en esta fecha. Genera en
                Opiniones o EOD force.
              </p>
            ) : (
              <ul className="max-h-40 space-y-1 overflow-y-auto text-[11px]">
                {report.opinions
                  .filter(
                    (o) => o.channel === "alarma" || o.channel === "aviso",
                  )
                  .slice(0, 12)
                  .map((o) => (
                    <li
                      key={o.instrumentId}
                      className="flex justify-between gap-2 border-b border-border/40 py-1"
                    >
                      <span>
                        <span
                          className={cn(
                            "mr-1.5 rounded px-1 text-[9px] uppercase",
                            o.channel === "alarma"
                              ? "bg-rose-500/20 text-rose-800 dark:text-rose-200"
                              : "bg-sky-500/20 text-sky-800 dark:text-sky-200",
                          )}
                        >
                          {o.channel}
                        </span>
                        {o.symbol ?? o.instrumentId.slice(0, 8)}
                      </span>
                      <span className="tabular-nums text-muted-foreground">
                        {"★".repeat(Math.max(0, Math.min(5, o.dictamenStars)))}
                      </span>
                    </li>
                  ))}
              </ul>
            )}
          </section>

          {/* Semana */}
          <section className="space-y-2 rounded-xl border border-border bg-card p-4 lg:col-span-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-foreground">
                Semana en curso
              </h3>
              <p className="text-[10px] text-muted-foreground">
                Barras = trades · línea = balance ledger
              </p>
            </div>
            <WeekActivityChart week={report.week} />
          </section>

          {/* Digest CTA */}
          <section className="rounded-xl border border-dashed border-border bg-muted/20 p-4 lg:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-foreground">
                  Envío al cierre (R3/R4)
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  HTML por email tras eod-batch (mismo correo de Alarmas). PDF
                  adjunto opcional. Requiere SMTP en el servidor. También puedes
                  enviar o descargar ahora.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={digestEnabled}
                    onChange={(e) =>
                      setPrefs({ dailyDigestEnabled: e.target.checked })
                    }
                    className="h-3.5 w-3.5 accent-primary"
                  />
                  Quiero el resumen diario
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={digestPdfEnabled}
                    disabled={!digestEnabled}
                    onChange={(e) =>
                      setPrefs({ dailyDigestPdfEnabled: e.target.checked })
                    }
                    className="h-3.5 w-3.5 accent-primary"
                  />
                  Adjuntar PDF
                </label>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px]"
                  disabled={!effectiveAccountId || downloadingPdf}
                  onClick={() => {
                    if (!effectiveAccountId) return;
                    setDownloadingPdf(true);
                    void api
                      .downloadDailyOpsDigestPdf(effectiveAccountId, {
                        asOf,
                        instrumentIds: studyIds,
                      })
                      .then((blob) => {
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `bolsa-resumen-operativo-${asOf}.pdf`;
                        a.click();
                        URL.revokeObjectURL(url);
                        pushToast("PDF descargado");
                      })
                      .catch((e: Error) => pushToast(`PDF · ${e.message}`))
                      .finally(() => setDownloadingPdf(false));
                  }}
                >
                  {downloadingPdf ? "PDF…" : "Descargar PDF"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px]"
                  disabled={!canSendDigest || sending || smtpReady === false}
                  title={
                    !digestEnabled
                      ? "Activa la suscripción"
                      : !isValidEmailLoose(alarmaEmail)
                        ? "Configura un correo en Notificaciones"
                        : smtpReady === false
                          ? (smtpMessage ??
                            "SMTP incompleto en el servidor (.env: SMTP_HOST + SMTP_FROM)")
                          : "POST …/daily-ops-report/email"
                  }
                  onClick={() => {
                    if (!effectiveAccountId) return;
                    if (smtpReady === false) {
                      pushToast(
                        smtpMessage ??
                          "SMTP incompleto en el servidor. Añade SMTP_HOST y SMTP_FROM al .env y reinicia la API.",
                      );
                      return;
                    }
                    setSending(true);
                    void api
                      .sendDailyOpsDigestEmail(effectiveAccountId, {
                        asOf,
                        instrumentIds: studyIds,
                        notifyEmail: alarmaEmail.trim() || null,
                        notifyDigestEnabled: true,
                        attachPdf: digestPdfEnabled,
                      })
                      .then((res) => {
                        const d = res.data;
                        if (d.sent) {
                          pushToast(
                            d.pdfAttached
                              ? `Digest+PDF enviado · ${d.asOf ?? asOf}`
                              : `Digest enviado · ${d.asOf ?? asOf}`,
                          );
                        } else {
                          const reason = d.skippedReason ?? "desconocido";
                          pushToast(
                            reason.includes("SMTP")
                              ? `Digest · ${reason}. Revisa .env (SMTP_HOST / SMTP_FROM) y reinicia la API.`
                              : `Digest skip (${reason})`,
                          );
                        }
                      })
                      .catch((e: Error) => pushToast(`Digest · ${e.message}`))
                      .finally(() => setSending(false));
                  }}
                >
                  {sending ? "Enviando…" : "Enviar ahora"}
                </Button>
              </div>
            </div>
            {smtpReady === false ? (
              <p className="mt-2 text-[10px] text-amber-700 dark:text-amber-300">
                {smtpMessage ??
                  "SMTP incompleto en el servidor. En `.env`: SMTP_HOST, SMTP_FROM (y opcional SMTP_USER / SMTP_PASSWORD / SMTP_PORT). Luego reinicia la API."}
              </p>
            ) : null}
            {!emailReady && digestEnabled ? (
              <p className="mt-2 text-[10px] text-amber-700 dark:text-amber-300">
                Activa email de Alarmas y un correo válido en Configuración →
                Notificaciones (mismo buzón para el digest).
              </p>
            ) : null}
            {report.notes.length > 0 ? (
              <ul className="mt-2 list-disc pl-4 text-[10px] text-muted-foreground">
                {report.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            ) : null}
          </section>
        </div>
      ) : null}
    </div>
  );
}
