# Premisa — Preferencias UI en `localStorage`

> **Premisa de producto (jul 2026).** Aplica a **toda** la app web.  
> Complementa [WORKSPACE_PERSISTENCE.md](./WORKSPACE_PERSISTENCE.md), [UI_PLATFORM.md](./UI_PLATFORM.md) y [RESPONSIVE_PREMISES.md](./RESPONSIVE_PREMISES.md).

---

## 1. Regla

**Todo elemento configurable de la UI** (layout, anchos, orden/visibilidad de columnas, paneles abiertos/colapsados, splits, favoritos de chrome, HUD, asistente, etc.) **se persiste en `localStorage` del navegador** del perfil en esa máquina.

| Qué | Dónde |
|-----|--------|
| Chrome / preferencias de UI | `localStorage` (por dispositivo · por perfil de navegador) |
| Contenido de dominio del espacio (gráficos abiertos, listas, dibujos, plantillas…) | Servidor (`/api/workspaces`) — ver [WORKSPACE_PERSISTENCE.md](./WORKSPACE_PERSISTENCE.md) |
| Auth / cuenta activa | También `localStorage` (sesión), no confundir con “chrome” |

**Consecuencia:** escritorio, portátil y móvil (o Chrome vs Edge) **no se pisan**. Cada entorno recuerda *su* layout. No es un bug: es el diseño.

---

## 2. Cómo hacerlo (nuevo UI)

1. Preferencias en store Zustand + `persist`, o helper `localStorage` con clave `bolsa-*-vN`.
2. Clave **versionada** (`…-v1`, `…-v2`); al romper el shape, subir versión y migrar lo legible.
3. Si el layout cambia por breakpoint (p. ej. lista|detalle horizontal vs apilado), **guardar por modo** (`wide` / `stack`), no un solo porcentaje compartido.
4. Persistir al **soltar** un resize (o debounce corto); no spamear en cada pixel si no hace falta.
5. No mandar chrome de layout al servidor “porque sí”. Solo si un ADR futuro define sync cross-device explícito.

---

## 3. Ejemplos actuales (no exhaustivo)

| Ámbito | Clave / store |
|--------|----------------|
| Dock Trading | `bolsa-trading-layout-v1` (listas/ops/operativa open · anchos · alturas de sección Operativa) |
| Libro operativo DEMO (MANUAL/SEMI) | `bolsa-demo-book-prefs-v1` |
| Notificaciones Alarmas (toast/email) + digest diario | `bolsa-notification-prefs-v1` |
| Anchos columnas listas | `bolsa-list-chrome-layout-v1` |
| Screeners | `bolsa-screener-preferences` |
| Backtesting splits / HUD / zona | `bolsa-backtest-layout-*`, `bolsa-backtest-hud-prefs-v1`, … |
| Hub Instrumentos | `bolsa-instruments-hub-prefs-v2` (wide/stack + secciones) |
| Backtesting DÍA D (fecha) | `bolsa-backtest-run-context-v1` → campo `diaD` |
| Trading MODO DÍA D (sesión) | `bolsa-dia-d-trading-session-v1` — ahora **LAB Verificar** (`universe: lab`; mode, gateDecisions, autoRunId; `fullBleedMovie` no se persiste) |
| Adopción TOP→TRADING | `bolsa-strategy-adoption-v1` (proyección del mandato vigente · ADR-020) |
| Mandato operativo (tenures) | `bolsa-mandate-tenures-v1` (**cache**; SoT BD M1b) |
| Mandato ↔ trades DEMO | `bolsa-mandate-trade-links-v1` (**cache**; SoT BD M1b) |
| TOP experimento DÍA D (F-D) | `bolsa-dia-d-experiment-top-v1` ([ADR-021](./adr/021-dia-d-reconciliation.md)) |
| Evidence DÍA D (archivo) | `bolsa-dia-d-evidence-archive-v1` (cap 30; opcional `researchEvidenceId`) |
| CORE-R cola revisión | `bolsa-core-r-review-queue-v1` (cap 40; open/done) · **SoT BD** `GET\|PUT /api/accounts/{id}/core-r` (Q3.4) |
| CORE-R scheduler | `bolsa-core-r-scheduler-v1` (`enabled`, `intervalMinutes`, `listId`, `scope`, `lastRemoteEnqueue*`) · sync BD · cron `CORE_R_CRON_ENABLED` · toast remoto `bolsa-core-r-last-seen-remote-enqueue` |
| CORE-R informe Lista AUTO | `bolsa-core-r-report-v1` (juicio post-settle; fuente de Encolar) · sync BD |
| Inbox alarmas Tracker | `bolsa-tracker-alarm-inbox-v1` |
| Preferencias de trade / cuenta activa | `bolsa-trade-preferences`, `bolsa-active-account` |

---

## 4. Qué no es esta premisa

- **No** sustituye la BD para datos de mercado, cartera, trackers, FA, backtests, etc.
- **No** implica que el workspace “documento” viva solo en el cliente (el contenido va al servidor).
- **No** garantiza sync entre dispositivos: hace falta export/import o una feature futura de sync de prefs.

---

## 5. Checklist al revisar PRs de UI

- [ ] ¿El usuario puede redimensionar / reordenar / mostrar-ocultar / colapsar algo?
- [ ] ¿Eso se recuerda al recargar en el **mismo** navegador?
- [ ] ¿Desktop y móvil tienen prefs separadas si el layout es distinto?
- [ ] ¿La clave está versionada y documentada en el store o en el doc de la feature?
