from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from budget.config import settings
from budget.models import Base

if context.config.config_file_name and context.config.attributes.get("configure_logger", True):
    fileConfig(context.config.config_file_name)

# NullPool: a one-shot migration run should not leave a connection pool behind.
with create_engine(settings.database_url, poolclass=NullPool).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
