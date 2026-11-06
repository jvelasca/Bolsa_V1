#!/usr/bin/env node
/**
 * MERCADO gráficos — verificación operativa del contrato OHLCV/indicadores/
 * frescura contra el stack local, con evidencia JSON.
 *
 * Uso (raíz del repo):
 *   node scripts/verify/verify_mercado_chart_operativa.mjs
 *   pnpm verify:mercado:chart
 *
 * Opciones:
 *   --api <url>           API FastAPI (default http://localhost:8000)
 *   --web <url>           Web Vite (default http://localhost:5173)
 *   --symbols A,B,C       Símbolos a auditar (default AAPL,MSFT,GOOGL)
 *   --instruments <n>     Si no se encuentra ninguno de los símbolos, audita los
 *                         primeros n instrumentos (default 3)
 *   --timeframes 1d,1wk   Escalas a comprobar (default 1d,1wk)
 *   --limit <n>           Barras solicitadas (default 120)
 *   --browser             Ejecuta también el E2E mock de operativa gráfica
 *   --browser-live        Ejecuta también el E2E live de solo lectura
 *   --out <dir>           Carpeta de evidencia (default evidence_runs/mercado-chart-YYYY-MM-DD)
 *   --json                Imprime el reporte completo por stdout
 *   --help
 *
 * Salida:
 *   - Código 0 si no hay fallos de contrato; 1 si hay fallos.
 *   - report.json en la carpeta de evidencia.
 */

import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const isWin = process.platform === "win32";

const VALID_FRESHNESS = new Set([
  "empty",
  "stale",
  "current",
  "gap_detected",
  "error",
]);

function parseArgs(argv) {
  const args = {
    api: "http://localhost:8000",
    web: "http://localhost:5173",
    symbols: ["AAPL", "MSFT", "GOOGL"],
    instruments: 3,
    timeframes: ["1d", "1wk"],
    limit: 120,
    browser: false,
    browserLive: false,
    out: null,
    json: false,
    help: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case "--api":
        args.api = argv[++i];
        break;
      case "--web":
        args.web = argv[++i];
        break;
      case "--symbols":
        args.symbols = String(argv[++i] ?? "")
          .split(",")
          .map((s) => s.trim().toUpperCase())
          .filter(Boolean);
        break;
      case "--instruments":
        args.instruments = Number(argv[++i] ?? 3);
        break;
      case "--timeframes":
        args.timeframes = String(argv[++i] ?? "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
        break;
      case "--limit":
        args.limit = Number(argv[++i] ?? 120);
        break;
      case "--browser":
        args.browser = true;
        break;
      case "--browser-live":
        args.browserLive = true;
        break;
      case "--out":
        args.out = argv[++i];
        break;
      case "--json":
        args.json = true;
        break;
      case "--help":
      case "-h":
        args.help = true;
        break;
      default:
        if (arg.startsWith("--")) {
          throw new Error(`Opción desconocida: ${arg}`);
        }
    }
  }
  return args;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

async function getJson(url, timeoutMs = 20_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal });
    const text = await response.text();
    let body = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = text;
    }
    return { status: response.status, ok: response.ok, body };
  } finally {
    clearTimeout(timer);
  }
}

function check(id, ok, detail, severity = "error") {
  return { id, ok, severity, detail };
}

function isSortedAscending(values) {
  for (let i = 1; i < values.length; i += 1) {
    if (new Date(values[i]).getTime() < new Date(values[i - 1]).getTime()) {
      return false;
    }
  }
  return true;
}

function auditBars(bars) {
  const problems = [];
  for (const bar of bars) {
    const label = `${bar.timestamp}`;
    const { open, high, low, close } = bar;
    if (![open, high, low, close].every((v) => Number.isFinite(Number(v)))) {
      problems.push(`${label}: OHLC no numérico`);
      continue;
    }
    if (Number(high) < Number(low)) {
      problems.push(`${label}: high < low`);
    }
    if (Number(high) < Math.max(Number(open), Number(close))) {
      problems.push(`${label}: high < max(open, close)`);
    }
    if (Number(low) > Math.min(Number(open), Number(close))) {
      problems.push(`${label}: low > min(open, close)`);
    }
    if (bar.volume != null && Number(bar.volume) < 0) {
      problems.push(`${label}: volumen negativo`);
    }
  }
  return problems;
}

