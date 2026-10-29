/**
 * Tracker Ayuda → Datos de mercado.
 * Resumen no técnico primero; detalle y rutas a docs después.
 * @see docs/MARKET_DATA.md
 * @see docs/adr/002-yahoo-primary-xtb-secondary.md
 */

import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";

export const DATA_MARKET_SYNC = {
  asOf: HELP_CONTENT_AS_OF,
  marketDoc: "docs/MARKET_DATA.md",
  dataModel: "docs/DATA_MODEL.md",
  adr: "docs/adr/002-yahoo-primary-xtb-secondary.md",
  adrIntraday: "docs/adr/007-intraday-ohlcv-persistence.md",
  configHint:
    "Configuración → Sync / proveedores (sync automática y estado de proveedores)",
  bdHint: "Configuración → BD (conteos, huérfanos y purga)",
} as const;

/** Orientación en lenguaje llano (primera tarjeta). */
export const DATA_MARKET_SUMMARY = {
  title: "En pocas palabras",
  body: "La app guarda en tu base de datos local el histórico de precios y una ficha fundamental de cada valor. Yahoo Finance es quien alimenta ese almacén. XTB (opcional) solo aporta la cotización del momento y sirve para comprobar que el cierre en BD no se ha desviado demasiado.",
  bullets: [
    "Yahoo → histórico de velas + datos fundamentales (perfil de la empresa).",
    "PostgreSQL → fuente de verdad para gráficos, backtests, escáneres e IA.",
    "XTB Bridge → precio en vivo y validación; no escribe el histórico.",
    "Puedes sincronizar a mano un valor, o dejar que la cola automática actualice los que estén desfasados.",
  ],
} as const;

/** Dos familias de datos que el usuario debe distinguir. */
export const DATA_FAMILIES = [
  {
    id: "technical",
    title: "Datos técnicos (velas OHLCV)",
    plain:
      "Son las velas del gráfico: apertura, máximo, mínimo, cierre y volumen. Sin ellas no hay gráfico ni análisis técnico.",
    detail:
      "Sync diario (1d) desde Yahoo → tabla ohlcv_bars. Otros timeframes (1m…1h, 1wk…) se piden bajo demanda y también se cachean en BD con TTL. Lectura de la app: siempre desde PostgreSQL.",
  },
  {
    id: "fundamental",
    title: "Datos fundamentales (ficha / snapshot)",
    plain:
      "Son ratios y cifras de la empresa (beneficios, deuda, ROE, márgenes, Altman Z, etc.) guardados como una «foto» del valor.",
    detail:
      "Yahoo quoteSummary → profile_snapshot JSONB (FA F2.8: PE, ROE, Altman, FCF, Piotroski, Graham, DCF/CAPM, ROIC, Beneish, ADV…). Filings en disco (`data/filings` + TF-IDF), fuera de Score_FUND. Stale >~30d → refresh. Docs: FIE + fa-status-and-test-plan-2026-07-31.",
  },
] as const;

export const DATA_SOURCES = [
  {
    id: "yahoo",
    title: "Yahoo Finance (primario)",
    role: "Almacén histórico",
    provides: [
      "Velas diarias (y otros intervalos bajo demanda)",
      "Perfil + fundamentales v3 + dividendos",
      "Noticias / macro efímeros para la IA (TTL en memoria, no BD de mercado)",
    ],
  },
  {
    id: "xtb",
    title: "XTB Bridge (secundario, opcional)",
    role: "Cinta en vivo",
    provides: [
      "Cotización bid/ask/last vía bridge HTTP local",
      "Validación vs último cierre en BD (aligned / review)",
      "No sustituye Yahoo para histórico ni backtest",
    ],
  },
] as const;

