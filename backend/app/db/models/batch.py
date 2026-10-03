import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, false
from sqlalchemy import func as sa_func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    stato: Mapped[str] = mapped_column(String(20), server_default="in_elaborazione")
    creato_il: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_func.now())
    totale_prodotti: Mapped[int] = mapped_column(Integer, nullable=False)
    completate: Mapped[int] = mapped_column(Integer, server_default="0")

    items: Mapped[list["BatchItem"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class BatchItem(Base):
    __tablename__ = "batch_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False
    )
    ordine_upload: Mapped[int] = mapped_column(Integer, nullable=False)
    # stato: in_coda | in_elaborazione | completato | parziale (un solo lato ok) | errore
    stato: Mapped[str] = mapped_column(String(20), server_default="in_coda")
    nome_candidato: Mapped[str | None] = mapped_column(String(255))
    nome_suggerito: Mapped[str | None] = mapped_column(String(255))
    data_candidata: Mapped[date | None] = mapped_column(Date)
    data_candidati_alternativi: Mapped[list | None] = mapped_column(JSONB)
    ocr_raw_text_titolo: Mapped[str | None] = mapped_column(Text)
    ocr_raw_text_data: Mapped[str | None] = mapped_column(Text)
    confidence_titolo: Mapped[float | None] = mapped_column(Float)
    confidence_data: Mapped[float | None] = mapped_column(Float)
    errore_titolo: Mapped[str | None] = mapped_column(Text)
    errore_data: Mapped[str | None] = mapped_column(Text)
    confermato: Mapped[bool] = mapped_column(Boolean, server_default=false())
    # riferimento logico a products.id, valorizzato solo dopo la conferma: niente FK
    # per evitare dipendenza circolare con products.batch_item_id
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # chiave nello storage immagini (vedi services/image_storage.py) della foto del
    # titolo, salvata subito all'upload perché è l'unico momento in cui i byte grezzi
    # sono disponibili — al contrario delle altre colonne OCR, sopravvive anche se il
    # batch non viene mai confermato (limite noto: nessuna pulizia automatica oggi).
    foto_titolo_key: Mapped[str | None] = mapped_column(String(255))

    batch: Mapped["Batch"] = relationship(back_populates="items")
