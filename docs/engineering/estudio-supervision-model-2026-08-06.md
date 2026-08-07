# Modelo «Estudio» — supervisión única (2026-08-06)

> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) → Product / Ops  
> **ADR:** [024-estudio-supervision-universe.md](../adr/024-estudio-supervision-universe.md)  
> **Estado:** implementado (membresía + Supervisión ON + cadencias 3 capas, 2026-08-06).  
> **Handoff:** [session-handoff-2026-08-06-estudio-supervision.md](./session-handoff-2026-08-06-estudio-supervision.md)

---

## 1. Problema

Dos listas con nombres parecidos y un lifecycle incompleto:

1. **Estudio** virtual = mesa Trading local (auto-add al abrir gráfico).
2. **Estudio personal** = tip de nombre API para CORE-R Auto-sync (v1.13).
3. Lab / Lista AUTO / Monitor no usan la Estudio virtual.
4. Quitar de lista ≠ parar supervisión.

El usuario quiere: *elige valores → A Estudio → supervisión completa; quitar → para*.

## 2. Modelo objetivo

```text
Catálogo / buscador ──A Estudio──► Lista Estudio (API)
                                      │
                         Supervisión ON│
                                      ▼
                         Lista AUTO + CORE-R Auto-sync
                                      │
                                      ▼
                         TOP / Lab / juicios → cola SEMI
                                      │
                         Proponer / Adoptar (humano)
                                      │
Gráfico ──solo mirar──► (sin efecto en membresía)

Quitar de Estudio ──► excluir campaña + dismiss colas
                      (no auto-cierra mandato / posición)
```

| Acción | Efecto |
|--------|--------|
| Pasar a Estudio | Membresía API; elegible para supervisión |
| Quitar de Estudio | Unsubscribe (campaña/colas); no borra histórico Lab |
| Supervisión ON | Arma Lista AUTO + CORE-R sobre Estudio |
| Supervisión OFF | Pausa ticks/tandas; conserva membresía y Finalistas |
| Abrir/cerrar gráfico | Sin efecto en membresía |
| Proponer / Adoptar | Humano (SEMI) |

## 3. As-is (referencia rápida)

| Pieza | Comportamiento actual | Archivos clave |
|-------|----------------------|----------------|
| Membresía Estudio | Store local + workspace; chart open añade | `visualization-store.ts`, `use-chart-visualization-sync.ts` |
| Nombre reservado | API no permite lista «Estudio» | `bolsa_application/lists.py`, `default-lists.ts` |
| Lista AUTO | Solo `listId` API; Play manual | `backtest-list-auto.ts`, `backtests-page.tsx` |
| CORE-R Auto-sync | Prefiere «Estudio personal» | `core-r-scheduler.ts`, `strategy-monitor-panel.tsx` |
| Remove | Quita membresía; **no** para campaña/colas | `use-list-instrument-removal.tsx`, `core-r-review-queue-store.ts` |
| SEMI gate | Exige Estudio virtual | `demo-book-prefs.ts`, `propose-instrument-supervised.ts` |

## 4. Diseño de implementación (siguiente stage)

### 4.1 Persistencia

- Lista API canónica **Estudio** (sistema o por cuenta).
- Excepción al reserved-name solo para esa lista canónica; carrusel sin chip duplicado.
- Migración: `visualization-store` → miembros API; si existe «Estudio personal», merge/rename y deprecar `ESTUDIO_PERSONAL_LIST_NAME`.
- IO + gate SEMI leen el mismo universo (cache local OK si refleja API).

### 4.2 Sin auto-add por gráfico

- Desactivar alta en `use-chart-visualization-sync.ts` (opcional: log de vistas sin membresía).
- Mantener bulk «A Estudio» / «Quitar» en Listas e Instrumentos.

### 4.3 Interruptor Supervisión + cadencias 3 capas

- Prefs (`bolsa-estudio-supervision-v1`, schema v2): `enabled` + 3 cadencias + presupuesto.
- Defaults **vela 1d al cierre**: vigilia 1d · frescura 1d · redisc. 30d (no vigilia cada hora).
- ON → arma CORE-R + frescura inicial; `EstudioSupervisionHost` programa media/lenta.
- OFF → pausa campaña + Auto-sync off; no borra membresía/Finalistas.
- UI: check ON/OFF + (···) con título/hint por capa (contraste alto); banner sin texto largo.
- Sellos por valor: Finalistas `lastSearchAt` / freshness · Lista AUTO board · CORE-R `enqueuedAt`.
- UI: Supervisión global solo en banner Estudio.
  Sincro ≠ Procesos; columnas en (···) cabecera Valores (`columnLayoutsByListId` por lista);
  cadencias en (···) Supervisión; bajo el nombre = resumen procesos; desplegable fila = precio + Operativa.
- **Actualizar** / **Redescubrir** (botones separados; OFF ok). Copy remove: «Eliminar de la lista».
- Manual/SEMI/AUTO → barra de estado + Cuentas (no panel Operativa por valor).
- UI procesos: [estudio-process-status-ui-2026-08-06.md](./estudio-process-status-ui-2026-08-06.md).

### 4.4 Remove = unsubscribe

1. Lista AUTO activa: sacar de pendientes / skip si es el current.
2. CORE-R: dismiss open por `instrumentId`; no re-encolar.
3. F3: dismiss propuestas abiertas de supervisión.
4. Mandato/posición: **no** cerrar auto; banner «sigue mandato activo».

### 4.5 Copy

- Retirar «Estudio personal» de HELP / `backtesting-tracker` / list-auto-ops tras el stage.
- Frase canónica: *Estudio = valores en supervisión. Supervisión ON = Lab + reevaluación. SEMI = confirmas operar y cambiar estrategia.*

## 5. Fases

1. ADR-024 + este doc (**hecho** 2026-08-06).
2. Estudio API canónica + migración + deprecar Estudio personal (**hecho**).
3. Quitar auto-add gráfico + copy (**hecho**).
4. Supervisión ON cableada a Lista AUTO + CORE-R (**hecho**).
5. Unsubscribe en remove (**hecho**).
6. Cadencias 3 capas + host + UI (···) (**hecho** 2026-08-06).
7. Tests: prefs/migración/due/slice rediscover (**hecho**); E2E smoke manual.

## 6. Fuera de alcance

- AUTO execute / auto-adopt (ADR-023).
- Borrar Finalistas al quitar.
- Cambiar embudo Lab interno.

## 7. Criterio de éxito

Usuario: *IBEX/buscador → A Estudio → Supervisión ON → revisa cola SEMI*.  
Una sola «Estudio»; cero «Estudio personal»; gráfico no mete valores; quitar para la supervisión de ese valor.

## 8. Retomar (agente siguiente)

Checklist de arranque:

1. Leer ADR-024 + este doc + [estudio-process-status-ui-2026-08-06.md](./estudio-process-status-ui-2026-08-06.md).
2. Handoff UI: [session-handoff-2026-08-06-estudio-process-ui.md](./session-handoff-2026-08-06-estudio-process-ui.md).
3. Smoke: Actualizar vs Redescubrir · badge OPERATIVA en barra · subtítulo `toca V`.
4. No tocar Camino D / `PAPER_D_EXECUTE`.
