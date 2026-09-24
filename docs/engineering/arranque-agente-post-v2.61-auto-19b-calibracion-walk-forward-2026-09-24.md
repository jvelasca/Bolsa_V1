# Arranque del agente siguiente — tras `v2.61-beta` (`AUTO-19B`) · 2026-09-24

**Estás aquí:** `AUTO-19B` (calibración del intervalo + walk-forward) está **cerrada y sellada** en
`v2.61-beta` / `1.86.0-beta`. **El sello del reparto NO se ha movido: sigue `auto18-v1`.** El flag
Adaptive sigue **OFF** por defecto.

**Lee primero (en este orden):**

1. [`PROJECT_STATE.md`](./PROJECT_STATE.md) — el estado vivo y la cadena de relevos.
2. El [plan de la fase](./plan-v2-61-auto-19b-calibracion-walk-forward-2026-09-24.md) — qué se quiso
   medir y con qué límites.
3. El [audit-pack](./audit-pack-v2-61-auto-19b-calibracion-walk-forward-2026-09-24.md) — qué se midió
   de verdad (y qué **no**).
4. El [relevo](./traspaso-relevo-post-v2.61-auto-19b-calibracion-walk-forward-2026-09-24.md).

## Qué queda abierto (y en qué orden tiene sentido atacarlo)

1. **Material PAPER real.** El instrumento está listo; el fixture sigue siendo **sintético y
   declarado**. El siguiente paso operativo es volcar ciclos PAPER reales al JSON del CLI
   (`scripts/research/auto_replay_battery.py --walk-forward --cycles ...`) y **leer** el reporte de
   calibración. Es ahí —y solo ahí— donde la cobertura empieza a hablar de la estrategia.
2. **`P(R > 0)`.** Declarado fuera de `v2.61`. Antes de añadirlo, decide si entra como pregunta propia
   del replay/calibración (con su `sample` y su nivel) o si requiere antes un modelo de retorno.
3. **Correlación entre estrategias.** También fuera de alcance: sin ella, el reparto por celda trata
   cada estrategia como independiente.
4. **Current-regime gating.** El walk-forward mide regímenes pasados; gatear por el régimen actual es
   una decisión distinta y no está implementada.

## Reglas de la casa que no cambian

- **Evidencia read-only.** El instrumento de calibración **no** toca el reparto (`auto18-v1`), el
  plan, el journal durable, el gobernador ni la tabla estado→efecto.
- **Sin muestra no hay veredicto.** `inconclusive`, nunca `supported` inventado.
- **Compuertas con el comando de CI.** `ruff check packages/py apps/api-python --config pyproject.toml`;
  el `mypy` exacto del YAML; `lint-imports --config packages/py/.importlinter`. Tests con
  `uv run --no-sync python -m pytest` (en esta máquina `uv run pytest` lo bloquea la directiva de
  Control de aplicaciones).
- **Matriz de mutaciones completa** antes de sellar: `uv run --no-sync python
  apps/api-python/scripts/v2_44_mutation_audit.py`, con restauración byte a byte y huella `git status`
  idéntica.
- **`*.md` sin `prettier`**; `governor.json` sin trackear; `main` en fast-forward y tag anotado.

## Lo que NO debes repetir

- No confundir «el instrumento mide» con «la estrategia funciona»: el fixture por defecto es
  **sintético**. Dilo siempre que publiques un número.
- No mover el sello del reparto «porque ahora hay calibración»: la calibración es **evidencia**, no un
  permiso de sizing.
- No tocar `auto_adaptive_journal.py` ni el gobernador en una fase de medición.
