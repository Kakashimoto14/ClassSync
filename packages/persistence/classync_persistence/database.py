"""PostgreSQL transaction boundary; no implicit URL, identity or data fallback."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.engine import URL


def postgres_engine(
    url: URL, *, connect_args: Mapping | None = None, pool_timeout: float = 30,
    pool_size: int = 5, max_overflow: int = 10,
) -> Engine:
    if url.drivername != "postgresql+psycopg":
        raise ValueError("The shared persistence boundary requires PostgreSQL with Psycopg")
    return create_engine(
        url,
        connect_args=dict(connect_args or {}),
        echo=False,
        hide_parameters=True,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
        pool_timeout=pool_timeout,
        pool_size=pool_size,
        max_overflow=max_overflow,
    )


@contextmanager
def transaction(engine: Engine) -> Iterator[Connection]:
    """Commit once on success, roll back on every exception, release the connection."""
    with engine.begin() as connection:
        yield connection
