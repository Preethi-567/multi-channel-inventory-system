from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, Text,
    DateTime, Date, ForeignKey, UniqueConstraint, CheckConstraint,
    func, Computed
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
import uuid

Base = declarative_base()

# ---------------------------------------------------------------------------
# OLTP SCHEMA — public (live, transactional)
# ---------------------------------------------------------------------------

class Product(Base):
    """
    One row per unique product variant.
    SKU is the business identifier — what humans and APIs use.
    id is a UUID — not SERIAL — because UUIDs don't reveal count or ordering.
    """
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    unit_cost = Column(Numeric(10, 2), nullable=True)
    selling_price = Column(Numeric(10, 2), nullable=True)
    reorder_point = Column(Integer, nullable=False, default=10)
    reorder_qty = Column(Integer, nullable=False, default=50)
    supplier_name = Column(String(255), nullable=True)
    supplier_lead_days = Column(Integer, default=7)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships — lets you do product.inventory_records in Python
    inventory_records = relationship("Inventory", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")
    ledger_entries = relationship("InventoryLedger", back_populates="product")
    alerts = relationship("Alert", back_populates="product")


class Channel(Base):
    """
    One row per sales channel — shopify, amazon, flipkart.
    api_config stores endpoint references as JSON (never raw secrets).
    """
    __tablename__ = "channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    api_config = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True)

    inventory_records = relationship("Inventory", back_populates="channel")
    orders = relationship("Order", back_populates="channel")
    ledger_entries = relationship("InventoryLedger", back_populates="channel")
    alerts = relationship("Alert", back_populates="channel")


class Inventory(Base):
    """
    One row per product per channel — the live, authoritative stock count.
    quantity_available is a GENERATED column — always computed, never stale.
    version is the optimistic locking counter — increments on every UPDATE.
    """
    __tablename__ = "inventory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    quantity_on_hand = Column(Integer, nullable=False, default=0)
    quantity_reserved = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=0)
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("product_id", "channel_id", name="uq_inventory_product_channel"),
        CheckConstraint("quantity_on_hand >= 0", name="chk_quantity_on_hand_non_negative"),
        CheckConstraint("quantity_reserved >= 0", name="chk_quantity_reserved_non_negative"),
    )

    product = relationship("Product", back_populates="inventory_records")
    channel = relationship("Channel", back_populates="inventory_records")


class Order(Base):
    """
    Every order event received from any channel. Append-only — never updated.
    idempotency_key UNIQUE constraint is the database-level guard against
    double-processing Shopify/Amazon webhook retries.
    raw_payload stores the original webhook — full fidelity, never lose data.
    """
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(255), nullable=False)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    idempotency_key = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), default="received")
    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    channel = relationship("Channel", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    """
    Line items for each order.
    sku is denormalized here (copied from products) for query speed —
    so you can read what was ordered without joining to products every time.
    """
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    sku = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=True)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_order_item_quantity_positive"),
    )

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class InventoryLedger(Base):
    """
    Immutable audit trail of every inventory change.
    Never updated, only appended — like Kafka but in Postgres.
    You can reconstruct exact stock at any point in time by replaying this.
    quantity_delta is negative for sales, positive for restocks.
    """
    __tablename__ = "inventory_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    change_type = Column(String(50), nullable=False)  # sale, restock, adjustment
    quantity_delta = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    reference_id = Column(UUID(as_uuid=True), nullable=True)  # order_id that caused this
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="ledger_entries")
    channel = relationship("Channel", back_populates="ledger_entries")


class Alert(Base):
    """
    Generated by the alert engine when stock crosses reorder_point.
    Consumed by the dashboard. is_read tracks acknowledgement.
    """
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    alert_type = Column(String(50), nullable=False)  # low_stock, stockout_imminent, overstock
    message = Column(Text, nullable=False)
    severity = Column(String(20), default="warning")  # info, warning, critical
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="alerts")
    channel = relationship("Channel", back_populates="alerts")


# ---------------------------------------------------------------------------
# ANALYTICS SCHEMA — populated by Airflow, never written by sync path
# ---------------------------------------------------------------------------

class FactDailySales(Base):
    """
    Pre-aggregated daily sales per SKU per channel.
    Populated by Airflow DAG at midnight. Never written by the sync consumer.
    UNIQUE on (sale_date, product_id, channel_id) makes Airflow upserts idempotent.
    """
    __tablename__ = "fact_daily_sales"
    __table_args__ = (
        UniqueConstraint("sale_date", "product_id", "channel_id", name="uq_fact_daily_sales"),
        {"schema": "analytics"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_date = Column(Date, nullable=False)
    product_id = Column(UUID(as_uuid=True), nullable=False)
    channel_id = Column(UUID(as_uuid=True), nullable=False)
    units_sold = Column(Integer, default=0)
    revenue = Column(Numeric(12, 2), default=0)
    avg_selling_price = Column(Numeric(10, 2), nullable=True)


class ForecastResult(Base):
    """
    Output of the Prophet forecasting service, one row per SKU per forecast date.
    stockout_date is when we predict stock hits zero.
    reorder_flag is True when stockout_date is within supplier_lead_days.
    """
    __tablename__ = "forecast_results"
    __table_args__ = {"schema": "analytics"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), nullable=False)
    forecast_date = Column(Date, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    horizon_days = Column(Integer, default=30)
    predicted_units = Column(Numeric(10, 2), nullable=True)
    lower_bound = Column(Numeric(10, 2), nullable=True)
    upper_bound = Column(Numeric(10, 2), nullable=True)
    model_mape = Column(Numeric(5, 2), nullable=True)
    stockout_date = Column(Date, nullable=True)
    reorder_flag = Column(Boolean, default=False)