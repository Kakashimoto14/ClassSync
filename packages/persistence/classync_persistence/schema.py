"""Explicit-connection Alembic entry point. Never migrate on service startup."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection


def migrate(connection: Connection, *, target: str = "head", downgrade: bool = False):
    if connection.dialect.name != "postgresql":
        raise ValueError("Identity migrations require an explicit PostgreSQL connection")
    if not connection.in_transaction():
        raise ValueError("Identity migrations require a caller-owned transaction")
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    config.attributes["connection"] = connection
    if downgrade:
        command.downgrade(config, target)
    else:
        command.upgrade(config, target)
