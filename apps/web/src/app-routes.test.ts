import { describe, expect, it } from "vitest";

import {
  ROUTE_PAGE_LOADERS,
  ROUTE_PAGES,
  type RoutePageName,
} from "@/app-routes";

const LAZY_SYMBOL = Symbol.for("react.lazy");

describe("app-routes (Fase 3.1: lazy por ruta)", () => {
  it("cada ruta declara un componente React.lazy", () => {
    const names = Object.keys(ROUTE_PAGE_LOADERS) as RoutePageName[];
    expect(names.length).toBeGreaterThan(20);
    for (const name of names) {
      const component = ROUTE_PAGES[name] as unknown as {
        $$typeof?: symbol;
      };
      expect(component, name).toBeDefined();
      expect(component.$$typeof, name).toBe(LAZY_SYMBOL);
    }
  });

  it("cada loader importa el módulo y exporta el componente con ese nombre", async () => {
    const names = Object.keys(ROUTE_PAGE_LOADERS) as RoutePageName[];
    for (const name of names) {
      const module = (await ROUTE_PAGE_LOADERS[name]()) as Record<
        string,
        unknown
      >;
      const exported = module[name];
      expect(
        typeof exported === "function" ||
          (typeof exported === "object" && exported !== null),
        `${name} no exporta un componente`,
      ).toBe(true);
    }
  }, 30_000);

  it("el mapa de rutas es la única fuente: no hay loaders duplicados", () => {
    const names = Object.keys(ROUTE_PAGE_LOADERS);
    expect(new Set(names).size).toBe(names.length);
    expect(Object.keys(ROUTE_PAGES).sort()).toEqual([...names].sort());
  });
});
