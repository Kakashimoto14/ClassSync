"""Only the explicit caller-owned transaction can select the migration target."""

from alembic import context

connection = context.config.attributes.get("connection")
if connection is None or context.is_offline_mode():
    raise RuntimeError("An explicit online PostgreSQL connection is required")
context.configure(connection=connection, transactional_ddl=True)
with context.begin_transaction():
    context.run_migrations()