export const DATA_SYNC_MODES = [
  {
    id: "manual",
    title: "Manual",
    body: "Botón «Sincronizar Yahoo» en gráfico / ficha / API. Fuerza descarga diaria + refresco de metadatos del valor.",
  },
  {
    id: "auto",
    title: "Automática (cola)",
    body: `Worker en segundo plano: cada cierto intervalo encola instrumentos vacíos, desfasados o con error y los procesa con pausas y reintentos. Ajustes en ${DATA_MARKET_SYNC.configHint}.`,
  },
  {
    id: "lazy",
    title: "Bajo demanda (intradía)",
    body: "Si pides un timeframe distinto de 1d y la caché está caducada, Yahoo rellena esas velas y las guarda en ohlcv_bars.",
  },
  {
    id: "fund-batch",
    title: "Fundamentales en lote",
    body: "Refresh concurrente del profile_snapshot para gates de escáner / calidad (sin rehacer todo el histórico de velas).",
  },
] as const;

export const DATA_VALIDATION = [
  {
    id: "sanity",
    title: "Sanidad al escribir",
    body: "Comprueba coherencia OHLC, fechas futuras, huecos y movimientos extremos. Errores graves bloquean el guardado; avisos quedan en el log de sync.",
  },
  {
    id: "consolidate",
    title: "Consolidación",
    body: "Al re-sincronizar no se pisan a ciegas las velas ya guardadas: se fusionan con política de delta para no corromper el histórico.",
  },
  {
    id: "freshness",
    title: "Frescura del gráfico",
    body: "Badge según calendario de la bolsa (p. ej. BME ~17:30 Madrid): current / stale / empty / gap / error.",
  },
  {
    id: "xtb-val",
    title: "Validación XTB",
    body: "Compara el last del bridge con el último cierre en BD. Desviación <2% → aligned; si no → review. Se guarda en last_xtb_validation + data_sync_log.",
  },
  {
    id: "quality",
    title: "Puntuación de calidad",
    body: "Score v1: frescura, profundidad de barras, sync, huecos y presencia de fundamentales (no depende de XTB).",
  },
] as const;

export const DATA_DB_MODELS = [
  {
    what: "Catálogo + ficha fundamental",
    where: "instruments (+ profile_snapshot, last_xtb_validation)",
  },
  {
    what: "Velas técnicas",
    where: "ohlcv_bars (timeframe, timestamp, OHLCV, source)",
  },
  {
    what: "Auditoría de sync / validación",
    where: "data_sync_log",
  },
  {
    what: "Ajustes de cola automática",
    where: "sync_settings (fila default)",
  },
  {
    what: "Cola de trabajo",
    where: "sync_queue",
  },
] as const;

/** Ciclo de vida: listas ↔ BD. */
export const DATA_INSTRUMENT_LIFECYCLE = {
  title: "Quitar de lista y limpiar BD",
  plain:
    "Quitar un ticker de una lista no borra su histórico. Solo si ya no está en ninguna lista persistente (catálogo o personal; Visualización/Cartera/Pendientes no cuentan) pasa a «huérfano»: la cola con scope=listas deja de actualizarlo. Puedes purgarlo entonces (borra velas, alertas, etc.) salvo que tenga posición u orden pendiente.",
  bullets: [
    "Al desmarcar la última lista → diálogo: solo lista vs borrar de BD (con avisos de alertas/rastreadores).",
    "Configuración → BD: conteo de tablas PostgreSQL, lista de huérfanos y purga en lote.",
    "Listas de catálogo no se editan; no se puede «sacar» un IBEX del catálogo desde la UI.",
  ],
} as const;

/** Flujo ordenado (detalle). */
export const DATA_FLOW_STEPS = [
  {
    id: "yahoo",
    title: "1. Descarga desde Yahoo",
    body: "Primera sync: ~5 años de diarias. Siguientes: incremental desde última fecha − 7 días (solape). Cliente Python con throttle y reintentos (429/5xx).",
  },
  {
    id: "validate",
    title: "2. Validar y consolidar",
    body: "Esquema de ingesta + sanity checks + plan de consolidación antes del upsert.",
  },
  {
    id: "pg",
    title: "3. Guardar en PostgreSQL",
    body: "Velas en ohlcv_bars; perfil/fundamentales en instruments.profile_snapshot; resultado en data_sync_log. Gráficos y backtests leen solo BD.",
  },
  {
    id: "modes",
    title: "4. Modos de sync",
    body: "Manual, cola automática (worker), lazy intradía y refresh de fundamentales. Preferencias editables en Configuración → Sync / proveedores.",
  },
  {
    id: "xtb",
    title: "5. XTB como contraste live",
    body: "Bridge opcional (mock o conector propio). Cotización en vivo y validación vs cierre; no escribe histórico OHLCV.",
  },
] as const;

