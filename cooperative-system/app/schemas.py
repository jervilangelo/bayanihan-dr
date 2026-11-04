"""Pydantic request/response contracts. Decimals serialize as strings to avoid float rounding."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

FarmerStatus = Literal["active", "inactive"]
ItemCategory = Literal["seed", "fertilizer", "pesticide", "produce", "equipment"]
TransactionType = Literal["sale", "purchase", "contribution"]

Name = Annotated[str, Field(min_length=1, max_length=60)]
Place = Annotated[str, Field(min_length=1, max_length=80)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Quantity = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Phone = Annotated[str, Field(pattern=r"^[0-9+\- ]{7,20}$")]

T = TypeVar("T")


class StrictModel(BaseModel):
    """Rejects unknown fields so read-only columns (e.g. share_capital) cannot be smuggled in."""

    model_config = ConfigDict(extra="forbid")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# ---------- farmers ----------

class FarmerBase(StrictModel):
    first_name: Name
    last_name: Name
    barangay: Place
    municipality: Place = "Naga City"
    province: Place = "Camarines Sur"
    phone: Phone | None = None
    farm_size_hectares: Annotated[Decimal, Field(ge=0, le=1000, max_digits=6, decimal_places=2)] = Decimal("0")
    primary_crop: Annotated[str, Field(min_length=1, max_length=40)]
    membership_date: date
    status: FarmerStatus = "active"


class FarmerCreate(FarmerBase):
    member_code: Annotated[str, Field(pattern=r"^BFC-\d{5}$")]


class FarmerUpdate(StrictModel):
    first_name: Name | None = None
    last_name: Name | None = None
    barangay: Place | None = None
    municipality: Place | None = None
    province: Place | None = None
    phone: Phone | None = None
    farm_size_hectares: Annotated[Decimal, Field(ge=0, le=1000, max_digits=6, decimal_places=2)] | None = None
    primary_crop: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    membership_date: date | None = None
    status: FarmerStatus | None = None


class FarmerRead(FarmerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    member_code: str
    share_capital: Decimal
    created_at: datetime
    updated_at: datetime


# ---------- inventory ----------

class InventoryBase(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    category: ItemCategory
    unit: Annotated[str, Field(min_length=1, max_length=20)]
    quantity_on_hand: Quantity = Decimal("0")
    unit_price: Money
    reorder_level: Quantity = Decimal("0")


class InventoryCreate(InventoryBase):
    sku: Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9-]{2,19}$")]


class InventoryUpdate(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    category: ItemCategory | None = None
    unit: Annotated[str, Field(min_length=1, max_length=20)] | None = None
    quantity_on_hand: Quantity | None = None
    unit_price: Money | None = None
    reorder_level: Quantity | None = None


class InventoryRead(InventoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def is_low_stock(self) -> bool:
        return self.reorder_level > 0 and self.quantity_on_hand <= self.reorder_level


# ---------- transactions ----------

class TransactionCreate(StrictModel):
    type: TransactionType
    farmer_id: int
    item_id: int | None = None
    quantity: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)] | None = None
    unit_price: Money | None = None
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)] | None = None
    occurred_at: datetime | None = None
    notes: Annotated[str, Field(max_length=255)] | None = None

    @model_validator(mode="after")
    def _check_shape(self):
        if self.type == "contribution":
            if self.item_id is not None or self.quantity is not None or self.unit_price is not None:
                raise ValueError("contribution must not reference an item, quantity or unit_price")
            if self.amount is None:
                raise ValueError("contribution requires a positive amount")
        else:
            if self.item_id is None or self.quantity is None:
                raise ValueError(f"{self.type} requires item_id and quantity")
            if self.amount is not None:
                raise ValueError(f"{self.type} amount is computed from quantity x unit_price")
        return self


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    type: TransactionType
    farmer_id: int
    item_id: int | None
    quantity: Decimal | None
    unit_price: Decimal | None
    amount: Decimal
    occurred_at: datetime
    notes: str | None
    created_at: datetime


# ---------- reports ----------

class TypeTotals(BaseModel):
    count: int
    amount: Decimal


class MemberCounts(BaseModel):
    total: int
    active: int
    inactive: int


class InventorySummary(BaseModel):
    items: int
    low_stock: int
    stock_value: Decimal


class TransactionSummary(BaseModel):
    count: int
    by_type: dict[TransactionType, TypeTotals]


class ReportSummary(BaseModel):
    generated_at: datetime
    members: MemberCounts
    inventory: InventorySummary
    transactions: TransactionSummary
    total_share_capital: Decimal
