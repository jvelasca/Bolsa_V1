# ADR-037: Mesa · Hoy — Operational UX (V1.15)

**Estado:** Accepted  
**Fecha:** 2026-08-26  
**Contexto:** V1.14 construyó Journal, Consola ops e incidentes Mesa. La UX operativa diaria sigue fragmentada en `/trading`, `/operations`, `/operational-console` y `/decision-board`.

**Depende de:** [ADR-031](./031-operational-model-tesis-plan-permiso.md) · [ADR-036](./036-decision-journal-study-view.md)

---

## 1. Decisión

Crear **`/mesa` (Mesa · Hoy)** como home operativa diaria que responde **«¿qué debo hacer hoy?»**, componiendo APIs existentes sin tocar el core operacional.

Tres capas de producto:

| Superficie     | Pregunta                 | Ruta                |
| -------------- | ------------------------ | ------------------- |
| **Journal**    | ¿Qué pensamos y por qué? | `/decision-journal` |
| **Mesa · Hoy** | ¿Qué debo hacer hoy?     | `/mesa`             |
| **Libro**      | ¿Qué posiciones tengo?   | `/operations`       |

**Consola operacional** (`/operational-console`) permanece como auditoría read-only (OE-1, OR-6, recon) — no es la home diaria.

## 2. Orden visual invariante

1. Incidente activo (entradas BLOQUEADAS)
2. Estado de sesión
3. Resumen cuenta
4. Requiere atención (action queue)
5. Posiciones comprimidas
6. Candidatos agrupados
7. Link salud del sistema

## 3. Fuentes de datos (sin HTTP nuevo)

- `GET decision-board` → action queue, candidatos, buckets
- `GET portfolio` + `GET account-summary` → KPIs y posiciones
- `GET decision-studies` → join tesis (opinión, geometría honesta)
- `GET operational-incidents/active` → banner incidente
- `GET ops-self-eval` → recon para incident workflow

Proyecciones shared: `mesa-hoy-model.ts`, `mapMesaStatusDimensions`.

## 4. Status en 3 dimensiones (presentación)

Tesis / Operativa / Posición — **no amplía** `JournalStudyUserStatus`.

## 5. Consecuencias

- Nav diario: `Mesa · Hoy` → Trading → Señales → Confirmar → Libro
- `/` redirige a `/mesa`
- Hoy strip en Trading: top-3 + link a Mesa
- Consola ops → menú Herramientas
- Confirm sigue siendo única firma; candidatos nunca muestran [COMPRAR]

## 6. Fuera de alcance V1.15

- Refactor `decision_journal_studies.py`
- Paginación UI studies/history
- Evolución opinión+fuerza (V1.16)
