"""
PostgreSQL access layer via SQLAlchemy.

All connection data (host, port, database name, schema, user,
password) comes from environment variables (.env) - no credentials
or connection data are hardcoded in code or in config.yaml.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_engine(config: dict) -> Engine:
    """
    The `config` parameter is kept in the signature for consistency
    with the rest of the pipeline's functions, but the connection
    itself depends only on .env.
    """
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    database = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    schema = os.getenv("DB_SCHEMA", "public")

    required = {"DB_HOST": host, "DB_PORT": port, "DB_NAME": database,
                "DB_USER": user, "DB_PASSWORD": password}
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            f"Missing environment variables in .env: {', '.join(missing)}"
        )

    url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"

    return create_engine(url, connect_args={"options": f"-csearch_path={schema}"})