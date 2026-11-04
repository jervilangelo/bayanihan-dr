"""Deterministic SYNTHETIC seed data for the Bicol Farmers Cooperative demo.

Every name is a random combination of common Filipino given names and surnames; none refers to a real
person. Phone numbers use the placeholder range 0900-000-xxxx. Place names are public geographic names.

The generator is seeded (ADR-005), so every fresh seed produces identical record counts and totals.
The disaster-recovery drill relies on this to verify a restored database.

Usage (inside the api container):
    python -m app.seed            # refuses to run if data already exists
    python -m app.seed --reset    # TRUNCATES all CMS tables first (destructive; local demo only)
"""

import argparse
import json
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Farmer, InventoryItem, Transaction
from app.services import CENT, reference_for

RANDOM_SEED = 2026
FARMER_COUNT = 1050
TRANSACTION_COUNT = 3000
LEDGER_START = datetime(2025, 11, 1, tzinfo=UTC)
LEDGER_DAYS = 365

GIVEN_NAMES = (
    "Maria", "Jose", "Juan", "Ana", "Antonio", "Rosario", "Ramon", "Teresita", "Eduardo", "Luzviminda",
    "Rogelio", "Corazon", "Ernesto", "Leonora", "Danilo", "Imelda", "Reynaldo", "Marites", "Rodel", "Jocelyn",
    "Arnel", "Divina", "Nestor", "Erlinda", "Romeo", "Nenita", "Wilfredo", "Gemma", "Joel", "Lorna",
    "Mark", "Kristine", "Jayson", "Angelica", "Ronald", "Mylene", "Christian", "Rowena", "Allan", "Shiela",
)
SURNAMES = (
    "Dela Cruz", "Santos", "Reyes", "Garcia", "Mendoza", "Bautista", "Villanueva", "Ramos", "Aquino", "Castillo",
    "Rivera", "Navarro", "Torres", "Flores", "Gonzales", "Lopez", "Morales", "Perez", "Sarmiento", "Bernal",
    "Obias", "Abonal", "Buenaflor", "Lanuza", "Bersabe", "Oñate", "Prado", "Rosales", "Nacario", "Malate",
    "Llorin", "Imperial", "Badiola", "Regmalos", "Tria", "Azur", "Belmonte", "Clores", "Dimaano", "Esplana",
)
NAGA_BARANGAYS = (
    "Abella", "Bagumbayan Norte", "Bagumbayan Sur", "Balatas", "Calauag", "Cararayan", "Carolina",
    "Concepcion Grande", "Concepcion Pequeña", "Dayangdang", "Del Rosario", "Dinaga", "Lerma", "Liboton",
    "Mabolo", "Pacol", "Panicuason", "Peñafrancia", "Sabang", "San Felipe", "San Isidro", "Santa Cruz",
    "Tabuco", "Tinago", "Triangulo",
)
NEARBY_TOWNS = ("Pili", "Canaman", "Magarao", "Milaor", "Camaligan", "Gainza", "Bombon", "Calabanga")
CROPS = ("Rice", "Rice", "Rice", "Corn", "Coconut", "Pili nut", "Abaca", "Vegetables", "Pineapple", "Sugarcane")

# sku, name, category, unit, opening stock, unit price (PHP), reorder level
CATALOGUE: tuple[tuple[str, str, str, str, int, str, int], ...] = (
    ("SEED-RC222-20", "Certified rice seed NSIC Rc222 (20 kg)", "seed", "bag", 400, "1250.00", 60),
    ("SEED-RC216-20", "Certified rice seed NSIC Rc216 (20 kg)", "seed", "bag", 300, "1300.00", 50),
    ("SEED-HYB-RICE", "Hybrid rice seed (15 kg)", "seed", "bag", 150, "4800.00", 25),
    ("SEED-CORN-YLW", "Yellow corn hybrid seed (18 kg)", "seed", "bag", 200, "5200.00", 30),
    ("SEED-VEG-PACK", "Assorted vegetable seed pack", "seed", "pack", 800, "85.00", 100),
    ("FERT-UREA-50", "Urea 46-0-0 (50 kg)", "fertilizer", "bag", 900, "1450.00", 150),
    ("FERT-COMP-50", "Complete 14-14-14 (50 kg)", "fertilizer", "bag", 700, "1650.00", 120),
    ("FERT-AMSUL-50", "Ammonium sulfate 21-0-0 (50 kg)", "fertilizer", "bag", 500, "950.00", 80),
    ("FERT-MOP-50", "Muriate of potash 0-0-60 (50 kg)", "fertilizer", "bag", 300, "1700.00", 50),
    ("FERT-ORG-50", "Organic fertilizer (50 kg)", "fertilizer", "bag", 600, "450.00", 100),
    ("FERT-FOLIAR-1L", "Foliar fertilizer (1 L)", "fertilizer", "bottle", 400, "380.00", 60),
    ("PEST-HERB-1L", "Pre-emergence herbicide (1 L)", "pesticide", "bottle", 350, "520.00", 50),
    ("PEST-INSECT-1L", "Insecticide (1 L)", "pesticide", "bottle", 300, "690.00", 50),
    ("PEST-FUNGI-500", "Fungicide (500 g)", "pesticide", "pack", 250, "430.00", 40),
    ("PEST-MOLLUS-1K", "Molluscicide for golden apple snail (1 kg)", "pesticide", "pack", 200, "310.00", 40),
    ("EQP-SPRAYER-16", "Knapsack sprayer (16 L)", "equipment", "unit", 60, "1850.00", 10),
    ("EQP-BOLO", "Farm bolo", "equipment", "unit", 120, "350.00", 20),
    ("EQP-SACK-50", "Woven polypropylene sack (50 kg)", "equipment", "piece", 5000, "12.00", 800),
    ("EQP-TARP-4X6", "Drying tarpaulin 4 x 6 m", "equipment", "unit", 80, "780.00", 15),
    ("EQP-BOOTS", "Rubber farm boots", "equipment", "pair", 150, "420.00", 25),
    ("PROD-PALAY-KG", "Palay (unmilled rice)", "produce", "kg", 0, "22.00", 0),
    ("PROD-CORN-KG", "Dried yellow corn", "produce", "kg", 0, "17.50", 0),
    ("PROD-COPRA-KG", "Copra", "produce", "kg", 0, "38.00", 0),
    ("PROD-PILI-KG", "Pili nut (in shell)", "produce", "kg", 0, "65.00", 0),
    ("PROD-ABACA-KG", "Abaca fiber", "produce", "kg", 0, "95.00", 0),
    ("PROD-VEG-KG", "Mixed vegetables", "produce", "kg", 0, "40.00", 0),
)


