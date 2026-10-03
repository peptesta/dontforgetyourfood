import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, String, Text, false
from sqlalchemy import func as sa_func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("idx_products_household_scadenza", "household_id", "data_scadenza"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id"), nullable=False
    )
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    data_scadenza: Mapped[date] = mapped_column(Date, nullable=False)
    data_aggiunta: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_func.now())
    stato: Mapped[str] = mapped_column(String(20), server_default="attivo")
    notificato_3gg: Mapped[bool] = mapped_column(Boolean, server_default=false())
    notificato_1gg: Mapped[bool] = mapped_column(Boolean, server_default=false())
    ocr_raw_text: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    # copiata da BatchItem.foto_titolo_key alla conferma (stesso file fisico, vedi
    # services/image_storage.py) — serve a mostrare la miniatura nella dispensa.
    foto_titolo_key: Mapped[str | None] = mapped_column(String(255))
    # riferimento logico a batch_items.id: niente FK per evitare dipendenza circolare
    # (batch_items.product_id referenzia a sua volta products.id)
    batch_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_func.now(), onupdate=sa_func.now()
    )
