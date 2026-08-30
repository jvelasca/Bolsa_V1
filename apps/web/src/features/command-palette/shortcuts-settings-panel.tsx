import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { PLATFORM_SHORTCUTS } from "@/features/command-palette/platform-shortcuts";

/** Config → Atajos — lista V1.31 (palette + L1 + Confirmar). */
export function ShortcutsSettingsPanel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Atajos de teclado</CardTitle>
        <CardDescription>
          No se disparan mientras escribes en un campo. Command palette: Ctrl/⌘
          K.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border text-sm">
          {PLATFORM_SHORTCUTS.map((row) => (
            <li
              key={row.id}
              className="flex items-center justify-between gap-4 py-2.5 first:pt-0 last:pb-0"
            >
              <span className="text-foreground">{row.action}</span>
              <kbd className="shrink-0 rounded border border-border bg-muted/40 px-2 py-0.5 font-mono text-xs text-muted-foreground">
                {row.keys}
              </kbd>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
