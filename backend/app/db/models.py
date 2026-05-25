import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    AdminFlowType,
    AdminSessionState,
    ApprovalMode,
    MessageDirection,
    MessageType,
    QuoteStatus,
    SessionSource,
    SessionState,
    WorkType,
)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Contractor(Base):
    __tablename__ = "contractors"

    id: Mapped[uuid.UUID] = _uuid_pk()
    phone: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    whatsapp_link_slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    api_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        unique=True,
        index=True,
    )
    wa_phone_number_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    approval_mode: Mapped[ApprovalMode] = mapped_column(
        Enum(ApprovalMode, name="approval_mode"),
        nullable=False,
        default=ApprovalMode.always_approve,
    )
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    pricing_configs: Mapped[list["PricingConfig"]] = relationship(back_populates="contractor")
    sessions: Mapped[list["Session"]] = relationship(back_populates="contractor")
    admin_sessions: Mapped[list["ContractorAdminSession"]] = relationship(
        back_populates="contractor"
    )


class ContractorAdminSession(Base):
    __tablename__ = "contractor_admin_sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    contractor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contractors.id", ondelete="CASCADE"), nullable=True, index=True
    )
    admin_phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    flow_type: Mapped[AdminFlowType] = mapped_column(
        Enum(AdminFlowType, name="admin_flow_type"), nullable=False
    )
    state: Mapped[AdminSessionState] = mapped_column(
        Enum(AdminSessionState, name="admin_session_state"), nullable=False
    )
    work_type: Mapped[WorkType | None] = mapped_column(
        Enum(WorkType, name="work_type"), nullable=True
    )
    draft_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    draft_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parse_notes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    validation_errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    contractor: Mapped[Contractor | None] = relationship(back_populates="admin_sessions")


class PricingConfig(Base):
    __tablename__ = "pricing_configs"
    __table_args__ = (
        Index(
            "ix_pricing_configs_active_per_work_type",
            "contractor_id",
            "work_type",
            unique=True,
            postgresql_where="is_active",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    contractor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contractors.id", ondelete="CASCADE"), nullable=False
    )
    work_type: Mapped[WorkType] = mapped_column(
        Enum(WorkType, name="work_type"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    contractor: Mapped[Contractor] = relationship(back_populates="pricing_configs")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    contractor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contractors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    buyer_phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[SessionSource] = mapped_column(
        Enum(SessionSource, name="session_source"),
        nullable=False,
        default=SessionSource.buyer_direct,
    )
    forward_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    state: Mapped[SessionState] = mapped_column(
        Enum(SessionState, name="session_state"),
        nullable=False,
        default=SessionState.greeting,
    )
    work_type: Mapped[WorkType | None] = mapped_column(
        Enum(WorkType, name="work_type"), nullable=True
    )
    collected_slots: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    missing_slots: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    contractor: Mapped[Contractor] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name="message_direction"), nullable=False
    )
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type"), nullable=False
    )
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_message_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="messages")


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contractor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contractors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    buyer_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    work_type: Mapped[WorkType] = mapped_column(
        Enum(WorkType, name="work_type"), nullable=False
    )
    line_items: Mapped[list] = mapped_column(JSONB, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[QuoteStatus] = mapped_column(
        Enum(QuoteStatus, name="quote_status"),
        nullable=False,
        default=QuoteStatus.draft,
    )
    pdf_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    validity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pricing_config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    contractor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contractors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
