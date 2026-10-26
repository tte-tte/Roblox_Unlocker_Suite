import logging
import random
import string
from pathlib import Path
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from config.settings import settings
from database.models import Base, AccountModel

logger: logging.Logger = logging.getLogger("roblox_suite.database")

DEMO_LOCK_ENABLED: bool = False
ALLOWED_DEMO_ACCOUNTS: frozenset[str] = frozenset({
    "bl0xfrui1_2025",
    "plikcog3190",
    "plixgale6817"
})

engine: AsyncEngine = create_async_engine(settings.database_url, echo=False)
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


class AccountRepository:
    @staticmethod
    async def init_db() -> None:
        try:
            Path("data").mkdir(parents=True, exist_ok=True)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema initialized successfully.")
        except Exception as exc:
            logger.error(f"Database initialization error: {exc}")
            raise

    @staticmethod
    def load_proxies_list() -> list[str]:
        proxy_path: Path = Path(settings.proxies_file_path)
        if not proxy_path.exists():
            return []
        try:
            return [line.strip() for line in proxy_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception:
            return []

    @staticmethod
    async def sync_from_file() -> int:
        added_count: int = 0
        file_path: Path = Path(settings.accounts_file_path)
        if not file_path.exists():
            logger.warning(f"Accounts file not found at {file_path}")
            return added_count

        proxies: list[str] = AccountRepository.load_proxies_list()

        try:
            raw_lines: list[str] = file_path.read_text(encoding="utf-8").splitlines()
            async with async_session_factory() as session:
                for idx, line in enumerate(raw_lines):
                    cleaned: str = line.strip()
                    if not cleaned or ":" not in cleaned:
                        continue
                    parts: list[str] = cleaned.split(":", 1)
                    username: str = parts[0].strip()
                    password: str = parts[1].strip()
                    if not username or not password:
                        continue

                    assigned_proxy: Optional[str] = proxies[idx % len(proxies)] if proxies else None
                    is_allowed: bool = (not DEMO_LOCK_ENABLED) or (username.lower() in ALLOWED_DEMO_ACCOUNTS)
                    init_status: str = "READY" if is_allowed else "DEMO_LOCKED"
                    init_lock: str = "PENDING_CHECK" if is_allowed else "UPGRADE_REQUIRED"
                    init_meta: str = "" if is_allowed else "Locked in Test Package"

                    stmt = select(AccountModel).where(AccountModel.username == username)
                    result = await session.execute(stmt)
                    existing: Optional[AccountModel] = result.scalar_one_or_none()
                    if existing is None:
                        new_acc: AccountModel = AccountModel(
                            username=username,
                            password=password,
                            proxy=assigned_proxy,
                            status=init_status,
                            lock_type=init_lock,
                            challenge_metadata=init_meta
                        )
                        session.add(new_acc)
                        added_count += 1
                    else:
                        existing.password = password
                        if assigned_proxy:
                            existing.proxy = assigned_proxy
                        if is_allowed and existing.status == "DEMO_LOCKED":
                            existing.status = "READY"
                            existing.lock_type = "PENDING_CHECK"
                            existing.challenge_metadata = ""
                await session.commit()
            logger.info(f"Synchronized accounts from file. Newly added: {added_count}")
            return added_count
        except Exception as exc:
            logger.error(f"Failed to sync accounts from file: {exc}")
            return added_count

    @staticmethod
    async def generate_accounts_batch(count: int, prefix: str = "RblxPlayer") -> int:
        created: int = 0
        proxies: list[str] = AccountRepository.load_proxies_list()
        file_path: Path = Path(settings.accounts_file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        clean_prefix: str = "".join(ch for ch in prefix if ch.isalnum())[:10] or "RblxUser"
        new_lines: list[str] = []

        try:
            async with async_session_factory() as session:
                for i in range(max(1, min(count, 500))):
                    rand_digits: str = "".join(random.choices(string.digits, k=6))
                    rand_letters: str = "".join(random.choices(string.ascii_lowercase, k=3))
                    username: str = f"{clean_prefix}_{rand_letters}{rand_digits}"[:20]
                    password: str = "Rblx_" + "".join(
                        random.choices(string.ascii_letters + string.digits, k=11)
                    )
                    assigned_proxy: Optional[str] = proxies[i % len(proxies)] if proxies else None

                    new_acc: AccountModel = AccountModel(
                        username=username,
                        password=password,
                        proxy=assigned_proxy,
                        status="READY",
                        lock_type="GENERATED_NEW",
                        challenge_metadata="Ready for Auto-Registration / Login"
                    )
                    session.add(new_acc)
                    new_lines.append(f"{username}:{password}")
                    created += 1
                await session.commit()

            with file_path.open("a", encoding="utf-8") as f:
                for item_line in new_lines:
                    f.write(f"\n{item_line}")

            logger.info(f"Generated {created} new accounts and appended to {file_path}")
            return created
        except Exception as exc:
            logger.error(f"Error generating accounts batch: {exc}")
            return created

    @staticmethod
    async def get_all_accounts() -> list[dict[str, Optional[str | int]]]:
        try:
            async with async_session_factory() as session:
                stmt = select(AccountModel).order_by(AccountModel.id.asc())
                result = await session.execute(stmt)
                records: Sequence[AccountModel] = result.scalars().all()
                return [item.to_dict() for item in records]
        except Exception as exc:
            logger.error(f"Error fetching accounts list: {exc}")
            return []

    @staticmethod
    async def get_account_by_id(account_id: int) -> Optional[AccountModel]:
        try:
            async with async_session_factory() as session:
                stmt = select(AccountModel).where(AccountModel.id == account_id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"Error fetching account {account_id}: {exc}")
            return None

    @staticmethod
    async def update_account_state(
        account_id: int,
        status: str,
        lock_type: Optional[str] = None,
        roblosecurity: Optional[str] = None,
        qr_code_url: Optional[str] = None,
        challenge_metadata: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        last_error: Optional[str] = None
    ) -> Optional[dict[str, Optional[str | int]]]:
        try:
            async with async_session_factory() as session:
                stmt = select(AccountModel).where(AccountModel.id == account_id)
                result = await session.execute(stmt)
                account: Optional[AccountModel] = result.scalar_one_or_none()
                if account is None:
                    return None

                account.status = status
                if lock_type is not None:
                    account.lock_type = lock_type
                if roblosecurity is not None:
                    account.roblosecurity = roblosecurity
                if qr_code_url is not None:
                    account.qr_code_url = qr_code_url
                if challenge_metadata is not None:
                    account.challenge_metadata = challenge_metadata
                if screenshot_path is not None:
                    account.screenshot_path = screenshot_path
                if last_error is not None:
                    account.last_error = last_error

                await session.commit()
                await session.refresh(account)
                return account.to_dict()
        except Exception as exc:
            logger.error(f"Failed to update state for account {account_id}: {exc}")
            return None