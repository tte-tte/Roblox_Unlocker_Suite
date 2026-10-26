import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

logger: logging.Logger = logging.getLogger("roblox_suite.config")


class Settings(BaseModel):
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/roblox_manager.db")
    accounts_file_path: str = os.getenv("ACCOUNTS_FILE_PATH", "data/accounts.txt")
    proxies_file_path: str = os.getenv("PROXIES_FILE_PATH", "data/proxies.txt")
    outlooks_file_path: str = os.getenv("OUTLOOKS_FILE_PATH", "data/outlooks.txt")
    screenshots_dir: str = os.getenv("SCREENSHOTS_DIR", "data/screenshots")

    browser_headless: bool = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
    browser_timeout_ms: int = int(os.getenv("BROWSER_TIMEOUT_MS", "30000"))
    max_concurrent_browsers: int = int(os.getenv("MAX_CONCURRENT_BROWSERS", "1"))
    press_and_hold_duration_sec: float = float(os.getenv("PRESS_AND_HOLD_DURATION_SEC", "5.8"))

    roblox_login_url: str = os.getenv("ROBLOX_LOGIN_URL", "https://www.roblox.com/login")
    roblox_not_approved_path: str = os.getenv("ROBLOX_NOT_APPROVED_PATH", "/not-approved")
    roblox_home_path: str = os.getenv("ROBLOX_HOME_PATH", "/home")

    selector_username_input: str = os.getenv("SELECTOR_USERNAME_INPUT", 'input[id="login-username"]')
    selector_password_input: str = os.getenv("SELECTOR_PASSWORD_INPUT", 'input[id="login-password"]')
    selector_login_button: str = os.getenv("SELECTOR_LOGIN_BUTTON", 'button[id="login-button"]')
    selector_cookie_banner_accept: str = os.getenv(
        "SELECTOR_COOKIE_BANNER_ACCEPT",
        "button.btn-cta-lg.cookie-btn.btn-primary-md"
    )
    selector_arkose_iframe: str = os.getenv(
        "SELECTOR_ARKOSE_IFRAME",
        'iframe[id="arkose-iframe"], iframe[src*="arkoselabs"], iframe[src*="funcaptcha"], iframe[title*="Verification"]'
    )
    selector_locked_modal_continue: str = os.getenv(
        "SELECTOR_LOCKED_MODAL_CONTINUE",
        'div.modal-content button.btn-primary-md, button:has-text("Continue")'
    )
    selector_agreement_button: str = os.getenv("SELECTOR_AGREEMENT_BUTTON", 'button:has-text("I Agree")')
    selector_qr_modal_container: str = os.getenv("SELECTOR_QR_MODAL_CONTAINER", 'div.modal-content, div[role="dialog"]')


def load_settings() -> Settings:
    try:
        instance: Settings = Settings()
        screenshots_path: Path = Path(instance.screenshots_dir)
        screenshots_path.mkdir(parents=True, exist_ok=True)
        return instance
    except Exception as exc:
        logger.error(f"Failed to initialize application settings: {exc}")
        raise


settings: Settings = load_settings()