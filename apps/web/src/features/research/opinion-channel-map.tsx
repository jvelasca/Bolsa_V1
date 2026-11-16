/**
 * Asesor → Análisis · mapa de canales y su leyenda — slice A3.
 *
 * Es la tabla que despliega el botón «Mapa canales»: cómo se asigna canal según la
 * recomendación y las ★. Movida TAL CUAL desde `asesor-opiniones-panel.tsx` (mismo
 * marcado, mismo `data-testid` y mismo texto).
 *
 * @see packages/shared/src/estudio-daily-opinions.ts (`OPINION_CHANNEL_MAP_LEGEND`)
 */

import {
  OPINION_CHANNEL_LEVEL_LABELS,
  OPINION_CHANNEL_MAP_LEGEND,
  marketStanceLabel,
} from "@bolsa/shared";

export function OpinionChannelMap() {
  return (
    <div
      className="overflow-x-auto rounded-md border border-border text-xs"
      data-testid="asesor-channel-map-legend"
    >
      <table className="w-full min-w-[28rem] text-left">
        <thead className="bg-muted/40 text-muted-foreground">
          <tr>
            <th scope="col" className="px-2 py-1.5 font-medium">
              Recomendación
            </th>
            <th scope="col" className="px-2 py-1.5 font-medium">
              ★
            </th>
            <th scope="col" className="px-2 py-1.5 font-medium">
              Canal
            </th>
            <th scope="col" className="px-2 py-1.5 font-medium">
              Acción
            </th>
          </tr>
        </thead>
        <tbody>
          {OPINION_CHANNEL_MAP_LEGEND.map((row) => (
            <tr
              key={`${row.stance}-${row.stars}-${row.level}`}
              className="border-t border-border/70"
            >
              <td className="px-2 py-1">
                {marketStanceLabel({ stance: row.stance }).label}
              </td>
              <td className="px-2 py-1 tabular-nums">{row.stars}</td>
              <td className="px-2 py-1">
                {OPINION_CHANNEL_LEVEL_LABELS[row.level]}
              </td>
              <td className="px-2 py-1 text-muted-foreground">{row.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-border px-2 py-1.5 text-[10px] text-muted-foreground">
        Canal asignado por recomendación y ★. Correo de Alarmas: menú usuario →
        Notificaciones. SMS aparcado.
      </p>
    </div>
  );
}
