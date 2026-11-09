/**
 * Reglas PURAS del validador de la medicion PAPER (`scripts/window-measurement-check.mjs`).
 *
 * Por que existe
 * --------------
 * Un CI GREEN y un `freeze OK` no dicen nada sobre la eficacia de AUTO: la medicion
 * solo vale si (a) se ejecuto sobre el arbol sellado, (b) termino con `forward.json`,
 * (c) los ticks son turnos evaluables y no `idle` ciegos, (d) la cobertura se declara
 * frente al universo operable y (e) hay ciclos CERRADOS. Estas funciones leen los
 * artefactos durables ya existentes y emiten un dictamen; no ejecutan la ventana.
 *
 * Doctrina de huecos
 * -----------------
 * `UNKNOWN != 0`. Un dato ausente se declara `UNKNOWN` (hueco) y **nunca** se rellena
 * con un cero medido. Un cero solo es dato cuando el artefacto lo dice explicitamente.
 *
 * Este modulo es PURO: no toca `git`, ni el sistema de ficheros, ni PostgreSQL. El CLI
 * (`scripts/window-measurement-check.mjs`) resuelve el material y llama aqui.
 */
import { WINDOW_CONFIG } from "./window-forward.mjs";

/** Umbrales de la ventana (ADR-046). Rebajarlos es un fallo duro del validador. */
export const REQUIRED_THRESHOLDS = Object.freeze({
  days: 4,
  episodes: 2,
  measurableCycles: 32,
});

export const CHECK_STATUS = Object.freeze({
  OK: "OK",
  WARN: "WARN",
  FAIL: "FAIL",
  UNKNOWN: "UNKNOWN",
});

export const VERDICT = Object.freeze({
  GREEN: "GREEN",
  INCONCLUSIVE: "INCONCLUSIVE",
  PREMATURE_TERMINATION: "PREMATURE_TERMINATION",
  INVALID: "INVALID",
  UNKNOWN: "UNKNOWN",
});

