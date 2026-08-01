import { PrismaClient } from '@prisma/client';
import { IBEX35_INSTRUMENTS } from '@bolsa/shared';

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

  await prisma.portfolio.upsert({
    where: { id: 'default-portfolio-seed' },
    update: {},
    create: {
      id: 'default-portfolio-seed',
      name: 'Cartera principal',
      currency: 'EUR',
      cash: 100000,
    },
  });
  console.log('Portfolio virtual creada: 100.000 € de efectivo inicial.');
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
