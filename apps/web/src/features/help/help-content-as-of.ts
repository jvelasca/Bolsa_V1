/**
 * Fecha única de sync Ayuda ↔ trackers ↔ encabezados de docs.
 * Actualizar al cambiar estado de producto (no tipografía).
 *
 * Incluye: espacios, BD, perfiles, listas/índices, embudo Play,
 * Finalistas→A/C, Monitor MVP, CORE-P, CORE-R **v1.12** (BD + cron off + toast remoto),
 * **Backtesting DÍA D** (v0.11 · archivo también en Ayuda),
 * Lista AUTO frescura **v1.3**, CORE-B **v0.2**, CAPM Tarjeta v0,
 * Composite **v1.1**, fix Trading fullBleed,
 * **ADR-019** dos universos LAB vs TRADING (U1–U5).
 * **ADR-020** Mandato operativo (M0–M3 + **M1b BD** · tenure + trades + churn + sync).
 * **ADR-021** Reconciliación DÍA D (F-hoy · F-D · V · SAME/DRIFT · contrafactual).
 * Continuidad Verify (lookback + carry) · higiene `strategyType` Finalistas.
 * Post-auditorías Q0–Q3 + Q1.6 warm-up + estabilidad IBEX (Gate C4 cerrado).
 * **2026-08-04** — Panel **Operativa** + lista **Estudio** (membresía · bulk · gate SEMI/AUTO)
 * + Chart TOP#1 switches · **A1–A5 prep** Libro AUTO / kill switch / ADR-023 Proposed.
 * Pack auditoría: `docs/engineering/audit-pack-pre-auto-a0-a5-2026-08-04.md`.
 * HELP.md sync Trading SEMI vs AUTO · Asesor Diario R1 · telemetría.
 * **2026-08-06** — **ADR-024** Estudio canónica + Supervisión ON + cadencias 3 capas
 * (vigilia / frescura / rediscubrimiento) · «Eliminar de la lista».
 * **2026-08-06b** — UI procesos (subtítulo V·F·R · Actualizar/Redescubrir) ·
 * Manual/SEMI/AUTO en barra de estado → Cuentas (fuera del panel Operativa por valor).
 * **2026-08-06c** — Actualizar/Redescubrir solo barra inferior · chips cadencia V·F·R en banner.
 * **2026-08-06d** — Visualizados = pestañas · Por IO · columnas recomendación ·
 * foco Cartera→Estudio→resto + scroll bajo cabecera sticky.
 * **2026-08-21** — **R-12 Track C · C5** HELP sync: Confirm primer nivel (`/confirm`) ·
 * Señales/Libro en mesa · AUTO cuenta entonces «No disponible (BETA)» (supersedido 2026-08-25 BETA-D) · frase SEMI trader.
 * **2026-08-24** — Ayuda → **Flujo y módulos** (universos LAB/TRADING · ciclo
 * investigación→operación · mapa de módulos para usuario básico).
 * **2026-08-24b** — U1 Ayuda de mesa: bloque **«Hoy en la mesa»** (Guía + Flujo)
 * · coach-marks `MesaTipButton` (Proponer F3 · Confirmar · Recomendación).
 * **2026-08-24c** — U3 Confirmar **panel lateral** desde Operativa / chip F3
 * (mismo SEMI; `/confirm` sigue como página completa).
 * **2026-08-25** — v1.8.0-beta: AUTO UI BETA-D (`ACTIVAR AUTO` + `PAPER_D_EXECUTE`
 * opt-in) · Decision Spine (tesis ≠ plan ≠ permiso) · TradePlan · tira Hoy
 * (proyección; sin plan → WATCH, nunca BUY) · advisory Thesis Health / Exit /
 * Bracket ≠ permiso. Ciclo C1 HELP sync.
 * **2026-08-25b** — F1 TradePlan v1: T1/T2 / R/R en el plan ≠ permiso.
 * **2026-08-25c** — F2 PositionState: posición abierta ≠ TradePlan; thin ≠ PositionState.
 * **2026-08-25d** — F2.1: OPEN/PARTIAL/PROTECTED/CLOSED; mark/reduce ≠ orden.
 * **2026-08-25e** — F3 ExitPlan: razones canónicas ≠ auto-exit; thin «Salida» ≠ ExitPlan.
 * **2026-08-25f** — F4 ExecutionPlan PAPER: plan de envío ≠ broker ≠ ExecuteTrade.
 * **2026-08-25g** — ExitPermission: veto salida ≠ check_opening ≠ auto-exit.
 * **2026-08-25h** — H1: orden pendiente a precio ≠ stop de posición (ADR-033).
 * **2026-08-25i** — H2: kill switch bloquea aperturas/AUTO; SEMI desriesgo humano permitido.
 * **2026-08-25j** — P1: tras fill, Operaciones muestra stop/T1/T2 del plan persistido; holding ≠ plan.
 * **2026-08-25k** — P2: al firmar, el tamaño es el riesgo del TradePlan, no % caja; override con motivo.
 * **2026-08-25l** — P3: cadena de salida ExitPlan → ExitPermission → SEMI; Lab/thin «Salida» ≠ puerto; no auto-exit CTA.
 * **2026-08-25m** — P4.1: Operaciones posiciones primero; CTAs → Confirm; cola entradas read-only; «No operar» → Journal.
 * **2026-08-25n** — P4.2: barra estado global; filtros cola entradas; Proteger + override stop en Confirm.
 * **2026-08-26** — OI-1: manual HTTP/pending alinean ledger↔PositionState; Confirm no miente post-fill;
 * Proteger persiste stop operativo (≠ broker); origen manual honesto en Operaciones.
 * **2026-08-26b** — OI-2: apertura SEMI exige TradePlan TRIGGERED en firma de riesgo;
 * sin plan → bloqueo `no_tradeplan` (manual HTTP sin cambio).
 * **2026-08-26c** — OI-3: excepción de execute → UNKNOWN (nunca ERROR ni
 * «no se ejecutó»); ExecutionRecord ≠ ExecutionPlan.
 * **2026-08-26d** — OI-4: PaperOrder CREATED→FILLED; orden creada ≠ fill;
 * venue PAPER (≠ broker).
 * **2026-08-26e** — OI-5: PositionRevision historia auditada de stop/status;
 * Proteger deja huella en snapshot (≠ reconciliación).
 * **2026-08-26f** — OI-6: PortfolioReconciliation detect/report
 * (cash/holdings/PositionState); no auto-heal · ≠ broker · ≠ ADR-021.
 * **2026-08-26g** — PaperBroker: venue PAPER (CREATED→fill→FILLED) antes de
 * BrokerAdapter; ≠ broker live · ≠ IBrokerAdapter.
 * **2026-08-26h** — BrokerAdapter: puerto Paper | Live; mesa usa paper
 * (PaperBroker). Mock live = no envío (`not_wired`) ≠ broker live.
 * **2026-08-26i** — PH-1: Proteger con persist None (H2) no dice
 * `protect_applied`; stop no cambió.
 * **2026-08-26j** — XL-1: XtbBrokerAdapter LIVE vía bridge; rejected/submitted
 * ≠ fill ledger; mock bridge fail-closed; ≠ thaw.
 * **2026-08-26k** — LR-1: LiveLedgerReconciliation live↔ledger detect/report;
 * sin bridge → unavailable (no clean falso); ≠ OI-6 paper interno.
 * **2026-08-26l** — XL-2: bridge filled → execute_trade ledger; submitted
 * sigue ≠ fill; boom → UNKNOWN.
 * **2026-08-26m** — VS-1: mesa Paper|Live (BROKER_VENUE + toggle); default
 * paper; Live sin URL → not_wired; ≠ thaw PAPER_D_EXECUTE.
 * **2026-08-26n** — OE-1: Autoeval SEMI·AUTO (barra + GET /risk/ops-self-eval);
 * measure ≠ Accept estricto · ≠ flip env.
 * **2026-08-26o** — OR-4: recon drift / live unavailable → DENY aperturas;
 * exits protectivos ALLOW; sin auto-heal.
 * **2026-08-26p** — OR-6: readiness PAPER_READY / PAPER_DEGRADED /
 * LIVE_EXPERIMENTAL / LIVE_BLOCKED (sin %); CTA Ejecutar en PAPER|LIVE.
 * **2026-08-27** — V1.20 ADR-040: nav L1 Hoy·Mercado·Cartera·Asesor·Laboratorio;
 * strip Hoy y MesaOperationalBar fuera del terminal Mercado; Spine/Consola/
 * Journal/Libro no son puertas L1; OpportunityScore aparcado.
 *
 * Auditoría cierre: `docs/engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md`
 *
 * Track FA / FIE (2026-08-01): valoración cerrada en código
 * F0–F2.8 + F3 Composite + F4 Screener + Paper D + cron FA→D ·
 * Beneish→distress · Tarjeta densificada · CAPM rf/ERP visibles.
 *
 * Docs:
 * - `docs/adr/024-estudio-supervision-universe.md`
 * - `docs/engineering/estudio-supervision-model-2026-08-06.md`
 * - `docs/engineering/estudio-process-status-ui-2026-08-06.md`
 * - `docs/engineering/session-handoff-2026-08-06-estudio-process-ui.md`
 * - `docs/engineering/visualizados-list-ux-2026-08-06.md`
 * - `docs/engineering/session-handoff-2026-08-06-visualizados-list-ux.md`
 * - `docs/engineering/trading-operativa-panel-2026-08-04.md`
 * - `docs/engineering/chart-top1-indicator-switch-2026-08-03.md`
 * - `docs/engineering/session-handoff-2026-08-04-operativa.md`
 * - `docs/engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md`
 * - `docs/adr/019-dual-universes-lab-vs-trading.md`
 * - `docs/adr/020-operating-mandate-tenure.md`
 * - `docs/adr/021-dia-d-reconciliation.md`
 * - `docs/engineering/dual-universes-lab-trading-design-2026-08-02.md`
 * - `docs/engineering/session-handoff-2026-08-01.md` ← handoff código racha
 * - `docs/engineering/fa-status-and-test-plan-2026-07-31.md`
 * - `docs/engineering/backtesting-dia-d-premises-2026-07-31.md`
 * - `docs/engineering/operativa-test-plan-2026-07-31.md`
 * - `docs/engineering/fundamental-intelligence-engine-2026-07-30.md`
 * - `docs/engineering/list-auto-ops-2026-07-29.md` § CORE-R
 *
 * Verificar: `pnpm test:fa` · `pnpm test:operativa` · `pnpm test:coach`
 *
 * @see docs/adr/024-estudio-supervision-universe.md
 * @see docs/engineering/estudio-process-status-ui-2026-08-06.md
 * @see docs/engineering/session-handoff-2026-08-06-estudio-process-ui.md
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 * @see docs/engineering/dual-universes-lab-trading-design-2026-08-02.md
 * @see docs/adr/020-operating-mandate-tenure.md
 * @see docs/engineering/session-handoff-2026-08-04-operativa.md
 * @see docs/engineering/lists-universes-design-2026-07-30.md
 */
export const HELP_CONTENT_AS_OF = "2026-08-27" as const;
