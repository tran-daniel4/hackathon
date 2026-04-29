import asyncio
import os
import sys
from logging.config import fileConfig

# asyncpg is incompatible with Windows ProactorEventLoop (the default on Python 3.8+).
# Switch to SelectorEventLoop when running migrations locally on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

from db.base import Base
import models.user  # noqa: F401 — registers User with Base.metadata

# override=True ensures .env values win over any stale shell environment variables
load_dotenv(find_dotenv(), override=True)

config = context.config
# ALEMBIC_DATABASE_URL uses localhost for running migrations from the host machine.
# DATABASE_URL uses the Docker service name and is used by the running API container.
db_url = os.environ.get("ALEMBIC_DATABASE_URL") or os.environ["DATABASE_URL"]
print(f"[alembic] connecting to: {db_url}")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(db_url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
