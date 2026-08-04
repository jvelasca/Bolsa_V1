# Resumen operativo diario — brief (2026-08-04)

> **Estado:** R1+R2+R3 entregados (web · prefs · HTML email EOD) · R4 PDF opcional  
> **Padres:** Canales Estudio · prefs notificación · telemetría A0 · SEMI Confirm  
> **Freeze:** no Camino D execute · no PDF tipográfico en R3
## Objetivo

Informe del **día operativo** para gestionar SEMI: estado de cuenta, ops hechas, pendientes (F3 / Alarmas), Avisos, y evolución de la **semana en curso**. Preview en app; email opt-in al cierre (R3).

## Fases

| Fase | Entrega |
|------|---------|
| **R1** | `GET …/daily-ops-report` + tab Asesor **Diario** (HTML atractivo + sparklines) |
| **R2** | Pref `dailyDigestEnabled` (mismo correo Alarmas) |
| **R3** | Job EOD → HTML email · `POST …/daily-ops-report/email` · flag `DAILY_OPS_DIGEST_EMAIL_ENABLED` |
| **R4** | PDF adjunto opcional |

## R3 — email

- Sibling de Alarmas tras `POST …/eod-batch` si `notifyDigestEnabled` + `accountId` + SMTP.
- Envío manual: `POST /api/accounts/{id}/daily-ops-report/email`.
- Destinatario = mismo `notifyEmail` / prefs Alarmas.
- HTML multipart + text/plain fallback (`daily_ops_digest_email.py`).
- Flags: `DAILY_OPS_DIGEST_EMAIL_ENABLED=false` (servidor); cliente `dailyDigestEnabled`.

Ver `packages/shared/src/daily-ops-report.ts` — `DailyOpsReportV1`.

Secciones UI:

1. Cabecera (asOf · cuenta · modo libro)  
2. Snapshot equity / cash / P&L / posiciones  
3. Operaciones del día (ledger buy/sell)  
4. Pendientes: F3 count · Alarmas · Avisos (si hay `instrumentIds` Estudio)  
5. Semana: barras actividad + sparkline balance_after  
6. CTA: abrir Operativa / Opiniones · suscripción digest (R2)

## Momento de envío (R3)

Tras `eod-batch` (manual force o cron cuando `ESTUDIO_EOD_OPINION_ENABLED`) · o botón **Enviar ahora** en Diario.

## Fuera de alcance

PDF tipográfico · multiusuario buzón servidor · AUTO execute.
