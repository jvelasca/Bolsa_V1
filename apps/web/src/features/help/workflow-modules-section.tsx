/**
 * Ayuda → Flujo y módulos.
 * Resumen para usuario básico; bloque experto en Hoy; fuentes help-registry (`workflow`).
 * @see docs/engineering/research-lifecycle.md
 * @see docs/adr/019-dual-universes-lab-vs-trading.md
 */
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { HoyEnLaMesaBlock } from "@/features/help/hoy-en-la-mesa";
import {
  OperatingDeskBasicBlocks,
  OperatingDeskExpertDetails,
} from "@/features/help/operating-desk-help-blocks";
import { HELP_CONTENT_AS_OF } from "@/features/help/help-registry";

function RouteLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="font-medium text-primary hover:underline">
      {children}
    </Link>
  );
}

function ModuleCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
      <h4 className="text-sm font-semibold text-foreground">{title}</h4>
      <div className="mt-1.5 text-sm text-muted-foreground">{children}</div>
    </div>
  );
}

export function WorkflowModulesSection() {
  return (
    <div className="space-y-5 text-sm">
      <HoyEnLaMesaBlock />

      <OperatingDeskBasicBlocks />

      <OperatingDeskExpertDetails />

      <p className="text-muted-foreground">
        Bolsa V1 combina <strong className="text-foreground">investigar</strong>{" "}
        (simular estrategias en el pasado) con{" "}
        <strong className="text-foreground">operar en demo</strong> (cuenta
        simulada con libro contable). Estás en{" "}
        <strong className="text-foreground">fase de pruebas</strong>: todo gira
        en torno a una{" "}
        <strong className="text-foreground">cuenta activa DEMO</strong> y a dos
        universos separados: el{" "}
        <strong className="text-foreground">Laboratorio</strong> y la{" "}
        <strong className="text-foreground">mesa de Trading</strong>.
      </p>

      <section>
        <h3 className="mb-2 font-semibold">Dos universos (no mezclarlos)</h3>
        <div className="grid gap-2 sm:grid-cols-2">
          <ModuleCard title="Laboratorio (LAB)">
            <p>
              Donde <em>estudias</em>: backtests, embudo Play, Finalistas,
              verificación DÍA D y cartera de experimentos. No toca tu dinero
              demo ni el ledger real de la cuenta.
            </p>
            <p className="mt-2">
              Pantalla: <RouteLink to="/backtests">Laboratorio</RouteLink>{" "}
              (alias Backtesting).
            </p>
          </ModuleCard>
          <ModuleCard title="Trading (mesa diaria)">
            <p>
              Donde <em>operas</em>: gráficos, lista Estudio, panel DECISIÓN,
              órdenes demo, mandato vigente y firma humana en Confirmar.
            </p>
            <p className="mt-2">
              Pantalla: <RouteLink to="/trading">Trading</RouteLink> +{" "}
              <RouteLink to="/confirm">Confirmar</RouteLink> +{" "}
              <RouteLink to="/operations">Libro</RouteLink>.
            </p>
          </ModuleCard>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          El puente entre ambos es <strong>Adoptar</strong> un Finalista del Lab
          → crea un <strong>mandato operativo</strong> en Trading para ese
          valor. Detalle: Ayuda → Trading.
        </p>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">
          Flujo típico (de la idea a la operación)
        </h3>
        <ol className="list-decimal space-y-2 pl-5 text-muted-foreground">
          <li>
            <strong className="text-foreground">Descubrir valores</strong> —{" "}
            <RouteLink to="/instruments">Instrumentos</RouteLink>,{" "}
            <RouteLink to="/screeners">Señales</RouteLink> o listas en Trading.
            Importa tickers y sincroniza datos (Ayuda → Datos de mercado).
          </li>
          <li>
            <strong className="text-foreground">Pasar a Estudio</strong> — añade
            el valor al universo supervisable (lista API Estudio). Sin Estudio
            no hay supervisión ni propuestas SEMI para ese ticker.
          </li>
          <li>
            <strong className="text-foreground">Investigar en el Lab</strong> —{" "}
            <RouteLink to="/backtests">Laboratorio</RouteLink> → Probar → Play
            (embudo automático) o pasos manuales → Finalistas. Opcional: DÍA D
            para verificar una fecha pasada (Ayuda → Backtesting).
          </li>
          <li>
            <strong className="text-foreground">Adoptar estrategia</strong> — en
            Finalistas, Checklist / Adoptar enlaza la estrategia #1 con tu
            cuenta demo (mandato operativo en Trading → DECISIÓN → Info).
          </li>
          <li>
            <strong className="text-foreground">Supervisar</strong> — en
            Estudio, activa <em>Supervisión ON</em> (velas, frescura,
            redescubrimiento). El Monitor y CORE-R avisan si conviene revisar
            (Ayuda → Backtesting).
          </li>
          <li>
            <strong className="text-foreground">Operar en SEMI</strong> — cuenta
            en modo SEMI. Alarmas Radar o propuestas F3 van a{" "}
            <RouteLink to="/confirm">Confirmar</RouteLink>: tú firmas; la app{" "}
            <em>nunca</em> envía órdenes solas.
          </li>
          <li>
            <strong className="text-foreground">Revisar resultado</strong> —{" "}
            <RouteLink to="/operations">Operaciones</RouteLink>,{" "}
            <RouteLink to="/history">Historial</RouteLink>,{" "}
            <RouteLink to="/fiscal">Fiscal</RouteLink> y Asesor → Diario.
          </li>
        </ol>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Módulos de la aplicación</h3>
        <p className="mb-3 text-muted-foreground">
          Cada bloque tiene su guía en Ayuda (?). Aquí va el mapa rápido:
        </p>
        <div className="space-y-2">
          <ModuleCard title="Inicio y cuentas">
            <ul className="list-disc space-y-1 pl-4">
              <li>
                <RouteLink to="/overview">Overview</RouteLink> — resumen de la
                cuenta activa y atajos.
              </li>
              <li>
                <RouteLink to="/accounts">Cuentas</RouteLink> — crear demo,
                depósitos, perfil inversor, modo operativo (Ayuda → Cuentas).
              </li>
            </ul>
          </ModuleCard>
          <ModuleCard title="Datos y análisis fundamental">
            <ul className="list-disc space-y-1 pl-4">
              <li>
                <RouteLink to="/instruments">Instrumentos</RouteLink> —
                catálogo, FA/TA, seguimiento Radar.
              </li>
              <li>
                Ayuda →{" "}
                <strong className="text-foreground">Datos de mercado</strong> —
                Yahoo, sync, BD.
              </li>
              <li>
                Ayuda →{" "}
                <strong className="text-foreground">Análisis del valor</strong>{" "}
                — score fundamental, screeners FA, Paper D.
              </li>
            </ul>
          </ModuleCard>
          <ModuleCard title="Investigación (Laboratorio)">
            <ul className="list-disc space-y-1 pl-4">
              <li>
                <RouteLink to="/backtests">Laboratorio</RouteLink> — backtests,
                embudo Play, Lista AUTO, Finalistas, Monitor, DÍA D.
              </li>
              <li>
                Ayuda → <strong className="text-foreground">Backtesting</strong>{" "}
                — guías DÍA D y CORE-R con estado en vivo.
              </li>
            </ul>
          </ModuleCard>
          <ModuleCard title="Operativa diaria (mesa)">
            <ul className="list-disc space-y-1 pl-4">
              <li>
                <RouteLink to="/mesa">Hoy</RouteLink> — inbox del día (Daily
                Desk). Detalles / Journal / Libro detrás de «Ver detalles».
              </li>
              <li>
                <RouteLink to="/trading">Mercado</RouteLink> — terminal:
                watchlist, gráfico, operativa (frase + CTA), operaciones.
              </li>
              <li>
                Ayuda → <strong className="text-foreground">Watchlist</strong> —
                listas, Visualizados, Estudio.
              </li>
              <li>
                <RouteLink to="/screeners">Señales</RouteLink> — rastreadores
                híbridos; alarmas → inbox Radar → Confirm.
              </li>
              <li>
                <RouteLink to="/confirm">Confirmar</RouteLink> — cola F3
                supervisada (única firma).
              </li>
              <li>
                <strong className="text-foreground">Libro</strong> —{" "}
                <RouteLink to="/operations">Operaciones</RouteLink> +{" "}
                <RouteLink to="/history">Historial</RouteLink>.
              </li>
            </ul>
          </ModuleCard>
          <ModuleCard title="Inteligencia y asesoría">
            <ul className="list-disc space-y-1 pl-4">
              <li>
                Ayuda →{" "}
                <strong className="text-foreground">Plataforma IA</strong> —
                Decision Engine, indicadores con IA, cola F3.
              </li>
              <li>
                <strong className="text-foreground">Asesor</strong> (menú) —
                Diario operativo, Opiniones Estudio, telemetría.
              </li>
              <li>
                <RouteLink to="/alerts">Alertas</RouteLink> — precio sobre
                instrumentos del catálogo.
              </li>
            </ul>
          </ModuleCard>
          <ModuleCard title="Soporte y ajustes">
            <ul className="list-disc space-y-1 pl-4">
              <li>
                <RouteLink to="/fiscal">Fiscal</RouteLink> — plusvalías y
                comisiones simuladas.
              </li>
              <li>
                <strong className="text-foreground">Configuración (⚙)</strong> —
                preferencias, comisiones, BD, sync (no es Ayuda).
              </li>
              <li>
                Ayuda →{" "}
                <strong className="text-foreground">Estado gráficos</strong> —
                salud de la plataforma de charts.
              </li>
            </ul>
          </ModuleCard>
        </div>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Modos de la cuenta demo</h3>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          <li>
            <strong className="text-foreground">MANUAL</strong> — tú operas
            desde el gráfico; sin cola de propuestas.
          </li>
          <li>
            <strong className="text-foreground">SEMI</strong> — modo
            recomendado: la app propone (F3, alarmas); tú confirmas en
            Confirmar.
          </li>
          <li>
            <strong className="text-foreground">AUTO</strong> — BETA-D: armar
            con <code>ACTIVAR AUTO</code>; execute solo con{" "}
            <code>PAPER_D_EXECUTE=1</code>. No confundir con Lista AUTO del
            Laboratorio.
          </li>
        </ul>
        <p className="mt-2 text-xs text-muted-foreground">
          Badge <code className="text-[10px]">OPERATIVA: …</code> en la barra
          inferior de Trading → clic abre Cuentas · Operativa.
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          <strong className="text-foreground">En la práctica:</strong> ranking /
          dictamen / calidad no son compra. Sin plan vivo, Hoy no inventa BUY
          (vigilar). Confirm es la firma. Detalle de capas en el bloque
          «Información avanzada» de Hoy (arriba).
        </p>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Por detrás (solo referencia)</h3>
        <p className="text-muted-foreground">
          Interfaz React, API Python y PostgreSQL. Datos de mercado vía Yahoo;
          estrategias y ledger en BD. Para arquitectura y ADRs usa el índice de
          docs del repo — aquí no se repiten.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Sync Ayuda {HELP_CONTENT_AS_OF}.
        </p>
      </section>
    </div>
  );
}
