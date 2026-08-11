/**
 * Ayuda → Watchlist (Listas / Valores).
 */

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { HelpSourcesFooter } from "@/features/help/help-sources-footer";
import {
  WATCHLIST_LISTS_UI,
  WATCHLIST_NEXT,
  WATCHLIST_SUMMARY,
  WATCHLIST_SYNC,
  WATCHLIST_VALUES_UI,
} from "@/features/settings/watchlist-lists-tracker";

export function WatchlistHelpSection() {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{WATCHLIST_SUMMARY.title}</CardTitle>
          <CardDescription>
            Watchlist · sync {WATCHLIST_SYNC.asOf}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-xs text-muted-foreground">
            {WATCHLIST_SUMMARY.body}
          </p>
          <ul className="list-disc space-y-1 pl-4 text-xs text-foreground">
            {WATCHLIST_SUMMARY.bullets.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Vista Listas</CardTitle>
          <CardDescription>Gestión y controles por fila</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {WATCHLIST_LISTS_UI.map((row) => (
              <li
                key={row.id}
                className="rounded-md border border-border/70 px-3 py-2"
              >
                <p className="text-sm font-medium text-foreground">
                  {row.title}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">{row.body}</p>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Vista Valores</CardTitle>
          <CardDescription>Contenido y carrusel</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {WATCHLIST_VALUES_UI.map((row) => (
              <li
                key={row.id}
                className="rounded-md border border-border/70 px-3 py-2"
              >
                <p className="text-sm font-medium text-foreground">
                  {row.title}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">{row.body}</p>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Para probar ahora</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {WATCHLIST_NEXT.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Persistencia:{" "}
            <code className="text-[10px]">{WATCHLIST_SYNC.persistenceDoc}</code>
            {" · "}
            Diseño índices:{" "}
            <code className="text-[10px]">{WATCHLIST_SYNC.listsDesignDoc}</code>
          </p>
        </CardContent>
      </Card>

      <HelpSourcesFooter sectionId="watchlist" />
    </div>
  );
}
