/**
 * Regresiones del validador de la medicion PAPER.
 *
 * Reglas que se protegen (muerden de verdad):
 *   - los tree hashes del tag mandan: un arbol distinto es `INVALID`, no un WARN;
 *   - sin `forward-market` no hay medicion: `PREMATURE_TERMINATION`;
 *   - 0 ciclos cerrados NUNCA puede producir `GREEN`;
 *   - un dato ausente es `UNKNOWN`, jamas un 0 de relleno;
 *   - umbrales rebajados son fallo duro;
 *   - el criterio `days` que cuenta un sabado se declara WARN.
 *
 * Ejecutar: `node --test scripts/lib/window-measurement-check.test.mjs`.
 */
import test from "node:test";
import assert from "node:assert/strict";

import {
  CHECK_STATUS,
  VERDICT,
  evaluateMeasurement,
  isMarketDayIso,
} from "./window-measurement-check.mjs";
import { WINDOW_CONFIG } from "./window-forward.mjs";

const PIN = WINDOW_CONFIG;

const manifestOk = {
  day: "20261109",
  status: "OK",
  configMode: "FROZEN",
  commit: "a5013f75",
  freeze: {
    ok: true,
    apps: PIN.appsHash,
    packages: PIN.packagesHash,
    expectedApps: PIN.appsHash,
    expectedPackages: PIN.packagesHash,
  },
};

const certificationOk = {
  certification: {
    days: 4,
    episodes: 2,
    measurableCycles: 32,
    dayList: ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"],
    thresholds: { days: 4, episodes: 2, measurableCycles: 32 },
    verdict: "GREEN",
    ready: true,
  },
};

function forwardOk(overrides = {}) {
  return {
    ticks: 400,
    stopReason: "completed",
    watchSize: 181,
    watchSource: "estudio",
    watchA: ["a"],
    watchB: ["b"],
    turnTotals: { decided: 32000 },
    marketRegime: { operableBySymbol: { a: true, b: false } },
    readiness: { facts: { closedCycles: 32 } },
    sample: {
      ticks: 400,
      closedCycles: 32,
      measurableCycles: 32,
      coverageStart: 181,
      coverageMidnight: 181,
      perVersion: { "v283-window-a": 16, "v283-window-b": 16 },
    },
    ...overrides,
  };
}

function evaluate({
  forward = null,
  manifest = manifestOk,
  certification = null,
  ...rest
} = {}) {
  return evaluateMeasurement({
    pin: PIN,
    tag: "v2.88.186-beta",
    tagTrees: { apps: PIN.appsHash, packages: PIN.packagesHash },
    tagCommit: "a5013f75",
    expectedTicks: 400,
    manifest,
    forward,
    forwardExists: Boolean(forward),
    certification,
    cyclesExport: null,
    ...rest,
  });
}

function byId(result, id) {
  return result.checks.find((item) => item.id === id);
}

// ---------------------------------------------------------------------------
// S1 - identidad del sello
// ---------------------------------------------------------------------------

test("S1: el arbol del tag coincide con el pin y la etiqueta stale es solo una nota", () => {
  const result = evaluate({
    forward: forwardOk(),
    certification: certificationOk,
  });
  assert.equal(byId(result, "S1.seal").status, CHECK_STATUS.OK);
  // `pin.commit` es `a81be599` y el tag es `a5013f75`: nota informativa, no fallo.
  assert.equal(byId(result, "S1.label").status, CHECK_STATUS.OK);
  assert.match(byId(result, "S1.label").detail, /etiqueta/);
});

test("S1: TREE_MOVED es fallo duro e invalida la medicion", () => {
  const result = evaluate({
    forward: forwardOk(),
    certification: certificationOk,
    tagTrees: { apps: "f".repeat(40), packages: PIN.packagesHash },
  });
  assert.equal(byId(result, "S1.seal").status, CHECK_STATUS.FAIL);
  assert.equal(byId(result, "S1.seal").code, "TREE_MOVED");
  assert.equal(result.verdict, VERDICT.INVALID);
  assert.equal(result.exitCode, 1);
});

test("S1: sello no resoluble es INVALID", () => {
  const result = evaluate({
    forward: forwardOk(),
    certification: certificationOk,
    tagTrees: null,
  });
  assert.equal(byId(result, "S1.seal").status, CHECK_STATUS.FAIL);
  assert.equal(result.verdict, VERDICT.INVALID);
});

test("S1: una corrida no congelada es fallo duro", () => {
  const result = evaluate({
    forward: forwardOk(),
    certification: certificationOk,
    manifest: { ...manifestOk, configMode: "ENV_OVERRIDE" },
  });
  assert.equal(byId(result, "S1.config").status, CHECK_STATUS.FAIL);
  assert.equal(byId(result, "S1.config").code, "RUNTIME_NOT_FROZEN");
  assert.equal(result.verdict, VERDICT.INVALID);
});