export const DATA_FRESHNESS_NOTES = [
  "Cada instrumento tiene un estado de frescura según el calendario de su bolsa. El badge del gráfico indica si la última vela diaria coincide con la fecha esperada.",
  "Si hay huecos en la ventana reciente o falla un sync, el valor puede entrar en la cola automática con reintentos espaciados (backoff).",
  "Los fundamentales envejecen: una ficha con más de ~30 días se considera stale para gates de análisis.",
] as const;

/**
 * Alcance real: listas vs cola automática vs gráfico abierto vs rastreadores.
 * Responde: «¿solo se actualiza lo que tengo en pestaña?»
 */
export const DATA_UPDATE_SCOPE = {
  title: "¿Qué se actualiza solo (y cada cuánto)?",
  plain:
    "Por defecto la cola automática mantiene frescos los valores que están en tus listas (universo de rastreadores), no hace falta tener el gráfico abierto. Procesa de uno en uno con pausas para no saturar Yahoo. El icono de sincronismo en cada fila de lista muestra si las diarias están al día (hover = detalle).",
  rows: [
    {
      who: "Cola automática (worker)",
      what: "Velas diarias (1d) + metadatos/fundamentales al sync. Scope defecto: solo instrumentos en listas. Alternativa: todos los activos desfasados.",
      when: "Cada scanIntervalMinutes (def. 30) escanea el universo; ~1 valor / 15 s + minDelaySeconds + throttle Yahoo. Opcional post-cierre Madrid.",
    },
    {
      who: "Listas de valores",
      what: "Cierre / % desde BD. Icono sync = frescura calendario (verde al día, azul desfasado, rojo error, gris vacío). Live quote solo filas expandidas (~15 s).",
      when: "No lanzan sync al abrir la lista; confían en la cola (o sync manual / gráfico).",
    },
    {
      who: "Pestaña de gráfico abierta",
      what: "Si el TF es 1d y empty/stale, sync Yahoo una vez al abrir.",
      when: "Atajo; no sustituye la cola de listas.",
    },
    {
      who: "Rastreadores",
      what: "Leen velas en BD. Sin barras suficientes → saltan el valor. Híbrido puede refrescar solo fundamentales stale.",
      when: "Con scope=listas + auto-sync activo, el universo del rastreador suele estar listo tras el ciclo de cola.",
    },
  ],
} as const;

export const DATA_MARKET_NEXT = [
  "Probar sync manual de un valor IBEX y revisar badge de frescura.",
  "Opcional: arrancar pnpm xtb:mock y Validar con XTB desde la ficha del instrumento.",
  "Ajustar cola en Configuración → Sync / proveedores si quieres sync solo post-cierre.",
  "Comprobar auto-sync activo antes de confiar en un rastreador masivo.",
  "Revisar Configuración → BD (conteos y huérfanos) tras limpiar listas de prueba.",
] as const;

/**
 * Verificación SECUENCIAL de proveedores y sincronismo (Config → Sync / proveedores).
 *
 * Cada paso declara qué hace el usuario, qué debe ver y dónde se comprueba. Es el mismo
 * recorrido que ejecutan las pruebas `PRV-*`, `SYN-*` y `UI-*` del documento
 * `docs/engineering/seguimiento-ui-proveedores-2026-10-29.md`: si un paso no se cumple,
 * el defecto se registra allí con su ID.
 */
