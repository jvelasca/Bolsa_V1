import { PrismaClient } from "@prisma/client";
import { IBEX35_INSTRUMENTS } from "@bolsa/shared";

const prisma = new PrismaClient();

async function main() {
  for (const item of IBEX35_INSTRUMENTS) {
    await prisma.instrument.upsert({
      where: { yahooSymbol: item.yahooSymbol },
      update: {
        name: item.name,
        symbol: item.symbol,
        exchange: item.exchange,
        currency: item.currency,
        type: item.type,
        isActive: true,
      },
      create: {
        symbol: item.symbol,
        yahooSymbol: item.yahooSymbol,
        name: item.name,
        exchange: item.exchange,
        currency: item.currency,
        type: item.type,
      },
    });
  }

  const count = await prisma.instrument.count();
  console.log(`Seed complete: ${count} instruments in database.`);

  // Lista catálogo IBEX 35 (id canónico `ibex35`). NO es cosmética: el incidente del
  // 2026-09-08 dejó una BD recién sembrada SIN `instrument_lists`, porque la lista la
  // creaba `ensure_ibex_catalog_list()` de forma perezosa y ninguna ruta la forzaba al
  // arrancar. Sembrarla aquí vuelve el catálogo declarativo y reproducible tras
  // `pnpm db:seed`, y alinea los campos con `SqlAlchemyInstrumentListRepository`.
  await prisma.instrumentList.upsert({
    where: { id: "ibex35" },
    update: {
      name: "IBEX 35",
      source: "catalog",
      kind: "linked_universe",
      universeCode: "IBEX35",
    },
    create: {
      id: "ibex35",
      name: "IBEX 35",
      source: "catalog",
      kind: "linked_universe",
      universeCode: "IBEX35",
    },
  });

  const ibexSymbols = IBEX35_INSTRUMENTS.map((item) => item.yahooSymbol);
  const orderBySymbol = new Map(
    ibexSymbols.map((symbol, index) => [symbol, index]),
  );
  const ibexInstruments = await prisma.instrument.findMany({
    where: { yahooSymbol: { in: ibexSymbols } },
    select: { id: true, yahooSymbol: true },
  });
  ibexInstruments.sort(
    (a, b) =>
      (orderBySymbol.get(a.yahooSymbol) ?? 0) -
      (orderBySymbol.get(b.yahooSymbol) ?? 0),
  );
  for (const [index, instrument] of ibexInstruments.entries()) {
    await prisma.instrumentListItem.upsert({
      where: {
        listId_instrumentId: { listId: "ibex35", instrumentId: instrument.id },
      },
      update: { sortOrder: index },
      create: {
        listId: "ibex35",
        instrumentId: instrument.id,
        sortOrder: index,
      },
    });
  }
  console.log(
    `Lista catálogo IBEX 35: ${ibexInstruments.length} constitutivos.`,
  );

  await prisma.portfolio.upsert({
    where: { id: "default-portfolio-seed" },
    update: {},
    create: {
      id: "default-portfolio-seed",
      name: "Cartera principal",
      currency: "EUR",
      cash: 100000,
    },
  });
  console.log("Portfolio virtual creada: 100.000 € de efectivo inicial.");
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