async function auditInstrumentTimeframe(api, instrument, timeframe, limit) {
  const checks = [];
  const base = `${api}/api/instruments/${encodeURIComponent(instrument.id)}`;

  const ohlcv = await getJson(
    `${base}/ohlcv?limit=${limit}&timeframe=${encodeURIComponent(timeframe)}`,
  );
  const bars = Array.isArray(ohlcv.body?.data) ? ohlcv.body.data : [];
  checks.push(
    check(
      "ohlcv.http",
      ohlcv.ok,
      `GET /ohlcv ${timeframe} → ${ohlcv.status}`,
      ohlcv.ok ? "info" : "error",
    ),
  );
  if (ohlcv.ok) {
    const declared = ohlcv.body?.meta?.count;
    checks.push(
      check(
        "ohlcv.meta-count",
        declared === bars.length,
        `meta.count=${declared} vs data.length=${bars.length}`,
      ),
    );
    const timestamps = bars.map((bar) => bar.timestamp);
    checks.push(
      check(
        "ohlcv.order",
        isSortedAscending(timestamps),
        `barras=${bars.length} asc=${isSortedAscending(timestamps)}`,
      ),
    );
    checks.push(
      check(
        "ohlcv.unique",
        new Set(timestamps).size === timestamps.length,
        `duplicados=${timestamps.length - new Set(timestamps).size}`,
      ),
    );
    checks.push(
      check(
        "ohlcv.limit",
        bars.length <= limit,
        `solicitadas=${limit} recibidas=${bars.length}`,
      ),
    );
    const invalid = auditBars(bars);
    checks.push(
      check(
        "ohlcv.ohlc-invariants",
        invalid.length === 0,
        invalid.length === 0 ? "OK" : invalid.slice(0, 5).join("; "),
      ),
    );
  }

  const indicators = await getJson(
    `${base}/indicators?limit=${limit}&timeframe=${encodeURIComponent(timeframe)}`,
  );
  const points = Array.isArray(indicators.body?.data)
    ? indicators.body.data
    : [];
  checks.push(
    check(
      "indicators.http",
      indicators.ok,
      `GET /indicators ${timeframe} → ${indicators.status}`,
      indicators.ok ? "info" : "error",
    ),
  );
  if (indicators.ok) {
    checks.push(
      check(
        "indicators.alignment",
        points.length === bars.length,
        `indicadores=${points.length} barras=${bars.length}`,
      ),
    );
    const barTs = bars.map((bar) => bar.timestamp);
    const indTs = points.map((point) => point.timestamp);
    checks.push(
      check(
        "indicators.timestamps",
        indTs.every((ts, index) => ts === barTs[index]),
        `alineación 1:1 por timestamp`,
      ),
    );
  }

  const status = await getJson(
    `${base}/data-status?timeframe=${encodeURIComponent(timeframe)}`,
  );
  const statusBody = status.body?.data ?? null;
  checks.push(
    check(
      "data-status.http",
      status.ok,
      `GET /data-status ${timeframe} → ${status.status}`,
      status.ok ? "info" : "error",
    ),
  );
  if (status.ok && statusBody) {
    checks.push(
      check(
        "data-status.freshness-enum",
        VALID_FRESHNESS.has(statusBody.freshnessStatus),
        `freshnessStatus=${statusBody.freshnessStatus}`,
      ),
    );
    checks.push(
      check(
        "data-status.timeframe",
        statusBody.timeframe === timeframe,
        `timeframe=${statusBody.timeframe}`,
      ),
    );
    const barCount = Number(statusBody.barCount);
    checks.push(
      check(
        "data-status.bar-count",
        Number.isFinite(barCount) && barCount >= 0,
        `barCount=${statusBody.barCount}`,
      ),
    );
    checks.push(
      check(
        "data-status.empty-consistent",
        statusBody.freshnessStatus !== "empty" || barCount === 0,
        `${statusBody.freshnessStatus} con barCount=${barCount}`,
      ),
    );
    if (statusBody.freshnessStatus === "current") {
      checks.push(
        check(
          "data-status.current-has-bars",
          barCount > 0,
          `current con barCount=${barCount}`,
        ),
      );
    }
  }

  return {
    timeframe,
    barCount: bars.length,
    indicatorCount: points.length,
    checks,
  };
}

async function resolveInstruments(api, args) {
  const response = await getJson(`${api}/api/instruments`);
  const list = Array.isArray(response.body?.data) ? response.body.data : [];
  if (!response.ok) {
    return { instruments: [], error: `GET /api/instruments → ${response.status}` };
  }
  const bySymbol = new Map(list.map((item) => [item.symbol, item]));
  const picked = args.symbols
    .map((symbol) => bySymbol.get(symbol))
    .filter(Boolean);
  if (picked.length > 0) return { instruments: picked, error: null };
  return {
    instruments: list.slice(0, Math.max(1, args.instruments)),
    error: `Símbolos no encontrados (${args.symbols.join(", ")}); se usan los primeros ${args.instruments}.`,
  };
}

