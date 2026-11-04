from alembic import command
from sqlalchemy import inspect

from app.db import engine
from tests.conftest import alembic_config


def test_migrations_downgrade_and_upgrade_cleanly():
    cfg = alembic_config()

    command.downgrade(cfg, "base")
    tables_after_downgrade = set(inspect(engine).get_table_names())
    assert {"farmers", "inventory_items", "transactions"}.isdisjoint(tables_after_downgrade)

    command.upgrade(cfg, "head")
    tables_after_upgrade = set(inspect(engine).get_table_names())
    assert {"farmers", "inventory_items", "transactions", "alembic_version"} <= tables_after_upgrade
