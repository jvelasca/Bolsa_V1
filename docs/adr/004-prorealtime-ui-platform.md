# ADR 004: Plataforma gráfica inspirada en ProRealTime

## Estado

En progreso — UI-4 listas + UI-5 propiedades gráfico (2026-06). Ver [UI_PLATFORM.md](../UI_PLATFORM.md).

## Contexto

Bolsa V1 tiene backend Python funcional (14 endpoints) y un frontend SPA básico (sidebar + páginas). El objetivo evoluciona hacia una **plataforma de análisis profesional** con:

- Sensación de aplicación de escritorio (menús, barras de herramientas, paneles acoplables).
- Espacios de trabajo persistentes (layout + configuración del usuario).
- Gráficos configurables en profundidad.
- Listas de instrumentos personalizables (no solo IBEX 35 fijo en UI).

Referencia UX: **ProRealTime** (estructura de menús, espacios de trabajo, propiedades de gráfico), adaptada a web moderna (React, accesibilidad, responsive parcial).

## Decisiones

### 0. Acceso con contraseña (fase inmediata)

| Ahora (R-8B.2)                                                                       | Roadmap ([ADR-027](./027-auth-multi-user-jwt-hybrid.md))         |
| ------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| Un operador / `APP_PASSWORD` (`APP_PASSWORD` en `.env`)                              | Multi-usuario JWT, tabla `users`, roles                          |
| Cookie **HttpOnly** + middleware FastAPI (`auth-store.ts`, `credentials: "include"`) | JWT en cookie HttpOnly **y** Bearer fallback (R-8B.2 compatible) |
| Bearer como fallback API                                                             | `sub` → principal; admin crea users (sin registro público)       |
| Sin registro público                                                                 | Opción C híbrida: C.1 instancia → C.2 JWT admin → C.3 multi-user |

**Flujo actual (R-8B.2):** pantalla login → cookie HttpOnly (token HMAC determinista, no JWT) → `/api/auth/status`; Bearer opcional en API.

**Flujo objetivo (ADR-027, post-F5):** login → JWT (`sub`, `exp`, `iat`) en cookie HttpOnly + Bearer; transición mantiene fallback `APP_PASSWORD` en C.1–C.2.

No bloquea espacios de trabajo ni listas; solo protege la instancia.

### 1. Shell de aplicación (Desktop-like)

Reemplazar sidebar simple por **Application Shell**:

```
┌─────────────────────────────────────────────────────────────┐
│ Menú: Archivo | Espacio de trabajo | Gráficos | Listas | ...  │
├─────────────────────────────────────────────────────────────┤
│ Toolbar principal (acciones contextuales)                      │
├──────────┬──────────────────────────────────────┬───────────┤
│ Panel    │  Área central (docking / tabs)       │ Panel     │
│ izquierdo│  - Gráficos                          │ derecho   │
│ (listas) │  - Detalle / cartera / backtests     │ (props)   │
├──────────┴──────────────────────────────────────┴───────────┤
│ Status bar (mercado, sync, usuario, workspace name)           │
└─────────────────────────────────────────────────────────────┘
```

**Stack UI:**

- **Radix UI** + Tailwind (ya en proyecto) para menús, dialogs, dropdowns.
- **Zustand** para estado UI local (workspace, paneles, selección).
- **react-resizable-panels** o **dockview** para layout acoplable (evaluar en spike).
- Tema oscuro por defecto (estilo terminal pro); claro opcional.

### 2. Espacios de trabajo (Workspaces)

Un **workspace** es un documento JSON versionado que persiste:

```typescript
interface WorkspaceDocument {
  version: 1;
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  layout: LayoutState; // paneles, tamaños, tabs activos
  charts: ChartInstanceConfig[]; // N gráficos abiertos
  lists: ListPanelConfig[]; // listas visibles y columnas
  preferences: UserPreferences; // tema, autosave, etc.
}
```

**Menú Archivo / Espacio de trabajo** (paridad funcional ProRealTime):

| Acción                      | Comportamiento v1                                            | Persistencia v1                                              |
| --------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Abrir                       | Dialog: lista de `.bolsa-workspace.json` locales + recientes | IndexedDB + filesystem (File System Access API donde exista) |
| Abrir reciente              | Submenú últimos 10                                           | `localStorage` recents                                       |
| Abrir defecto               | Carga `default.bolsa-workspace.json`                         | Bundled + user override                                      |
| Guardar                     | Sobrescribe workspace actual                                 | IndexedDB                                                    |
| Guardar como…               | Nuevo nombre / export file                                   | Download JSON                                                |
| Autoguardado on/off         | Cada 60s si dirty                                            | Preference en workspace                                      |
| Renombrar                   | Cambia `name`                                                | —                                                            |
| Recargar                    | Relee desde disco/IDB sin cerrar app                         | —                                                            |
| Exportar                    | JSON descargable                                             | —                                                            |
| Abrir en este PC al iniciar | Flag `openOnStartup`                                         | Preference global                                            |
| Cerrar plataforma           | Confirm si dirty                                             | —                                                            |

**Fase 2:** sync workspace a backend (`POST /api/workspaces`) cuando exista multi-usuario.

### 3. Gráficos

Cada instancia de gráfico = `ChartInstanceConfig` + componente `OhlcvChart` (Lightweight Charts) extendido.

**Menú Gráficos / ⋯ (evolución jul 2026):**

