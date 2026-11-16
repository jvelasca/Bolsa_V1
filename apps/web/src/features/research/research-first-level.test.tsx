/**
 * Gate falsable de primer nivel · Asesor (`/research`) — oleadas 4 y A4 (UI 6.x).
 *
 * El primer nivel de Asesor solo muestra resultado/veredicto («¿Por qué?»); la
 * jerga estadística/de ingeniería (`Sharpe`, `campaignId`, `WFE`/`PBO`/`DSR`,
 * `ledger`, `prec.5d`, `recall≈`, `Proxy Outcomes`…) vive detrás del
 * `TechnicalDetail` único.
 *
 * Slice A4: la exención ciega `LEVEL_3_FRAGMENT_TOKENS` (una lista de tokens
 * perdonados por archivo) se sustituye por un invariante ESTRUCTURAL: un fragmento
 * de nivel 3 sin disclosure propio solo se admite si se importa en UN único archivo,
 * ese archivo abre un `TechnicalDetail`, y el fragmento se monta DENTRO de él. Así
 * el vocabulario prohibido vuelve a auditarse en todos los archivos: ya no hay
 * tokens exentos, solo montajes justificados.
 *
 * @see apps/web/src/components/first-level-gate.ts
 * @see apps/web/src/components/technical-detail.tsx
 * @see docs/engineering/auditoria-ui-6-x-global-2026-10-08.md §5 (oleada 4)
 * @see docs/engineering/auditoria-operativa-asesor-2026-11-15.md §H-17..H-20 (slice A4)
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  findFirstLevelDashes,
  FORBIDDEN_FIRST_LEVEL_TOKENS,
  findFirstLevelViolations,
  stripTechnicalDetailBlocks,
} from "@/components/first-level-gate";

const RESEARCH_DIR = __dirname;
const SRC_ROOT = resolve(__dirname, "../../..");

function readSource(file: string): string {
  return readFileSync(resolve(RESEARCH_DIR, file), "utf8");
}

/**
 * Fuente sin comentarios: el gate audita copy renderizada, no JSDoc. Un comentario
 * que nombra `PBO`/`prec.5d` no es una fuga de primer nivel.
 */
function withoutComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

/**
 * Falsos positivos legítimos del gate textual sobre TSX: además de identificar
 * la jerga, estos tokens son nombres de parámetro HTTP / estado de React / query
 * de URL (`row.proposedBy`, `presetKey:`, `?runId=`). No se pintan como texto —
 * se pinta su valor, que sí va plegado tras el `Detalle técnico`.
 */
const CODE_IDENTIFIER_TOKENS: readonly string[] = [
  "proposedBy",
  "presetKey",
  "runId",
];

const FIRST_LEVEL_TOKENS = FORBIDDEN_FIRST_LEVEL_TOKENS.filter(
  (token) => !CODE_IDENTIFIER_TOKENS.includes(token),
);

/**
 * Todos los módulos de `apps/web/src/features/research/` que pintan UI de primer
 * nivel (glob real: `*.tsx` no-test de la carpeta, más el poller que emite toast).
 * Los fragmentos de nivel 3 están incluidos a propósito: su jerga se justifica con
 * `level3FragmentViolation`, no con una lista de tokens exentos.
 */
const SOURCES: Record<string, string> = {
  "research-page.tsx": readSource("research-page.tsx"),
  "asesor-hub-tabs.tsx": readSource("asesor-hub-tabs.tsx"),
  "asesor-ui.tsx": readSource("asesor-ui.tsx"),
  "asesor-opiniones-panel.tsx": readSource("asesor-opiniones-panel.tsx"),
  "asesor-telemetry-strip.tsx": readSource("asesor-telemetry-strip.tsx"),
  "opinion-channel-map.tsx": readSource("opinion-channel-map.tsx"),
  "asesor-dictamen-cell.tsx": readSource("asesor-dictamen-cell.tsx"),
  "asesor-daily-ops-panel.tsx": readSource("asesor-daily-ops-panel.tsx"),
  "asesor-daily-hero.tsx": readSource("asesor-daily-hero.tsx"),
  "asesor-daily-channels.tsx": readSource("asesor-daily-channels.tsx"),
  "asesor-week-chart.tsx": readSource("asesor-week-chart.tsx"),
  "asesor-cartera-panel.tsx": readSource("asesor-cartera-panel.tsx"),
  "asesor-cartera-row.tsx": readSource("asesor-cartera-row.tsx"),
  "asesor-cartera-filters.tsx": readSource("asesor-cartera-filters.tsx"),
  "asesor-cartera-technical-detail.tsx": readSource(
    "asesor-cartera-technical-detail.tsx",
  ),
  "asesor-strength-bar.tsx": readSource("asesor-strength-bar.tsx"),
  "asesor-journal-bridge.tsx": readSource("asesor-journal-bridge.tsx"),
  "estudio-opinion-alarm-poller.tsx": readSource(
    "estudio-opinion-alarm-poller.tsx",
  ),
  "research-trial-result-block.tsx": readSource(
    "research-trial-result-block.tsx",
  ),
  "research-lab-evidence-summary.tsx": readSource(
    "research-lab-evidence-summary.tsx",
  ),
  "lab-summary-panel.tsx": readSource("lab-summary-panel.tsx"),
  "lab-health-card.tsx": readSource("lab-health-card.tsx"),
  "lab-trial-history-panel.tsx": readSource("lab-trial-history-panel.tsx"),
  "lab-trial-detail-panel.tsx": readSource("lab-trial-detail-panel.tsx"),
};

