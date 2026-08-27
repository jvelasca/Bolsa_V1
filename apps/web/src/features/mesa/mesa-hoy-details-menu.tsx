/**
 * «Ver detalles» — sustituye a las pestañas L2 de Hoy (V1.23 Fase 4).
 * Los deep-links `?view=` siguen funcionando para power users.
 */

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { OpaqueMenuPanel } from "@/components/ui/opaque-menu-panel";
import { HOY_DETAIL_ITEMS } from "@/features/mesa/mesa-hoy-view";
import { HOY_DETALLES_LABEL } from "@/features/confirm/daily-nav";

export function MesaHoyDetailsMenu() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        data-testid="hoy-details-menu-trigger"
      >
        {HOY_DETALLES_LABEL}
        <ChevronDown className="ml-1.5 h-3.5 w-3.5" />
      </Button>
      {open ? (
        <OpaqueMenuPanel align="right" className="min-w-[230px]">
          <ul role="menu" data-testid="hoy-details-menu">
            {HOY_DETAIL_ITEMS.map((item) => (
              <li key={item.id} role="none">
                <Link
                  role="menuitem"
                  to={item.href}
                  onClick={() => setOpen(false)}
                  className="block px-3 py-1.5 hover:bg-accent"
                  data-testid={`hoy-details-item-${item.id}`}
                >
                  <span className="block text-xs font-medium">
                    {item.label}
                  </span>
                  <span className="block text-[10px] text-muted-foreground">
                    {item.hint}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </OpaqueMenuPanel>
      ) : null}
    </div>
  );
}
