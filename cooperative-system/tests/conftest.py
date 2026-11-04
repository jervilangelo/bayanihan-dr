"""Shared fixtures.

Tests run against a real PostgreSQL database (``cms_test``) so constraints, numerics and row locks are
exercised exactly as in production. A guard refuses to run against any database whose name does not end
in ``_test``, so the suite can never truncate real cooperative data.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import make_url, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine
from app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES = ("transactions", "inventory_items", "farmers")


def alembic_config() -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    db_name = make_url(get_settings().database_url).database or ""
    if not db_name.endswith("_test"):
        pytest.exit(f"Refusing to run tests against non-test database '{db_name}'", returncode=2)
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


# ---------- payload factories ----------

def farmer_payload(**overrides) -> dict:
    payload = {
        "member_code": "BFC-00001",
        "first_name": "Maria",
        "last_name": "Dela Cruz",
        "barangay": "Pacol",
        "municipality": "Naga City",
        "province": "Camarines Sur",
        "phone": "0900-000-0001",
        "farm_size_hectares": "1.50",
        "primary_crop": "Rice",
        "membership_date": "2019-06-15",
        "status": "active",
    }
    payload.update(overrides)
    return payload


def item_payload(**overrides) -> dict:
    payload = {
        "sku": "FERT-UREA-50",
        "name": "Urea fertilizer 46-0-0 (50 kg bag)",
        "category": "fertilizer",
        "unit": "bag",
        "quantity_on_hand": "100.00",
        "unit_price": "1450.00",
        "reorder_level": "20.00",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def farmer(client) -> dict:
    resp = client.post("/api/v1/farmers", json=farmer_payload())
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def item(client) -> dict:
    resp = client.post("/api/v1/inventory", json=item_payload())
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def produce_item(client) -> dict:
    resp = client.post(
        "/api/v1/inventory",
        json=item_payload(
            sku="PROD-PALAY-KG",
            name="Palay (unmilled rice), per kg",
            category="produce",
            unit="kg",
            quantity_on_hand="0.00",
            unit_price="22.00",
            reorder_level="0.00",
        ),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
