from pathlib import Path

from sqlalchemy import create_engine, text

url = None
for line in Path(__file__).resolve().parents[3].joinpath(".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        url = line.split("=", 1)[1].strip().strip('"')
        break

if not url:
    raise SystemExit("DATABASE_URL not found")

engine = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
with engine.connect() as conn:
    enums = conn.execute(
        text(
            """
            SELECT typname, enumlabel
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE typname ILIKE '%timeframe%'
            ORDER BY 1, 2
            """
        )
    ).fetchall()
    print("enums:", enums)
    cols = conn.execute(
        text(
            """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'ohlcv_bars'
              AND column_name IN ('timeframe', 'timestamp')
            """
        )
    ).fetchall()
    print("columns:", cols)
    try:
        migrations = conn.execute(
            text("SELECT migration_name, finished_at FROM _prisma_migrations ORDER BY finished_at")
        ).fetchall()
        print("migrations:", migrations)
    except Exception as exc:
        print("migrations table:", exc)
