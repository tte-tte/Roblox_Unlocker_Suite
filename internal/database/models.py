from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AccountModel(Base):
    __tablename__: str = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(256), nullable=False)
    proxy: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    outlook_email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="IDLE", nullable=False)
    lock_type: Mapped[str] = mapped_column(String(64), default="UNKNOWN", nullable=False)
    roblosecurity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qr_code_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    challenge_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Optional[str | int]]:
        updated_iso: str = self.updated_at.strftime("%H:%M:%S") if self.updated_at else ""
        return {
            "id": self.id,
            "username": self.username,
            "password": self.password,
            "proxy": self.proxy or "Direct",
            "outlook_email": self.outlook_email or "None",
            "status": self.status,
            "lock_type": self.lock_type,
            "has_cookie": "YES" if self.roblosecurity else "NO",
            "qr_code_url": self.qr_code_url or "",
            "challenge_metadata": self.challenge_metadata or "",
            "screenshot_path": self.screenshot_path or "",
            "last_error": self.last_error or "",
            "updated_at": updated_iso
        }