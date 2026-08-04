/**
 * Menú y diálogo de Ayuda (?).
 *
 * Guía + secciones de seguimiento. Espacios de trabajo documentados en Guía
 * (barra superior) y Trading (gestor / arranque). Fuentes: `help-registry.ts`.
 * Sync: `HELP_CONTENT_AS_OF`.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { CircleHelp } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Dialog } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { AiPlatformSection } from '@/features/settings/ai-platform-section';
import { BacktestingHelpSection } from '@/features/settings/backtesting-help-section';
import { ValueAnalysisSection } from '@/features/settings/value-analysis-section';
import { ChartPlatformSection } from '@/features/settings/chart-platform-section';
import { DataCaptureSection } from '@/features/settings/data-capture-section';
import { WatchlistHelpSection } from '@/features/settings/watchlist-help-section';
import { HelpSourcesFooter } from '@/features/help/help-sources-footer';
import {
  HELP_CONTENT_AS_OF,
  HELP_SECTIONS,
  trackingSections,
  type HelpRegistrySectionId,
} from '@/features/help/help-registry';
import { useUiStore, type PlatformConfigTab } from '@/stores/ui-store';

const CONTACT_EMAIL = 'josealberto.vel@gmail.com';

type HelpSection = HelpRegistrySectionId;

const SECTION_LABELS: Record<HelpSection, string> = Object.fromEntries(
  HELP_SECTIONS.map((s) => [s.id, s.label]),
) as Record<HelpSection, string>;

function HelpNav({
  active,
  onSelect,
}: {
  active: HelpSection;
  onSelect: (section: HelpSection) => void;
}) {
  return (
    <nav className="flex flex-wrap gap-1 border-b border-border pb-3">
      {(Object.keys(SECTION_LABELS) as HelpSection[]).map((id) => (
        <button
          key={id}
          type="button"
          onClick={() => onSelect(id)}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
            active === id
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-accent hover:text-foreground',
          )}
        >
          {SECTION_LABELS[id]}
        </button>
      ))}
    </nav>
  );
}

function RouteLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="font-medium text-primary hover:underline">
      {children}
    </Link>
  );
}

function OpenConfigLink({
  tab,
  children,
}: {
  tab?: PlatformConfigTab;
  children: ReactNode;
}) {
  const openConfig = useUiStore((s) => s.openPlatformConfig);
  return (
    <button
      type="button"
      className="font-medium text-primary hover:underline"
      onClick={() => openConfig(tab ?? 'general')}
    >
      {children}
    </button>
  );
}

function GuideContent() {
  return (
    <div className="space-y-5 text-sm">
      <p className="text-muted-foreground">
        Bolsa V1 es una plataforma personal de gestión bursátil con terminal de trading, cuentas
        simuladas, ledger contable y fiscal. Todo el patrimonio y las operaciones se gestionan por{' '}
        <strong>cuenta de inversión</strong> (modelo estilo XTB).
      </p>

      <section>
        <h3 className="mb-2 font-semibold">Navegación principal</h3>
        <ul className="space-y-2 text-muted-foreground">
          <li>
            <RouteLink to="/overview">Overview</RouteLink> — Cuenta activa, patrimonio y atajos a
            Trading, Backtesting (Play / Lista AUTO / Finalistas) y análisis fundamental (Tarjeta
            Valor · Screeners FA · Paper D).
          </li>
          <li>
            <strong>← →</strong> (inicio de la barra, antes de Overview) — historial de
            navegación SPA (atrás / adelante entre rutas y queries).
          </li>
          <li>
            <RouteLink to="/trading">Trading</RouteLink> — Workspace de gráficos, watchlist,
            indicadores y panel de operaciones.
          </li>
          <li>
            <RouteLink to="/accounts">Cuentas</RouteLink> — Hub de cuentas: resumen, posiciones,
            movimientos de efectivo y configuración.
          </li>
          <li>
            <RouteLink to="/alerts">Alertas</RouteLink> — Alertas de precio sobre instrumentos del
            catálogo.
          </li>
        </ul>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Más pantallas</h3>
        <ul className="space-y-2 text-muted-foreground">
          <li>
            <RouteLink to="/operations">Operaciones</RouteLink> — Posiciones abiertas y órdenes
            pendientes de la cuenta activa.
          </li>
          <li>
            <RouteLink to="/history">Historial</RouteLink> — Libro mayor (ledger) y registro de
            operaciones ejecutadas.
          </li>
          <li>
            <RouteLink to="/fiscal">Fiscal</RouteLink> — Informe de plusvalías realizadas y
            latentes por ejercicio.
          </li>
          <li>
            <RouteLink to="/instruments">Instrumentos</RouteLink> — Hub del valor (tabla
            configurable: anchos, orden, favoritas; FA/TA; seguimiento Radar). Importación desde
            Listas.
          </li>
          <li>
            <RouteLink to="/backtests">Backtesting</RouteLink> — Simulaciones históricas. Guía y
            seguimiento en Ayuda → <strong className="text-foreground">Backtesting</strong>.
          </li>
          <li>
            <RouteLink to="/screeners">Rastreadores</RouteLink> — Escaneo de universo y señales en la
            última barra.
          </li>
        </ul>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Configuración vs Ayuda</h3>
        <ul className="space-y-1 text-muted-foreground">
          <li>
            <strong className="text-foreground">Configuración (⚙)</strong> — solo preferencias y
            ajustes: cuenta activa, espacio (General), comisiones, confirmaciones, sync, BD.
          </li>
          <li>
            <strong className="text-foreground">Ayuda (?)</strong> — guías y seguimiento. Las
            secciones de tracking (IA, datos, estado gráficos) salen de ficheros{' '}
            <code className="text-xs">*-tracker.ts</code> coordinados con docs (sync{' '}
            {HELP_CONTENT_AS_OF}).
          </li>
        </ul>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Seguimiento coordinado</h3>
        <ul className="space-y-1 text-muted-foreground">
          {trackingSections().map((s) => {
            const tracker = s.sources.find((x) => x.role === 'tracker');
            return (
              <li key={s.id}>
                <strong className="text-foreground">{s.label}</strong>
                {tracker ? (
                  <>
                    {' '}
                    ← <code className="text-[10px]">{tracker.path.split('/').pop()}</code>
                  </>
                ) : null}
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-xs text-muted-foreground">
          Índice: <code>docs/HELP.md</code> · registro:{' '}
          <code className="text-[10px]">help-registry.ts</code>
        </p>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Barra superior</h3>
        <ul className="space-y-1 text-muted-foreground">
          <li>
            <strong>Nav</strong> — Overview, Trading, Cuentas, Alertas, Instrumentos, Backtesting,
            Rastreadores.
          </li>
          <li>
            <strong>Grupo tras separador</strong> — Flechas ← → (historial). En Trading, además:
            watchlist, operaciones y restablecer paneles.
          </li>
          <li>
            <strong>Chip del espacio</strong> — Nombre (punto ámbar = pendiente). Clic → gestor:
            cambiar, nuevo, duplicar, renombrar, <em>Exportar JSON</em> y <em>Guardar actual</em>.
            Autoguardado por defecto.
          </li>
          <li>
            <strong>Ayuda</strong> — Guías y seguimiento (IA, datos, gráficos…).
          </li>
          <li>
            <strong>Configuración (⚙)</strong> — General (incluye restablecer paneles), perfil
            inversor, comisiones/fiscal, confirmaciones, BD, sync.
          </li>
          <li>
            <strong>Sesión (usuario)</strong> — Cerrar sesión.
          </li>
        </ul>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Cuenta activa</h3>
        <p className="text-muted-foreground">
          El selector de cuenta está en la <strong className="text-foreground">barra inferior</strong>{' '}
          (Trading / Operaciones) y en Configuración. Define patrimonio, trades y fiscal. No está
          en la barra superior.
        </p>
      </section>
    </div>
  );
}

function AccountsContent() {
  return (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p>
        Cada <strong>cuenta DEMO</strong> (simulada) es la unidad visible: efectivo, posiciones,
        comisiones y fiscal van unidos a ella. No hay subcarteras en la interfaz.
      </p>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Premisa (bloqueada)</h3>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Solo se opera con <strong className="text-foreground">una cuenta activa</strong> a la
            vez (selector barra inferior / «Usar ahora»).
          </li>
          <li>
            Hoy todas las cuentas operativas son <strong className="text-foreground">DEMO</strong>{' '}
            (capital simulado).
          </li>
          <li>
            <strong className="text-foreground">Paper</strong> = futuro enlace a{' '}
            <em>broker real</em> por API — no es simulación y no se usa hasta entonces.
          </li>
        </ul>
        <p className="mt-2 text-[11px]">
          Detalle: docs/engineering/account-premises-demo-vs-paper-2026-07-31.md
        </p>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Cuenta activa</h3>
        <p className="text-muted-foreground">
          Es la cuenta con la que opera la app (Trading, patrimonio, Backtesting→demo, Radar,
          Supervisado). Se restaura al reabrir. Cámbiala en el selector de la barra o en{' '}
          <RouteLink to="/accounts">Cuentas</RouteLink> con «Usar ahora». Puedes tener varias demos
          (p. ej. otro mercado); solo una es la activa.
        </p>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Movimientos del libro mayor</h3>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Depósito inicial</strong> — capital al crear la cuenta.
          </li>
          <li>
            <strong>Comisión y cargos</strong> — se descuentan del efectivo: comisión broker (% con mín/máx),
            IVA, impuesto de transmisiones en compras y, si aplica, custodia anual sobre patrimonio.
          </li>
          <li>
            <strong>Compra / Venta</strong> — importe de la operación; las comisiones van en líneas
            separadas.
          </li>
        </ul>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Crear cuenta</h3>
        <p>
          Desde <RouteLink to="/accounts">Cuentas</RouteLink> → <em>Nueva demo</em>. El asistente pide
          identidad, capital, <strong>perfil inversor del catálogo</strong> (lista selectable; o
          crear uno nuevo), comisiones y fiscal. Una cuenta = un perfil activo. Se cambia después en{' '}
          <OpenConfigLink tab="investor-profile">Configuración → Perfil inversor</OpenConfigLink> o
          en la ficha de la cuenta.
        </p>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Movimientos de efectivo</h3>
        <p>
          En la pestaña <em>Movimientos</em> del detalle de cuenta: depósitos y retiradas externas
          (simulan capital que entra o sale de la cuenta demo).
        </p>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Ciclo de vida (modo demo)</h3>
        <ol className="list-decimal space-y-1 pl-5">
          <li>
            <strong>Editar</strong> — Nombre y descripción en Configuración de la cuenta.
          </li>
          <li>
            <strong>Cerrar</strong> — Soft-delete: deja de operar pero <em>sigue en BD</em> (ledger e
            historial para auditoría/fiscal).
          </li>
          <li>
            <strong>Eliminar</strong> — Solo demos ya cerradas. Borra la fila de cuenta y carteras,
            posiciones, transacciones, ledger y órdenes. Los perfiles del catálogo se conservan.
            También desde <OpenConfigLink tab="bd">Configuración → BD</OpenConfigLink> (lista y
            purga en lote).
          </li>
        </ol>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Ledger</h3>
        <p>
          Registro append-only de todos los movimientos: depósitos, compras/ventas, comisiones,
          custodia. Consultable en <RouteLink to="/history">Historial</RouteLink>.
        </p>
      </section>
    </div>
  );
}

function TradingContent() {
  return (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p>
        El workspace de <RouteLink to="/trading">Trading</RouteLink> combina gráficos
        multi-timeframe, watchlist y operativa sobre la <strong className="text-foreground">cuenta
        activa DEMO</strong>.
      </p>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Panel Operativa</h3>
        <p>
          Columna derecha a <strong className="text-foreground">altura completa</strong> (hasta la
          barra de estado). Operaciones queda a la izquierda, bajo watchlist y gráfico. Tres
          secciones con scroll y altura ajustable:
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            <strong className="text-foreground">Recomendación</strong> — Índice Operativo (IO),
            gauges TA/FA, ranking «El n de N en Estudio», TOP #1 / adopción, enlaces{' '}
            <strong className="text-foreground">Abrir estudio (LAB)</strong> y{' '}
            <strong className="text-foreground">Verificar D→hoy</strong> (si hay DÍA D en el
            pasado).
          </li>
          <li>
            <strong className="text-foreground">Info</strong> — mandato / Learning.
          </li>
          <li>
            <strong className="text-foreground">Configuración</strong> — a la derecha
            «Operativa: manual|semi|auto» (sin desplegar); el bloque usa el{' '}
            <strong className="text-foreground">nombre de la cuenta activa</strong> (MANUAL/SEMI,
            % cash, máx. posiciones, geo).{' '}
            <strong className="text-foreground">AUTO</strong> se muestra como «prep» con riesgos
            (Camino D / Risk Engine / kill switch); pill deshabilitada hasta checklist thaw +{' '}
            <code className="text-[10px]">PAPER_D_EXECUTE</code>. Kill switch en el mismo bloque
            (API runtime). Armado local con doble confirmación (frase{' '}
            <code className="text-[10px]">ACTIVAR AUTO</code>) no habilita execute. Usa SEMI + Confirm.
          </li>
        </ul>
        <p className="mt-2">
          Lista virtual <strong className="text-foreground">Estudio</strong> = universo
          operativo (membresía explícita). Abrir gráfico añade; cerrar pestaña no quita.
          Selección masiva → «A Estudio». SEMI/AUTO exigen pertenencia; MANUAL no. La
          verificación ya no vive en la mesa Trading (ADR-019).
        </p>
        <h4 className="mb-1 mt-3 font-semibold text-foreground">SEMI vs AUTO (2026-08-04)</h4>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong className="text-foreground">SEMI</strong> — camino operativo diario: Alarma /
            Proponer F3 → Confirm humano → fill DEMO.
          </li>
          <li>
            <strong className="text-foreground">AUTO</strong> — solo prep: pill disabled, kill
            switch y armado local (<code className="text-[10px]">ACTIVAR AUTO</code>). Execute
            requiere checklist thaw + ADR-023 Accepted +{' '}
            <code className="text-[10px]">PAPER_D_EXECUTE=1</code> (default off).
          </li>
          <li>
            <strong className="text-foreground">Asesor → Diario</strong> — resumen operativo del
            día (cuenta · trades · F3 · Alarmas/Avisos · semana). Preview en app; email HTML
            (+ PDF opt-in R4) o descarga PDF.
          </li>
          <li>
            <strong className="text-foreground">Asesor → Opiniones</strong> — telemetría A0
            (días / precisión / recall proxy) para medir P1–P4 antes de thaw.
          </li>
        </ul>
        <h4 className="mb-1 mt-3 font-semibold text-foreground">Barra de estado (inferior)</h4>
        <p>
          Izquierda: conexión · cuenta Activa · métricas. Derecha (ancho fijo):{' '}
          <strong className="text-foreground">Colas</strong> (Velas · CORE-R · F3 · Lista AUTO) y{' '}
          <strong className="text-foreground">Alarmas Radar</strong> (badge nº sin leer). El rail
          no salta al cambiar conteos.
        </p>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Mandato operativo (ADR-020)</h3>
        <p>
          Cuando <strong className="text-foreground">Adoptas</strong> un Finalista (Checklist /
          Camino A), se abre un <strong className="text-foreground">mandato vigente</strong> para
          ese instrumento×cuenta: qué estrategia gobierna la operativa y desde cuándo. Si adoptas
          otra, el tramo anterior se cierra y queda en el historial (actor usuario / Operativa /
          CORE-R).
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            Timeline en Operativa → Info: tramos, motivo del cambio y resumen de churn (usuario vs
            sistema).
          </li>
          <li>
            Los trades DEMO (orden mercado / pendientes) se <strong className="text-foreground">
            enlazan
            </strong>{' '}
            al mandato vigente (local) para atribución futura.
          </li>
          <li>
            Distinto de Finalistas LAB (estudio) y del tag “setup” de un trade suelto.
          </li>
        </ul>
        <p className="mt-2">
          Docs: <code className="text-[0.85em]">docs/adr/020-operating-mandate-tenure.md</code> ·{' '}
          <code className="text-[0.85em]">docs/engineering/trading-operativa-panel-2026-08-04.md</code>.
        </p>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Alarmas Radar (barra inferior)</h3>
        <p>
          La campana junto a los hilos muestra el <strong className="text-foreground">inbox de
          entrada/salida</strong> de rastreadores. Llegan desde un scan manual en Screeners o
          desde un job programado (<code className="text-[0.85em]">on_bar_close</code>), aunque
          Screeners no esté abierto. Solo alarmas de la{' '}
          <strong className="text-foreground">cuenta activa DEMO</strong>. Clic en un valor → abre
          el gráfico; <strong className="text-foreground">F3</strong> → propone y abre Confirm
          supervisado. No ejecuta órdenes sola.
        </p>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Gráficos y barras</h3>
        <ul className="list-disc space-y-1 pl-5">
          <li>Varias pestañas de gráfico con instrumentos independientes.</li>
          <li>
            <strong>Barra global del gráfico</strong> (arriba): indicadores, compra/venta rápida,
            estado de datos, inspector. Su ⚙ configura solo esa barra.
          </li>
          <li>
            <strong>Barra de datos</strong> (Escala · Valor · Cursor): timeframe, metadatos del
            valor, OHLC bajo el cursor. La <strong>estrella</strong> en cada zona añade accesos
            directos; el ⚙ de esa barra configura visibilidad, fondo y favoritos.
          </li>
          <li>
            <strong>Inspector</strong> (panel derecho): modo <strong>Datos</strong> (instrumento,
            gráfico, vela, BD) y modo <strong>Config</strong> (capas, objetos, estilos, selección).
          </li>
          <li>
            Indicadores técnicos desde el catálogo; dibujos y plantillas en el inspector.
          </li>
          <li>
            <strong className="text-foreground">Finalista #1</strong>: switch «todos» en la barra
            general (Indicadores) y «este» en la barra del gráfico en uso. OFF quita solo overlays
            con origen finalist-top1.
          </li>
          <li>
            <strong>Gate bar-a-bar</strong> (estrategias híbridas): superponer la línea de paso de
            gate desde una estrategia guardada.
          </li>
        </ul>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Indicadores con IA</h3>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Catálogo de indicadores → asistente por prompt: describe el indicador en lenguaje natural.
          </li>
          <li>
            Borrador vía <code>AIGovernanceProxy</code> (Ollama / OpenAI / heurística). Revisa antes
            de añadir al gráfico.
          </li>
          <li>
            Seguimiento de fases F0–F6 y arquitectura de decisión (Assessment → Runtime → Gate): Ayuda
            → <strong>Plataforma IA</strong> (no está en Configuración).
          </li>
        </ul>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Decision Engine (supervisado)</h3>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          <li>
            Los motores emiten <strong className="text-foreground">Assessments</strong> (informe),
            no órdenes. El <strong className="text-foreground">DecisionRuntime</strong> propone la
            acción; el Policy Gate solo verifica (pasivo en propose, hard en paper_auto).
          </li>
          <li>
            El LLM <strong className="text-foreground">nunca</strong> envía órdenes ni calcula PnL.
            Backtest y trading automático <strong className="text-foreground">sí</strong> operan y
            miden PnL — vía motor determinista + Gate, no vía chat. Macro live (Yahoo ^VIX) entra
            como Assessment en propose.
          </li>
          <li>
            Prueba el flujo en Ayuda → <strong className="text-foreground">Plataforma IA</strong> →
            Supervisado F3. Desde Rastreadores puedes{' '}
            <strong className="text-foreground">Encolar F3</strong> (top hits → cola supervisada).
          </li>
          <li>
            Perfil inversor por cuenta:{' '}
            <OpenConfigLink tab="investor-profile">Configuración → Perfil inversor</OpenConfigLink>.
          </li>
        </ul>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Operar</h3>
        <ul className="list-disc space-y-1 pl-5">
          <li>Compra/venta a mercado desde el diálogo de operación en el gráfico.</li>
          <li>
            Órdenes pendientes en el panel inferior; cotizaciones live en lote (~15 s).
          </li>
          <li>
            Confirmación opcional con comisiones:{' '}
            <OpenConfigLink tab="confirmations">Configuración → Confirmaciones</OpenConfigLink>.
          </li>
        </ul>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Watchlist (Listas / Valores)</h3>
        <p className="text-sm text-muted-foreground">
          Detalle del panel izquierdo, carrusel y pertenencia al gráfico:{' '}
          <strong className="text-foreground">Ayuda → Watchlist (Listas / Valores)</strong>.
        </p>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Espacio de trabajo</h3>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Al arrancar: <strong className="text-foreground">último espacio activo</strong> de este
            dispositivo; si no hay, el marcado como preferido (estrella).
          </li>
          <li>
            Chip superior (nombre) → gestor: cambiar, <em>Nuevo (blanco)</em>,{' '}
            <em>Duplicar activo</em>, renombrar, eliminar, <em>Exportar JSON</em>,{' '}
            <em>Guardar actual</em>.
          </li>
          <li>
            Autoguardado y plantilla de gráficos nuevos:{' '}
            <OpenConfigLink tab="general">Configuración → General</OpenConfigLink> o el propio
            gestor.
          </li>
          <li>
            Se persisten gráficos abiertos, dibujos, listas y preferencias en el servidor. El layout
            de paneles Trading y los anchos de columnas de listas se guardan en este
            dispositivo (no se pisan al cambiar de PC).
          </li>
          <li>
            Detalle técnico: <code>docs/WORKSPACE_PERSISTENCE.md</code>.
          </li>
        </ul>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Rastreadores híbridos</h3>
        <p>
          En <RouteLink to="/screeners">Rastreadores</RouteLink>: escaneo con rating, gate de
          fundamentales y señales. Ver <code>docs/HYBRID_TRACKERS.md</code>.
        </p>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Diagnóstico de rendimiento</h3>
        <p className="mb-1">Consola del navegador (F12), con el gráfico abierto:</p>
        <ol className="list-decimal space-y-1 pl-5">
          <li>
            <code>bolsaPerfStart()</code> → usa la app → <code>bolsaPerfStop()</code>
          </li>
          <li>
            <code>bolsaPerfHud(true)</code> / <code>bolsaPerfReport()</code>
          </li>
        </ol>
        <p className="mt-2 text-xs">Detalle en <code>docs/PERFORMANCE.md</code>.</p>
      </section>
    </div>
  );
}

function FiscalContent() {
  return (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p>
        Cada cuenta tiene perfil fiscal configurable (jurisdicción ES por defecto): método de
        coste (FIFO o coste medio), transmisiones, retención dividendos y tipo sobre plusvalías.
        Edición en{' '}
        <OpenConfigLink tab="commissions">Configuración → Comisiones y fiscal</OpenConfigLink>.
      </p>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Comisiones simuladas</h3>
        <ul className="list-disc space-y-1 pl-5">
          <li>Presets: broker estándar ES, XTB, IBKR (personalizable).</li>
          <li>Comisión por operación, mínimos/máximos, IVA sobre comisión.</li>
          <li>Impuesto de transmisiones en compras (según perfil).</li>
          <li>Custodia anual opcional (% sobre patrimonio).</li>
        </ul>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Informe fiscal</h3>
        <p>
          En <RouteLink to="/fiscal">Fiscal</RouteLink>: plusvalías realizadas, latentes, comisiones
          acumuladas y estimación de impuesto.
        </p>
      </section>
    </div>
  );
}

function AboutContent() {
  return (
    <div className="space-y-4 text-sm">
      <p className="text-muted-foreground">
        <strong className="text-foreground">Bolsa V1</strong> — plataforma personal de gestión
        bursátil inspirada en terminales profesionales (ProRealTime / XTB). Backend FastAPI +
        PostgreSQL; frontend React + Vite.
      </p>
      <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-muted-foreground">
        <p className="text-xs uppercase tracking-wide">Modo actual</p>
        <p className="mt-1">Cuentas simuladas · Sin conexión a broker real · Datos Yahoo Finance</p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Contacto</p>
        <a
          href={`mailto:${CONTACT_EMAIL}`}
          className="mt-1 inline-block font-medium text-primary hover:underline"
        >
          {CONTACT_EMAIL}
        </a>
      </div>
      <p className="text-xs text-muted-foreground">
        Docs: <code>docs/HELP.md</code> (mapa Ayuda), <code>docs/AI_PLATFORM_SOLUTION.md</code>,{' '}
        <code>docs/API_REFERENCE.md</code>. Contenido de seguimiento sync {HELP_CONTENT_AS_OF}.
      </p>
      <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
        {HELP_SECTIONS.filter((s) => s.kind === 'tracking').map((s) => (
          <li key={s.id}>
            {s.label}: tracker en{' '}
            <code className="text-[10px]">
              {s.sources.find((x) => x.role === 'tracker')?.path.split('/').pop()}
            </code>
          </li>
        ))}
      </ul>
    </div>
  );
}

function HelpBody({
  section,
  sessionId,
  panel,
}: {
  section: HelpSection;
  sessionId?: string | null;
  panel?: 'supervised-f3' | 'monitor' | null;
}) {
  let content: ReactNode;
  switch (section) {
    case 'guide':
      content = <GuideContent />;
      break;
    case 'accounts':
      content = <AccountsContent />;
      break;
    case 'trading':
      content = <TradingContent />;
      break;
    case 'watchlist':
      content = <WatchlistHelpSection />;
      break;
    case 'value-analysis':
      content = <ValueAnalysisSection initialSessionId={sessionId} />;
      break;
    case 'backtesting':
      content = <BacktestingHelpSection focusMonitor={panel === 'monitor'} />;
      break;
    case 'ai':
      content = (
        <AiPlatformSection
          compact
          focusPanel={panel === 'supervised-f3' ? 'supervised-f3' : null}
        />
      );
      break;
    case 'data':
      content = (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Cómo entran y se guardan los datos. Los{' '}
            <strong className="text-foreground">ajustes</strong> de cola automática están en{' '}
            <OpenConfigLink tab="other">Configuración → Otras</OpenConfigLink>.
          </p>
          <DataCaptureSection compact />
        </div>
      );
      break;
    case 'charts-status':
      content = <ChartPlatformSection compact />;
      break;
    case 'fiscal':
      content = <FiscalContent />;
      break;
    case 'about':
      content = <AboutContent />;
      break;
  }

  return (
    <>
      {content}
      {section === 'value-analysis' ||
      section === 'watchlist' ||
      section === 'backtesting' ? null : (
        <HelpSourcesFooter sectionId={section} />
      )}
    </>
  );
}

export function AppHelpMenu() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [section, setSection] = useState<HelpSection>('guide');
  const [focusSessionId, setFocusSessionId] = useState<string | null>(null);
  const [focusPanel, setFocusPanel] = useState<'supervised-f3' | 'monitor' | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  useEffect(() => {
    function onOpenHelp(event: Event) {
      const detail = (
        event as CustomEvent<{
          section?: HelpSection;
          sessionId?: string;
          panel?: 'supervised-f3' | 'monitor';
        }>
      ).detail;
      const next = detail?.section ?? 'guide';
      setSection(next);
      setFocusSessionId(detail?.sessionId ?? null);
      setFocusPanel(detail?.panel ?? null);
      setDialogOpen(true);
      setMenuOpen(false);
    }
    window.addEventListener('bolsa:open-help', onOpenHelp);
    return () => window.removeEventListener('bolsa:open-help', onOpenHelp);
  }, []);

  function openSection(next: HelpSection) {
    setMenuOpen(false);
    setFocusSessionId(null);
    setFocusPanel(null);
    setSection(next);
    setDialogOpen(true);
  }

  return (
    <>
      <div ref={ref} className="relative">
        <button
          type="button"
          onClick={() => setMenuOpen((v) => !v)}
          className="flex items-center rounded-md p-1.5 text-sm hover:bg-accent"
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          aria-label="Ayuda"
          title="Ayuda"
        >
          <CircleHelp className="h-4 w-4" />
        </button>
        {menuOpen && (
          <div
            role="menu"
            className="absolute right-0 top-full z-50 mt-1 min-w-[240px] rounded-md border border-border bg-card py-1 shadow-xl"
          >
            {(Object.keys(SECTION_LABELS) as HelpSection[]).map((id) => (
              <button
                key={id}
                type="button"
                role="menuitem"
                className="flex w-full px-3 py-1.5 text-left text-sm hover:bg-accent"
                onClick={() => openSection(id)}
              >
                {SECTION_LABELS[id]}
              </button>
            ))}
          </div>
        )}
      </div>

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={SECTION_LABELS[section]}
        description={
          trackingSections().some((s) => s.id === section)
            ? 'Información y seguimiento — no cambia preferencias'
            : undefined
        }
        className="h-[min(85vh,42rem)] max-w-4xl"
      >
        <HelpNav
          active={section}
          onSelect={(id) => {
            setFocusSessionId(null);
            setFocusPanel(null);
            setSection(id);
          }}
        />
        <div className="mt-4 h-[min(62vh,32rem)] overflow-y-auto pr-1">
          <HelpBody section={section} sessionId={focusSessionId} panel={focusPanel} />
        </div>
      </Dialog>
    </>
  );
}