const CODE_FILE = /\.(ts|tsx)$/;
const TEST_FILE = /\.(test|spec)\.(ts|tsx)$/;

type SourceFile = { rel: string; source: string };

function filesUnder(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === "__snapshots__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      filesUnder(full, out);
    } else if (CODE_FILE.test(entry) && !TEST_FILE.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

let cachedFiles: SourceFile[] | null = null;

/** `apps/web/src` completo una sola vez: sirve para resolver importadores. */
function allSourceFiles(): SourceFile[] {
  cachedFiles ??= filesUnder(SRC_ROOT).map((abs) => ({
    rel: relative(SRC_ROOT, abs).replace(/\\/g, "/"),
    source: readFileSync(abs, "utf8"),
  }));
  return cachedFiles;
}

/** Archivos que importan `@/features/research/<base>` (o una ruta relativa a él). */
function importersOf(moduleBase: string, files: SourceFile[]): SourceFile[] {
  const ref = new RegExp(`["'][^"']*/${moduleBase}["']`);
  return files.filter(
    (file) =>
      file.rel !== `features/research/${moduleBase}.tsx` &&
      ref.test(file.source),
  );
}

/** Componentes que exporta el módulo (los que un padre podría montar). */
function exportedComponents(source: string): string[] {
  return [...source.matchAll(/export function (\w+)/g)].map(
    (match) => match[1]!,
  );
}

/**
 * ¿El fragmento se monta SOLO dentro de un `TechnicalDetail`?
 *
 * Se comprueba sobre el texto del importador: el primer nivel (sin los bloques de
 * nivel 3) no puede contener el tag del fragmento.
 */
function mountsInsideDisclosure(source: string, component: string): boolean {
  return (
    source.includes(`<${component}`) &&
    !stripTechnicalDetailBlocks(source).includes(`<${component}`)
  );
}

/**
 * `null` si un fragmento de nivel 3 está justificado por estructura; si no, el
 * motivo del fallo. Un módulo con jerga en su primer nivel solo pasa si:
 * 1. tiene un ÚNICO importador;
 * 2. ese importador abre un `TechnicalDetail` (con su `testId`);
 * 3. el fragmento se monta dentro de ese disclosure.
 */
function level3FragmentViolation(
  file: string,
  source: string,
  files: SourceFile[],
): string | null {
  const base = file.replace(/\.(tsx|ts)$/, "");
  const components = exportedComponents(source);
  if (components.length === 0) {
    return `${file}: fragmento sin componente exportado identificable`;
  }
  const importers = importersOf(base, files);
  if (importers.length !== 1) {
    return `${file}: se importa en ${importers.length} archivo(s) (${importers
      .map((importer) => importer.rel)
      .join(
        ", ",
      )}); un fragmento de nivel 3 debe tener un único punto de montaje`;
  }
  const importer = importers[0]!;
  if (!/<TechnicalDetail\b[^>]*\btestId=/.test(importer.source)) {
    return `${file}: ${importer.rel} no abre un TechnicalDetail con testId`;
  }
  for (const component of components) {
    if (!importer.source.includes(`<${component}`)) {
      return `${file}: ${importer.rel} no monta <${component}>`;
    }
    if (!mountsInsideDisclosure(importer.source, component)) {
      return `${file}: <${component}> se monta fuera del TechnicalDetail de ${importer.rel}`;
    }
  }
  return null;
}

describe("Asesor · primer nivel sin jerga de ingeniería (R-G1 / RT-04)", () => {
  it("ninguna superficie expone jerga fuera de TechnicalDetail", () => {
    const files = allSourceFiles();
    for (const [file, source] of Object.entries(SOURCES)) {
      const violations = findFirstLevelViolations(
        withoutComments(source),
        FIRST_LEVEL_TOKENS,
      );
      if (violations.length === 0) continue;
      // Sin exenciones por token: un archivo con jerga en su primer nivel solo se
      // admite si es un fragmento de nivel 3 montado DENTRO del disclosure único
      // de su importador.
      expect(
        level3FragmentViolation(file, source, files),
        `${file}: ${violations.join(", ")} fuera de un TechnicalDetail`,
      ).toBeNull();
    }
  });

  it("usa el disclosure único `TechnicalDetail` (sin `<details>` paralelos)", () => {
    for (const [file, source] of Object.entries(SOURCES)) {
      expect(source, file).not.toContain("<details");
      expect(source, file).not.toContain("<summary");
    }
  });

  it("LabHealthCard es un fragmento de nivel 3 montado dentro del disclosure del LAB", () => {
    const health = SOURCES["lab-health-card.tsx"]!;
    // R5 · la salud del laboratorio vive en /backtests, no en Asesor.
    const labResearch = readFileSync(
      resolve(SRC_ROOT, "src/features/backtests/lab-research-section.tsx"),
      "utf8",
    );
    expect(labResearch).toContain('testId="lab-research-health-technical"');
    expect(labResearch).toContain("<LabHealthCard");
    // Se monta al otro lado del disclosure: en el primer nivel no queda el tag.
    expect(stripTechnicalDetailBlocks(labResearch)).not.toContain(
      "<LabHealthCard",
    );
    // Y la jerga sigue existiendo: solo que dentro del disclosure.
    expect(health).toContain("Sharpe presente");
    expect(health).toContain("campaignId");
    // El invariante estructural lo demuestra sin exenciones por token.
    expect(
      level3FragmentViolation("lab-health-card.tsx", health, allSourceFiles()),
    ).toBeNull();
  });

  it("el invariante distingue un montaje dentro del disclosure de uno fuera", () => {
    // Control de falsabilidad: si el fragmento se monta en primer nivel, el
    // invariante lo rechaza; por tanto sigue protegiendo.
    expect(
      mountsInsideDisclosure(
        '<TechnicalDetail testId="x"><LabHealthCard /></TechnicalDetail>',
        "LabHealthCard",
      ),
    ).toBe(true);
    expect(
      mountsInsideDisclosure("<div><LabHealthCard /></div>", "LabHealthCard"),
    ).toBe(false);
    expect(
      level3FragmentViolation(
        "lab-health-card.tsx",
        "export function LabHealthCard() { return null; }",
        [
          {
            rel: "features/research/lab-summary-panel.tsx",
            source: [
              'import { LabHealthCard } from "@/features/research/lab-health-card";',
              '<TechnicalDetail testId="asesor-lab-metrics-technical"><p>ok</p></TechnicalDetail>',
              "<LabHealthCard health={h} />",
            ].join("\n"),
          },
        ],
      ),
    ).toContain("fuera del TechnicalDetail");
  });

  it("Análisis: el primer nivel solo declara alarmas, avisos y sin dictamen", () => {
    const firstLevel = stripTechnicalDetailBlocks(
      SOURCES["asesor-opiniones-panel.tsx"]!,
    );
    expect(firstLevel).toContain("alarmas");
    expect(firstLevel).toContain("avisos");
    expect(firstLevel).toContain("sin dictamen");
    // El diagnóstico (recuento de Estudio, silencios, asOf) no vive aquí.
    expect(firstLevel).not.toContain("valores en Estudio");
    expect(firstLevel).not.toContain("en silencio");
  });

  it("la jerga de telemetría vive dentro del disclosure de la tira", () => {
    const strip = SOURCES["asesor-telemetry-strip.tsx"]!;
    // Un solo disclosure para A0 + A6 + diagnóstico (no dos hermanos).
    expect(strip.match(/<TechnicalDetail\b/g)).toHaveLength(1);
    expect(strip).toMatch(
      /<TechnicalDetail\s+testId=\{ASESOR_OPINIONS_TELEMETRY_TEST_ID\}/,
    );
    const rendered = withoutComments(strip);
    const firstLevel = stripTechnicalDetailBlocks(rendered);
    // El JSX parte las frases en varias líneas: se compara con espacios colapsados.
    const flatRendered = rendered.replace(/\s+/g, " ");
    const flatFirstLevel = firstLevel.replace(/\s+/g, " ");
    for (const token of [
      "prec.5d",
      "recall≈",
      "Proxy Outcomes",
      "P1–P5",
      "Execute env",
    ]) {
      // No se borra: se pliega.
      expect(flatRendered, token).toContain(token);
      expect(flatFirstLevel, token).not.toContain(token);
    }
  });

  it("«aviso» tiene un único tono en asesor-ui y «alarma» conserva el rojo", () => {
    const ui = SOURCES["asesor-ui.tsx"]!;
    expect(ui).toContain("ASESOR_CHANNEL_TONE");
    expect(ui).toMatch(/aviso:\s*\{[\s\S]*?amber-500/);
    expect(ui).toMatch(/alarma:\s*\{[\s\S]*?rose-500/);
    // Análisis y Diario leen la misma fuente: no declaran colores de canal propios.
    for (const file of [
      "asesor-opiniones-panel.tsx",
      "asesor-daily-channels.tsx",
    ]) {
      const source = SOURCES[file]!;
      expect(source, file).toContain("ASESOR_CHANNEL_TONE");
      expect(source, file).not.toContain("bg-sky-500");
      expect(source, file).not.toContain("bg-amber-500");
      expect(source, file).not.toContain("bg-rose-500");
    }
  });

  it("no usa «Sin datos.» ni el comodín `—` de dato ausente (UI5-14)", () => {
    for (const [file, source] of Object.entries(SOURCES)) {
      expect(stripTechnicalDetailBlocks(source), file).not.toContain(
        "Sin datos.",
      );
    }
    expect(
      stripTechnicalDetailBlocks(SOURCES["research-page.tsx"]!),
    ).not.toMatch(/\?\?\s*"—"/);
  });

  it("ningún archivo usa `—` de primer nivel ni colapsa un hueco a 0", () => {
    for (const [file, source] of Object.entries(SOURCES)) {
      expect(findFirstLevelDashes(source), file).toEqual([]);
      // `UNKNOWN ≠ 0`: ni siquiera en nivel 3 se rellena un hueco con cero.
      expect(source, file).not.toMatch(/\?\?\s*0(?![.\d])/);
      expect(source, file).not.toContain('"—"');
    }
  });

  it("el Diario declara la ausencia en vez de normalizar a colección vacía (H-22)", () => {
    // `?? []` sobre el parte convertiría «no llegó» en «cero», que es la misma
    // mentira que `?? 0`. Se comprueba solo aquí: en las respuestas de
    // react-query el estado de carga ya está cubierto por la query.
    for (const file of [
      "asesor-daily-ops-panel.tsx",
      "asesor-daily-channels.tsx",
      "asesor-week-chart.tsx",
    ]) {
      const source = SOURCES[file]!;
      expect(source, file).not.toMatch(/\?\?\s*\[\s*\]/);
      expect(source, file).toContain("asDeclaredList");
    }
  });

  it("Diario nombra el resultado, no el almacén (`Ledger`)", () => {
    const firstLevel = stripTechnicalDetailBlocks(
      SOURCES["asesor-daily-ops-panel.tsx"]!,
    );
    expect(firstLevel).not.toContain("Ledger");
    expect(firstLevel).not.toContain("balance ledger");
  });

  it("Diario es un resumen diario: no refresca cada minuto", () => {
    const source = SOURCES["asesor-daily-ops-panel.tsx"]!;
    expect(source).not.toMatch(/refetchInterval:\s*60_000/);
    expect(source).toMatch(/refetchInterval:\s*5\s*\*\s*60_000/);
    expect(SOURCES["asesor-daily-channels.tsx"]!).toContain(
      'data-testid="asesor-daily-ops-see-all"',
    );
  });

  it("research-lab-evidence.ts no filtra `Ledger` en el tooltip de primer nivel", () => {
    // El `title` del resumen de evidencia se monta como tooltip en la celda «Evidencia»
    // de `/research?tab=history` (primer nivel): el vocabulario debe ser humano (UI5-20).
    expect(readSource("research-lab-evidence.ts")).not.toContain("Ledger");
  });

  it("research-trial-result-block.tsx no usa el comodín `—` fuera del nivel 3", () => {
    // El único guion permitido vive dentro del `TechnicalDetail` (helpers
    // `formatMetric`/`formatBps`), y se referencia por el rótulo reservado, no por
    // el literal (UI5-14 / `UNKNOWN ≠ 0`).
    expect(SOURCES["research-trial-result-block.tsx"]!).not.toContain('"—"');
  });
});
