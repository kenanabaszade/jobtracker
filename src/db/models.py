from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    keywords: Mapped[list[Keyword]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[UserJobNotification]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Keyword(Base):
    __tablename__ = "keywords"
    __table_args__ = (UniqueConstraint("user_id", "text_normalized", name="uq_keyword_user_norm"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text_raw: Mapped[str] = mapped_column(String(512))
    text_normalized: Mapped[str] = mapped_column(String(512), index=True)

    user: Mapped[User] = relationship(back_populates="keywords")


class UserJobNotification(Base):
    __tablename__ = "user_job_notifications"
    __table_args__ = (UniqueConstraint("user_id", "job_url", name="uq_user_job_url"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_url: Mapped[str] = mapped_column(Text, index=True)
    source_site: Mapped[str] = mapped_column(String(128))
    title_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    notified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="notifications")
