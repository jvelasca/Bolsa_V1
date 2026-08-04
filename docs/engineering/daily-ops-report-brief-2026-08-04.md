# Resumen operativo diario — brief (2026-08-04)

> **Estado:** R1 entregado (vista web + API) · R2 prefs stub · R3 email EOD pendiente  
> **Padres:** Canales Estudio · prefs notificación · telemetría A0 · SEMI Confirm  
> **Freeze:** no Camino D execute · no PDF tipográfico en R1
## Objetivo

Informe del **día operativo** para gestionar SEMI: estado de cuenta, ops hechas, pendientes (F3 / Alarmas), Avisos, y evolución de la **semana en curso**. Preview en app; email opt-in al cierre (R3).

## Fases

| Fase | Entrega |
|------|---------|
| **R1** | `GET …/daily-ops-report` + tab Asesor **Diario** (HTML atractivo + sparklines) |
| **R2** | Pref `dailyDigestEnabled` (mismo correo Alarmas) |
| **R3** | Job EOD → HTML email (+ PDF adjunto opcional R4) |

## Contrato R1 (payload)

Ver `packages/shared/src/daily-ops-report.ts` — `DailyOpsReportV1`.

Secciones UI:

1. Cabecera (asOf · cuenta · modo libro)  
2. Snapshot equity / cash / P&L / posiciones  
3. Operaciones del día (ledger buy/sell)  
4. Pendientes: F3 count · Alarmas · Avisos (si hay `instrumentIds` Estudio)  
5. Semana: barras actividad + sparkline balance_after  
6. CTA: abrir Operativa / Opiniones · suscripción digest (R2)

## Momento de envío (R3)

Tras cierre del mercado de los símbolos operados / Estudio — enganchar al pipeline EOD dictámenes (`eod-batch`), flag off-by-default.

## Fuera de R1

PDF · SMTP digest · AUTO execute · multiusuario buzón servidor.
