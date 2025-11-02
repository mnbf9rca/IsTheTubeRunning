import logging
from collections.abc import Collection, Mapping
from logging.config import fileConfig
from typing import Any

from alembic import context
from alembic.runtime.migration import MigrationContext, MigrationInfo

# Import settings and models
from app.core.config import settings
from app.core.utils import convert_async_db_url_to_sync
from app.models import Base  # This will import all models
from sqlalchemy import engine_from_config, pool

logger = logging.getLogger("alembic.env")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with our settings (convert asyncpg to psycopg2 for sync migrations)
database_url = convert_async_db_url_to_sync(settings.DATABASE_URL)
config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Track migrations for logging
        migrations_applied = []

        def on_version_apply(
            ctx: MigrationContext,
            step: MigrationInfo,
            heads: Collection[Any],
            run_args: Mapping[str, Any],
        ) -> None:
            """Callback when a migration is applied."""
            migrations_applied.append(step.up_revision_id)
            logger.info(f"Applying migration {step.up_revision_id}")

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            on_version_apply=on_version_apply,
        )

        # Get current and target revisions
        migration_context = context.get_context()
        current_rev = migration_context.get_current_revision()
        script = context.script
        head_rev = script.get_current_head()

        # Log migration status
        if current_rev == head_rev:
            logger.info(f"✓ Database already at target revision: {head_rev or 'base'}")
        elif current_rev is None:
            logger.info(f"Initializing database to revision: {head_rev}")
        else:
            logger.info(f"Upgrading database from {current_rev} to {head_rev}")

        with context.begin_transaction():
            context.run_migrations()

        # Log completion
        if migrations_applied:
            logger.info(
                f"✓ Successfully applied {len(migrations_applied)} migration(s). Database now at revision: {head_rev}"
            )
        elif current_rev != head_rev:
            # This shouldn't happen, but log it if it does
            logger.warning("Migration completed but no migrations were applied. This may indicate an issue.")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
