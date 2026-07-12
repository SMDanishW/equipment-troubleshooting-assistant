import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="SQLAlchemy 2.0.36 model annotation parsing is incompatible with Python 3.14; the project runtime is Python 3.12.",
)

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


EXPECTED_TABLES = {
    "agent_traces",
    "conversations",
    "document_images",
    "documents",
    "ingestion_jobs",
    "text_chunks",
    "users",
}


def test_initial_migration_upgrades_matches_models_and_downgrades(tmp_path):
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

        inspector = inspect(connection)
        assert EXPECTED_TABLES.issubset(set(inspector.get_table_names()))
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == "20260712_0002"

        command.check(config)
        command.downgrade(config, "base")

        remaining_tables = set(inspect(connection).get_table_names())
        assert EXPECTED_TABLES.isdisjoint(remaining_tables)