export const DATA_PROVIDER_VERIFY = [
  {
    id: "HLP-1",
    title: "1 · Abrir la configuración de proveedores",
    action:
      "Configuración → Sync / proveedores. Observa las tarjetas de Yahoo Finance y XTB Bridge.",
    expect:
      "Cada tarjeta muestra capacidades, prioridad, intervalo y un estado HONESTO: «Sin verificar» si nunca se ha medido, no «Disponible».",
    check: "Pantalla · GET /api/market/providers",
  },
  {
    id: "HLP-2",
    title: "2 · Verificar XTB con el bridge simulado",
    action: "Arranca `pnpm xtb:mock` y pulsa «Probar conexión» en XTB Bridge.",
    expect:
      "«Conexión OK» con el mensaje del bridge. Al recargar, la hora de última verificación sigue ahí (se ha persistido).",
    check:
      "Pantalla · POST /api/market/providers/xtb/test · tabla market_provider_settings",
  },
  {
    id: "HLP-3",
    title: "3 · Verificar Yahoo",
    action:
      "Pulsa «Probar conexión» en Yahoo Finance (hace una petición real acotada).",
    expect:
      "Precio de referencia de ^IBEX con su marca de tiempo, o un motivo de fallo legible si no hay red. Nunca un 500.",
    check: "Pantalla · POST /api/market/providers/yahoo/test",
  },
  {
    id: "HLP-4",
    title: "4 · Guardar prioridad e intervalo",
    action:
      "Cambia la prioridad o el intervalo mínimo y pulsa «Guardar» en la tarjeta.",
    expect:
      "Un solo PATCH, mensaje de guardado y el valor persiste tras recargar la página. El throttle del cliente Yahoo se aplica en el siguiente tick.",
    check:
      "Pantalla · PATCH /api/market/providers/{id} · columna min_interval_seconds",
  },
  {
    id: "HLP-5",
    title: "5 · Deshabilitar Yahoo y comprobar el fallo cerrado",
    action:
      "Desmarca «Usar este proveedor» en Yahoo. Mira el aviso de Sincronización y pulsa «Encolar valores desactualizados ahora».",
    expect:
      "Aviso visible de proveedor deshabilitado; la respuesta declara `skippedReason=provider_disabled:yahoo` y no se encola nada. Un sync manual devuelve 409 con el mismo motivo.",
    check:
      "Pantalla · POST /api/sync/queue/enqueue-stale · POST /api/instruments/{id}/sync",
  },
  {
    id: "HLP-6",
    title: "6 · Rehabilitar y encolar de verdad",
    action:
      "Vuelve a habilitar Yahoo y pulsa «Encolar valores desactualizados ahora».",
    expect:
      "Se informa de escaneados/encolados y la cola muestra estados traducidos (Pendiente, Procesando, Fallido) y el último error cuando lo hay.",
    check: "Pantalla · GET /api/sync/queue · tabla sync_queue",
  },
  {
    id: "HLP-7",
    title: "7 · Guardar la configuración de la cola",
    action:
      "En Sincronización automática cambia intervalo, pausa, reintentos o universo y pulsa «Guardar cambios».",
    expect:
      "Un único PATCH con los campos cambiados; los valores fuera de rango bloquean el guardado con mensaje; tras recargar se mantienen.",
    check: "Pantalla · PATCH /api/sync/settings · tabla sync_settings",
  },
  {
    id: "HLP-8",
    title: "8 · Comprobar el icono de servidores en la barra de estado",
    action:
      "Ve a Mercado. En la barra inferior, mira el icono de servidores de datos (a la derecha) y, si quieres, apágalo desde el engranaje de esa misma barra.",
    expect:
      "Verde si todos los proveedores habilitados responden, rojo si alguno cae. Al reiniciar la API la medición se rehace sola. Un clic en el icono abre Configuración · Sync / proveedores; el engranaje de la barra decide si el icono se muestra.",
    check:
      "Pantalla · GET /api/market/providers/health · columna last_check_at de market_provider_settings",
  },
] as const;