test("S1: corrida de otro arbol SIN forward es informativa (dictamen prematuro, no INVALID)", () => {
  const result = evaluate({
    forward: null,
    certification: null,
    manifest: {
      ...manifestOk,
      freeze: {
        ...manifestOk.freeze,
        apps: "0c64a5602e45df7b225a49551cd81d304cdd336e",
      },
    },
  });
  const config = byId(result, "S1.config");
  assert.equal(config.status, CHECK_STATUS.FAIL);
  assert.equal(config.hard, false);
  assert.match(config.detail, /informativo/);
  assert.equal(result.verdict, VERDICT.PREMATURE_TERMINATION);
});

test("S1: en modo historico el arbol distinto es WARN y no invalida el dictamen", () => {
  const forward = forwardOk({
    readiness: { facts: { closedCycles: 0 } },
    sample: { ...forwardOk().sample, closedCycles: 0, measurableCycles: 0 },
  });
  const result = evaluate({
    forward,
    certification: {
      certification: {
        ...certificationOk.certification,
        episodes: 0,
        measurableCycles: 0,
        verdict: "INCONCLUSIVE",
        ready: false,
      },
    },
    manifest: {
      ...manifestOk,
      freeze: {
        ...manifestOk.freeze,
        apps: "0c64a5602e45df7b225a49551cd81d304cdd336e",
      },
    },
    strictRunTree: false,
  });
  assert.equal(byId(result, "S1.config").status, CHECK_STATUS.WARN);
  assert.match(byId(result, "S1.config").detail, /modo historico/);
  assert.equal(result.verdict, VERDICT.INCONCLUSIVE);
});

test("S1: corrida de otro arbol CON forward es fallo duro", () => {
  const result = evaluate({
    forward: forwardOk(),
    certification: certificationOk,
    manifest: {
      ...manifestOk,
      freeze: {
        ...manifestOk.freeze,
        apps: "0c64a5602e45df7b225a49551cd81d304cdd336e",
      },
    },
  });
  assert.equal(byId(result, "S1.config").status, CHECK_STATUS.FAIL);
  assert.equal(result.verdict, VERDICT.INVALID);
});

// ---------------------------------------------------------------------------
// S2 - terminacion
// ---------------------------------------------------------------------------

test("S2: sin forward-market la medicion no cuenta (terminacion prematura)", () => {
  const result = evaluate({
    forward: null,
    certification: null,
    manifest: {
      ...manifestOk,
      status: "HARD_ERROR",
      reason: "FORWARD_ERROR",
      steps: { forward: { exit: 1, ok: false, kind: "usage_error" } },
    },
  });
  const run = byId(result, "S2.run");
  assert.equal(run.status, CHECK_STATUS.FAIL);
  assert.equal(run.code, "PREMATURE_TERMINATION");
  assert.match(run.detail, /error de uso/);
  assert.equal(result.verdict, VERDICT.PREMATURE_TERMINATION);
  assert.equal(result.exitCode, 0);
});

test("S2: un stopReason distinto de completed declara la corrida parada", () => {
  const result = evaluate({
    forward: forwardOk({ stopReason: "premature" }),
    certification: certificationOk,
  });
  assert.equal(byId(result, "S2.run").status, CHECK_STATUS.WARN);
  assert.equal(result.verdict, VERDICT.PREMATURE_TERMINATION);
});

// ---------------------------------------------------------------------------
// S3 - ticks
// ---------------------------------------------------------------------------

test("S3: menos ticks que el tope y ticks ciegos declarados son WARN, no ceros", () => {
  const result = evaluate({
    forward: forwardOk({ ticks: 292, blindTicks: 263 }),
    certification: certificationOk,
  });
  assert.equal(byId(result, "S3.ticks").status, CHECK_STATUS.WARN);
  assert.match(byId(result, "S3.ticks").detail, /292\/400/);
  assert.equal(byId(result, "S3.blind").status, CHECK_STATUS.WARN);
  assert.match(byId(result, "S3.blind").detail, /29 evaluables/);
});

test("S3: sin dato de ticks ciegos el estado es UNKNOWN, no 0", () => {
  const result = evaluate({
    forward: forwardOk(),
    certification: certificationOk,
  });
  assert.equal(byId(result, "S3.blind").status, CHECK_STATUS.UNKNOWN);
  assert.match(byId(result, "S3.blind").detail, /hueco/);
});

// ---------------------------------------------------------------------------
// S4 - universo
// ---------------------------------------------------------------------------

