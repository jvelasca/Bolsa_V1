# Resumen operativo diario — brief (2026-08-04)

> **Estado:** R1–R4 entregados (web · prefs · HTML email · PDF opt-in)  
> **Padres:** Canales Estudio · prefs notificación · telemetría A0 · SEMI Confirm  
> **Freeze:** no Camino D execute · PDF tipográfico avanzado fuera de alcance

## Objetivo

Informe del **día operativo** para gestionar SEMI: estado de cuenta, ops hechas, pendientes (F3 / Alarmas), Avisos, y evolución de la **semana en curso**. Preview en app; email opt-in al cierre; PDF adjunto/descarga opcional.

## Fases

| Fase | Entrega |
|------|---------|
| **R1** | `GET …/daily-ops-report` + tab Asesor **Diario** (HTML atractivo + sparklines) |
| **R2** | Pref `dailyDigestEnabled` (mismo correo Alarmas) |
| **R3** | Job EOD → HTML email · `POST …/daily-ops-report/email` · flag `DAILY_OPS_DIGEST_EMAIL_ENABLED` |
| **R4** | PDF adjunto opt-in · `GET …/daily-ops-report.pdf` · pref `dailyDigestPdfEnabled` |

## R3 — email

- Sibling de Alarmas tras `POST …/eod-batch` si `notifyDigestEnabled` + `accountId` + SMTP.
- Envío manual: `POST /api/accounts/{id}/daily-ops-report/email`.
- Destinatario = mismo `notifyEmail` / prefs Alarmas.
- HTML multipart + text/plain fallback (`daily_ops_digest_email.py`).
- Flags: `DAILY_OPS_DIGEST_EMAIL_ENABLED=false` (servidor); cliente `dailyDigestEnabled`.

## R4 — PDF

- Generador stdlib Helvetica (`daily_ops_digest_pdf.py`) — sin reportlab.
- Adjunto si `attachPdf` / `dailyDigestPdfEnabled` / `DAILY_OPS_DIGEST_PDF_ENABLED`.
- Descarga: `GET /api/accounts/{id}/daily-ops-report.pdf?asOf=&instrumentIds=`.
- Respuesta email incluye `pdfAttached`.

## Contrato R1 (payload)

Ver `packages/shared/src/daily-ops-report.ts` — `DailyOpsReportV1`.

Secciones UI:

1. Cabecera (asOf · cuenta · modo libro)  
2. Snapshot equity / cash / P&L / posiciones  
3. Operaciones del día (ledger buy/sell)  
4. Pendientes: F3 count · Alarmas · Avisos (si hay `instrumentIds` Estudio)  
5. Semana: barras actividad + sparkline balance_after  
6. CTA: Operativa / Opiniones · digest · PDF

## Momento de envío

Tras `eod-batch` · o botones **Enviar ahora** / **Descargar PDF** en Diario.

## Fuera de alcance

PDF tipográfico (brand fonts) · multiusuario buzón servidor · AUTO execute.
