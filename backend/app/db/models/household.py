import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Household(Base):
    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(255), server_default="Casa")
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # se True, l'OCR corregge automaticamente foto capovolte/ruotate (0/90/180/270)
    # prima del riconoscimento testo — costa qualche centinaio di ms in più per foto.
    correggi_orientamento: Mapped[bool] = mapped_column(Boolean, server_default=true())

    users: Mapped[list["User"]] = relationship(back_populates="household")
