"""ORM models for persistence."""

from __future__ import annotations

from datetime import datetime

from .connection import SQLALCHEMY_AVAILABLE

if SQLALCHEMY_AVAILABLE:
    from sqlalchemy import (
        JSON,
        Boolean,
        DateTime,
        Float,
        ForeignKey,
        Integer,
        String,
        Text,
    )
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

    class Base(DeclarativeBase):
        pass


    class DealORM(Base):
        __tablename__ = "deals"

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        external_id: Mapped[str] = mapped_column(String(128), index=True)
        status: Mapped[str] = mapped_column(String(32), default="pending_docs")
        metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
        created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
        updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


    class ExtractionRunORM(Base):
        __tablename__ = "extraction_runs"

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        deal_id: Mapped[str] = mapped_column(String(64), index=True)
        pipeline_id: Mapped[str] = mapped_column(String(128), index=True)
        version: Mapped[int] = mapped_column(Integer, default=1)
        status: Mapped[str] = mapped_column(String(32), default="pending")
        document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
        agent_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
        triggered_by: Mapped[str] = mapped_column(String(255), default="")
        created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
        completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
        error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
        metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

        fields: Mapped[list["ExtractedFieldORM"]] = relationship(
            back_populates="run",
            cascade="all, delete-orphan",
        )


    class ExtractedFieldORM(Base):
        __tablename__ = "extracted_fields"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        run_id: Mapped[str] = mapped_column(ForeignKey("extraction_runs.id", ondelete="CASCADE"), index=True)
        field_path: Mapped[str] = mapped_column(String(255), index=True)
        value_json: Mapped[dict | str | list | int | float | bool | None] = mapped_column("value", JSON, nullable=True)
        confidence: Mapped[float] = mapped_column(Float, default=0.0)
        citation_json: Mapped[dict | None] = mapped_column("citation", JSON, nullable=True)
        attested: Mapped[bool] = mapped_column(Boolean, default=False)
        attested_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
        overridden: Mapped[bool] = mapped_column(Boolean, default=False)
        override_value_json: Mapped[dict | str | list | int | float | bool | None] = mapped_column("override_value", JSON, nullable=True)
        override_justification: Mapped[str | None] = mapped_column(Text, nullable=True)

        run: Mapped["ExtractionRunORM"] = relationship(back_populates="fields")


    class ReviewTaskORM(Base):
        __tablename__ = "review_tasks"

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        run_id: Mapped[str] = mapped_column(String(64), index=True)
        run_type: Mapped[str] = mapped_column(String(32), default="extraction")
        assignees: Mapped[list[str]] = mapped_column(JSON, default=list)
        required_attestations: Mapped[int] = mapped_column(Integer, default=1)
        status: Mapped[str] = mapped_column(String(32), default="pending")
        created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
        completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


    class FieldRevisionORM(Base):
        __tablename__ = "field_revisions"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        run_id: Mapped[str] = mapped_column(String(64), index=True)
        run_type: Mapped[str] = mapped_column(String(32), default="extraction")
        field_path: Mapped[str] = mapped_column(String(255), index=True)
        version: Mapped[int] = mapped_column(Integer, default=1)
        value_json: Mapped[dict | str | list | int | float | bool | None] = mapped_column("value", JSON, nullable=True)
        source: Mapped[str] = mapped_column(String(64), default="ai_extracted")
        changed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
        changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
        justification: Mapped[str | None] = mapped_column(Text, nullable=True)


    class AttestationORM(Base):
        __tablename__ = "attestations"

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        task_id: Mapped[str] = mapped_column(String(64), index=True)
        reviewer_id: Mapped[str] = mapped_column(String(128))
        reviewer_email: Mapped[str] = mapped_column(String(255))
        decision: Mapped[str] = mapped_column(String(32))
        fields_attested: Mapped[list[str]] = mapped_column(JSON, default=list)
        overrides: Mapped[list[dict]] = mapped_column(JSON, default=list)
        comments: Mapped[str] = mapped_column(Text, default="")
        timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

else:  # pragma: no cover - placeholder models when SQLAlchemy is unavailable
    class Base:  # type: ignore[no-redef]
        """Placeholder base when SQLAlchemy is unavailable."""


    class DealORM:  # type: ignore[no-redef]
        pass


    class ExtractionRunORM:  # type: ignore[no-redef]
        pass


    class ExtractedFieldORM:  # type: ignore[no-redef]
        pass


    class ReviewTaskORM:  # type: ignore[no-redef]
        pass


    class FieldRevisionORM:  # type: ignore[no-redef]
        pass


    class AttestationORM:  # type: ignore[no-redef]
        pass