- Abrir valor → crea o activa pestaña (**unicidad por `instrumentId`**; ver [WORKSPACE_PERSISTENCE](../WORKSPACE_PERSISTENCE.md) §2b)
- Usar gráfico activo como plantilla de gráficos nuevos (sustituye el antiguo «Duplicar gráfico», que provocaba sync inconsistente)
- Propiedades… (inspector / diálogos de barra)

**Tabs de propiedades** (consenso inicial):

| Tab                    | Opciones                                                                                  |
| ---------------------- | ----------------------------------------------------------------------------------------- |
| Cuadrícula y escala    | Líneas H/V principales y secundarias; densidad; margen vacío derecho/ superior (% barras) |
| Cursor                 | Tipo (crosshair / magnet); snap OHLC; panel info precio on/off; OHLC en tooltip           |
| Iconos en precio       | Marcadores: órdenes ejecutadas, alertas (fase alertas)                                    |
| Barra de título        | Símbolo, timeframe, último, %; estilo compacto / expandido                                |
| Etiquetas y filigrana  | Labels indicadores; watermark texto/logo                                                  |
| Colores                | Velas alcista/bajista, fondo, grid, volumen, SMA/EMA/RSI                                  |
| Datos históricos       | Dividendos, vencimientos, settlement (cuando API lo soporte)                              |
| Barras de herramientas | Inferior (timeframe, zoom); objetos (líneas, rectángulos — fase dibujo)                   |

Config serializada en workspace; defaults en `packages/shared/src/chart-defaults.ts`.

### 4. Listas — especificación (GAP cerrado)

**Estado previo:** No existía documento ni implementación de "Listas". Solo página `/instruments` con grid de cards del IBEX seed. No hay `watchlists` en BD ni API.

**Definición acordada — "Listas" en Bolsa V1:**

Una **Lista** es un panel tabular configurable, equivalente ProRealTime "List of values" / watchlist.

```typescript
interface InstrumentList {
  id: string;
  name: string; // ej. "IBEX 35", "Energía", "Mis favoritos"
  source: "catalog" | "custom"; // catálogo sistema vs usuario
  instrumentIds: string[]; // orden manual
  columns: ListColumnId[]; // columnas visibles y orden
  sort?: { column: ListColumnId; dir: "asc" | "desc" };
  filters?: ListFilter[];
}

type ListColumnId =
  | "symbol"
  | "name"
  | "lastClose"
  | "changePct"
  | "changeAbs"
  | "volume"
  | "barCount"
  | "syncStatus"
  | "sector"
  | "currency"
  | "bid"
  | "ask"
  | "spreadPct"; // XTB cuando live
```

**Menú Listas:**

| Acción              | Descripción                                        |
| ------------------- | -------------------------------------------------- |
| Nueva lista         | Lista vacía o desde plantilla                      |
| Duplicar lista      | Copia configuración                                |
| Importar IBEX 35    | Lista sistema predefinida (seed actual)            |
| Propiedades lista   | Columnas, orden, filtros, color filas              |
| Enlazar con gráfico | Click fila → cambia instrumento del gráfico activo |
| Exportar CSV        | Exportación local                                  |

**API futura (Sprint Listas):**

```
GET    /api/lists
POST   /api/lists
GET    /api/lists/:id
PATCH  /api/lists/:id
DELETE /api/lists/:id
GET    /api/lists/:id/quotes   # batch meta + live quote
```

**v1 sin backend:** listas custom solo en workspace JSON; lista IBEX desde `GET /api/instruments` existente.

### 5. Relación entre módulos

```
Workspace
 ├── layout (paneles)
 ├── lists[] ──click──► chart.activeInstrumentId
 ├── charts[] ──config──► ChartInstanceConfig
 └── preferences
```

## Fuera de alcance inmediato

- Dibujo chartista avanzado (Fibonacci, canales) — fase 3 UI
- Alertas en tiempo real — fase alertas + workers
- Multi-monitor nativo — web limita; usar ventanas popup opcional

## Plan de implementación

| Fase     | Entregable                                               | Depende de      |
| -------- | -------------------------------------------------------- | --------------- | ---------------------- |
| **UI-0** | Cutover `VITE_API_URL` → Python; retirar TS API          | Backend ✓       |
| **UI-1** | Login contraseña + middleware API                        | UI-0            |
| **UI-2** | Application shell (menú Archivo/Espacio/Gráficos/Listas) | UI-1            |
| **UI-3** | Workspace persist (IndexedDB + export/import)            | UI-2            |
| **UI-4** | Panel Listas (tabla IBEX + columnas configurables)       | UI-2            |
| **UI-5** | Chart properties dialog (grid, cursor, colores)          | UI-3            | ✅                     |
| **UI-6** | API `/api/lists` + sync workspace cloud                  | Auth multi-user | ✅ v1 (sin multi-user) |
| **UI-7** | Docking paneles redimensionables                         | UI-2            | ✅ v1                  |
| **UI-8** | Pestañas centrales multi-gráfico                         | UI-5            | ✅ v1                  |

## Consecuencias

**Positivas:** UX profesional diferenciada; workspace portable; base para alertas y dibujo.

**Negativas:** Mayor complejidad frontend; migración de páginas actuales a paneles; curva de aprendizaje diseño.

## Referencias

- ProRealTime — menús Espacio de trabajo, Gráficos, Listas
- ADR-003 — backend Python, OpenAPI
- Frontend actual: `apps/web/src/components/layout/app-layout.tsx`
