from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from bdr_engine.config import DbTarget, RetentionPolicy, Settings
from bdr_engine.store import BackupStore

SOURCE_DB = "bdr_src_test"
TABLES = ("farmers", "inventory_items", "transactions")


def _target(dbname: str) -> DbTarget | None:
    host = os.environ.get("BDR_TEST_PG_HOST")
    if not host:
        return None
    return DbTarget(
        host=host,
        port=int(os.environ.get("BDR_TEST_PG_PORT", "5432")),
        user=os.environ.get("BDR_TEST_PG_USER", "postgres"),
        password=os.environ["BDR_TEST_PG_PASSWORD"],
        dbname=dbname,
    )


def make_settings(tmp_path: Path, source: DbTarget | None = None, verify: DbTarget | None = None) -> Settings:
    dummy = DbTarget("unused", 5432, "unused", "unused", "unused")
    return Settings(
        source=source or dummy,
        verify=verify or dummy,
        backup_dir=tmp_path / "backups",
        tables=TABLES,
        retention=RetentionPolicy(keep_all_hours=24, keep_daily_days=7),
        dump_timeout_seconds=120,
        restore_timeout_seconds=120,
    )


@pytest.fixture
def store(tmp_path: Path) -> BackupStore:
    return BackupStore(tmp_path / "backups")


@pytest.fixture(scope="session")
def pg_server() -> DbTarget:
    target = _target("postgres")
    if target is None:
        pytest.skip("integration tests need BDR_TEST_PG_HOST (run them with the backup-tests compose service)")
    return target


@pytest.fixture
def source_db(pg_server: DbTarget) -> Iterator[DbTarget]:
    """A small CMS-shaped database with known record counts: 5 farmers, 3 items, 7 transactions."""
    import psycopg

    from bdr_engine import pg

    pg.drop_database(pg_server, SOURCE_DB)
    pg.create_database(pg_server, SOURCE_DB)
    source = DbTarget(pg_server.host, pg_server.port, pg_server.user, pg_server.password, SOURCE_DB)
    with psycopg.connect(**source.conninfo()) as conn:
        conn.execute("CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)")
        conn.execute("INSERT INTO alembic_version VALUES ('0001')")
        conn.execute("CREATE TABLE farmers (id serial PRIMARY KEY, name text NOT NULL)")
        conn.execute("CREATE TABLE inventory_items (id serial PRIMARY KEY, name text NOT NULL)")
        conn.execute("CREATE TABLE transactions (id serial PRIMARY KEY, amount numeric(12,2) NOT NULL)")
        conn.execute("INSERT INTO farmers (name) SELECT 'Farmer ' || g FROM generate_series(1, 5) g")
        conn.execute("INSERT INTO inventory_items (name) SELECT 'Item ' || g FROM generate_series(1, 3) g")
        conn.execute("INSERT INTO transactions (amount) SELECT g * 10.5 FROM generate_series(1, 7) g")
    yield source
    pg.drop_database(pg_server, SOURCE_DB)


@pytest.fixture
def live_settings(tmp_path: Path, source_db: DbTarget, pg_server: DbTarget) -> Settings:
    return make_settings(tmp_path, source=source_db, verify=pg_server)
