/**
 * Asesor → Diario — resumen operativo del día (R1 preview) — slice A3.
 *
 * El panel solo compone: hero (`asesor-daily-hero.tsx`), canales del día
 * (`asesor-daily-channels.tsx`), semana (`asesor-week-chart.tsx`), actividad del
 * día y el envío al cierre. Sin cambio de comportamiento: mismos textos, mismos
 * `data-testid`.
 *
 * @see docs/engineering/daily-ops-report-brief-2026-08-04.md
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { DailyOpsReportV1 } from "@bolsa/shared";
import { api } from "@/lib/api";
import { formatPriceOrAbsent } from "@/features/charts/chart-utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { loadDemoBookPrefs } from "@/features/trading/demo-book-prefs";
import {
  isValidEmailLoose,
  notificationEmailReady,
} from "@/features/config/notification-prefs";
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";
import { useNotificationPrefsStore } from "@/stores/notification-prefs-store";
import { useAlertsStore } from "@/stores/alerts-store";
import { absentDataLabel } from "@/components/absent-data";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { TechnicalDetail } from "@/components/technical-detail";
import { AsesorDailyChannels } from "@/features/research/asesor-daily-channels";
import { AsesorDailyHero } from "@/features/research/asesor-daily-hero";
import {
  asDeclaredList,
  asDeclaredNumber,
} from "@/features/research/asesor-daily-ops-guards";
import { AsesorWeekChart } from "@/features/research/asesor-week-chart";

function todayIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function AsesorDailyOpsPanel({ className }: { className?: string }) {
  const {
    account,
    effectiveAccountId,
    isLoading: accountsLoading,
  } = useActiveAccount();
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
    refetchInterval: 5 * 60_000,
    staleTime: 60_000,
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

  // Payload parcial (H-22): cada colección se declara o se afirma, nunca se
  // convierte en `[]` — eso diría «cero» desde un hueco.
  const trades = asDeclaredList<DailyOpsReportV1["tradesToday"][number]>(
    report?.tradesToday,
  );
  const notes = asDeclaredList<string>(report?.notes);
  const f3Pending = asDeclaredNumber(report?.f3PendingCount);

  return (
    <div className={cn("space-y-4", className)} data-testid="asesor-daily-ops">
      {/* Hero */}
      <AsesorDailyHero
        accountName={account?.name}
        hasActiveAccount={Boolean(effectiveAccountId)}
        asOf={asOf}
        mode={book.mode}
        estudioCount={report?.estudioCount ?? studyIds.length}
        report={report}
        isLoading={reportQuery.isLoading || accountsLoading}
      />

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
                Trades {trades ? trades.length : absentDataLabel()}
              </span>
              <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-amber-900 dark:text-amber-200">
                F3 pendiente {f3Pending ?? absentDataLabel()}
              </span>
            </div>
            <TechnicalDetail testId="asesor-daily-ops-technical">
              <p>
                Movimientos registrados hoy:{" "}
                {asDeclaredList(report.ledgerToday)?.length ??
                  absentDataLabel()}
              </p>
            </TechnicalDetail>
            {!trades ? (
              <p className="text-xs text-muted-foreground">
                {absentDataLabel()} · el parte del día no trajo los movimientos.
              </p>
            ) : trades.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Sin compras/ventas registradas hoy.
              </p>
            ) : (
              <ul className="max-h-48 space-y-1.5 overflow-y-auto text-[11px]">
                {trades.map((t) => (
                  <li
                    key={t.id}
                    className="flex items-center justify-between gap-2 border-b border-border/50 py-1"
                  >
                    <span className="font-medium text-foreground">
                      {t.type.toUpperCase()}{" "}
                      {t.symbol ?? t.instrumentId ?? absentDataLabel()}
                    </span>
                    <span className="tabular-nums text-muted-foreground">
                      {t.quantity != null ? `${t.quantity} × ` : ""}
                      {formatPriceOrAbsent(t.price ?? t.amount)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <AsesorDailyChannels report={report} />

          <AsesorWeekChart
            week={asDeclaredList<DailyOpsReportV1["week"][number]>(report.week)}
          />

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
            {notes && notes.length > 0 ? (
              <ul className="mt-2 list-disc pl-4 text-[10px] text-muted-foreground">
                {notes.map((n) => (
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
