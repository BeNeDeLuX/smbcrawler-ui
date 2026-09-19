from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class ScanSource(str, enum.Enum):
    crawl = "crawl"
    import_ = "import"


class ScanStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    canceled = "canceled"
    imported = "imported"


class AnnotationKind(str, enum.Enum):
    path = "path"
    file = "file"
    secret = "secret"


class AnnotationStatus(str, enum.Enum):
    open = "open"
    reviewed = "reviewed"
    false_positive = "false_positive"
    important = "important"


class Scan(Base):
    __tablename__ = "scan"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    source: Mapped[ScanSource] = mapped_column(Enum(ScanSource, name="scan_source"))
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status"), default=ScanStatus.queued, index=True
    )
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    rq_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dir: Mapped[str] = mapped_column(String(500))

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    credential: Mapped["Credential | None"] = relationship(
        back_populates="scan", cascade="all, delete-orphan", uselist=False
    )
    annotations: Mapped[list["Annotation"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class Credential(Base):
    __tablename__ = "credential"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("scan.id", ondelete="CASCADE"), primary_key=True
    )
    blob: Mapped[bytes] = mapped_column(LargeBinary)  # Fernet-encrypted JSON

    scan: Mapped[Scan] = relationship(back_populates="credential")


class Annotation(Base):
    __tablename__ = "annotation"
    __table_args__ = (UniqueConstraint("scan_id", "kind", "ref", name="uq_annotation_ref"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=_uuid)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("scan.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[AnnotationKind] = mapped_column(Enum(AnnotationKind, name="annotation_kind"))
    ref: Mapped[str] = mapped_column(String(512))
    status: Mapped[AnnotationStatus] = mapped_column(
        Enum(AnnotationStatus, name="annotation_status"), default=AnnotationStatus.open
    )
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scan: Mapped[Scan] = relationship(back_populates="annotations")


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
