"""Alembic environment — reads MEMES_DATABASE_URL from memes_shared config."""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make repo root + shared importable
ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "shared")):
    if p not in sys.path:
        sys.path.insert(0, p)

from memes_shared.config import get_settings  # noqa: E402
from memes_shared.db.base import Base  # noqa: E402
import memes_shared.models  # noqa: F401,E402  (register all tables)

config = context.config

if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().effective_database_url)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
