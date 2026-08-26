import { createServer } from 'node:http';
import { randomUUID } from 'node:crypto';

const PORT = Number(process.env.XTB_BRIDGE_PORT ?? 3002);
/** Fail-closed: mock rechaza órdenes salvo XTB_BRIDGE_ALLOW_ORDERS=1. */
const ALLOW_ORDERS = process.env.XTB_BRIDGE_ALLOW_ORDERS === '1';
/** Con ALLOW + FILL: responde filled (ledger vía adapter XL-2). */
const FILL_ORDERS = process.env.XTB_BRIDGE_FILL_ORDERS === '1';

function hashSeed(text) {
  let hash = 0;
  for (const char of text) {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  }
  return hash;
}

function mockPrice(symbol) {
  const base = 8 + (hashSeed(symbol) % 4000) / 100;
  const jitter = Math.sin(Date.now() / 60000) * 0.05;
  return Number((base * (1 + jitter)).toFixed(4));
}

/** Simula cotización en vivo anclada al cierre de referencia (±0,4 %). */
function mockQuoteFromReference(symbol, referenceRaw) {
  const reference = Number(referenceRaw);
  if (!Number.isFinite(reference) || reference <= 0) {
    return mockPrice(symbol);
  }
  const drift = Math.sin(Date.now() / 120000 + hashSeed(symbol)) * 0.004;
  return Number((reference * (1 + drift)).toFixed(4));
}

function sendJson(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

const server = createServer((req, res) => {
  const url = new URL(req.url ?? '/', `http://localhost:${PORT}`);

  if (req.method === 'GET' && url.pathname === '/health') {
    sendJson(res, 200, { status: 'ok', mode: 'mock', message: 'XTB bridge simulado' });
    return;
  }

  const quoteMatch = url.pathname.match(/^\/symbols\/([^/]+)\/quote$/);
  if (req.method === 'GET' && quoteMatch) {
    const symbol = decodeURIComponent(quoteMatch[1]);
    const reference = url.searchParams.get('reference');
    const last = reference ? mockQuoteFromReference(symbol, reference) : mockPrice(symbol);
    const spread = last * 0.001;
    sendJson(res, 200, {
      symbol,
      bid: Number((last - spread).toFixed(4)),
      ask: Number((last + spread).toFixed(4)),
      last,
      timestamp: new Date().toISOString(),
    });
    return;
  }

  const barsMatch = url.pathname.match(/^\/symbols\/([^/]+)\/bars$/);
  if (req.method === 'GET' && barsMatch) {
    const symbol = decodeURIComponent(barsMatch[1]);
    const from = url.searchParams.get('from') ?? '2024-01-01';
    const to = url.searchParams.get('to') ?? '2024-12-31';
    const start = new Date(`${from}T00:00:00.000Z`);
    const end = new Date(`${to}T00:00:00.000Z`);
    const bars = [];
    let price = mockPrice(symbol);

    for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
      if (d.getUTCDay() === 0 || d.getUTCDay() === 6) continue;
      const delta = (Math.random() - 0.5) * 0.4;
      price = Math.max(1, price * (1 + delta / 100));
      const open = price;
      const close = price * (1 + (Math.random() - 0.5) * 0.01);
      const high = Math.max(open, close) * 1.005;
      const low = Math.min(open, close) * 0.995;
      bars.push({
        timestamp: d.toISOString().slice(0, 10),
        open: Number(open.toFixed(4)),
        high: Number(high.toFixed(4)),
        low: Number(low.toFixed(4)),
        close: Number(close.toFixed(4)),
        volume: Math.floor(100000 + Math.random() * 500000),
      });
      price = close;
    }

    sendJson(res, 200, { bars });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/account/cash') {
    sendJson(res, 200, {
      cash: Number(process.env.XTB_BRIDGE_MOCK_CASH ?? 0),
      currency: 'EUR',
    });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/account/positions') {
    let positions = [];
    try {
      positions = JSON.parse(process.env.XTB_BRIDGE_MOCK_POSITIONS ?? '[]');
    } catch {
      positions = [];
    }
    sendJson(res, 200, { positions });
    return;
  }

  if (req.method === 'POST' && url.pathname === '/orders') {
    let body = '';
    req.on('data', (chunk) => {
      body += chunk;
    });
    req.on('end', () => {
      let parsed = {};
      try {
        parsed = body ? JSON.parse(body) : {};
      } catch {
        sendJson(res, 400, { status: 'rejected', reason: 'invalid_json' });
        return;
      }
      if (!ALLOW_ORDERS) {
        sendJson(res, 200, {
          status: 'rejected',
          reason: 'live_orders_disabled',
          instrumentId: parsed.instrumentId ?? null,
        });
        return;
      }
      const venueOrderId = `xtb-mock-${randomUUID().slice(0, 8)}`;
      const echo = {
        venueOrderId,
        instrumentId: parsed.instrumentId ?? null,
        side: parsed.side ?? null,
        quantity: parsed.quantity ?? null,
      };
      if (FILL_ORDERS) {
        const filled = {
          status: 'filled',
          reason: 'live_filled',
          ...echo,
        };
        if (parsed.price != null && parsed.price !== '') {
          filled.fillPrice = parsed.price;
        }
        sendJson(res, 200, filled);
        return;
      }
      sendJson(res, 200, {
        status: 'submitted',
        reason: 'live_submitted_no_fill',
        ...echo,
      });
    });
    return;
  }

  sendJson(res, 404, { error: 'Not found' });
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    fetch(`http://127.0.0.1:${PORT}/health`)
      .then((response) => {
        if (!response.ok) throw new Error(`health ${response.status}`);
        return response.json();
      })
      .then((body) => {
        if (body?.mode === 'mock') {
          console.log(
            `[xtb-bridge-mock] puerto ${PORT} ya en uso — reutilizando mock existente`,
          );
          process.exit(0);
          return;
        }
        console.error(
          `[xtb-bridge-mock] puerto ${PORT} ocupado por otro servicio (no es el mock XTB)`,
        );
        process.exit(1);
      })
      .catch(() => {
        console.error(
          `[xtb-bridge-mock] puerto ${PORT} ocupado — libera el puerto o define XTB_BRIDGE_PORT`,
        );
        process.exit(1);
      });
    return;
  }
  console.error('[xtb-bridge-mock] error al arrancar:', err.message);
  process.exit(1);
});

server.listen(PORT, () => {
  console.log(`[xtb-bridge-mock] http://localhost:${PORT} (modo simulado)`);
});
