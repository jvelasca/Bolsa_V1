# Evidencia S1 — OPERATIVA y Asesor (2026-11-12)

Evidencia **textual** del antes/después del vocabulario de recomendación. Las capturas
completas quedan para S5; aquí se registra lo que cambia en el primer nivel y lo que las
guardas impiden que vuelva.

**Alcance:** `Δ motor = 0` · `Δ decisión = 0` · sin migración · sin `contract:gen`.
El "antes" se leyó del árbol de trabajo con los cambios de la 067 sin sellar; **no** se
commitea nada en S1.

## OPERATIVA · bloque de recomendación

Fichero: `apps/web/src/features/trading/operativa-dictamen.tsx`.

| Antes | Después |
| --- | --- |
| Kicker «Postura sugerida hoy» | «Recomendación» |
| `buy` / `hold_watch` / `overbought`… como texto | Comprar / Mantener / Sin respaldo… |
| Motivos en `snake_case` (`top_low · io_medium`) | «Estrategia del Lab sin respaldo · Calidad de señal sin señal de compra» |
| «★ dictamen ≠ ★ TOP» | Prosa: la ★ mide la recomendación del día, no la estrategia del Lab |
| `no_trade` siempre «No operar» | «No evaluable · Cartera sin medir» si la cartera no se midió |
| IO `null` → ★3 aparente | «Sin medir» en confianza y en ★ |
| Sin tope de motivos | Máx. 3 visibles; el resto en tooltip con `(+N)` |

## Asesor · Opiniones de hoy

Fichero: `apps/web/src/features/research/asesor-opiniones-panel.tsx`.

| Antes | Después |
| --- | --- |
| Cabecera de tabla «Stance» | «Recomendación» |
| `INSTRUMENT_DAILY_OPINION_STANCE_LABELS` con «Vigilar»/«Sobrecomprado» | Denominaciones canónicas |
| `item.reasons.slice(0, 2).join(" · ")` | `visibleReasons` traducido |
| «BUY-alarma» | «Comprar · alarma» |
| «Thaw P3≥70% / P4≥55%» visible | «Criterio de mejora del estudio sin activar AUTO» + detalle en tooltip |
| «(N en silencio · hold/no_trade)» | «(N sin aviso)» |
| «Mapa fijo §5.2 (`opinion-channel-map`)» | «Canal asignado por recomendación y ★» |
| «★ dictamen ≠ ★ TOP» | Retirado del copy |

## Estudio · Operativa diaria

Fichero: `apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx`.

| Antes | Después |
| --- | --- |
| `value.opinion.stance` en crudo | `marketStanceLabelFromKey` (por causa en `no_trade`) |
| `canal alarma` | `Alarma` (etiqueta del mapa de canales) |
| `reasons.join(" · ")` | `visibleReasons` traducido |

## Instrumento · evolución del dictamen

Fichero: `apps/web/src/features/instruments/instrument-dictamen-evolution.tsx`.

| Antes | Después |
| --- | --- |
| `reasonHint` = `reasons.slice(0,2).join(", ")` | Etiquetas traducidas de la tabla |
| `★{dictamenStars}` aunque el IO fuera `null` | «Sin medir» cuando no hay medición |
| «★ dictamen ≠ ★ TOP» | «La ★ mide la recomendación del día; no es la de la estrategia del Lab» |

## Email de alarmas

Fichero: `packages/py/infrastructure/src/bolsa_infrastructure/alerts/estudio_opinion_email.py`.

Cuerpo antes: `- BBVA · buy ★5 · asOf=… · strong_buy_signal; top_high`.

Cuerpo después: `- BBVA · Comprar ★★★★★ · asOf=… · Señal de compra fuerte; Estrategia
del Lab con respaldo alto`. Con `io_score is None` la ★ se declara «Sin medir».

## Cómo se verifica

- `pnpm --filter @bolsa/shared test` — `market-vocabulary.test.ts` (totalidad, sin
  `snake_case`, `Sin respaldo`, `Comprar`/Lab, `No evaluable`, `Mixta` ≠ `Lateral`).
- `pnpm --filter @bolsa/web test -- operativa-recomendacion-vocabulary` — render de las 7
  posturas sin clave interna y textos retirados fuera de las superficies.
- `python -m pytest packages/py/infrastructure/tests/test_estudio_opinion_email_notify.py -q`
  — cuerpo sin claves crudas.
- `git diff --exit-code -- packages/py/application/src/bolsa_application/daily_opinion_stance.py`
  — el motor no se toca.