class SeedError(RuntimeError):
    pass


def _is_empty(db: Session) -> bool:
    return all(
        db.scalar(select(func.count()).select_from(model)) == 0 for model in (Farmer, InventoryItem, Transaction)
    )


def _build_farmers(rng: random.Random) -> list[Farmer]:
    farmers = []
    for n in range(1, FARMER_COUNT + 1):
        in_naga = rng.random() < 0.7
        farmers.append(
            Farmer(
                member_code=f"BFC-{n:05d}",
                first_name=rng.choice(GIVEN_NAMES),
                last_name=rng.choice(SURNAMES),
                barangay=rng.choice(NAGA_BARANGAYS) if in_naga else "Poblacion",
                municipality="Naga City" if in_naga else rng.choice(NEARBY_TOWNS),
                province="Camarines Sur",
                phone=f"0900-000-{n:04d}",
                farm_size_hectares=Decimal(rng.randint(25, 500)) / 100,
                primary_crop=rng.choice(CROPS),
                membership_date=date(2005, 1, 1) + timedelta(days=rng.randint(0, 7300)),
                status="inactive" if rng.random() < 0.08 else "active",
                share_capital=Decimal("0.00"),
            )
        )
    return farmers


def _build_items() -> list[InventoryItem]:
    return [
        InventoryItem(
            sku=sku,
            name=name,
            category=category,
            unit=unit,
            quantity_on_hand=Decimal(opening),
            unit_price=Decimal(price),
            reorder_level=Decimal(reorder),
        )
        for sku, name, category, unit, opening, price, reorder in CATALOGUE
    ]


def _build_transactions(rng: random.Random, farmers: list[Farmer], items: list[InventoryItem]) -> list[Transaction]:
    """Generate ledger entries while applying the same rules as ``services.create_transaction``."""
    active = [f for f in farmers if f.status == "active"]
    inputs = [i for i in items if i.category != "produce"]
    produce = [i for i in items if i.category == "produce"]
    timestamps = sorted(
        LEDGER_START + timedelta(minutes=rng.randint(0, LEDGER_DAYS * 24 * 60)) for _ in range(TRANSACTION_COUNT)
    )

    txns: list[Transaction] = []
    for occurred_at in timestamps:
        roll = rng.random()
        if roll < 0.45:
            item = rng.choice(inputs)
            quantity = Decimal(rng.randint(1, 10))
            if item.quantity_on_hand < quantity:  # out of stock: record a contribution instead
                roll = 1.0
            else:
                farmer = rng.choice(active)
                item.quantity_on_hand -= quantity
                txns.append(_txn("sale", farmer, item, quantity, item.unit_price, occurred_at))
                continue
        if roll < 0.75:
            item = rng.choice(produce)
            farmer = rng.choice(farmers)
            quantity = Decimal(rng.randint(50, 1500))
            item.quantity_on_hand += quantity
            txns.append(_txn("purchase", farmer, item, quantity, item.unit_price, occurred_at))
        else:
            farmer = rng.choice(farmers)
            amount = Decimal(rng.randint(2, 40) * 50).quantize(CENT)
            farmer.share_capital += amount
            txns.append(
                Transaction(type="contribution", farmer=farmer, amount=amount, occurred_at=occurred_at,
                            notes="Share capital contribution")
            )
    return txns


def _txn(kind, farmer, item, quantity, unit_price, occurred_at) -> Transaction:
    return Transaction(
        type=kind,
        farmer=farmer,
        item=item,
        quantity=quantity,
        unit_price=unit_price,
        amount=(quantity * unit_price).quantize(CENT),
        occurred_at=occurred_at,
    )


def run(reset: bool = False) -> dict[str, int]:
    rng = random.Random(RANDOM_SEED)
    with Session(engine) as db:
        if reset:
            db.execute(text("TRUNCATE transactions, inventory_items, farmers RESTART IDENTITY CASCADE"))
        elif not _is_empty(db):
            raise SeedError("database already contains CMS data; re-run with --reset to replace it")

        farmers = _build_farmers(rng)
        items = _build_items()
        db.add_all(farmers)
        db.add_all(items)
        db.flush()

        txns = _build_transactions(rng, farmers, items)
        db.add_all(txns)
        db.flush()
        for txn in txns:
            txn.reference = reference_for(txn.id)
        db.commit()

    return {"farmers": len(farmers), "inventory_items": len(items), "transactions": len(txns)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="truncate existing CMS data first (destructive)")
    args = parser.parse_args()
    try:
        print(json.dumps({"seeded": run(reset=args.reset)}))
    except SeedError as exc:
        raise SystemExit(f"seed aborted: {exc}") from exc


if __name__ == "__main__":
    main()
