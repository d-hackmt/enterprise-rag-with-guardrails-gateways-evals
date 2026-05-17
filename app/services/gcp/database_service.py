import os
import logfire

_pool = None


def get_db_pool():
    """
    Returns a psycopg3 ConnectionPool for LangGraph PostgresSaver.

    Connection strategy:
      - Cloud Run:  DB_HOST = /cloudsql/<connection_name>  (Unix socket via mounted volume)
      - Local dev:  DB_HOST = localhost or IP              (TCP)

    Returns None if any required env var is missing — callers fall back to MemorySaver.
    """
    global _pool
    if _pool is not None:
        return _pool

    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_name = os.getenv("DB_NAME")

    if not all([db_host, db_user, db_pass, db_name]):
        logfire.info("ℹ️ DB env vars not set — Postgres pool skipped")
        return None

    try:
        from psycopg_pool import ConnectionPool

        # Unix socket path (Cloud Run): /cloudsql/project:region:instance
        # TCP host (local dev): localhost or IP address
        conninfo = (
            f"host={db_host} dbname={db_name} user={db_user} password={db_pass}"
        )

        _pool = ConnectionPool(conninfo, min_size=1, max_size=5, open=True)
        logfire.info("✅ Postgres connection pool initialized")
        return _pool

    except Exception as e:
        logfire.error(f"❌ Postgres pool init failed: {e}")
        return None