test("S4: cobertura parcial del ESTUDIO es WARN y nunca se presenta como operable", () => {
  const forward = forwardOk({
    sample: { ...forwardOk().sample, coverageStart: 62, coverageMidnight: 84 },
  });
  const result = evaluate({ forward, certification: certificationOk });
  const cosmos = byId(result, "S4.universe");
  assert.equal(cosmos.status, CHECK_STATUS.WARN);
  assert.match(cosmos.detail, /ESTUDIO 181/);
  assert.match(cosmos.detail, /operables 1/);
  assert.match(cosmos.detail, /62\/181/);
});

test("S4: cobertura no declarada es UNKNOWN", () => {
  const forward = forwardOk({
    sample: { ticks: 400, closedCycles: 32, measurableCycles: 32 },
  });
  const result = evaluate({ forward, certification: certificationOk });
  assert.equal(byId(result, "S4.universe").status, CHECK_STATUS.UNKNOWN);
});

// ---------------------------------------------------------------------------
// S5 - ciclos
// ---------------------------------------------------------------------------

test("S5: 0 ciclos cerrados nunca produce GREEN", () => {
  const forward = forwardOk({
    readiness: { facts: { closedCycles: 0 } },
    sample: { ...forwardOk().sample, closedCycles: 0, measurableCycles: 0 },
  });
  const certification = {
    certification: {
      ...certificationOk.certification,
      days: 4,
      episodes: 0,
      measurableCycles: 0,
      verdict: "INCONCLUSIVE",
      ready: false,
    },
  };
  const result = evaluate({ forward, certification });
  assert.equal(byId(result, "S5.cycles").status, CHECK_STATUS.WARN);
  assert.match(byId(result, "S5.cycles").detail, /0 ciclos/);
  assert.equal(result.verdict, VERDICT.INCONCLUSIVE);
  assert.equal(result.exitCode, 0);
});

test("S5: sin bloque de ciclos es UNKNOWN y el export vacio se declara bloqueado", () => {
  const forward = forwardOk({ readiness: {}, sample: { ticks: 400 } });
  const result = evaluate({
    forward,
    certification: {
      certification: {
        days: 4,
        episodes: null,
        measurableCycles: null,
        dayList: [],
        thresholds: {},
      },
    },
    cyclesExport: { present: true, empty: true, count: null },
  });
  assert.equal(byId(result, "S5.cycles").status, CHECK_STATUS.UNKNOWN);
  assert.match(byId(result, "S5.cycles").detail, /hueco declarado/);
  assert.match(byId(result, "S5.cycles").detail, /bloqueado/);
  assert.equal(result.verdict, VERDICT.INCONCLUSIVE);
});

// ---------------------------------------------------------------------------
// S6 - umbrales y dias
// ---------------------------------------------------------------------------

test("S6: umbrales rebajados son fallo duro", () => {
  const certification = {
    certification: {
      ...certificationOk.certification,
      thresholds: { days: 4, episodes: 1, measurableCycles: 10 },
    },
  };
  const result = evaluate({ forward: forwardOk(), certification });
  assert.equal(byId(result, "S6.thresholds").status, CHECK_STATUS.FAIL);
  assert.equal(byId(result, "S6.thresholds").code, "THRESHOLD_RELAXED");
  assert.equal(result.verdict, VERDICT.INVALID);
});

test("S6: un sabado en dayList se declara WARN (deuda del criterio days)", () => {
  const certification = {
    certification: {
      ...certificationOk.certification,
      dayList: [...certificationOk.certification.dayList, "2026-11-07"],
    },
  };
  const result = evaluate({ forward: forwardOk(), certification });
  assert.equal(byId(result, "S6.days").status, CHECK_STATUS.WARN);
  assert.match(byId(result, "S6.days").detail, /2026-11-07/);
});

test("S6: isMarketDayIso no depende de la zona horaria de la maquina", () => {
  assert.equal(isMarketDayIso("2026-11-09"), true); // lunes
  assert.equal(isMarketDayIso("2026-11-07"), false); // sabado
  assert.equal(isMarketDayIso("2026-11-08"), false); // domingo
  assert.equal(isMarketDayIso("no-es-fecha"), true);
});

// ---------------------------------------------------------------------------
// Dictamen completo
// ---------------------------------------------------------------------------

test("dictamen GREEN sintetico: solo con ciclos cerrados y umbrales cumplidos", () => {
  const result = evaluate({
    forward: forwardOk(),
    certification: certificationOk,
  });
  assert.equal(result.verdict, VERDICT.GREEN);
  assert.equal(result.exitCode, 0);
  assert.equal(result.facts.closedCycles, 32);
});

test("dictamen: sin material durable el estado es UNKNOWN y sale 2", () => {
  const result = evaluate({
    forward: null,
    manifest: null,
    certification: null,
  });
  assert.equal(result.verdict, VERDICT.UNKNOWN);
  assert.equal(result.exitCode, 2);
});
