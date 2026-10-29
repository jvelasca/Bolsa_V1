/**
 * Panel BD — estados honestos y la única acción de escritura.
 *
 * Lo que se protege aquí: el panel no inventa salud. Un dato no medido se muestra como
 * «No disponible» (``unknown``, gris), no como cero ni como verde; el rojo se reserva a
 * fallos medidos. La única acción posible es crear una copia, y exige escribir ``COPIAR``.
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { DatabaseMaintenanceDto } from "@bolsa/shared";

const getDatabaseMaintenance = vi.fn(async () => ({ data: makeReport() }));
const createDatabaseBackup = vi.fn(async () => ({
  data: {
    run: {
      ok: true,
      file: "/repo/db-backups/bolsa_v1-20261029-150000-000.sql.gz",
      bytes: 52_000_000,
      sha256: "abcdef0123456789".padEnd(64, "0"),
      schemaRevision: "060_provider_check_policy",
      pruned: 1,
      mirrorPath: null,
      durationMs: 1234,
      errorCode: null,
      error: null,
    },
    backups: makeReport().backups,
  },
}));

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  api: {
    getDatabaseMaintenance: () => getDatabaseMaintenance(),
    createDatabaseBackup: (confirm: string) => createDatabaseBackup(confirm),
  },
}));

import { DatabaseMaintenancePanel } from "@/features/config/database-maintenance-panel";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function makeReport(
  overrides: Partial<DatabaseMaintenanceDto> = {},
): DatabaseMaintenanceDto {
  return {
    status: "ok",
    generatedAt: "2026-10-29T12:00:00Z",
    connected: true,
    message: "PostgreSQL conectado",
    schema: {
      status: "ok",
      currentRevision: "060_provider_check_policy",
      expectedHead: "060_provider_check_policy",
      databaseTables: 89,
      expectedTables: 87,
      missingTables: [],
      missingColumns: [],
      missingConstraints: [],
      unexpectedTables: [],
      allowlisted: ["table custody_obligation: tabla histórica"],
      detail: "Esquema en head (060_provider_check_policy)",
    },
    capacity: {
      status: "ok",
      databaseBytes: 51_380_224,
      databasePretty: "49.0 MB",
      tables: [
        {
          table: "ohlcv_bars",
          label: "Velas OHLCV",
          rows: 43_000,
          sizeBytes: 20_000_000,
          sizePretty: "19.1 MB",
        },
      ],
      detail: "49.0 MB en total",
    },
    maintenance: {
      status: "ok",
      autovacuumEnabled: true,
      naptimeSeconds: 60,
      deadTuplesTotal: 12,
      tablesWithDeadTuples: [],
      lastAutovacuum: null,
      detail: "autovacuum activo",
    },
    connections: {
      status: "ok",
      total: 4,
      active: 1,
      idle: 3,
      idleInTransaction: 0,
      maxConnections: 100,
      longestTransactionSeconds: null,
      detail: "4 conexiones (1 activas, 3 idle)",
    },
    backups: {
      status: "ok",
      accessible: true,
      directory: "C:/repo/db-backups",
      count: 3,
      retention: 14,
      latestName: "bolsa_v1-20261029-030000.sql.gz",
      latestBytes: 52_000_000,
      latestCreatedAt: "2026-10-29T03:00:00Z",
      latestSchema: "060_provider_check_policy",
      ageHours: 9,
      stale: false,
      checksumPresent: true,
      mirrorConfigured: false,
      detail: "3 copia(s); la más reciente 9.0 h",
    },
    integrity: {
      status: "ok",
      checks: [
        {
          id: "integrity.sync_settings_singleton",
          label: "Fila única de sync_settings",
          status: "ok",
          detail: "Existe exactamente una fila de configuración",
          value: "default",
        },
      ],
      detail: "1 comprobaciones de coherencia sin hallazgos",
    },
    checks: [],
    ...overrides,
  };
}

function renderPanel(report: DatabaseMaintenanceDto) {
  getDatabaseMaintenance.mockResolvedValueOnce({ data: report });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <DatabaseMaintenancePanel />
    </QueryClientProvider>,
  );
}

describe("DatabaseMaintenancePanel", () => {
  it("muestra esquema, capacidad, copias e integridad sin acciones de escritura", async () => {
    renderPanel(makeReport());

    expect(await screen.findByText("Esquema y migraciones")).toBeTruthy();
    expect(screen.getByText("Capacidad")).toBeTruthy();
    expect(screen.getByText("Copias de seguridad")).toBeTruthy();
    expect(screen.getByText("Integridad")).toBeTruthy();
    expect(
      screen.getAllByText("060_provider_check_policy").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/49.0 MB/)).toBeTruthy();
    expect(screen.getByText("bolsa_v1-20261029-030000.sql.gz")).toBeTruthy();
    expect(screen.getByText(/1 divergencia/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /vacuum/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /purgar/i })).toBeNull();
  });

  it("declara «No disponible» cuando el directorio de copias no es accesible", async () => {
    renderPanel(
      makeReport({
        status: "warning",
        backups: {
          ...makeReport().backups,
          status: "warning",
          accessible: false,
          count: 0,
          latestName: null,
          ageHours: null,
          stale: null,
          detail: "El directorio de copias no existe o no es visible",
        },
      }),
    );

    const unavailable = await screen.findByTestId("maintenance-unavailable");
    expect(unavailable.textContent).toContain("No disponible");
    expect(
      screen.getAllByTestId("maintenance-status-warning").length,
    ).toBeGreaterThan(0);
  });

  it("con la BD caída no inventa datos ni pinta verde", async () => {
    const report = makeReport({
      status: "error",
      connected: false,
      message: "PostgreSQL inaccesible",
    });
    renderPanel({
      ...report,
      schema: {
        ...report.schema,
        status: "unknown",
        currentRevision: null,
        detail: "PostgreSQL no responde",
      },
      capacity: {
        ...report.capacity,
        status: "unknown",
        databasePretty: "—",
        tables: [],
        detail: "PostgreSQL no responde",
      },
      maintenance: {
        ...report.maintenance,
        status: "unknown",
        autovacuumEnabled: null,
        naptimeSeconds: null,
        deadTuplesTotal: 0,
        tablesWithDeadTuples: [],
        detail: "PostgreSQL no responde",
      },
      connections: {
        ...report.connections,
        status: "unknown",
        total: 0,
        active: 0,
        idle: 0,
        maxConnections: null,
        longestTransactionSeconds: null,
        detail: "PostgreSQL no responde",
      },
      backups: {
        ...report.backups,
        status: "unknown",
        accessible: false,
        count: 0,
        latestName: null,
        ageHours: null,
        stale: null,
        detail: "PostgreSQL no responde",
      },
      integrity: {
        status: "unknown",
        checks: [],
        detail: "PostgreSQL no responde",
      },
    });

    expect(await screen.findByText(/Sin conexión/)).toBeTruthy();
    expect(
      screen.getAllByTestId("maintenance-status-unknown"),
    ).not.toHaveLength(0);
    expect(screen.queryByTestId("maintenance-status-ok")).toBeNull();
    expect(
      screen.getAllByTestId("maintenance-unavailable").length,
    ).toBeGreaterThanOrEqual(3);
  });

  it("el botón de copia no dispara nada hasta escribir COPIAR", async () => {
    renderPanel(makeReport());

    fireEvent.click(await screen.findByTestId("db-backup-start"));
    const confirm = screen.getByTestId(
      "db-backup-confirm",
    ) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText(/Escribe/i), {
      target: { value: "copiar" },
    });
    expect(confirm.disabled).toBe(false);

    fireEvent.click(confirm);
    await waitFor(() =>
      expect(createDatabaseBackup).toHaveBeenCalledWith("COPIAR"),
    );
    expect(await screen.findByTestId("db-backup-result")).toBeTruthy();
  });

  it("un fallo de la copia se muestra en rojo y no pinta éxito", async () => {
    createDatabaseBackup.mockRejectedValueOnce(
      new Error("backup_in_progress: Ya hay una copia en curso"),
    );
    renderPanel(makeReport());

    fireEvent.click(await screen.findByTestId("db-backup-start"));
    fireEvent.change(screen.getByLabelText(/Escribe/i), {
      target: { value: "COPIAR" },
    });
    fireEvent.click(screen.getByTestId("db-backup-confirm"));

    const error = await screen.findByTestId("db-backup-error");
    expect(error.textContent).toContain("backup_in_progress");
    expect(screen.queryByTestId("db-backup-result")).toBeNull();
  });
});