function runPlaywright(specFile, env) {
  const spec = `gp-v190-mercado-chart-${specFile}`;
  console.log(`\n── Playwright ${spec} ──`);
  const args = [
    "--filter",
    "@bolsa/web",
    "exec",
    "playwright",
    "test",
    spec,
    "--reporter=line",
  ];
  const result = spawnSync(
    isWin ? `pnpm ${args.join(" ")}` : "pnpm",
    isWin ? [] : args,
    {
      cwd: repoRoot,
      stdio: "inherit",
      shell: isWin,
      env: { ...process.env, ...env },
    },
  );
  const code = result.status ?? 1;
  if (code !== 0) console.error(`✗ FAIL: ${spec} (exit ${code})`);
  else console.log(`✓ OK: ${spec}`);
  return { spec, ok: code === 0, exitCode: code };
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exit(2);
  }
  if (args.help) {
    const header = String(process.argv[1] ?? "");
    console.log(`Uso: node ${path.relative(process.cwd(), header)} [opciones]`);
    console.log("Opciones: --api --web --symbols --instruments --timeframes --limit --browser --browser-live --out --json");
    return;
  }

  const api = args.api.replace(/\/$/, "");
  const outDir = path.resolve(
    repoRoot,
    args.out ?? path.join("evidence_runs", `mercado-chart-${today()}`),
  );
  mkdirSync(outDir, { recursive: true });

  const report = {
    generatedAt: new Date().toISOString(),
    kind: "mercado-chart-operativa",
    apiUrl: api,
    webUrl: args.web,
    requested: {
      symbols: args.symbols,
      timeframes: args.timeframes,
      limit: args.limit,
    },
    health: null,
    instruments: [],
    warnings: [],
    failures: [],
    browser: [],
    ok: false,
  };

  console.log("MERCADO gráficos — verificación operativa");
  console.log(`API: ${api}`);
  console.log(`Evidencia: ${outDir}`);

  const health = await getJson(`${api}/api/health`);
  report.health = { status: health.status, body: health.body };
  if (!health.ok) {
    report.failures.push(`GET /api/health → ${health.status}`);
    finalize();
    return;
  }
  console.log(`✓ salud API ${health.status}`);

  const resolved = await resolveInstruments(api, args);
  if (resolved.error) report.warnings.push(resolved.error);
  if (resolved.instruments.length === 0) {
    report.failures.push("No hay instrumentos para auditar.");
    finalize();
    return;
  }

  for (const instrument of resolved.instruments) {
    const entry = {
      id: instrument.id,
      symbol: instrument.symbol,
      name: instrument.name ?? null,
      timeframes: [],
    };
    for (const timeframe of args.timeframes) {
      const result = await auditInstrumentTimeframe(
        api,
        instrument,
        timeframe,
        args.limit,
      );
      entry.timeframes.push(result);
      const failed = result.checks.filter((c) => !c.ok && c.severity === "error");
      console.log(
        `${failed.length === 0 ? "✓" : "✗"} ${instrument.symbol} ${timeframe}: ` +
          `barras=${result.barCount} indicadores=${result.indicatorCount} ` +
          `checks=${result.checks.length - failed.length}/${result.checks.length}`,
      );
      for (const failure of failed) {
        report.failures.push(
          `${instrument.symbol} ${timeframe} ${failure.id}: ${failure.detail}`,
        );
      }
    }
    report.instruments.push(entry);
  }

  if (args.browser) {
    report.browser.push(
      runPlaywright("operativa-mock.spec.ts", { E2E_RUN: "1" }),
    );
  }
  if (args.browserLive) {
    report.browser.push(
      runPlaywright("live.spec.ts", {
        PLAYWRIGHT_BASE_URL: args.web,
        E2E_INTEGRATION: "1",
      }),
    );
  }
  for (const run of report.browser) {
    if (!run.ok) report.failures.push(`Playwright ${run.spec} exit ${run.exitCode}`);
  }

  finalize();

  function finalize() {
    report.ok = report.failures.length === 0;
    const reportPath = path.join(outDir, "report.json");
    writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    console.log(`\nReporte: ${reportPath}`);
    if (report.warnings.length > 0) {
      console.log("Avisos:");
      for (const warning of report.warnings) console.log(`  · ${warning}`);
    }
    if (!report.ok) {
      console.error(`\n✗ ${report.failures.length} fallo(s):`);
      for (const failure of report.failures) console.error(`  · ${failure}`);
      process.exitCode = 1;
    } else {
      console.log("\n✓ Contrato OHLCV/indicadores/frescura OK");
    }
    if (args.json) console.log(JSON.stringify(report, null, 2));
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