/** @param {unknown} value */
function num(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** @param {unknown} value */
function text(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

/** @param {unknown} value */
function short(value) {
  return value ? String(value).slice(0, 8) : "null";
}

/**
 * @param {string} id
 * @param {string} title
 * @param {string} status
 * @param {string} detail
 * @param {{ hard?: boolean, code?: string }} [extra]
 */
function check(id, title, status, detail, extra = {}) {
  return { id, title, status, detail, ...extra };
}

/**
 * S1 - identidad del sello. Los tree hashes son la autoridad del freeze; la etiqueta
 * `commit` del pin es procedencia informativa (misma doctrina que `freezeStatus()` de
 * `scripts/window-pin.mjs`).
 *
 * Una corrida ejecutada sobre otro arbol solo es fallo DURO si hay `forward-market`:
 * si la corrida no dejo medicion, la discrepancia de arbol es informativa y el
 * dictamen debe ser `PREMATURE_TERMINATION`, no `INVALID`.
 *
 * @param {{
 *   pin: typeof WINDOW_CONFIG,
 *   tag: string,
 *   tagTrees: {apps?: string, packages?: string} | null,
 *   tagCommit?: string | null,
 *   manifest?: any | null,
 *   forwardExists?: boolean,
 *   strictRunTree?: boolean,
 * }} input
 */
export function evaluateSeal({
  pin,
  tag,
  tagTrees,
  tagCommit = null,
  manifest = null,
  forwardExists = true,
  strictRunTree = true,
}) {
  const checks = [];
  const treesOk = Boolean(tagTrees?.apps && tagTrees?.packages);
  if (!treesOk) {
    checks.push(
      check(
        "S1.seal",
        `Arbol de ${tag} = pin`,
        CHECK_STATUS.FAIL,
        `no se pudo resolver ${tag}^{}:apps|packages (sello ausente o tag no presente)`,
        { hard: true, code: "SEAL_UNRESOLVED" },
      ),
    );
  } else {
    const appsOk = tagTrees.apps === pin.appsHash;
    const packagesOk = tagTrees.packages === pin.packagesHash;
    checks.push(
      check(
        "S1.seal",
        `Arbol de ${tag} = pin`,
        appsOk && packagesOk ? CHECK_STATUS.OK : CHECK_STATUS.FAIL,
        `apps ${short(tagTrees.apps)} / packages ${short(tagTrees.packages)} · ` +
          `pin ${short(pin.appsHash)} / ${short(pin.packagesHash)}`,
        appsOk && packagesOk ? {} : { hard: true, code: "TREE_MOVED" },
      ),
    );
  }

  const labelStale = Boolean(
    pin.commit && tagCommit && pin.commit !== tagCommit,
  );
  checks.push(
    check(
      "S1.label",
      "Etiqueta commit del pin",
      CHECK_STATUS.OK,
      labelStale
        ? `nota: etiqueta ${pin.commit} != tag ${short(tagCommit)}; el freeze real son los tree hashes`
        : `etiqueta ${pin.commit ?? "null"} coherente con el tag`,
    ),
  );

  if (!manifest) {
    checks.push(
      check(
        "S1.config",
        "Config congelada de la corrida",
        CHECK_STATUS.UNKNOWN,
        "sin manifest.json: la identidad de la corrida no se puede declarar",
      ),
    );
  } else {
    const freeze = manifest.freeze ?? {};
    const modeOk = text(manifest.configMode) === "frozen";
    const appsKnown = Boolean(freeze.apps);
    const packagesKnown = Boolean(freeze.packages);
    const appsOk = !appsKnown || freeze.apps === pin.appsHash;
    const packagesOk = !packagesKnown || freeze.packages === pin.packagesHash;
    const freezeOk = freeze.ok !== false;
    const ok = modeOk && appsOk && packagesOk && freezeOk;
    const configOk = modeOk && freezeOk;
    const detail =
      `configMode ${manifest.configMode ?? "null"} · freeze.ok ${freeze.ok ?? "null"} · ` +
      `apps ${short(freeze.apps)} / packages ${short(freeze.packages)}` +
      (appsOk && packagesOk
        ? ""
        : ` · pin ${short(pin.appsHash)} / ${short(pin.packagesHash)}`);
    let detailSuffix = "";
    if (!ok) {
      if (!strictRunTree)
        detailSuffix = " · modo historico: no se exige el arbol sellado";
      else if (!forwardExists)
        detailSuffix =
          " · corrida de otro arbol y sin forward-market: informativo";
    }
    checks.push(
      check(
        "S1.config",
        "Config congelada de la corrida",
        ok
          ? CHECK_STATUS.OK
          : strictRunTree
            ? CHECK_STATUS.FAIL
            : CHECK_STATUS.WARN,
        `${detail}${detailSuffix}`,
        ok
          ? {}
          : {
              hard: !configOk || (forwardExists && strictRunTree),
              code: "RUNTIME_NOT_FROZEN",
            },
      ),
    );
  }

  return checks;
}

/**
 * S2 - la corrida. Sin `forward-market-<day>.json` la medicion NO cuenta: es
 * terminacion prematura, no una corrida corta. Se distingue el error de uso del
 * fallo duro del proceso.
 *
 * @param {{ manifest?: any | null, forward?: any | null, forwardExists: boolean }} input
 */
export function evaluateRun({
  manifest = null,
  forward = null,
  forwardExists,
}) {
  if (!forwardExists) {
    const kind = manifest?.steps?.forward?.kind ?? null;
    const exit = manifest?.steps?.forward?.exit ?? null;
    const detail =
      text(kind) === "usage_error"
        ? `sin forward-market: la corrida termino por error de uso (exit ${exit}), no por el tope`
        : `sin forward-market: terminacion prematura (status ${manifest?.status ?? "desconocido"}` +
          `${manifest?.reason ? ` / ${manifest.reason}` : ""})`;
    return check("S2.run", "Corrida completa", CHECK_STATUS.FAIL, detail, {
      code: "PREMATURE_TERMINATION",
      premature: true,
    });
  }

  const stopReason = text(forward?.stopReason);
  if (!stopReason) {
    return check(
      "S2.run",
      "Corrida completa",
      CHECK_STATUS.UNKNOWN,
      "forward-market presente pero sin stopReason: no se declara completada",
    );
  }
  if (stopReason !== "completed") {
    return check(
      "S2.run",
      "Corrida completa",
      CHECK_STATUS.WARN,
      `forward-market presente con stopReason '${forward.stopReason}': la medicion no cuenta`,
      { premature: true, code: "STOPPED_EARLY" },
    );
  }
  return check(
    "S2.run",
    "Corrida completa",
    CHECK_STATUS.OK,
    "forward-market presente · stopReason completed",
  );
}

/**
 * S3 - ticks durables frente al tope declarado. Terminar antes del tope no invalida
 * el CI, pero si la medicion.
 *
 * @param {{ forward?: any | null, expectedTicks?: number | null }} input
 */
export function evaluateTicks({ forward = null, expectedTicks = null }) {
  if (!forward) {
    return check(
      "S3.ticks",
      "Ticks frente al tope",
      CHECK_STATUS.UNKNOWN,
      "sin forward-market: sin ticks que contar",
    );
  }
  const ticks = num(forward.ticks) ?? num(forward.sample?.ticks);
  if (ticks === null) {
    return check(
      "S3.ticks",
      "Ticks frente al tope",
      CHECK_STATUS.UNKNOWN,
      "ticks no declarados en el artefacto",
    );
  }
  const expected = num(expectedTicks);
  const decided = num(forward.turnTotals?.decided);
  const suffix = decided === null ? "" : ` · turnos decididos ${decided}`;
  if (expected === null) {
    return check(
      "S3.ticks",
      "Ticks frente al tope",
      CHECK_STATUS.OK,
      `${ticks} ticks (tope no declarado)${suffix}`,
    );
  }
  if (ticks < expected) {
    return check(
      "S3.ticks",
      "Ticks frente al tope",
      CHECK_STATUS.WARN,
      `${ticks}/${expected}: la corrida termino antes del tope${suffix}`,
    );
  }
  if (ticks > expected) {
    return check(
      "S3.ticks",
      "Ticks frente al tope",
      CHECK_STATUS.WARN,
      `${ticks}/${expected}: el tope declarado es menor que lo ejecutado${suffix}`,
    );
  }
  return check(
    "S3.ticks",
    "Ticks frente al tope",
    CHECK_STATUS.OK,
    `${ticks}/${expected} ticks${suffix}`,
  );
}

/**
 * S3b - ticks ciegos: recorridos sin barra del dia corriente. Un tick ciego NO es un
 * turno evaluable. Si el artefacto no lo declara, se devuelve UNKNOWN (hueco), nunca 0.
 *
 * @param {{ forward?: any | null, blindTicks?: number | null }} input
 */
export function evaluateBlindTicks({ forward = null, blindTicks = null }) {
  if (!forward) {
    return check(
      "S3.blind",
      "Ticks ciegos",
      CHECK_STATUS.UNKNOWN,
      "sin forward-market: sin material para medir",
    );
  }
  const resolved =
    num(blindTicks) ??
    num(forward.blindTicks) ??
    num(forward.sample?.blindTicks);
  if (resolved === null) {
    return check(
      "S3.blind",
      "Ticks ciegos",
      CHECK_STATUS.UNKNOWN,
      "no declarados en el artefacto: se declara hueco (no se asume 0)",
    );
  }
  const ticks = num(forward.ticks) ?? num(forward.sample?.ticks);
  if (resolved === 0) {
    return check(
      "S3.blind",
      "Ticks ciegos",
      CHECK_STATUS.OK,
      "0 ciegos declarados",
    );
  }
  const evaluable = ticks === null ? null : ticks - resolved;
  return check(
    "S3.blind",
    "Ticks ciegos",
    CHECK_STATUS.WARN,
    `${resolved} de ${ticks ?? "null"} sin barra del dia corriente: no son turnos` +
      (evaluable === null ? "" : ` (${evaluable} evaluables)`),
  );
}

/**
 * S4 - universo. El watch del ESTUDIO no es el universo operable: se declaran por
 * separado y la cobertura de barra se mide contra el tamano del ESTUDIO.
 *
 * @param {{
 *   forward?: any | null,
 *   coverageStart?: number | null,
 *   coverageMidnight?: number | null,
 * }} input
 */
export function evaluateUniverse({
  forward = null,
  coverageStart = null,
  coverageMidnight = null,
}) {
  if (!forward) {
    return check(
      "S4.universe",
      "Universo y cobertura",
      CHECK_STATUS.UNKNOWN,
      "sin forward-market: sin universo que medir",
    );
  }
  const watchSize =
    num(forward.watchSize) ??
    ((Array.isArray(forward.watchA) ? forward.watchA.length : 0) +
      (Array.isArray(forward.watchB) ? forward.watchB.length : 0) ||
      null);
  const operables = Object.values(
    forward.marketRegime?.operableBySymbol ?? {},
  ).filter(Boolean).length;
  const start =
    num(coverageStart) ??
    num(forward.coverageStart) ??
    num(forward.sample?.coverageStart);
  const midnight =
    num(coverageMidnight) ??
    num(forward.coverageMidnight) ??
    num(forward.sample?.coverageMidnight);
  const source = text(forward.watchSource);

  const parts = [
    `ESTUDIO ${watchSize ?? "null"}`,
    `operables ${operables}`,
    `cobertura arranque ${start ?? "null"}/${watchSize ?? "null"}`,
    `medianoche ${midnight ?? "null"}/${watchSize ?? "null"}`,
  ];
  if (source && source !== "estudio")
    parts.push(`watchSource ${forward.watchSource}`);

  if (start === null && midnight === null) {
    return check(
      "S4.universe",
      "Universo y cobertura",
      CHECK_STATUS.UNKNOWN,
      `${parts.join(" · ")} · cobertura no declarada: hueco, no cero`,
    );
  }
  const full =
    watchSize !== null &&
    start !== null &&
    midnight !== null &&
    start >= watchSize &&
    midnight >= watchSize;
  const sourceOk = !source || source === "estudio";
  const ok = full && sourceOk;
  const notes = [];
  if (!full) notes.push("cobertura parcial del universo ESTUDIO");
  if (!sourceOk) notes.push("watchSource distinto de ESTUDIO");
  return check(
    "S4.universe",
    "Universo y cobertura",
    ok ? CHECK_STATUS.OK : CHECK_STATUS.WARN,
    `${parts.join(" · ")}${notes.length > 0 ? ` · ${notes.join("; ")}` : ""}`,
  );
}

/**
 * S5 - ciclos cerrados. Es la unica prueba de eficacia: fills o posiciones abiertas no
 * son ciclos. Un export vacio (bloqueado por `paper_cycles_export.py`) es hueco
 * declarado, no fallo del validador.
 *
 * @param {{
 *   forward?: any | null,
 *   certification?: any | null,
 *   cyclesExport?: { present?: boolean, empty?: boolean, count?: number | null } | null,
 * }} input
 */
export function evaluateCycles({
  forward = null,
  certification = null,
  cyclesExport = null,
}) {
  const facts = forward?.readiness?.facts ?? {};
  const sample = forward?.sample ?? {};
  const cert = certification?.certification ?? certification ?? {};

  const closed = num(facts.closedCycles) ?? num(sample.closedCycles);
  const measurable =
    num(sample.measurableCycles) ??
    num(facts.measurableCycles) ??
    num(cert.measurableCycles);
  const episodes = num(cert.episodes);
  const perVersion = sample.perVersion ?? facts.perVersion ?? null;

  let exportNote = "";
  if (cyclesExport) {
    if (cyclesExport.present === false)
      exportNote = " · export de ciclos ausente";
    else if (cyclesExport.empty)
      exportNote =
        " · export bloqueado (fichero vacio): no hay ciclos cerrados con fill durable";
    else if (cyclesExport.count !== null && cyclesExport.count !== undefined) {
      exportNote = ` · export ${cyclesExport.count} ciclos`;
    }
  }

  if (closed === null && measurable === null) {
    return check(
      "S5.cycles",
      "Ciclos cerrados",
      CHECK_STATUS.UNKNOWN,
      `sin bloque de ciclos en el artefacto: hueco declarado${exportNote}`,
    );
  }

  const detail =
    `cerrados ${closed ?? "null"} · medibles ${measurable ?? "null"}/${REQUIRED_THRESHOLDS.measurableCycles} · ` +
    `episodios ${episodes ?? "null"}/${REQUIRED_THRESHOLDS.episodes}` +
    (perVersion && typeof perVersion === "object"
      ? ` · perVersion ${JSON.stringify(perVersion)}`
      : "") +
    exportNote;

  if (closed === 0) {
    return check(
      "S5.cycles",
      "Ciclos cerrados",
      CHECK_STATUS.WARN,
      `${detail} · 0 ciclos: sin evidencia de eficacia`,
    );
  }
  if (
    measurable !== null &&
    measurable < REQUIRED_THRESHOLDS.measurableCycles
  ) {
    return check(
      "S5.cycles",
      "Ciclos cerrados",
      CHECK_STATUS.WARN,
      `${detail} · ciclos medibles insuficientes`,
    );
  }
  if (closed === null) {
    return check(
      "S5.cycles",
      "Ciclos cerrados",
      CHECK_STATUS.UNKNOWN,
      `${detail} · ciclos cerrados no declarados: hueco`,
    );
  }
  return check("S5.cycles", "Ciclos cerrados", CHECK_STATUS.OK, detail);
}

/**
 * S6a - umbrales. Rebajar `minDays`/`minEpisodes`/`minCycles` es fallo duro: cambia el
 * contrato de la certificacion, no la medicion.
 *
 * @param {{ certification?: any | null }} input
 */
export function evaluateThresholds({ certification = null }) {
  if (!certification) {
    return check(
      "S6.thresholds",
      "Umbrales sin rebajar",
      CHECK_STATUS.UNKNOWN,
      "sin certificacion: no hay umbrales que contrastar",
    );
  }
  const cert = certification.certification ?? certification;
  const thresholds = cert.thresholds ?? {};
  const pairs = [
    ["days", "days"],
    ["episodes", "episodes"],
    ["measurableCycles", "measurableCycles"],
  ];
  const rebajados = [];
  for (const [field, key] of pairs) {
    const value = num(thresholds[field]);
    if (value !== null && value < REQUIRED_THRESHOLDS[key])
      rebajados.push(`${field} ${value}<${REQUIRED_THRESHOLDS[key]}`);
  }
  if (rebajados.length > 0) {
    return check(
      "S6.thresholds",
      "Umbrales sin rebajar",
      CHECK_STATUS.FAIL,
      `umbral rebajado: ${rebajados.join(", ")}`,
      { hard: true, code: "THRESHOLD_RELAXED" },
    );
  }
  return check(
    "S6.thresholds",
    "Umbrales sin rebajar",
    CHECK_STATUS.OK,
    `days ${REQUIRED_THRESHOLDS.days} / episodes ${REQUIRED_THRESHOLDS.episodes} / cycles ${REQUIRED_THRESHOLDS.measurableCycles}`,
  );
}

/**
 * S6b - criterio `days`. Un dia sin sesion no es un dia de ventana.
 *
 * @param {{ certification?: any | null }} input
 */
export function evaluateDayList({ certification = null }) {
  if (!certification) {
    return check(
      "S6.days",
      "Dias con sesion",
      CHECK_STATUS.UNKNOWN,
      "sin certificacion: sin dayList",
    );
  }
  const cert = certification.certification ?? certification;
  const dayList = Array.isArray(cert.dayList) ? cert.dayList : [];
  if (dayList.length === 0) {
    return check(
      "S6.days",
      "Dias con sesion",
      CHECK_STATUS.UNKNOWN,
      "dayList vacio: hueco declarado",
    );
  }
  const sinSesion = dayList.filter((day) => !isMarketDayIso(day));
  if (sinSesion.length > 0) {
    return check(
      "S6.days",
      "Dias con sesion",
      CHECK_STATUS.WARN,
      `${dayList.length} dias, ${sinSesion.length} sin sesion (${sinSesion.join(", ")}) contados como ventana`,
    );
  }
  return check(
    "S6.days",
    "Dias con sesion",
    CHECK_STATUS.OK,
    `${dayList.length} dias, todos con sesion`,
  );
}

/**
 * ¿La fecha ISO `YYYY-MM-DD` cae en dia de mercado? Se evalua en UTC a mediodia para
 * no depender de la zona horaria de la maquina.
 * @param {unknown} iso
 */
export function isMarketDayIso(iso) {
  const match = String(iso ?? "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return true; // formato inesperado: no se acusa un dia sin sesion
  const date = new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12),
  );
  const weekday = date.getUTCDay();
  return weekday !== 0 && weekday !== 6;
}

/**
 * Dictamen final a partir de las comprobaciones y de los hechos medidos.
 *
 * Precedencia: fallo duro (sello/umbral) > terminacion prematura > GREEN >
 * INCONCLUSIVE. `GREEN` exige ciclos cerrados y umbrales cumplidos; un `0` de ciclos
 * nunca puede producir `GREEN`.
 *
 * @param {Array<ReturnType<typeof check>>} checks
 * @param {{
 *   materialPresent?: boolean,
 *   premature?: boolean,
 *   closedCycles?: number | null,
 *   measurableCycles?: number | null,
 *   episodes?: number | null,
 * }} [facts]
 */
export function buildVerdict(checks, facts = {}) {
  if (checks.some((item) => item.status === CHECK_STATUS.FAIL && item.hard)) {
    return { verdict: VERDICT.INVALID, exitCode: 1 };
  }
  if (facts.materialPresent === false) {
    return { verdict: VERDICT.UNKNOWN, exitCode: 2 };
  }
  const premature =
    facts.premature === true ||
    checks.some(
      (item) => item.code === "PREMATURE_TERMINATION" || item.premature,
    );
  if (premature) {
    return { verdict: VERDICT.PREMATURE_TERMINATION, exitCode: 0 };
  }
  const closed = num(facts.closedCycles);
  const measurable = num(facts.measurableCycles);
  const episodes = num(facts.episodes);
  const thresholdsMet =
    (measurable === null ||
      measurable >= REQUIRED_THRESHOLDS.measurableCycles) &&
    (episodes === null || episodes >= REQUIRED_THRESHOLDS.episodes) &&
    (closed === null || closed > 0);
  if (closed !== null && closed > 0 && thresholdsMet) {
    return { verdict: VERDICT.GREEN, exitCode: 0 };
  }
  return { verdict: VERDICT.INCONCLUSIVE, exitCode: 0 };
}

/**
 * Extrae los hechos que alimentan el dictamen de un paquete de artefactos.
 *
 * @param {{ forward?: any | null, certification?: any | null, manifest?: any | null }} input
 */
export function collectFacts({
  forward = null,
  certification = null,
  manifest = null,
}) {
  const cert = certification?.certification ?? certification ?? {};
  const facts = forward?.readiness?.facts ?? {};
  const sample = forward?.sample ?? {};
  return {
    materialPresent: Boolean(forward || certification || manifest),
    closedCycles: num(facts.closedCycles) ?? num(sample.closedCycles),
    measurableCycles:
      num(sample.measurableCycles) ??
      num(facts.measurableCycles) ??
      num(cert.measurableCycles),
    episodes: num(cert.episodes),
    premature: false,
  };
}

/**
 * Evalua todo el paquete y devuelve las comprobaciones, los hechos y el dictamen.
 *
 * @param {{
 *   pin: typeof WINDOW_CONFIG,
 *   tag: string,
 *   tagTrees: {apps?: string, packages?: string} | null,
 *   tagCommit?: string | null,
 *   day: string,
 *   expectedTicks?: number | null,
 *   blindTicks?: number | null,
 *   coverageStart?: number | null,
 *   coverageMidnight?: number | null,
 *   manifest?: any | null,
 *   forward?: any | null,
 *   forwardExists: boolean,
 *   certification?: any | null,
 *   cyclesExport?: { present?: boolean, empty?: boolean, count?: number | null } | null,
 *   strictRunTree?: boolean,
 * }} input
 */
export function evaluateMeasurement(input) {
  const {
    pin,
    tag,
    tagTrees,
    tagCommit = null,
    strictRunTree = true,
    expectedTicks = null,
    blindTicks = null,
    coverageStart = null,
    coverageMidnight = null,
    manifest = null,
    forward = null,
    forwardExists,
    certification = null,
    cyclesExport = null,
  } = input;

  const checks = [
    ...evaluateSeal({
      pin,
      tag,
      tagTrees,
      tagCommit,
      manifest,
      forwardExists,
      strictRunTree,
    }),
    evaluateRun({ manifest, forward, forwardExists }),
    evaluateTicks({ forward, expectedTicks }),
    evaluateBlindTicks({ forward, blindTicks }),
    evaluateUniverse({ forward, coverageStart, coverageMidnight }),
    evaluateCycles({ forward, certification, cyclesExport }),
    evaluateThresholds({ certification }),
    evaluateDayList({ certification }),
  ];

  const facts = collectFacts({ forward, certification, manifest });
  facts.premature = checks.some(
    (item) => item.code === "PREMATURE_TERMINATION" || item.premature === true,
  );
  const verdict = buildVerdict(checks, facts);
  return { checks, facts, ...verdict };
}

/** @param {Array<ReturnType<typeof check>>} checks */
export function summarizeChecks(checks) {
  const summary = { OK: 0, WARN: 0, FAIL: 0, UNKNOWN: 0 };
  for (const item of checks) {
    if (summary[item.status] !== undefined) summary[item.status] += 1;
  }
  return summary;
}
